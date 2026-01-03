FROM python:3.11-slim

WORKDIR /app

# Runtime utilities:
# - bash: required by verifier
# - locales: deterministic locale
# - gnucobol: COBOL compiler/runtime
RUN apt-get update \
	&& apt-get install -y --no-install-recommends bash ca-certificates locales gnucobol \
	&& rm -rf /var/lib/apt/lists/* \
	&& mkdir -p /logs/verifier

ENV LANG=C.UTF-8 LC_ALL=C.UTF-8

# Copy application files (build context is the environment/ directory)
COPY . /app/environment/

# COBOL program expects input.dat in the working directory
RUN ln -s /app/environment/data/input.dat /app/input.dat

# Compile the code
# The source is in /app/environment/app/reconcile.cbl
RUN cobc -x -o reconcile_app environment/app/reconcile.cbl

# Default command
CMD ["./reconcile_app"]
