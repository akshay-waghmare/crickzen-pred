from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional


@dataclass(slots=True)
class CorpusManifest:
    corpus_version: str
    input_path: str
    raw_backfill_dir: Optional[str]
    eligible_rows: int
    excluded_rows: int
    exclusion_breakdown: Dict[str, int]
    feature_columns: List[str]
    window_fields: List[str]
    pca_components: int
    random_seed: int
    fit_split_policy: str
    source_rows: int
    corpus_coverage: float

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class StageManifest:
    stage: str
    status: str
    artifact_paths: Dict[str, str]
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class GateDecision:
    recommendation: str
    winning_variant: Optional[str]
    gate_failures: List[str]
    gates_passed: Dict[str, bool]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
