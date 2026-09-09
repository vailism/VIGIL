FROM python:3.12-slim

WORKDIR /app

# Install system dependencies if required for lightgbm or pandas
RUN apt-get update && apt-get install -y libgomp1 && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY sanket/ /app/sanket/
# Copy DATA/ as fallback, but don't fail if we want to build without it.
# Actually, the user wants us to upload to GCS, but keep it in github for now.
# So we will copy it, but in Cloud Run it will use GCS if SANKET_STORAGE_MODE=gcs is set.
COPY DATA/ /app/DATA/

ENV PYTHONPATH=/app
ENV SANKET_STORAGE_MODE=gcs

CMD ["sh", "-c", "uvicorn sanket.api:app --host 0.0.0.0 --port ${PORT:-8000}"]
