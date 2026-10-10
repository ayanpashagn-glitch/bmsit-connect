"""Scheduled expired-auth cleanup and failed object deletion retries."""
import subprocess
import sys
import time
import logging

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    while True:
        result = subprocess.run([sys.executable, '-m', 'app.storage_maintenance', 'cleanup'])
        if result.returncode:
            logging.error('Maintenance failed; inspect service health and retry queue')
        time.sleep(3600)
