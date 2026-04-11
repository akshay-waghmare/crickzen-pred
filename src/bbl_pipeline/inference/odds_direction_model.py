from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict


@dataclass
class OddsDirectionModel:
    model_dir: Path | None = None
    status: str = 'unavailable'

    @classmethod
    def load(cls, model_dir: str | Path | None) -> 'OddsDirectionModel':
        path = Path(model_dir) if model_dir else None
        if path and path.exists():
            return cls(model_dir=path, status='not_implemented')
        return cls(model_dir=path, status='unavailable')

    def predict(self, *_args: Any, **_kwargs: Any) -> Dict[str, Any]:
        return {
            'status': self.status,
            'reason': 'ODM live inference is planned after training artifacts exist.',
        }
