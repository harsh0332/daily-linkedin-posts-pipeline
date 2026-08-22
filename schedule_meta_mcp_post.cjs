const puppeteer = require('puppeteer-core');
const fs = require('fs');
const path = require('path');

function delay(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

async function findShadowElement(page, selectorFn, arg) {
  return await page.evaluateHandle((fnStr, argVal) => {
    const fn = eval('(' + fnStr + ')');
    function search(root) {
      const el = fn(root, argVal);
      if (el) return el;
      const walker = document.createTreeWalker(root, NodeFilter.SHOW_ELEMENT, null, false);
      let node;
      while (node = walker.nextNode()) {
        if (node.shadowRoot) {
          const res = search(node.shadowRoot);
          if (res) return res;
        }
      }
      return null;
    }
    return search(document.body);
  }, selectorFn.toString(), arg);
}

async function clickNativelyShadow(page, selectorFn, arg) {
  const handle = await findShadowElement(page, selectorFn, arg);
  const element = handle.asElement();
  if (!element) return false;

  const info = await page.evaluate(el => {
    if (!el) return null;
    const rect = el.getBoundingClientRect();
    return {
      x: rect.left + rect.width / 2,
      y: rect.top + rect.height / 2,
      width: rect.width,
      height: rect.height,
      tagName: el.tagName,
      className: el.className,
      text: el.innerText ? el.innerText.trim().substring(0, 30) : ''
    };
  }, element);

  if (!info || info.width === 0 || info.height === 0) {
    await handle.dispose();
    return false;
  }

  console.log(`clickNativelyShadow: Found <${info.tagName} class="${info.className}" text="${info.text}">`);

  try {
    await element.scrollIntoViewIfNeeded();
    await delay(300);
    await page.mouse.click(info.x, info.y);
    await handle.dispose();
    return true;
  } catch (err) {
    console.log(`Fallback event dispatch: ${err.message}`);
    try {
      const clicked = await page.evaluate(el => {
        if (!el) return false;
        el.focus();
        const opts = { bubbles: true, cancelable: true, view: window };
        el.dispatchEvent(new MouseEvent('pointerdown', opts));
        el.dispatchEvent(new MouseEvent('mousedown', opts));
        el.dispatchEvent(new MouseEvent('pointerup', opts));
        el.dispatchEvent(new MouseEvent('mouseup', opts));
        el.click();
        return true;
      }, element);
      await handle.dispose();
      return clicked;
    } catch (e) {
      await handle.dispose();
      return false;
    }
  }
}

async function waitForSelectorShadow(page, selector, timeout = 15000) {
  const startTime = Date.now();
  while (Date.now() - startTime < timeout) {
    const handle = await findShadowElement(page, (root, sel) => root.querySelector(sel), selector);
    if (handle && handle.asElement()) return handle;
    if (handle) await handle.dispose();
    await delay(500);
  }
  throw new Error(`Timeout waiting for selector: ${selector}`);
}

async function getElementShadow(page, selector) {
  const handle = await findShadowElement(page, (root, sel) => root.querySelector(sel), selector);
  if (handle && handle.asElement()) return handle.asElement();
  if (handle) await handle.dispose();
  return null;
}

async function fillFieldShadow(page, selector, value) {
  const el = await getElementShadow(page, selector);
  if (!el) throw new Error(`Could not find element to fill: ${selector}`);
  
  await page.evaluate((input) => {
    input.focus();
    input.select();
  }, el);
  
  await delay(500);
  await page.keyboard.press('Backspace');
  await delay(500);
  await page.keyboard.type(value);
  await page.keyboard.press('Enter');
  await delay(200);
  await page.keyboard.press('Escape');
  await delay(200);
  await page.keyboard.press('Tab');
  await el.dispose();
  await delay(1000);
}

async function fillTimeComboboxShadow(page, selector, value) {
  const el = await getElementShadow(page, selector);
  if (!el) throw new Error(`Could not find combobox element to fill: ${selector}`);
  
  await page.evaluate((input) => {
    input.focus();
    input.select();
  }, el);
  
  await delay(500);
  await page.keyboard.press('Backspace');
  await delay(500);
  await page.keyboard.type(value);
  console.log(`Typed ${value} into time combobox...`);
  await delay(1500);
  
  await page.keyboard.press('ArrowDown');
  await delay(500);
  await page.keyboard.press('Enter');
  await el.dispose();
  await delay(1000);
}

async function fillEditorText(page, text) {
  console.log("Filling post caption text into .ql-editor...");
  const editorHandle = await findShadowElement(page, (root) => {
    return root.querySelector('.ql-editor') || root.querySelector('div[contenteditable="true"]');
  });
  
  const editor = editorHandle.asElement();
  if (!editor) throw new Error("Could not find post content editor element");

  await page.evaluate(el => {
    el.focus();
    el.innerHTML = '';
  }, editor);

  const lines = text.split('\n');
  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    if (line.length > 0) {
      await page.keyboard.type(line, { delay: 1 });
    }
    if (i < lines.length - 1) {
      await page.keyboard.down('Shift');
      await page.keyboard.press('Enter');
      await page.keyboard.up('Shift');
    }
  }
  await editorHandle.dispose();
  await delay(1000);
}

(async () => {
  const userDataDir = path.join(__dirname, 'chrome-session');
  console.log("Launching browser with saved session...");

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

    console.log("Navigating to LinkedIn feed...");
    await page.goto('https://www.linkedin.com/feed/', { waitUntil: 'domcontentloaded', timeout: 30000 });
    await delay(4000);

    // Hide messaging overlays
    await page.evaluate(() => {
      const style = document.createElement('style');
      style.innerHTML = `.msg-overlay-container, [class*="msg-overlay"], #msg-overlay { display: none !important; }`;
      document.head.appendChild(style);
    });

    console.log("Opening 'Start a post' modal...");
    const clickStartPost = await clickNativelyShadow(page, (root) => {
      return Array.from(root.querySelectorAll('*')).find(
        el => (el.tagName === 'BUTTON' || el.getAttribute('role') === 'button' || el.getAttribute('aria-label') === 'Start a post') &&
              el.innerText && el.innerText.trim().includes('Start a post')
      );
    });
    if (!clickStartPost) throw new Error("Could not find 'Start a post' button");

    const editorSelector = '.ql-editor, [contenteditable="true"]';
    await waitForSelectorShadow(page, editorSelector, 15000);
    await delay(1500);

    // Fill caption text
    const captionText = fs.readFileSync(path.join(__dirname, 'meta_mcp_post.txt'), 'utf8');
    await fillEditorText(page, captionText);

    // Open Schedule Modal
    console.log("Opening Schedule Settings modal (clicking clock icon)...");
    const clickedScheduleIcon = await clickNativelyShadow(page, (root) => {
      const modal = root.querySelector('.share-box, .artdeco-modal, [role="dialog"]');
      const container = modal || root;
      const buttons = Array.from(container.querySelectorAll('button'));
      const postBtn = buttons.find(b => b.innerText && b.innerText.trim() === 'Post');
      if (postBtn && postBtn.previousElementSibling) {
        return postBtn.previousElementSibling;
      }
      return buttons.find(b => b.ariaLabel && b.ariaLabel.includes('Schedule'));
    });
    if (!clickedScheduleIcon) throw new Error("Could not click Schedule clock icon");
    await delay(3000);

    // Set Date & Time for July 26, 2026 at 7:00 AM
    const targetDate = "07/26/2026";
    const targetTime = "7:00 AM";
    console.log(`Setting schedule: Date=${targetDate}, Time=${targetTime}`);

    await fillFieldShadow(page, 'input[placeholder*="Date"], input[aria-label*="date"], input[id*="date"]', targetDate);
    await fillTimeComboboxShadow(page, 'input[placeholder*="Time"], input[aria-label*="time"], input[id*="time"], input[role="combobox"]', targetTime);

    // Click Next
    console.log("Saving schedule settings (clicking Next)...");
    const clickedNext = await clickNativelyShadow(page, (root) => {
      return Array.from(root.querySelectorAll('button')).find(
        b => b.innerText && b.innerText.trim() === 'Next'
      );
    });
    if (!clickedNext) throw new Error("Could not click Next in schedule modal");
    await delay(3000);

    // Click final Schedule button
    console.log("Clicking final 'Schedule' button...");
    const clickedScheduleFinal = await clickNativelyShadow(page, (root) => {
      return Array.from(root.querySelectorAll('button')).find(
        b => b.innerText && b.innerText.trim() === 'Schedule'
      );
    });
    if (!clickedScheduleFinal) throw new Error("Could not find final 'Schedule' button in composer modal");

    console.log("Waiting 6s for scheduling process to complete...");
    await delay(6000);

    console.log("🎉 META ADS MCP SERVER POST SCHEDULED SUCCESSFULLY FOR 7:00 AM!");
    await browser.close();
    process.exit(0);

  } catch (err) {
    console.error("Automator Exception:", err);
    if (browser) await browser.close();
    process.exit(1);
  }
})();
