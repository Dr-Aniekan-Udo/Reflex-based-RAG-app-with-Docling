"""
Celery application configuration with Redis broker.
"""
import os
from celery import Celery

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

celery_app = Celery(
    "rag_app",
    broker=REDIS_URL,
    backend=REDIS_URL,
    include=["RAG_app.core.celery_tasks"],
)

celery_app.conf.update(
    # Task serialization
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",

    # Timezone
    timezone="UTC",
    enable_utc=True,

    # Task execution
    task_track_started=True,
    task_time_limit=600,          # Hard limit: 10 minutes
    task_soft_time_limit=480,     # Soft limit: 8 minutes (warning before kill)

    # Worker behavior
    worker_prefetch_multiplier=1,  # Only fetch 1 task at a time
    worker_max_tasks_per_child=1,  # Restart worker process after each task (memory leak prevention)

    # Rate limiting
    task_default_rate_limit="2/m",  # Max 2 tasks per minute globally

    # Retries
    task_default_retry_delay=30,
    task_max_retries=3,

    # Result backend
    result_backend=REDIS_URL,
    result_expires=3600,           # Results expire after 1 hour
    result_extended=True,

    # Broker connection
    broker_connection_retry_on_startup=True,
    broker_connection_max_retries=10,
    broker_connection_timeout=30,

    # Visibility timeout (must exceed longest task time)
    broker_transport_options={
        "visibility_timeout": 7200,  # 2 hours
    },
)
