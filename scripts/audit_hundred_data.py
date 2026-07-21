"""Audit and fingerprint The Hundred Cricsheet JSON dataset.

The audit is deliberately independent of model training. It makes the standard
training cohort and every quarantine reason explicit before candidate metrics
are generated.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any, Dict, Iterable, List

from bbl_pipeline.ingestion.hundred_normalizer import HundredNormalizer


def _sha256_files(files: Iterable[Path]) -> str:
    digest = hashlib.sha256()
    for path in files:
        digest.update(path.name.encode("utf-8"))
        digest.update(path.read_bytes())
    return digest.hexdigest()


def audit_directory(input_dir: Path) -> Dict[str, Any]:
    files = sorted(input_dir.glob("*.json"))
    normalizer = HundredNormalizer()
    quarantine: List[Dict[str, Any]] = []
    seasons: Counter[str] = Counter()
    genders: Counter[str] = Counter()
    outcomes: Counter[str] = Counter()
    legal_balls_by_innings: Counter[str] = Counter()
    raw_delivery_rows = 0
    main_innings = 0
    extra_innings = 0
    parseable = 0
    standard_matches = 0

    for path in files:
        try:
            match = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            quarantine.append({"match_id": path.stem, "reason_code": "invalid_json", "detail": str(exc)})
            continue

        parseable += 1
        info = match.get("info") or {}
        season = str(info.get("season", "unknown"))
        gender = str(info.get("gender", "unknown"))
        seasons[season] += 1
        genders[gender] += 1

        outcome = info.get("outcome") or {}
        outcome_key = str(outcome.get("result") or outcome.get("method") or ("winner" if outcome.get("winner") else "missing"))
        outcomes[outcome_key] += 1
        reasons: List[str] = []
        if info.get("balls_per_over") != 5 or info.get("overs") != 20:
            reasons.append("unexpected_balls_per_over")
        if not info.get("teams") or len(info.get("teams", [])) != 2:
            reasons.append("missing_required_metadata")
        if outcome.get("result") == "no result":
            reasons.append("no_result")
        if outcome.get("result") == "tie" or outcome.get("eliminator"):
            reasons.append("tie_or_super_five")
        if outcome.get("method") == "D/L":
            reasons.append("dls_target_not_supported")
        if not outcome.get("winner"):
            reasons.append("missing_winner")

        match_main_innings = 0
        match_has_overflow = False
        for innings_number, innings in enumerate(match.get("innings", []) or [], start=1):
            is_super_five = innings_number > 2 or bool(innings.get("super_over"))
            if is_super_five:
                extra_innings += 1
            else:
                main_innings += 1
                match_main_innings += 1

            raw_delivery_rows += sum(len(over.get("deliveries", []) or []) for over in innings.get("overs", []) or [])
            normalized = normalizer.normalize_innings(
                innings,
                match_id=path.stem,
                innings_number=innings_number,
                gender=gender,
                winner=outcome.get("winner"),
                is_super_five=is_super_five,
            )
            legal_balls_by_innings[str(normalized.legal_balls)] += 1
            if "legal_ball_overflow" in normalized.anomaly_flags:
                match_has_overflow = True

        if match_has_overflow:
            reasons.append("legal_ball_overflow")
        if match_main_innings != 2:
            reasons.append("missing_required_metadata")

        if reasons:
            quarantine.append({
                "match_id": path.stem,
                "season": season,
                "gender": gender,
                "reason_codes": sorted(set(reasons)),
            })
        else:
            standard_matches += 1

    return {
        "source_dir": str(input_dir),
        "source_file_count": len(files),
        "parseable_file_count": parseable,
        "source_fingerprint_sha256": _sha256_files(files),
        "seasons": dict(sorted(seasons.items())),
        "genders": dict(sorted(genders.items())),
        "outcomes": dict(sorted(outcomes.items())),
        "raw_delivery_rows": raw_delivery_rows,
        "main_innings": main_innings,
        "extra_innings": extra_innings,
        "legal_balls_by_innings": dict(sorted(legal_balls_by_innings.items(), key=lambda item: int(item[0]))),
        "standard_training_match_count": standard_matches,
        "quarantine_match_count": len(quarantine),
        "quarantine": quarantine,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()

    if not args.input_dir.is_dir():
        raise SystemExit(f"Input directory does not exist: {args.input_dir}")
    report = audit_directory(args.input_dir)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "audit_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    (args.output_dir / "quarantine_manifest.json").write_text(
        json.dumps(report["quarantine"], indent=2), encoding="utf-8"
    )
    print(json.dumps({
        key: report[key]
        for key in (
            "source_file_count",
            "parseable_file_count",
            "standard_training_match_count",
            "quarantine_match_count",
            "raw_delivery_rows",
        )
    }, indent=2))


if __name__ == "__main__":
    main()

