// Verifies the 2026-08-20 selector fixes against LIVE LinkedIn.
// Goes: Start a post -> Expand content types -> Document -> upload PDF ->
// checks the title field and the Done control. Then DISMISSES.
// It never clicks Done, Next, Schedule or Post.
const puppeteer = require('puppeteer');
const path = require('path');
const PDF = path.join(__dirname, 'carousel-routine/output/2026-08-20/carousel-branded/linkedin-carousel-1.pdf');
const ok = [], bad = [];
function check(name, pass, extra) {
  (pass ? ok : bad).push(name);
  console.log(`  [${pass ? 'PASS' : 'FAIL'}] ${name}${extra ? '  ' + extra : ''}`);
}

async function getElementShadow(page, selector) {
  const h = await page.evaluateHandle((sel) => {
    function findEl(root) {
      if (!root) return null;
      const el = root.querySelector(sel);
      if (el) return el;
      const w = document.createTreeWalker(root, NodeFilter.SHOW_ELEMENT, null, false);
      let n; while (n = w.nextNode()) if (n.shadowRoot) { const f = findEl(n.shadowRoot); if (f) return f; }
      return null;
    }
    return findEl(document.body);
  }, selector);
  return h.asElement();
}

(async () => {
  const browser = await puppeteer.launch({
    headless: false, userDataDir: path.join(__dirname, 'chrome-session'),
    defaultViewport: null, args: ['--start-maximized','--no-sandbox','--disable-setuid-sandbox']
  });
  const page = (await browser.pages())[0] || await browser.newPage();
  try {
    await page.goto('https://www.linkedin.com/feed/', { waitUntil:'domcontentloaded', timeout:60000 });
    await new Promise(r => setTimeout(r, 6000));

    await page.evaluate(() => {
      const b = Array.from(document.querySelectorAll('button,[role="button"]'))
        .find(e => ((e.innerText||'')+(e.getAttribute('aria-label')||'')).toLowerCase().includes('start a post'));
      if (b) b.click();
    });
    await new Promise(r => setTimeout(r, 9000));
    check('composer opened at /sharing/compose', /sharing\/compose/.test(page.url()), page.url().slice(0,60));

    // FIX 1 — the "+"
    const plus = await page.evaluate(() => {
      const exact = Array.from(document.querySelectorAll('button[aria-label], [role="button"][aria-label]')).find(el => {
        const l = (el.getAttribute('aria-label')||'').toLowerCase();
        const r = el.getBoundingClientRect();
        return r.width>0 && r.height>0 && (l === 'expand content types' || l.includes('expand content'));
      });
      if (!exact) return null;
      const r = exact.getBoundingClientRect();
      return { x: r.left + r.width/2, y: r.top + r.height/2 };
    });
    check('FIX 1: "Expand content types" found', !!plus, plus ? `at ${Math.round(plus.x)},${Math.round(plus.y)}` : '');
    if (!plus) throw new Error('cannot continue without the + control');
    await page.mouse.click(plus.x, plus.y);
    await new Promise(r => setTimeout(r, 6000));

    // FIX 2 — Document as an <a>
    const doc = await page.evaluate(() => {
      const el = Array.from(document.querySelectorAll('a[aria-label], button[aria-label], [role="button"][aria-label], [role="menuitem"][aria-label]')).find(e => {
        const l = (e.getAttribute('aria-label')||'').trim().toLowerCase();
        const r = e.getBoundingClientRect();
        return r.width>0 && r.height>0 && (l === 'document' || l === 'add a document' || l === 'share a document');
      });
      if (!el) return null;
      const r = el.getBoundingClientRect();
      return { x: r.left + r.width/2, y: r.top + r.height/2, tag: el.tagName };
    });
    check('FIX 2: "Document" found', !!doc, doc ? `<${doc.tag}>` : '');
    if (!doc) throw new Error('cannot continue without the Document control');
    await page.mouse.click(doc.x, doc.y);
    console.log('  waiting 12s for the document dialog (user reported 3-4s+)...');
    await new Promise(r => setTimeout(r, 12000));

    // FIX 3 — upload
    let uploaded = false;
    const fi = await getElementShadow(page, 'input[type="file"]');
    if (fi) { await fi.uploadFile(PDF); uploaded = true; check('FIX 3: uploaded via input[type=file]', true); }
    else {
      const desc = await page.evaluate(() => {
        const WANTED = ['choose file','upload from computer','select file','add a document'];
        function find(root, d) {
          if (!root || d > 5) return null;
          for (const e of root.querySelectorAll('button,label,div[role="button"],span,a')) {
            const t = ((e.innerText||'')+' '+(e.getAttribute('aria-label')||'')).toLowerCase();
            const r = e.getBoundingClientRect();
            if (r.width>0 && r.height>0 && WANTED.some(w => t.includes(w))) return e;
          }
          const w = document.createTreeWalker(root, NodeFilter.SHOW_ELEMENT, null, false);
          let n; while (n = w.nextNode()) if (n.shadowRoot) { const f = find(n.shadowRoot, d+1); if (f) return f; }
          return null;
        }
        const b = find(document.body, 0);
        if (!b) return null;
        window.__docChooseBtn = b;
        return b.tagName + ' "' + (b.innerText||'').trim().slice(0,30) + '"';
      });
      check('FIX 3: "Choose file" control found', !!desc, desc || '');
      if (desc) {
        const [fc] = await Promise.all([
          page.waitForFileChooser({ timeout: 10000 }).catch(() => null),
          page.evaluate(() => { const b = window.__docChooseBtn; if (b) { b.click(); return true; } return false; })
        ]);
        if (fc) { await fc.accept([PDF]); uploaded = true; check('FIX 3: uploaded via fileChooser', true); }
        else check('FIX 3: uploaded via fileChooser', false, 'chooser never opened');
      }
    }

    if (uploaded) {
      console.log('  waiting 15s for LinkedIn to process the PDF...');
      await new Promise(r => setTimeout(r, 15000));
      await page.screenshot({ path: path.join(__dirname,'diag','V_after_upload.png') }).catch(()=>{});

      const titleSel = 'input.document-title-form__title-input, input[placeholder*="title to your document"], input[placeholder*="title" i], input[aria-label*="title" i], input[name*="title" i]';
      const t = await getElementShadow(page, titleSel);
      check('title field present after upload', !!t);
      if (t) { const mx = await page.evaluate(e => e.maxLength, t); console.log('        maxLength =', mx, '(DOC_TITLE_MAX is 58)'); }

      const doneInfo = await page.evaluate(() => {
        const c = Array.from(document.querySelectorAll('button, a, [role="button"]')).filter(el => (el.innerText||'').trim() === 'Done');
        const vis = c.filter(el => { if (el.closest && el.closest('.video-js,[class*="vjs-"]')) return false; const r = el.getBoundingClientRect(); return r.width>0&&r.height>0; });
        return { total: c.length, tags: c.map(e=>e.tagName), visible: vis.length, visTags: vis.map(e=>e.tagName) };
      });
      check('FIX 4: a visible "Done" control is findable', doneInfo.visible > 0,
        `all=[${doneInfo.tags}] visible=[${doneInfo.visTags}]`);
      const oldWay = await page.evaluate(() =>
        Array.from(document.querySelectorAll('button')).filter(b => (b.innerText||'').trim()==='Done')
          .filter(b => { const r=b.getBoundingClientRect(); return r.width>0&&r.height>0; }).length);
      console.log(`        old button-only search would find: ${oldWay} visible  <- ${oldWay===0?'this is why it timed out':''}`);
    }

    console.log('\n  Dismissing without posting...');
    await page.keyboard.press('Escape');
    await new Promise(r => setTimeout(r, 2000));
  } catch (e) {
    console.error('\nERROR:', e.message);
    await page.screenshot({ path: path.join(__dirname,'diag','V_error.png') }).catch(()=>{});
  } finally {
    console.log(`\n==== ${ok.length} passed, ${bad.length} failed ====`);
    if (bad.length) console.log('failed: ' + bad.join(', '));
    await new Promise(r => setTimeout(r, 2000));
    await browser.close();
    console.log('Browser closed. Nothing was posted or scheduled.');
  }
})();
