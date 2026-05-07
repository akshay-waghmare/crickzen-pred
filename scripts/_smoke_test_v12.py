"""Smoke test: verify v12 loads cleanly via the routing path."""
import json, sys
sys.path.insert(0, "src")
from bbl_pipeline.training.calibration import PlattCalibrator
from bbl_pipeline.inference.inn2_phase_router import Inn2PhaseRouter

cfg = json.load(open("models/ipl_v11/routing_config.json"))
phase_dir = cfg["inn2_phase_model_dir"]
print(f"inn2_phase_model_dir: {phase_dir}")

router = Inn2PhaseRouter.load(phase_dir)
print("Router loaded OK")
print("  Phase models:", list(router._models.keys()))

mid_cals = router._calibrators["mid"]
phase_iso_type = type(mid_cals["phase_iso"]).__name__
per_over_types = set(type(c).__name__ for c in mid_cals["per_over"].values())
print(f"  MID phase_iso type: {phase_iso_type}")
print(f"  MID per_over count: {len(mid_cals['per_over'])}")
print(f"  MID per_over types: {per_over_types}")

import numpy as np
raw_mid = np.array([0.3, 0.5, 0.7])
cal = mid_cals["per_over"].get(10, mid_cals["phase_iso"])
out = cal.transform(raw_mid)
print(f"  MID cal over-10: {raw_mid} -> {out.round(4)}")

pp_cals = router._calibrators["pp"]
pp_type = type(pp_cals["phase_iso"]).__name__
print(f"  PP phase_iso type: {pp_type}")

print("Smoke test PASSED")
