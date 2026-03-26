/**
 * IPT Scraper Microservice
 * Express REST API for IPTorrents scraping
 */

const express = require('express');
const scraper = require('./scraper');
const logger = require('./logger');
const config = require('./config');

const app = express();
const PORT = config.PORT || 3000;

// Middleware
app.use(express.json());
app.use((req, res, next) => {
  logger.info(`${req.method} ${req.path}`, { ip: req.ip });
  next();
});

// Health check
app.get('/health', (req, res) => {
  res.json({
    status: 'healthy',
    service: 'ipt-scraper',
    version: '2.0.0',
    uptime: process.uptime(),
  });
});

// Trigger scan (regular POST endpoint)
app.post('/api/scan', async (req, res) => {
  try {
    logger.info('Scan triggered via API');

    const results = await scraper.scan();

    res.json({
      success: true,
      timestamp: new Date().toISOString(),
      results: {
        total: results.length,
        new: results.filter(r => r.isNew).length,
        torrents: results,
      },
    });
  } catch (error) {
    logger.error('Scan failed', { error: error.message });
    res.status(500).json({
      success: false,
      error: error.message,
    });
  }
});

// Trigger scan with SSE streaming logs
app.get('/api/scan/stream', async (req, res) => {
  logger.info('Streaming scan triggered via API');

  // Set SSE headers
  res.setHeader('Content-Type', 'text/event-stream');
  res.setHeader('Cache-Control', 'no-cache');
  res.setHeader('Connection', 'keep-alive');
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.flushHeaders();

  // Helper to send SSE event
  const sendEvent = (data) => {
    res.write(`data: ${JSON.stringify(data)}\n\n`);
  };

  try {
    // Run scan with log callback
    const results = await scraper.scan((logEntry) => {
      sendEvent({ type: 'log', ...logEntry });
    });

    // Send final results
    sendEvent({
      type: 'complete',
      timestamp: new Date().toISOString(),
      results: {
        total: results.length,
        new: results.filter(r => r.isNew).length,
      },
    });
  } catch (error) {
    sendEvent({
      type: 'error',
      timestamp: new Date().toISOString(),
      message: error.message,
    });
  } finally {
    res.end();
  }
});

// Get latest results
app.get('/api/results', async (req, res) => {
  try {
    const results = await scraper.getLatestResults();

    res.json({
      success: true,
      timestamp: results.timestamp,
      results: {
        total: results.torrents.length,
        new: results.torrents.filter(t => t.isNew).length,
        torrents: results.torrents,
      },
    });
  } catch (error) {
    logger.error('Failed to get results', { error: error.message });
    res.status(500).json({
      success: false,
      error: error.message,
    });
  }
});

// Get known torrents
app.get('/api/known', async (req, res) => {
  try {
    const known = await scraper.getKnownTorrents();

    res.json({
      success: true,
      count: known.length,
      torrents: known,
    });
  } catch (error) {
    logger.error('Failed to get known torrents', { error: error.message });
    res.status(500).json({
      success: false,
      error: error.message,
    });
  }
});

// Clear known torrents
app.delete('/api/known', async (req, res) => {
  try {
    await scraper.clearKnownTorrents();

    logger.info('Known torrents cleared');
    res.json({
      success: true,
      message: 'Known torrents cleared',
    });
  } catch (error) {
    logger.error('Failed to clear known torrents', { error: error.message });
    res.status(500).json({
      success: false,
      error: error.message,
    });
  }
});

// Error handler
app.use((err, req, res, next) => {
  logger.error('Unhandled error', { error: err.message, stack: err.stack });
  res.status(500).json({
    success: false,
    error: 'Internal server error',
  });
});

// Start server
const server = app.listen(PORT, () => {
  logger.info(`IPT Scraper API started`, { port: PORT });
});

// Graceful shutdown
process.on('SIGTERM', () => {
  logger.info('SIGTERM received, shutting down gracefully');

  server.close(async () => {
    logger.info('HTTP server closed');

    // Close browser if open
    await scraper.cleanup();

    process.exit(0);
  });
});

process.on('SIGINT', () => {
  logger.info('SIGINT received, shutting down gracefully');

  server.close(async () => {
    logger.info('HTTP server closed');

    // Close browser if open
    await scraper.cleanup();

    process.exit(0);
  });
});

module.exports = app;
