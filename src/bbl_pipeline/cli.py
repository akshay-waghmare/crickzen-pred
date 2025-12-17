import click
from pathlib import Path
import structlog
from datetime import datetime, timezone
import time
import json
import pandas as pd
import numpy as np

from bbl_pipeline.config import load_config
from bbl_pipeline.utils.logging import configure_logging
from bbl_pipeline.ingestion.loader import iter_match_files, load_match_file
from bbl_pipeline.ingestion.processor import process_match
from bbl_pipeline.ingestion.writer import write_parquet
from bbl_pipeline.ingestion.state import IngestionState
from bbl_pipeline.utils.errors import ErrorHandler
from bbl_pipeline.processing.registry import EntityRegistry
from bbl_pipeline.processing.resolution import EntityResolver

logger = structlog.get_logger()

@click.group()
@click.option('--config', type=click.Path(exists=True), help='Path to config file')
@click.pass_context
def main(ctx, config):
    """BBL Data Pipeline CLI"""
    ctx.ensure_object(dict)
    cfg = load_config(Path(config) if config else None)
    ctx.obj['config'] = cfg
    configure_logging(cfg.log_level)

@main.command()
@click.option('--input-dir', type=click.Path(exists=True), help='Input directory containing JSON files')
@click.option('--output-dir', type=click.Path(), help='Output directory for Parquet files')
@click.option('--incremental', is_flag=True, help='Only process new or modified files')
@click.pass_context
def ingest(ctx, input_dir, output_dir, incremental):
    """Ingest Cricsheet JSON files and convert to Parquet."""
    cfg = ctx.obj['config']
    input_path = Path(input_dir) if input_dir else cfg.input_dir
    output_path = Path(output_dir) if output_dir else cfg.output_dir
    is_incremental = incremental or cfg.incremental
    
    # Ensure output directory exists
    output_path.mkdir(parents=True, exist_ok=True)
    
    state = IngestionState(output_path / "ingestion_state.json")
    error_handler = ErrorHandler(cfg.error_policy)

    # Initialize Entity Resolution
    registry_path = output_path / "entity_registry.json"
    registry = EntityRegistry.load(registry_path)
    resolver = EntityResolver(registry)
    
    summary = {
        "total_files_scanned": 0,
        "processed": 0,
        "skipped_incremental": 0,
        "errors": 0,
        "start_time": datetime.now(timezone.utc).isoformat()
    }
    start_time = time.time()
    
    # Buffers for chunked writing
    main_buffer = []
    super_over_buffer = []
    processed_files_buffer = []
    
    CHUNK_SIZE = 50 # Number of files to process before writing
    
    def flush_buffers():
        if not processed_files_buffer:
            return
            
        source_files = [p.name for p in processed_files_buffer]
        
        # Write main matches
        if main_buffer:
            write_parquet(
                main_buffer, 
                output_path / "matches", 
                source_files=source_files,
                partition_cols=['season']
            )
            
        # Write super overs
        if super_over_buffer:
            write_parquet(
                super_over_buffer, 
                output_path / "super_overs", 
                source_files=source_files,
                partition_cols=['season']
            )
            
        # Update state
        for p in processed_files_buffer:
            state.mark_processed(p)
        state.save()
        
        # Clear buffers
        main_buffer.clear()
        super_over_buffer.clear()
        processed_files_buffer.clear()

    try:
        logger.info("Starting ingestion", input_dir=str(input_path), incremental=is_incremental)
        
        for file_path in iter_match_files(input_path):
            summary["total_files_scanned"] += 1
            
            if is_incremental and state.is_processed(file_path):
                summary["skipped_incremental"] += 1
                continue
                
            try:
                data = load_match_file(file_path)
                match_id = file_path.stem
                
                main_recs, super_recs = process_match(data, match_id, resolver)
                
                main_buffer.extend(main_recs)
                super_over_buffer.extend(super_recs)
                processed_files_buffer.append(file_path)
                summary["processed"] += 1
                
                if len(processed_files_buffer) >= CHUNK_SIZE:
                    flush_buffers()
                    
            except Exception as e:
                summary["errors"] += 1
                error_handler.handle(e, {"file": str(file_path)})
        
        # Flush remaining records
        flush_buffers()

    finally:
        duration = time.time() - start_time
        summary["duration_seconds"] = round(duration, 2)
        summary["end_time"] = datetime.now(timezone.utc).isoformat()
        
        logger.info("Ingestion completed", **summary)
        
        # Save summary report
        with open(output_path / "ingestion_summary.json", "w") as f:
            json.dump(summary, f, indent=2)
            
        # Save entity registry
        registry.save(registry_path)

@main.command()
@click.option('--input-dir', type=click.Path(exists=True), help='Input directory containing JSON files')
@click.pass_context
def resolve(ctx, input_dir):
    """Scan for entities and resolve against registry."""
    cfg = ctx.obj['config']
    input_path = Path(input_dir) if input_dir else cfg.input_dir
    
    # Initialize Registry
    output_path = Path(cfg.output_dir)
    registry_path = output_path / "entity_registry.json"
    registry = EntityRegistry.load(registry_path)
    resolver = EntityResolver(registry)
    
    logger.info("Starting entity resolution scan", input_dir=str(input_path))
    
    unique_players = set()
    unique_teams = set()
    unique_venues = set()
    
    # Scan files
    count = 0
    for file_path in iter_match_files(input_path):
        try:
            data = load_match_file(file_path)
            info = data.get('info', {})
            
            # Teams
            for team in info.get('teams', []):
                unique_teams.add(team)
                
            # Venue
            if 'venue' in info:
                unique_venues.add(info['venue'])
                
            # Players
            if 'registry' in info and 'people' in info['registry']:
                for name in info['registry']['people']:
                    unique_players.add(name)
            else:
                # Fallback to scanning deliveries
                for inning in data.get('innings', []):
                    for over in inning.get('overs', []):
                        for delivery in over.get('deliveries', []):
                            if 'batter' in delivery: unique_players.add(delivery['batter'])
                            if 'bowler' in delivery: unique_players.add(delivery['bowler'])
                            if 'non_striker' in delivery: unique_players.add(delivery['non_striker'])
                            
            count += 1
            if count % 100 == 0:
                logger.info(f"Scanned {count} files...")
                
        except Exception as e:
            logger.error(f"Error scanning file {file_path}: {e}")
            
    logger.info("Scan complete", files=count, players=len(unique_players), teams=len(unique_teams), venues=len(unique_venues))
    
    # Resolve and Report
    logger.info("Resolving entities...")
    
    unknown_players = []
    unknown_teams = []
    unknown_venues = []
    
    for p in unique_players:
        pid, score = resolver.resolve_player(p)
        if not pid:
            unknown_players.append(p)
            
    for t in unique_teams:
        tid, score = resolver.resolve_team(t)
        if not tid:
            unknown_teams.append(t)
            
    for v in unique_venues:
        vid, score = resolver.resolve_venue(v)
        if not vid:
            unknown_venues.append(v)
            
    print(f"\n--- Entity Resolution Report ---")
    print(f"Total Players: {len(unique_players)}")
    print(f"Unknown Players: {len(unknown_players)}")
    if unknown_players:
        print(f"Sample Unknown: {unknown_players[:10]}")
        
    print(f"\nTotal Teams: {len(unique_teams)}")
    print(f"Unknown Teams: {len(unknown_teams)}")
    if unknown_teams:
        print(f"Sample Unknown: {unknown_teams[:10]}")

    print(f"\nTotal Venues: {len(unique_venues)}")
    print(f"Unknown Venues: {len(unknown_venues)}")
    if unknown_venues:
        print(f"Sample Unknown: {unknown_venues[:10]}")

@main.command()
@click.option('--data-dir', type=click.Path(exists=True), help='Directory containing Parquet files')
@click.pass_context
def validate(ctx, data_dir):
    """Validate processed data against schema."""
    cfg = ctx.obj['config']
    data_path = Path(data_dir) if data_dir else Path(cfg.output_dir)
    
    from bbl_pipeline.validation.schema import MatchSchema
    import pandera as pa
    
    logger.info("Starting validation", data_dir=str(data_path))
    
    # Validate matches
    matches_path = data_path / "matches"
    if matches_path.exists():
        try:
            # Read parquet dataset (handles partitioning)
            df = pd.read_parquet(matches_path)
            logger.info(f"Validating {len(df)} match records...")
            MatchSchema.validate(df, lazy=True)
            logger.info("Matches validation passed!")
        except pa.errors.SchemaErrors as err:
            logger.error("Matches validation failed!")
            # Log a sample of errors
            logger.error(f"Schema errors found: {len(err.failure_cases)}")
            logger.error(err.failure_cases.head().to_string())
        except Exception as e:
            logger.error(f"Error validating matches: {e}")
    else:
        logger.warning(f"No matches found at {matches_path}")
        
    # Validate super overs
    so_path = data_path / "super_overs"
    if so_path.exists():
        try:
            df = pd.read_parquet(so_path)
            logger.info(f"Validating {len(df)} super over records...")
            MatchSchema.validate(df, lazy=True)
            logger.info("Super overs validation passed!")
        except pa.errors.SchemaErrors as err:
            logger.error("Super overs validation failed!")
            logger.error(f"Schema errors found: {len(err.failure_cases)}")
            logger.error(err.failure_cases.head().to_string())
        except Exception as e:
            logger.error(f"Error validating super overs: {e}")

@main.command()
@click.option('--input-dir', required=True, help="Directory containing raw parquet files (e.g. data/bbl_raw/matches)")
@click.option('--output-dir', required=True, help="Directory to save training data")
@click.option('--feature-store-dir', required=True, help="Directory to save feature store artifacts")
def process(input_dir, output_dir, feature_store_dir):
    """Process raw data into training features."""
    from bbl_pipeline.data.processor import process_bbl_data
    
    try:
        process_bbl_data(
            Path(input_dir), 
            Path(output_dir), 
            Path(feature_store_dir)
        )
        click.echo("Data processing complete.")
    except Exception as e:
        logger.error("Processing failed", error=str(e))
        raise click.ClickException(str(e))

@main.command()
@click.option('--input-file', type=click.Path(exists=True), required=True, help='Path to training dataset (parquet)')
@click.option('--output-dir', type=click.Path(), required=True, help='Directory to save model artifacts')
@click.option('--calibration/--no-calibration', default=False, help='Enable/disable post-hoc calibration. Default: no calibration (best Brier)')
@click.pass_context
def train(ctx, input_file, output_dir, calibration):
    """
    Train, evaluate, and select the champion model.
    """
    from bbl_pipeline.training.trainer import Trainer
    from bbl_pipeline.training.selection import select_champion
    import joblib
    import json
    
    input_path = Path(input_file)
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    logger.info("Loading training data", path=str(input_path))
    df = pd.read_parquet(input_path)
    
    # Assume 'is_winner' is target
    target_col = 'is_winner'
    if target_col not in df.columns:
        raise ValueError(f"Target column '{target_col}' not found in dataset.")
    
    y = df[target_col]
    X = df.drop(columns=[target_col])
    
    # Default: no calibration (best Brier score)
    trainer = Trainer(use_calibration=calibration)

    if not calibration:
        logger.info("Training without post-hoc calibration (best Brier score)")
    else:
        logger.info("Training with post-hoc calibration enabled")
    
    results = trainer.evaluate_models(X, y)
    
    champion_meta = select_champion(results)
    champion_name = champion_meta['model_name']
    
    logger.info(f"Champion selected: {champion_name}")
    
    # Train final model
    final_model = trainer.train_final_model(champion_name, X, y)
    
    # Save artifacts
    model_path = output_path / "champion_model.joblib"
    joblib.dump(final_model, model_path)
    
    # Save metadata
    # Convert numpy types to python types for JSON serialization
    def convert_types(obj):
        if isinstance(obj, (pd.DataFrame, pd.Series)):
            return obj.to_dict()
        if isinstance(obj, np.integer):
            return int(obj)
        if isinstance(obj, np.floating):
            return float(obj)
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        return str(obj)

    meta_path = output_path / "champion_metadata.json"
    with open(meta_path, 'w') as f:
        json.dump(champion_meta, f, indent=2, default=convert_types)
        
    logger.info("Training complete", output_dir=str(output_path))

@main.command()
@click.option('--model-dir', type=click.Path(exists=True), required=True)
@click.option('--venue', required=True)
@click.option('--batting', required=True)
@click.option('--bowling', required=True)
@click.option('--score', required=True, help="Format: runs/wickets e.g. 120/3")
@click.option('--over', required=True, type=float, help="Format: over.ball e.g. 14.2")
@click.option('--batsman1', default="Unknown", help="Name of striker")
@click.option('--batsman2', default="Unknown", help="Name of non-striker")
@click.option('--bowler', default="Unknown", help="Name of bowler")
def predict(model_dir, venue, batting, bowling, score, over, batsman1, batsman2, bowler):
    """Predict win probability."""
    from bbl_pipeline.inference.predictor import Predictor
    from bbl_pipeline.inference.schema import MatchState
    
    # Parse score
    try:
        if '/' in score:
            runs, wickets = map(int, score.split('/'))
        else:
            runs = int(score)
            wickets = 0
    except ValueError:
        raise click.BadParameter("Score must be in format runs/wickets (e.g. 120/3) or runs (e.g. 120)")
        
    # Parse over
    ov = int(over)
    ball = int(round((over - ov) * 10))
    if ball > 6: # Allow extras?
        pass 
    
    state = MatchState(
        match_id="cli_prediction",
        venue=venue,
        batting_team=batting,
        bowling_team=bowling,
        innings=1, # Default to 1
        over=ov,
        ball=ball,
        current_score=runs,
        wickets_lost=wickets,
        batsman_1=batsman1, 
        batsman_2=batsman2,
        bowler=bowler
    )
    
    try:
        predictor = Predictor.load(model_dir)
        prob = predictor.predict(state)
        click.echo(f"Win Probability for {batting}: {prob:.2%}")
    except Exception as e:
        logger.error(f"Prediction failed: {e}")
        click.echo(f"Error: {e}")

@main.command()
@click.option('--model-dir', type=click.Path(exists=True), required=True)
@click.option('--test-data', type=click.Path(exists=True), required=True)
def evaluate(model_dir, test_data):
    """Evaluate model on hold-out test set."""
    from bbl_pipeline.inference.predictor import Predictor
    from bbl_pipeline.inference.schema import MatchState
    from bbl_pipeline.training.evaluation import expected_calibration_error
    from sklearn.metrics import brier_score_loss, log_loss, roc_auc_score
    
    logger.info("Loading model and test data...")
    predictor = Predictor.load(model_dir)
    df = pd.read_parquet(test_data)
    
    target_col = 'is_winner'
    if target_col not in df.columns:
        raise ValueError(f"Target column '{target_col}' not found.")
    
    y_true = df[target_col]
    X = df.drop(columns=[target_col])
    
    # Predict
    # Predictor expects MatchState, but here we have a DataFrame.
    # We can use the underlying model directly if we hydrate features manually?
    # Or we construct MatchState for each row? (Slow)
    # Or we assume X is already features?
    
    # If X is raw data, we need hydration.
    # Predictor._hydrate_features takes MatchState.
    # We should probably expose a batch prediction method in Predictor that takes DataFrame?
    # Or assume X is already hydrated features matching training schema?
    
    # If 'test-data' is the output of feature engineering, it has features.
    # But Predictor uses FeatureStore.
    
    # If we are evaluating the *model artifact* (which is CalibratedModel), we can just use model.predict_proba(X).
    # Assuming X has the right columns.
    
    try:
        # We access the underlying model directly for batch evaluation
        # This assumes X columns match what the model expects.
        y_prob = predictor.model.predict_proba(X)[:, 1]
        
        brier = brier_score_loss(y_true, y_prob)
        ll = log_loss(y_true, y_prob)
        auc = roc_auc_score(y_true, y_prob)
        ece = expected_calibration_error(y_true, y_prob)
        
        click.echo(f"Evaluation Results:")
        click.echo(f"Brier Score: {brier:.4f}")
        click.echo(f"Log Loss:    {ll:.4f}")
        click.echo(f"AUC:         {auc:.4f}")
        click.echo(f"ECE:         {ece:.4f}")
        
    except Exception as e:
        logger.error(f"Evaluation failed: {e}")
        click.echo(f"Error: {e}")

@main.command()
@click.option('--input-file', required=True, help='Path to training dataset (parquet)')
@click.option('--model-name', default='rf', help='Model to analyze (rf, xgboost, logreg)')
def analyze(input_file, model_name):
    """Analyze feature importance."""
    from bbl_pipeline.training.trainer import Trainer
    
    df = pd.read_parquet(input_file)
    target_col = 'is_winner'
    
    if target_col not in df.columns:
        raise click.ClickException(f"Target '{target_col}' not found in dataset")
        
    y = df[target_col]
    X = df.drop(columns=[target_col])
    
    trainer = Trainer()
    try:
        importance = trainer.get_feature_importance(model_name, X, y)
        if importance.empty:
            click.echo("No feature importance available for this model.")
        else:
            click.echo(f"\nFeature Importance ({model_name}):")
            click.echo(importance.to_string(index=False))
            
            # Save to CSV
            output_csv = Path(input_file).parent / f"feature_importance_{model_name}.csv"
            importance.to_csv(output_csv, index=False)
            click.echo(f"\nSaved to {output_csv}")
            
    except Exception as e:
        raise click.ClickException(str(e))


@main.command(name='generate-oof')
@click.option('--input-file', type=click.Path(exists=True), required=True, help='Path to training dataset (parquet)')
@click.option('--model-dir', type=click.Path(exists=True), required=True, help='Model directory containing champion_model.joblib')
@click.option('--n-splits', type=int, default=5, show_default=True, help='Number of folds for OOF predictions')
@click.option('--target-col', default='is_winner', show_default=True, help='Target column name')
def generate_oof(input_file, model_dir, n_splits, target_col):
    """Generate an OOF isotonic calibrator (models/.../isotonic_calibrator.pkl) for an existing model."""
    from sklearn.model_selection import KFold
    from sklearn.isotonic import IsotonicRegression
    from sklearn.base import clone
    from sklearn.metrics import brier_score_loss
    from bbl_pipeline.training.evaluation import expected_calibration_error
    from bbl_pipeline.training.calibration import CalibratedModel
    import joblib

    input_path = Path(input_file)
    model_path = Path(model_dir)
    champion_path = model_path / 'champion_model.joblib'
    if not champion_path.exists():
        raise click.ClickException(f"champion_model.joblib not found at {champion_path}")

    logger.info('Loading training data', path=str(input_path))
    df = pd.read_parquet(input_path)
    if target_col not in df.columns:
        raise click.ClickException(f"Target column '{target_col}' not found in dataset")

    y = df[target_col]

    # Drop obviously-non-feature columns if present
    X = df.drop(columns=[target_col])
    for col in list(X.columns):
        if str(col).startswith('__'):
            X = X.drop(columns=[col])

    # Keep numeric features only (models expect numeric)
    X = X.select_dtypes(include=[np.number]).fillna(0)

    logger.info('Loading champion model', path=str(champion_path))
    champion_model = joblib.load(champion_path)

    # If the saved model is already a calibrated wrapper, use its base estimator for OOF.
    base_model_template = champion_model
    if isinstance(champion_model, CalibratedModel) and hasattr(champion_model, 'base_estimator'):
        base_model_template = champion_model.base_estimator
        logger.warning('Model appears already calibrated; generating OOF calibrator from base_estimator. For BBL-style inference, champion_model.joblib should be uncalibrated.')

    # If the base model has an explicit feature list, align X to those columns.
    selected_features = None
    if hasattr(base_model_template, 'selected_features_') and base_model_template.selected_features_:
        selected_features = [c for c in base_model_template.selected_features_ if c in X.columns]
    elif hasattr(base_model_template, 'feature_names_in_') and base_model_template.feature_names_in_ is not None:
        selected_features = [c for c in list(base_model_template.feature_names_in_) if c in X.columns]

    if selected_features:
        X = X[selected_features]

    logger.info('Generating out-of-fold predictions', n_splits=n_splits, rows=len(X), features=X.shape[1])
    kf = KFold(n_splits=n_splits, shuffle=False)
    oof_probs = np.zeros(len(y), dtype=float)

    for fold_idx, (train_idx, val_idx) in enumerate(kf.split(X), start=1):
        model = clone(base_model_template)
        model.fit(X.iloc[train_idx], y.iloc[train_idx])
        oof_probs[val_idx] = model.predict_proba(X.iloc[val_idx])[:, 1]
        logger.info('OOF fold complete', fold=fold_idx, train_size=len(train_idx), val_size=len(val_idx))

    iso = IsotonicRegression(out_of_bounds='clip')
    iso.fit(oof_probs, y)

    # Report OOF calibration metrics (before/after)
    oof_brier_raw = float(brier_score_loss(y, oof_probs))
    oof_ece_raw = float(expected_calibration_error(y.values if hasattr(y, 'values') else y, oof_probs))
    oof_probs_cal = iso.predict(oof_probs)
    oof_brier_cal = float(brier_score_loss(y, oof_probs_cal))
    oof_ece_cal = float(expected_calibration_error(y.values if hasattr(y, 'values') else y, oof_probs_cal))

    logger.info(
        'OOF calibration metrics',
        brier_raw=oof_brier_raw,
        ece_raw=oof_ece_raw,
        brier_calibrated=oof_brier_cal,
        ece_calibrated=oof_ece_cal,
    )

    calibrator_out = model_path / 'isotonic_calibrator.pkl'
    joblib.dump(iso, calibrator_out)
    logger.info('Saved OOF isotonic calibrator', path=str(calibrator_out))

if __name__ == '__main__':
    main()
