FROM python:3.11-slim

# cups-bsd provides lpr; cups-client provides lpstat and other CUPS tools
RUN apt-get update && apt-get install -y --no-install-recommends cups-bsd cups-client \
    && rm -rf /var/lib/apt/lists/*

# Route all CUPS commands to the macOS host's CUPS server, using IPP 1.1
# (macOS rejects the IPP 2.0 negotiation Linux cups-client defaults to).
RUN mkdir -p /etc/cups && \
    echo "ServerName host.docker.internal/version=1.1" > /etc/cups/client.conf

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY bot.py monitor.py gallery.py ./
