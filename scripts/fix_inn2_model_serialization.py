"""
Fix ipl_inn2_v1 phase model serialization.

The models were saved when XGBLRBlend was defined in __main__ (scripts/run_inn2_research.py).
This script re-saves them with the stable package class:
    bbl_pipeline.training.blend_model.XGBLRBlend

Run once from the project root:
    python scripts/fix_inn2_model_serialization.py
"""

import sys
import joblib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

# 1. Import the package class (stable module path)
from bbl_pipeline.training.blend_model import XGBLRBlend as PackageXGBLRBlend

# 2. Inject into __main__ so the old joblib file can unpickle
#    (pickle looks up class by __main__.XGBLRBlend)
import __main__
__main__.XGBLRBlend = PackageXGBLRBlend

MODEL_DIR = ROOT / "models" / "ipl_inn2_v1"
PHASES = ["pp", "mid", "death"]

for phase in PHASES:
    path = MODEL_DIR / f"champion_model_{phase}.joblib"
    if not path.exists():
        print(f"[SKIP] {path} does not exist")
        continue

    # Load using the __main__ alias → gives us a PackageXGBLRBlend instance
    old_model = joblib.load(path)
    print(f"[LOADED] {phase}: class={type(old_model).__module__}.{type(old_model).__name__}")

    # Ensure the instance is typed as PackageXGBLRBlend (copy attrs if class mismatch)
    if type(old_model) is not PackageXGBLRBlend:
        new_model = PackageXGBLRBlend.__new__(PackageXGBLRBlend)
        new_model.__dict__.update(old_model.__dict__)
        old_model = new_model

    # Re-save — joblib will now write bbl_pipeline.training.blend_model.XGBLRBlend
    joblib.dump(old_model, path)

    # Verify round-trip
    check = joblib.load(path)
    assert type(check).__module__ == "bbl_pipeline.training.blend_model", (
        f"Expected bbl_pipeline.training.blend_model, got {type(check).__module__}"
    )
    print(f"[OK]     {phase}: saved as {type(check).__module__}.{type(check).__name__}")

print("\nAll phase models re-serialized. Run smoke test to verify.")
