"""
Celery configuration and initialization for AnyLingo.
Handles asynchronous task processing for media files and YouTube videos.
"""

from celery import Celery
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Create Celery instance
celery = Celery(
    'anylingo',
    broker=os.getenv('REDIS_URL', 'redis://localhost:6379/0'),
    backend=os.getenv('REDIS_URL', 'redis://localhost:6379/0')
)

# Configuration
celery.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    task_track_started=True,
    task_time_limit=7200,  # 2 hours max per task
    task_soft_time_limit=6900,  # Soft limit at 115 minutes
    worker_prefetch_multiplier=1,  # Process one task at a time
    worker_max_tasks_per_child=1,  # Restart worker after EACH task (critical for memory management)
    result_expires=86400,  # Results expire after 24 hours
    task_ignore_result=False,
    task_store_eager_result=True,
)

# Import tasks directly (not using autodiscovery for now)
import tasks.media_tasks