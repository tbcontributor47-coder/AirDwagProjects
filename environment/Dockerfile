FROM python:3.9-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    bash \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install yq for YAML processing
RUN curl -L https://github.com/mikefarah/yq/releases/latest/download/yq_linux_amd64 -o /usr/local/bin/yq && \
    chmod +x /usr/local/bin/yq

WORKDIR /app
RUN mkdir -p /logs/agent /logs/verifier && chmod -R 777 /logs

# The context is the 'environment/' directory.
# This copies 'environment/app/' to '/app/app/'
COPY . /app/

CMD ["bash", "/app/tests/test.sh"]
