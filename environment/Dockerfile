FROM python:3.9-slim

# System dependencies only
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    unzip \
    bash \
    jq \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy files
# We only copy the environment and tests. 
# solution/ is excluded via .dockerignore to prevent cheating.
COPY environment /app/environment
COPY tests /app/tests

CMD ["bash", "/app/tests/test.sh"]
