FROM python:3.11-slim AS base

# Install system dependencies including psql client
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Ensure LF line endings and execution permissions
RUN sed -i 's/\r$//' /app/entrypoint.sh /app/Infrastructure/postgres/deploy.sh \
    && chmod +x /app/entrypoint.sh /app/Infrastructure/postgres/deploy.sh

EXPOSE 8001
# CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8001"]

ENTRYPOINT ["/app/entrypoint.sh"]