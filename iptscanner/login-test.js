const fs = require('fs');
const puppeteer = require('puppeteer');
const path = require('path');

// Debug helper
function debug(msg) {
  console.error('DEBUG: ' + msg);
}

async function testLogin() {
  let browser;
  try {
    debug('Starting login test...');
    // Load cookies
    const cookiesPath = process.env.COOKIES_PATH || path.join(__dirname, 'cookies.json');
    debug('Loading cookies from: ' + cookiesPath);
    
    if (!fs.existsSync(cookiesPath)) {
      console.error(JSON.stringify({ 
        success: false, 
        error: 'Cookies file not found: ' + cookiesPath 
      }));
      process.exit(1);
    }
    
    const cookies = JSON.parse(fs.readFileSync(cookiesPath, 'utf8'));
    debug('Cookies loaded successfully');
    
    // Launch browser with explicit parameters for compatibility
    debug('Launching browser...');
    browser = await puppeteer.launch({
      headless: true,
      args: [
        "--no-sandbox",
        "--disable-setuid-sandbox",
        "--disable-dev-shm-usage",
        "--disable-accelerated-2d-canvas",
        "--disable-gpu"
      ]
    });
    
    debug('Browser launched successfully');
    
    const page = await browser.newPage();
    debug('New page created');
    
    await page.setUserAgent("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36");
    debug('User agent set');
    
    // Set cookies and navigate to site
    debug('Navigating to iptorrents.com...');
    await page.goto("https://iptorrents.com", { 
      waitUntil: "domcontentloaded", 
      timeout: 60000  // Increased timeout to 60 seconds
    });
    
    debug('Setting cookies...');
    await page.setCookie(...cookies);
    debug('Cookies set successfully');
    
    // Navigate to member page and check login status
    debug('Navigating to member page...');
    await page.goto("https://iptorrents.com/t", { 
      waitUntil: "networkidle2", 
      timeout: 60000  // Increased timeout 
    });
    debug('Loaded member page');
    
    // For debugging, save the page content
    const content = await page.content();
    debug('Page content length: ' + content.length);
    
    // Check if we're logged in by looking for logout link
    debug('Checking for user menu or logout link...');
    const userMenu = await page.$('a[href*="/u/"]') || await page.$('a.logout');
    const isLoggedIn = !!userMenu;
    debug('Login status: ' + (isLoggedIn ? 'Logged in' : 'Not logged in'));
    
    console.log(JSON.stringify({ success: isLoggedIn }));
    await browser.close();
    debug('Browser closed');
  } catch (e) {
    debug('Error in testLogin: ' + e.message);
    if (browser) {
      try {
        await browser.close();
        debug('Browser closed after error');
      } catch (closeError) {
        debug('Error closing browser: ' + closeError.message);
      }
    }
    console.error(JSON.stringify({ 
      success: false, 
      error: e.message,
      stack: e.stack
    }));
    process.exit(1);
  }
}

debug('Script started');
testLogin().catch(e => {
  debug('Uncaught error: ' + e.message);
  console.error(JSON.stringify({ 
    success: false, 
    error: 'Uncaught error: ' + e.message,
    stack: e.stack
  }));
  process.exit(1);
});