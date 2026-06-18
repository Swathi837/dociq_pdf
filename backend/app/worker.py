import os
from celery import Celery
from celery.schedules import crontab

REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")

celery_app = Celery(
    "dociq",
    broker=REDIS_URL,
    backend=REDIS_URL,
    include=[
        "app.tasks.process_document",
        "app.tasks.alert_scheduler",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    worker_prefetch_multiplier=1,
    task_acks_late=True,
    # Beat schedule — runs daily at 9am UTC
    beat_schedule={
        "check-deadlines-daily": {
            "task": "check_deadlines",
            "schedule": crontab(hour=9, minute=0),
        },
    },
)