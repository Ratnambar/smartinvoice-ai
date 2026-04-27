FROM python:3.11-slim

WORKDIR /app

# System dependencies for psycopg2 and pdfplumber
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Python packages
# Copy requirements first — Docker caches this layer
# so it only reinstalls if requirements.txt changes
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create directories the app needs at runtime
RUN mkdir -p logs data/invoices

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]