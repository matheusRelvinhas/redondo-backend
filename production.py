import os
import multiprocessing
import subprocess
from dotenv import load_dotenv
from loguru import logger

load_dotenv()

def get_optimal_workers():
    cpu_cores = multiprocessing.cpu_count()
    optimal_workers = (2 * cpu_cores) + 1
    return optimal_workers

if __name__ == '__main__':
    os.environ['ENVIRONMENT'] = 'production'
    
    port = int(os.getenv('FLASK_RUN_PORT', 3001))
    workers = int(os.getenv('GUNICORN_WORKERS', get_optimal_workers()))
    
    gunicorn_cmd = [
        'gunicorn',
        '-w', str(workers),
        '-b', f'0.0.0.0:{port}',
        '--worker-class', 'sync',
        '--max-requests', '1000',
        '--max-requests-jitter', '50',
        '--timeout', '120',
        '--access-logfile', '-',
        '--error-logfile', '-',
        '--log-level', 'info',
        'wsgi:app'
    ]
    
    try:
        subprocess.run(gunicorn_cmd, check=True)
    except FileNotFoundError:
        logger.error("Error: gunicorn not installed.")
    except KeyboardInterrupt:
        logger.info("\n⛔ Server stopped by user.")
