/**
 * Logger
 * Winston-based structured logging
 */

const winston = require('winston');
const config = require('./config');

const logger = winston.createLogger({
  level: config.LOG_LEVEL,
  format: winston.format.combine(
    winston.format.timestamp(),
    winston.format.errors({ stack: true }),
    winston.format.json()
  ),
  defaultMeta: {
    service: 'ipt-scraper',
    version: '2.0.0',
  },
  transports: [
    new winston.transports.Console({
      format:
        config.NODE_ENV === 'development'
          ? winston.format.combine(
              winston.format.colorize(),
              winston.format.simple()
            )
          : winston.format.json(),
    }),
  ],
});

module.exports = logger;
