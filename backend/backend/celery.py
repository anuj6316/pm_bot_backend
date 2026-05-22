import os
from celery import Celery

# Tell Celery which Django settings module to use
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "backend.settings")

app = Celery("backend")

# Load all Celery configuration from Django settings
# namespace='CELERY' means Celery only reads settings that start with CELERY_
# This keeps Django settings and Celery settings cleanly separated
app.config_from_object("django.conf:settings", namespace="CELERY")

app.autodiscover_tasks([])
