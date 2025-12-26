FROM python:3.13-slim-bookworm

# Install runtime dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends bash ca-certificates && \
    rm -rf /var/lib/apt/lists/*

# Create log directories with open permissions
RUN mkdir -p /logs/agent /logs/verifier && chmod -R 0777 /logs

# Copy only application code (not tests or solution)
COPY app/ /app/

WORKDIR /app
