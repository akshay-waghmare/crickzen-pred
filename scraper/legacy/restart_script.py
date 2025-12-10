import os
import sys
import time
import signal
import subprocess

def restart_application():
    # Get the current script's path
    current_script = os.path.abspath(sys.argv[0])
    
    # Restart the script after a short delay
    time.sleep(2)  # Add a small delay before restarting

    # Kill the existing process and restart the application
    os.execv(sys.executable, [sys.executable] + [current_script])

if __name__ == "__main__":
    restart_application()
