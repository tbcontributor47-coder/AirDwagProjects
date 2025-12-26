FROM python:3.11-slim

WORKDIR /app

# Install dependencies
RUN pip install --no-cache-dir pytest

# Copy application files
COPY environment/app/ /app/
COPY schema.json /app/
COPY clearing_accounts.txt /app/
COPY tests/ /app/tests/

# Make scripts executable
RUN chmod +x /app/validate_eft.py

# Default command runs tests
CMD ["python3", "-m", "pytest", "tests/test_validator.py", "-v"]
