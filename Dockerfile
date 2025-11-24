## ===========================
##       BUILDER STAGE
## ===========================
FROM python:3.13-slim-bookworm AS builder

# Install required system packages for building wheels
RUN apt-get update \
 && apt-get install -y --no-install-recommends build-essential curl \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install uv (recommended method)
COPY --from=ghcr.io/astral-sh/uv:0.9.1 /uv /uvx /bin/

# Copy dependency files first (for caching)
COPY pyproject.toml uv.lock ./

# Create venv & install dependencies using uv
RUN uv sync --frozen

# Copy full application source (only needed files)
COPY vector_db.py main.py gunicorn_config.py data_loader.py custom_types.py .python-version ./

## ===========================
##      PRODUCTION STAGE
## ===========================
FROM python:3.13-slim-bookworm AS production

# Create a non-root user
RUN useradd --create-home --shell /usr/sbin/nologin appuser

WORKDIR /app

# Copy virtual environment generated in builder
COPY --from=builder /app/.venv /app/.venv

# Copy project files
COPY --from=builder /app/vector_db.py \
                    /app/main.py \
                    /app/gunicorn_config.py \
                    /app/data_loader.py \
                    /app/custom_types.py \
                    /app/.python-version \
                    /app/

# Environment configuration
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    OPENAI_API_KEY="" \
    QDRANT_HOST="" \
    QDRANT_PORT="" \
    QDRANT_COLLECTION="" \
    PORT=8080

# Expose FastAPI/Gunicorn port
EXPOSE 8000

# Switch to unprivileged user
USER appuser

# Run application using Gunicorn
CMD ["gunicorn", "-c", "gunicorn_config.py", "main:app"]
