FROM python:3.11-slim

WORKDIR /app

# Runtime utilities:
# - bash: required by verifier `tests/test.sh`
# - locales: deterministic locale
# - gnucobol: COBOL compiler/runtime
RUN apt-get update \
	&& apt-get install -y --no-install-recommends bash ca-certificates locales gnucobol \
	&& rm -rf /var/lib/apt/lists/* \
	&& mkdir -p /logs/verifier

ENV LANG=C.UTF-8 LC_ALL=C.UTF-8

# Copy application files from the environment build context
COPY app/ /app/

RUN chmod +x /app/run_cobol.sh

# Default command (not relied on by Jenkins): keep container alive briefly
CMD ["/bin/sh", "-c", "sleep 1"]
