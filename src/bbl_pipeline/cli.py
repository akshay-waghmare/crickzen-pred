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


@main.command(name='analyze-oof')
@click.option('--input-file', type=click.Path(exists=True), required=True, help='Path to training dataset (parquet)')
@click.option('--model-dir', type=click.Path(exists=True), required=True, help='Model directory containing champion_model.joblib')
@click.option('--n-splits', type=int, default=5, show_default=True, help='Number of folds for cross-validation')
@click.option('--target-col', default='is_winner', show_default=True, help='Target column name')
@click.option('--innings-col', default='innings', show_default=True, help='Innings column name (optional)')
@click.option('--overs-col', default='overs_remaining', show_default=True, help='Overs remaining column (optional, for phase analysis)')
def analyze_oof(input_file, model_dir, n_splits, target_col, innings_col, overs_col):
    """
    Comprehensive OOF calibration analysis comparing 7 methods:
    - Raw (uncalibrated)
    - Combined (single isotonic)
    - Innings-Specific (2 calibrators)
    - Innings×Phase (6 calibrators)
    - Brier-Optimized (per-over)
    - ECE-Optimized (histogram binning)
    - LogLoss-Optimized (Platt scaling)
    
    Generates detailed metrics breakdown by innings, phase, and overall.
    """
    from bbl_pipeline.training.oof_analyzer import OOFAnalyzer
    from sklearn.base import clone
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
    
    y = df[target_col].values
    
    # Get innings and overs columns if available
    innings = df[innings_col].values if innings_col in df.columns else None
    overs_remaining = df[overs_col].values if overs_col in df.columns else None
    
    # Get resource_win_prob if available (for baseline comparison)
    resource_win_prob = df['resource_win_prob'].values if 'resource_win_prob' in df.columns else None
    if resource_win_prob is not None:
        logger.info('Found resource_win_prob feature for baseline comparison')
    
    if overs_remaining is not None:
        # Calculate over number from overs_remaining
        over = np.ceil(20 - overs_remaining).astype(int) + 1
        over = np.clip(over, 1, 20)
    else:
        over = None
    
    # Prepare features
    X = df.drop(columns=[target_col])
    
    # Drop non-feature columns (but keep overs_remaining, is_powerplay, is_death_overs as they ARE features)
    # Only drop innings (metadata) and is_middle_overs (not used in model)
    non_feature_cols = [innings_col, 'is_middle_overs']
    for col in list(X.columns):
        if str(col).startswith('__') or col in non_feature_cols:
            if col in X.columns:
                X = X.drop(columns=[col])
    
    # Keep numeric features only
    X = X.select_dtypes(include=[np.number]).fillna(0)
    
    logger.info('Loading champion model', path=str(champion_path))
    champion_model = joblib.load(champion_path)
    
    # Extract base model if wrapped
    from bbl_pipeline.training.calibration import CalibratedModel
    base_model = champion_model
    if isinstance(champion_model, CalibratedModel) and hasattr(champion_model, 'base_estimator'):
        base_model = champion_model.base_estimator
        logger.info('Using base estimator from calibrated model')
    
    # Align features if model has feature list
    if hasattr(base_model, 'selected_features_') and base_model.selected_features_:
        selected_features = [c for c in base_model.selected_features_ if c in X.columns]
        X = X[selected_features]
    elif hasattr(base_model, 'feature_names_in_') and base_model.feature_names_in_ is not None:
        selected_features = [c for c in list(base_model.feature_names_in_) if c in X.columns]
        X = X[selected_features]
    
    logger.info('Starting OOF analysis', samples=len(X), features=X.shape[1], n_splits=n_splits)
    
    # Run analysis
    analyzer = OOFAnalyzer(
        model=base_model,
        X=X,
        y=y,
        innings=innings,
        over=over,
        resource_win_prob=resource_win_prob,
        n_splits=n_splits
    )
    
    calibrators, results_df = analyzer.run_analysis(output_dir=model_path)
    
    # Display summary
    click.echo("\n" + "="*80)
    click.echo("OOF CALIBRATION ANALYSIS COMPLETE")
    click.echo("="*80)
    
    # Overall results
    overall = results_df[results_df['segment'] == 'overall'].sort_values('brier')
    click.echo("\n📊 OVERALL PERFORMANCE:\n")
    click.echo(overall[['method', 'brier', 'ece', 'logloss']].to_string(index=False, float_format=lambda x: f'{x:.4f}'))
    
    # Rankings
    click.echo("\n🏆 RANKINGS:\n")
    click.echo(f"Best Brier:   {overall.iloc[0]['method']} ({overall.iloc[0]['brier']:.4f})")
    ece_best = overall.sort_values('ece').iloc[0]
    click.echo(f"Best ECE:     {ece_best['method']} ({ece_best['ece']:.4f})")
    ll_best = overall.sort_values('logloss').iloc[0]
    click.echo(f"Best LogLoss: {ll_best['method']} ({ll_best['logloss']:.4f})")
    
    click.echo(f"\n✅ Results saved to: {model_path}")
    click.echo(f"   - oof_calibration_results.csv (detailed metrics)")
    click.echo(f"   - oof_calibrators.pkl (trained calibrators)")
    click.echo(f"   - OOF_CALIBRATION_REPORT.md (markdown report)")


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

    # Check if innings column exists for innings-specific calibration
    has_innings = 'innings' in df.columns
    has_phase = all(col in df.columns for col in ['is_powerplay', 'is_death_overs'])
    has_overs = 'overs_remaining' in df.columns
    
    if has_innings:
        logger.info('Innings column detected - will generate innings-specific calibrators')
        innings_col = df['innings'].copy()
    
    if has_overs:
        logger.info('Overs column detected - will generate per-over (brier_optimized) calibrators')
        overs_remaining_col = df['overs_remaining'].copy()
        # Calculate over number from overs_remaining
        over_col = np.ceil(20 - overs_remaining_col.values).astype(int) + 1
        over_col = np.clip(over_col, 1, 20)
    
    if has_phase:
        logger.info('Phase columns detected - will generate innings×phase specific calibrators')
        powerplay_col = df['is_powerplay'].copy()
        death_col = df['is_death_overs'].copy()
    
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

    # Create innings-specific and innings×phase-specific calibrators
    if has_innings:
        # Train separate calibrators for each innings
        iso_inn1 = IsotonicRegression(y_min=0.01, y_max=0.99, out_of_bounds='clip')
        iso_inn2 = IsotonicRegression(y_min=0.01, y_max=0.99, out_of_bounds='clip')
        # Also train a combined calibrator for comparison
        iso_combined = IsotonicRegression(y_min=0.01, y_max=0.99, out_of_bounds='clip')
        
        mask_inn1 = (innings_col == 1).values
        mask_inn2 = (innings_col == 2).values
        
        iso_inn1.fit(oof_probs[mask_inn1], y.values[mask_inn1] if hasattr(y, 'values') else y[mask_inn1])
        iso_inn2.fit(oof_probs[mask_inn2], y.values[mask_inn2] if hasattr(y, 'values') else y[mask_inn2])
        iso_combined.fit(oof_probs, y)
        
        # Calculate innings-specific metrics
        oof_probs_cal_inn1 = iso_inn1.predict(oof_probs[mask_inn1])
        oof_probs_cal_inn2 = iso_inn2.predict(oof_probs[mask_inn2])
        
        y_inn1 = y.values[mask_inn1] if hasattr(y, 'values') else y[mask_inn1]
        y_inn2 = y.values[mask_inn2] if hasattr(y, 'values') else y[mask_inn2]
        
        inn1_brier_raw = float(brier_score_loss(y_inn1, oof_probs[mask_inn1]))
        inn1_ece_raw = float(expected_calibration_error(y_inn1, oof_probs[mask_inn1]))
        inn1_brier_cal = float(brier_score_loss(y_inn1, oof_probs_cal_inn1))
        inn1_ece_cal = float(expected_calibration_error(y_inn1, oof_probs_cal_inn1))
        
        inn2_brier_raw = float(brier_score_loss(y_inn2, oof_probs[mask_inn2]))
        inn2_ece_raw = float(expected_calibration_error(y_inn2, oof_probs[mask_inn2]))
        inn2_brier_cal = float(brier_score_loss(y_inn2, oof_probs_cal_inn2))
        inn2_ece_cal = float(expected_calibration_error(y_inn2, oof_probs_cal_inn2))
        
        logger.info(
            'Innings 1 calibration metrics',
            samples=int(mask_inn1.sum()),
            brier_raw=inn1_brier_raw,
            ece_raw=inn1_ece_raw,
            brier_calibrated=inn1_brier_cal,
            ece_calibrated=inn1_ece_cal,
        )
        logger.info(
            'Innings 2 calibration metrics',
            samples=int(mask_inn2.sum()),
            brier_raw=inn2_brier_raw,
            ece_raw=inn2_ece_raw,
            brier_calibrated=inn2_brier_cal,
            ece_calibrated=inn2_ece_cal,
        )
        
        # Store combined metrics for overall reporting
        oof_brier_raw = float(brier_score_loss(y, oof_probs))
        oof_ece_raw = float(expected_calibration_error(y.values if hasattr(y, 'values') else y, oof_probs))
        oof_probs_cal = oof_probs.copy()
        oof_probs_cal[mask_inn1] = oof_probs_cal_inn1
        oof_probs_cal[mask_inn2] = oof_probs_cal_inn2
        oof_brier_cal = float(brier_score_loss(y, oof_probs_cal))
        oof_ece_cal = float(expected_calibration_error(y.values if hasattr(y, 'values') else y, oof_probs_cal))
        
        # Generate innings×phase specific calibrators if phase columns exist
        phase_calibrators = {}
        phase_metrics = {}
        
        if has_phase:
            logger.info('Generating innings×phase specific calibrators')
            
            # Define phase masks
            powerplay_mask = (powerplay_col == 1).values
            death_mask = (death_col == 1).values
            middle_mask = ~powerplay_mask & ~death_mask
            
            # Train calibrator for each innings × phase combination
            for inn in [1, 2]:
                inn_mask = (innings_col == inn).values
                
                for phase_name, phase_mask in [('powerplay', powerplay_mask), 
                                                ('middle', middle_mask), 
                                                ('death', death_mask)]:
                    mask = inn_mask & phase_mask
                    if mask.sum() >= 10:  # Minimum samples requirement
                        cal = IsotonicRegression(y_min=0.01, y_max=0.99, out_of_bounds='clip')
                        y_phase = y.values[mask] if hasattr(y, 'values') else y[mask]
                        cal.fit(oof_probs[mask], y_phase)
                        
                        key = f'inn{inn}_{phase_name}'
                        phase_calibrators[key] = cal
                        
                        # Calculate metrics for this combination
                        probs_raw = oof_probs[mask]
                        probs_cal = cal.predict(probs_raw)
                        
                        phase_metrics[key] = {
                            'samples': int(mask.sum()),
                            'brier_raw': float(brier_score_loss(y_phase, probs_raw)),
                            'brier_calibrated': float(brier_score_loss(y_phase, probs_cal)),
                            'ece_raw': float(expected_calibration_error(y_phase, probs_raw)),
                            'ece_calibrated': float(expected_calibration_error(y_phase, probs_cal)),
                        }
                        
                        logger.info(
                            f'Phase calibrator: {key}',
                            samples=phase_metrics[key]['samples'],
                            brier_raw=phase_metrics[key]['brier_raw'],
                            brier_cal=phase_metrics[key]['brier_calibrated'],
                            ece_raw=phase_metrics[key]['ece_raw'],
                            ece_cal=phase_metrics[key]['ece_calibrated'],
                        )

        # Generate per-over (brier_optimized) calibrators if overs column exists
        per_over_calibrators = {}
        per_over_metrics = {}
        
        if has_overs:
            logger.info('Generating per-over (brier_optimized) calibrators')
            
            for inn in [1, 2]:
                inn_mask = (innings_col == inn).values
                
                for ov in range(1, 21):
                    mask = inn_mask & (over_col == ov)
                    if mask.sum() >= 30:  # Minimum samples requirement
                        cal = IsotonicRegression(y_min=0.01, y_max=0.99, out_of_bounds='clip')
                        y_over = y.values[mask] if hasattr(y, 'values') else y[mask]
                        cal.fit(oof_probs[mask], y_over)
                        
                        key = f'inn{inn}_over{ov}'
                        per_over_calibrators[key] = cal
                        
                        # Calculate metrics for this combination
                        probs_raw = oof_probs[mask]
                        probs_cal = cal.predict(probs_raw)
                        
                        per_over_metrics[key] = {
                            'samples': int(mask.sum()),
                            'brier_raw': float(brier_score_loss(y_over, probs_raw)),
                            'brier_calibrated': float(brier_score_loss(y_over, probs_cal)),
                            'ece_raw': float(expected_calibration_error(y_over, probs_raw)),
                            'ece_calibrated': float(expected_calibration_error(y_over, probs_cal)),
                        }
            
            logger.info(f'Generated {len(per_over_calibrators)} per-over calibrators')

    else:
        # Single calibrator for all data (backward compatible)
        iso = IsotonicRegression(out_of_bounds='clip')
        iso.fit(oof_probs, y)
        
        oof_brier_raw = float(brier_score_loss(y, oof_probs))
        oof_ece_raw = float(expected_calibration_error(y.values if hasattr(y, 'values') else y, oof_probs))
        oof_probs_cal = iso.predict(oof_probs)
        oof_brier_cal = float(brier_score_loss(y, oof_probs_cal))
        oof_ece_cal = float(expected_calibration_error(y.values if hasattr(y, 'values') else y, oof_probs_cal))

    logger.info(
        'Overall OOF calibration metrics',
        brier_raw=oof_brier_raw,
        ece_raw=oof_ece_raw,
        brier_calibrated=oof_brier_cal,
        ece_calibrated=oof_ece_cal,
    )

    # Store calibrator with metadata for model compatibility checking
    import hashlib
    feature_list = list(X.columns) if hasattr(X, 'columns') else []
    feature_hash = hashlib.md5('_'.join(sorted(feature_list)).encode()).hexdigest()
    
    if has_innings:
        # Innings-specific calibrators
        calibrator_metadata = {
            'type': 'innings_phase_specific' if (has_phase and phase_calibrators) else 'innings_specific',
            'calibrator_innings1': iso_inn1,
            'calibrator_innings2': iso_inn2,
            'calibrator_combined': iso_combined,  # For comparison
            'model_path': str(champion_path),
            'features': feature_list,
            'feature_hash': feature_hash,
            'n_features': len(feature_list),
            'created_date': pd.Timestamp.now().isoformat(),
            'oof_brier_raw': oof_brier_raw,
            'oof_brier_calibrated': oof_brier_cal,
            'oof_ece_raw': oof_ece_raw,
            'oof_ece_calibrated': oof_ece_cal,
            'innings1_metrics': {
                'samples': int(mask_inn1.sum()),
                'brier_raw': inn1_brier_raw,
                'brier_calibrated': inn1_brier_cal,
                'ece_raw': inn1_ece_raw,
                'ece_calibrated': inn1_ece_cal,
            },
            'innings2_metrics': {
                'samples': int(mask_inn2.sum()),
                'brier_raw': inn2_brier_raw,
                'brier_calibrated': inn2_brier_cal,
                'ece_raw': inn2_ece_raw,
                'ece_calibrated': inn2_ece_cal,
            },
        }
        
        # Add phase calibrators if available
        if has_phase and phase_calibrators:
            calibrator_metadata['phase_calibrators'] = phase_calibrators
            calibrator_metadata['phase_metrics'] = phase_metrics
            logger.info(f'Generated {len(phase_calibrators)} innings×phase calibrators')
        
        # Add per-over (brier_optimized) calibrators if available
        if has_overs and per_over_calibrators:
            calibrator_metadata['per_over_calibrators'] = per_over_calibrators
            calibrator_metadata['per_over_metrics'] = per_over_metrics
            logger.info(f'Added {len(per_over_calibrators)} per-over (brier_optimized) calibrators')
    else:
        # Single calibrator (backward compatible)
        calibrator_metadata = {
            'type': 'single',
            'calibrator': iso,
            'model_path': str(champion_path),
            'features': feature_list,
            'feature_hash': feature_hash,
            'n_features': len(feature_list),
            'created_date': pd.Timestamp.now().isoformat(),
            'oof_brier_raw': oof_brier_raw,
            'oof_brier_calibrated': oof_brier_cal,
            'oof_ece_raw': oof_ece_raw,
            'oof_ece_calibrated': oof_ece_cal,
        }
    
    calibrator_out = model_path / 'isotonic_calibrator.pkl'
    joblib.dump(calibrator_metadata, calibrator_out)
    if has_innings:
        cal_type = 'innings_phase_specific' if (has_phase and phase_calibrators) else 'innings_specific'
        logger.info(
            f'Saved {cal_type} calibrators with metadata',
            path=str(calibrator_out),
            feature_hash=feature_hash,
            type=cal_type,
            n_phase_calibrators=len(phase_calibrators) if phase_calibrators else 0
        )
    else:
        logger.info(
            'Saved OOF isotonic calibrator with metadata',
            path=str(calibrator_out),
            feature_hash=feature_hash,
            type='single'
        )
    
    # Update model registry with calibrator information
    try:
        registry_path = Path(__file__).parent.parent.parent / 'models' / 'model_registry.json'
        project_root = registry_path.parent.parent  # Go up from models/model_registry.json to project root
        
        if registry_path.exists():
            with open(registry_path, 'r') as f:
                registry = json.load(f)
            
            # Find model entry in registry by matching model_dir path
            # Normalize paths to use forward slashes for cross-platform compatibility
            try:
                model_dir_rel = str(model_path.relative_to(project_root)).replace('\\', '/')
            except ValueError:
                # If relative_to fails, try comparing absolute paths
                model_dir_abs = str(model_path.resolve()).replace('\\', '/')
                project_root_abs = str(project_root.resolve()).replace('\\', '/')
                if model_dir_abs.startswith(project_root_abs):
                    model_dir_rel = model_dir_abs[len(project_root_abs):].lstrip('/')
                else:
                    raise
            updated = False
            
            # Check active models
            for league, model_info in registry.get('active_models', {}).items():
                if model_info.get('path') == model_dir_rel:
                    model_info['calibrator'] = {
                        'path': f"{model_dir_rel}/isotonic_calibrator.pkl",
                        'type': 'isotonic_regression',
                        'generated_date': calibrator_metadata['created_date'],
                        'oof_metrics': {
                            'brier_raw': calibrator_metadata['oof_brier_raw'],
                            'brier_calibrated': calibrator_metadata['oof_brier_calibrated'],
                            'ece_raw': calibrator_metadata['oof_ece_raw'],
                            'ece_calibrated': calibrator_metadata['oof_ece_calibrated']
                        },
                        'n_features': calibrator_metadata['n_features'],
                        'feature_hash': calibrator_metadata['feature_hash']
                    }
                    updated = True
                    logger.info(f'Updated registry for {league} model', league=league)
                    break
            
            # Check archived models if not found in active
            if not updated:
                for league, model_info in registry.get('archived_models', {}).items():
                    if model_info.get('path') == model_dir_rel:
                        model_info['calibrator'] = {
                            'path': f"{model_dir_rel}/isotonic_calibrator.pkl",
                            'type': 'isotonic_regression',
                            'generated_date': calibrator_metadata['created_date'],
                            'oof_metrics': {
                                'brier_raw': calibrator_metadata['oof_brier_raw'],
                                'brier_calibrated': calibrator_metadata['oof_brier_calibrated'],
                                'ece_raw': calibrator_metadata['oof_ece_raw'],
                                'ece_calibrated': calibrator_metadata['oof_ece_calibrated']
                            },
                            'n_features': calibrator_metadata['n_features'],
                            'feature_hash': calibrator_metadata['feature_hash']
                        }
                        updated = True
                        logger.info(f'Updated registry for archived {league} model', league=league)
                        break
            
            if updated:
                # Update last_updated date
                from datetime import datetime
                registry['last_updated'] = datetime.now().strftime('%Y-%m-%d')
                
                # Write back to registry
                with open(registry_path, 'w') as f:
                    json.dump(registry, f, indent=2)
                logger.info('Model registry updated successfully')
            else:
                logger.warning(f'Model {model_dir_rel} not found in registry - skipping registry update')
    except Exception as e:
        logger.warning(f'Failed to update model registry: {e}')

@main.command()
@click.option('--source-dir', type=click.Path(exists=True), default='recently_played_30_male',
              help='Source directory containing recently played JSON files (default: recently_played_30_male)')
@click.option('--league', type=click.Choice(['bbl', 'sa20', 'ilt20', 'bpl', 'ssm', 'wpl', 'all']), required=True,
              help='League to extract matches for')
@click.option('--dry-run', is_flag=True, help='Show which files would be copied without actually copying')
@click.pass_context  
def update_matches(ctx, source_dir, league, dry_run):
    """
    Update league JSON folder with matches from recently_played folder.
    
    Scans the source directory for matches matching the specified league
    and copies them to the appropriate league folder (e.g., sat_male_json for SA20).
    Existing files are overwritten.
    
    Examples:
        bbl-pipeline update-matches --league sa20
        bbl-pipeline update-matches --league bbl --source-dir recently_played_30_male
        bbl-pipeline update-matches --league all --dry-run
    """
    import shutil
    
    source_path = Path(source_dir)
    
    # League name patterns to match in event.name
    league_patterns = {
        'bbl': ['Big Bash League'],
        'sa20': ['SA20'],
        'ilt20': ['International League T20', 'ILT20'],
        'bpl': ['Bangladesh Premier League', 'BPL'],
        'ssm': ['Super Smash'],
        'wpl': ['Women\'s Premier League', 'WPL'],
    }
    
    # Target directories for each league
    target_dirs = {
        'bbl': 'bbl_male_json',
        'sa20': 'sat_male_json',
        'ilt20': 'ilt_male_json',
        'bpl': 'bpl_male_json',
        'ssm': 'ssm_male_json',
        'wpl': 'wpl_female_json',
    }
    
    leagues_to_process = list(league_patterns.keys()) if league == 'all' else [league]
    
    total_copied = 0
    results = {}
    
    for lg in leagues_to_process:
        patterns = league_patterns[lg]
        target_dir = Path(target_dirs[lg])
        
        if not target_dir.exists():
            logger.warning(f'Target directory {target_dir} does not exist, creating it')
            if not dry_run:
                target_dir.mkdir(parents=True, exist_ok=True)
        
        matches_found = []
        
        for json_file in sorted(source_path.glob('*.json')):
            try:
                with open(json_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                event_name = data.get('info', {}).get('event', {}).get('name', '')
                match_type = data.get('info', {}).get('match_type', '')
                
                # Check if this matches any of the league patterns
                if any(pattern.lower() in event_name.lower() for pattern in patterns):
                    # Also check it's a T20 match
                    if match_type == 'T20':
                        match_num = data.get('info', {}).get('event', {}).get('match_number', '?')
                        teams = data.get('info', {}).get('teams', [])
                        dates = data.get('info', {}).get('dates', ['?'])
                        matches_found.append({
                            'file': json_file.name,
                            'match_num': match_num,
                            'teams': teams,
                            'date': dates[0] if dates else '?'
                        })
                        
            except Exception as e:
                logger.error(f'Error reading {json_file.name}: {e}')
        
        results[lg] = matches_found
        
        if matches_found:
            click.echo(f'\n{lg.upper()}: Found {len(matches_found)} matches')
            for m in matches_found:
                team_str = ' vs '.join(m['teams']) if m['teams'] else 'Unknown'
                click.echo(f"  {m['file']}: Match {m['match_num']} - {team_str} ({m['date']})")
            
            if not dry_run:
                for m in matches_found:
                    src = source_path / m['file']
                    dst = target_dir / m['file']
                    shutil.copy2(src, dst)
                    total_copied += 1
                click.echo(f'  Copied {len(matches_found)} files to {target_dir}')
        else:
            click.echo(f'\n{lg.upper()}: No matches found')
    
    # Summary
    if dry_run:
        total_would_copy = sum(len(m) for m in results.values())
        click.echo(f'\nDRY RUN: Would copy {total_would_copy} files total')
    else:
        click.echo(f'\nTotal: Copied {total_copied} files')


@main.command()
@click.option('--league', type=click.Choice(['bbl', 'sa20', 'ilt20', 'bpl', 'ssm', 'wpl']), required=True,
              help='League to retrain model for')
@click.option('--version', type=str, required=True,
              help='Model version (e.g., v2, v3). Creates models/<league>_<version>')
@click.option('--clean', is_flag=True, default=True,
              help='Delete existing raw/features before reprocessing (default: True)')
@click.option('--skip-ingest', is_flag=True, help='Skip ingestion step (use existing raw data)')
@click.option('--skip-process', is_flag=True, help='Skip processing step (use existing features)')
@click.option('--n-splits', type=int, default=5, help='Number of CV splits for OOF analysis')
@click.pass_context
def retrain(ctx, league, version, clean, skip_ingest, skip_process, n_splits):
    """
    Full retraining pipeline for a league model.
    
    Runs the complete pipeline: ingest → process → train → generate-oof → analyze-oof
    
    Examples:
        bbl-pipeline retrain --league sa20 --version v2
        bbl-pipeline retrain --league bbl --version v13 --skip-ingest
        bbl-pipeline retrain --league wpl --version v3 --n-splits 3
    """
    import shutil
    import subprocess
    import sys
    
    # League configurations
    league_config = {
        'bbl': {
            'json_dir': 'bbl_male_json',
            'raw_dir': 'data/bbl_raw',
            'features_dir': 'data/bbl_features',
            'feature_store_dir': 'data/bbl_feature_store',
            'model_prefix': 'bbl',
        },
        'sa20': {
            'json_dir': 'sat_male_json',
            'raw_dir': 'data/sat_raw',
            'features_dir': 'data/sat_features',
            'feature_store_dir': 'data/sat_feature_store',
            'model_prefix': 'sat',
        },
        'ilt20': {
            'json_dir': 'ilt_male_json',
            'raw_dir': 'data/ilt_raw',
            'features_dir': 'data/ilt_features',
            'feature_store_dir': 'data/ilt_feature_store',
            'model_prefix': 'ilt20',
        },
        'bpl': {
            'json_dir': 'bpl_male_json',
            'raw_dir': 'data/bpl_raw',
            'features_dir': 'data/bpl_features',
            'feature_store_dir': 'data/bpl_feature_store',
            'model_prefix': 'bpl',
        },
        'ssm': {
            'json_dir': 'ssm_male_json',
            'raw_dir': 'data/ssm_raw',
            'features_dir': 'data/ssm_features',
            'feature_store_dir': 'data/ssm_feature_store',
            'model_prefix': 'ssm',
        },
        'wpl': {
            'json_dir': 'wpl_female_json',
            'raw_dir': 'data/wpl_raw',
            'features_dir': 'data/wpl_features',
            'feature_store_dir': 'data/wpl_feature_store',
            'model_prefix': 'wpl',
        },
    }
    
    cfg = league_config[league]
    
    # Append version to directories
    features_dir = f"{cfg['features_dir']}_{version}"
    feature_store_dir = f"{cfg['feature_store_dir']}_{version}"
    model_dir = f"models/{cfg['model_prefix']}_{version}"
    
    click.echo(f"\n{'='*60}")
    click.echo(f"  RETRAINING {league.upper()} MODEL - {version}")
    click.echo(f"{'='*60}")
    click.echo(f"  JSON Source:    {cfg['json_dir']}")
    click.echo(f"  Raw Data:       {cfg['raw_dir']}")
    click.echo(f"  Features:       {features_dir}")
    click.echo(f"  Feature Store:  {feature_store_dir}")
    click.echo(f"  Model Output:   {model_dir}")
    click.echo(f"{'='*60}\n")
    
    # Count source files
    json_path = Path(cfg['json_dir'])
    if json_path.exists():
        json_count = len(list(json_path.glob('*.json')))
        click.echo(f"📁 Found {json_count} JSON files in {cfg['json_dir']}")
    else:
        click.echo(f"❌ JSON directory not found: {cfg['json_dir']}")
        return
    
    # Step 0: Clean if requested
    if clean and not skip_ingest:
        click.echo(f"\n🧹 Cleaning existing data...")
        for dir_path in [cfg['raw_dir'], features_dir, feature_store_dir]:
            p = Path(dir_path)
            if p.exists():
                shutil.rmtree(p)
                click.echo(f"   Deleted: {dir_path}")
    
    # Step 1: Ingest
    if not skip_ingest:
        click.echo(f"\n📥 Step 1/6: INGESTION (JSON → Parquet)")
        click.echo(f"   bbl-pipeline ingest --input-dir {cfg['json_dir']} --output-dir {cfg['raw_dir']}")
        result = subprocess.run([
            sys.executable, '-m', 'bbl_pipeline.cli', 'ingest',
            '--input-dir', cfg['json_dir'],
            '--output-dir', cfg['raw_dir']
        ], capture_output=False)
        if result.returncode != 0:
            click.echo(f"❌ Ingestion failed!")
            return
        click.echo(f"   ✅ Ingestion complete")
    else:
        click.echo(f"\n⏭️  Step 1/6: INGESTION (skipped)")
    
    # Step 2: Process
    if not skip_process:
        click.echo(f"\n⚙️  Step 2/6: PROCESSING (Parquet → Features)")
        click.echo(f"   bbl-pipeline process --input-dir {cfg['raw_dir']}/matches --output-dir {features_dir} --feature-store-dir {feature_store_dir}")
        result = subprocess.run([
            sys.executable, '-m', 'bbl_pipeline.cli', 'process',
            '--input-dir', f"{cfg['raw_dir']}/matches",
            '--output-dir', features_dir,
            '--feature-store-dir', feature_store_dir
        ], capture_output=False)
        if result.returncode != 0:
            click.echo(f"❌ Processing failed!")
            return
        click.echo(f"   ✅ Processing complete")
    else:
        click.echo(f"\n⏭️  Step 2/6: PROCESSING (skipped)")
    
    # Step 3: Train (without --calibration, calibration comes from generate-oof)
    click.echo(f"\n🎯 Step 3/6: TRAINING (Features → Model)")
    click.echo(f"   bbl-pipeline train --input-file {features_dir}/training.parquet --output-dir {model_dir}")
    result = subprocess.run([
        sys.executable, '-m', 'bbl_pipeline.cli', 'train',
        '--input-file', f"{features_dir}/training.parquet",
        '--output-dir', model_dir
    ], capture_output=False)
    if result.returncode != 0:
        click.echo(f"❌ Training failed!")
        return
    click.echo(f"   ✅ Training complete")
    
    # Step 4: Generate OOF
    click.echo(f"\n🔧 Step 4/6: GENERATE-OOF (Create calibrators for inference)")
    click.echo(f"   bbl-pipeline generate-oof --input-file {features_dir}/training.parquet --model-dir {model_dir}")
    result = subprocess.run([
        sys.executable, '-m', 'bbl_pipeline.cli', 'generate-oof',
        '--input-file', f"{features_dir}/training.parquet",
        '--model-dir', model_dir
    ], capture_output=False)
    if result.returncode != 0:
        click.echo(f"❌ Generate-OOF failed!")
        return
    click.echo(f"   ✅ Generate-OOF complete")
    
    # Step 5: Analyze OOF
    click.echo(f"\n📊 Step 5/6: ANALYZE-OOF (Detailed calibration analysis)")
    click.echo(f"   bbl-pipeline analyze-oof --input-file {features_dir}/training.parquet --model-dir {model_dir} --n-splits {n_splits}")
    result = subprocess.run([
        sys.executable, '-m', 'bbl_pipeline.cli', 'analyze-oof',
        '--input-file', f"{features_dir}/training.parquet",
        '--model-dir', model_dir,
        '--n-splits', str(n_splits)
    ], capture_output=False)
    if result.returncode != 0:
        click.echo(f"❌ Analyze-OOF failed!")
        return
    click.echo(f"   ✅ Analyze-OOF complete")
    
    # Step 6: Update Model Registry
    click.echo(f"\n📝 Step 6/6: UPDATING MODEL REGISTRY")
    
    # League name mapping for registry
    registry_league_names = {
        'bbl': 'BBL',
        'sa20': 'SAT',
        'ilt20': 'ILT20',
        'bpl': 'BPL',
        'ssm': 'SSM',
        'wpl': 'WPL',
    }
    
    registry_path = Path('models/model_registry.json')
    if registry_path.exists():
        try:
            with open(registry_path, 'r') as f:
                registry = json.load(f)
            
            league_key = registry_league_names.get(league, league.upper())
            
            # Read OOF results for metrics
            oof_results_path = Path(model_dir) / 'oof_calibration_results.csv'
            brier_score = None
            ece_score = None
            if oof_results_path.exists():
                oof_df = pd.read_csv(oof_results_path)
                # Get brier_optimized overall metrics
                brier_row = oof_df[(oof_df['method'] == 'brier_optimized') & (oof_df['segment'] == 'overall')]
                if len(brier_row) > 0:
                    brier_score = float(brier_row['brier'].iloc[0])
                    ece_score = float(brier_row['ece'].iloc[0])
            
            # Count samples from training data
            training_path = Path(features_dir) / 'training.parquet'
            samples = 0
            if training_path.exists():
                training_df = pd.read_parquet(training_path)
                samples = len(training_df)
            
            # Read calibrator metadata
            calibrator_path = Path(model_dir) / 'isotonic_calibrator.pkl'
            calibrator_info = {}
            if calibrator_path.exists():
                import joblib
                cal_data = joblib.load(calibrator_path)
                if isinstance(cal_data, dict) and 'metadata' in cal_data:
                    meta = cal_data['metadata']
                    calibrator_info = {
                        'path': f"{model_dir}/isotonic_calibrator.pkl",
                        'type': meta.get('type', 'innings_phase_specific'),
                        'generated_date': meta.get('created_date', datetime.now().isoformat()),
                        'oof_metrics': {
                            'brier_raw': meta.get('oof_brier_raw', 0),
                            'brier_calibrated': meta.get('oof_brier_calibrated', 0),
                            'ece_raw': meta.get('oof_ece_raw', 0),
                            'ece_calibrated': meta.get('oof_ece_calibrated', 0)
                        },
                        'n_features': meta.get('n_features', 25),
                        'feature_hash': meta.get('feature_hash', '')
                    }
            
            # Update or create model entry
            model_entry = {
                'path': model_dir,
                'version': version,
                'description': f"XGBLogRegEnsemble (25 features) + Per-Over Brier-Optimized Calibration (Brier: {brier_score:.4f}, ECE: {ece_score:.4f})" if brier_score else f"XGBLogRegEnsemble retrained {version}",
                'training': {
                    'samples': samples,
                    'date': datetime.now().strftime('%Y-%m-%d'),
                    'brier_score': brier_score
                },
                'calibrator': calibrator_info,
                'feature_store': {
                    'path': feature_store_dir,
                    'version': version,
                    'generated_date': datetime.now().strftime('%Y-%m-%d'),
                    'training_data_samples': samples
                }
            }
            
            # Update active_models
            registry['active_models'][league_key] = model_entry
            registry['last_updated'] = datetime.now().strftime('%Y-%m-%d')
            
            with open(registry_path, 'w') as f:
                json.dump(registry, f, indent=2)
            
            click.echo(f"   ✅ Updated model_registry.json for {league_key}")
            
        except Exception as e:
            click.echo(f"   ⚠️ Failed to update registry: {e}")
    else:
        click.echo(f"   ⚠️ Model registry not found at {registry_path}")
    
    # Summary
    click.echo(f"\n{'='*60}")
    click.echo(f"  ✅ RETRAINING COMPLETE: {league.upper()} {version}")
    click.echo(f"{'='*60}")
    click.echo(f"  Model:         {model_dir}/champion_model.joblib")
    click.echo(f"  Calibrator:    {model_dir}/isotonic_calibrator.pkl")
    click.echo(f"  Feature Store: {feature_store_dir}")
    click.echo(f"  OOF Report:    {model_dir}/OOF_CALIBRATION_REPORT.md")
    click.echo(f"  Registry:      models/model_registry.json (updated)")
    click.echo(f"{'='*60}")
    click.echo(f"\n📌 Next steps:")
    click.echo(f"   1. Review OOF report: cat {model_dir}/OOF_CALIBRATION_REPORT.md")
    click.echo(f"   2. Test inference: python -m src.bbl_pipeline.inference.crex_live_predictor --model-dir {model_dir} --feature-store-dir {feature_store_dir}")


if __name__ == '__main__':
    main()
