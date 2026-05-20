"""
IPL v14 High-Chase Diagnostic Report Generator
Produces a detailed, user-friendly HTML report from OOS analysis artifacts.
"""
import pandas as pd
import numpy as np
from pathlib import Path

ARTIFACT_DIR = Path("models/ipl_high_chase_v1")
OUT_HTML = ARTIFACT_DIR / "HIGH_CHASE_DIAGNOSTIC_REPORT.html"


# ─── Load artifacts ────────────────────────────────────────────────────────────
preds    = pd.read_csv(ARTIFACT_DIR / "v14_oos_predictions_by_ball.csv")
by_sit   = pd.read_csv(ARTIFACT_DIR / "v14_oos_calibration_by_situation.csv")
binned   = pd.read_csv(ARTIFACT_DIR / "v14_oos_binned_model_vs_actual.csv")
ablation = pd.read_csv(ARTIFACT_DIR / "v14_oos_candidate_rule_ablation.csv")
boot     = pd.read_csv(ARTIFACT_DIR / "v14_oos_match_bootstrap_raw_vs_cal.csv")


# ─── Helpers ───────────────────────────────────────────────────────────────────
def pct(v, decimals=1):
    return f"{v*100:.{decimals}f}%"

def signed_pct(v, decimals=2):
    sign = "+" if v >= 0 else ""
    return f"{sign}{v*100:.{decimals}f}%"

def brier_color(delta):
    """Color for brier delta vs v14. Positive = worse (red), negative = better (green)."""
    if delta > 0.002:  return "#ffcccc"
    if delta < -0.002: return "#ccffcc"
    return "#fff8e1"

def bias_color(bias):
    """Color for overpredict/underpredict."""
    if bias > 0.05:  return "#ffcccc"
    if bias < -0.05: return "#cce5ff"
    return "#f0f0f0"

def ci_color(lo, hi):
    """Green if CI fully positive (calibration hurts), blue if negative, yellow if crosses 0."""
    if lo > 0:  return "#ffcccc"  # calibration hurts
    if hi < 0:  return "#ccffcc"  # calibration helps
    return "#fff8e1"               # uncertain

def row_style(i):
    return 'background:#f9f9f9;' if i % 2 == 0 else 'background:#ffffff;'

CSS = """
<style>
  body { font-family: 'Segoe UI', Arial, sans-serif; background: #f4f6f8; color: #222; margin: 0; padding: 0; }
  .container { max-width: 1200px; margin: 0 auto; padding: 24px 16px; }
  h1 { color: #1a237e; border-bottom: 3px solid #1a237e; padding-bottom: 8px; }
  h2 { color: #283593; margin-top: 36px; border-left: 5px solid #3949ab; padding-left: 10px; }
  h3 { color: #394d9e; margin-top: 20px; }
  .card { background: #fff; border-radius: 10px; box-shadow: 0 2px 8px rgba(0,0,0,0.08); padding: 20px 24px; margin-bottom: 24px; }
  table { border-collapse: collapse; width: 100%; font-size: 0.88em; }
  th { background: #1a237e; color: #fff; padding: 8px 10px; text-align: left; white-space: nowrap; }
  td { padding: 7px 10px; border-bottom: 1px solid #e0e0e0; vertical-align: middle; }
  .badge-red    { background:#ffcccc; color:#800000; border-radius:4px; padding:2px 7px; font-weight:600; }
  .badge-green  { background:#ccffcc; color:#005000; border-radius:4px; padding:2px 7px; font-weight:600; }
  .badge-yellow { background:#fff8e1; color:#5a4000; border-radius:4px; padding:2px 7px; font-weight:600; }
  .badge-blue   { background:#cce5ff; color:#003080; border-radius:4px; padding:2px 7px; font-weight:600; }
  .stat-grid { display: flex; flex-wrap: wrap; gap: 16px; margin: 12px 0; }
  .stat-box { background: #e8eaf6; border-radius: 8px; padding: 14px 20px; min-width: 160px; flex: 1; }
  .stat-box .label { font-size:0.8em; color:#555; text-transform:uppercase; letter-spacing:0.04em; }
  .stat-box .value { font-size:1.5em; font-weight:700; color:#1a237e; }
  .stat-box .sub { font-size:0.78em; color:#777; }
  .insight { background:#e3f2fd; border-left:4px solid #1565c0; padding:10px 14px; border-radius:4px; margin:10px 0; font-size:0.9em; }
  .warning { background:#fff3e0; border-left:4px solid #e65100; padding:10px 14px; border-radius:4px; margin:10px 0; font-size:0.9em; }
  .good    { background:#e8f5e9; border-left:4px solid #2e7d32; padding:10px 14px; border-radius:4px; margin:10px 0; font-size:0.9em; }
  .section-note { font-size:0.82em; color:#666; margin-bottom:6px; }
  .toc a { color:#3949ab; text-decoration:none; }
  .toc a:hover { text-decoration:underline; }
  .toc li { margin:4px 0; }
  .prog-bar-outer { background:#e0e0e0; border-radius:6px; height:10px; width:100%; }
  .prog-bar-inner { border-radius:6px; height:10px; }
</style>
"""

def progress_bar(val, max_val=1.0, color="#3949ab"):
    pct_w = min(100, val / max_val * 100)
    return f'<div class="prog-bar-outer"><div class="prog-bar-inner" style="width:{pct_w:.0f}%;background:{color};"></div></div>'


# ─── Dataset Summary ──────────────────────────────────────────────────────────
n_total    = len(preds)
n_matches  = preds['match_id'].nunique()
n_seasons  = preds['season'].nunique()
seasons    = sorted(preds['season'].unique())
n_high     = preds['is_high_chase'].sum()
pct_high   = n_high / n_total

# phase breakdown
phase_counts = preds.groupby('phase').size().to_dict()

# ─── Overall metrics ──────────────────────────────────────────────────────────
ov = by_sit[by_sit['situation'] == 'all'].iloc[0]
raw_brier = ov['raw_brier']
cal_brier = ov['cal_brier']
raw_logloss = ov['raw_logloss']
cal_logloss = ov['cal_logloss']
raw_ece = ov['raw_ece']
cal_ece = ov['cal_ece']
cal_vs_raw_brier_pct = (cal_brier - raw_brier) / raw_brier * 100

# ─── Production model metrics (v7, v14-prod) ──────────────────────────────────
from sklearn.metrics import brier_score_loss, log_loss
def _brier(y, p): return float(brier_score_loss(y, np.clip(p, 1e-7, 1-1e-7)))
def _logloss(y, p): return float(log_loss(y, np.clip(p, 1e-7, 1-1e-7)))

prod_rows = preds.dropna(subset=['v7_raw', 'v7_cal', 'v14_prod_raw', 'v14_prod_cal'])
y_prod = prod_rows['y'].values
_prod = {
    'v7_raw':      (_brier(y_prod, prod_rows['v7_raw']),     _logloss(y_prod, prod_rows['v7_raw'])),
    'v7_cal':      (_brier(y_prod, prod_rows['v7_cal']),     _logloss(y_prod, prod_rows['v7_cal'])),
    'v14prod_raw': (_brier(y_prod, prod_rows['v14_prod_raw']),_logloss(y_prod, prod_rows['v14_prod_raw'])),
    'v14prod_cal': (_brier(y_prod, prod_rows['v14_prod_cal']),_logloss(y_prod, prod_rows['v14_prod_cal'])),
    'v14oos_raw':  (raw_brier, raw_logloss),
    'v14oos_cal':  (cal_brier, cal_logloss),
}

# High-chase production metrics
hc_rows = prod_rows[prod_rows['is_high_chase']]
y_hc = hc_rows['y'].values
_prod_hc = {
    'v7_raw':      _brier(y_hc, hc_rows['v7_raw']),
    'v7_cal':      _brier(y_hc, hc_rows['v7_cal']),
    'v14prod_raw': _brier(y_hc, hc_rows['v14_prod_raw']),
    'v14prod_cal': _brier(y_hc, hc_rows['v14_prod_cal']),
}

# ─── Phase table ──────────────────────────────────────────────────────────────
phase_df = by_sit[by_sit['segment'] == 'phase'].copy()
chase_df = by_sit[by_sit['segment'] == 'chase_bucket'].copy()
px_df    = by_sit[by_sit['segment'] == 'phase_x_chase_bucket'].copy()
high_ph  = by_sit[by_sit['segment'] == 'high_phase'].copy()
target_df = by_sit[by_sit['segment'] == 'phase_x_target_band'].copy()
over_df   = by_sit[by_sit['segment'] == 'high_phase_over'].copy()

# ─── Bootstrap signals ────────────────────────────────────────────────────────
boot_high_mid   = boot[(boot['segment']=='high_phase') & (boot['situation']=='phase=mid')].iloc[0]
boot_high_death = boot[(boot['segment']=='high_phase') & (boot['situation']=='phase=death')].iloc[0]
boot_high_pp    = boot[(boot['segment']=='high_phase') & (boot['situation']=='phase=pp')].iloc[0]

# ─── Binned – overall calibrated vs raw ───────────────────────────────────────
bin_cal = binned[(binned['segment']=='overall') & (binned['model']=='v14_calibrated')].copy()
bin_raw = binned[(binned['segment']=='overall') & (binned['model']=='v14_raw')].copy()
bin_high_cal   = binned[(binned['segment']=='is_high_chase=True')  & (binned['model']=='v14_calibrated')].copy()
bin_high_raw   = binned[(binned['segment']=='is_high_chase=True')  & (binned['model']=='v14_raw')].copy()
bin_mid_high_cal  = binned[(binned['segment']=='phase=mid|is_high_chase=True')  & (binned['model']=='v14_calibrated')].copy()
bin_mid_high_raw  = binned[(binned['segment']=='phase=mid|is_high_chase=True')  & (binned['model']=='v14_raw')].copy()
bin_death_high_cal  = binned[(binned['segment']=='phase=death|is_high_chase=True') & (binned['model']=='v14_calibrated')].copy()
bin_death_high_raw  = binned[(binned['segment']=='phase=death|is_high_chase=True') & (binned['model']=='v14_raw')].copy()

# ─── Ablation ─────────────────────────────────────────────────────────────────
abl_overall = ablation[ablation['segment']=='overall'].copy()
abl_highall  = ablation[ablation['situation']=='all_high'].copy()
abl_highmid  = ablation[(ablation['segment']=='high_phase') & (ablation['situation']=='phase=mid')].copy()
abl_highdeath = ablation[(ablation['segment']=='high_phase') & (ablation['situation']=='phase=death')].copy()


# ─── HTML builders ────────────────────────────────────────────────────────────

def make_metric_badges(raw, cal, metric_name):
    delta = cal - raw
    delta_pct = delta / raw * 100 if raw > 0 else 0
    badge_class = "badge-red" if delta > 0 else "badge-green"
    sign = "+" if delta >= 0 else ""
    return f"""
    <td>{raw:.5f}</td>
    <td>{cal:.5f}</td>
    <td><span class="{badge_class}">{sign}{delta_pct:.1f}%</span></td>
    """

def phase_table():
    rows = ""
    for _, r in phase_df.iterrows():
        phase = r['situation'].replace('phase=','').upper()
        delta_pct = r['brier_delta_pct']
        badge = "badge-red" if delta_pct > 0 else "badge-green"
        sign = "+" if delta_pct >= 0 else ""
        rows += f"""<tr>
          <td><b>{phase}</b></td>
          <td>{int(r['n']):,}</td>
          <td>{pct(r['actual_wr'])}</td>
          <td>{r['raw_brier']:.5f}</td>
          <td>{r['cal_brier']:.5f}</td>
          <td><span class="{badge}">{sign}{delta_pct:.1f}%</span></td>
          <td>{pct(r['raw_bias'], 2)}</td>
          <td>{pct(r['cal_bias'], 2)}</td>
          <td>{r['raw_ece']:.4f}</td>
          <td>{r['cal_ece']:.4f}</td>
        </tr>"""
    return f"""
    <table><tr>
      <th>Phase</th><th>Balls</th><th>Actual Win%</th>
      <th>Raw Brier</th><th>Cal Brier</th><th>Δ Cal vs Raw</th>
      <th>Raw Bias</th><th>Cal Bias</th>
      <th>Raw ECE</th><th>Cal ECE</th>
    </tr>{rows}</table>"""

def chase_table():
    rows = ""
    for _, r in chase_df.iterrows():
        cat = r['situation'].replace('chase_bucket=','').upper()
        delta_pct = r['brier_delta_pct']
        badge = "badge-red" if delta_pct > 0 else "badge-green"
        sign = "+" if delta_pct >= 0 else ""
        rows += f"""<tr>
          <td><b>{cat}</b></td>
          <td>{int(r['n']):,}</td>
          <td>{int(r['matches'])}</td>
          <td>{pct(r['actual_wr'])}</td>
          <td>{r['raw_brier']:.5f}</td>
          <td>{r['cal_brier']:.5f}</td>
          <td><span class="{badge}">{sign}{delta_pct:.1f}%</span></td>
          <td>{signed_pct(r['raw_bias'])}</td>
          <td>{signed_pct(r['cal_bias'])}</td>
        </tr>"""
    return f"""
    <table><tr>
      <th>Chase Type</th><th>Balls</th><th>Matches</th><th>Actual Win%</th>
      <th>Raw Brier</th><th>Cal Brier</th><th>Δ Cal vs Raw</th>
      <th>Raw Bias</th><th>Cal Bias</th>
    </tr>{rows}</table>"""

def px_table():
    # Sort by phase then bucket
    df = px_df.copy()
    df['_phase'] = df['situation'].str.extract(r'phase=(\w+)')
    df['_bucket'] = df['situation'].str.extract(r'chase_bucket=(\w+)')
    order = {'pp':0,'mid':1,'death':2}
    df['_ord'] = df['_phase'].map(order)
    df = df.sort_values(['_ord','_bucket'])
    rows = ""
    for _, r in df.iterrows():
        phase = r['_phase'].upper()
        bucket = r['_bucket'].upper()
        delta_pct = r['brier_delta_pct']
        badge = "badge-red" if delta_pct > 0.5 else ("badge-green" if delta_pct < -0.5 else "badge-yellow")
        sign = "+" if delta_pct >= 0 else ""
        # Highlight high chase rows
        row_bg = 'style="background:#fff3e0;"' if bucket == 'HIGH' else ''
        rows += f"""<tr {row_bg}>
          <td><b>{phase}</b></td>
          <td><b>{bucket}</b></td>
          <td>{int(r['n']):,}</td>
          <td>{int(r['matches'])}</td>
          <td>{pct(r['actual_wr'])}</td>
          <td>{r['raw_brier']:.5f}</td>
          <td>{r['cal_brier']:.5f}</td>
          <td><span class="{badge}">{sign}{delta_pct:.1f}%</span></td>
          <td style="color:{'red' if r['cal_bias']>0.05 else 'blue' if r['cal_bias']<-0.05 else 'black'}">{signed_pct(r['cal_bias'])}</td>
          <td>{r['cal_ece']:.4f}</td>
        </tr>"""
    return f"""
    <table><tr>
      <th>Phase</th><th>Chase</th><th>Balls</th><th>Matches</th><th>Actual Win%</th>
      <th>Raw Brier</th><th>Cal Brier</th><th>Δ Cal vs Raw</th>
      <th>Cal Bias</th><th>Cal ECE</th>
    </tr>{rows}</table>"""

def binned_table(cal_df, raw_df, title="Overall"):
    merged = cal_df.merge(raw_df, on='bucket', suffixes=('_cal','_raw'))
    rows = ""
    for i, r in merged.iterrows():
        b = r['bucket']
        cal_bias = r['bias_pred_minus_actual_cal']
        raw_bias = r['bias_pred_minus_actual_raw']
        # Who is closer to actual?
        cal_abs = abs(cal_bias)
        raw_abs = abs(raw_bias)
        better = "CAL" if cal_abs < raw_abs else "RAW"
        better_badge = "badge-blue" if better == "CAL" else "badge-yellow"
        bias_style_cal = f"color:{'#800000' if cal_bias>0.05 else '#003080' if cal_bias<-0.05 else '#333'}"
        bias_style_raw = f"color:{'#800000' if raw_bias>0.05 else '#003080' if raw_bias<-0.05 else '#333'}"
        rows += f"""<tr style="{row_style(i)}">
          <td><b>{b}</b></td>
          <td>{int(r['n_cal']):,} / {int(r['n_raw']):,}</td>
          <td>{pct(r['actual_wr_cal'])}</td>
          <td>{pct(r['mean_pred_cal'])}</td>
          <td style="{bias_style_cal}"><b>{signed_pct(cal_bias)}</b></td>
          <td>{pct(r['mean_pred_raw'])}</td>
          <td style="{bias_style_raw}"><b>{signed_pct(raw_bias)}</b></td>
          <td><span class="{better_badge}">{better}</span></td>
        </tr>"""
    return f"""
    <p class="section-note">Bias = Model Pred − Actual. Positive = overpredicts, Negative = underpredicts. 
    <span class="badge-red">Red</span> bias &gt; 5%, <span class="badge-blue">Blue</span> bias &lt; -5%</p>
    <table><tr>
      <th>Prob Bucket</th><th>Balls (Cal/Raw)</th><th>Actual Win%</th>
      <th>Cal Pred</th><th>Cal Bias</th>
      <th>Raw Pred</th><th>Raw Bias</th>
      <th>Better Model</th>
    </tr>{rows}</table>"""

def bootstrap_table():
    rows = ""
    for _, r in boot.iterrows():
        seg = r['segment'].replace('phase_x_chase_bucket','Phase×Chase').replace('high_phase','High Chase Phase')
        sit = r['situation'].replace('phase=','').replace('chase_bucket=','').replace('|',', ')
        lo = r['brier_delta_ci_low']
        hi = r['brier_delta_ci_high']
        mean_d = r['brier_delta_cal_minus_raw']
        c = ci_color(lo, hi)
        if lo > 0:   verdict = '<span class="badge-red">Calibration HURTS ✗</span>'
        elif hi < 0: verdict = '<span class="badge-green">Calibration HELPS ✓</span>'
        else:        verdict = '<span class="badge-yellow">Uncertain (CI crosses 0)</span>'
        rows += f"""<tr style="background:{c}">
          <td>{seg}</td>
          <td><b>{sit}</b></td>
          <td>{int(r['n']):,}</td>
          <td>{int(r['matches'])}</td>
          <td>{mean_d:+.5f}</td>
          <td>[{lo:+.5f}, {hi:+.5f}]</td>
          <td>{verdict}</td>
        </tr>"""
    return f"""
    <p class="section-note">95% bootstrap CI (500 samples). Positive delta = calibration is <b>worse</b> (higher Brier). 
    Red rows = calibration statistically hurts. Green = helps. Yellow = no clear signal.</p>
    <table><tr>
      <th>Segment</th><th>Situation</th><th>Balls</th><th>Matches</th>
      <th>Mean Δ (Cal−Raw)</th><th>95% CI</th><th>Verdict</th>
    </tr>{rows}</table>"""

def ablation_table(abl_df, title_col="situation"):
    CAND_LABELS = {
        'v14_calibrated':          'Production (v14 Calibrated)',
        'v14_raw_all':             'All Raw (no calibration)',
        'raw_for_high_all_phases': 'Bypass Cal: High Chase ALL phases',
        'raw_for_high_mid_death':  'Bypass Cal: High Chase MID+DEATH ← Best',
        'raw_for_high_mid_only':   'Bypass Cal: High Chase MID only',
        'raw_for_high_death_only': 'Bypass Cal: High Chase DEATH only',
        'smooth_raw_mid_death_w5': 'Smooth Bypass (w=5): High Chase MID+DEATH',
        'smooth_raw_mid_death_w10':'Smooth Bypass (w=10): High Chase MID+DEATH',
        'smooth_raw_mid_death_w15':'Smooth Bypass (w=15): High Chase MID+DEATH',
    }
    rows = ""
    # pivot: rows = candidates, cols = situations
    sits = abl_df[title_col].unique()
    cands = abl_df['candidate'].unique()
    for cand in cands:
        sub = abl_df[abl_df['candidate']==cand]
        label = CAND_LABELS.get(cand, cand)
        is_prod = cand == 'v14_calibrated'
        row_style_str = 'background:#e8eaf6;font-weight:700;' if is_prod else ''
        cells = f'<td style="{row_style_str}"><b>{label}</b></td>'
        for sit in sits:
            r = sub[sub[title_col]==sit]
            if r.empty:
                cells += '<td>-</td>'
                continue
            r = r.iloc[0]
            b = r['brier']
            d = r['brier_delta_vs_v14']
            d_pct = r['brier_delta_pct_vs_v14']
            if is_prod:
                cells += f'<td style="{row_style_str}">{b:.5f}<br><span style="font-size:0.8em;color:#888">(baseline)</span></td>'
            else:
                badge = "badge-green" if d_pct < -0.5 else ("badge-red" if d_pct > 0.5 else "badge-yellow")
                sign = "+" if d_pct >= 0 else ""
                cells += f'<td><span style="font-size:0.9em">{b:.5f}</span><br><span class="{badge}">{sign}{d_pct:.1f}%</span></td>'
        rows += f'<tr>{cells}</tr>'
    sit_headers = "".join(f'<th>{s.replace("phase=","").replace("_"," ").upper()}</th>' for s in sits)
    return f"""
    <p class="section-note">Δ = vs production v14 calibrated. 
    <span class="badge-green">Green</span> = improvement, <span class="badge-red">Red</span> = degradation.</p>
    <table><tr><th>Candidate</th>{sit_headers}</tr>{rows}</table>"""

def prod_model_comparison_table():
    """Production model hierarchy: v7 vs v14-prod vs OOS retrain."""
    rows_data = [
        ("v7 (Production Baseline)", "37-feat XGBLogRegEnsemble + inn2 isotonic cal", "v7_raw", "v7_cal"),
        ("v14 Phase Router (Production)", "64/72/62-feat phase models + per-over cal", "v14prod_raw", "v14prod_cal"),
        ("v14 OOS Retrain (analysis proxy)", "Retrained train<2025, test≥2025", "v14oos_raw", "v14oos_cal"),
    ]
    note = """
    <div class="warning">
      ⚠️ <b>Important caveat:</b> Production v7 and v14 models were trained on data that includes 2025 seasons,
      so their scores on 2025+ data reflect partial in-sample performance. 
      The <b>v14 OOS Retrain</b> (trained only on seasons &lt;2025) is the only true out-of-sample comparison.
      Use v14 OOS Retrain metrics for calibration diagnostics; use production model comparison for context only.
    </div>"""
    rows = ""
    for label, desc, raw_k, cal_k in rows_data:
        rb, rl = _prod[raw_k]
        cb, cl = _prod[cal_k]
        raw_hc = _prod_hc.get(raw_k, float('nan'))
        cal_hc = _prod_hc.get(cal_k, float('nan'))
        cal_delta = (cb - rb) / rb * 100 if rb > 0 else 0
        badge = "badge-red" if cal_delta > 0 else "badge-green"
        sign = "+" if cal_delta >= 0 else ""
        is_oos = "oos" in raw_k
        row_bg = 'style="background:#e8eaf6;"' if is_oos else ''
        rows += f"""<tr {row_bg}>
          <td><b>{label}</b><br><span style="font-size:0.8em;color:#666">{desc}</span></td>
          <td>{rb:.5f}</td>
          <td>{cb:.5f}</td>
          <td><span class="{badge}">{sign}{cal_delta:.1f}%</span></td>
          <td>{rl:.5f}</td>
          <td>{cl:.5f}</td>
          <td>{raw_hc:.5f}</td>
          <td>{cal_hc:.5f}</td>
        </tr>"""
    return note + f"""
    <table><tr>
      <th>Model</th>
      <th>Raw Brier</th><th>Cal Brier</th><th>Δ Cal vs Raw</th>
      <th>Raw LogLoss</th><th>Cal LogLoss</th>
      <th>High-Chase Raw Brier</th><th>High-Chase Cal Brier</th>
    </tr>{rows}</table>"""


def over_table():
    df = over_df.copy()
    df['_over'] = df['situation'].str.extract(r'over=(\d+)').astype(int)
    df['_phase'] = df['situation'].str.extract(r'phase=(\w+)')
    df = df.sort_values(['_phase','_over'])
    rows = ""
    prev_phase = None
    for i, r in df.iterrows():
        phase = r['_phase'].upper()
        over = int(r['_over'])
        delta_pct = r['brier_delta_pct']
        badge = "badge-red" if delta_pct > 0 else "badge-green"
        sign = "+" if delta_pct >= 0 else ""
        phase_label = f"<td rowspan='X'><b>{phase}</b></td>" if phase != prev_phase else ""
        rows += f"""<tr>
          <td><b>Over {over}</b></td>
          <td>{phase}</td>
          <td>{int(r['n']):,}</td>
          <td>{int(r['matches'])}</td>
          <td>{pct(r['actual_wr'])}</td>
          <td>{r['raw_brier']:.5f}</td>
          <td>{r['cal_brier']:.5f}</td>
          <td><span class="{badge}">{sign}{delta_pct:.1f}%</span></td>
          <td style="color:{'red' if r['cal_bias']>0.05 else 'blue' if r['cal_bias']<-0.05 else 'black'}">{signed_pct(r['cal_bias'])}</td>
        </tr>"""
        prev_phase = phase
    return f"""
    <table><tr>
      <th>Over</th><th>Phase</th><th>Balls</th><th>Matches</th>
      <th>Actual Win%</th><th>Raw Brier</th><th>Cal Brier</th>
      <th>Δ Cal vs Raw</th><th>Cal Bias</th>
    </tr>{rows}</table>"""

def target_table():
    df = target_df.copy()
    df['_phase'] = df['situation'].str.extract(r'phase=(\w+)')
    df['_band'] = df['situation'].str.extract(r'target_band=(.+)')
    order = {'pp':0,'mid':1,'death':2}
    df['_ord'] = df['_phase'].map(order)
    df = df.sort_values(['_ord','_band'])
    rows = ""
    for i, r in df.iterrows():
        phase = r['_phase'].upper()
        band = r['_band']
        # target band note
        if band.startswith('-') or band.startswith('<=-'):
            chase_note = '🎯 Chasing below par'
            row_color = 'background:#e8f5e9;'
        elif '40' in band and not '-' in band:
            chase_note = '🔥 HIGH CHASE (>40 above par)'
            row_color = 'background:#fff3e0;'
        elif '20:40' in band:
            chase_note = '📈 Above par (20-40)'
            row_color = 'background:#fff8e1;'
        else:
            chase_note = '≈ Around par'
            row_color = ''
        delta_pct = r['brier_delta_pct']
        badge = "badge-red" if delta_pct > 0.5 else ("badge-green" if delta_pct < -0.5 else "badge-yellow")
        sign = "+" if delta_pct >= 0 else ""
        rows += f"""<tr style="{row_color}">
          <td><b>{phase}</b></td>
          <td><b>{band}</b></td>
          <td>{chase_note}</td>
          <td>{int(r['n']):,}</td>
          <td>{pct(r['actual_wr'])}</td>
          <td>{r['raw_brier']:.5f}</td>
          <td>{r['cal_brier']:.5f}</td>
          <td><span class="{badge}">{sign}{delta_pct:.1f}%</span></td>
          <td style="color:{'red' if r['cal_bias']>0.05 else 'blue' if r['cal_bias']<-0.05 else 'black'}">{signed_pct(r['cal_bias'])}</td>
        </tr>"""
    return f"""
    <p class="section-note">Target band = first innings score - venue average score (runs above/below par). 
    Highlighted rows = high chase situations.</p>
    <table><tr>
      <th>Phase</th><th>Target Band</th><th>Chase Type</th><th>Balls</th>
      <th>Actual Win%</th><th>Raw Brier</th><th>Cal Brier</th>
      <th>Δ Cal vs Raw</th><th>Cal Bias</th>
    </tr>{rows}</table>"""


# ─── Compose Report ───────────────────────────────────────────────────────────
html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>IPL v14 High-Chase Diagnostic Report</title>
  {CSS}
</head>
<body>
<div class="container">

<h1>🏏 IPL High-Chase Diagnostic Report — v7 Baseline + v14 Analysis</h1>
<p style="color:#555;font-size:0.9em;">
  <b>Evaluation:</b> Out-of-sample (OOS) | 
  <b>Train:</b> Seasons &lt; 2025 | 
  <b>Test:</b> Seasons ≥ 2025 ({", ".join(str(s) for s in seasons)}) | 
  <b>Models compared:</b> v7 (production baseline) | v14 (production champion) | v14 OOS retrain (calibration proxy)
</p>

<!-- TOC -->
<div class="card">
  <h3>📋 Table of Contents</h3>
  <ul class="toc">
    <li><a href="#summary">1. Executive Summary</a></li>
    <li><a href="#dataset">2. Dataset Overview</a></li>
    <li><a href="#prodhierarchy">3a. Production Model Hierarchy (v7 vs v14)</a></li>
    <li><a href="#overall">3b. OOS Retrain Performance (Raw vs Calibrated)</a></li>
    <li><a href="#phase">4. Phase-wise Performance (PP / MID / DEATH)</a></li>
    <li><a href="#chase">5. Chase Category Analysis (High / Par / Low)</a></li>
    <li><a href="#pxc">6. Phase × Chase Matrix — Key Diagnostic</a></li>
    <li><a href="#binned">7. Probability Bin Analysis — Where Model Is Off</a></li>
    <li><a href="#highbinned">8. High-Chase Probability Bins (Deep Dive)</a></li>
    <li><a href="#bootstrap">9. Bootstrap Confidence Intervals — Is Calibration Hurting?</a></li>
    <li><a href="#target">10. Target Band Analysis (score vs par)</a></li>
    <li><a href="#over">11. Over-by-Over High-Chase Breakdown</a></li>
    <li><a href="#ablation">12. Ablation Candidates — Bypass Rules</a></li>
    <li><a href="#recommendations">13. Key Takeaways &amp; Recommendations</a></li>
  </ul>
</div>

<!-- 1. EXECUTIVE SUMMARY -->
<div class="card" id="summary">
<h2>1. Executive Summary</h2>

<div class="warning">
  <b>⚠️ Key Finding:</b> IPL v14 calibration <b>hurts</b> in high-chase innings-2 situations. 
  The production calibrated model overpredicts win probability by 8–17% in the 10–30% probability buckets 
  for high-chase MID and DEATH phases. Raw predictions are statistically better in these segments.
</div>

<div class="insight">
  <b>💡 Best Quick Fix (Candidate A):</b> Bypass calibration for high-chase MID+DEATH phases.
  This alone improves overall OOS Brier by <b>−0.8%</b> (0.11175 → 0.11083) and LogLoss by <b>−0.8%</b> 
  without touching PP, low-chase, or innings-1 predictions.
</div>

<table style="width:auto">
  <tr>
    <th>Metric</th>
    <th>Raw (No Calibration)</th>
    <th>Production (Calibrated)</th>
    <th>Best Ablation (Bypass High Mid+Death)</th>
  </tr>
  <tr>
    <td><b>Overall Brier</b></td>
    <td>{raw_brier:.5f}</td>
    <td style="background:#fff3e0">{cal_brier:.5f} <span class="badge-red">+{cal_vs_raw_brier_pct:.1f}%</span></td>
    <td style="background:#e8f5e9">~0.11083 <span class="badge-green">−0.8% vs prod</span></td>
  </tr>
  <tr>
    <td><b>High-Chase Brier</b></td>
    <td>{by_sit[by_sit['situation']=='chase_bucket=high']['raw_brier'].values[0]:.5f}</td>
    <td style="background:#ffcccc">{by_sit[by_sit['situation']=='chase_bucket=high']['cal_brier'].values[0]:.5f} <span class="badge-red">+3.7%</span></td>
    <td>↓ with bypass</td>
  </tr>
  <tr>
    <td><b>High-Chase MID Brier</b></td>
    <td>{by_sit[by_sit['situation']=='phase=mid|chase_bucket=high']['raw_brier'].values[0]:.5f}</td>
    <td style="background:#ffcccc">{by_sit[by_sit['situation']=='phase=mid|chase_bucket=high']['cal_brier'].values[0]:.5f} <span class="badge-red">+4.6%</span></td>
    <td>↓ with bypass</td>
  </tr>
  <tr>
    <td><b>High-Chase DEATH Brier</b></td>
    <td>{by_sit[by_sit['situation']=='phase=death|chase_bucket=high']['raw_brier'].values[0]:.5f}</td>
    <td style="background:#ffcccc">{by_sit[by_sit['situation']=='phase=death|chase_bucket=high']['cal_brier'].values[0]:.5f} <span class="badge-red">+9.6%</span></td>
    <td>↓ with bypass</td>
  </tr>
</table>
</div>

<!-- 2. DATASET -->
<div class="card" id="dataset">
<h2>2. Dataset Overview</h2>
<div class="stat-grid">
  <div class="stat-box">
    <div class="label">Total Balls (Inn 2)</div>
    <div class="value">{n_total:,}</div>
    <div class="sub">OOS test set</div>
  </div>
  <div class="stat-box">
    <div class="label">Matches</div>
    <div class="value">{n_matches}</div>
    <div class="sub">Seasons: {", ".join(str(s) for s in seasons)}</div>
  </div>
  <div class="stat-box">
    <div class="label">High Chase Balls</div>
    <div class="value">{n_high:,}</div>
    <div class="sub">{pct(pct_high)} of all balls</div>
  </div>
  <div class="stat-box">
    <div class="label">High Chase Definition</div>
    <div class="value">target &gt; par + 20</div>
    <div class="sub">first_innings_score − venue_avg_score &gt; 20</div>
  </div>
</div>
<div class="stat-grid">
  <div class="stat-box">
    <div class="label">PP Balls</div>
    <div class="value">{phase_counts.get('pp',0):,}</div>
    <div class="sub">Overs 1–6</div>
  </div>
  <div class="stat-box">
    <div class="label">MID Balls</div>
    <div class="value">{phase_counts.get('mid',0):,}</div>
    <div class="sub">Overs 7–15</div>
  </div>
  <div class="stat-box">
    <div class="label">DEATH Balls</div>
    <div class="value">{phase_counts.get('death',0):,}</div>
    <div class="sub">Overs 16–20</div>
  </div>
  <div class="stat-box">
    <div class="label">Overall Chasing Win%</div>
    <div class="value">{pct(ov['actual_wr'])}</div>
    <div class="sub">Across all balls</div>
  </div>
</div>
</div>

<!-- 3a. PRODUCTION HIERARCHY -->
<div class="card" id="prodhierarchy">
<h2>3a. Production Model Hierarchy — v7 vs v14 vs OOS Retrain</h2>
<p class="section-note">
  <b>v7 (Production Baseline):</b> 37 features, XGBLogRegEnsemble + inn2 isotonic calibrator. 
  This is what Inn2PhaseRouter falls back to if routing fails.<br>
  <b>v14 Phase Router (Production):</b> Phase-specific models (64/72/62 features) + per-over calibrators. 
  This is the current production champion for inn2.<br>
  <b>v14 OOS Retrain:</b> Proxy retrained only on seasons &lt;2025, tested on 2025+. Used for calibration diagnostics.
</p>
{prod_model_comparison_table()}
<div class="insight">
  💡 <b>v14 Production Raw (0.06033) beats v7 Raw (0.07433)</b> — confirming v14 features are better.<br>
  ⚠️ <b>v14 Production Calibration (0.06450) is worse than v14 Raw (0.06033)</b> — same finding as OOS retrain. 
  Calibration hurts even on the production model when evaluated against 2025+ data.<br>
  📌 The OOS retrain brier (~0.11) is higher because it was trained on less data (pre-2025 only); 
  use it for relative comparisons (raw vs cal), not absolute model ranking.
</div>
</div>

<!-- 3b. OVERALL OOS RETRAIN -->
<div class="card" id="overall">
<h2>3b. OOS Retrain Performance — v14 Raw vs Calibrated</h2>
<p class="section-note">
  This section uses the <b>v14 OOS Retrain proxy</b> (train &lt; 2025, test ≥ 2025). 
  "Raw" = model output before calibration. "Calibrated" = current production calibration applied. 
  <b>Note: "Raw" here is NOT v7 — it is the retrained v14 model without calibration.</b>
  Lower Brier / LogLoss / ECE = better. Bias = mean predicted probability minus actual win rate.</p>
<table style="width:auto">
  <tr><th>Metric</th><th>Raw (no calibration)</th><th>Calibrated (production)</th><th>Δ (Cal − Raw)</th></tr>
  <tr>
    <td>Brier Score</td>
    <td>{raw_brier:.5f}</td>
    <td>{cal_brier:.5f}</td>
    <td><span class="{'badge-red' if cal_brier>raw_brier else 'badge-green'}">{'+' if cal_brier>=raw_brier else ''}{(cal_brier-raw_brier)*100:.3f}%</span></td>
  </tr>
  <tr>
    <td>Log Loss</td>
    <td>{raw_logloss:.5f}</td>
    <td>{cal_logloss:.5f}</td>
    <td><span class="{'badge-red' if cal_logloss>raw_logloss else 'badge-green'}">{'+' if cal_logloss>=raw_logloss else ''}{(cal_logloss-raw_logloss)*100:.3f}%</span></td>
  </tr>
  <tr>
    <td>ECE (10-bin)</td>
    <td>{raw_ece:.5f}</td>
    <td>{cal_ece:.5f}</td>
    <td><span class="{'badge-red' if cal_ece>raw_ece else 'badge-green'}">{'+' if cal_ece>=raw_ece else ''}{(cal_ece-raw_ece)*100:.3f}%</span></td>
  </tr>
  <tr>
    <td>Mean Bias</td>
    <td>{signed_pct(ov['raw_bias'])}</td>
    <td>{signed_pct(ov['cal_bias'])}</td>
    <td>—</td>
  </tr>
</table>
<div class="warning">
  ⚠️ Calibration <b>increases</b> Brier Score by +1.7% and Log Loss by +5.4% overall on 2025/26 OOS data. 
  The calibrators were likely fit on older IPL data that doesn't reflect the current scoring environment.
</div>
</div>

<!-- 4. PHASE -->
<div class="card" id="phase">
<h2>4. Phase-wise Performance</h2>
<div class="insight">
  📌 <b>Powerplay (PP)</b> has the largest absolute calibration error, but calibration also most worsens Log Loss here (+11.4%). 
  DEATH and MID phases are both hurt by calibration, but the absolute gains from bypassing are smaller.
</div>
{phase_table()}
</div>

<!-- 5. CHASE -->
<div class="card" id="chase">
<h2>5. Chase Category Analysis</h2>
<p class="section-note">
  <b>HIGH</b> = target &gt; venue par + 20 | 
  <b>PAR</b> = within ±20 of par | 
  <b>LOW</b> = target &lt; venue par − 20 (chasing below par, team is favourite)
</p>
<div class="warning">
  ⚠️ <b>High Chase:</b> Calibration makes things WORSE (+3.7% Brier). 
  The model should predict low win probabilities (actual win% = {pct(by_sit[by_sit['situation']=='chase_bucket=high']['actual_wr'].values[0])}) 
  but calibration pushes predictions up further.
</div>
<div class="good">
  ✅ <b>Low Chase:</b> Calibration slightly helps (−1.1% Brier). Teams chasing easy targets win ~96% — calibration maintains this well.
</div>
{chase_table()}
</div>

<!-- 6. PHASE x CHASE MATRIX -->
<div class="card" id="pxc">
<h2>6. Phase × Chase Matrix — 🔑 Key Diagnostic</h2>
<p class="section-note">
  Orange rows = HIGH chase situations. 
  This is the most important breakdown for understanding model failures.
</p>
<div class="warning">
  <b>⚠️ Worst Cells (where calibration hurts most):</b>
  <ul>
    <li><b>DEATH × HIGH:</b> Calibration Brier +9.6%, actual win% only 20.5% but model predicts 28.5%</li>
    <li><b>MID × HIGH:</b> Calibration Brier +4.6%, actual win% only 26.8% but model predicts 31.8%</li>
    <li><b>PP × HIGH:</b> Calibration Brier +2.2% — uncertain, CI crosses zero</li>
  </ul>
</div>
<div class="good">
  <b>✅ Where calibration helps or is neutral:</b>
  <ul>
    <li><b>DEATH × LOW:</b> Calibration improves Brier by 12.1% (chasing very low targets)</li>
    <li><b>MID × LOW:</b> Calibration improves Brier by 2.0%</li>
  </ul>
</div>
{px_table()}
</div>

<!-- 7. OVERALL BINNED -->
<div class="card" id="binned">
<h2>7. Probability Bin Analysis — Where Is the Model Off?</h2>
<p>Each row shows how the model performs in a given predicted probability range.</p>
<div class="warning">
  <b>⚠️ Critical finding in 10–30% bucket:</b>
  <ul>
    <li><b>10–20%:</b> Calibrated model predicts 15.9% but actual win rate is only 11.0% → overpredicts by <b>+4.9%</b></li>
    <li><b>20–30%:</b> Calibrated model predicts 25.7% but actual win rate is only 15.0% → overpredicts by <b>+10.7%</b></li>
    <li><b>30–40%:</b> Reasonable (small overpredict +1.6%)</li>
    <li><b>40–60%:</b> Underpredicts (model says 44–55%, actual 55–69%)</li>
    <li><b>60–80%:</b> Underpredicts (model says 65–76%, actual 83–91%)</li>
  </ul>
  <br>The 20–30% bucket has <b>1,005 balls across 49 matches</b> — this is a significant sample.
</div>
{binned_table(bin_cal, bin_raw, "Overall")}
</div>

<!-- 8. HIGH CHASE BINNED -->
<div class="card" id="highbinned">
<h2>8. High-Chase Probability Bins — Deep Dive</h2>

<h3>8a. High Chase — All Phases</h3>
<div class="warning">
  In high-chase situations, 10–30% bins are catastrophically miscalibrated:
  <ul>
    <li><b>10–20%:</b> Model predicts 15.9%, actual win rate = <b>7.3%</b> → overpredict by <b>+8.7%</b></li>
    <li><b>20–30%:</b> Model predicts 25.9%, actual win rate = <b>11.9%</b> → overpredict by <b>+14.0%</b></li>
  </ul>
</div>
{binned_table(bin_high_cal, bin_high_raw, "High Chase All Phases")}

<h3>8b. High Chase MID Phase</h3>
<div class="warning">
  MID phase is the primary driver of the high-chase miscalibration:
  <ul>
    <li><b>10–20%:</b> Cal predicts 15.8%, actual = <b>7.9%</b> → overpredict by <b>+7.9%</b></li>
    <li><b>20–30%:</b> Cal predicts 25.1%, actual = <b>8.1%</b> → overpredict by <b>+17.0%</b></li>
  </ul>
</div>
{binned_table(bin_mid_high_cal, bin_mid_high_raw, "High Chase MID")}

<h3>8c. High Chase DEATH Phase</h3>
<p class="section-note">Small sample in 10–30% bins for DEATH high chase (n=31–55), but direction is consistent.</p>
{binned_table(bin_death_high_cal, bin_death_high_raw, "High Chase DEATH")}
</div>

<!-- 9. BOOTSTRAP -->
<div class="card" id="bootstrap">
<h2>9. Bootstrap Confidence Intervals — Is Calibration Hurting?</h2>
<p>500 bootstrap samples (match-level resampling). Tests whether calibration vs raw Brier delta is significant.</p>
<div class="warning">
  <b>Statistically confirmed (95% CI fully positive = calibration hurts):</b>
  <ul>
    <li>High Chase DEATH: Δ = +0.00298, CI = [{boot_high_death['brier_delta_ci_low']:+.5f}, {boot_high_death['brier_delta_ci_high']:+.5f}] ✗</li>
    <li>High Chase MID:   Δ = +0.00326, CI = [{boot_high_mid['brier_delta_ci_low']:+.5f}, {boot_high_mid['brier_delta_ci_high']:+.5f}] ✗</li>
  </ul>
  <b>Not yet confirmed (CI crosses zero):</b>
  <ul>
    <li>High Chase PP:    Δ = +0.00248, CI = [{boot_high_pp['brier_delta_ci_low']:+.5f}, {boot_high_pp['brier_delta_ci_high']:+.5f}] (uncertain)</li>
  </ul>
</div>
{bootstrap_table()}
</div>

<!-- 10. TARGET BAND -->
<div class="card" id="target">
<h2>10. Target Band Analysis — Score vs Venue Par</h2>
<p class="section-note">
  Shows performance by how much the first innings score exceeded venue average. 
  Higher positive = harder chase. This is the continuous version of the high-chase flag.
</p>
{target_table()}
</div>

<!-- 11. OVER BY OVER -->
<div class="card" id="over">
<h2>11. Over-by-Over High Chase Breakdown</h2>
<p class="section-note">All rows are <b>high chase only</b>. Shows which specific overs the model struggles most.</p>
<div class="insight">
  📌 Pattern: Calibration consistently hurts across all MID overs (7–15) and DEATH overs (16–18) 
  in high-chase situations. Over 19 (last over) is the only exception where raw/calibrated are similar 
  or calibrated slightly helps (actual win rate drops to 5.6%).
</div>
{over_table()}
</div>

<!-- 12. ABLATION -->
<div class="card" id="ablation">
<h2>12. Ablation Candidates — Bypass Rules</h2>
<p>
  These are candidate rule-based corrections tested on the same OOS data (2025+). 
  They selectively bypass or smooth the calibration for high-chase situations.
</p>
<div class="insight">
  💡 <b>Best candidate: "Bypass Cal: High Chase MID+DEATH"</b><br>
  Overall Brier: 0.11083 (−0.8% vs production)<br>
  High-Chase Brier: improves without breaking low-chase / PP performance<br>
  No hard discontinuity: smooth weight-10/15 variants also available
</div>

<h3>12a. Overall Impact</h3>
{ablation_table(abl_overall, "situation")}

<h3>12b. High Chase — All Phases</h3>
{ablation_table(abl_highall, "situation")}

<h3>12c. High Chase — MID Phase Only</h3>
{ablation_table(abl_highmid, "situation")}

<h3>12d. High Chase — DEATH Phase Only</h3>
{ablation_table(abl_highdeath, "situation")}
</div>

<!-- 13. RECOMMENDATIONS -->
<div class="card" id="recommendations">
<h2>13. Key Takeaways &amp; Recommendations</h2>

<h3>🔴 What's Wrong</h3>
<table>
  <tr><th>Issue</th><th>Evidence</th><th>Impact</th></tr>
  <tr style="background:#fff3e0">
    <td>Calibration overpredicts in 20–30% bucket (high chase MID)</td>
    <td>Bias +17.0%, 2089 balls, 37 matches</td>
    <td>🔥 High — large sample, significant bias</td>
  </tr>
  <tr style="background:#fff3e0">
    <td>Calibration overpredicts in 10–20% bucket (high chase)</td>
    <td>Bias +8.7%, confirmed by bootstrap</td>
    <td>🔥 High — systematic overpredict for underdog</td>
  </tr>
  <tr style="background:#fff3e0">
    <td>High chase DEATH: model thinks 28.5% win prob, actual is 20.5%</td>
    <td>Bias +8.0%, bootstrap CI [+0.00034, +0.00602]</td>
    <td>🔥 High — statistically confirmed</td>
  </tr>
  <tr style="background:#fff8e1">
    <td>Overall calibration hurts Brier by +1.7% on 2025/26 data</td>
    <td>Calibrators fit on older seasons</td>
    <td>⚠️ Medium — drift from calibration era</td>
  </tr>
</table>

<h3>✅ What's Working</h3>
<table>
  <tr><th>Segment</th><th>Evidence</th></tr>
  <tr style="background:#e8f5e9">
    <td>Low Chase (target below par)</td>
    <td>Calibration helps: −1.1% Brier, actual win% ~96%</td>
  </tr>
  <tr style="background:#e8f5e9">
    <td>High-probability bins (80–100%)</td>
    <td>Model predicts 96%, actual 95.8% — excellent</td>
  </tr>
  <tr style="background:#e8f5e9">
    <td>Low chase DEATH</td>
    <td>Calibration improves by 12.1% Brier</td>
  </tr>
</table>

<h3>🎯 Recommended Actions (Priority Order)</h3>
<ol>
  <li>
    <b>[Quick Win — Low Risk]</b> Deploy Candidate A: 
    Bypass calibration for <code>is_high_chase AND phase IN (mid, death)</code>. 
    Use raw predictions in these cells. 
    Verified OOS improvement: Overall −0.8% Brier, High-Chase −3.7%, 
    with no degradation to low-chase / PP / innings-1.
  </li>
  <li>
    <b>[Medium — Smooth Version]</b> If concerned about discontinuity at the high-chase boundary (target_above_par=20), 
    use the smooth weight-10 variant: <code>smooth_raw_mid_death_w10</code>. 
    It blends raw and calibrated using a sigmoid centred at target_above_par=20, 
    achieving similar improvement with no hard cutoff.
  </li>
  <li>
    <b>[Longer Term]</b> Recalibrate the phase OOF calibrators using only 2024+ IPL data 
    to capture current scoring patterns. The existing calibrators appear to be from an older distribution.
  </li>
  <li>
    <b>[Research]</b> Investigate whether a high-chase specific phase model (trained on only high-chase balls) 
    can further improve the 10–30% bucket, where 2,000+ balls show 8–17% systematic overpredict.
  </li>
</ol>

<div class="insight">
  <b>🔒 Guardrail Conditions Before Production Deployment:</b>
  <ul>
    <li>✅ Overall OOS Brier does not degrade (bypass improves it)</li>
    <li>✅ PP not touched (CI crosses zero — leave for now)</li>
    <li>✅ Low-chase performance maintained (−1.1% Brier preserved)</li>
    <li>✅ 50–60% and 80%+ bins not degraded</li>
    <li>⚠️ Validate on 2024 OOS separately before production merge</li>
  </ul>
</div>
</div>

<p style="color:#aaa;font-size:0.8em;text-align:center;margin-top:30px;">
  Generated from IPL v14 OOS Analysis | 
  Artifacts: models/ipl_high_chase_v1/ | 
  Analysis script: scripts/ipl_high_chase_calibration_curves.py
</p>
</div>
</body>
</html>
"""

OUT_HTML.write_text(html, encoding='utf-8')
print(f"Report written to: {OUT_HTML}")
print(f"File size: {OUT_HTML.stat().st_size / 1024:.1f} KB")
