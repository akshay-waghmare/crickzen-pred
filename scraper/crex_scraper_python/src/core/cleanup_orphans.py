"""Orphaned Chromium process cleanup for scraper resilience.

Scans for orphaned browser processes and terminates them to prevent
resource leaks from crashed or improperly terminated scrapers.
"""

import threading
import time
from typing import List, Optional

try:
    import psutil
except ImportError:
    psutil = None  # type: ignore

from ..loggers.adapters import get_logger
from ..config import get_settings

logger = get_logger(component="orphan_cleanup")

_cleanup_thread: Optional[threading.Thread] = None
_cleanup_stop_event = threading.Event()


def find_orphaned_chromium_processes() -> List[int]:
    """Find orphaned Chromium/Playwright browser processes.
    
    Returns list of PIDs for processes that appear to be orphaned
    (no parent process or parent is not Python).
    """
    if psutil is None:
        logger.warning("cleanup.psutil_unavailable")
        return []
    
    orphaned_pids = []
    
    try:
        for proc in psutil.process_iter(['pid', 'name', 'ppid', 'create_time']):
            try:
                name = proc.info['name'].lower()
                
                # Check if it's a Chromium/browser process
                if not any(browser in name for browser in ['chromium', 'chrome', 'playwright']):
                    continue
                
                # Check if parent exists and is Python
                try:
                    parent = psutil.Process(proc.info['ppid'])
                    parent_name = parent.name().lower()
                    
                    # If parent is not Python, likely orphaned
                    if 'python' not in parent_name:
                        orphaned_pids.append(proc.info['pid'])
                        logger.info(
                            "cleanup.orphan_detected",
                            metadata={
                                "pid": proc.info['pid'],
                                "name": proc.info['name'],
                                "ppid": proc.info['ppid'],
                                "parent_name": parent_name,
                            }
                        )
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    # Parent doesn't exist - definitely orphaned
                    orphaned_pids.append(proc.info['pid'])
                    logger.info(
                        "cleanup.orphan_no_parent",
                        metadata={"pid": proc.info['pid'], "name": proc.info['name']}
                    )
                    
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
                
    except Exception as e:
        logger.error("cleanup.scan_error", metadata={"error": str(e)})
    
    return orphaned_pids


def terminate_processes(pids: List[int]) -> int:
    """Terminate processes by PID list.
    
    Returns count of successfully terminated processes.
    """
    if psutil is None or not pids:
        return 0
    
    terminated_count = 0
    
    for pid in pids:
        try:
            proc = psutil.Process(pid)
            proc.terminate()
            
            # Wait up to 5 seconds for graceful termination
            try:
                proc.wait(timeout=5)
            except psutil.TimeoutExpired:
                # Force kill if still alive
                proc.kill()
                proc.wait(timeout=2)
            
            terminated_count += 1
            logger.info("cleanup.terminated", metadata={"pid": pid})
            
        except psutil.NoSuchProcess:
            logger.debug("cleanup.already_dead", metadata={"pid": pid})
            terminated_count += 1
        except psutil.AccessDenied:
            logger.warning("cleanup.access_denied", metadata={"pid": pid})
        except Exception as e:
            logger.error("cleanup.terminate_error", metadata={"pid": pid, "error": str(e)})
    
    return terminated_count


def cleanup_orphans_once() -> int:
    """Run one cleanup cycle. Returns count of terminated processes."""
    logger.info("cleanup.scan_start")
    
    orphaned_pids = find_orphaned_chromium_processes()
    
    if not orphaned_pids:
        logger.info("cleanup.scan_complete", metadata={"orphans_found": 0})
        return 0
    
    logger.info("cleanup.orphans_found", metadata={"count": len(orphaned_pids), "pids": orphaned_pids})
    
    terminated = terminate_processes(orphaned_pids)
    
    logger.info(
        "cleanup.scan_complete",
        metadata={"orphans_found": len(orphaned_pids), "terminated": terminated}
    )
    
    return terminated


def _cleanup_loop(interval_seconds: int) -> None:
    """Background loop that runs cleanup periodically."""
    logger.info("cleanup.loop_started", metadata={"interval_seconds": interval_seconds})
    
    while not _cleanup_stop_event.is_set():
        try:
            cleanup_orphans_once()
        except Exception as e:
            logger.error("cleanup.loop_error", metadata={"error": str(e)})
        
        # Sleep in small chunks so we can respond to stop event quickly
        for _ in range(interval_seconds):
            if _cleanup_stop_event.is_set():
                break
            time.sleep(1)
    
    logger.info("cleanup.loop_stopped")


def start_cleanup_thread(interval_seconds: Optional[int] = None) -> None:
    """Start background cleanup thread.
    
    Args:
        interval_seconds: Cleanup interval. Defaults to config setting (30m standard, 60m tiny).
    """
    global _cleanup_thread
    
    if _cleanup_thread and _cleanup_thread.is_alive():
        logger.warning("cleanup.already_running")
        return
    
    if interval_seconds is None:
        settings = get_settings()
        interval_seconds = settings.orphan_cleanup_interval_seconds
    
    _cleanup_stop_event.clear()
    _cleanup_thread = threading.Thread(
        target=_cleanup_loop,
        args=(interval_seconds,),
        daemon=True,
        name="OrphanCleanup"
    )
    _cleanup_thread.start()
    logger.info("cleanup.thread_started", metadata={"interval_seconds": interval_seconds})


def stop_cleanup_thread(timeout: float = 5.0) -> None:
    """Stop background cleanup thread."""
    global _cleanup_thread
    
    if not _cleanup_thread or not _cleanup_thread.is_alive():
        return
    
    logger.info("cleanup.stopping")
    _cleanup_stop_event.set()
    _cleanup_thread.join(timeout=timeout)
    _cleanup_thread = None
    logger.info("cleanup.stopped")


__all__ = [
    "cleanup_orphans_once",
    "find_orphaned_chromium_processes",
    "start_cleanup_thread",
    "stop_cleanup_thread",
    "terminate_processes",
]
