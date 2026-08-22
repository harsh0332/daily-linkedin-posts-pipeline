const puppeteer = require('puppeteer');
const path = require('path');
const readline = require('readline');

(async () => {
  console.log("Launching Chrome for LinkedIn Login...");
  try {
    const browser = await puppeteer.launch({
      headless: false,
      userDataDir: path.join(__dirname, 'chrome-session'),
      defaultViewport: null,
      args: ['--start-maximized']
    });
    
    const pages = await browser.pages();
    const page = pages[0] || await browser.newPage();
    
    await page.goto('https://www.linkedin.com/login', { waitUntil: 'networkidle2' });
    console.log("\n====================================================================");
    console.log("Browser window has opened. Please login manually in the browser.");
    console.log("If 2FA / verification code is requested, enter it in the browser.");
    console.log("Once logged in and showing your LinkedIn feed, return here.");
    console.log("====================================================================\n");
    console.log("Press [ENTER] in this terminal once you are logged in to save and exit...");

    const rl = readline.createInterface({
      input: process.stdin,
      output: process.stdout
    });

    rl.question('', async () => {
      console.log("Saving session and closing browser...");
      await browser.close();
      rl.close();
      console.log("LinkedIn session saved successfully in './chrome-session'!");
      process.exit(0);
    });
  } catch (err) {
    console.error("Failed to launch browser:", err);
    process.exit(1);
  }
})();
