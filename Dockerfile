FROM python:3.11-slim

WORKDIR /app

# System dependencies for panphon/epitran
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Add web deps
RUN pip install --no-cache-dir fastapi uvicorn

# App code
COPY engine/ engine/
COPY data/de_words.db data/
COPY web/ web/

# Run FastAPI
CMD ["uvicorn", "web.api:app", "--host", "0.0.0.0", "--port", "7860"]
