FROM python:3.11-slim

# System dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    bash \
    ca-certificates \
    locales \
    gnucobol \
    && rm -rf /var/lib/apt/lists/*

ENV LANG=C.UTF-8 LC_ALL=C.UTF-8

WORKDIR /app

# Copy the environment directory to /app/environment
# Context is the 'environment' directory itself during 'docker build'
COPY . /app/environment/

# Set working directory to /app where the host will mount 'tests' and 'solution'
WORKDIR /app
