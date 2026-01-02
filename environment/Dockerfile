FROM python:3.9-slim

# System dependencies only
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    unzip \
    bash \
    jq \
    && rm -rf /var/lib/apt/lists/*

# Install Python verification deps
RUN pip install pyyaml==6.0.1

WORKDIR /app

# Copy the environment first to keep the solution and tests potentially separate
COPY environment /app/environment
COPY tests /app/tests

# Purge solution from the image to prevent cheating
# (Alternatively, use .dockerignore which is better)

CMD ["bash", "/app/tests/test.sh"]
