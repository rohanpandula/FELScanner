/**
 * Configuration
 * Environment variable management
 */

require('dotenv').config();

module.exports = {
  // Server
  PORT: process.env.PORT || 3000,
  NODE_ENV: process.env.NODE_ENV || 'production',

  // FlareSolverr
  FLARESOLVERR_URL: process.env.FLARESOLVERR_URL || 'http://flaresolverr:8191',

  // IPTorrents
  IPT_UID: process.env.IPT_UID || '',
  IPT_PASS: process.env.IPT_PASS || '',
  IPT_CF_CLEARANCE: process.env.IPT_CF_CLEARANCE || '',
  IPT_HIDE_CATS: process.env.IPT_HIDE_CATS || '0',
  IPT_HIDE_TOP: process.env.IPT_HIDE_TOP || '0',
  IPT_SEARCH_URL: process.env.IPT_SEARCH_URL || 'https://iptorrents.com/t?q=BL%2BEL%2BRPU&qf=all#torrents',

  // Scraper
  SEARCH_TERM: process.env.SEARCH_TERM || 'BL+EL+RPU',
  HEADLESS: process.env.HEADLESS !== 'false',

  // Data
  DATA_PATH: process.env.DATA_PATH || '/data',

  // Logging
  LOG_LEVEL: process.env.LOG_LEVEL || 'info',
};
