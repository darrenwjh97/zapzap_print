FROM python:3.11-slim

# cups-client provides lpr so the print bot can send jobs to the host Mac's CUPS
RUN apt-get update && apt-get install -y --no-install-recommends cups-client \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY bot.py monitor.py gallery.py ./
