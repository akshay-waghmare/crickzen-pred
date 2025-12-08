import pandas as pd
from pathlib import Path
import structlog
from typing import List, Optional

logger = structlog.get_logger()

def compact_partition(partition_path: Path, target_size_mb: int = 100):
    """
    Compact small parquet files in a partition into larger files.
    
    Args:
        partition_path: Path to the partition directory (e.g. .../season=2023)
        target_size_mb: Target size for compacted files in MB.
    """
    if not partition_path.exists():
        return
        
    files = list(partition_path.glob("*.parquet"))
    if not files:
        return
        
    # Check total size or file count
    # If we have many small files, we compact.
    # Simple strategy: Read all, write one (or few).
    
    # For now, let's just read all and write one file if there are multiple files.
    if len(files) <= 1:
        return
        
    logger.info(f"Compacting {len(files)} files in {partition_path}")
    
    try:
        dfs = []
        for f in files:
            dfs.append(pd.read_parquet(f))
            
        combined_df = pd.concat(dfs, ignore_index=True)
        
        # Write to a new file
        # We use a temporary name first
        temp_file = partition_path / "compacted_temp.parquet"
        combined_df.to_parquet(temp_file, index=False)
        
        # Delete old files
        for f in files:
            f.unlink()
            
        # Rename temp file
        final_name = partition_path / f"part-00000-{pd.Timestamp.now().strftime('%Y%m%d%H%M%S')}.parquet"
        temp_file.rename(final_name)
        
        logger.info(f"Compaction complete. Created {final_name}")
        
    except Exception as e:
        logger.error(f"Compaction failed for {partition_path}: {e}")

def compact_dataset(dataset_path: Path):
    """
    Compact all partitions in a dataset.
    """
    # Assuming hive partitioning: dataset/col=val/
    # Or dataset/matches/season=2023/
    
    # We walk the directory tree
    # We look for directories that contain parquet files
    # Note: rglob("*") includes files, we filter for dirs
    
    # A better way is to walk and check if dir contains parquet files
    for path in dataset_path.rglob("*"):
        if path.is_dir():
            # Check if it has parquet files directly inside
            if any(path.glob("*.parquet")):
                compact_partition(path)
