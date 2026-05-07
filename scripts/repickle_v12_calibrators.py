"""
Re-pickle v12 calibrators using the canonical PlattCalibrator class.

The original calibrators were saved with the class defined in
scripts/build_ipl_v12.py — importing that module runs all the global
training code. This script re-saves them using the stable
bbl_pipeline.training.calibration.PlattCalibrator class.
"""
import warnings; warnings.filterwarnings("ignore")
import pickle, sys, json
import numpy as np, pandas as pd
import joblib
from pathlib import Path
from scipy.special import logit
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import LogisticRegression

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
from bbl_pipeline.training.blend_model import XGBLRBlend  # needed for joblib unpickle

# ── Local definition to unpickle the old pkl (avoids importing build script) ──
class PlattCalibrator:
    def __init__(self, C=1.0): self.C=C; self._eps=1e-6
    def fit(self, raw, y):
        X=logit(np.clip(raw,self._eps,1-self._eps)).reshape(-1,1)
        self._lr=LogisticRegression(C=self.C,max_iter=2000,random_state=42)
        self._lr.fit(X,y.astype(int)); return self
    def transform(self, raw):
        X=logit(np.clip(raw,self._eps,1-self._eps)).reshape(-1,1)
        return self._lr.predict_proba(X)[:,1]
    def predict(self, raw): return self.transform(raw)

# Inject into scripts.build_ipl_v12 namespace so pickle.load can find it
import types
_fake_module = types.ModuleType("scripts.build_ipl_v12")
_fake_module.PlattCalibrator = PlattCalibrator
sys.modules["scripts.build_ipl_v12"] = _fake_module

# Now import the canonical class (what we want to re-save as)
from bbl_pipeline.training.calibration import PlattCalibrator as CanonicalPlatt

V12 = Path("models/ipl_v12")

print("Loading v12 calibrators from pkl...")
old_cals = pickle.load(open(V12 / "phase_oof_calibrators.pkl", "rb"))

def migrate_calibrator(cal):
    """Convert a local PlattCalibrator → canonical PlattCalibrator, preserving parameters."""
    if type(cal).__name__ == "PlattCalibrator":
        new_cal = CanonicalPlatt(C=cal.C)
        new_cal._lr = cal._lr  # copy the fitted LogisticRegression directly
        return new_cal
    return cal  # IsotonicRegression — no migration needed

new_cals = {}
for phase, phase_dict in old_cals.items():
    new_phase = {}
    # phase_iso
    new_phase["phase_iso"] = migrate_calibrator(phase_dict["phase_iso"])
    # per_over
    new_phase["per_over"] = {
        ov: migrate_calibrator(cal)
        for ov, cal in phase_dict["per_over"].items()
    }
    new_cals[phase] = new_phase
    n_platt = sum(1 for c in [new_phase["phase_iso"]] + list(new_phase["per_over"].values())
                  if type(c).__name__ == "PlattCalibrator")
    n_iso   = sum(1 for c in [new_phase["phase_iso"]] + list(new_phase["per_over"].values())
                  if type(c).__name__ == "IsotonicRegression")
    print(f"  {phase.upper()}: {n_platt} PlattCalibrators (canonical), {n_iso} IsotonicRegression")

# Save
with open(V12 / "phase_oof_calibrators.pkl", "wb") as f:
    pickle.dump(new_cals, f)
print(f"\nSaved re-pickled calibrators → {V12 / 'phase_oof_calibrators.pkl'}")

# Verify round-trip
print("\nVerifying round-trip unpickle...")
# Remove fake module so canonical load path is tested
del sys.modules["scripts.build_ipl_v12"]
reloaded = pickle.load(open(V12 / "phase_oof_calibrators.pkl", "rb"))
for phase, pd_ in reloaded.items():
    pi = type(pd_["phase_iso"]).__name__
    n_po = len(pd_["per_over"])
    print(f"  {phase}: phase_iso={pi}, per_over={n_po} calibrators ✓")
print("Re-pickling complete.")
