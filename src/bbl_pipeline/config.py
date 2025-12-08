import yaml
import os
from pathlib import Path
from typing import Any, Dict, Optional
from dataclasses import dataclass

@dataclass
class PipelineConfig:
    input_dir: Path
    output_dir: Path
    registry_path: Path
    incremental: bool = False
    log_level: str = "INFO"
    error_policy: str = "skip" # skip, flag, fail

    @classmethod
    def from_yaml(cls, config_path: Path) -> 'PipelineConfig':
        """Load configuration from a YAML file."""
        if not config_path.exists():
            raise FileNotFoundError(f"Config file not found: {config_path}")

        with open(config_path, 'r') as f:
            config_dict = yaml.safe_load(f) or {}
        
        return cls(
            input_dir=Path(config_dict.get('input_dir', './data/raw')),
            output_dir=Path(config_dict.get('output_dir', './data/processed')),
            registry_path=Path(config_dict.get('registry_path', './config/entity_registry.yaml')),
            incremental=config_dict.get('incremental', False),
            log_level=config_dict.get('log_level', 'INFO'),
            error_policy=config_dict.get('error_policy', 'skip')
        )

def load_config(config_path: Optional[Path] = None) -> PipelineConfig:
    """
    Load configuration from a file or return defaults.
    """
    if config_path:
        return PipelineConfig.from_yaml(config_path)
    
    # Default config
    return PipelineConfig(
        input_dir=Path("./data/raw"),
        output_dir=Path("./data/processed"),
        registry_path=Path("./config/entity_registry.yaml")
    )
