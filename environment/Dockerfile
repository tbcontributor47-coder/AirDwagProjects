FROM hashicorp/terraform:light

# Install verification tools
RUN apk add --no-cache \
    python3 \
    py3-pip \
    curl \
    bash \
    jq

# Install Prometheus tool (promtool) for validation
RUN curl -LO https://github.com/prometheus/prometheus/releases/download/v2.45.0/prometheus-2.45.0.linux-amd64.tar.gz \
    && tar xvfz prometheus-2.45.0.linux-amd64.tar.gz \
    && mv prometheus-2.45.0.linux-amd64/promtool /usr/bin/promtool \
    && rm -rf prometheus-2.45.0.linux-amd64*

# Install Python deps for verification
RUN pip3 install pyyaml

WORKDIR /app

COPY . /app/

CMD ["bash", "/app/tests/test.sh"]
