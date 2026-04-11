from __future__ import annotations

from pathlib import Path
from typing import Any, Dict


def train_odm(*args: Any, **kwargs: Any) -> Dict[str, Any]:
    raise NotImplementedError('ODM trainer is planned in Phase 4. Export/build validation is implemented first.')


def save_odm_artifacts(*args: Any, **kwargs: Any) -> None:
    raise NotImplementedError('ODM artifact saving is planned in Phase 4.')
