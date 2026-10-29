FROM python:3.12-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt python-multipart

COPY visionflow ./visionflow

ENV VF_DATABASE_URL=postgresql://visionflow:visionflow@db:5432/visionflow \
    VF_CV_BACKEND=local \
    VF_DATA_DIR=/app/data

EXPOSE 8000
# Entrypoint: wait for the DB, create the schema, then serve. Honour $PORT so
# platforms like Render/Railway (which assign a port) work unchanged.
CMD bash -c "\
  until python -c 'import psycopg,os; psycopg.connect(os.environ[\"VF_DATABASE_URL\"]).close()' 2>/dev/null; do \
    echo 'waiting for db...'; sleep 1; done; \
  python -m visionflow.cli initdb; \
  python -m uvicorn visionflow.api.app:app --host 0.0.0.0 --port ${PORT:-8000}"
