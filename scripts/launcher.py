"""
Cricket Live Predictor Launcher — Desktop GUI
==============================================
Tkinter app to start/stop multiple concurrent CREX live predictors and
the Streamlit dashboard.  Supports auto-detecting the league from CREX
URLs, and running up to 6 match slots simultaneously.

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

# ---------------------------------------------------------------------------
# League presets — model_dir, feature_store_dir, output_json, states_dir
# ---------------------------------------------------------------------------
LEAGUE_CONFIGS = {
    "IPL": {
        "league": "ipl",
        "model_dir": "models/t20_male_v2",
        "feature_store_dir": "data/ipl_feature_store_v1",
        "output_json": "data/ipl_live_ml.json",
        "states_dir": "data/match_states/ipl",
    },
    "PSL": {
        "league": "psl",
        "model_dir": "models/t20_male_v2",
        "feature_store_dir": "data/psl_feature_store_v1",
        "output_json": "data/psl_live_ml.json",
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


class MatchSlot:
    """One row in the matches panel: URL entry + league combo + start/stop."""

    def __init__(self, parent: ttk.Frame, idx: int, app: "LauncherApp"):
        self.app = app
        self.idx = idx
        self.proc: subprocess.Popen | None = None

        self.frame = ttk.Frame(parent)
        self.frame.pack(fill="x", pady=2)

        # Slot label
        ttk.Label(self.frame, text=f"#{idx + 1}", width=3).pack(side="left")

        # URL entry
        self.url_var = tk.StringVar()
        self.url_var.trace_add("write", self._on_url_change)
        self.url_entry = ttk.Entry(self.frame, textvariable=self.url_var, width=72)
        self.url_entry.pack(side="left", padx=(2, 4))

        # League dropdown
        self.league_var = tk.StringVar(value="IPL")
        self.league_combo = ttk.Combobox(
            self.frame, textvariable=self.league_var,
            values=list(LEAGUE_CONFIGS.keys()), state="readonly", width=16,
        )
        self.league_combo.pack(side="left", padx=2)

        # Start / Stop
        self.start_btn = ttk.Button(self.frame, text="▶", width=3, command=self.start)
        self.start_btn.pack(side="left", padx=2)
        self.stop_btn = ttk.Button(self.frame, text="⏹", width=3, command=self.stop, state="disabled")
        self.stop_btn.pack(side="left", padx=2)

        # Status indicator
        self.status_var = tk.StringVar(value="idle")
        self.status_label = ttk.Label(self.frame, textvariable=self.status_var,
                                      foreground="gray", width=22)
        self.status_label.pack(side="left", padx=(4, 0))

    # --- Auto-detect league when URL changes ---
    def _on_url_change(self, *_args):
        url = self.url_var.get().strip()
        if url:
            detected = detect_league_from_url(url)
            if detected:
                self.league_var.set(detected)

    # --- Start / Stop ---
    def start(self):
        url = self.url_var.get().strip()
        if not url:
            return
        if self.proc and self.proc.poll() is None:
            return

        cfg = LEAGUE_CONFIGS[self.league_var.get()]

        # Per-slot output file: append slot index when multiple matches use same league
        output_json = cfg["output_json"].replace(".json", f"_{self.idx + 1}.json")

        cmd = [
            sys.executable, "-m", "src.bbl_pipeline.inference.crex_live_predictor",
            "--match-url", url,
            "--model-dir", cfg["model_dir"],
            "--feature-store-dir", cfg["feature_store_dir"],
            "--league", cfg["league"],
            "--output-json", output_json,
        ]
        if self.app.record_var.get():
            cmd += ["--record-states", "--states-dir", cfg["states_dir"]]

        tag = f"M{self.idx + 1}"
        self.app._log(f"[{tag}] Starting: {cfg['league'].upper()} → {url.split('/')[-1][:50]}")
        try:
            self.proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, bufsize=1, encoding="utf-8", errors="replace",
                cwd=str(PROJECT_ROOT),
                env={**os.environ, "PYTHONIOENCODING": "utf-8"},
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if sys.platform == "win32" else 0,
            )
            self.status_var.set(f"running (PID {self.proc.pid})")
            self.status_label.configure(foreground="green")
            self.start_btn.configure(state="disabled")
            self.stop_btn.configure(state="normal")

            threading.Thread(
                target=self.app._stream_output, args=(self.proc, tag), daemon=True,
            ).start()
            threading.Thread(
                target=self._watch, daemon=True,
            ).start()
        except Exception as e:
            self.app._log(f"[{tag}] ERROR: {e}")

    def stop(self):
        if self.proc and self.proc.poll() is None:
            self.app._log(f"[M{self.idx + 1}] Stopping...")
            self.app._kill_proc(self.proc)
            self.proc = None
        self._set_stopped()

    def _watch(self):
        if self.proc:
            self.proc.wait()
            code = self.proc.returncode
            self.app.root.after(0, self.app._log,
                                f"[M{self.idx + 1}] Exited (code {code})")
            self.app.root.after(0, self._set_stopped)

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
        self.root.geometry("1000x750")
        self.root.minsize(900, 650)

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
            for line in iter(proc.stdout.readline, ""):
                if not line:
                    break
                self.root.after(0, self._log, f"[{label}] {line.rstrip()}")
        except Exception:
            pass

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
        cmd = [sys.executable, "-m", "streamlit", "run", app_path, "--server.port", "8501"]

        self._log("Starting Streamlit on http://localhost:8501")
        try:
            self.streamlit_proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, bufsize=1, encoding="utf-8", errors="replace",
                cwd=str(PROJECT_ROOT),
                env={**os.environ, "PYTHONIOENCODING": "utf-8"},
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if sys.platform == "win32" else 0,
            )
            self.st_status.set(f"Streamlit: running (PID {self.streamlit_proc.pid})")
            self.start_st_btn.configure(state="disabled")
            self.stop_st_btn.configure(state="normal")

            threading.Thread(
                target=self._stream_output, args=(self.streamlit_proc, "ST"), daemon=True,
            ).start()
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
