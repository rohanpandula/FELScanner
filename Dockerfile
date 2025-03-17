FROM python:3.10-slim

# Add metadata
LABEL maintainer="rohanpandula (https://github.com/rohanpandula)"
LABEL description="FELScanner - Plex media scanner for Dolby Vision and Atmos content"
LABEL version="1.0.0"

# Install dependencies including curl for healthcheck, network tools, and Node.js
RUN apt-get update && apt-get install -y \
    curl \
    iputils-ping \
    net-tools \
    dnsutils \
    netcat-openbsd \
    gnupg && \
    # Install Node.js
    curl -fsSL https://deb.nodesource.com/setup_18.x | bash - && \
    apt-get install -y nodejs && \
    # Clean up
    rm -rf /var/lib/apt/lists/*

# Verify Node.js and npm installation
RUN node --version && npm --version

# Set working directory
WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY app.py scanner.py ./
COPY static/ ./static/
COPY templates/ ./templates/
COPY check-plex.sh ./
RUN chmod +x check-plex.sh

# Copy IPTScanner files
COPY iptscanner/ ./iptscanner/

# Install Node.js dependencies for IPTScanner
WORKDIR /app/iptscanner
RUN npm install --no-cache
WORKDIR /app

# Create directories for persistent data and set permissions
RUN mkdir -p /data/exports && \
    mkdir -p /data/iptscanner/data && \
    mkdir -p /data/iptscanner/profile && \
    chmod -R 777 /data

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV FLASK_APP=app.py
ENV DATA_DIR=/data
ENV NODE_ENV=production

# Expose port
EXPOSE 5000

# Volume for persistent data
VOLUME ["/data"]

# Use a healthcheck to verify the application is running properly
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:5000/ || exit 1

# Start the application
CMD ["python", "app.py"] 