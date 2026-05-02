FROM python:3.11-slim

# cups-bsd provides lpr; cups-client provides lpstat and other CUPS tools
RUN apt-get update && apt-get install -y --no-install-recommends cups-bsd cups-client \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY bot.py monitor.py gallery.py ./
