"""
Cricket Live Predictor Launcher — Desktop GUI
==============================================
Tkinter app to start/stop the CREX live predictor and Streamlit dashboard.

Usage:
    python scripts/launcher.py
"""

import os
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

# ---------------------------------------------------------------------------
# League presets — model_dir, feature_store_dir, output_json, states_dir
# ---------------------------------------------------------------------------
LEAGUE_CONFIGS = {
    "IPL": {
        "league": "ipl",
        "model_dir": "models/t20_male_v2",
        "feature_store_dir": "data/bbl_feature_store_v2",
        "output_json": "data/ipl_live_ml.json",
        "states_dir": "data/match_states/ipl",
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
        "model_dir": "models/t20_male_v2",
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


def _detect_package_source() -> str:
    """Return the filesystem path the bbl_pipeline package is loaded from."""
    try:
        import bbl_pipeline
        return str(Path(bbl_pipeline.__file__).resolve().parent.parent)
    except ImportError:
        return "(not installed)"


class LauncherApp:
    """Main launcher window."""

    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("🏏 Cricket Live Predictor Launcher")
        self.root.geometry("820x700")
        self.root.minsize(700, 600)

        self.predictor_proc: subprocess.Popen | None = None
        self.streamlit_proc: subprocess.Popen | None = None
        self._log_threads: list[threading.Thread] = []

        self._build_ui()
        self._log(f"Project root: {PROJECT_ROOT}")
        self._log(f"Package source: {_detect_package_source()}")
        self._log("Ready. Paste a CREX URL and click Start.")

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------
    def _build_ui(self):
        pad = dict(padx=8, pady=4)

        # --- Top frame: URL + league ---
        top = ttk.LabelFrame(self.root, text="Match Configuration", padding=10)
        top.pack(fill="x", **pad)

        ttk.Label(top, text="CREX URL:").grid(row=0, column=0, sticky="w")
        self.url_var = tk.StringVar()
        url_entry = ttk.Entry(top, textvariable=self.url_var, width=80)
        url_entry.grid(row=0, column=1, columnspan=3, sticky="ew", padx=(4, 0))

        ttk.Label(top, text="League:").grid(row=1, column=0, sticky="w", pady=(6, 0))
        self.league_var = tk.StringVar(value="IPL")
        league_combo = ttk.Combobox(
            top, textvariable=self.league_var,
            values=list(LEAGUE_CONFIGS.keys()), state="readonly", width=20,
        )
        league_combo.grid(row=1, column=1, sticky="w", padx=(4, 0), pady=(6, 0))
        league_combo.bind("<<ComboboxSelected>>", self._on_league_change)

        self.record_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(top, text="Record match states", variable=self.record_var).grid(
            row=1, column=2, sticky="w", padx=(16, 0), pady=(6, 0),
        )

        top.columnconfigure(1, weight=1)

        # --- Config display ---
        cfg_frame = ttk.LabelFrame(self.root, text="Resolved Configuration", padding=8)
        cfg_frame.pack(fill="x", **pad)

        self.cfg_text = tk.StringVar()
        self._update_config_display()
        ttk.Label(cfg_frame, textvariable=self.cfg_text, font=("Consolas", 9), justify="left").pack(
            anchor="w",
        )

        # --- Buttons ---
        btn_frame = ttk.Frame(self.root)
        btn_frame.pack(fill="x", **pad)

        self.start_pred_btn = ttk.Button(btn_frame, text="▶  Start Predictor", command=self._start_predictor)
        self.start_pred_btn.pack(side="left", padx=4)

        self.stop_pred_btn = ttk.Button(btn_frame, text="⏹  Stop Predictor", command=self._stop_predictor, state="disabled")
        self.stop_pred_btn.pack(side="left", padx=4)

        ttk.Separator(btn_frame, orient="vertical").pack(side="left", fill="y", padx=8)

        self.start_st_btn = ttk.Button(btn_frame, text="▶  Start Streamlit", command=self._start_streamlit)
        self.start_st_btn.pack(side="left", padx=4)

        self.stop_st_btn = ttk.Button(btn_frame, text="⏹  Stop Streamlit", command=self._stop_streamlit, state="disabled")
        self.stop_st_btn.pack(side="left", padx=4)

        ttk.Separator(btn_frame, orient="vertical").pack(side="left", fill="y", padx=8)

        ttk.Button(btn_frame, text="🚀 Start All", command=self._start_all).pack(side="left", padx=4)
        ttk.Button(btn_frame, text="🛑 Stop All", command=self._stop_all).pack(side="left", padx=4)

        # --- Status bar ---
        status_frame = ttk.Frame(self.root)
        status_frame.pack(fill="x", **pad)

        self.pred_status = tk.StringVar(value="Predictor: stopped")
        self.st_status = tk.StringVar(value="Streamlit: stopped")

        ttk.Label(status_frame, textvariable=self.pred_status, foreground="gray").pack(side="left", padx=(0, 20))
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
    # Helpers
    # ------------------------------------------------------------------
    def _get_config(self) -> dict:
        return LEAGUE_CONFIGS[self.league_var.get()]

    def _update_config_display(self):
        cfg = self._get_config()
        lines = (
            f"league: {cfg['league']}    model: {cfg['model_dir']}    "
            f"feature_store: {cfg['feature_store_dir']}\n"
            f"output_json: {cfg['output_json']}    states_dir: {cfg['states_dir']}"
        )
        self.cfg_text.set(lines)

    def _on_league_change(self, _event=None):
        self._update_config_display()

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
    # Predictor
    # ------------------------------------------------------------------
    def _start_predictor(self):
        url = self.url_var.get().strip()
        if not url:
            messagebox.showwarning("No URL", "Please enter a CREX match URL.")
            return
        if self.predictor_proc and self.predictor_proc.poll() is None:
            messagebox.showinfo("Running", "Predictor is already running.")
            return

        cfg = self._get_config()
        cmd = [
            sys.executable, "-m", "src.bbl_pipeline.inference.crex_live_predictor",
            "--match-url", url,
            "--model-dir", cfg["model_dir"],
            "--feature-store-dir", cfg["feature_store_dir"],
            "--league", cfg["league"],
            "--output-json", cfg["output_json"],
        ]
        if self.record_var.get():
            cmd += ["--record-states", "--states-dir", cfg["states_dir"]]

        self._log(f"Starting predictor: {' '.join(cmd[-6:])}")
        try:
            self.predictor_proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, bufsize=1,
                cwd=str(PROJECT_ROOT),
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if sys.platform == "win32" else 0,
            )
            self.pred_status.set(f"Predictor: running (PID {self.predictor_proc.pid})")
            self.start_pred_btn.configure(state="disabled")
            self.stop_pred_btn.configure(state="normal")

            t = threading.Thread(target=self._stream_output, args=(self.predictor_proc, "PRED"), daemon=True)
            t.start()
            self._log_threads.append(t)

            # Monitor for exit
            threading.Thread(target=self._watch_proc, args=(self.predictor_proc, "Predictor"), daemon=True).start()
        except Exception as e:
            self._log(f"ERROR starting predictor: {e}")

    def _stop_predictor(self):
        if self.predictor_proc and self.predictor_proc.poll() is None:
            self._log("Stopping predictor...")
            self._kill_proc(self.predictor_proc)
            self.predictor_proc = None
        self.pred_status.set("Predictor: stopped")
        self.start_pred_btn.configure(state="normal")
        self.stop_pred_btn.configure(state="disabled")

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
                text=True, bufsize=1,
                cwd=str(PROJECT_ROOT),
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if sys.platform == "win32" else 0,
            )
            self.st_status.set(f"Streamlit: running (PID {self.streamlit_proc.pid})")
            self.start_st_btn.configure(state="disabled")
            self.stop_st_btn.configure(state="normal")

            t = threading.Thread(target=self._stream_output, args=(self.streamlit_proc, "ST"), daemon=True)
            t.start()
            self._log_threads.append(t)

            threading.Thread(target=self._watch_proc, args=(self.streamlit_proc, "Streamlit"), daemon=True).start()
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

    # ------------------------------------------------------------------
    # Start / Stop all
    # ------------------------------------------------------------------
    def _start_all(self):
        self._start_predictor()
        self._start_streamlit()

    def _stop_all(self):
        self._stop_predictor()
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

    def _watch_proc(self, proc: subprocess.Popen, label: str):
        """Wait for proc to exit and update UI."""
        proc.wait()
        self.root.after(0, self._log, f"{label} exited (code {proc.returncode})")
        if label == "Predictor":
            self.root.after(0, lambda: self.pred_status.set("Predictor: stopped"))
            self.root.after(0, lambda: self.start_pred_btn.configure(state="normal"))
            self.root.after(0, lambda: self.stop_pred_btn.configure(state="disabled"))
        elif label == "Streamlit":
            self.root.after(0, lambda: self.st_status.set("Streamlit: stopped"))
            self.root.after(0, lambda: self.start_st_btn.configure(state="normal"))
            self.root.after(0, lambda: self.stop_st_btn.configure(state="disabled"))

    def _on_close(self):
        self._stop_all()
        self.root.destroy()


def main():
    root = tk.Tk()
    LauncherApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
