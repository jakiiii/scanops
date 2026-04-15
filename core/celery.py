from __future__ import absolute_import, unicode_literals
import os
from celery import Celery

app = Celery('core')

# Use the full path to the settings module
app.config_from_object('core.settings', namespace='CELERY')

# This will auto-discover tasks from all installed Django apps
app.autodiscover_tasks()


if __name__ == '__main__':
    app.start()
