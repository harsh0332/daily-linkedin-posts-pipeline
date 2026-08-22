const puppeteer = require('puppeteer-core');
const path = require('path');

function delay(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

(async () => {
  const userDataDir = path.join(__dirname, 'chrome-session');
  console.log("Launching browser to delete the recent post...");

  const browser = await puppeteer.launch({
    executablePath: "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    headless: false,
    userDataDir: userDataDir,
    args: [
      '--no-sandbox',
      '--disable-setuid-sandbox',
      '--disable-gpu',
      '--disable-dev-shm-usage',
      '--use-mock-keychain',
      '--password-store=basic',
      '--window-size=1280,1200',
      '--disable-extensions',
      '--disable-component-update',
      '--no-default-browser-check'
    ]
  });

  try {
    const pages = await browser.pages();
    const page = pages[0] || await browser.newPage();
    await page.setViewport({ width: 1280, height: 1200 });

    console.log("Navigating to LinkedIn recent activity page...");
    await page.goto('https://www.linkedin.com/in/harshchouksey/recent-activity/all/', { waitUntil: 'domcontentloaded', timeout: 30000 });
    await delay(4000);

    // Hide messaging overlays
    await page.evaluate(() => {
      const style = document.createElement('style');
      style.innerHTML = `.msg-overlay-container, [class*="msg-overlay"], #msg-overlay { display: none !important; }`;
      document.head.appendChild(style);
    });

    console.log("Looking for top post control options (...)");
    const clickedMenu = await page.evaluate(() => {
      const allButtons = Array.from(document.querySelectorAll('button'));
      const menuBtn = allButtons.find(b => {
        const aria = (b.getAttribute('aria-label') || '').toLowerCase();
        const txt = (b.innerText || '').trim();
        return (aria.includes('control menu') || aria.includes('option') || aria.includes('more options') || txt === '…' || txt === '...') && b.offsetWidth > 0;
      });
      if (menuBtn) {
        menuBtn.click();
        return true;
      }
      return false;
    });

    if (!clickedMenu) {
      console.log("Retrying menu button search on feed...");
      await page.goto('https://www.linkedin.com/feed/', { waitUntil: 'domcontentloaded', timeout: 30000 });
      await delay(4000);
      await page.evaluate(() => {
        const allButtons = Array.from(document.querySelectorAll('button'));
        const menuBtn = allButtons.find(b => {
          const aria = (b.getAttribute('aria-label') || '').toLowerCase();
          return aria.includes('option menu') || aria.includes('control menu');
        });
        if (menuBtn) menuBtn.click();
      });
    }

    await delay(2000);

    console.log("Clicking 'Delete post' option...");
    const clickedDeleteOption = await page.evaluate(() => {
      const allItems = Array.from(document.querySelectorAll('div, li, button, span'));
      const delItem = allItems.find(el => {
        const txt = (el.innerText || '').trim();
        return (txt === 'Delete post' || txt.includes('Delete post') || txt === 'Delete') && el.offsetWidth > 0;
      });
      if (delItem) {
        delItem.click();
        return true;
      }
      return false;
    });

    if (!clickedDeleteOption) throw new Error("Could not find 'Delete post' option in menu");
    await delay(2000);

    console.log("Confirming post deletion...");
    const clickedConfirmDelete = await page.evaluate(() => {
      const allBtns = Array.from(document.querySelectorAll('button'));
      const confirmBtn = allBtns.find(b => {
        const txt = (b.innerText || '').trim();
        const isPrimary = b.className && (b.className.includes('primary') || b.className.includes('artdeco-button--primary'));
        return (txt === 'Delete' || txt.includes('Delete')) && isPrimary;
      });
      if (confirmBtn) {
        confirmBtn.click();
        return true;
      }
      return false;
    });

    if (!clickedConfirmDelete) throw new Error("Could not click Delete on confirmation modal");

    await delay(4000);
    console.log("✅ POST DELETED SUCCESSFULLY FROM LINKEDIN!");
    await browser.close();
    process.exit(0);

  } catch (err) {
    console.error("Delete script error:", err.message);
    if (browser) await browser.close();
    process.exit(1);
  }
})();
