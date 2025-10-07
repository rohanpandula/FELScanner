#!/usr/bin/env node
const fs = require("fs");
const path = require("path");
const axios = require("axios");
const cron = require("node-cron");
const { exec } = require("child_process");
const puppeteer = require("puppeteer");
const crypto = require("crypto");
const readline = require("readline");

let CONFIG = {
  iptorrents: {
    url: "https://iptorrents.com/login",
    searchUrl: "https://iptorrents.com/t?q=BL%2BEL%2BRPU&qf=adv#torrents",
    searchTerm: "BL+EL+RPU",
    cookiePath: ""
  },
  telegram: {
    enabled: process.env.TELEGRAM_ENABLED === 'true',
    botToken: process.env.TELEGRAM_TOKEN || "",
    chatId: process.env.TELEGRAM_CHAT_ID || ""
  },
  checkInterval: "0 */2 * * *",
  dataPath: path.join(__dirname, "known_torrents.json"),
  configPath: path.join(__dirname, "config.json"),
  cookiesPath: path.join(__dirname, "cookies.json"),
  headless: true,
  debug: false,
  loginComplete: false,
  userDataDir: path.join(__dirname, "browser-profile"),
  lastUpdateTime: null,
  oneTimeRun: false
};

let knownTorrents = new Set();
let lastFoundTorrents = [];

const wait = ms => new Promise(r => setTimeout(r, ms));
const rlInterface = () => readline.createInterface({ input: process.stdin, output: process.stdout });
const ask = q => new Promise(r => { const rl = rlInterface(); rl.question(q, ans => { rl.close(); r(ans) }) });

const loadConfig = () => {
  try {
    if (fs.existsSync(CONFIG.configPath)) {
      let c = JSON.parse(fs.readFileSync(CONFIG.configPath, "utf8"));
      CONFIG = { ...CONFIG, ...c };
      CONFIG.iptorrents.searchUrl = `https://iptorrents.com/t?q=${encodeURIComponent(CONFIG.iptorrents.searchTerm)}&qf=adv#torrents`;
      console.log("Configuration loaded");
    }
  } catch (e) {
    console.error("Config load error:", e.message)
  }
};

const saveConfig = () => {
  try {
    const d = path.dirname(CONFIG.configPath);
    if (!fs.existsSync(d)) fs.mkdirSync(d, { recursive: true });
    fs.writeFileSync(CONFIG.configPath, JSON.stringify(CONFIG, null, 2));
    console.log("Configuration saved")
  } catch (e) {
    console.error("Config save error:", e.message)
  }
};

const loadKnownTorrents = () => {
  try {
    if (fs.existsSync(CONFIG.dataPath)) {
      knownTorrents = new Set(JSON.parse(fs.readFileSync(CONFIG.dataPath, "utf8")));
      console.log(`Loaded ${knownTorrents.size} known torrents`);
      return
    }
  } catch (e) {
    console.error("Load known error:", e.message)
  };
  knownTorrents = new Set();
  fs.writeFileSync(CONFIG.dataPath, JSON.stringify([...knownTorrents]));
};

// Utility function to clean the known torrents list (use if needed to reset)
const cleanupKnownTorrents = async () => {
  console.log(`Before cleanup: ${knownTorrents.size} known torrents`);
  // If you need to completely reset:
  // knownTorrents = new Set();
  // Or if you want to deduplicate, you would do that here
  saveKnownTorrents();
  console.log(`After cleanup: ${knownTorrents.size} known torrents`);
};

const saveKnownTorrents = () => {
  try {
    fs.writeFileSync(CONFIG.dataPath, JSON.stringify([...knownTorrents]));
  } catch (e) {
    console.error("Save known error:", e.message)
  }
};

const loadCookies = async page => {
  if (!fs.existsSync(CONFIG.cookiesPath)) return false;
  try {
    let c = JSON.parse(fs.readFileSync(CONFIG.cookiesPath, "utf8"));
    await page.goto("https://iptorrents.com", { waitUntil: "domcontentloaded", timeout: 30000 });
    await page.setCookie(...c);
    return true
  } catch (e) {
    console.error("Cookies load error:", e.message);
    return false
  }
};

const manualCookieEntry = async () => {
  console.log("Manual cookie entry required. Extract 'uid' and 'pass' cookies from your browser.");
  let uid = await ask('Enter "uid" cookie: ');
  let pass = await ask('Enter "pass" cookie: ');
  if (!uid || !pass) {
    console.log("Both cookies required.");
    return false
  }
  let c = [
    { name: "uid", value: uid, domain: ".iptorrents.com", path: "/", expires: Math.floor(Date.now() / 1000) + 86400 * 30 },
    { name: "pass", value: pass, domain: ".iptorrents.com", path: "/", expires: Math.floor(Date.now() / 1000) + 86400 * 30 }
  ];
  fs.writeFileSync(CONFIG.cookiesPath, JSON.stringify(c));
  console.log("Cookies saved.");
  CONFIG.loginComplete = true;
  return true
};

const checkLoginStatus = async page => {
  await wait(3000);
  let url = page.url();
  if (url.includes("/login") || url.includes("/recover")) {
    console.log("Not logged in.");
    return false
  }
  let userMenu = await page.$('a[href*="/u/"]') || await page.$('a.logout');
  return !!userMenu
};

const navigateToPage = async (page, url, desc) => {
  console.log("Navigating to", desc);
  try {
    await page.goto(url, { waitUntil: "networkidle2", timeout: 60000 });
    await wait(3000);
    if (CONFIG.debug) await page.screenshot({ path: `${desc.replace(/\s+/g, "-").toLowerCase()}.png` });
    return true
  } catch (e) {
    console.error("Error navigating to", desc, e.message);
    return false
  }
};

const buildTorrentIdentifiers = torrent => {
  const rawLink = (torrent.link || "").trim();
  let canonicalLink = rawLink;

  if (canonicalLink && canonicalLink.startsWith("/")) {
    canonicalLink = `https://iptorrents.com${canonicalLink}`;
  }

  const fallbackParts = [
    torrent.name || "",
    torrent.size || "",
    torrent.addedRaw || torrent.added || ""
  ].join("|");

  const primarySource = canonicalLink || fallbackParts;
  const legacySource = torrent.name || "";

  return {
    primary: crypto.createHash("md5").update(primarySource).digest("hex"),
    legacy: crypto.createHash("md5").update(legacySource).digest("hex")
  };
};

const isNewTorrent = torrent => {
  const ids = buildTorrentIdentifiers(torrent);
  return !(knownTorrents.has(ids.primary) || knownTorrents.has(ids.legacy));
};

const addToKnownTorrents = torrent => {
  const ids = buildTorrentIdentifiers(torrent);
  knownTorrents.add(ids.primary);
  if (ids.legacy && ids.legacy !== ids.primary) {
    knownTorrents.add(ids.legacy);
  }
  saveKnownTorrents()
};

const displayTorrentsTable = () => {
  console.clear();
  
  // Print header with styling
  console.log("\n\x1b[1;36m╔═══════════════════════════════════════════════════════════╗\x1b[0m");
  console.log("\x1b[1;36m║               \x1b[1;33mIPTORRENTS MONITOR\x1b[1;36m                         ║\x1b[0m");
  console.log("\x1b[1;36m╚═══════════════════════════════════════════════════════════╝\x1b[0m\n");
  
  console.log(`\x1b[1mSearch Term:\x1b[0m ${CONFIG.iptorrents.searchTerm}`);
  console.log(`\x1b[1mLast Check:\x1b[0m  ${CONFIG.lastUpdateTime ? formatDateLA(CONFIG.lastUpdateTime) : "Never"}`);
  console.log(`\x1b[1mSchedule:\x1b[0m    ${cronToHumanReadable(CONFIG.checkInterval)}`);
  console.log(`\x1b[1mTelegram:\x1b[0m    ${CONFIG.telegram.enabled ? '\x1b[32mEnabled\x1b[0m' : '\x1b[31mDisabled\x1b[0m'}`);
  
  let disp = lastFoundTorrents.slice(0, 12);
  if (disp.length === 0) {
    console.log("\n\x1b[33mNo torrents found.\x1b[0m");
    return;
  }
  
  // Print a header for the table
  console.log("\n\x1b[1;36m╔════╦══════════════════════════════════════════════╦═══════════╦═══════════╦══════════════╗\x1b[0m");
  console.log("\x1b[1;36m║\x1b[1;33m #  \x1b[1;36m║\x1b[1;33m Title                                       \x1b[1;36m║\x1b[1;33m Size      \x1b[1;36m║\x1b[1;33m S / L     \x1b[1;36m║\x1b[1;33m Added        \x1b[1;36m║\x1b[0m");
  console.log("\x1b[1;36m╠════╬══════════════════════════════════════════════╬═══════════╬═══════════╬══════════════╣\x1b[0m");
  
  disp.forEach((t, i) => {
    // Format name to fit in the table (46 chars)
    let n = t.name.length > 46 ? t.name.substring(0, 43) + "..." : t.name.padEnd(46);
    
    // Format size to be consistent width
    let size = t.size.padEnd(9);
    
    // Format seeds/peers ratio
    let seedColor = t.seeders > 20 ? "\x1b[32m" : t.seeders > 5 ? "\x1b[33m" : "\x1b[31m";
    let leechColor = t.leechers > 10 ? "\x1b[31m" : "\x1b[90m";
    
    let ratio = `${seedColor}${String(t.seeders).padStart(3)}\x1b[0m / ${leechColor}${String(t.leechers).padStart(3)}\x1b[0m`;
    
    // Special formatting for "New" torrents
    let rowStart = t.isNew ? "\x1b[1;32m" : "\x1b[1;36m";
    let titleColor = t.isNew ? "\x1b[1;92m" : "\x1b[0m";
    let newTag = t.isNew ? " \x1b[1;33m[NEW]\x1b[0m" : "";
    
    // Format added date
    let added = t.added.padEnd(12);
    
    console.log(`${rowStart}║\x1b[1;33m ${(i + 1).toString().padStart(2)} \x1b[1;36m║${titleColor} ${n} \x1b[1;36m║\x1b[0m ${size} \x1b[1;36m║\x1b[0m ${ratio} \x1b[1;36m║\x1b[0m ${added}${newTag} \x1b[1;36m║\x1b[0m`);
  });
  
  console.log("\x1b[1;36m╚════╩══════════════════════════════════════════════╩═══════════╩═══════════╩══════════════╝\x1b[0m\n");
  
  // Display message log
  if (messageLog.length > 0) {
    console.log("\x1b[1;36m╔═══════════════════════════════════════════════════════════╗\x1b[0m");
    console.log("\x1b[1;36m║                    \x1b[1;33mACTIVITY LOG\x1b[1;36m                         ║\x1b[0m");
    console.log("\x1b[1;36m╚═══════════════════════════════════════════════════════════╝\x1b[0m\n");
    
    // Show the most recent 5 messages
    const recentMessages = messageLog.slice(-5);
    recentMessages.forEach(msg => {
      console.log(`  ${msg}`);
    });
    console.log("");
  }
  
  console.log("\x1b[90mPress Ctrl+C to exit\x1b[0m\n");
};

const sendTelegramMessage = async msg => {
  // Use environment variables if available
  const telegramEnabled = process.env.TELEGRAM_ENABLED === 'true' || CONFIG.telegram.enabled;
  const telegramToken = process.env.TELEGRAM_TOKEN || CONFIG.telegram.botToken;
  const telegramChatId = process.env.TELEGRAM_CHAT_ID || CONFIG.telegram.chatId;
  
  if (!telegramEnabled || !telegramToken || telegramToken === "YOUR_BOT_TOKEN") return;
  try {
    // Split long messages to avoid Telegram's length limit
    const MAX_LENGTH = 4000;
    let messageParts = [];
    
    if (msg.length <= MAX_LENGTH) {
      messageParts = [msg];
    } else {
      // First part has the header
      let header = msg.split('\n\n')[0] + '\n\n';
      let items = msg.slice(header.length).split('\n\n');
      
      let currentPart = header;
      for (const item of items) {
        if (currentPart.length + item.length + 2 > MAX_LENGTH) {
          messageParts.push(currentPart);
          currentPart = `${header}(Continued)\n\n${item}\n\n`;
        } else {
          currentPart += item + '\n\n';
        }
      }
      if (currentPart.length > 0) {
        messageParts.push(currentPart);
      }
    }
    
    // Send each part
    for (let i = 0; i < messageParts.length; i++) {
      const response = await axios.post(
        `https://api.telegram.org/bot${telegramToken}/sendMessage`,
        {
          chat_id: telegramChatId,
          text: messageParts[i],
          parse_mode: "HTML"
        },
        {
          headers: {
            'Content-Type': 'application/json'
          }
        }
      );
      
      // Log the success message
      logMessage(`Telegram notification part ${i+1}/${messageParts.length} sent successfully`);
      
      // Add a small delay between messages to avoid rate limiting
      if (i < messageParts.length - 1) {
        await wait(500);
      }
    }
    
    return true;
  } catch (e) {
    const errorMessage = e.response?.data?.description || e.message;
    logMessage(`Telegram error: ${errorMessage}`);
    return false;
  }
};

// Skip wizard if configuration already exists and is valid
const setupWizard = async () => {
  // Skip wizard if configuration exists and looks valid
  if (fs.existsSync(CONFIG.configPath)) {
    try {
      const config = JSON.parse(fs.readFileSync(CONFIG.configPath, "utf8"));
      if (config.iptorrents && config.iptorrents.searchTerm && config.checkInterval) {
        // Configuration looks valid, skip wizard
        logMessage("Configuration loaded, skipping setup wizard");
        return;
      }
    } catch (e) {
      // If there's an error reading config, proceed with wizard
      console.error("Error validating config:", e.message);
    }
  }
  
  let ans = await ask("Configuration found. Run setup wizard? (y/n) [n]: ");
  if (ans.toLowerCase() === "y") {
    let st = await ask(`Enter search term [${CONFIG.iptorrents.searchTerm}]: `);
    if (st.trim()) CONFIG.iptorrents.searchTerm = st;
    CONFIG.iptorrents.searchUrl = `https://iptorrents.com/t?q=${encodeURIComponent(CONFIG.iptorrents.searchTerm)}&qf=adv#torrents`;
    
    let head = await ask("Run in headless mode? (y/n) [y]: ");
    CONFIG.headless = head.toLowerCase() === "n" ? false : true;
    
    let deb = await ask("Enable debug mode? (y/n) [n]: ");
    CONFIG.debug = deb.toLowerCase() === "y";
    
    let tel = await ask("Use Telegram notifications? (y/n) [n]: ");
    CONFIG.telegram.enabled = tel.toLowerCase() === "y";
    
    if (CONFIG.telegram.enabled) {
      let token = await ask(`Enter bot token [${CONFIG.telegram.botToken}]: `);
      if (token.trim()) CONFIG.telegram.botToken = token;
      
      let chat = await ask(`Enter chat id [${CONFIG.telegram.chatId}]: `);
      if (chat.trim()) CONFIG.telegram.chatId = chat;
    }
    
    let interval = await ask("Enter check interval value (number) [2]: ");
    let intVal = interval.trim() ? parseInt(interval) : 2;
    
    console.log("Select unit: 1. Minutes 2. Hours 3. Days [2]: ");
    let unit = await ask("Unit: ");
    unit = unit.trim() === "1" ? "minutes" : unit.trim() === "3" ? "days" : "hours";
    
    CONFIG.checkInterval = unit === "minutes" ? `*/${intVal} * * * *` : unit === "days" ? `0 0 */${intVal} * * *` : `0 */${intVal} * * *`;
    saveConfig()
  }
};

const processArgs = () => {
  const args = process.argv.slice(2);
  
  if (args.includes("--reset") || args.includes("-r")) {
    console.log("Resetting known torrents. All torrents will appear as new on next check.");
    if (fs.existsSync(CONFIG.dataPath)) fs.unlinkSync(CONFIG.dataPath);
    process.exit(0)
  }
  
  if (args.includes("--help") || args.includes("-h")) {
    console.log("Usage: node monitor-iptorrents.js [--reset|-r] [--help|-h] [--config <path>] [--one-time]");
    console.log("  --reset, -r      : Reset the known torrents database");
    console.log("  --help, -h       : Show this help message");
    console.log("  --config <path>  : Use the specified config file");
    console.log("  --one-time       : Run once and exit (don't schedule future checks)");
    process.exit(0)
  }
  
  // Check for config file path
  const configIndex = args.indexOf("--config");
  if (configIndex !== -1 && configIndex + 1 < args.length) {
    CONFIG.configPath = args[configIndex + 1];
    console.log(`Using config file: ${CONFIG.configPath}`);
  }
  
  // Check for one-time run flag
  CONFIG.oneTimeRun = args.includes("--one-time");
  if (CONFIG.oneTimeRun) {
    console.log("Running in one-time mode (will exit after scan)");
  }
};

// Format date in Los Angeles timezone
const formatDateLA = (date) => {
  return new Date(date).toLocaleString('en-US', {
    timeZone: 'America/Los_Angeles',
    month: 'short',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
    hour12: true
  });
};

// Helper to convert cron schedule to human readable text
const cronToHumanReadable = (cronExpression) => {
  const parts = cronExpression.split(' ');
  
  // Handle "0 */2 * * *" format (every 2 hours)
  if (parts[0] === '0' && parts[1].startsWith('*/')) {
    const hours = parseInt(parts[1].substring(2));
    return `Every ${hours} hour${hours > 1 ? 's' : ''}`;
  }
  
  // Default fallback for other schedules
  return "Custom schedule"; 
};

// Keep a log of messages/events for display
const messageLog = [];
const logMessage = (message) => {
  const timestamp = formatDateLA(new Date());
  messageLog.push(`[${timestamp}] ${message}`);
  // Limit log size to avoid memory issues
  if (messageLog.length > 100) {
    messageLog.shift();
  }
};

const scrapeIPTorrents = async (sendNotificationOnFirstRun = false) => {
  logMessage("Starting IPTorrents scrape");
  let browser;
  try {
    browser = await puppeteer.launch({
      headless: CONFIG.headless ? 'new' : false, // Use new headless mode
      userDataDir: CONFIG.userDataDir,
      args: ["--no-sandbox", "--disable-setuid-sandbox", "--window-size=1920,1080"],
      defaultViewport: { width: 1920, height: 1080 }
    });
    
    const page = await browser.newPage();
    await page.setUserAgent("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36");
    
    await loadCookies(page);
    
    if (!await navigateToPage(page, "https://iptorrents.com", "Main page"))
      throw new Error("Main page load failed");
      
    if (!await checkLoginStatus(page)) {
      console.log("Not logged in. Attempting manual cookie entry.");
      await browser.close();
      if (!await manualCookieEntry())
        throw new Error("Cookie entry failed");
      return []
    }
    
    if (!await navigateToPage(page, CONFIG.iptorrents.searchUrl, "Search results"))
      throw new Error("Search page load failed");
      
    logMessage("Loaded search results page");
    await wait(5000);
    
    // Wait for torrents table with longer timeout
    await page.waitForSelector("table#torrents", { timeout: 30000 })
      .catch(() => console.log("Timed out waiting for torrent table"));
      
    if (CONFIG.debug)
      await page.screenshot({ path: "search-results.png", fullPage: true });
    
    // Improved selector to get all torrent rows
    const torrents = await page.evaluate(() => {
      const results = [];
      const rows = document.querySelectorAll("table#torrents > tbody > tr");
      
      rows.forEach(row => {
        // Skip header rows
        if (row.classList.contains("head") || row.classList.contains("header"))
          return;
          
        const cells = row.querySelectorAll("td");
        if (cells.length < 8) return; // Ensure we have enough cells
        
        // Get torrent name from the link
        const nameCell = cells[1]; // Second column contains the name
        const linkElem = nameCell.querySelector("a[href^='/t/']");
        const name = linkElem ? linkElem.textContent.trim() : "Unknown";
        const link = linkElem ? linkElem.href : "";
        
        // Check if this torrent has the "New" tag
        const hasNewTag = nameCell.querySelector("span.tag") !== null;
        
        // Get added date - it's in the format "rating year genre | X hours ago by uploader" 
        const subDiv = nameCell.querySelector(".sub");
        let added = "Unknown";
        let addedRaw = ""; // Raw date string for parsing
        
        if (subDiv) {
          const subText = subDiv.textContent.trim();
          // The date is after the pipe character
          if (subText.includes(" | ")) {
            addedRaw = subText.split(" | ")[1].trim();
            added = addedRaw;
          } else {
            addedRaw = subText.trim();
            added = addedRaw;
          }
        }
        
        // Get size, seeders, leechers from their specific columns
        const size = cells[5].textContent.trim(); // Size column
        const seeders = parseInt(cells[7].textContent.trim()) || 0; // Seeders column
        const leechers = parseInt(cells[8].textContent.trim()) || 0; // Leechers column
        
        // Add to results
        results.push({
          name: name,
          link: link,
          size: size,
          seeders: seeders,
          leechers: leechers,
          added: added,
          addedRaw: addedRaw, // Store raw date for better parsing
          isNew: hasNewTag
        });
      });
      
      return results;
    });

    CONFIG.lastUpdateTime = new Date().toISOString();
    
    // Sort torrents by added date (newest first)
    // Convert the text date to a sortable value and make it human-readable
    torrents.forEach(t => {
      const addedText = t.added;
      let timeValue = 0;
      let relativeDate = "";
      
      // Handle multiple formats like "1.8 hours ago by Lama" or "1.1 days ago"
      // Extract just the time part without the uploader
      let timePart = addedText;
      if (addedText.includes(" by ")) {
        timePart = addedText.split(" by ")[0].trim();
      }
      
      // Process the time part
      if (timePart.includes('mins ago') || timePart.includes('minutes ago') || timePart.includes('min ago')) {
        const mins = parseFloat(timePart.split(' ')[0]);
        timeValue = Date.now() - (mins * 60 * 1000);
        relativeDate = `${mins.toFixed(0)} min ago`;
      } else if (timePart.includes('hours ago') || timePart.includes('hour ago')) {
        const hours = parseFloat(timePart.split(' ')[0]);
        timeValue = Date.now() - (hours * 60 * 60 * 1000);
        relativeDate = `${hours.toFixed(1)} hr ago`;
      } else if (timePart.includes('days ago') || timePart.includes('day ago')) {
        const days = parseFloat(timePart.split(' ')[0]);
        timeValue = Date.now() - (days * 24 * 60 * 60 * 1000);
        relativeDate = `${days.toFixed(1)} day ago`;
      } else if (timePart.includes('weeks ago') || timePart.includes('week ago')) {
        const weeks = parseFloat(timePart.split(' ')[0]);
        timeValue = Date.now() - (weeks * 7 * 24 * 60 * 60 * 1000);
        relativeDate = `${weeks.toFixed(1)} wk ago`;
      } else {
        // If we can't parse it, just use the original
        relativeDate = timePart;
        // Default to a very old time so it sorts at the bottom
        timeValue = 0;
      }
      
      // Store both the human-readable date and numeric timestamp for sorting
      t.added = relativeDate;
      t.sortTime = timeValue;
      
      // Debug sorting values 
      if (CONFIG.debug) {
        console.log(`Parsed time: "${timePart}" -> ${relativeDate} (sortTime: ${timeValue})`);
      }
    });
    
    // Sort torrents by the calculated time (newest first)
    // With "New" tag torrents at the top
    torrents.sort((a, b) => {
      // First prioritize torrents with the "New" tag
      if (a.isNew && !b.isNew) return -1;
      if (!a.isNew && b.isNew) return 1;
      
      // Compare actual upload times - lower timeValue means more recent
      // If sortTime isn't available, fallback to Date.now() - this can happen on first run
      const aTime = a.sortTime || Date.now();
      const bTime = b.sortTime || Date.now();
      
      // Sort newest first (higher number = more recent = should come first)
      return bTime - aTime;
    });
    
    lastFoundTorrents = torrents;
    
    // Log some statistics about what we found
    const newCount = torrents.filter(t => t.isNew).length;
    if (newCount > 0) {
      logMessage(`Found ${torrents.length} torrents (${newCount} with "New" tag)`);
    } else {
      logMessage(`Found ${torrents.length} torrents (sorted by upload time)`);
    }
    
    displayTorrentsTable();

    // Find only genuinely new torrents by checking against our tracking database
    const newTorrents = torrents.filter(isNewTorrent);
    console.log("New torrents:", newTorrents.length);

    if (newTorrents.length > 0) {
      newTorrents.forEach(addToKnownTorrents);
      
      // Only send Telegram notification on regular runs (not on first launch)
      // unless specifically requested
      if (sendNotificationOnFirstRun || !isFirstRun) {
        const currentTimeLA = formatDateLA(new Date());
        let msg = `<b>IPTorrents: ${newTorrents.length} new torrents found!</b>\n<b>Search:</b> ${CONFIG.iptorrents.searchTerm}\n<b>Time:</b> ${currentTimeLA}\n\n`;
        
        newTorrents.forEach((t, i) => {
          msg += `${i + 1}. <b>${t.name}</b>\nSize: ${t.size}\nSeeds/Peers: ${t.seeders}/${t.leechers}\nAdded: ${t.added}\n\n`;
        });
        
        const sent = await sendTelegramMessage(msg);
        if (sent) {
          logMessage(`Notified about ${newTorrents.length} new torrents`);
        }
      } else {
        logMessage(`Found ${newTorrents.length} new torrents (notification suppressed on first run)`);
      }
    }
    
    await browser.close();
    return torrents;
  } catch (e) {
    if (browser) await browser.close();
    console.error("Scrape error:", e.message);
    return [];
  }
};

// Add a global flag to track first run state
let isFirstRun = true;

const main = async () => {
  processArgs();
  loadConfig();
  await setupWizard();
  loadKnownTorrents();
  
  // First run, don't send notifications unless explicitly requested
  const sendNotificationOnFirstRun = false; // Set to true if you want notifications on first run
  const torrents = await scrapeIPTorrents(sendNotificationOnFirstRun);
  
  // After first run is complete
  isFirstRun = false;
  
  // If one-time run was requested, exit now
  if (CONFIG.oneTimeRun) {
    console.log("One-time run completed, exiting");
    displayTorrentsTable();
    // Write the torrents to the dataPath for the Python script to read
    fs.writeFileSync(CONFIG.dataPath, JSON.stringify(torrents, null, 2));
    process.exit(0);
  }
  
  cron.schedule(CONFIG.checkInterval, async () => {
    logMessage(`Running scheduled check`);
    await scrapeIPTorrents();
  });
  
  // Show initial display
  displayTorrentsTable();
  
  logMessage(`Monitor started - checking ${cronToHumanReadable(CONFIG.checkInterval)}`);
};

main();
