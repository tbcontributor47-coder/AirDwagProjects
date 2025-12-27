FROM python:3.11-slim

WORKDIR /app

# Minimal runtime utilities:
# - bash: required by verifier `tests/test.sh`
# - ca-certificates: required for pip to fetch wheels reliably
RUN apt-get update \
	&& apt-get install -y --no-install-recommends bash ca-certificates \
	&& rm -rf /var/lib/apt/lists/* \
	&& mkdir -p /logs/verifier

# Copy application files from the environment build context
COPY app/ /app/

# Make the primary script executable if present
RUN if [ -f /app/validate_eft.py ]; then chmod +x /app/validate_eft.py; fi

# Create payees DB inside the image so the runtime `/app` contains `payees.db`
# The helper script `create_payees_db.py` is included in the app/ directory.
RUN if [ -f /app/create_payees_db.py ]; then python3 /app/create_payees_db.py /app/payees.db; fi

# Default command: run tests if any are present under /app/tests
CMD ["/bin/sh", "-c", "if [ -d /app/tests ]; then python3 -m pytest /app/tests/test_outputs.py -v; else sleep 1; fi"]