import os
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from loguru import logger

# Add parent directory to path to access models and config
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Configure logger
logger.add(
    os.path.join(os.path.dirname(__file__), '..', 'logs', 'cache_cleanup.log'),
    rotation="500 MB",
    retention="7 days"
)

CACHE_DIR = os.path.join(os.path.dirname(__file__), '..', 'cache')
MAX_AGE_HOURS = 24  # Delete files older than 24 hours (1 day)


def clean_cache(max_age_hours=MAX_AGE_HOURS):
    """
    Remove cache files older than max_age_hours.
    
    Args:
        max_age_hours (int): Maximum age of cache files in hours
    """
    if not os.path.exists(CACHE_DIR):
        logger.warning(f"Cache directory does not exist: {CACHE_DIR}")
        return
    
    current_time = time.time()
    max_age_seconds = max_age_hours * 3600
    deleted_count = 0
    error_count = 0
    total_size_freed = 0
    
    logger.info(f"Starting cache cleanup. Max age: {max_age_hours} hours")
    logger.info(f"Cache directory: {CACHE_DIR}")
    
    try:
        for filename in os.listdir(CACHE_DIR):
            file_path = os.path.join(CACHE_DIR, filename)
            
            # Skip directories
            if os.path.isdir(file_path):
                continue
            
            try:
                file_age_seconds = current_time - os.path.getmtime(file_path)
                
                if file_age_seconds > max_age_seconds:
                    file_size = os.path.getsize(file_path)
                    os.remove(file_path)
                    deleted_count += 1
                    total_size_freed += file_size
                    
                    age_days = file_age_seconds / 86400
                    logger.debug(f"Deleted: {filename} (Age: {age_days:.2f} days, Size: {file_size} bytes)")
            
            except Exception as e:
                error_count += 1
                logger.error(f"Error processing file {filename}: {e}")
        
        # Convert bytes to MB for logging
        size_mb = total_size_freed / (1024 * 1024)
        logger.info(
            f"Cache cleanup completed. "
            f"Deleted: {deleted_count} files, "
            f"Freed: {size_mb:.2f} MB, "
            f"Errors: {error_count}"
        )
        
        return {
            'deleted_count': deleted_count,
            'total_size_freed': total_size_freed,
            'error_count': error_count,
            'size_mb': size_mb
        }
    
    except Exception as e:
        logger.error(f"Fatal error during cache cleanup: {e}")
        raise


if __name__ == '__main__':
    result = clean_cache()
    print(f"\nCache cleanup result:")
    print(f"  Files deleted: {result['deleted_count']}")
    print(f"  Space freed: {result['size_mb']:.2f} MB")
    print(f"  Errors: {result['error_count']}")
