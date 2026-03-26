/**
 * IPTorrents Scraper
 * Puppeteer + FlareSolverr integration for scraping IPTorrents
 */

const fs = require('fs').promises;
const path = require('path');
const axios = require('axios');
const logger = require('./logger');
const config = require('./config');

// File paths
const KNOWN_TORRENTS_FILE = path.join(config.DATA_PATH, 'known_torrents.json');
const LATEST_RESULTS_FILE = path.join(config.DATA_PATH, 'latest_results.json');

let browser = null;

/**
 * Initialize data directory
 */
async function ensureDataDir() {
  try {
    await fs.mkdir(config.DATA_PATH, { recursive: true });
  } catch (error) {
    logger.error('Failed to create data directory', { error: error.message });
  }
}

/**
 * Load known torrents from file
 */
async function loadKnownTorrents() {
  try {
    const data = await fs.readFile(KNOWN_TORRENTS_FILE, 'utf8');
    return JSON.parse(data);
  } catch (error) {
    // File doesn't exist or is invalid
    return [];
  }
}

/**
 * Save known torrents to file
 */
async function saveKnownTorrents(torrents) {
  await ensureDataDir();
  await fs.writeFile(
    KNOWN_TORRENTS_FILE,
    JSON.stringify(torrents, null, 2),
    'utf8'
  );
}

/**
 * Save latest results to file
 */
async function saveLatestResults(results) {
  await ensureDataDir();
  const data = {
    timestamp: new Date().toISOString(),
    torrents: results,
  };
  await fs.writeFile(
    LATEST_RESULTS_FILE,
    JSON.stringify(data, null, 2),
    'utf8'
  );
}

/**
 * Use FlareSolverr to bypass Cloudflare
 */
async function solveCaptcha(url) {
  try {
    logger.info('Requesting FlareSolverr to solve Cloudflare challenge');

    const cookies = [
      { name: 'uid', value: config.IPT_UID },
      { name: 'pass', value: config.IPT_PASS },
    ];

    // Add cf_clearance if available (critical for Cloudflare bypass)
    if (config.IPT_CF_CLEARANCE) {
      cookies.push({ name: 'cf_clearance', value: config.IPT_CF_CLEARANCE });
    }

    // Add optional cookies
    if (config.IPT_HIDE_CATS) {
      cookies.push({ name: 'hideCats', value: config.IPT_HIDE_CATS });
    }
    if (config.IPT_HIDE_TOP) {
      cookies.push({ name: 'hideTop', value: config.IPT_HIDE_TOP });
    }

    const response = await axios.post(
      `${config.FLARESOLVERR_URL}/v1`,
      {
        cmd: 'request.get',
        url: url,
        maxTimeout: 60000,
        cookies: cookies,
      },
      {
        headers: { 'Content-Type': 'application/json' },
        timeout: 65000,
      }
    );

    if (response.data.status === 'ok') {
      logger.info('Cloudflare challenge solved successfully');
      return response.data.solution.response;
    } else {
      throw new Error(`FlareSolverr failed: ${response.data.message}`);
    }
  } catch (error) {
    logger.error('FlareSolverr request failed', { error: error.message });
    throw error;
  }
}

/**
 * Parse torrents from HTML response
 */
function parseTorrents(html) {
  const torrents = [];

  // Extract the main torrents table
  const tableMatch = html.match(/<table\s+id="torrents"[^>]*>.*?<tbody>(.*?)<\/tbody>/s);
  if (!tableMatch) {
    logger.warn('Could not find torrents table in HTML');
    return torrents;
  }

  const tbodyHtml = tableMatch[1];

  // Match all table rows
  const rowPattern = /<tr>(.*?)<\/tr>/gs;
  const rowMatches = tbodyHtml.matchAll(rowPattern);

  for (const rowMatch of rowMatches) {
    const rowHtml = rowMatch[1];

    // Extract all table cells
    const cells = [];
    const cellPattern = /<td[^>]*>(.*?)<\/td>/gs;
    const cellMatches = rowHtml.matchAll(cellPattern);

    for (const cellMatch of cellMatches) {
      cells.push(cellMatch[1]);
    }

    // Need at least 9 cells for a valid torrent row
    if (cells.length < 9) continue;

    // Cell 1 contains the name and link
    const nameCell = cells[1];

    // Extract title from the main link (handles both absolute and relative URLs)
    const titleMatch = nameCell.match(/<a[^>]*href="(?:https?:\/\/iptorrents\.com)?\/t\/\d+"[^>]*>([^<]+)</);
    if (!titleMatch) continue;

    const title = titleMatch[1].trim();

    // Extract torrent ID from download link in cell 3
    const downloadCell = cells[3];
    const idMatch = downloadCell.match(/download\.php\/(\d+)/);
    if (!idMatch) continue;

    const torrentId = idMatch[1];

    // Extract link to torrent page (handles both absolute and relative URLs)
    const linkMatch = nameCell.match(/href="((?:https?:\/\/iptorrents\.com)?\/t\/(\d+))"/);
    const link = linkMatch ? (linkMatch[1].startsWith('http') ? linkMatch[1] : `https://iptorrents.com${linkMatch[1]}`) : `https://iptorrents.com/t/${torrentId}`;

    // Cell 5 contains size
    const sizeCell = cells[5];
    const sizeMatch = sizeCell.match(/([\d.]+\s*[KMGT]?B)/);
    const size = sizeMatch ? sizeMatch[1].trim() : null;

    // Cells 7 and 8 contain seeders and leechers
    const seeders = parseInt(cells[7].trim(), 10) || 0;
    const leechers = parseInt(cells[8].trim(), 10) || 0;

    // Check if torrent is marked as "New"
    const isNew = nameCell.includes('class="tag">New<');

    // Extract metadata from sub div (contains date info)
    let added = 'Unknown';
    const subMatch = nameCell.match(/<div class="sub">([^<]+)</);
    if (subMatch) {
      const subText = subMatch[1];
      // Extract the date part after the pipe (e.g., "7.3 1965 Comedy Crime Mystery 2160p | 10.3 hours ago by TvTeam")
      const datePart = subText.split('|')[1];
      if (datePart) {
        added = datePart.trim();
      }
    }

    torrents.push({
      id: torrentId,
      name: title,
      link: link,
      size: size,
      seeders: seeders,
      leechers: leechers,
      added: added,
      isNew: isNew,
      downloadUrl: `https://iptorrents.com/download.php/${torrentId}/${title.replace(/[^a-zA-Z0-9]/g, '_')}.torrent`,
      timestamp: new Date().toISOString(),
    });
  }

  logger.info('Parsed torrents from HTML', { count: torrents.length });
  return torrents;
}

/**
 * Scan IPTorrents for new FEL torrents
 * @param {Function} onLog - Optional callback for streaming log messages
 */
async function scan(onLog = null) {
  // Helper to emit log messages
  const emitLog = (message, data = {}) => {
    logger.info(message, data);
    if (onLog) {
      const logEntry = {
        timestamp: new Date().toISOString(),
        message,
        ...data,
      };
      onLog(logEntry);
    }
  };

  try {
    // Check for multi-page scan (temporary for seeding)
    const numPages = parseInt(process.env.SCAN_PAGES || '1', 10);

    emitLog('Starting IPTorrents scan', {
      search_term: config.SEARCH_TERM,
      pages: numPages,
    });

    let allFoundTorrents = [];

    // Fetch multiple pages
    for (let page = 0; page < numPages; page++) {
      const pageUrl = page === 0
        ? config.IPT_SEARCH_URL
        : config.IPT_SEARCH_URL + `&p=${page}`;

      emitLog(`Fetching page ${page + 1}/${numPages}...`);

      // Use FlareSolverr to get page content
      emitLog('Solving Cloudflare challenge...');
      const html = await solveCaptcha(pageUrl);
      emitLog('Cloudflare challenge solved');

      // Parse torrents from HTML
      const pageTorrents = parseTorrents(html);

      emitLog(`Page ${page + 1} complete`, { torrents_found: pageTorrents.length });

      allFoundTorrents = allFoundTorrents.concat(pageTorrents);

      // Add delay between pages to avoid rate limiting
      if (page < numPages - 1) {
        emitLog('Waiting before next page...');
        await new Promise(resolve => setTimeout(resolve, 2000));
      }
    }

    // Remove duplicates by ID
    const uniqueTorrents = Array.from(
      new Map(allFoundTorrents.map(t => [t.id, t])).values()
    );

    emitLog('Deduplication complete', { unique_torrents: uniqueTorrents.length });

    // Load known torrents
    emitLog('Checking for new torrents...');
    const knownTorrents = await loadKnownTorrents();
    const knownIds = new Set(knownTorrents.map(t => t.id));

    // Identify new torrents
    const results = uniqueTorrents.map(torrent => ({
      ...torrent,
      isNew: !knownIds.has(torrent.id),
    }));

    const newTorrents = results.filter(t => t.isNew);

    if (newTorrents.length > 0) {
      emitLog('New torrents discovered!', { new_count: newTorrents.length });

      // Add new torrents to known list
      const updatedKnown = [
        ...knownTorrents,
        ...newTorrents.map(({ isNew, ...torrent }) => torrent),
      ];

      // Limit known torrents to last 1000
      const trimmedKnown = updatedKnown.slice(-1000);

      await saveKnownTorrents(trimmedKnown);
      emitLog('Cache updated');
    } else {
      emitLog('No new torrents found');
    }

    // Save latest results
    await saveLatestResults(results);

    emitLog('Scan complete!', { total: results.length, new: newTorrents.length });

    return results;
  } catch (error) {
    const errorMsg = `Scan failed: ${error.message}`;
    logger.error('Scan failed', { error: error.message, stack: error.stack });
    if (onLog) {
      onLog({ timestamp: new Date().toISOString(), message: errorMsg, error: true });
    }
    throw error;
  }
}

/**
 * Get latest scan results
 */
async function getLatestResults() {
  try {
    const data = await fs.readFile(LATEST_RESULTS_FILE, 'utf8');
    return JSON.parse(data);
  } catch (error) {
    return {
      timestamp: null,
      torrents: [],
    };
  }
}

/**
 * Get known torrents
 */
async function getKnownTorrents() {
  return await loadKnownTorrents();
}

/**
 * Clear known torrents
 */
async function clearKnownTorrents() {
  await saveKnownTorrents([]);
  logger.info('Known torrents cleared');
}

/**
 * Cleanup resources
 */
async function cleanup() {
  if (browser) {
    await browser.close();
    browser = null;
    logger.info('Browser closed');
  }
}

module.exports = {
  scan,
  getLatestResults,
  getKnownTorrents,
  clearKnownTorrents,
  cleanup,
};
