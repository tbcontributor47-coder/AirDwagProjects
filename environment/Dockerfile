FROM python:3.11-slim

WORKDIR /app

# Copy application files from the environment build context
COPY app/ /app/

# Make the primary script executable if present
RUN if [ -f /app/validate_eft.py ]; then chmod +x /app/validate_eft.py; fi

# Default command: run tests if any are present under /app/tests
CMD ["/bin/sh", "-c", "if [ -d /app/tests ]; then python3 -m pytest /app/tests/test_validator.py -v; else sleep 1; fi"]
