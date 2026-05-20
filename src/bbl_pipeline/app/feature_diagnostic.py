"""
Feature Diagnostic Tool — Streamlit app.

Real-time inspector for features being fed to live prediction models.
Shows feature population status across all model phases (Inn1 + Inn2 PP/Mid/Death)
for both innings, with auto-refresh.

Usage:
    streamlit run src/bbl_pipeline/app/feature_diagnostic.py --server.port 8503
"""

from __future__ import annotations

import json
import time
import traceback
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
import streamlit as st

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Feature Diagnostic",
    page_icon="🔬",
    layout="wide",
    initial_sidebar_state="expanded",
)

PROJECT_ROOT = Path(__file__).resolve().parents[3]

# ── Helpers ───────────────────────────────────────────────────────────────────

@st.cache_resource(show_spinner="Loading models…")
def load_inn1_model(model_dir: str):
    """Load the Inn1 model and return (model, feature_list)."""
    routing = Path(model_dir) / "routing_config.json"
    if routing.exists():
        cfg = json.loads(routing.read_text())
        if cfg.get("type") == "inn2_phase_router":
            model_dir = cfg.get("inn1_model_dir", model_dir)
    path = Path(model_dir) / "champion_model.joblib"
    if not path.exists():
        return None, []
    model = joblib.load(path)
    feats = list(getattr(model, "selected_features_", None) or
                 getattr(model, "TOP_FEATURES", None) or [])
    return model, feats


@st.cache_resource(show_spinner="Loading Inn2 phase router…")
def load_inn2_phase_features(model_dir: str) -> dict[str, list[str]]:
    """Return {phase: [feature_names]} from the inn2 phase model dir."""
    routing = Path(model_dir) / "routing_config.json"
    phase_dir = model_dir
    if routing.exists():
        cfg = json.loads(routing.read_text())
        if cfg.get("type") == "inn2_phase_router":
            phase_dir = cfg.get("inn2_phase_model_dir", model_dir)
    feat_file = Path(phase_dir) / "phase_features.json"
    if feat_file.exists():
        return json.loads(feat_file.read_text())
    return {}


def load_live_json(path: str) -> dict | None:
    p = Path(path)
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text())
    except Exception:
        return None


def engineer_inn2(raw_feats: dict) -> dict:
    """Apply inn2 feature engineering and return the enriched dict."""
    try:
        from bbl_pipeline.features.inn2_engineering import engineer_inn2_features
        row = pd.DataFrame([raw_feats])
        row_eng = engineer_inn2_features(row)
        return row_eng.iloc[0].to_dict()
    except Exception as e:
        st.warning(f"inn2_engineering failed: {e}")
        return raw_feats


def _classify(val: Any) -> str:
    """Classify a feature value as 'ok', 'zero', or 'null'."""
    if val is None or (isinstance(val, float) and np.isnan(val)):
        return "null"
    if val == 0 or val == 0.0:
        return "zero"
    return "ok"


def build_feature_table(
    feature_names: list[str],
    feats: dict,
) -> pd.DataFrame:
    rows = []
    for f in feature_names:
        val = feats.get(f, "__MISSING__")
        if val == "__MISSING__":
            status = "❌ MISSING"
            display = "—"
        elif val is None or (isinstance(val, float) and np.isnan(val)):
            status = "⚠️ NULL"
            display = "null"
        elif val == 0 or val == 0.0:
            status = "🟡 ZERO"
            display = "0.0"
        else:
            status = "✅ OK"
            display = f"{val:.5g}" if isinstance(val, float) else str(val)
        rows.append({"Feature": f, "Status": status, "Value": display})
    return pd.DataFrame(rows)


def summary_bar(df: pd.DataFrame, label: str):
    total = len(df)
    ok    = (df["Status"] == "✅ OK").sum()
    zero  = (df["Status"] == "🟡 ZERO").sum()
    null_ = (df["Status"] == "⚠️ NULL").sum()
    miss  = (df["Status"] == "❌ MISSING").sum()

    cols = st.columns(5)
    cols[0].metric(f"{label}", f"{total} total")
    cols[1].metric("✅ OK",      ok,   delta=None)
    cols[2].metric("🟡 ZERO",   zero, delta=None)
    cols[3].metric("⚠️ NULL",   null_, delta=None)
    cols[4].metric("❌ MISSING", miss, delta=None if miss == 0 else f"-{miss}",
                   delta_color="inverse")


def color_rows(df: pd.DataFrame) -> pd.DataFrame.style:
    def _bg(val):
        colors = {
            "✅ OK":       "background-color: #1a3a1a; color: #7fff7f",
            "🟡 ZERO":     "background-color: #3a3a00; color: #ffff7f",
            "⚠️ NULL":     "background-color: #3a1a00; color: #ffaa44",
            "❌ MISSING":  "background-color: #3a0000; color: #ff6666",
        }
        return colors.get(val, "")
    # pandas ≥2.1 renamed applymap → map
    styler = df.style
    apply_fn = getattr(styler, "map", None) or getattr(styler, "applymap")
    return apply_fn(_bg, subset=["Status"])


# ── Scan all live JSONs and pick the freshest active one ─────────────────────
def _scan_live_jsons() -> list[dict]:
    """Return metadata for every live JSON, sorted newest-first."""
    data_dir = PROJECT_ROOT / "data"
    candidates = [
        f for f in data_dir.rglob("*live_ml*.json")
        if "history" not in f.name
        and "odm" not in f.name
        and "livematch" not in f.name
    ]
    rows = []
    now = time.time()
    for f in candidates:
        try:
            age_s = now - f.stat().st_mtime
            d = json.loads(f.read_text(encoding="utf-8"))
            batting = d.get("batting_team", "")
            score   = d.get("score", "")
            wkts    = d.get("wickets", "")
            overs   = d.get("overs", "")
            tgt     = d.get("target_runs")
            wp      = d.get("bat_win_prob")
            wp_str  = f"{wp*100:.0f}%" if wp is not None else "—"
            active  = age_s < 90          # updated within last 90 s
            rows.append({
                "path":    str(f.relative_to(PROJECT_ROOT)),
                "name":    f.name,
                "age_s":   age_s,
                "active":  active,
                "batting": batting,
                "score":   f"{score}/{wkts} ({overs})" if batting else "—",
                "target":  f"chasing {tgt}" if tgt else "Inn1",
                "wp":      wp_str,
            })
        except Exception:
            pass
    rows.sort(key=lambda r: r["age_s"])   # freshest first
    return rows

live_rows = _scan_live_jsons()

# Auto-select: first active file, else first file overall
auto_path = next((r["path"] for r in live_rows if r["active"]), None)
if not auto_path and live_rows:
    auto_path = live_rows[0]["path"]

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.title("🔬 Feature Diagnostic")
    st.markdown("---")

    # Show all found JSONs with status so user can see which is active
    st.markdown("**📡 Live prediction feeds**")
    if not live_rows:
        st.warning("No live_ml JSON files found in `data/`.")
    else:
        options = []
        labels  = []
        for r in live_rows:
            age_s = r["age_s"]
            if age_s < 90:
                age_label = f"🟢 {int(age_s)}s ago"
            elif age_s < 300:
                age_label = f"🟡 {int(age_s//60)}m ago"
            else:
                age_label = f"🔴 {int(age_s//60)}m ago"
            label = f"{age_label}  |  {r['name']}"
            if r["batting"]:
                label += f"\n   {r['batting']}  {r['score']}  {r['target']}  wp={r['wp']}"
            options.append(r["path"])
            labels.append(label)

        default_idx = options.index(auto_path) if auto_path in options else 0
        selected_json = st.radio(
            "Select feed",
            options,
            index=default_idx,
            format_func=lambda p: labels[options.index(p)],
        )

    st.markdown("---")
    refresh_secs = st.slider("Auto-refresh (seconds)", 5, 60, 10)
    show_only_issues = st.checkbox("Show only issues (missing/null/zero)", value=False)
    filter_phase = st.selectbox("Filter phase table", ["All phases", "Inn1", "PP", "Mid", "Death"])

    st.markdown("---")
    st.caption(f"Project: `{PROJECT_ROOT.name}`")
    if st.button("🔄 Refresh now"):
        st.rerun()


# ── Load selected JSON ────────────────────────────────────────────────────────
json_path = str(PROJECT_ROOT / selected_json) if selected_json else ""
data = load_live_json(json_path)

# ── Header ────────────────────────────────────────────────────────────────────
st.title("🔬 Live Feature Diagnostic")

if data is None:
    st.error(f"Could not load `{selected_json}` — predictor may not be running yet.")
    time.sleep(refresh_secs)
    st.rerun()

# ── Auto-detect model dir from the JSON itself ────────────────────────────────
detected_model_dir = data.get("model_dir", "")
model_path = str(PROJECT_ROOT / detected_model_dir) if detected_model_dir else ""

# Resolve routing config → show actual inn1 + inn2 dirs in sidebar
routing_info = {}
if model_path:
    routing_cfg_path = Path(model_path) / "routing_config.json"
    if routing_cfg_path.exists():
        routing_info = json.loads(routing_cfg_path.read_text())

inn1_dir_display = routing_info.get("inn1_model_dir", detected_model_dir) if routing_info else detected_model_dir
inn2_dir_display = routing_info.get("inn2_phase_model_dir", "") if routing_info else ""

with st.sidebar:
    st.markdown("**🤖 Auto-detected models**")
    st.info(f"**Entry:** `{detected_model_dir}`")
    if routing_info:
        st.success(f"**Inn1:** `{inn1_dir_display}`")
        st.success(f"**Inn2 phases:** `{inn2_dir_display}`")
    else:
        st.success(f"**Model:** `{detected_model_dir}`")
    st.caption("(from JSON `model_dir` field)")

inn1_model, inn1_feats = load_inn1_model(model_path) if model_path else (None, [])
inn2_phase_feats = load_inn2_phase_features(model_path) if model_path else {}

# ── Match state banner ────────────────────────────────────────────────────────
bat   = data.get("batting_team", "?")
score = data.get("score", 0)
wkts  = data.get("wickets", 0)
overs = data.get("overs", 0.0)
tgt   = data.get("target_runs")
inns  = data.get("innings", "?")
phase = data.get("phase", "—")
ts    = data.get("timestamp", "")

col1, col2, col3, col4, col5 = st.columns(5)
col1.metric("Batting", bat)
col2.metric("Score", f"{score}/{wkts}")
col3.metric("Overs", f"{overs}")
col4.metric("Target", tgt or "Inn1")
col5.metric("bat_win_prob", f"{data.get('bat_win_prob', 0)*100:.1f}%")

st.caption(f"Last update: `{ts}` | Phase: `{phase}` | Innings: `{inns}` | JSON: `{selected_json}`")
st.markdown("---")

# ── Raw + Engineered feature dicts ───────────────────────────────────────────
raw_feats = data.get("features", {})
is_inn2   = tgt is not None or (inns and str(inns) == "2")
eng_feats = engineer_inn2(raw_feats) if is_inn2 else raw_feats

raw_count = len(raw_feats)
eng_count = len(eng_feats)
new_count = eng_count - raw_count

st.subheader("📦 Feature Pool Summary")
c1, c2, c3 = st.columns(3)
c1.metric("Raw features (from predictor)", raw_count)
c2.metric("After inn2 engineering", eng_count if is_inn2 else "N/A (Inn1)")
c3.metric("Features added by engineering", new_count if is_inn2 else "—")

if is_inn2:
    with st.expander("🆕 Features added by engineer_inn2_features()", expanded=False):
        added = sorted(set(eng_feats.keys()) - set(raw_feats.keys()))
        st.write(f"**{len(added)} new features:**")
        added_vals = {f: eng_feats[f] for f in added}
        added_df = pd.DataFrame([
            {"Feature": f, "Value": f"{v:.5g}" if isinstance(v, float) else str(v)}
            for f, v in sorted(added_vals.items())
        ])
        st.dataframe(added_df, use_container_width=True, height=300)

st.markdown("---")

# ── Inn1 Model Features ───────────────────────────────────────────────────────
show_inn1 = filter_phase in ("All phases", "Inn1")
if show_inn1:
    st.subheader(f"🏏 Inn1 Model — `{inn1_dir_display}` ({len(inn1_feats)} features)")
    if not inn1_feats:
        st.warning("Could not load Inn1 feature list from model.")
    else:
        df_inn1 = build_feature_table(inn1_feats, raw_feats)
        summary_bar(df_inn1, "Inn1")
        if show_only_issues:
            df_inn1 = df_inn1[df_inn1["Status"] != "✅ OK"]
        if df_inn1.empty:
            st.success("All Inn1 features are ✅ OK and non-zero!")
        else:
            st.dataframe(color_rows(df_inn1), use_container_width=True, height=min(40 * len(df_inn1) + 40, 600))

st.markdown("---")

# ── Inn2 Phase Features ───────────────────────────────────────────────────────
if inn2_phase_feats:
    phase_label_map = {"pp": ("PP", "overs 1–6"), "mid": ("Mid", "overs 7–15"), "death": ("Death", "overs 16–20")}
    phase_filter_map = {"PP": "pp", "Mid": "mid", "Death": "death"}
    active_phases = ["pp", "mid", "death"]
    if filter_phase in phase_filter_map:
        active_phases = [phase_filter_map[filter_phase]]
    elif filter_phase == "Inn1":
        active_phases = []

    for ph in active_phases:
        pf = inn2_phase_feats.get(ph, [])
        label, over_range = phase_label_map.get(ph, (ph.upper(), ""))
        # Use engineered features for Inn2 check
        check_feats = eng_feats if is_inn2 else raw_feats
        df_ph = build_feature_table(pf, check_feats)

        missing_count = (df_ph["Status"] == "❌ MISSING").sum()
        null_count    = (df_ph["Status"] == "⚠️ NULL").sum()
        icon = "✅" if missing_count == 0 and null_count == 0 else "❌"

        with st.expander(f"{icon} Inn2 {label} ({over_range}) — {len(pf)} features | missing={missing_count} null={null_count}", expanded=(missing_count > 0 or null_count > 0 or filter_phase != "All phases")):
            summary_bar(df_ph, f"Inn2 {label}")
            if show_only_issues:
                df_ph = df_ph[df_ph["Status"] != "✅ OK"]
            if df_ph.empty:
                st.success(f"All {label} features are ✅ OK!")
            else:
                st.dataframe(color_rows(df_ph), use_container_width=True, height=min(40 * len(df_ph) + 40, 700))

            if not is_inn2:
                st.info("ℹ️ Currently Inn1 — Inn2 features will be computed live when chase begins.")
elif filter_phase not in ("Inn1",):
    st.info("No Inn2 phase feature list found for this model.")

# ── All raw features dump ─────────────────────────────────────────────────────
st.markdown("---")
with st.expander("📋 All raw features from predictor JSON", expanded=False):
    search = st.text_input("Filter feature name", key="raw_search", placeholder="e.g. momentum, inn1, venue")
    all_raw = pd.DataFrame([
        {"Feature": k, "Value": f"{v:.6g}" if isinstance(v, float) else str(v),
         "Type": type(v).__name__}
        for k, v in sorted(raw_feats.items())
        if not search or search.lower() in k.lower()
    ])
    st.caption(f"Showing {len(all_raw)} of {len(raw_feats)} raw features")
    st.dataframe(all_raw, use_container_width=True, height=500)

if is_inn2:
    with st.expander("📋 All engineered features (post inn2_engineering)", expanded=False):
        search2 = st.text_input("Filter feature name", key="eng_search", placeholder="e.g. pp_ease, momentum")
        all_eng = pd.DataFrame([
            {"Feature": k,
             "Value": f"{v:.6g}" if isinstance(v, float) else str(v),
             "Source": "🆕 engineered" if k not in raw_feats else "raw"}
            for k, v in sorted(eng_feats.items())
            if not search2 or search2.lower() in k.lower()
        ])
        st.caption(f"Showing {len(all_eng)} of {len(eng_feats)} engineered features")
        st.dataframe(all_eng, use_container_width=True, height=500)

# ── Calibration chain ─────────────────────────────────────────────────────────
st.markdown("---")
st.subheader("🎯 Calibration Chain")
cal_keys = [
    ("raw_win_prob",             "Raw"),
    ("calibrated_combined_prob", "Combined isotonic"),
    ("calibrated_phase_prob",    "Phase isotonic"),
    ("calibrated_per_over_prob", "Per-over isotonic"),
    ("shadow_t_prob",            "Temperature (shadow)"),
    ("league_calibrated_prob",   "League calibrated"),
    ("bat_win_prob",             "Final (bat_win_prob)"),
]
cal_cols = st.columns(len(cal_keys))
for col, (key, label) in zip(cal_cols, cal_keys):
    val = data.get(key)
    if val is not None:
        col.metric(label, f"{val*100:.1f}%")
    else:
        col.metric(label, "—")

# ── Footer / auto-refresh ─────────────────────────────────────────────────────
st.markdown("---")
placeholder = st.empty()
for i in range(refresh_secs, 0, -1):
    placeholder.caption(f"⏱ Auto-refreshing in {i}s…")
    time.sleep(1)
placeholder.caption("🔄 Refreshing…")
st.rerun()
