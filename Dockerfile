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
    gnupg \
    # Add the gcc compiler for psutil
    gcc \
    python3-dev \
    # Add Chrome dependencies for Puppeteer
    ca-certificates \
    fonts-liberation \
    libasound2 \
    libatk-bridge2.0-0 \
    libatk1.0-0 \
    libc6 \
    libcairo2 \
    libcups2 \
    libdbus-1-3 \
    libexpat1 \
    libfontconfig1 \
    libgbm1 \
    libglib2.0-0 \
    libgtk-3-0 \
    libnspr4 \
    libnss3 \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libstdc++6 \
    libx11-6 \
    libx11-xcb1 \
    libxcb1 \
    libxcomposite1 \
    libxcursor1 \
    libxdamage1 \
    libxext6 \
    libxfixes3 \
    libxi6 \
    libxrandr2 \
    libxrender1 \
    libxss1 \
    libxtst6 \
    lsb-release \
    wget \
    xdg-utils \
    # Install Chromium (works on both ARM and AMD64)
    chromium \
    && \
    # Install Node.js
    curl -fsSL https://deb.nodesource.com/setup_18.x | bash - && \
    apt-get install -y nodejs && \
    # Clean up
    rm -rf /var/lib/apt/lists/*

# Verify Node.js and npm installation
RUN node --version && npm --version

# Set working directory
WORKDIR /app

# Create and activate a Python virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Clone the repository from the radar branch
RUN apt-get update && apt-get install -y git && \
    git clone -b radar https://github.com/rohanpandula/FELScanner.git /tmp/felscanner && \
    cp -r /tmp/felscanner/* /app/ && \
    rm -rf /tmp/felscanner && \
    apt-get remove -y git && \
    apt-get autoremove -y && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Copy application files (these will be overwritten by the cloned repository)
# COPY app.py scanner.py ./
# COPY static/ ./static/
# COPY templates/ ./templates/

# Copy IPTScanner files (these will be overwritten by the cloned repository)
# COPY iptscanner/ ./iptscanner/

# Install Node.js dependencies for IPTScanner
WORKDIR /app/iptscanner
# Set Puppeteer to skip downloading Chrome and use system Chromium
ENV PUPPETEER_SKIP_CHROMIUM_DOWNLOAD=true
ENV PUPPETEER_EXECUTABLE_PATH=/usr/bin/chromium
# Install Node.js dependencies with increased network timeout
RUN npm install --no-cache --network-timeout=100000
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

# Start the application with host network binding
CMD ["python", "-u", "app.py", "--host=0.0.0.0", "--port=5000"] 