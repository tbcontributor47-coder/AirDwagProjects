FROM python:3.9-slim

# System dependencies only
RUN apt-get update && apt-get install -y --no-install-recommends \
    bash \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy files
# Context is the environment directory. We copy it to /app/environment
# to match the paths expected by the tests and solution.
COPY . /app/environment/

CMD ["bash", "/app/tests/test.sh"]
