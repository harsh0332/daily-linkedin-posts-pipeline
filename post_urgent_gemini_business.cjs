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
  if (!element) {
    return false;
  }
  
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
    console.log(`Fallback event dispatch for click: ${err.message}`);
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
    } catch (evalErr) {
      await handle.dispose();
      return false;
    }
  }
}

async function waitForSelectorShadow(page, selector, timeout = 15000) {
  const startTime = Date.now();
  while (Date.now() - startTime < timeout) {
    const handle = await findShadowElement(page, (root, sel) => root.querySelector(sel), selector);
    if (handle && handle.asElement()) {
      return handle;
    }
    if (handle) await handle.dispose();
    await delay(500);
  }
  throw new Error(`Timeout waiting for shadow selector: ${selector}`);
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

    // Click 'Add a document' button
    console.log("Clicking 'Add a document' button...");
    let clickedDoc = await clickNativelyShadow(page, (root) => {
      const btns = Array.from(root.querySelectorAll('button'));
      return btns.find(b => b.ariaLabel && b.ariaLabel.includes('Add a document')) ||
             btns.find(b => b.innerText && b.innerText.includes('Add a document')) ||
             btns.find(b => b.innerText && b.innerText.includes('document'));
    });

    if (!clickedDoc) {
      console.log("Clicking 'More' button to expose document button...");
      await clickNativelyShadow(page, (root) => {
        return Array.from(root.querySelectorAll('button')).find(
          b => (b.ariaLabel && b.ariaLabel.includes('More')) || (b.innerText && b.innerText.includes('More'))
        );
      });
      await delay(1500);

      clickedDoc = await clickNativelyShadow(page, (root) => {
        const btns = Array.from(root.querySelectorAll('button'));
        return btns.find(b => b.ariaLabel && b.ariaLabel.includes('Add a document')) ||
               btns.find(b => b.innerText && b.innerText.includes('Add a document')) ||
               btns.find(b => b.innerText && b.innerText.includes('document'));
      });
    }

    if (!clickedDoc) throw new Error("Could not find 'Add a document' button");
    await delay(2000);

    // Upload Carousel PDF
    const pdfPath = path.resolve(__dirname, 'gemini_business_carousel.pdf');
    console.log("Uploading Carousel PDF:", pdfPath);

    const fileInputHandle = await page.evaluateHandle(() => {
      function findFileInput(root) {
        const walker = document.createTreeWalker(root, NodeFilter.SHOW_ELEMENT, null, false);
        let node;
        while (node = walker.nextNode()) {
          if (node.tagName === 'INPUT' && node.type === 'file') return node;
          if (node.shadowRoot) {
            const found = findFileInput(node.shadowRoot);
            if (found) return found;
          }
        }
        return null;
      }
      return findFileInput(document.body);
    });

    if (!fileInputHandle) throw new Error("Could not find file input element");
    const fileInput = fileInputHandle.asElement();
    await fileInput.uploadFile(pdfPath);
    console.log("Uploaded Carousel PDF! Waiting 4s for document modal...");
    await delay(4000);

    // Type document title
    console.log("Typing document title...");
    const titleInputHandle = await findShadowElement(page, (root) => {
      return root.querySelector('input.document-title-form__title-input') ||
             root.querySelector('input[placeholder*="title to your document"]') ||
             root.querySelector('input[placeholder*="document"]');
    });

    if (titleInputHandle && titleInputHandle.asElement()) {
      const titleInput = titleInputHandle.asElement();
      await titleInput.focus();
      await page.keyboard.type("Gemini Free AI Integrations for Business", { delay: 10 });
      await titleInput.dispose();
      console.log("Typed document title.");
    }
    await delay(2000);

    // Click Done on document modal
    console.log("Waiting for Done button to become active...");
    let doneActive = false;
    for (let attempt = 0; attempt < 30; attempt++) {
      const isActive = await page.evaluate(() => {
        function findDone(root) {
          const buttons = Array.from(root.querySelectorAll('button'));
          const b = buttons.find(btn => btn.innerText && btn.innerText.trim() === 'Done');
          if (b) {
            const isVisible = b.offsetWidth > 0 || b.offsetHeight > 0 || window.getComputedStyle(b).display !== 'none';
            const isDisabled = b.hasAttribute('disabled') || b.disabled || (b.getAttribute('aria-disabled') === 'true') || (typeof b.className === 'string' && b.className.includes('disabled'));
            return isVisible && !isDisabled;
          }
          const walker = document.createTreeWalker(root, NodeFilter.SHOW_ELEMENT, null, false);
          let node;
          while (node = walker.nextNode()) {
            if (node.shadowRoot) {
              const res = findDone(node.shadowRoot);
              if (res) return res;
            }
          }
          return null;
        }
        return findDone(document.body);
      });

      if (isActive) {
        doneActive = true;
        break;
      }
      await delay(1000);
    }

    if (!doneActive) throw new Error("Done button did not activate on Document modal");

    console.log("Clicking 'Done' on Document Modal...");
    const clickedDocDone = await clickNativelyShadow(page, (root) => {
      return Array.from(root.querySelectorAll('button')).find(b => {
        const txt = b.innerText ? b.innerText.trim() : '';
        const isVisible = b.offsetWidth > 0 || b.offsetHeight > 0 || window.getComputedStyle(b).display !== 'none';
        const isNotVideoJS = typeof b.className === 'string' && !b.className.includes('vjs-');
        const isDisabled = b.hasAttribute('disabled') || b.disabled || (b.getAttribute('aria-disabled') === 'true') || (typeof b.className === 'string' && b.className.includes('disabled'));
        return txt === 'Done' && isVisible && isNotVideoJS && !isDisabled;
      });
    });

    if (!clickedDocDone) throw new Error("Could not click Done on Document modal");
    await delay(4000);

    // Fill caption text
    const captionText = fs.readFileSync(path.join(__dirname, 'urgent_gemini_business_post.txt'), 'utf8');
    await fillEditorText(page, captionText);

    // Click 'Post' button to publish immediately
    console.log("Clicking final 'Post' button to publish immediately...");
    const clickedPost = await clickNativelyShadow(page, (root) => {
      const btns = Array.from(root.querySelectorAll('button'));
      return btns.find(b => {
        const txt = b.innerText ? b.innerText.trim() : '';
        const isPrimary = b.className && (b.className.includes('share-actions__primary-action') || b.className.includes('artdeco-button--primary'));
        return (txt === 'Post' || txt === 'Publish') && isPrimary;
      });
    });

    if (!clickedPost) throw new Error("Could not click final 'Post' button");

    console.log("Waiting 8s for publishing process to finish...");
    await delay(8000);
    console.log("🎉 GEMINI BUSINESS INTEGRATIONS CAROUSEL POST PUBLISHED SUCCESSFULLY TO LINKEDIN!");

    await browser.close();
    process.exit(0);

  } catch (err) {
    console.error("Automator Exception:", err);
    if (browser) await browser.close();
    process.exit(1);
  }
})();
