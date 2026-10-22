FROM python:3.11-slim

# Enforce Python stdout flushing and disable bytecode cache
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# Install security certificates and system build tools
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy application domains
COPY greenops/ ./greenops/
COPY data/ ./data/

# Run as non-privileged service user (CIS Docker Benchmark)
RUN useradd -m -u 10001 greenops && \
    chown -R greenops:greenops /app
USER greenops

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

CMD ["uvicorn", "greenops.main:app", "--host", "0.0.0.0", "--port", "8000"]
