# IPT Scraper Microservice - Multi-stage Docker Build

# ============================================================================
# BASE STAGE
# ============================================================================
FROM node:18-slim as base

# Install Puppeteer dependencies
RUN apt-get update && apt-get install -y \
    wget \
    ca-certificates \
    fonts-liberation \
    libappindicator3-1 \
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
    libgcc1 \
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
    xdg-utils \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Use existing node user (UID 1000) instead of creating new user
# RUN useradd -m -u 1000 -s /bin/bash app

# Copy package files
COPY --chown=node:node package*.json ./

# Install dependencies
RUN npm install --production && \
    npm cache clean --force

# ============================================================================
# DEVELOPMENT STAGE
# ============================================================================
FROM base as development

# Install dev dependencies
RUN npm install

# Copy source code
COPY --chown=node:node . .

# Create data directory
RUN mkdir -p /data && chown node:node /data

# Switch to node user
USER node

# Expose port
EXPOSE 3000

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD wget --no-verbose --tries=1 --spider http://localhost:3000/health || exit 1

# Development command (with nodemon)
CMD ["npm", "run", "dev"]

# ============================================================================
# PRODUCTION STAGE
# ============================================================================
FROM base as production

# Copy source code
COPY --chown=node:node ./src ./src

# Create data directory
RUN mkdir -p /data && chown node:node /data

# Switch to node user
USER node

# Expose port
EXPOSE 3000

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD wget --no-verbose --tries=1 --spider http://localhost:3000/health || exit 1

# Production command
CMD ["npm", "start"]
