FROM eclipse-temurin:17-jdk

# Install Maven, GnuCOBOL, Python, and other dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    maven \
    gnucobol \
    bash \
    curl \
    ca-certificates \
    python3 \
    python3-pip \
    && rm -rf /var/lib/apt/lists/*

# Pre-install pytest
RUN pip install --no-cache-dir pytest --break-system-packages

ENV LANG=C.UTF-8 LC_ALL=C.UTF-8

WORKDIR /app

# Copy the environment directory to /app/environment
COPY . /app/environment/

WORKDIR /app
