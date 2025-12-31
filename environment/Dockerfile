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

# Copy application files
COPY app/ /app/

# Compile the code
RUN cobc -x -o merge_app merge.cbl

# Default command
CMD ["./merge_app"]
