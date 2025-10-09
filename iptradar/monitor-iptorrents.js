#!/usr/bin/env node
const fs = require("fs");
const path = require("path");
const axios = require("axios");
const cron = require("node-cron");
const crypto = require("crypto");
const readline = require("readline");
const { fetchTorrents, normaliseCookies } = require("./fetch-once");

const DEFAULT_SOLVER_URL = process.env.FLARESOLVERR_URL || "http://localhost:8191";

let CONFIG = {
  iptorrents: {
    url: "https://iptorrents.com/login",
    searchUrl: "https://iptorrents.com/t?q=BL%2BEL%2BRPU&qf=adv#torrents",
    searchTerm: "BL+EL+RPU"
  },
  telegram: {
    enabled: false,
    botToken: "YOUR_BOT_TOKEN",
    chatId: "YOUR_CHAT_ID"
  },
  checkInterval: "0 */2 * * *",
  solverUrl: DEFAULT_SOLVER_URL,
  solverTimeout: 60000,
  dataPath: path.join(__dirname, "known_torrents.json"),
  configPath: path.join(__dirname, "config.json"),
  cookiesPath: path.join(__dirname, "cookies.json"),
  debug: false,
  loginComplete: false,
  lastUpdateTime: null
};

let knownTorrents = new Set();
let lastFoundTorrents = [];
let isFirstRun = true;

const sleep = ms => new Promise(res => setTimeout(res, ms));
const rlInterface = () => readline.createInterface({ input: process.stdin, output: process.stdout });
const ask = prompt => new Promise(resolve => {
  const rl = rlInterface();
  rl.question(prompt, answer => {
    rl.close();
    resolve(answer);
  });
});

function ensureDirectory(filepath) {
  const dir = path.dirname(filepath);
  if (!fs.existsSync(dir)) {
    fs.mkdirSync(dir, { recursive: true });
  }
}

function loadConfig() {
  try {
    if (!fs.existsSync(CONFIG.configPath)) {
      return;
    }
    const raw = JSON.parse(fs.readFileSync(CONFIG.configPath, "utf8"));
    CONFIG = {
      ...CONFIG,
      ...raw,
      iptorrents: { ...CONFIG.iptorrents, ...(raw.iptorrents || {}) },
      telegram: { ...CONFIG.telegram, ...(raw.telegram || {}) }
    };
    CONFIG.iptorrents.searchUrl = `https://iptorrents.com/t?q=${encodeURIComponent(CONFIG.iptorrents.searchTerm)}&qf=adv#torrents`;
    if (!CONFIG.solverUrl) CONFIG.solverUrl = DEFAULT_SOLVER_URL;
    if (!CONFIG.solverTimeout || Number.isNaN(CONFIG.solverTimeout)) {
      CONFIG.solverTimeout = 60000;
    }
    console.log("Configuration loaded");
  } catch (error) {
    console.error("Config load error:", error.message);
  }
}

function saveConfig() {
  try {
    ensureDirectory(CONFIG.configPath);
    const serialisable = {
      ...CONFIG,
      iptorrents: { ...CONFIG.iptorrents },
      telegram: { ...CONFIG.telegram }
    };
    fs.writeFileSync(CONFIG.configPath, JSON.stringify(serialisable, null, 2));
    console.log("Configuration saved");
  } catch (error) {
    console.error("Config save error:", error.message);
  }
}

function loadKnownTorrents() {
  try {
    if (!fs.existsSync(CONFIG.dataPath)) {
      ensureDirectory(CONFIG.dataPath);
      fs.writeFileSync(CONFIG.dataPath, JSON.stringify([]));
      knownTorrents = new Set();
      return;
    }
    knownTorrents = new Set(JSON.parse(fs.readFileSync(CONFIG.dataPath, "utf8")));
    console.log(`Loaded ${knownTorrents.size} known torrents`);
  } catch (error) {
    console.error("Load known error:", error.message);
    knownTorrents = new Set();
  }
}

function saveKnownTorrents() {
  try {
    ensureDirectory(CONFIG.dataPath);
    fs.writeFileSync(CONFIG.dataPath, JSON.stringify([...knownTorrents]));
  } catch (error) {
    console.error("Save known error:", error.message);
  }
}

function readCookieFile() {
  if (!fs.existsSync(CONFIG.cookiesPath)) {
    return [];
  }
  try {
    const raw = JSON.parse(fs.readFileSync(CONFIG.cookiesPath, "utf8"));
    return normaliseCookies(raw);
  } catch (error) {
    console.error("Cookies read error:", error.message);
    return [];
  }
}

function writeCookieFile(cookies) {
  const payload = normaliseCookies(cookies);
  ensureDirectory(CONFIG.cookiesPath);
  fs.writeFileSync(CONFIG.cookiesPath, JSON.stringify(payload, null, 2));
}

async function manualCookieEntry() {
  console.log("Manual cookie entry required. Extract 'uid' and 'pass' cookies from your browser.");
  const uid = (await ask('Enter "uid" cookie: ')).trim();
  const pass = (await ask('Enter "pass" cookie: ')).trim();

  if (!uid || !pass) {
    console.log("Both cookies are required.");
    return false;
  }

  const now = Math.floor(Date.now() / 1000);
  writeCookieFile([
    { name: "uid", value: uid, domain: ".iptorrents.com", path: "/", expires: now + 86400 * 30 },
    { name: "pass", value: pass, domain: ".iptorrents.com", path: "/", expires: now + 86400 * 30 }
  ]);

  CONFIG.loginComplete = true;
  saveConfig();
  console.log("Cookies saved.");
  return true;
}

function mergeSolverCookies(newCookies) {
  if (!Array.isArray(newCookies) || newCookies.length === 0) {
    return;
  }

  const existing = readCookieFile();
  const map = new Map();

  for (const cookie of normaliseCookies(existing)) {
    const key = `${cookie.name}|${cookie.domain || ''}|${cookie.path || '/'}`;
    map.set(key, cookie);
  }

  for (const cookie of normaliseCookies(newCookies)) {
    const key = `${cookie.name}|${cookie.domain || ''}|${cookie.path || '/'}`;
    map.set(key, {
      ...cookie,
      domain: cookie.domain || ".iptorrents.com",
      path: cookie.path || "/",
      expires: cookie.expires || Math.floor(Date.now() / 1000) + 86400
    });
  }

  writeCookieFile([...map.values()]);
}

const generateTorrentId = torrent => crypto.createHash("md5").update(`${torrent.name}`).digest("hex");
const isNewTorrent = torrent => !knownTorrents.has(generateTorrentId(torrent));
const addToKnownTorrents = torrent => {
  knownTorrents.add(generateTorrentId(torrent));
  saveKnownTorrents();
};

function formatDateLA(date) {
  return new Date(date).toLocaleString("en-US", {
    timeZone: "America/Los_Angeles",
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
    hour12: true
  });
}

function cronToHumanReadable(expression) {
  const parts = expression.trim().split(/\s+/);
  if (parts.length < 2) return "Custom schedule";

  if (parts[0].startsWith("*/")) {
    const minutes = parseInt(parts[0].slice(2), 10);
    if (!Number.isNaN(minutes)) {
      return `Every ${minutes} minute${minutes > 1 ? "s" : ""}`;
    }
  }

  if (parts[0] === "0" && parts[1]?.startsWith("*/")) {
    const hours = parseInt(parts[1].slice(2), 10);
    if (!Number.isNaN(hours)) {
      return `Every ${hours} hour${hours > 1 ? "s" : ""}`;
    }
  }

  if (parts[0] === "0" && parts[1] === "0" && parts[2]?.startsWith("*/")) {
    const days = parseInt(parts[2].slice(2), 10);
    if (!Number.isNaN(days)) {
      return `Every ${days} day${days > 1 ? "s" : ""}`;
    }
  }

  return "Custom schedule";
}

const messageLog = [];
function logMessage(message) {
  messageLog.push(`[${formatDateLA(new Date())}] ${message}`);
  if (messageLog.length > 100) {
    messageLog.shift();
  }
}

function computeRelativeTime(rawText, now) {
  if (!rawText) {
    return { label: "Unknown", epoch: now };
  }

  const trimmed = rawText.split(" by ")[0].trim();
  const lower = trimmed.toLowerCase();
  const value = parseFloat(trimmed);

  if (Number.isNaN(value)) {
    return { label: trimmed, epoch: now };
  }

  const unitMap = [
    { includes: ["min"], ms: 60 * 1000, formatter: val => `${Math.round(val)} min ago` },
    { includes: ["hour"], ms: 60 * 60 * 1000, formatter: val => `${val.toFixed(1)} hr ago` },
    { includes: ["day"], ms: 24 * 60 * 60 * 1000, formatter: val => `${val.toFixed(1)} day ago` },
    { includes: ["week"], ms: 7 * 24 * 60 * 60 * 1000, formatter: val => `${val.toFixed(1)} wk ago` },
    { includes: ["month"], ms: 30 * 24 * 60 * 60 * 1000, formatter: val => `${val.toFixed(1)} mo ago` }
  ];

  for (const entry of unitMap) {
    if (entry.includes.some(term => lower.includes(term))) {
      const epoch = now - value * entry.ms;
      return { label: entry.formatter(value), epoch };
    }
  }

  return { label: trimmed, epoch: now };
}

function postProcessTorrents(torrents) {
  const now = Date.now();
  const processed = torrents.map(torrent => {
    const entry = { ...torrent };
    const { label, epoch } = computeRelativeTime(entry.addedRaw || entry.added || "", now);
    entry.added = label;
    entry.sortEpoch = entry.isNew ? Number.MAX_SAFE_INTEGER : epoch;
    return entry;
  });

  processed.sort((a, b) => {
    if (a.isNew && !b.isNew) return -1;
    if (!a.isNew && b.isNew) return 1;
    return (b.sortEpoch || 0) - (a.sortEpoch || 0);
  });

  return processed;
}

function displayTorrentsTable() {
  console.clear();

  console.log("\n\x1b[1;36m╔═══════════════════════════════════════════════════════════╗\x1b[0m");
  console.log("\x1b[1;36m║               \x1b[1;33mIPTORRENTS MONITOR\x1b[1;36m                         ║\x1b[0m");
  console.log("\x1b[1;36m╚═══════════════════════════════════════════════════════════╝\x1b[0m\n");

  console.log(`\x1b[1mSearch Term:\x1b[0m ${CONFIG.iptorrents.searchTerm}`);
  console.log(`\x1b[1mLast Check:\x1b[0m  ${CONFIG.lastUpdateTime ? formatDateLA(CONFIG.lastUpdateTime) : "Never"}`);
  console.log(`\x1b[1mSchedule:\x1b[0m    ${cronToHumanReadable(CONFIG.checkInterval)}`);
  console.log(`\x1b[1mTelegram:\x1b[0m    ${CONFIG.telegram.enabled ? "\x1b[32mEnabled\x1b[0m" : "\x1b[31mDisabled\x1b[0m"}`);

  const rows = lastFoundTorrents.slice(0, 12);
  if (rows.length === 0) {
    console.log("\n\x1b[33mNo torrents found.\x1b[0m\n");
  } else {
    console.log("\n\x1b[1;36m╔════╦══════════════════════════════════════════════╦═══════════╦═══════════╦══════════════╗\x1b[0m");
    console.log("\x1b[1;36m║\x1b[1;33m #  \x1b[1;36m║\x1b[1;33m Title                                       \x1b[1;36m║\x1b[1;33m Size      \x1b[1;36m║\x1b[1;33m S / L     \x1b[1;36m║\x1b[1;33m Added        \x1b[1;36m║\x1b[0m");
    console.log("\x1b[1;36m╠════╬══════════════════════════════════════════════╬═══════════╬═══════════╬══════════════╣\x1b[0m");

    rows.forEach((torrent, index) => {
      const title = torrent.name.length > 46 ? `${torrent.name.slice(0, 43)}...` : torrent.name.padEnd(46);
      const size = (torrent.size || "").padEnd(9);
      const seedColor = torrent.seeders > 20 ? "\x1b[32m" : torrent.seeders > 5 ? "\x1b[33m" : "\x1b[31m";
      const leechColor = torrent.leechers > 10 ? "\x1b[31m" : "\x1b[90m";
      const ratio = `${seedColor}${String(torrent.seeders).padStart(3)}\x1b[0m / ${leechColor}${String(torrent.leechers).padStart(3)}\x1b[0m`;
      const rowStart = torrent.isNew ? "\x1b[1;32m" : "\x1b[1;36m";
      const titleColor = torrent.isNew ? "\x1b[1;92m" : "\x1b[0m";
      const newTag = torrent.isNew ? " \x1b[1;33m[NEW]\x1b[0m" : "";
      const added = (torrent.added || "").padEnd(12);

      console.log(`${rowStart}║\x1b[1;33m ${(index + 1).toString().padStart(2)} \x1b[1;36m║${titleColor} ${title} \x1b[1;36m║\x1b[0m ${size} \x1b[1;36m║\x1b[0m ${ratio} \x1b[1;36m║\x1b[0m ${added}${newTag} \x1b[1;36m║\x1b[0m`);
    });

    console.log("\x1b[1;36m╚════╩══════════════════════════════════════════════╩═══════════╩═══════════╩══════════════╝\x1b[0m\n");
  }

  if (messageLog.length > 0) {
    console.log("\x1b[1;36m╔═══════════════════════════════════════════════════════════╗\x1b[0m");
    console.log("\x1b[1;36m║                    \x1b[1;33mACTIVITY LOG\x1b[1;36m                         ║\x1b[0m");
    console.log("\x1b[1;36m╚═══════════════════════════════════════════════════════════╝\x1b[0m\n");
    messageLog.slice(-5).forEach(message => console.log(`  ${message}`));
    console.log("");
  }

  console.log("\x1b[90mPress Ctrl+C to exit\x1b[0m\n");
}

async function sendTelegramMessage(message) {
  if (!CONFIG.telegram.enabled || CONFIG.telegram.botToken === "YOUR_BOT_TOKEN") {
    return false;
  }

  try {
    const MAX_LENGTH = 4000;
    const sections = [];

    if (message.length <= MAX_LENGTH) {
      sections.push(message);
    } else {
      const [header, ...rest] = message.split("\n\n");
      let current = `${header}\n\n`;

      for (const block of rest) {
        if (current.length + block.length + 2 > MAX_LENGTH) {
          sections.push(current);
          current = `${header} (continued)\n\n${block}\n\n`;
        } else {
          current += `${block}\n\n`;
        }
      }

      if (current.trim().length) {
        sections.push(current);
      }
    }

    for (let i = 0; i < sections.length; i += 1) {
      await axios.post(
        `https://api.telegram.org/bot${CONFIG.telegram.botToken}/sendMessage`,
        {
          chat_id: CONFIG.telegram.chatId,
          text: sections[i],
          parse_mode: "HTML"
        },
        { headers: { "Content-Type": "application/json" } }
      );

      logMessage(`Telegram notification part ${i + 1}/${sections.length} sent successfully`);

      if (i < sections.length - 1) {
        await sleep(500);
      }
    }

    return true;
  } catch (error) {
    const description = error.response?.data?.description || error.message;
    logMessage(`Telegram error: ${description}`);
    return false;
  }
}

async function setupWizard() {
  if (fs.existsSync(CONFIG.configPath)) {
    try {
      const existing = JSON.parse(fs.readFileSync(CONFIG.configPath, "utf8"));
      if (existing.iptorrents?.searchTerm && existing.checkInterval) {
        logMessage("Configuration detected, skipping setup wizard");
        return;
      }
    } catch (error) {
      console.error("Error validating existing config:", error.message);
    }
  }

  const runWizard = (await ask("Configuration found. Run setup wizard? (y/n) [n]: ")).trim().toLowerCase();
  if (runWizard !== "y") {
    return;
  }

  const searchTerm = (await ask(`Enter search term [${CONFIG.iptorrents.searchTerm}]: `)).trim();
  if (searchTerm) {
    CONFIG.iptorrents.searchTerm = searchTerm;
    CONFIG.iptorrents.searchUrl = `https://iptorrents.com/t?q=${encodeURIComponent(CONFIG.iptorrents.searchTerm)}&qf=adv#torrents`;
  }

  const solverUrl = (await ask(`FlareSolverr URL [${CONFIG.solverUrl}]: `)).trim();
  if (solverUrl) {
    CONFIG.solverUrl = solverUrl;
  }

  const timeoutAnswer = (await ask(`Solver timeout in seconds [${Math.round(CONFIG.solverTimeout / 1000)}]: `)).trim();
  const timeoutSeconds = parseInt(timeoutAnswer, 10);
  if (!Number.isNaN(timeoutSeconds) && timeoutSeconds > 0) {
    CONFIG.solverTimeout = timeoutSeconds * 1000;
  }

  const debugAnswer = (await ask("Enable debug mode (saves last HTML)? (y/n) [n]: ")).trim().toLowerCase();
  CONFIG.debug = debugAnswer === "y";

  const telegramAnswer = (await ask("Use Telegram notifications? (y/n) [n]: ")).trim().toLowerCase();
  CONFIG.telegram.enabled = telegramAnswer === "y";
  if (CONFIG.telegram.enabled) {
    const token = (await ask(`Enter bot token [${CONFIG.telegram.botToken}]: `)).trim();
    if (token) CONFIG.telegram.botToken = token;
    const chat = (await ask(`Enter chat id [${CONFIG.telegram.chatId}]: `)).trim();
    if (chat) CONFIG.telegram.chatId = chat;
  }

  const intervalValue = (await ask("Enter check interval value (number) [2]: ")).trim();
  const intervalNumeric = intervalValue ? parseInt(intervalValue, 10) : 2;
  console.log("Select unit: 1. Minutes  2. Hours  3. Days [2]");
  const unitAnswer = (await ask("Unit: ")).trim();

  if (unitAnswer === "1") {
    CONFIG.checkInterval = `*/${intervalNumeric} * * * *`;
  } else if (unitAnswer === "3") {
    CONFIG.checkInterval = `0 0 */${intervalNumeric} * * *`;
  } else {
    CONFIG.checkInterval = `0 */${intervalNumeric} * * *`;
  }

  saveConfig();
}

function processArgs() {
  const args = process.argv.slice(2);
  if (args.includes("--help") || args.includes("-h")) {
    console.log("Usage: node monitor-iptorrents.js [--reset|-r] [--help|-h]");
    process.exit(0);
  }
  if (args.includes("--reset") || args.includes("-r")) {
    console.log("Reset flag detected, removing stored cookies");
    CONFIG.loginComplete = false;
    if (fs.existsSync(CONFIG.cookiesPath)) {
      fs.unlinkSync(CONFIG.cookiesPath);
    }
  }
}

async function scrapeIPTorrents(sendNotificationOnFirstRun = false) {
  logMessage("Starting IPTorrents scrape");
  try {
    const cookies = readCookieFile();
    if ((!cookies || cookies.length === 0) && !(await manualCookieEntry())) {
      throw new Error("Cookie entry failed");
    }

    const result = await fetchTorrents({
      cookiesPath: CONFIG.cookiesPath,
      searchTerm: CONFIG.iptorrents.searchTerm,
      solverUrl: CONFIG.solverUrl,
      timeout: CONFIG.solverTimeout,
      debugPath: CONFIG.debug ? path.join(__dirname, "search-results.html") : undefined
    });

    mergeSolverCookies(result.solverCookies);
    CONFIG.lastUpdateTime = result.fetchedAt;
    saveConfig();

    lastFoundTorrents = postProcessTorrents(result.torrents || []);

    const newCount = lastFoundTorrents.filter(t => t.isNew).length;
    if (newCount > 0) {
      logMessage(`Found ${lastFoundTorrents.length} torrents (${newCount} tagged as new)`);
    } else {
      logMessage(`Found ${lastFoundTorrents.length} torrents`);
    }

    displayTorrentsTable();

    const newTorrents = lastFoundTorrents.filter(isNewTorrent);
    if (newTorrents.length > 0) {
      newTorrents.forEach(addToKnownTorrents);

      if (CONFIG.telegram.enabled && (sendNotificationOnFirstRun || !isFirstRun)) {
        const timestamp = formatDateLA(new Date());
        let body = `<b>IPTorrents: ${newTorrents.length} new torrents found!</b>\n`;
        body += `<b>Search:</b> ${CONFIG.iptorrents.searchTerm}\n`;
        body += `<b>Time:</b> ${timestamp}\n\n`;

        newTorrents.slice(0, 10).forEach((torrent, index) => {
          body += `${index + 1}. <b>${torrent.name}</b>\nSize: ${torrent.size}\nSeeds/Peers: ${torrent.seeders}/${torrent.leechers}\nAdded: ${torrent.added}\n\n`;
        });

        if (newTorrents.length > 10) {
          body += `…and ${newTorrents.length - 10} more`;
        }

        await sendTelegramMessage(body);
      } else {
        logMessage(`Found ${newTorrents.length} new torrents (notification suppressed)`);
      }
    } else {
      logMessage("No new torrents detected");
    }

    return lastFoundTorrents;
  } catch (error) {
    logMessage(`Scrape error: ${error.message}`);
    console.error("Scrape error:", error.message);
    return [];
  }
}

async function main() {
  processArgs();
  loadConfig();
  await setupWizard();
  loadKnownTorrents();

  const sendNotificationOnFirstRun = false;
  await scrapeIPTorrents(sendNotificationOnFirstRun);
  isFirstRun = false;

  cron.schedule(CONFIG.checkInterval, async () => {
    logMessage("Running scheduled check");
    await scrapeIPTorrents();
  });

  displayTorrentsTable();
  logMessage(`Monitor started - checking ${cronToHumanReadable(CONFIG.checkInterval)}`);
}

main();
