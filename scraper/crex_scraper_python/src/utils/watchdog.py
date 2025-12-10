"""
Watchdog for Orphan Process Cleanup.
"""

import logging
import psutil
import time
import os
import signal

logger = logging.getLogger(__name__)

class ProcessWatchdog:
    """
    Monitors and cleans up orphan browser processes.
    """

    def __init__(self, target_names=("chrome", "chromium", "playwright")):
        self.target_names = target_names
        self.my_pid = os.getpid()

    def cleanup_orphans(self):
        """
        Kill processes that are not children of the current process
        but belong to the target names (if running in a container where we own the namespace).
        """
        try:
            current_process = psutil.Process(self.my_pid)
            children = current_process.children(recursive=True)
            child_pids = {p.pid for p in children}
            
            for proc in psutil.process_iter(['pid', 'name', 'ppid']):
                try:
                    if proc.info['pid'] == self.my_pid:
                        continue
                        
                    if any(name in proc.info['name'].lower() for name in self.target_names):
                        # If it's not my child, and I'm the main process (PID 1) or similar, kill it.
                        # In a container, we might want to be aggressive.
                        if proc.info['pid'] not in child_pids:
                            logger.warning(f"Found orphan process {proc.info['pid']} ({proc.info['name']}). Killing...")
                            proc.kill()
                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                    pass
                    
        except Exception as e:
            logger.error(f"Error during orphan cleanup: {e}")
