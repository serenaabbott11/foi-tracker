# OPS-4a: production-oriented image for the FOI Deadline Tracker.
#
# python:3.12-slim base, non-root user, Gunicorn WSGI server,
# HEALTHCHECK pointing at /api/healthz. Data is in a named volume so the
# DB survives container replacement. See docs/DEPLOYMENT.md for usage.

FROM python:3.12-slim

# System packages needed at runtime: sqlite3 CLI for backup/restore scripts
# and the healthcheck-in-python-onliner needs nothing extra.
RUN apt-get update && apt-get install -y --no-install-recommends \
        sqlite3 \
    && rm -rf /var/lib/apt/lists/*

RUN useradd --system --create-home --shell /usr/sbin/nologin foi

WORKDIR /app

# Install Python deps first for better layer caching.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# App code.
COPY foi_tracker/ ./foi_tracker/
COPY scripts/ ./scripts/
COPY run.py .

# Data + backups live in named volumes so the DB survives image rebuilds.
RUN mkdir -p /data /backups && chown foi:foi /data /backups
VOLUME ["/data", "/backups"]

ENV FOI_DB=/data/foi.db \
    BACKUP_DIR=/backups \
    PYTHONUNBUFFERED=1

USER foi
EXPOSE 5002

# HEALTHCHECK relies on OPS-6's /api/healthz endpoint.
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request as u, sys; sys.exit(0 if u.urlopen('http://localhost:5002/api/healthz').status == 200 else 1)" \
    || exit 1

CMD ["gunicorn", "--bind", "0.0.0.0:5002", "--workers", "2", \
     "--access-logfile", "-", "--error-logfile", "-", \
     "foi_tracker.app:app"]
