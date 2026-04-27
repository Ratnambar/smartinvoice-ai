import os
import sys

from celery import Celery

_redis = os.environ.get("CELERY_BROKER_URL") or os.environ.get("REDIS_URL", "redis://localhost:6379/0")
_result = os.environ.get("CELERY_RESULT_BACKEND", _redis)

celery_app = Celery(
    "smartinvoice",
    broker=_redis,
    backend=_result,
)

celery_app.conf.update(
    task_serializer = "json",
    result_serializer = "json",
    accept_content = ["json"],
    timezone = "Asia/Kolkata",
    task_track_started = True,
)

# Prefork/billiard uses multiprocessing semaphores that often fail on Windows
# (PermissionError on semlock). Use solo (in-process) or threads instead.
if sys.platform == "win32":
    celery_app.conf.worker_pool = "solo"

# Import for side effects: registers @task objects on this app. Without this, the worker
# never loads task modules and raises KeyError for the task name (see Celery protocol docs).
import app.workers.tasks  # noqa: F401