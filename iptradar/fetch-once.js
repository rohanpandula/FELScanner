#!/usr/bin/env node
const fs = require('fs');
const path = require('path');
const axios = require('axios');
const cheerio = require('cheerio');
const yargs = require('yargs/yargs');
const { hideBin } = require('yargs/helpers');

function normaliseCookies(rawCookies) {
  if (Array.isArray(rawCookies)) return rawCookies;
  if (rawCookies && typeof rawCookies === 'object') {
    const entries = [];
    for (const [name, value] of Object.entries(rawCookies)) {
      entries.push({
        name,
        value,
        domain: '.iptorrents.com',
        path: '/',
        expires: Math.floor(Date.now() / 1000) + 86400 * 30
      });
    }
    return entries;
  }
  return [];
}

async function requestThroughSolver(url, cookies, solverUrl, timeout) {
  const endpoint = `${solverUrl.replace(/\/+$/, '')}/v1`;
  const payload = {
    cmd: 'request.get',
    url,
    maxTimeout: timeout,
    cookies
  };

  const response = await axios.post(endpoint, payload, {
    timeout: timeout + 15000
  });

  if (!response.data || response.data.status !== 'ok') {
    throw new Error(
      response.data && response.data.message
        ? `FlareSolverr error: ${response.data.message}`
        : 'Unknown FlareSolverr error'
    );
  }

  const solution = response.data.solution;
  if (!solution || typeof solution.response !== 'string') {
    throw new Error('Invalid response received from FlareSolverr');
  }

  return solution;
}

function parseTorrentTable(html) {
  const $ = cheerio.load(html);
  const rows = $('table#torrents > tbody > tr');
  const results = [];

  rows.each((_, row) => {
    const $row = $(row);
    if ($row.hasClass('head') || $row.hasClass('header')) return;

    const cells = $row.find('td');
    if (cells.length < 8) return;

    const nameCell = $(cells[1]);
    const linkElem = nameCell.find("a[href^='/t/']").first();

    const name = linkElem.text().trim() || 'Unknown';
    let link = linkElem.attr('href') || '';
    if (link) {
      link = new URL(link, 'https://iptorrents.com').href;
    }

    const hasNewTag = nameCell.find('span.tag').length > 0;

    const subDiv = nameCell.find('.sub').first();
    let addedRaw = '';
    if (subDiv.length) {
      const text = subDiv.text().trim();
      addedRaw = text.includes(' | ') ? text.split(' | ')[1].trim() : text;
    }

    const size = (cells[5] && $(cells[5]).text().trim()) || '';
    const seeders = parseInt((cells[7] && $(cells[7]).text().trim()) || '0', 10) || 0;
    const leechers = parseInt((cells[8] && $(cells[8]).text().trim()) || '0', 10) || 0;

    results.push({
      name,
      link,
      size,
      seeders,
      leechers,
      addedRaw,
      added: addedRaw,
      isNew: hasNewTag
    });
  });

  return results;
}

async function fetchTorrents({
  cookiesPath,
  searchTerm,
  solverUrl = 'http://localhost:8191',
  timeout = 60000,
  debugPath
}) {
  const resolvedCookiesPath = path.resolve(cookiesPath);
  if (!fs.existsSync(resolvedCookiesPath)) {
    throw new Error(`Cookies file not found: ${resolvedCookiesPath}`);
  }

  let rawCookies;
  try {
    rawCookies = JSON.parse(fs.readFileSync(resolvedCookiesPath, 'utf8'));
  } catch (error) {
    throw new Error(`Failed to read cookies file: ${error.message}`);
  }

  const cookies = normaliseCookies(rawCookies);
  if (!Array.isArray(cookies) || cookies.length === 0) {
    throw new Error('Cookies file does not contain a valid cookie array.');
  }

  const searchUrl = new URL(
    `/t?q=${encodeURIComponent(searchTerm)}&qf=adv#torrents`,
    'https://iptorrents.com'
  ).toString();

  const solution = await requestThroughSolver(
    searchUrl,
    cookies,
    solverUrl,
    timeout
  );

  if (debugPath) {
    fs.writeFileSync(path.resolve(debugPath), solution.response, 'utf8');
  }

  const torrents = parseTorrentTable(solution.response);
  return {
    searchTerm,
    fetchedAt: new Date().toISOString(),
    torrents,
    solverCookies: solution.cookies || [],
    userAgent: solution.userAgent || '',
    status: 'ok'
  };
}

async function runCli() {
  const argv = yargs(hideBin(process.argv))
    .option('cookies', {
      alias: 'c',
      describe: 'Path to IPTorrents cookies JSON file',
      type: 'string',
      demandOption: true
    })
    .option('search', {
      alias: 's',
      describe: 'Search term to use (e.g. BL+EL+RPU)',
      type: 'string',
      demandOption: true
    })
    .option('output', {
      alias: 'o',
      describe: 'Optional path to write JSON results',
      type: 'string'
    })
    .option('solver-url', {
      alias: ['u', 'solver'],
      describe: 'FlareSolverr base URL',
      type: 'string',
      default: process.env.FLARESOLVERR_URL || 'http://localhost:8191'
    })
    .option('timeout', {
      alias: 't',
      describe: 'Maximum time (ms) FlareSolverr can take to solve the challenge',
      type: 'number',
      default: 60000
    })
    .option('debug', {
      describe: 'Write raw HTML response alongside JSON output',
      type: 'boolean',
      default: false
    })
    .strict()
    .help()
    .argv;

  try {
    const result = await fetchTorrents({
      cookiesPath: argv.cookies,
      searchTerm: argv.search.trim(),
      solverUrl: argv['solver-url'],
      timeout: argv.timeout,
      debugPath: argv.debug ? 'fetch-debug.html' : undefined
    });

    if (argv.output) {
      fs.writeFileSync(path.resolve(argv.output), JSON.stringify(result, null, 2));
      console.log(`Saved ${result.torrents.length} torrents to ${argv.output}`);
    } else {
      console.log(JSON.stringify(result, null, 2));
    }
  } catch (error) {
    console.error(`Error: ${error.message}`);
    process.exit(1);
  }
}

if (require.main === module) {
  runCli();
}

module.exports = {
  fetchTorrents,
  parseTorrentTable,
  normaliseCookies
};
