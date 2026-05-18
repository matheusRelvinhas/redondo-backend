import os
import sys
from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler
from loguru import logger

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from script.clean_cache import clean_cache


class CacheCleanupScheduler:
    _scheduler = None
    _is_running = False
    @classmethod
    def start(cls, interval_hours=6):
        if cls._is_running:
            logger.warning("Cache cleanup scheduler is already running")
            return
        try:
            cls._scheduler = BackgroundScheduler(daemon=True)
            cls._scheduler.add_job(
                func=cls._cleanup_task,
                trigger="interval",
                hours=interval_hours,
                id="cache_cleanup",
                name="Cache Cleanup Task",
                replace_existing=True,
                max_instances=1
            )
            cls._scheduler.start()
            cls._is_running = True
            logger.info(f"Cache cleanup scheduler started. Interval: {interval_hours} hours")
            
        except Exception as e:
            logger.error(f"Failed to start cache cleanup scheduler: {e}")
    
    @classmethod
    def stop(cls):
        if cls._scheduler and cls._is_running:
            cls._scheduler.shutdown()
            cls._is_running = False
            logger.info("Cache cleanup scheduler stopped")
            
    @classmethod
    def _cleanup_task(cls):
        """Internal method to execute the cleanup task."""
        try:
            logger.info(f"[{datetime.now()}] Starting scheduled cache cleanup")
            result = clean_cache()
            logger.info(
                f"Scheduled cleanup completed: "
                f"Deleted {result['deleted_count']} files, "
                f"Freed {result['size_mb']:.2f} MB"
            )
        except Exception as e:
            logger.error(f"Scheduled cache cleanup failed: {e}")


def init_cache_cleanup_scheduler(app, interval_hours=6):
    CacheCleanupScheduler.start(interval_hours=interval_hours)
    
    def shutdown_scheduler():
        CacheCleanupScheduler.stop()
    
    app.teardown_appcontext(lambda exc=None: shutdown_scheduler())
