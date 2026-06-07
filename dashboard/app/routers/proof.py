"""
Proof API routes for the CrickenZen dashboard.

Exposes stable backend contracts for summary metrics, segment metrics,
and proof-ledger rows consumed by the proof page and Ask CrickenZen surfaces.
"""

from __future__ import annotations

from fastapi import APIRouter, Query

from app.proof_metrics import (
    load_latest_summary,
    load_latest_segments,
    load_latest_ledger,
    load_latest_manifest,
)

router = APIRouter(prefix="/api/proof", tags=["Proof"])


@router.get("/summary")
def proof_summary(league: str = Query(default="ipl", description="League identifier")):
    data = load_latest_summary(league=league)
    return data


@router.get("/segments")
def proof_segments(league: str = Query(default="ipl", description="League identifier")):
    data = load_latest_segments(league=league)
    return {
        "league": league,
        "segments": data,
        "count": len(data),
    }


@router.get("/ledger")
def proof_ledger(league: str = Query(default="ipl", description="League identifier")):
    data = load_latest_ledger(league=league)
    return {
        "league": league,
        "ledger": data,
        "count": len(data),
    }


@router.get("/manifest")
def proof_manifest(league: str = Query(default="ipl", description="League identifier")):
    return load_latest_manifest(league=league)
