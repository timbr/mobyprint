FROM python:3.12-slim

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    cups-client \
    libcups2-dev \
    libreoffice-writer \
    poppler-utils \
    avahi-utils \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create upload directory
RUN mkdir -p /tmp/mobyprint

EXPOSE 8631

CMD ["python", "app.py"]
