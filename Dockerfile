# Jarvis application image.
#
# Two stages so build tooling and wheel caches do not ship to production. The
# runtime stage installs no compiler, which keeps the image small and removes
# a class of attack surface.

FROM python:3.12-slim AS builder

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /build

# Requirements are copied alone so this layer is cached until they change,
# rather than on every source edit.
COPY requirements.txt ./
RUN python -m venv /opt/venv \
    && /opt/venv/bin/pip install --no-cache-dir -r requirements.txt


FROM python:3.12-slim AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/opt/venv/bin:$PATH"

# Runs unprivileged: a container that does not need root should not have it.
RUN useradd --create-home --uid 10001 jarvis

WORKDIR /app

COPY --from=builder /opt/venv /opt/venv
COPY --chown=jarvis:jarvis app ./app
COPY --chown=jarvis:jarvis alembic ./alembic
COPY --chown=jarvis:jarvis scripts ./scripts
COPY --chown=jarvis:jarvis frontend ./frontend
COPY --chown=jarvis:jarvis alembic.ini ./

# Directories the application writes to at runtime. Without these, generating
# or ingesting documents inside the container fails with EACCES, because the
# WORKDIR itself belongs to root.
RUN mkdir -p /app/documents /app/eval/results && chown -R jarvis:jarvis /app

USER jarvis

EXPOSE 8000

# Uses the health endpoint the application already exposes, so the container's
# notion of healthy matches the application's.
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=4).status == 200 else 1)"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
