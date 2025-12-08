import click
from pathlib import Path
import structlog
from datetime import datetime, timezone
import time
import json
import pandas as pd

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

if __name__ == '__main__':
    main()
