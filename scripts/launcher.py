"""
Cricket Live Predictor Launcher — Desktop GUI
==============================================
Tkinter app to start/stop multiple concurrent CREX live predictors and
the Streamlit dashboard. Supports auto-detecting the league from CREX
URLs, launching predictors in separate terminal windows, and starting
reduced-over / MC-only runs from the GUI.

Usage:
    python scripts/launcher.py
"""

import os
import re
import sys
import signal
import subprocess
import threading
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
from pathlib import Path
from datetime import datetime

# ---------------------------------------------------------------------------
# Project root (repo root, one level up from scripts/)
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent
os.chdir(PROJECT_ROOT)

MAX_MATCH_SLOTS = 6
WINDOWS_PROCESS_GROUP = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
WINDOWS_NEW_CONSOLE = getattr(subprocess, "CREATE_NEW_CONSOLE", 0)

# ---------------------------------------------------------------------------
# League presets — model_dir, feature_store_dir, output_json, states_dir
# ---------------------------------------------------------------------------
LEAGUE_CONFIGS = {
    "IPL": {
        "league": "ipl",
        "model_dir": "models/t20_male_v2",
        "feature_store_dir": "data/ipl_feature_store_v2",
        "output_json": "data/ipl_live_ml.json",
        "display_json": "data/ipl_live_ml_odm.json",
        "odm_model_dir": "models/odm_v1",
        "states_dir": "data/match_states/ipl",
    },
    "PSL": {
        "league": "psl",
        "model_dir": "models/t20_male_v2",
        "feature_store_dir": "data/psl_feature_store_v1",
        "output_json": "data/psl_live_ml.json",
        "display_json": "data/psl_live_ml_odm.json",
        "odm_model_dir": "models/odm_v1",
        "states_dir": "data/match_states/psl",
    },
    "BBL": {
        "league": "bbl",
        "model_dir": "models/bbl_v12",
        "feature_store_dir": "data/bbl_feature_store_v2",
        "output_json": "data/bbl_live_ml.json",
        "states_dir": "data/match_states/bbl",
    },
    "SA20": {
        "league": "sa20",
        "model_dir": "models/t20_male_v2",
        "feature_store_dir": "data/bbl_feature_store_v2",
        "output_json": "data/sa20_live_ml.json",
        "states_dir": "data/match_states/sa20",
    },
    "ILT20": {
        "league": "ilt20",
        "model_dir": "models/ilt20_v5",
        "feature_store_dir": "data/ilt_feature_store_v3",
        "output_json": "data/ilt20_live_ml.json",
        "states_dir": "data/match_states/ilt20",
    },
    "WPL": {
        "league": "wpl",
        "model_dir": "models/wpl_v2",
        "feature_store_dir": "data/bbl_feature_store_v2",
        "output_json": "data/wpl_live_ml.json",
        "states_dir": "data/match_states/wpl",
    },
    "T20 World Cup": {
        "league": "t20i_male",
        "model_dir": "models/t20_international_male_v2",
        "feature_store_dir": "data/t20_international_male_feature_store_v2",
        "output_json": "data/wc_live_ml.json",
        "states_dir": "data/match_states/t20_wc",
    },
    "SSM (Super Smash)": {
        "league": "ssm",
        "model_dir": "models/t20_male_v2",
        "feature_store_dir": "data/bbl_feature_store_v2",
        "output_json": "data/ssm_live_ml.json",
        "states_dir": "data/match_states/ssm",
    },
    "BPL": {
        "league": "bpl",
        "model_dir": "models/t20_male_v2",
        "feature_store_dir": "data/bbl_feature_store_v2",
        "output_json": "data/bpl_live_ml.json",
        "states_dir": "data/match_states/bpl",
    },
}

# Patterns in CREX URLs → league key
_URL_LEAGUE_PATTERNS: list[tuple[str, str]] = [
    (r"indian-premier-league", "IPL"),
    (r"pakistan-super-league", "PSL"),
    (r"big-bash-league", "BBL"),
    (r"betway-sa20|sa20-league|sa20", "SA20"),
    (r"international-league-t20|ilt20", "ILT20"),
    (r"womens-premier-league|wpl", "WPL"),
    (r"t20-world-cup|icc-mens-t20", "T20 World Cup"),
    (r"super-smash", "SSM (Super Smash)"),
    (r"bangladesh-premier-league|bpl", "BPL"),
]


def detect_league_from_url(url: str) -> str | None:
    """Return the LEAGUE_CONFIGS key if the URL matches a known league."""
    url_lower = url.lower()
    for pattern, league_key in _URL_LEAGUE_PATTERNS:
        if re.search(pattern, url_lower):
            return league_key
    return None


def _detect_package_source() -> str:
    """Return the filesystem path the bbl_pipeline package is loaded from."""
    try:
        import bbl_pipeline
        return str(Path(bbl_pipeline.__file__).resolve().parent.parent)
    except ImportError:
        return "(not installed)"


def _python_executable() -> str:
    """Prefer the repository virtualenv interpreter for launcher child processes."""
    candidates = [
        PROJECT_ROOT / ".venv" / "Scripts" / "python.exe",
        PROJECT_ROOT / ".venv" / "bin" / "python",
    ]
    for candidate in candidates:
        if candidate.exists():
            return str(candidate)
    return sys.executable


def build_output_json_path(output_json: str, mc_only: bool = False) -> str:
    """Return the base output JSON path for the selected prediction mode."""
    path = Path(output_json)
    stem = path.stem
    if mc_only:
        if stem.endswith("_live_ml"):
            stem = f"{stem[:-len('_live_ml')]}_live_mc"
        elif stem.endswith("_ml"):
            stem = f"{stem[:-len('_ml')]}_mc"
        elif not stem.endswith("_mc"):
            stem = f"{stem}_mc"
    return str(path.with_name(f"{stem}{path.suffix}"))


def build_slot_output_json(output_json: str, slot_idx: int, mc_only: bool = False) -> str:
    """Return the per-slot output JSON path used by the launcher."""
    path = Path(build_output_json_path(output_json, mc_only=mc_only))
    return str(path.with_name(f"{path.stem}_{slot_idx + 1}{path.suffix}"))


def build_slot_display_json(
    output_json: str,
    slot_idx: int,
    *,
    mc_only: bool = False,
    display_json: str | None = None,
) -> str:
    """Return the JSON path the dashboard should read for this launcher slot."""
    if mc_only or not display_json:
        return build_slot_output_json(output_json, slot_idx, mc_only=mc_only)
    return build_slot_output_json(display_json, slot_idx)


def format_output_json_hint(output_json: str) -> str:
    """Format the launcher hint for the active output JSON file."""
    return f"Output JSON: {Path(output_json)}"


def format_slot_output_hint(output_json: str, display_json: str | None = None) -> str:
    """Format the launcher hint including the ODM mirror when present."""
    hint = format_output_json_hint(output_json)
    if display_json and Path(display_json) != Path(output_json):
        return f"{hint} | ODM mirror: {Path(display_json)}"
    return hint


class MatchSlot:
    """One row in the matches panel: URL entry + league combo + start/stop."""

    def __init__(self, parent: ttk.Frame, idx: int, app: "LauncherApp"):
        self.app = app
        self.idx = idx
        self.proc: subprocess.Popen | None = None
        self.bridge_proc: subprocess.Popen | None = None

        self.frame = ttk.Frame(parent)
        self.frame.pack(fill="x", pady=2)
        self.row = ttk.Frame(self.frame)
        self.row.pack(fill="x")

        # Slot label
        ttk.Label(self.row, text=f"#{idx + 1}", width=3).pack(side="left")

        # URL entry
        self.url_var = tk.StringVar()
        self.url_var.trace_add("write", self._on_url_change)
        self.url_entry = ttk.Entry(self.row, textvariable=self.url_var, width=72)
        self.url_entry.pack(side="left", padx=(2, 4))

        # League dropdown
        self.league_var = tk.StringVar(value="IPL")
        self.league_var.trace_add("write", self._refresh_output_hint)
        self.league_combo = ttk.Combobox(
            self.row, textvariable=self.league_var,
            values=list(LEAGUE_CONFIGS.keys()), state="readonly", width=16,
        )
        self.league_combo.pack(side="left", padx=2)

        # Start / Stop
        self.start_btn = ttk.Button(self.row, text="▶", width=3, command=self.start)
        self.start_btn.pack(side="left", padx=2)
        self.stop_btn = ttk.Button(self.row, text="⏹", width=3, command=self.stop, state="disabled")
        self.stop_btn.pack(side="left", padx=2)

        # Status indicator
        self.status_var = tk.StringVar(value="idle")
        self.status_label = ttk.Label(self.row, textvariable=self.status_var,
                                      foreground="gray", width=22)
        self.status_label.pack(side="left", padx=(4, 0))

        self.output_hint_var = tk.StringVar()
        self.output_hint_label = ttk.Label(
            self.frame,
            textvariable=self.output_hint_var,
            foreground="gray",
        )
        self.output_hint_label.pack(anchor="w", padx=(28, 0))

        self.options_row = ttk.Frame(self.frame)
        self.options_row.pack(anchor="w", padx=(28, 0), pady=(2, 0))

        self.mc_only_var = tk.BooleanVar(value=False)
        self.mc_only_var.trace_add("write", self._refresh_output_hint)
        ttk.Checkbutton(
            self.options_row,
            text="MC-only",
            variable=self.mc_only_var,
        ).pack(side="left")

        ttk.Label(self.options_row, text="Total overs").pack(side="left", padx=(12, 4))
        self.total_overs_var = tk.StringVar()
        self.total_overs_var.trace_add("write", self._refresh_output_hint)
        self.total_overs_entry = ttk.Entry(self.options_row, textvariable=self.total_overs_var, width=6)
        self.total_overs_entry.pack(side="left")

        ttk.Label(self.options_row, text="Revised target").pack(side="left", padx=(12, 4))
        self.revised_target_var = tk.StringVar()
        self.revised_target_entry = ttk.Entry(self.options_row, textvariable=self.revised_target_var, width=7)
        self.revised_target_entry.pack(side="left")

        self._refresh_output_hint()

    # --- Auto-detect league when URL changes ---
    def _on_url_change(self, *_args):
        url = self.url_var.get().strip()
        if url:
            detected = detect_league_from_url(url)
            if detected:
                self.league_var.set(detected)

    def _current_output_json(self) -> str:
        cfg = LEAGUE_CONFIGS[self.league_var.get()]
        return build_slot_output_json(
            cfg["output_json"],
            self.idx,
            mc_only=self._requested_mc_only(),
        )

    def _current_display_json(self) -> str:
        cfg = LEAGUE_CONFIGS[self.league_var.get()]
        return build_slot_display_json(
            cfg["output_json"],
            self.idx,
            mc_only=self._requested_mc_only(),
            display_json=cfg.get("display_json"),
        )

    def _refresh_output_hint(self, *_args):
        self.output_hint_var.set(
            format_slot_output_hint(
                self._current_output_json(),
                self._current_display_json(),
            )
        )

    def _requested_mc_only(self) -> bool:
        if self.mc_only_var.get():
            return True
        total_overs_text = self.total_overs_var.get().strip()
        if not total_overs_text:
            return False
        try:
            return int(total_overs_text) < 20
        except ValueError:
            return False

    def _parse_optional_int(self, value: str, label: str, *, minimum: int, maximum: int | None = None) -> int | None:
        value = value.strip()
        if not value:
            return None
        try:
            parsed = int(value)
        except ValueError:
            messagebox.showerror("Invalid value", f"{label} must be a whole number.")
            return None
        if parsed < minimum or (maximum is not None and parsed > maximum):
            if maximum is None:
                messagebox.showerror("Invalid value", f"{label} must be at least {minimum}.")
            else:
                messagebox.showerror("Invalid value", f"{label} must be between {minimum} and {maximum}.")
            return None
        return parsed

    # --- Start / Stop ---
    def start(self):
        url = self.url_var.get().strip()
        if not url:
            return
        if self.proc and self.proc.poll() is None:
            return

        cfg = LEAGUE_CONFIGS[self.league_var.get()]
        total_overs = self._parse_optional_int(
            self.total_overs_var.get(),
            "Total overs",
            minimum=1,
            maximum=50,
        )
        if self.total_overs_var.get().strip() and total_overs is None:
            return
        revised_target = self._parse_optional_int(
            self.revised_target_var.get(),
            "Revised target",
            minimum=1,
        )
        if self.revised_target_var.get().strip() and revised_target is None:
            return

        mc_only = self._requested_mc_only()
        output_json = self._current_output_json()
        display_json = self._current_display_json()

        cmd = [
            _python_executable(), "-m", "src.bbl_pipeline.inference.crex_live_predictor",
            "--match-url", url,
            "--model-dir", cfg["model_dir"],
            "--feature-store-dir", cfg["feature_store_dir"],
            "--league", cfg["league"],
            "--output-json", output_json,
        ]
        odm_model_dir = cfg.get("odm_model_dir")
        if odm_model_dir and not mc_only:
            cmd += ["--odm-model-dir", odm_model_dir]
        if mc_only:
            cmd.append("--mc-only")
        if total_overs is not None:
            cmd += ["--total-overs", str(total_overs)]
        if revised_target is not None:
            cmd += ["--revised-target", str(revised_target)]
        if self.app.record_var.get():
            cmd += ["--record-states", "--states-dir", cfg["states_dir"]]

        tag = f"M{self.idx + 1}"
        self.app._log(f"[{tag}] Starting: {cfg['league'].upper()} → {url.split('/')[-1][:50]}")
        self.app._log(f"[{tag}] {format_output_json_hint(output_json)}")
        if display_json != output_json:
            self.app._log(f"[{tag}] ODM mirror: {Path(display_json)}")
        if mc_only or (total_overs is not None and total_overs < 20):
            mode_bits = ["MC-only"]
            if total_overs is not None:
                mode_bits.append(f"{total_overs} overs")
            if revised_target is not None:
                mode_bits.append(f"target {revised_target}")
            self.app._log(f"[{tag}] Mode: {' | '.join(mode_bits)}")
        try:
            self.proc = self.app._launch_process(cmd, tag)
            self.bridge_proc = None
            if display_json != output_json and odm_model_dir and not mc_only:
                self.bridge_proc = self._start_odm_bridge(
                    output_json=output_json,
                    display_json=display_json,
                    odm_model_dir=odm_model_dir,
                    cfg=cfg,
                    tag=tag,
                )
            self.status_var.set(f"running (PID {self.proc.pid})")
            self.status_label.configure(foreground="green")
            self.start_btn.configure(state="disabled")
            self.stop_btn.configure(state="normal")
            threading.Thread(
                target=self._watch, daemon=True,
            ).start()
            if self.bridge_proc:
                threading.Thread(
                    target=self._watch_bridge, daemon=True,
                ).start()
        except Exception as e:
            self.app._log(f"[{tag}] ERROR: {e}")

    def _start_odm_bridge(
        self,
        *,
        output_json: str,
        display_json: str,
        odm_model_dir: str,
        cfg: dict,
        tag: str,
    ) -> subprocess.Popen:
        bridge_tag = f"{tag}-ODM"
        bridge_cmd = [
            _python_executable(), "scripts/odm_live_json_bridge.py",
            "--input-json", output_json,
            "--output-json", display_json,
            "--feature-store-dir", cfg["feature_store_dir"],
            "--league", cfg["league"],
            "--odm-model-dir", odm_model_dir,
        ]
        self.app._log(f"[{bridge_tag}] Starting ODM bridge")
        return self.app._launch_process(bridge_cmd, bridge_tag)

    def stop(self):
        if self.proc and self.proc.poll() is None:
            self.app._log(f"[M{self.idx + 1}] Stopping...")
            self.app._kill_proc(self.proc)
            self.proc = None
        if self.bridge_proc and self.bridge_proc.poll() is None:
            self.app._log(f"[M{self.idx + 1}-ODM] Stopping...")
            self.app._kill_proc(self.bridge_proc)
            self.bridge_proc = None
        self._set_stopped()

    def _watch(self):
        if self.proc:
            self.proc.wait()
            code = self.proc.returncode
            bridge_proc = self.bridge_proc
            if bridge_proc and bridge_proc.poll() is None:
                self.app._kill_proc(bridge_proc)
                self.bridge_proc = None
            self.app.root.after(0, self.app._log,
                                f"[M{self.idx + 1}] Exited (code {code})")
            self.app.root.after(0, self._set_stopped)

    def _watch_bridge(self):
        if self.bridge_proc:
            self.bridge_proc.wait()
            code = self.bridge_proc.returncode
            self.bridge_proc = None
            self.app.root.after(0, self.app._log,
                                f"[M{self.idx + 1}-ODM] Exited (code {code})")

    def _set_stopped(self):
        self.status_var.set("idle")
        self.status_label.configure(foreground="gray")
        self.start_btn.configure(state="normal")
        self.stop_btn.configure(state="disabled")

    @property
    def is_running(self) -> bool:
        return self.proc is not None and self.proc.poll() is None

    def destroy(self):
        self.stop()
        self.frame.destroy()


class LauncherApp:
    """Main launcher window — supports multiple concurrent match predictors."""

    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("🏏 Cricket Live Predictor Launcher")
        self.root.geometry("1080x780")
        self.root.minsize(960, 680)

        self.streamlit_proc: subprocess.Popen | None = None
        self.match_slots: list[MatchSlot] = []

        self._build_ui()
        self._log(f"Project root: {PROJECT_ROOT}")
        self._log(f"Package source: {_detect_package_source()}")
        self._log("Ready. Paste CREX URLs, leagues auto-detect. Click ▶ or Start All.")

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------
    def _build_ui(self):
        pad = dict(padx=8, pady=4)

        # --- Matches frame ---
        matches_lf = ttk.LabelFrame(self.root, text="Matches (paste URLs — league auto-detects)", padding=8)
        matches_lf.pack(fill="x", **pad)

        # Header row
        hdr = ttk.Frame(matches_lf)
        hdr.pack(fill="x")
        ttk.Label(hdr, text="#", width=3).pack(side="left")
        ttk.Label(hdr, text="CREX URL", width=72).pack(side="left", padx=(2, 4))
        ttk.Label(hdr, text="League", width=16).pack(side="left", padx=2)
        ttk.Label(hdr, text="", width=8).pack(side="left")
        ttk.Label(hdr, text="Status", width=22).pack(side="left", padx=(4, 0))

        self._slots_frame = ttk.Frame(matches_lf)
        self._slots_frame.pack(fill="x")

        # Start with 2 slots
        for _ in range(2):
            self._add_slot()

        # Add / remove slot buttons
        slot_btns = ttk.Frame(matches_lf)
        slot_btns.pack(fill="x", pady=(4, 0))
        ttk.Button(slot_btns, text="+ Add Match Slot", command=self._add_slot).pack(side="left")
        ttk.Button(slot_btns, text="- Remove Last", command=self._remove_slot).pack(side="left", padx=4)

        # --- Options ---
        opt_frame = ttk.Frame(self.root)
        opt_frame.pack(fill="x", **pad)

        self.record_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(opt_frame, text="Record match states", variable=self.record_var).pack(side="left")

        self.separate_terminal_var = tk.BooleanVar(value=(sys.platform == "win32"))
        ttk.Checkbutton(
            opt_frame,
            text="Launch processes in separate terminal windows",
            variable=self.separate_terminal_var,
        ).pack(side="left", padx=(16, 0))

        # --- Global buttons ---
        btn_frame = ttk.Frame(self.root)
        btn_frame.pack(fill="x", **pad)

        ttk.Button(btn_frame, text="🚀 Start All Predictors", command=self._start_all_predictors).pack(side="left", padx=4)
        ttk.Button(btn_frame, text="🛑 Stop All Predictors", command=self._stop_all_predictors).pack(side="left", padx=4)

        ttk.Separator(btn_frame, orient="vertical").pack(side="left", fill="y", padx=8)

        self.start_st_btn = ttk.Button(btn_frame, text="▶  Start Streamlit", command=self._start_streamlit)
        self.start_st_btn.pack(side="left", padx=4)

        self.stop_st_btn = ttk.Button(btn_frame, text="⏹  Stop Streamlit", command=self._stop_streamlit, state="disabled")
        self.stop_st_btn.pack(side="left", padx=4)

        ttk.Separator(btn_frame, orient="vertical").pack(side="left", fill="y", padx=8)

        ttk.Button(btn_frame, text="🚀 Start Everything", command=self._start_everything).pack(side="left", padx=4)
        ttk.Button(btn_frame, text="🛑 Stop Everything", command=self._stop_everything).pack(side="left", padx=4)

        # --- Status bar ---
        status_frame = ttk.Frame(self.root)
        status_frame.pack(fill="x", **pad)
        self.st_status = tk.StringVar(value="Streamlit: stopped")
        ttk.Label(status_frame, textvariable=self.st_status, foreground="gray").pack(side="left")

        # --- Log output ---
        log_frame = ttk.LabelFrame(self.root, text="Log Output", padding=4)
        log_frame.pack(fill="both", expand=True, **pad)

        self.log_box = scrolledtext.ScrolledText(
            log_frame, height=16, font=("Consolas", 9), wrap="word",
            state="disabled", bg="#1e1e1e", fg="#d4d4d4",
            insertbackground="white",
        )
        self.log_box.pack(fill="both", expand=True)

        # Close handler
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    # ------------------------------------------------------------------
    # Match slot management
    # ------------------------------------------------------------------
    def _add_slot(self):
        if len(self.match_slots) >= MAX_MATCH_SLOTS:
            messagebox.showinfo("Limit", f"Maximum {MAX_MATCH_SLOTS} match slots.")
            return
        slot = MatchSlot(self._slots_frame, len(self.match_slots), self)
        self.match_slots.append(slot)

    def _remove_slot(self):
        if not self.match_slots:
            return
        slot = self.match_slots.pop()
        slot.destroy()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _log(self, msg: str):
        ts = datetime.now().strftime("%H:%M:%S")
        self.log_box.configure(state="normal")
        self.log_box.insert("end", f"[{ts}] {msg}\n")
        self.log_box.see("end")
        self.log_box.configure(state="disabled")

    def _stream_output(self, proc: subprocess.Popen, label: str):
        """Read stdout+stderr from proc and append to log box."""
        try:
            if proc.stdout is None:
                return
            for line in iter(proc.stdout.readline, ""):
                if not line:
                    break
                self.root.after(0, self._log, f"[{label}] {line.rstrip()}")
        except Exception:
            pass

    def _launch_process(self, cmd: list[str], label: str) -> subprocess.Popen:
        """Launch a child process either inline or in a separate terminal window."""
        kwargs = {
            "cwd": str(PROJECT_ROOT),
            "env": {**os.environ, "PYTHONIOENCODING": "utf-8"},
        }

        creationflags = 0
        if sys.platform == "win32":
            creationflags |= WINDOWS_PROCESS_GROUP
            if self.separate_terminal_var.get():
                creationflags |= WINDOWS_NEW_CONSOLE
        if creationflags:
            kwargs["creationflags"] = creationflags

        if self.separate_terminal_var.get() and sys.platform == "win32":
            proc = subprocess.Popen(cmd, **kwargs)
            self._log(f"[{label}] Opened in a separate terminal window.")
            return proc

        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            encoding="utf-8",
            errors="replace",
            **kwargs,
        )
        threading.Thread(
            target=self._stream_output,
            args=(proc, label),
            daemon=True,
        ).start()
        return proc

    # ------------------------------------------------------------------
    # Predictor controls (all slots)
    # ------------------------------------------------------------------
    def _start_all_predictors(self):
        started = 0
        for slot in self.match_slots:
            if slot.url_var.get().strip() and not slot.is_running:
                slot.start()
                started += 1
        if started == 0:
            messagebox.showinfo("Nothing to start", "No URLs entered or all already running.")

    def _stop_all_predictors(self):
        for slot in self.match_slots:
            slot.stop()

    # ------------------------------------------------------------------
    # Streamlit
    # ------------------------------------------------------------------
    def _start_streamlit(self):
        if self.streamlit_proc and self.streamlit_proc.poll() is None:
            messagebox.showinfo("Running", "Streamlit is already running.")
            return

        app_path = str(PROJECT_ROOT / "src" / "bbl_pipeline" / "app" / "live_streamlit_app.py")
        cmd = [_python_executable(), "-m", "streamlit", "run", app_path, "--server.port", "8501"]

        self._log("Starting Streamlit on http://localhost:8501")
        try:
            self.streamlit_proc = self._launch_process(cmd, "ST")
            self.st_status.set(f"Streamlit: running (PID {self.streamlit_proc.pid})")
            self.start_st_btn.configure(state="disabled")
            self.stop_st_btn.configure(state="normal")
            threading.Thread(target=self._watch_streamlit, daemon=True).start()
        except Exception as e:
            self._log(f"ERROR starting Streamlit: {e}")

    def _stop_streamlit(self):
        if self.streamlit_proc and self.streamlit_proc.poll() is None:
            self._log("Stopping Streamlit...")
            self._kill_proc(self.streamlit_proc)
            self.streamlit_proc = None
        self.st_status.set("Streamlit: stopped")
        self.start_st_btn.configure(state="normal")
        self.stop_st_btn.configure(state="disabled")

    def _watch_streamlit(self):
        if self.streamlit_proc:
            self.streamlit_proc.wait()
            self.root.after(0, self._log,
                            f"Streamlit exited (code {self.streamlit_proc.returncode})")
            self.root.after(0, lambda: self.st_status.set("Streamlit: stopped"))
            self.root.after(0, lambda: self.start_st_btn.configure(state="normal"))
            self.root.after(0, lambda: self.stop_st_btn.configure(state="disabled"))

    # ------------------------------------------------------------------
    # Start / Stop everything
    # ------------------------------------------------------------------
    def _start_everything(self):
        self._start_all_predictors()
        self._start_streamlit()

    def _stop_everything(self):
        self._stop_all_predictors()
        self._stop_streamlit()

    # ------------------------------------------------------------------
    # Process helpers
    # ------------------------------------------------------------------
    def _kill_proc(self, proc: subprocess.Popen):
        """Terminate a subprocess tree."""
        try:
            if sys.platform == "win32":
                subprocess.call(
                    ["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                )
            else:
                os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass

    def _on_close(self):
        self._stop_everything()
        self.root.destroy()


def main():
    root = tk.Tk()
    LauncherApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
