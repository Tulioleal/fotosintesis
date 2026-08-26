FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HOME=/tmp \
    PYTHONPYCACHEPREFIX=/tmp/pycache

WORKDIR /app

COPY pyproject.toml ./
COPY alembic.ini ./
COPY app ./app
COPY migrations ./migrations
COPY scripts ./scripts

RUN pip install --no-cache-dir -e .

# Fixed unprivileged runtime identity (UID/GID 10001). The runtime user has no
# writable ownership inside the image: /app stays root-owned and read-only, and
# all runtime writes (HOME, bytecode cache, local object storage) go to /tmp,
# which Kubernetes backs with an explicit emptyDir volume. Build and dependency
# steps above ran as root; production uses GCS object storage.
RUN addgroup --system --gid 10001 app \
    && adduser --system --uid 10001 --ingroup app --home /tmp app

EXPOSE 8000

USER 10001:10001

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
