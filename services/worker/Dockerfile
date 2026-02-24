FROM python:3.11-slim

WORKDIR /workspace

COPY shared/python /workspace/shared/python
COPY services/worker /workspace/service

RUN pip install --no-cache-dir -r /workspace/service/requirements.txt \
    && pip install --no-cache-dir -e /workspace/shared/python

WORKDIR /workspace/service
CMD ["celery", "-A", "app.worker.celery_app", "worker", "--loglevel=info", "--pool=solo"]
