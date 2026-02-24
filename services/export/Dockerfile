FROM python:3.11-slim

WORKDIR /workspace

COPY shared/python /workspace/shared/python
COPY services/export /workspace/service

RUN pip install --no-cache-dir -r /workspace/service/requirements.txt \
    && pip install --no-cache-dir -e /workspace/shared/python

WORKDIR /workspace/service
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
