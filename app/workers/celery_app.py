import sys

from celery import Celery

celery_app = Celery(
    "smartinvoice",
    broker= "redis://localhost:6379/0",
    backend= "redis://localhost:6379/0"
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