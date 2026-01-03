FROM python:3.11-slim-bookworm

# Install ONLY runtime system dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends bash ca-certificates && \
    rm -rf /var/lib/apt/lists/*

# Standard location for evaluation logs
RUN mkdir -p /logs/verifier && chmod -R 0777 /logs

# Copy application code from context
COPY app/ /app/
COPY data/ /app/data/

WORKDIR /app

# Ensure logs dir is writable
RUN chmod -R 777 /logs
