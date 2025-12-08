import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
import structlog

logger = structlog.get_logger()

def write_parquet(
    data: List[Dict[str, Any]], 
    output_dir: Path, 
    schema_version: str = "1.0.0",
    source_files: Optional[List[str]] = None,
    partition_cols: List[str] = None
) -> None:
    """
    Write data to a partitioned Parquet dataset with provenance metadata.
    
    Args:
        data: List of dictionaries containing the data.
        output_dir: Root directory for the dataset.
        schema_version: Version string of the schema.
        source_files: List of source filenames (for metadata).
        partition_cols: List of columns to partition by. Defaults to ['season'].
    """
    if not data:
        logger.warning("No data to write")
        return

    if partition_cols is None:
        partition_cols = ['season']

    try:
        df = pd.DataFrame(data)
        
        # Convert date columns to datetime if needed (though processor should have done it)
        if 'date' in df.columns and not pd.api.types.is_datetime64_any_dtype(df['date']):
             df['date'] = pd.to_datetime(df['date'])

        table = pa.Table.from_pandas(df)
        
        # Add provenance metadata
        metadata = table.schema.metadata or {}
        new_metadata = {
            b'schema_version': schema_version.encode('utf-8'),
            b'ingestion_timestamp': datetime.now(timezone.utc).isoformat().encode('utf-8'),
            b'source_files_count': str(len(source_files or [])).encode('utf-8')
        }
        metadata.update(new_metadata)
        table = table.replace_schema_metadata(metadata)
        
        # Write partitioned dataset
        pq.write_to_dataset(
            table,
            root_path=str(output_dir),
            partition_cols=partition_cols,
            compression='zstd',
            existing_data_behavior='overwrite_or_ignore'
        )
        logger.info("Wrote parquet dataset", output_dir=str(output_dir), rows=len(df), partitions=partition_cols)
        
    except Exception as e:
        logger.error("Failed to write parquet dataset", error=str(e))
        raise e
