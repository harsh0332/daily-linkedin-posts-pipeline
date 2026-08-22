const puppeteer = require('puppeteer');
const fs = require('fs');
const path = require('path');

const screenshotDir = path.resolve(__dirname, './slack_downloads');
fs.mkdirSync(screenshotDir, { recursive: true });

const postsToSchedule = [
  {
    id: 1,
    type: 'carousel',
    date: '08/14/2026',
    time: '9:30 AM',
    assetPath: path.resolve(__dirname, './slack_downloads/carousel-aug14.pdf'),
    title: 'Meta Ad Hook Framework for D2C',
    caption: `80% of Meta ad spend is wasted in the first 3 seconds because modern audiences scroll past generic product intros.

Here is the exact 3-step Hook Framework we use to achieve 3.4x ROAS on D2C brands:

1️⃣ Pattern Interrupt (First 1.5s): Ditch polished studio video. Use native, high-contrast UGC angles.
2️⃣ Pain Specificity (Sec 1.5 - 3.0): Call out the exact problem in bold onscreen text.
3️⃣ Instant Outcome (Sec 3.0 - 5.0): Show the outcome before explaining how it works.

📌 Check out the full breakdown in the carousel slides below.

What hook style is currently giving you the lowest CPA? Let's discuss in the comments! 👇

#MetaAds #PerformanceMarketing #D2CGrowth #PaidSocial #AdvertisingStrategy`
  },
  {
    id: 2,
    type: 'regular',
    date: '08/15/2026',
    time: '9:30 AM',
    caption: `Most founders try to scale Meta ads by looking at 7-day click ROAS inside Ads Manager.

Then they double budget and watch profits collapse. Why?

Because Meta's internal attribution engine claims credit for view-throughs, retargeting touches, and brand-organic conversions that would have happened anyway.

Here is how high-scale D2C and B2B brands actually track ad efficiency:

1. First-Party CAPI Integration
Instead of relying on browser pixels alone, route purchase webhooks directly via server-to-server (n8n / Meta CAPI). This recovers 15-20% of lost iOS data.

2. Blended CAC over Platform ROAS
Track (Total Ad Spend) / (New Customers Acquired). If platform ROAS goes up but blended CAC goes up, your ads are just cannibalizing existing demand.

3. Single Concept Testing
Stop creating 50 ad variations at once. Test ONE core hook angle with 3 visual variations. Identify the winner, then double budget on top-of-funnel broad targeting.

Scaling isn't about spending more money on average ads; it's about validating one high-converting angle with bulletproof attribution.

Are you relying on platform ROAS or blended CAC?

#PerformanceMarketing #MetaAds #GrowthMarketing #AdAttribution #D2C`
  },
  {
    id: 3,
    type: 'carousel',
    date: '08/16/2026',
    time: '9:30 AM',
    assetPath: path.resolve(__dirname, './slack_downloads/carousel-aug16.pdf'),
    title: '90-Second Lead Nurture Stack',
    caption: `The 5-Minute Rule: If you respond to a new lead after 5 minutes, your qualification rate drops by 80%.

Most B2B and High-Ticket Lead Gen businesses lose 30-40% of deals simply because SDRs take 2 hours to send the first WhatsApp or email.

Here is the 90-Second Automated Nurture Stack built with n8n:

⚡ Step 1: Instant Lead Capture (Meta Instant Form / Webhook)
⚡ Step 2: Automated Qualification Node (AI Agent categorizes lead budget & fit)
⚡ Step 3: Personalized WhatsApp Message (Sent within 90 seconds via WhatsApp API)
⚡ Step 4: Calendar Sync & CRM Pipeline Update

Swipe through the carousel slides below to see the full n8n workflow architecture! ➡️

How fast is your sales team responding to inbound leads?

#Automation #n8n #LeadGeneration #WhatsAppMarketing #B2BSales #WorkflowAutomation`
  }
];

const editorSelector = '.ql-editor, div[contenteditable="true"][role="textbox"], div[contenteditable="true"]';

async function getElementShadow(page, selector) {
  const handle = await page.evaluateHandle((sel) => {
    function findEl(root) {
      if (!root) return null;
      const el = root.querySelector(sel);
      if (el) return el;
      const walker = document.createTreeWalker(root, NodeFilter.SHOW_ELEMENT, null, false);
      let node;
      while (node = walker.nextNode()) {
        if (node.shadowRoot) {
          const found = findEl(node.shadowRoot);
          if (found) return found;
        }
      }
      return null;
    }
    return findEl(document.body);
  }, selector);
  return handle.asElement();
}

async function waitForSelectorShadow(page, selector, timeout = 15000) {
  const startTime = Date.now();
  while (Date.now() - startTime < timeout) {
    const el = await getElementShadow(page, selector);
    if (el) {
      await el.dispose();
      return true;
    }
    await new Promise(r => setTimeout(r, 500));
  }
  throw new Error(`Timeout waiting for shadow selector: ${selector}`);
}

async function clickNativelyShadow(page, finderFn) {
  try {
    await page.evaluate(() => {
      document.querySelectorAll('.msg-overlay-container, [class*="msg-overlay"], #msg-overlay').forEach(el => el.remove());
    });

    const handle = await page.evaluateHandle((finder) => {
      const fn = new Function('return ' + finder)();
      function findInShadow(root) {
        if (!root) return null;
        const res = fn(root);
        if (res) return res;
        const walker = document.createTreeWalker(root, NodeFilter.SHOW_ELEMENT, null, false);
        let node;
        while (node = walker.nextNode()) {
          if (node.shadowRoot) {
            const found = findInShadow(node.shadowRoot);
            if (found) return found;
          }
        }
        return null;
      }
      return findInShadow(document.body);
    }, finderFn.toString());

    const el = handle.asElement();
    if (el) {
      const tagAndClass = await page.evaluate(e => {
        return `${e.tagName} class="${e.className}" text="${e.innerText ? e.innerText.trim().substring(0,30) : ''}"`;
      }, el);
      console.log(`clickNativelyShadow: Found element: <${tagAndClass}>`);
      try {
        await page.evaluate(e => {
          e.focus();
          e.scrollIntoView({ block: 'center', inline: 'center' });
        }, el);
        await new Promise(r => setTimeout(r, 200));
        await el.click();
      } catch (clickErr) {
        console.log("Puppeteer native click failed, falling back to programmatic event sequence:", clickErr.message);
        await page.evaluate(e => {
          const rect = e.getBoundingClientRect();
          const x = rect.left + rect.width / 2;
          const y = rect.top + rect.height / 2;
          const opts = { bubbles: true, cancelable: true, view: window, screenX: x, screenY: y, clientX: x, clientY: y };
          e.dispatchEvent(new PointerEvent('pointerdown', opts));
          e.dispatchEvent(new MouseEvent('mousedown', opts));
          e.focus();
          e.dispatchEvent(new PointerEvent('pointerup', opts));
          e.dispatchEvent(new MouseEvent('mouseup', opts));
          e.dispatchEvent(new MouseEvent('click', opts));
        }, el);
      }
      await el.dispose();
      return true;
    }
    return false;
  } catch (err) {
    console.error("clickNativelyShadow error:", err);
    return false;
  }
}

async function clickNativelyShadowRetry(page, finderFn, timeout = 15000) {
  const startTime = Date.now();
  while (Date.now() - startTime < timeout) {
    const clicked = await clickNativelyShadow(page, finderFn);
    if (clicked) return true;
    await new Promise(r => setTimeout(r, 1000));
  }
  return false;
}

async function fillFieldShadow(page, selector, value) {
  const el = await getElementShadow(page, selector);
  if (!el) throw new Error(`Could not find element to fill: ${selector}`);
  
  await page.evaluate((input) => {
    input.focus();
    input.select();
  }, el);
  
  await new Promise(r => setTimeout(r, 500));
  await page.keyboard.press('Backspace');
  
  await new Promise(r => setTimeout(r, 500));
  await page.keyboard.type(value);
  await page.keyboard.press('Enter');
  await new Promise(r => setTimeout(r, 200));
  await page.keyboard.press('Escape');
  await new Promise(r => setTimeout(r, 200));
  await page.keyboard.press('Tab');
  await el.dispose();
  await new Promise(r => setTimeout(r, 1000));
}

async function fillTimeComboboxShadow(page, selector, value) {
  const el = await getElementShadow(page, selector);
  if (!el) throw new Error(`Could not find combobox element to fill: ${selector}`);
  
  await page.evaluate((input) => {
    input.focus();
    input.select();
  }, el);
  
  await new Promise(r => setTimeout(r, 500));
  await page.keyboard.press('Backspace');
  
  await new Promise(r => setTimeout(r, 500));
  await page.keyboard.type(value);
  console.log(`Typed ${value} into time combobox, waiting for suggestions...`);
  await new Promise(r => setTimeout(r, 1500));
  
  await page.keyboard.press('ArrowDown');
  await new Promise(r => setTimeout(r, 500));
  await page.keyboard.press('Enter');
  await el.dispose();
  await new Promise(r => setTimeout(r, 1000));
}

(async () => {
  console.log("🚀 Launching Chrome for Adhoc Scheduling (Aug 14, 15, 16)...");
  const userDataDir = path.resolve(__dirname, './chrome-session');

  const browser = await puppeteer.launch({
    headless: false,
    userDataDir: userDataDir,
    executablePath: '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
    args: [
      '--no-sandbox',
      '--disable-setuid-sandbox',
      '--disable-gpu',
      '--disable-dev-shm-usage',
      '--use-mock-keychain',
      '--password-store=basic'
    ]
  });

  const page = await browser.newPage();
  await page.setViewport({ width: 1280, height: 900 });

  for (const post of postsToSchedule) {
    console.log(`\n==================================================`);
    console.log(`Scheduling Adhoc Post ${post.id}/3 (${post.type}): Date=${post.date}, Time=${post.time}`);
    console.log(`==================================================`);

    console.log("Navigating to feed home page...");
    try {
      await page.goto('https://www.linkedin.com/feed/', { waitUntil: 'domcontentloaded', timeout: 30000 });
    } catch (err) {
      console.log("Navigation timeout/error, continuing:", err.message);
    }
    await new Promise(r => setTimeout(r, 4000));

    // Hide messaging overlays
    await page.evaluate(() => {
      const style = document.createElement('style');
      style.id = 'hide-msg-overlay-style-' + Date.now();
      style.innerHTML = `.msg-overlay-container, [class*="msg-overlay"], #msg-overlay { display: none !important; }`;
      (document.head || document.documentElement).appendChild(style);
    });

    // Close any open composers
    await page.evaluate(() => {
      function findDismissBtn(root) {
        if (!root) return null;
        const btn = Array.from(root.querySelectorAll('button')).find(
          b => b.ariaLabel && (b.ariaLabel.includes('Dismiss') || b.ariaLabel.includes('Close'))
        );
        if (btn) return btn;
        const walker = document.createTreeWalker(root, NodeFilter.SHOW_ELEMENT, null, false);
        let node;
        while (node = walker.nextNode()) {
          if (node.shadowRoot) {
            const found = findDismissBtn(node.shadowRoot);
            if (found) return found;
          }
        }
        return null;
      }
      const dismiss = findDismissBtn(document.body);
      if (dismiss) dismiss.click();
    });
    await new Promise(r => setTimeout(r, 2000));

    console.log("Clicking 'Start a post'...");
    const clickStartPost = await clickNativelyShadow(page, (root) => {
      return Array.from(root.querySelectorAll('*')).find(
        el => (el.tagName === 'BUTTON' || el.getAttribute('role') === 'button' || el.getAttribute('aria-label') === 'Start a post') &&
              el.innerText && el.innerText.trim().includes('Start a post')
      );
    });
    if (!clickStartPost) throw new Error("Could not find 'Start a post' button");

    await waitForSelectorShadow(page, editorSelector, 15000);
    await new Promise(r => setTimeout(r, 1000));

    if (post.type === 'carousel') {
      console.log("Handling Carousel document upload...");
      let clickedDoc = await clickNativelyShadow(page, (root) => {
        const btns = Array.from(root.querySelectorAll('button'));
        return btns.find(b => b.ariaLabel && b.ariaLabel.includes('Add a document')) ||
               btns.find(b => b.innerText && b.innerText.includes('Add a document')) ||
               btns.find(b => b.innerText && b.innerText.includes('document'));
      });

      if (!clickedDoc) {
        console.log("Checking 'More' menu...");
        await clickNativelyShadow(page, (root) => {
          return Array.from(root.querySelectorAll('button')).find(
            b => (b.ariaLabel && b.ariaLabel.includes('More')) || (b.innerText && b.innerText.includes('More'))
          );
        });
        await new Promise(r => setTimeout(r, 1500));
        clickedDoc = await clickNativelyShadow(page, (root) => {
          const btns = Array.from(root.querySelectorAll('button'));
          return btns.find(b => b.ariaLabel && b.ariaLabel.includes('Add a document')) ||
                 btns.find(b => b.innerText && b.innerText.includes('Add a document')) ||
                 btns.find(b => b.innerText && b.innerText.includes('document'));
        });
      }

      if (!clickedDoc) throw new Error("Could not find 'Add a document' button");
      await new Promise(r => setTimeout(r, 2000));

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

      if (!fileInputHandle) throw new Error("Could not find file input for document");
      const fileInput = fileInputHandle.asElement();
      await fileInput.uploadFile(post.assetPath);
      console.log("Document uploaded. Waiting 4s for processing...");
      await new Promise(r => setTimeout(r, 4000));

      // Title
      await waitForSelectorShadow(page, 'input.document-title-form__title-input, input[placeholder*="title to your document"]');
      const titleInput = await getElementShadow(page, 'input.document-title-form__title-input, input[placeholder*="title to your document"]');
      await titleInput.focus();
      await page.keyboard.type(post.title);
      await titleInput.dispose();
      console.log(`Document title typed (${post.title.length} chars):`, post.title);

      // Verify title
      const titleVal = await page.evaluate(() => {
        function findTitleInput(root) {
          const el = root.querySelector('input.document-title-form__title-input, input[placeholder*="title to your document"]');
          if (el) return el.value.trim();
          const walker = document.createTreeWalker(root, NodeFilter.SHOW_ELEMENT, null, false);
          let node;
          while (node = walker.nextNode()) {
            if (node.shadowRoot) {
              const val = findTitleInput(node.shadowRoot);
              if (val) return val;
            }
          }
          return null;
        }
        return findTitleInput(document.body);
      });
      console.log("Title value in DOM:", titleVal);
      if (!titleVal || titleVal === "") {
        throw new Error("Validation Failed: Document title input is blank!");
      }

      // Wait for Done button to be active
      console.log("Waiting for document upload to finish (Done button to become enabled)...");
      let doneBtnEnabled = false;
      for (let attempt = 0; attempt < 60; attempt++) {
        const isDoneActive = await page.evaluate(() => {
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
            return false;
          }
          return findDone(document.body);
        });
        
        if (isDoneActive) {
          doneBtnEnabled = true;
          console.log("Upload complete! Done button is now active.");
          break;
        }
        await new Promise(r => setTimeout(r, 1000));
      }
      if (!doneBtnEnabled) throw new Error("Upload timed out or Done button was not enabled.");

      const clickedDone = await clickNativelyShadowRetry(page, (root) => {
        return Array.from(root.querySelectorAll('button')).find(b => {
          const txt = b.innerText ? b.innerText.trim() : '';
          const isVisible = b.offsetWidth > 0 || b.offsetHeight > 0 || window.getComputedStyle(b).display !== 'none';
          const isNotVideoJS = typeof b.className === 'string' && !b.className.includes('vjs-');
          const isDisabled = b.hasAttribute('disabled') || b.disabled || (typeof b.className === 'string' && b.className.includes('disabled'));
          return txt === 'Done' && isVisible && isNotVideoJS && !isDisabled;
        });
      });
      if (!clickedDone) throw new Error("Could not click Done on document creator");
      await new Promise(r => setTimeout(r, 3000));
    }

    // Fill caption paragraph by paragraph
    console.log("Filling post caption text...");
    await waitForSelectorShadow(page, editorSelector, 15000);
    const editorEl = await getElementShadow(page, editorSelector);
    await editorEl.focus();

    await page.evaluate((el) => {
      el.focus();
      document.execCommand('selectAll', false, null);
      document.execCommand('delete', false, null);
    }, editorEl);
    await new Promise(r => setTimeout(r, 1000));

    const paragraphs = post.caption.split('\n');
    for (let i = 0; i < paragraphs.length; i++) {
      if (i > 0) {
        await page.keyboard.press('Enter');
        await new Promise(r => setTimeout(r, 150));
      }
      if (paragraphs[i]) {
        await page.keyboard.type(paragraphs[i]);
        await new Promise(r => setTimeout(r, 150));
      }
    }
    await new Promise(r => setTimeout(r, 2000));
    await editorEl.dispose();

    // Verify caption
    const editorText = await page.evaluate(() => {
      function findText(root) {
        const el = root.querySelector('.ql-editor');
        if (el) return el.innerText.trim();
        const walker = document.createTreeWalker(root, NodeFilter.SHOW_ELEMENT, null, false);
        let node;
        while (node = walker.nextNode()) {
          if (node.shadowRoot) {
            const txt = findText(node.shadowRoot);
            if (txt) return txt;
          }
        }
        return null;
      }
      return findText(document.body);
    });
    console.log("Caption text in editor (length):", editorText ? editorText.length : 0);
    if (!editorText || editorText.length < 5) {
      throw new Error("Validation Failed: Post caption in editor is blank or too short!");
    }

    // Open Schedule Modal
    console.log("Opening Schedule Settings...");
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
    if (!clickedScheduleIcon) throw new Error("Could not find or click Schedule post clock icon");
    await new Promise(r => setTimeout(r, 4000));

    // Set Date & Time
    console.log(`Setting schedule: Date=${post.date}, Time=${post.time}`);
    await fillFieldShadow(page, 'input[placeholder*="Date"], input[aria-label*="date"], input[id*="date"]', post.date);

    let normalizedTime = post.time;
    if (normalizedTime.startsWith('0')) {
      normalizedTime = normalizedTime.substring(1);
    }
    await fillTimeComboboxShadow(page, 'input[placeholder*="Time"], input[aria-label*="time"], input[id*="time"], input[role="combobox"]', normalizedTime);

    // Click Next
    console.log("Saving schedule settings (clicking Next)...");
    const clickedNext = await clickNativelyShadow(page, (root) => {
      return Array.from(root.querySelectorAll('button')).find(
        b => b.innerText && b.innerText.trim() === 'Next'
      );
    });
    if (!clickedNext) throw new Error("Could not click Next in schedule modal");
    await new Promise(r => setTimeout(r, 3000));

    // Click Schedule
    console.log("Clicking final 'Schedule' button...");
    const clickedScheduleFinal = await clickNativelyShadow(page, (root) => {
      return Array.from(root.querySelectorAll('button')).find(
        b => b.innerText && b.innerText.trim() === 'Schedule'
      );
    });
    if (!clickedScheduleFinal) throw new Error("Could not find final 'Schedule' button in composer modal");

    console.log("Success! Waiting 6s for scheduling process to complete...");
    await new Promise(r => setTimeout(r, 6000));

    const isClosed = await page.evaluate(() => {
      return !document.querySelector('.ql-editor');
    });
    if (!isClosed) {
      console.log("Sending Escape key...");
      await page.keyboard.press('Escape');
      await new Promise(r => setTimeout(r, 2000));
    }

    console.log(`✓ Successfully scheduled Adhoc Post ${post.id}/3 for ${post.date}!`);
  }

  await browser.close();
  console.log("\n============================================================");
  console.log("🎉 ALL 3 ADHOC POSTS (AUG 14, 15, 16) SCHEDULED SUCCESSFULLY!");
  console.log("============================================================");
})();
