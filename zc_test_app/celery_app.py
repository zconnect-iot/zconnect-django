from celery import Celery
app = Celery('zc_test_app')
app.config_from_object('django.conf:settings', namespace="CELERY")
