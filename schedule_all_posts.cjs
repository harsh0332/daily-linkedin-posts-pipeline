const puppeteer = require('puppeteer');
const fs = require('fs');
const path = require('path');
const os = require('os');
const { loadConfig } = require('./config_loader.cjs');

// ---- Phase 1: single source of truth ----------------------------------------
// loadConfig() asserts on startup that format_mix sums to posts_per_batch and
// that the horizon x slots can hold the batch. It aborts non-zero on mismatch.
const CONFIG = loadConfig();
const POSTS_PER_BATCH = CONFIG.posts_per_batch;
const BATCH_HORIZON_DAYS = CONFIG.batch_horizon_days;
const TIME_SLOTS = CONFIG.time_slots;
const FORMAT_MIX = CONFIG.format_mix;
const TIMEZONE = CONFIG.timezone;
const WEEKDAYS_ONLY = CONFIG.weekdays_only === true;

// Module scope on purpose. Guard D and the watermark write live in DIFFERENT
// functions; declaring these inside one of them put the other's references out
// of scope, and because the watermark write sits inside a try/catch the
// ReferenceError would have been swallowed - five posts live, watermark never
// advanced, and the next run rescheduling the same dates.
const DAY_NUM = { sun: 0, mon: 1, tue: 2, wed: 3, thu: 4, fri: 5, sat: 6 };
const DAY_NAME = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday',
                  'Friday', 'Saturday'];

function isoDayOf(d) {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`
    + `-${String(d.getDate()).padStart(2, '0')}`;
}

// The weekday pillar 1 claims, e.g. "Mon" -> 1. undefined if not declared.
function pillarOneWeekday() {
  const first = Array.isArray(CONFIG.pillars) ? CONFIG.pillars[0] : null;
  if (!first || typeof first.day !== 'string') return undefined;
  return DAY_NUM[first.day.slice(0, 3).toLowerCase()];
}

// Phase 1: "today" is the calendar date in the configured timezone, not the
// machine's local date. The audit flagged a complete absence of timezone
// handling; this is the one place it matters, because Guard C compares the
// batch start against tomorrow.
function todayInTimezone() {
  try {
    const s = new Intl.DateTimeFormat('en-CA', {
      timeZone: TIMEZONE, year: 'numeric', month: '2-digit', day: '2-digit'
    }).format(new Date());
    const [y, m, d] = s.split('-').map(Number);
    return new Date(y, m - 1, d);
  } catch (e) {
    console.warn(`Could not resolve timezone "${TIMEZONE}", falling back to system local date.`);
    const n = new Date();
    return new Date(n.getFullYear(), n.getMonth(), n.getDate());
  }
}
// ------------------------------------------------------------------------------

// ---- 2026-08-21: consumption happens HERE, not at generation time ----------
// generate_all_content.py used to write used_topics/used_angles/used_sources the
// moment a post reached disk. But a post on disk is not a post on LinkedIn, and
// drafts that were never scheduled still burned a benchmark figure, a Reddit
// question and two angles. The generator now only DECLARES what each post would
// consume, in batch_manifest.json. This records it per post, immediately after
// that post is genuinely on LinkedIn's queue - the same moment the checkpoint is
// written, so the two can never disagree.
const MANIFEST_FILE = path.join(__dirname, 'batch_manifest.json');

function readManifest() {
  try {
    if (!fs.existsSync(MANIFEST_FILE)) return null;
    const m = JSON.parse(fs.readFileSync(MANIFEST_FILE, 'utf8'));
    return Array.isArray(m.posts) ? m : null;
  } catch (e) {
    console.error(`  batch_manifest.json unreadable (${e.message}). Nothing will`);
    console.error('  be marked as used; the next batch may repeat this material.');
    return null;
  }
}

function readJsonOr(file, fallback) {
  try { return fs.existsSync(file) ? JSON.parse(fs.readFileSync(file, 'utf8')) : fallback; }
  catch (e) { return fallback; }
}

function recordConsumption(entry) {
  if (!entry) return;
  const today = new Date().toISOString().slice(0, 10);
  const done = [];

  if (entry.topic) {
    const f = path.join(__dirname, 'used_topics.json');
    const topics = readJsonOr(f, []);
    if (Array.isArray(topics) && !topics.includes(entry.topic)) {
      topics.push(entry.topic);
      fs.writeFileSync(f, JSON.stringify(topics, null, 2) + '\n');
      done.push('topic');
    }
  }

  if (entry.angle_key) {
    const f = path.join(__dirname, 'used_angles.json');
    const st = readJsonOr(f, { angles: {}, theses: {} });
    st.angles = st.angles || {};
    st.theses = st.theses || {};
    st.angles[entry.angle_key] = today;
    if (entry.thesis) {
      st.theses[entry.thesis] = st.theses[entry.thesis] || [];
      st.theses[entry.thesis].push(today);
    }
    fs.writeFileSync(f, JSON.stringify(st, null, 2) + '\n');
    done.push(`angle ${entry.angle_key}`);
  }

  if (entry.source_key && entry.pillar_id) {
    const f = path.join(__dirname, 'used_sources.json');
    const st = readJsonOr(f, {});
    st[entry.pillar_id] = st[entry.pillar_id] || {};
    st[entry.pillar_id][entry.source_key] = today;
    fs.writeFileSync(f, JSON.stringify(st, null, 2) + '\n');
    done.push(`source ${entry.pillar_id} <- ${entry.source_key}`);
  }

  if (done.length) console.log(`  consumed: ${done.join('; ')}`);
}

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
  // 2026-08-20: clicking "Start a post" now NAVIGATES the main frame to
  // linkedin.com/sharing/compose. While that navigation is in flight,
  // evaluateHandle throws "detached Frame" / "Execution context was destroyed".
  // This loop used to let that escape and kill the whole post. A navigation is
  // exactly the condition we are waiting through, so swallow it and keep
  // polling until the real timeout.
  const startTime = Date.now();
  let lastErr = null;
  while (Date.now() - startTime < timeout) {
    try {
      const el = await getElementShadow(page, selector);
      if (el) {
        await el.dispose();
        return true;
      }
    } catch (e) {
      lastErr = e;
      const msg = (e && e.message) || '';
      if (!/detached Frame|Execution context was destroyed|Target closed|Session closed/i.test(msg)) {
        throw e;
      }
    }
    await new Promise(r => setTimeout(r, 500));
  }
  throw new Error(`Timeout waiting for shadow selector: ${selector}`
    + (lastErr ? ` (last error: ${lastErr.message})` : ''));
}

async function clickNativelyShadow(page, finderFn) {
  for (let frameRetry = 0; frameRetry < 3; frameRetry++) {
    try {
      const frame = page.mainFrame();
      await frame.evaluate(() => {
        document.querySelectorAll('.msg-overlay-container, [class*="msg-overlay"], #msg-overlay').forEach(el => el.remove());
      });

      const handle = await frame.evaluateHandle((finder) => {
        const fn = new Function('return ' + finder)();
        function findInShadow(root) {
          if (!root) return null;
          if (root.querySelectorAll) {
            root.querySelectorAll('.msg-overlay-container, [class*="msg-overlay"], #msg-overlay').forEach(el => el.remove());
          }
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
        const tagAndClass = await frame.evaluate(e => {
          return `${e.tagName} class="${e.className}" text="${e.innerText ? e.innerText.trim().substring(0,30) : ''}"`;
        }, el);
        console.log(`clickNativelyShadow: Found element: <${tagAndClass}>`);
        try {
          const coords = await frame.evaluate(e => {
            e.focus();
            e.scrollIntoView({ block: 'center', inline: 'center' });
            const rect = e.getBoundingClientRect();
            return { x: rect.left + rect.width / 2, y: rect.top + rect.height / 2 };
          }, el);
          await new Promise(r => setTimeout(r, 300));
          await page.mouse.click(coords.x, coords.y);
        } catch (clickErr) {
          console.log("Puppeteer mouse click failed, falling back to el.click():", clickErr.message);
          await frame.evaluate(e => {
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
        return true;
      }
      return false;
    } catch (err) {
      if (err.message.includes('detached Frame') || err.message.includes('Execution context was destroyed')) {
        console.log(`clickNativelyShadow: Frame detached, re-anchoring mainFrame (attempt ${frameRetry + 1}/3)...`);
        await new Promise(r => setTimeout(r, 1000));
        continue;
      }
      console.log("clickNativelyShadow error:", err.message);
      return false;
    }
  }
  return false;
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

// ---- Phase 0b: markdown-tolerant marker handling ---------------------------
// The model emits marker lines inconsistently: "CAROUSEL CAPTION:",
// "**CAROUSEL CAPTION:**" and "*CAROUSEL CAPTION:*" all occur in the archives.
// Normalise a line by stripping markdown emphasis and whitespace BEFORE
// matching, and strip emphasis from the captured text afterwards — .trim()
// alone cannot remove a leading '*', which is how "**" reached published posts.
//
// ⚠ KNOWN DUPLICATION: identical normalisation exists in Python at
//   send_to_slack.py:363-393 (MARKDOWN_EMPHASIS / normalise_marker / is_marker
//   / extract_caption). The two must stay in sync or the Slack preview will
//   disagree with what is published. Collapse into one shared definition when
//   this pipeline gets a config layer.
const MARKDOWN_EMPHASIS = /^[\s*_`]+|[\s*_`]+$/g;

function stripEmphasis(text) {
  return String(text === null || text === undefined ? '' : text).replace(MARKDOWN_EMPHASIS, '');
}

function normaliseMarker(line) {
  return stripEmphasis(line);
}

// Returns the text following `marker` on the same line, or null if this line
// does not start with that marker (emphasis and padding ignored).
function markerRemainder(line, marker) {
  const norm = normaliseMarker(line);
  const target = String(marker).toUpperCase().replace(/:+$/, '');
  if (norm.toUpperCase().indexOf(target) !== 0) return null;
  // The marker must be followed by ':' (optionally wrapped in emphasis).
  // Without this, a prose line such as "Hooks that convert are short" matched
  // the 'Hook:' marker and became the LinkedIn document title.
  const after = norm.slice(target.length);
  const sep = after.match(/^[\s*_`]*:+/);
  if (!sep) return null;
  return stripEmphasis(after.slice(sep[0].length));
}

function isMarkerLine(line, marker) {
  return markerRemainder(line, marker) !== null;
}

// Capture everything after a marker line. Returns null if the marker is absent,
// so callers can preserve the existing "leave caption as the whole body" path.
function extractCaption(bodyLines, markers) {
  let start = -1;
  let sameLine = '';
  for (let k = 0; k < bodyLines.length && start === -1; k++) {
    for (const m of markers) {
      const rem = markerRemainder(bodyLines[k], m);
      if (rem !== null) { start = k; sameLine = rem; break; }
    }
  }
  if (start === -1) return null;
  const out = [];
  if (sameLine) out.push(sameLine);
  for (let k = start + 1; k < bodyLines.length; k++) out.push(bodyLines[k]);
  return stripEmphasis(out.join('\n'));
}

// A poll option line, tolerating "**☐ Option**" as well as "☐ Option".
function isOptionLine(line) {
  return /^(?:☐|\[\s*\]|•|-)/.test(normaliseMarker(line));
}

// Strip only WRAPPING quotes. Removing every quote (as the old hook-line code
// did) mangles apostrophes: "Don't" -> "Dont", "Meta's" -> "Metas".
function stripWrappingQuotes(text) {
  return String(text === null || text === undefined ? '' : text)
    .replace(/^["'“”‘’]+|["'“”‘’]+$/g, '');
}

// LinkedIn caps the carousel document title. 58 characters per the project
// owner's observation of the composer. NOT verifiable from this repo — no run
// has ever captured the input's maxLength attribute (every past run published
// the 16-char literal "Branded Carousel"). Kept as one named constant so a
// corrected limit is a single-line change. The title step logs the input's real
// maxLength at run time so the next run confirms or corrects this number.
const DOC_TITLE_MAX = 58;
// Widened 2026-08-20 after LinkedIn redesigned "Share a document". The original
// class-only selector is kept first so behaviour is unchanged when it matches.
const DOC_TITLE_SELECTOR = [
  'input.document-title-form__title-input',
  'input[placeholder*="title to your document"]',
  'input[placeholder*="title" i]',
  'input[aria-label*="title" i]',
  'input[name*="title" i]'
].join(', ');

// Conjunctions, articles and prepositions that must not be left dangling at
// the end of a truncated title.
const TITLE_TRAILING_WORDS = new Set([
  'and', 'but', 'or', 'nor', 'so', 'yet', 'if', 'when', 'while', 'than', 'that',
  'the', 'a', 'an',
  'to', 'for', 'with', 'of', 'in', 'on', 'from', 'at', 'by', 'as', 'into',
  'onto', 'about', 'over', 'under', 'via'
]);

// Shortest acceptable clause. Below this, a clause cut is worse than a word cut
// ("Bad data" from "Bad data. It clouds judgment...").
const TITLE_MIN_CLAUSE = 20;

// An opening quote left without its partner by truncation ("a 'winning") is
// stray punctuation too, so the orphaned final word goes with it.
//
// Scoped deliberately to the FINAL word only. A whole-string odd-quote count
// is wrong for English: apostrophes in contractions and possessives ("Don't",
// "client's") are unpaired by nature, and counting them truncated real titles
// down to "Don".
function dropUnbalancedQuoteTail(text) {
  const t = String(text || '').trim();
  const m = t.match(/\s(["'“‘])([^\s"'”’]*)$/);
  if (!m) return t;
  // Drop the final word only if its opening quote is never closed.
  const after = t.slice(m.index + 2);
  if (/["'”’]/.test(after)) return t;
  return t.slice(0, m.index).trim();
}

function tidyTitleEnd(text) {
  let t = String(text || '').trim();
  for (;;) {
    const before = t;
    // '?' and '!' are deliberately NOT stripped: hooks are often questions
    // ("Why cut a winning product?") and the mark carries meaning in a title.
    t = t.replace(/[\s,;:.\-–—"']+$/, '');
    const m = t.match(/\s([A-Za-z]+)$/);
    if (m && TITLE_TRAILING_WORDS.has(m[1].toLowerCase())) t = t.slice(0, m.index);
    t = dropUnbalancedQuoteTail(t);
    if (t === before) break;
  }
  return t.trim();
}

// Fit any candidate title into the document-title limit:
//   1. hard cap, cut on a word boundary, no ellipsis
//   2. prefer the first complete clause that fits
//   3. drop trailing punctuation and dangling conjunctions/prepositions
function fitTitle(text, maxLen) {
  const limit = maxLen || DOC_TITLE_MAX;
  const src = String(text || '').replace(/\s+/g, ' ').trim();
  if (!src) return '';
  if (src.length <= limit) return tidyTitleEnd(src);

  // Sentence end = . ! ? followed by whitespace or end-of-string, so decimals
  // ("9.21 ROAS") and "₹10L/mo." mid-number are not treated as clause ends.
  const re = /[.!?](?=\s|$)/g;
  let m;
  let clauseEnd = -1;
  while ((m = re.exec(src)) !== null) {
    if (m.index >= limit) break;
    if (m.index >= TITLE_MIN_CLAUSE) { clauseEnd = m.index; break; }
  }
  if (clauseEnd !== -1) {
    // Keep a closing '?' or '!' (meaningful); drop a closing '.' (noise).
    const punct = src[clauseEnd];
    const end = (punct === '?' || punct === '!') ? clauseEnd + 1 : clauseEnd;
    return tidyTitleEnd(src.slice(0, end));
  }

  const cut = src.slice(0, limit);
  const lastSpace = cut.lastIndexOf(' ');
  return tidyTitleEnd(lastSpace > 0 ? cut.slice(0, lastSpace) : cut);
}

// Derive a LinkedIn document title from caption text when no Hook line exists.
function titleFromCaption(caption, maxLen) {
  const firstLine = String(caption || '')
    .split('\n')
    .map(l => stripWrappingQuotes(stripEmphasis(l)).trim())
    .find(l => l.length > 0);
  return fitTitle(firstLine, maxLen);
}
// ----------------------------------------------------------------------------

function parseTodayPosts() {
  const txtPath = path.join(__dirname, 'linkedin_posts_today.txt');
  if (!fs.existsSync(txtPath)) {
    console.error("\n" + "=".repeat(64));
    console.error("FATAL: required input file is missing.");
    console.error(`  Expected: ${txtPath}`);
    console.error("");
    console.error("This file is produced by the content generation step");
    console.error("(generate_all_content.py). There is no fallback batch.");
    console.error("Nothing has been scheduled. Aborting.");
    console.error("=".repeat(64) + "\n");
    process.exit(1);
  }
  
  try {
    const content = fs.readFileSync(txtPath, 'utf8');
    const sections = content.split(/={10,}/);
    const posts = [];
    let postIdx = 0;
    
    for (let i = 0; i < sections.length; i++) {
      const sec = sections[i].trim();
      if (!sec) continue;
      
      const lines = sec.split('\n');
      const header = lines[0].trim();
      if (/^\d+\./.test(header)) {
        const body = (sections[i + 1] || '').trim();
        if (!body) continue;
        
        postIdx++;
        i++; // skip body section
        
        const type = header.toLowerCase().includes('carousel') ? 'carousel' :
                     header.toLowerCase().includes('infographic') ? 'infographic' :
                     header.toLowerCase().includes('poll') ? 'poll' : 'regular';
                     
        const post = {
          id: postIdx,
          type: type,
          caption: body
        };
        
        if (type === 'poll') {
          const bodyLines = body.split('\n');
          // Phase 0b: isOptionLine() tolerates emphasised options ("**☐ A**"),
          // which the old startsWith('☐') check dropped silently.
          const pollLines = bodyLines.filter(line => isOptionLine(line));
          const cleanBodyLines = bodyLines.filter(line => !isOptionLine(line));

          const firstOptIdx = bodyLines.findIndex(line => isOptionLine(line));
          let question = "Choose the best option:";
          if (firstOptIdx !== -1) {
            for (let k = firstOptIdx - 1; k >= 0; k--) {
              const line = stripEmphasis(bodyLines[k]);
              if (line) {
                question = line;
                break;
              }
            }
          }
          // Phase 0b: drop the literal label so LinkedIn does not show
          // "Question: How do you ...". Only the label is removed. Re-strip
          // emphasis afterwards: "**Question:** X" leaves a dangling "**"
          // once the label is gone — the same trailing-emphasis trap that
          // published "**" from the caption marker.
          question = stripEmphasis(
            question.replace(/^(?:poll\s+)?question\s*[:\-–]\s*/i, '')
          ).trim();
          if (question.length > 140) {
            question = question.substring(0, 137) + '...';
          }

          post.caption = cleanBodyLines.join('\n').trim();
          post.title = question.trim();
          post.pollOptionsStr = pollLines.map(opt => {
            let val = stripEmphasis(normaliseMarker(opt).replace(/^[☐\[ \]\-\•]+/, ''));
            if (val.length > 30) {
              val = val.substring(0, 27) + '...';
            }
            return val;
          }).slice(0, 4).join('|');
        } else if (type === 'carousel') {
          const bodyLines = body.split('\n');
          // Phase 0b: emphasis-tolerant. The old .includes() + .split() left the
          // trailing "**" of "**CAROUSEL CAPTION:**" at the head of the caption,
          // which .trim() cannot remove — that is what published "**".
          const carouselCaption = extractCaption(bodyLines, ['CAROUSEL CAPTION:', 'Caption:']);
          if (carouselCaption !== null) {
            post.caption = carouselCaption;
          }

          // Phase 0b: title precedence is Hook line -> first caption line ->
          // literal fallback. Previously the prompt never emitted a Hook line,
          // so every carousel published with the title "Branded Carousel".
          const hookLine = bodyLines.find(line => isMarkerLine(line, 'Hook text:') || isMarkerLine(line, 'Hook:'));
          let carouselTitle = '';
          if (hookLine) {
            // slice at the FIRST colon: the old split(':')[1] truncated any
            // hook text that itself contained a colon.
            const colonAt = hookLine.indexOf(':');
            carouselTitle = stripWrappingQuotes(stripEmphasis(hookLine.slice(colonAt + 1)).trim()).trim();
          }
          if (!carouselTitle) carouselTitle = titleFromCaption(post.caption);
          // Cap applies whichever source won — a Hook line can exceed it too.
          carouselTitle = fitTitle(carouselTitle);
          post.title = carouselTitle || 'Branded Carousel';
          
          let carouselIdx = '1';
          const match = header.match(/CAROUSEL\s*(\d+)/i);
          if (match) carouselIdx = match[1];

          const localToday = new Date();
          const localOffset = localToday.getTimezoneOffset();
          const localDateObj = new Date(localToday.getTime() - (localOffset * 60 * 1000));
          const ydate = localDateObj.toISOString().split('T')[0];
          const pdfDir = path.join(__dirname, 'carousel-routine', 'output', ydate, 'carousel-branded', `carousel-${carouselIdx}`);
          let pdfFile = path.join(__dirname, 'slack_downloads', `carousel-${carouselIdx}.pdf`);
          if (fs.existsSync(pdfDir)) {
            const files = fs.readdirSync(pdfDir).filter(f => f.endsWith('.pdf'));
            if (files.length > 0) {
              pdfFile = path.join(pdfDir, files[0]);
            }
          }
          post.assetPath = pdfFile;

          // ---- Phase 1 drift guard --------------------------------------------
          // The carousel index is derived TWICE and independently: here from the
          // post header ("CAROUSEL 2"), and in the generator/builder from a
          // per-format counter that names carousel_data_N.json and carousel-N.pdf.
          // They agree by construction today, and nothing enforces that. Phase 2
          // rewrites the generator, which is exactly when they could drift.
          //
          // A carousel published without its PDF is worse than a failed run, so
          // this aborts rather than falling back to another index's file or
          // silently posting text with no document attached.
          if (!fs.existsSync(post.assetPath)) {
            console.error("\n" + "=".repeat(64));
            console.error("FATAL: carousel asset missing — refusing to schedule.");
            console.error(`  Post header : "${header}"`);
            console.error(`  Derived index: ${carouselIdx}`);
            console.error(`  Expected file: ${post.assetPath}`);
            console.error(`  Also checked : ${pdfDir}`);
            console.error("");
            console.error("  Either the carousel build step did not run, or the header");
            console.error("  index and the generated filename have drifted apart.");
            console.error("  Not falling back to a different file.");
            console.error("Nothing has been scheduled. Aborting.");
            console.error("=".repeat(64) + "\n");
            process.exit(1);
          }
          // -----------------------------------------------------------------------
        } else if (type === 'infographic') {
          let infoIdx = '1';
          const match = header.match(/INFOGRAPHIC\s*(\d+)/i);
          if (match) infoIdx = match[1];

          post.assetPath = path.join(__dirname, `linkedin-infographic-${infoIdx}.png`);
          if (!fs.existsSync(post.assetPath)) {
            const dateStr = new Date().toISOString().split('T')[0].replace(/-/g, '');
            post.assetPath = path.join(__dirname, `linkedin-infographic-${dateStr}.png`);
          }
          
          const bodyLines = body.split('\n');
          // Phase 0b: same emphasis-tolerant extraction as the carousel branch.
          // This marker happens to be plain in every archived run, but the code
          // was identically vulnerable — one bolded emission would publish "**".
          const infographicCaption = extractCaption(bodyLines, ['INFOGRAPHIC CAPTION:', 'Caption:']);
          if (infographicCaption !== null) {
            post.caption = infographicCaption;
          }
        }
        
        posts.push(post);
      }
    }
    
    // ---- Phase 0 date guards ------------------------------------------------
    // Fail closed. Never fall back to "today", never accept a past date, never
    // clamp or silently correct. Any ambiguity aborts before a post is opened.
    const atMidnight = (d) => new Date(d.getFullYear(), d.getMonth(), d.getDate());
    const isoDay = (d) =>
      `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
    const abortSchedule = (title, detail) => {
      console.error("\n" + "=".repeat(64));
      console.error(`FATAL: ${title}`);
      if (detail) console.error(detail);
      console.error("Nothing has been scheduled. Aborting.");
      console.error("=".repeat(64) + "\n");
      process.exit(1);
    };

    let startDateObj;
    const stateFile = path.join(__dirname, 'pipeline_state.json');

    // GUARD A — START_DATE_OFFSET must be a non-negative integer.
    if (process.env.START_DATE_OFFSET !== undefined) {
      const rawOffset = process.env.START_DATE_OFFSET;
      const offset = parseInt(rawOffset, 10);
      if (Number.isNaN(offset)) {
        abortSchedule("START_DATE_OFFSET is not an integer.", `  Got: "${rawOffset}"`);
      }
      if (offset < 0) {
        abortSchedule(
          "START_DATE_OFFSET is negative — this would backdate the batch.",
          `  Got: ${offset}. Refusing to schedule into the past.`
        );
      }
      startDateObj = todayInTimezone();
      startDateObj.setDate(startDateObj.getDate() + offset);
      console.log(`START_DATE_OFFSET=${offset} set — overriding pipeline_state.json.`);

    // GUARD B — pipeline_state.json must exist and be well formed.
    } else {
      if (!fs.existsSync(stateFile)) {
        abortSchedule(
          "pipeline_state.json is missing.",
          `  Expected: ${stateFile}\n` +
          "  This file is the scheduling watermark; without it the batch start\n" +
          "  date cannot be established. Restore it from state-backups/, or set\n" +
          "  START_DATE_OFFSET explicitly if you intend to override it."
        );
      }
      let stateData;
      try {
        stateData = JSON.parse(fs.readFileSync(stateFile, 'utf8'));
      } catch (e) {
        abortSchedule(
          "pipeline_state.json is not valid JSON.",
          `  ${e && e.message ? e.message : e}`
        );
      }
      const rawDate = stateData && stateData.last_scheduled_date;
      if (!rawDate || typeof rawDate !== 'string') {
        abortSchedule(
          "pipeline_state.json has no usable last_scheduled_date.",
          `  Got: ${JSON.stringify(rawDate)}`
        );
      }
      const parts = rawDate.split('-');
      if (parts.length !== 3) {
        abortSchedule(
          "last_scheduled_date is malformed (expected YYYY-MM-DD).",
          `  Got: "${rawDate}"`
        );
      }
      const [yy, mm, dd] = parts.map((n) => parseInt(n, 10));
      const lastDate = new Date(yy, mm - 1, dd);
      if (
        Number.isNaN(lastDate.getTime()) ||
        lastDate.getFullYear() !== yy ||
        lastDate.getMonth() !== mm - 1 ||
        lastDate.getDate() !== dd
      ) {
        abortSchedule(
          "last_scheduled_date is not a real calendar date.",
          `  Got: "${rawDate}"`
        );
      }
      startDateObj = new Date(lastDate);
      startDateObj.setDate(startDateObj.getDate() + 1);
    }

    // GUARD C — however the start date was derived, it must be tomorrow or later.
    const earliestAllowed = todayInTimezone();
    earliestAllowed.setDate(earliestAllowed.getDate() + 1);
    if (atMidnight(startDateObj) < earliestAllowed) {
      abortSchedule(
        "computed batch start date is not in the future.",
        `  Computed start:   ${isoDay(startDateObj)}\n` +
        `  Earliest allowed: ${isoDay(earliestAllowed)} (tomorrow)\n` +
        "  Not clamping. Fix pipeline_state.json or START_DATE_OFFSET and re-run."
      );
    }
    console.log(`Batch start date: ${isoDay(startDateObj)} — date guards passed.`);
    // -------------------------------------------------------------------------

    const formatDate = (d) => {
      const mm = String(d.getMonth() + 1).padStart(2, '0');
      const dd = String(d.getDate()).padStart(2, '0');
      const yyyy = d.getFullYear();
      return `${mm}/${dd}/${yyyy}`;
    };

    // ---- Phase 1: schedule derived from pipeline_config.json ----------------
    // Fill day by day, in time_slots order, until posts_per_batch is reached.
    // With weekdays_only, Saturday and Sunday are skipped entirely, so the batch
    // covers the next N weekday slots whatever day the run happens on.
    // Nothing about the batch shape is declared here any more.
    const schedule = [];
    let firstSlotDate = null;
    for (let dayOffset = 0; dayOffset < BATCH_HORIZON_DAYS && schedule.length < POSTS_PER_BATCH; dayOffset++) {
      const d = new Date(startDateObj);
      d.setDate(d.getDate() + dayOffset);
      if (WEEKDAYS_ONLY && (d.getDay() === 0 || d.getDay() === 6)) continue;
      const dateStr = formatDate(d);
      for (const time of TIME_SLOTS) {
        if (schedule.length >= POSTS_PER_BATCH) break;
        if (schedule.length === 0) firstSlotDate = new Date(d);
        schedule.push({ date: dateStr, time: time });
      }
    }

    // The horizon must actually have held the batch. Without this, a too-narrow
    // window would silently leave trailing posts with undefined date/time and
    // fail mid-run, after earlier posts were already live.
    if (schedule.length < POSTS_PER_BATCH) {
      abortSchedule(
        "the scheduling window is too narrow for this batch.",
        `  Filled ${schedule.length} of ${POSTS_PER_BATCH} slots\n` +
        `  batch_horizon_days: ${BATCH_HORIZON_DAYS}` +
        (WEEKDAYS_ONLY ? " (weekends skipped)" : "") + "\n" +
        `  time_slots per day: ${TIME_SLOTS.length}\n` +
        "  Widen batch_horizon_days in pipeline_config.json."
      );
    }

    // GUARD D — post 1 must land on the weekday its pillar claims.
    // Posts are assigned to slots positionally below, so nothing otherwise ties
    // pillar 1 ("Mon  ad-teardown") to an actual Monday. If the batch starts on
    // a Tuesday, every day label in pipeline_config.json is silently wrong, and
    // because the watermark is derived from the batch it stays wrong for every
    // batch after it.
    const firstPillar = Array.isArray(CONFIG.pillars) ? CONFIG.pillars[0] : null;
    const wantDay = pillarOneWeekday();
    if (wantDay !== undefined && firstSlotDate) {
      const gotDay = firstSlotDate.getDay();
      if (gotDay !== wantDay) {
        abortSchedule(
          `post 1 would publish on a ${DAY_NAME[gotDay]}, not a ${DAY_NAME[wantDay]}.`,
          `  Post 1 slot:     ${isoDay(firstSlotDate)} (${DAY_NAME[gotDay]})\n` +
          `  Pillar 1:        "${firstPillar.day}  ${firstPillar.id}"\n` +
          `  Batch start:     ${isoDay(startDateObj)}\n` +
          "\n" +
          "  Posts are assigned to slots in order, so post 1 carries pillar 1.\n" +
          "  Publishing it on the wrong weekday makes every day label in\n" +
          "  pipeline_config.json wrong, and the next watermark inherits it.\n" +
          "\n" +
          `  Fix: set last_scheduled_date in pipeline_state.json to the day\n` +
          `  before a ${DAY_NAME[wantDay]}, or pass START_DATE_OFFSET so the\n` +
          `  batch starts on one. Nothing has been scheduled.`
        );
      }
    }
    // -------------------------------------------------------------------------

    posts.forEach((p, idx) => {
      if (schedule[idx]) {
        p.date = schedule[idx].date;
        p.time = schedule[idx].time;
      }
    });

    console.log(`Parsed ${posts.length} posts dynamically from linkedin_posts_today.txt!`);
    return posts;
  } catch (err) {
    console.error("\n" + "=".repeat(64));
    console.error("FATAL: could not parse linkedin_posts_today.txt.");
    console.error(`  ${err && err.message ? err.message : err}`);
    console.error("");
    console.error("There is no fallback batch. Nothing has been scheduled.");
    console.error("=".repeat(64) + "\n");
    process.exit(1);
  }
}

// ==========================================
// Batch shape comes from pipeline_config.json.
// Nothing about counts, days or times is declared here.
// ==========================================

(async () => {
  const posts = parseTodayPosts();

  // ---- Phase 0 hard guard -------------------------------------------------
  // There is deliberately NO fallback batch. parseTodayPosts() exits non-zero
  // if linkedin_posts_today.txt is missing or unparseable, so reaching this
  // point with an empty batch means there is nothing legitimate to schedule.
  if (!Array.isArray(posts) || posts.length === 0) {
    console.error("\n" + "=".repeat(64));
    console.error("FATAL: no posts were parsed from linkedin_posts_today.txt.");
    console.error("Nothing has been scheduled. Run the generation step first.");
    console.error("=".repeat(64) + "\n");
    process.exit(1);
  }
  // -------------------------------------------------------------------------

  // ---- Phase 0 checkpointing ----------------------------------------------
  // Each post is written to the checkpoint the moment LinkedIn confirms it,
  // so a crash mid-batch leaves an accurate record of what actually went live.
  const checkpointFile = path.join(__dirname, 'schedule_checkpoint.json');

  const readCheckpoint = () => {
    if (!fs.existsSync(checkpointFile)) return null;
    try {
      return JSON.parse(fs.readFileSync(checkpointFile, 'utf8'));
    } catch (e) {
      console.error("\n" + "=".repeat(64));
      console.error("FATAL: schedule_checkpoint.json exists but is not valid JSON.");
      console.error(`  ${e && e.message ? e.message : e}`);
      console.error("  Cannot determine which posts already went live.");
      console.error("  Inspect it manually before re-running.");
      console.error("Nothing has been scheduled. Aborting.");
      console.error("=".repeat(64) + "\n");
      process.exit(1);
    }
  };

  const writeCheckpoint = (cp) => {
    fs.writeFileSync(checkpointFile, JSON.stringify(cp, null, 2));
  };

  // Startup: refuse to run on top of an interrupted batch. No auto-resume.
  const batchManifest = readManifest();
  if (batchManifest) {
    console.log(`batch_manifest.json: ${batchManifest.posts.length} post(s) declare `
      + `what they consume. Recorded per post as each one is scheduled.`);
  } else {
    console.log('No batch_manifest.json. Nothing will be marked as used - the next '
      + 'batch may repeat this material.');
  }

  const prior = readCheckpoint();
  if (prior && prior.status === 'in_progress' && Array.isArray(prior.completed) && prior.completed.length > 0) {
    const done = prior.completed;
    const doneIds = new Set(done.map(p => p.id));
    console.error("\n" + "=".repeat(64));
    console.error("FATAL: a previous scheduling run did not finish.");
    console.error(`  Batch start date: ${prior.batch_start_date}`);
    console.error(`  Started at:       ${prior.started_at}`);
    console.error(`  Progress:         ${done.length} of ${prior.total_posts} posts scheduled`);
    console.error("");
    console.error("  ALREADY LIVE on LinkedIn (do NOT re-schedule these):");
    done.forEach(p => {
      console.error(`    ✓ post ${p.id} (${p.type})  ${p.date} ${p.time}`);
    });
    const missing = [];
    for (let i = 1; i <= prior.total_posts; i++) if (!doneIds.has(i)) missing.push(i);
    console.error("");
    console.error("  NOT scheduled:");
    if (missing.length === 0) {
      console.error("    (none — batch may have failed after the last post)");
    } else {
      missing.forEach(id => {
        const p = prior.planned && prior.planned.find(x => x.id === id);
        console.error(p ? `    ✗ post ${id} (${p.type})  ${p.date} ${p.time}` : `    ✗ post ${id}`);
      });
    }
    console.error("");
    console.error("  Resolve manually, then delete or edit schedule_checkpoint.json.");
    console.error("  This script will NOT auto-resume.");
    console.error("Nothing has been scheduled. Aborting.");
    console.error("=".repeat(64) + "\n");
    process.exit(1);
  }

  // Open a fresh checkpoint for this batch.
  const checkpoint = {
    status: 'in_progress',
    batch_start_date: posts[0] && posts[0].date,
    started_at: new Date().toISOString(),
    source_file: 'linkedin_posts_today.txt',
    total_posts: posts.length,
    planned: posts.map(p => ({ id: p.id, type: p.type, date: p.date, time: p.time })),
    completed: []
  };
  writeCheckpoint(checkpoint);
  // -------------------------------------------------------------------------

  const screenshotDir = path.join(__dirname, 'slack_downloads');
  let browser;
  try {
    console.log("Launching browser with saved session...");
    browser = await puppeteer.launch({
      headless: false,
      userDataDir: path.join(__dirname, 'chrome-session'),
      defaultViewport: null,
      timeout: 60000,
      args: ['--start-maximized', '--no-sandbox', '--disable-setuid-sandbox']
    });
    let page;
    const pages = await browser.pages();
    if (pages.length > 0 && !pages[0].isClosed()) {
      page = pages[0];
    } else {
      page = await browser.newPage();
    }
    try {
      await page.setViewport({ width: 1280, height: 1200 });
    } catch (e) {
      page = await browser.newPage();
      await page.setViewport({ width: 1280, height: 1200 });
    }

    console.log(`\n${'='.repeat(60)}`);
    console.log(`SCHEDULING ALL ${posts.length} POSTS (${TIME_SLOTS.length}/day over ${BATCH_HORIZON_DAYS} days, ${TIMEZONE})`);
    console.log(`${'='.repeat(60)}\n`);

    for (const post of posts) {
      console.log(`\n${'='.repeat(50)}`);
      console.log(`Scheduling Post ${post.id}/${posts.length} (${post.type}): Date=${post.date}, Time=${post.time}`);
      console.log(`${'='.repeat(50)}`);
      const prefix = `${screenshotDir}/post_${post.id}_${post.type}`;

      // Navigate to feed for clean state
      console.log("Navigating to feed home page...");
      try {
        await page.goto('https://www.linkedin.com/feed/', { waitUntil: 'domcontentloaded', timeout: 30000 });
      } catch (err) {
        console.log("Navigation timeout/error, continuing:", err.message);
      }
      await new Promise(r => setTimeout(r, 4000));

      // Hide messaging overlays
      console.log("Hiding messaging overlays...");
      for (let ret = 0; ret < 5; ret++) {
        try {
          await page.evaluate(() => {
            const style = document.createElement('style');
            style.id = 'hide-msg-overlay-style-' + Date.now();
            style.innerHTML = `
              .msg-overlay-container, 
              [class*="msg-overlay"], 
              #msg-overlay { 
                display: none !important; 
              }
            `;
            (document.head || document.documentElement).appendChild(style);
          });
          break;
        } catch (e) {
          await new Promise(r => setTimeout(r, 1000));
        }
      }

      // Close any open composers
      console.log("Checking and closing any open composers first...");
      await page.evaluate(() => {
        function findDismissBtn(root) {
          if (!root) return null;
          const btn = Array.from(root.querySelectorAll('button')).find(
            b => {
              const label = b.getAttribute('aria-label') || '';
              const txt = b.innerText || '';
              const cls = b.className || '';
              return label.includes('Dismiss') || 
                     txt.includes('Dismiss') ||
                     label.toLowerCase() === 'close' ||
                     cls.includes('close-button');
            }
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
        const dismissBtn = findDismissBtn(document.body);
        if (dismissBtn) dismissBtn.click();
      });
      await new Promise(r => setTimeout(r, 2000));

      console.log("Clicking 'Start a post'...");
      const clickStartPost = await clickNativelyShadowRetry(page, (root) => {
        return Array.from(root.querySelectorAll('*')).find(
          el => (el.tagName === 'BUTTON' || el.getAttribute('role') === 'button' || el.getAttribute('aria-label') === 'Start a post') &&
                el.innerText && el.innerText.trim().includes('Start a post')
        );
      }, 20000);
      if (!clickStartPost) throw new Error("Could not find 'Start a post' button");

      // 2026-08-20: this used to be a same-page modal. It is now a navigation to
      // /sharing/compose, measured at ~9s to become interactive, so 15s was too
      // tight and the extra second afterwards was not enough for the toolbar.
      const editorSelector = '.ql-editor, [contenteditable="true"]';
      await waitForSelectorShadow(page, editorSelector, 45000);
      await new Promise(r => setTimeout(r, 3000));
      console.log(`Composer ready at ${page.url()}`);

      // ========== STEP 1: SET SCHEDULE DATE & TIME FIRST (ON CLEAN COMPOSER) ==========
      console.log(`Setting schedule FIRST on clean composer: Date=${post.date}, Time=${post.time}`);
      let clickedScheduleIcon = false;
      for (let retry = 0; retry < 10; retry++) {
        const clockCoords = await page.evaluate(() => {
          const btns = Array.from(document.querySelectorAll('button, div[role="button"]')).filter(el => {
            if (el.closest && el.closest('[class*="msg-overlay"], #msg-overlay, .msg-overlay-container')) return false;
            const r = el.getBoundingClientRect();
            return r.width > 0 && r.height > 0;
          });

          // 1. Clock icon match
          const clockBtn = btns.find(b => {
            const aria = (b.getAttribute('aria-label') || '').toLowerCase();
            const title = (b.getAttribute('title') || '').toLowerCase();
            const svg = b.querySelector('svg');
            const icon = svg ? (svg.getAttribute('data-test-icon') || svg.getAttribute('data-icon') || '').toLowerCase() : '';
            return aria.includes('schedule') || aria.includes('clock') || aria.includes('later') || title.includes('schedule') || icon.includes('clock') || icon.includes('schedule');
          });
          if (clockBtn) {
            const r = clockBtn.getBoundingClientRect();
            return { x: r.left + r.width / 2, y: r.top + r.height / 2 };
          }

          // 2. Button left of Post
          const postBtn = btns.find(b => (b.innerText || '').trim() === 'Post');
          if (postBtn) {
            const r = postBtn.getBoundingClientRect();
            return { x: r.left - 25, y: r.top + r.height / 2 };
          }

          return null;
        });

        if (clockCoords) {
          await page.mouse.click(clockCoords.x, clockCoords.y);
          console.log(`Clicked Schedule clock icon at coordinates (${Math.round(clockCoords.x)}, ${Math.round(clockCoords.y)})`);
          clickedScheduleIcon = true;
          break;
        }
        await new Promise(r => setTimeout(r, 1000));
      }
      if (!clickedScheduleIcon) throw new Error("Could not find or click Schedule post clock icon");
      await new Promise(r => setTimeout(r, 3000));

      // Fill Date & Time in Schedule Modal using native mouse click & keyboard typing
      const normalizedTime = post.time.startsWith('0') ? post.time.substring(1) : post.time;
      console.log(`Filling schedule modal: Date=${post.date}, Time=${normalizedTime}`);

      const inputCoords = await page.evaluate(() => {
        function findInputsInRoot(root, acc = []) {
          if (!root) return acc;
          const els = Array.from(root.querySelectorAll('input, [role="combobox"], [contenteditable="true"]')).filter(el => {
            const r = el.getBoundingClientRect();
            return r.width > 50 && r.height > 15 && r.top > 50 && r.top < 400 && el.type !== 'hidden';
          });
          acc.push(...els);
          const walker = document.createTreeWalker(root, NodeFilter.SHOW_ELEMENT, null, false);
          let node;
          while (node = walker.nextNode()) {
            if (node.shadowRoot) findInputsInRoot(node.shadowRoot, acc);
          }
          return acc;
        }

        const found = findInputsInRoot(document.body);
        if (found.length >= 2) {
          // Sort by vertical position (top)
          found.sort((a, b) => a.getBoundingClientRect().top - b.getBoundingClientRect().top);
          return found.map(inp => {
            const r = inp.getBoundingClientRect();
            return { x: r.left + 50, y: r.top + r.height / 2 };
          });
        }

        // Fallback: Modal relative offsets
        const allModals = Array.from(document.querySelectorAll('*')).filter(el => {
          const txt = (el.innerText || '').slice(0, 50);
          const r = el.getBoundingClientRect();
          return txt.includes('Schedule post') && r.width > 300 && r.height > 200 && r.top < 200;
        });

        if (allModals.length > 0) {
          const m = allModals[allModals.length - 1];
          const mr = m.getBoundingClientRect();
          return [
            { x: mr.left + 100, y: mr.top + 92 },
            { x: mr.left + 100, y: mr.top + 155 }
          ];
        }

        return null;
      });

      if (!inputCoords || inputCoords.length < 2) {
        throw new Error("Could not find Date and Time input coordinates in schedule modal");
      }

      // 1. Fill Date Input natively
      const dateCoord = inputCoords[0];
      await page.mouse.click(dateCoord.x, dateCoord.y);
      await new Promise(r => setTimeout(r, 200));
      await page.evaluate(() => {
        const inputs = Array.from(document.querySelectorAll('input')).filter(i => i.type !== 'hidden' && i.getBoundingClientRect().top < 400);
        if (inputs.length > 0) {
          inputs[0].focus();
          inputs[0].select();
          inputs[0].value = '';
        }
      });
      await page.keyboard.down('Meta');
      await page.keyboard.press('KeyA');
      await page.keyboard.up('Meta');
      await page.keyboard.press('Backspace');
      for (let i = 0; i < 15; i++) await page.keyboard.press('Backspace');
      await new Promise(r => setTimeout(r, 200));
      await page.keyboard.type(post.date, { delay: 50 });
      await new Promise(r => setTimeout(r, 200));
      await page.keyboard.press('Enter');
      await new Promise(r => setTimeout(r, 200));
      await page.keyboard.press('Tab');
      await new Promise(r => setTimeout(r, 500));

      // 2. Fill Time Input natively
      const timeCoord = inputCoords[1];
      await page.mouse.click(timeCoord.x, timeCoord.y);
      await new Promise(r => setTimeout(r, 200));
      await page.evaluate(() => {
        const inputs = Array.from(document.querySelectorAll('input')).filter(i => i.type !== 'hidden' && i.getBoundingClientRect().top < 400);
        if (inputs.length > 1) {
          inputs[1].focus();
          inputs[1].select();
          inputs[1].value = '';
        }
      });
      await page.keyboard.down('Meta');
      await page.keyboard.press('KeyA');
      await page.keyboard.up('Meta');
      await page.keyboard.press('Backspace');
      for (let i = 0; i < 15; i++) await page.keyboard.press('Backspace');
      await new Promise(r => setTimeout(r, 200));
      await page.keyboard.type(normalizedTime, { delay: 50 });
      await new Promise(r => setTimeout(r, 200));
      await page.keyboard.press('Enter');
      await new Promise(r => setTimeout(r, 200));
      await page.keyboard.press('Tab');
      await new Promise(r => setTimeout(r, 500));

      // 3. Verify values
      const checkVals = await page.evaluate(() => {
        const inputs = Array.from(document.querySelectorAll('input')).filter(i => i.type !== 'hidden' && i.getBoundingClientRect().top < 400);
        return inputs.map(i => i.value);
      });
      console.log("Schedule inputs in DOM after typing:", checkVals);

      await page.screenshot({ path: `${prefix}_schedule_settings.png` });

      // Click Confirm
      console.log("Clicking 'Confirm' button in schedule modal...");
      let clickedConfirm = false;
      for (let retry = 0; retry < 10; retry++) {
        clickedConfirm = await page.evaluate(() => {
          const btns = Array.from(document.querySelectorAll('button')).filter(el => {
            const txt = (el.innerText || '').trim();
            const r = el.getBoundingClientRect();
            return (txt === 'Confirm' || txt === 'Next') && r.width > 0 && r.height > 0 && !el.disabled;
          });
          if (btns.length > 0) {
            btns[0].focus();
            btns[0].click();
            return true;
          }
          return false;
        });

        if (clickedConfirm) {
          console.log("Clicked Confirm button in schedule modal successfully!");
          break;
        }
        await new Promise(r => setTimeout(r, 1000));
      }
      if (!clickedConfirm) throw new Error("Could not click Confirm in schedule modal");
      await new Promise(r => setTimeout(r, 3000));

      // ========== HANDLE ATTACHMENTS ==========
      if (post.type === 'poll') {
        console.log("Handling Poll attachment...");
        await clickNativelyShadow(page, (root) => {
          return Array.from(root.querySelectorAll('button')).find(
            b => (b.ariaLabel && b.ariaLabel.includes('More')) || (b.innerText && b.innerText.includes('More'))
          );
        });
        await new Promise(r => setTimeout(r, 1500));

        const clickedPoll = await clickNativelyShadow(page, (root) => {
          return Array.from(root.querySelectorAll('button')).find(
            b => (b.ariaLabel && b.ariaLabel.includes('Create a poll')) || (b.innerText && b.innerText.includes('Create a poll'))
          );
        });
        if (!clickedPoll) throw new Error("Could not find 'Create a poll' button");
        await new Promise(r => setTimeout(r, 2000));

        // Fill question
        await waitForSelectorShadow(page, 'textarea.polls-detour__question-field, textarea[placeholder*="commute"], textarea[id*="question"]');
        const questionEl = await getElementShadow(page, 'textarea.polls-detour__question-field, textarea[placeholder*="commute"], textarea[id*="question"]');
        await questionEl.focus();
        await page.keyboard.type(post.title);
        await questionEl.dispose();
        console.log("Filled poll question.");

        const options = post.pollOptionsStr.split('|').map(o => o.trim());
        
        const getInputs = async () => {
          const inputsHandle = await page.evaluateHandle(() => {
            function findInputs(root) {
              let found = [];
              const els = root.querySelectorAll('input[id*="poll-option"]');
              for (const el of els) found.push(el);
              const walker = document.createTreeWalker(root, NodeFilter.SHOW_ELEMENT, null, false);
              let node;
              while (node = walker.nextNode()) {
                if (node.shadowRoot) found = found.concat(findInputs(node.shadowRoot));
              }
              return found;
            }
            return findInputs(document.body);
          });
          const properties = await inputsHandle.getProperties();
          const currentInputs = [];
          for (const property of properties.values()) {
            const el = property.asElement();
            if (el) currentInputs.push(el);
          }
          return currentInputs;
        };

        let optionInputs = await getInputs();
        if (optionInputs.length < 2) throw new Error("Option inputs not found");
        
        await optionInputs[0].focus();
        await page.keyboard.type(options[0]);
        await new Promise(r => setTimeout(r, 300));
        
        await optionInputs[1].focus();
        await page.keyboard.type(options[1]);
        await new Promise(r => setTimeout(r, 300));

        if (options[2]) {
          console.log("Adding third option...");
          try {
            await clickNativelyShadow(page, (root) => {
              return Array.from(root.querySelectorAll('button')).find(b => b.innerText && b.innerText.includes('Add option'));
            });
          } catch (e) {
            console.log("Ignored click error for option 3, retrying getInputs:", e.message);
          }
          await new Promise(r => setTimeout(r, 1500));
          
          try {
            optionInputs = await getInputs();
            if (optionInputs.length >= 3) {
              await optionInputs[2].focus();
              await page.keyboard.type(options[2]);
              await new Promise(r => setTimeout(r, 300));
            }
          } catch (e) {
            console.log("Failed to fill option 3:", e.message);
          }
        }

        if (options[3]) {
          console.log("Adding fourth option...");
          try {
            await clickNativelyShadow(page, (root) => {
              return Array.from(root.querySelectorAll('button')).find(b => b.innerText && b.innerText.includes('Add option'));
            });
          } catch (e) {
            console.log("Ignored click error for option 4, retrying getInputs:", e.message);
          }
          await new Promise(r => setTimeout(r, 1500));
          
          try {
            optionInputs = await getInputs();
            if (optionInputs.length >= 4) {
              await optionInputs[3].focus();
              await page.keyboard.type(options[3]);
              await new Promise(r => setTimeout(r, 300));
            }
          } catch (e) {
            console.log("Failed to fill option 4:", e.message);
          }
        }

        // Verify poll options
        console.log("Performing validation check on typed poll options...");
        const verifyVals = await page.evaluate(() => {
          function findInputs(root) {
            let found = [];
            const els = root.querySelectorAll('input[id*="poll-option"]');
            for (const el of els) found.push(el.value.trim());
            const walker = document.createTreeWalker(root, NodeFilter.SHOW_ELEMENT, null, false);
            let node;
            while (node = walker.nextNode()) {
              if (node.shadowRoot) found = found.concat(findInputs(node.shadowRoot));
            }
            return found;
          }
          return findInputs(document.body);
        });
        console.log("Values found in inputs:", verifyVals);
        if (verifyVals.some(v => v === "")) {
          throw new Error("Validation Failed: Some poll option inputs are blank in React state/DOM!");
        }

        await page.screenshot({ path: `${prefix}_filled.png` });

        // Click Done
        console.log("Clicking Done on Poll creator...");
        const clickedPollDone = await clickNativelyShadowRetry(page, (root) => {
          return Array.from(root.querySelectorAll('button')).find(b => {
            const txt = b.innerText ? b.innerText.trim() : '';
            const isVisible = b.offsetWidth > 0 || b.offsetHeight > 0 || window.getComputedStyle(b).display !== 'none';
            const isNotVideoJS = typeof b.className === 'string' && !b.className.includes('vjs-');
            const isDisabled = b.hasAttribute('disabled') || b.disabled || (typeof b.className === 'string' && b.className.includes('disabled'));
            return txt === 'Done' && isVisible && isNotVideoJS && !isDisabled;
          });
        });
        if (!clickedPollDone) throw new Error("Could not click Done on Poll creator");
        await new Promise(r => setTimeout(r, 2000));

      } else if (post.type === 'carousel') {
        console.log("Handling Carousel document upload...");
        await waitForSelectorShadow(page, '.ql-editor, [contenteditable="true"]', 15000);
        await new Promise(r => setTimeout(r, 1500));

        // Step 1: Click '+' button below editor using physical mouse coordinates
        console.log("Clicking '+' detour button below editor to expand toolbar...");
        let clickedPlus = false;
        let lastPlusCoords = null;
        for (let retry = 0; retry < 10; retry++) {
          const coords = await page.evaluate(() => {
            // 2026-08-20: LinkedIn redesigned the composer. The "+" is no longer
            // the 4th icon in a row that can be found by sorting left-to-right;
            // it is a named control. Verified live in the composer at
            // linkedin.com/sharing/compose. Exact label first, old positional
            // heuristics kept below as fallback.
            const exact = Array.from(document.querySelectorAll(
              'button[aria-label], [role="button"][aria-label]'
            )).find(el => {
              const l = (el.getAttribute('aria-label') || '').toLowerCase();
              const r = el.getBoundingClientRect();
              return r.width > 0 && r.height > 0 &&
                (l === 'expand content types' || l.includes('expand content'));
            });
            if (exact) {
              const r = exact.getBoundingClientRect();
              return { x: r.left + r.width / 2, y: r.top + r.height / 2, via: 'aria' };
            }

            const editor = document.querySelector('.ql-editor, [contenteditable="true"]');
            if (!editor) return null;
            const editorRect = editor.getBoundingClientRect();

            // Find all button elements located immediately below the editor (DO NOT include svg to avoid duplication)
            const btns = Array.from(document.querySelectorAll('button, div[role="button"]')).filter(el => {
              if (el.closest && el.closest('[class*="msg-overlay"], #msg-overlay, .msg-overlay-container')) return false;
              if (el.closest && el.closest('.feed-shared-update-v2, .occludable-update, .feed-shared-update')) return false;
              const label = (el.getAttribute('aria-label') || el.ariaLabel || '').toLowerCase();
              if (label.includes('dismiss') || label.includes('close') || label.includes('cancel') || label.includes('post')) return false;
              const r = el.getBoundingClientRect();
              return r.width > 0 && r.height > 0 && r.top >= (editorRect.bottom - 20) && r.top <= (editorRect.bottom + 250);
            });

            // Filter for small icon buttons on the left side of the composer footer (width < 60)
            const toolbarBtns = btns.filter(el => {
              const r = el.getBoundingClientRect();
              return r.width <= 60 && r.left >= (editorRect.left - 50) && r.left <= (editorRect.left + 400);
            });

            // Match by attribute first
            const byAttr = toolbarBtns.find(b => {
              const label = (b.getAttribute('aria-label') || b.ariaLabel || '').toLowerCase();
              const svg = b.querySelector('svg');
              const svgIcon = svg ? (svg.getAttribute('data-icon') || svg.getAttribute('data-test-icon') || '').toLowerCase() : '';
              return label.includes('add to your post') || label.includes('more') || label.includes('overflow') || label.includes('plus') ||
                     svgIcon.includes('plus') || svgIcon.includes('more');
            });
            if (byAttr) {
              const r = byAttr.getBoundingClientRect();
              return { x: r.left + r.width / 2, y: r.top + r.height / 2 };
            }

            // Sort toolbar buttons strictly from left to right
            toolbarBtns.sort((a, b) => a.getBoundingClientRect().left - b.getBoundingClientRect().left);

            // In the bottom toolbar: Index 0=Emoji, Index 1=Media, Index 2=Occasion, Index 3=Plus (+)
            if (toolbarBtns.length >= 4) {
              const r = toolbarBtns[3].getBoundingClientRect();
              return { x: r.left + r.width / 2, y: r.top + r.height / 2 };
            }
            if (toolbarBtns.length > 0) {
              const r = toolbarBtns[toolbarBtns.length - 1].getBoundingClientRect();
              return { x: r.left + r.width / 2, y: r.top + r.height / 2 };
            }
            return null;
          });

          if (coords) {
            await page.mouse.click(coords.x, coords.y);
            console.log(`Clicked '+' button at coordinates (${Math.round(coords.x)}, ${Math.round(coords.y)})`);
            clickedPlus = true;
            lastPlusCoords = coords;
            break;
          }
          await new Promise(r => setTimeout(r, 1000));
        }
        if (!clickedPlus) throw new Error("Could not click '+' detour button");
        await new Promise(r => setTimeout(r, 2000));

        // Step 2: Click Document icon button (8th icon in expanded toolbar)
        console.log("Toolbar expanded! Clicking Document icon button to open 'Share a document' screen...");
        let clickedDoc = false;
        for (let retry = 0; retry < 10; retry++) {
          const docCoords = await page.evaluate((plusY) => {
            // 2026-08-20: after "Expand content types", the Document entry is an
            // <a aria-label="Document">. The old code looked only at <svg> and
            // picked index 7 by horizontal position, which the redesign broke.
            const exactDoc = Array.from(document.querySelectorAll(
              'a[aria-label], button[aria-label], [role="button"][aria-label], [role="menuitem"][aria-label]'
            )).find(el => {
              const l = (el.getAttribute('aria-label') || '').trim().toLowerCase();
              const r = el.getBoundingClientRect();
              return r.width > 0 && r.height > 0 &&
                (l === 'document' || l === 'add a document' || l === 'share a document');
            });
            if (exactDoc) {
              const r = exactDoc.getBoundingClientRect();
              return { x: r.left + r.width / 2, y: r.top + r.height / 2, via: 'aria' };
            }

            // Find all SVGs sitting in the exact same horizontal toolbar row as the plus button
            const svgs = Array.from(document.querySelectorAll('svg')).filter(s => {
              if (s.closest && s.closest('[class*="msg-overlay"], #msg-overlay, .msg-overlay-container')) return false;
              if (s.closest && s.closest('.feed-shared-update-v2, .occludable-update, .feed-shared-update')) return false;
              const r = s.getBoundingClientRect();
              const centerY = r.top + r.height / 2;
              return r.width > 0 && r.height > 0 && Math.abs(centerY - plusY) < 30 && r.left > 150 && r.left < 650;
            });

            // Sort strictly from left to right
            svgs.sort((a, b) => a.getBoundingClientRect().left - b.getBoundingClientRect().left);

            // In the 9-icon expanded toolbar: 0=Emoji, 1=Photo, 2=Occasion, 3=Video, 4=Event, 5=Job, 6=Poll, 7=Document (📄), 8=Close (✖️)
            if (svgs.length >= 8) {
              const r = svgs[7].getBoundingClientRect();
              return { x: r.left + r.width / 2, y: r.top + r.height / 2 };
            }
            if (svgs.length >= 2) {
              const r = svgs[svgs.length - 2].getBoundingClientRect();
              return { x: r.left + r.width / 2, y: r.top + r.height / 2 };
            }
            return null;
          }, lastPlusCoords ? lastPlusCoords.y : 440);

          if (docCoords) {
            await page.mouse.click(docCoords.x, docCoords.y);
            console.log(`Clicked Document icon button at coordinates (${Math.round(docCoords.x)}, ${Math.round(docCoords.y)})`);
            clickedDoc = true;
            break;
          }
          await new Promise(r => setTimeout(r, 1000));
        }
        if (!clickedDoc) throw new Error("Could not click Document icon button");
        await new Promise(r => setTimeout(r, 2500));

        // Step 3: On 'Share a document' screen, upload PDF asset
        console.log("On 'Share a document' screen. Uploading PDF asset...");
        // 2026-08-20 FIX. This step failed on every attempt of the 08/24 batch
        // and scheduled nothing. Root cause: BOTH upload paths searched only the
        // light DOM (`document.querySelector`), while LinkedIn's redesigned
        // "Share a document" dialog renders its file input and its "Choose file"
        // button inside a shadow root. The image path at the bottom of this file
        // already recursed into shadow roots; the document path never did.
        // Both paths below are now shadow-aware. getElementShadow() is the same
        // helper the title lookup uses.
        let uploaded = false;
        for (let attempt = 0; attempt < 10; attempt++) {
          // Path 1: the real <input type=file>, wherever it lives.
          const fileInputEl = await getElementShadow(page, 'input[type="file"]');
          if (fileInputEl) {
            await fileInputEl.uploadFile(post.assetPath);
            await fileInputEl.dispose();
            console.log("Uploaded PDF via input[type='file'] (shadow-aware lookup).");
            uploaded = true;
            break;
          }

          // Path 2: click "Choose file" and catch the native file chooser.
          // The finder recurses into shadow roots and returns a description so
          // the log says what it actually clicked.
          const chooseDesc = await page.evaluate(() => {
            const WANTED = ['choose file', 'upload from computer', 'select file', 'add a document'];
            function find(root) {
              if (!root) return null;
              const els = root.querySelectorAll('button, label, div[role="button"], span, a');
              for (const e of els) {
                const txt = ((e.innerText || '') + ' ' + (e.getAttribute('aria-label') || '')).toLowerCase();
                if (WANTED.some(w => txt.includes(w))) return e;
              }
              const walker = document.createTreeWalker(root, NodeFilter.SHOW_ELEMENT, null, false);
              let node;
              while (node = walker.nextNode()) {
                if (node.shadowRoot) {
                  const found = find(node.shadowRoot);
                  if (found) return found;
                }
              }
              return null;
            }
            const btn = find(document.body);
            if (!btn) return null;
            window.__docChooseBtn = btn;
            return `${btn.tagName} "${(btn.innerText || btn.getAttribute('aria-label') || '').trim().slice(0, 40)}"`;
          });

          if (chooseDesc) {
            console.log(`Found upload control in shadow DOM: <${chooseDesc}>. Intercepting file chooser...`);
            const [fileChooser] = await Promise.all([
              page.waitForFileChooser({ timeout: 8000 }).catch(() => null),
              page.evaluate(() => {
                const btn = window.__docChooseBtn;
                if (!btn) return false;
                btn.scrollIntoView({ block: 'center' });
                btn.click();
                return true;
              })
            ]);
            if (fileChooser) {
              await fileChooser.accept([post.assetPath]);
              console.log("Uploaded PDF via fileChooser.");
              uploaded = true;
              break;
            }
            console.log("  file chooser did not open on that click; retrying...");
          }
          await new Promise(r => setTimeout(r, 1000));
        }

        if (!uploaded) {
          // Say what the dialog actually contained, so a further LinkedIn
          // redesign is diagnosable from the log instead of a screenshot.
          const dump = await page.evaluate(() => {
            function collect(root, out) {
              if (!root) return out;
              const els = root.querySelectorAll('button, label, input, div[role="button"], h2, h3');
              for (const e of els) {
                const t = ((e.innerText || '') + ' ' + (e.getAttribute('aria-label') || '')).trim();
                out.push(`${e.tagName}${e.type ? '[' + e.type + ']' : ''}: ${t.slice(0, 50)}`);
              }
              const walker = document.createTreeWalker(root, NodeFilter.SHOW_ELEMENT, null, false);
              let node;
              while (node = walker.nextNode()) if (node.shadowRoot) collect(node.shadowRoot, out);
              return out;
            }
            return collect(document.body, []).slice(0, 40);
          }).catch(() => []);
          console.error("  Dialog contents (light + shadow DOM):");
          dump.forEach(d => console.error("    " + d));
          throw new Error("Could not upload document: no input[type=file] and no 'Choose file' control found, in light or shadow DOM");
        }

        console.log("Document uploaded. Waiting 4s for processing...");
        await new Promise(r => setTimeout(r, 4000));
        await new Promise(r => setTimeout(r, 4000));

        // Title
        console.log("Waiting for document title field to appear...");
        let titleInputHandle = null;
        for (let waitAttempt = 0; waitAttempt < 30; waitAttempt++) {
          titleInputHandle = await page.evaluateHandle(() => {
            function findTitle(root) {
              if (!root) return null;
              const inputs = Array.from(root.querySelectorAll('input[type="text"], input:not([type]), textarea'));
              for (const inp of inputs) {
                const label = (inp.getAttribute('aria-label') || inp.placeholder || inp.name || inp.id || '').toLowerCase();
                const parentText = (inp.parentElement ? inp.parentElement.innerText : '').toLowerCase();
                if (label.includes('title') || parentText.includes('title') || (typeof inp.className === 'string' && inp.className.includes('title'))) {
                  return inp;
                }
              }
              const walker = document.createTreeWalker(root, NodeFilter.SHOW_ELEMENT, null, false);
              let node;
              while (node = walker.nextNode()) {
                if (node.shadowRoot) {
                  const res = findTitle(node.shadowRoot);
                  if (res) return res;
                }
              }
              return null;
            }
            return findTitle(document.body);
          });

          if (titleInputHandle && titleInputHandle.asElement()) {
            break;
          }
          await new Promise(r => setTimeout(r, 1000));
        }

        if (!titleInputHandle || !titleInputHandle.asElement()) {
          throw new Error("Could not find document title input in light or shadow DOM");
        }

        const titleInput = titleInputHandle.asElement();
        try {
          const realMax = await page.evaluate(el => el.maxLength, titleInput);
          if (realMax && realMax > 0 && realMax !== DOC_TITLE_MAX) {
            console.log(`⚠ LinkedIn title maxLength is ${realMax}, but DOC_TITLE_MAX is ${DOC_TITLE_MAX} — update the constant.`);
          } else if (realMax && realMax > 0) {
            console.log(`Document title maxLength confirmed: ${realMax}`);
          }
        } catch (e) { /* probe only, never fatal */ }
        await titleInput.focus();
        await page.keyboard.type(post.title);
        await titleInput.dispose();
        console.log(`Document title typed (${post.title.length}/${DOC_TITLE_MAX} chars):`, post.title);

        // Verify title
        const titleVal = await page.evaluate(() => {
          function findTitleInput(root) {
            if (!root) return null;
            const inputs = Array.from(root.querySelectorAll('input[type="text"], input:not([type]), textarea'));
            for (const inp of inputs) {
              const label = (inp.getAttribute('aria-label') || inp.placeholder || inp.name || inp.id || '').toLowerCase();
              const parentText = (inp.parentElement ? inp.parentElement.innerText : '').toLowerCase();
              if (label.includes('title') || parentText.includes('title') || (typeof inp.className === 'string' && inp.className.includes('title'))) {
                return inp.value.trim();
              }
            }
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

        await page.screenshot({ path: `${prefix}_doc_uploaded.png` });

        // Click Done after waiting for upload to complete
        console.log("Waiting for document upload to finish (Done button to become enabled)...");
        let doneBtnEnabled = false;
        for (let attempt = 0; attempt < 60; attempt++) {
          const isDoneActive = await page.evaluate(() => {
            function findDone(root) {
              // 2026-08-20: the dialog's Done is an <a>, not a <button>, and the
              // page also contains a HIDDEN <button>Done</button> belonging to
              // the video player's subtitles menu. Searching buttons only found
              // nothing usable, so this loop always timed out. Match anchors and
              // role=button too, and require real visibility.
              const cands = Array.from(root.querySelectorAll('button, a, [role="button"]'))
                .filter(el => (el.innerText || '').trim() === 'Done');
              const b = cands.find(el => {
                if (el.closest && el.closest('.video-js, [class*="video-js"], [class*="vjs-"]')) return false;
                const r = el.getBoundingClientRect();
                return r.width > 0 && r.height > 0;
              });
              if (b) {
                const isDisabled = b.hasAttribute('disabled') || b.disabled || (b.getAttribute('aria-disabled') === 'true') || (typeof b.className === 'string' && b.className.includes('disabled'));
                return !isDisabled;
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
        if (!doneBtnEnabled) {
          throw new Error("Upload timed out or Done button was not enabled.");
        }

        console.log("Clicking Done button on Document uploader...");
        let clickedDocDone = false;
        for (let retry = 0; retry < 10; retry++) {
          clickedDocDone = await page.evaluate(() => {
            const btns = Array.from(document.querySelectorAll('button, a, [role="button"]')).filter(b => {
              const txt = (b.innerText || '').trim();
              if (txt !== 'Done') return false;
              if (b.closest && b.closest('.video-js, [class*="video-js"], [class*="vjs-"]')) return false;
              const r = b.getBoundingClientRect();
              return r.width > 0 && r.height > 0;
            });
            const activeDone = btns.find(b => {
              const isDis = b.hasAttribute('disabled') || b.disabled || (b.getAttribute('aria-disabled') === 'true');
              return !isDis;
            });
            if (activeDone) {
              activeDone.focus();
              activeDone.click();
              return true;
            }
            return false;
          });

          if (clickedDocDone) {
            console.log("Clicked Done button on Document uploader successfully!");
            break;
          }
          await new Promise(r => setTimeout(r, 1000));
        }
        if (!clickedDocDone) throw new Error("Could not click Done on Document uploader");
        await new Promise(r => setTimeout(r, 4000));

      } else if (post.type === 'infographic') {
        console.log("Handling Infographic image upload...");
        const clickedMedia = await clickNativelyShadow(page, (root) => {
          const btns = Array.from(root.querySelectorAll('button'));
          return btns.find(b => b.ariaLabel && b.ariaLabel.includes('Add media')) ||
                 btns.find(b => b.innerText && b.innerText.includes('Add media')) ||
                 btns.find(b => b.innerText && b.innerText.includes('Photo')) ||
                 btns.find(b => b.ariaLabel && b.ariaLabel.includes('Photo'));
        });
        if (!clickedMedia) throw new Error("Could not find image upload button");
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
        if (!fileInputHandle) throw new Error("Could not find file input in shadow DOM");
        const fileInput = fileInputHandle.asElement();
        await fileInput.uploadFile(post.assetPath);
        console.log("Image uploaded. Waiting 4s for processing...");
        await new Promise(r => setTimeout(r, 4000));

        await page.screenshot({ path: `${prefix}_image_uploaded.png` });

        // Click Next/Done in image editor
        const clickedImageNext = await clickNativelyShadowRetry(page, (root) => {
          return Array.from(root.querySelectorAll('button')).find(b => {
            const txt = b.innerText ? b.innerText.trim() : '';
            const isMatch = txt === 'Next' || txt === 'Done';
            const isVisible = b.offsetWidth > 0 || b.offsetHeight > 0 || window.getComputedStyle(b).display !== 'none';
            const isNotVideoJS = typeof b.className === 'string' && !b.className.includes('vjs-');
            const isDisabled = b.hasAttribute('disabled') || b.disabled || (typeof b.className === 'string' && b.className.includes('disabled'));
            return isMatch && isVisible && isNotVideoJS && !isDisabled;
          });
        });
        if (!clickedImageNext) throw new Error("Could not click Next/Done in image editor");
        await new Promise(r => setTimeout(r, 3000));
      }

      // ========== FILL CAPTION ==========
      console.log("Filling post caption text...");
      await waitForSelectorShadow(page, editorSelector, 15000);
      const editorEl = await getElementShadow(page, editorSelector);
      await editorEl.focus();

      // Clear contents
      await page.evaluate((el) => {
        el.focus();
        document.execCommand('selectAll', false, null);
        document.execCommand('delete', false, null);
      }, editorEl);
      await new Promise(r => setTimeout(r, 1000));

      // Type paragraph by paragraph
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
          const el = root.querySelector('.ql-editor, [contenteditable="true"], div[role="textbox"], .editor-content');
          if (el) return (el.innerText || el.textContent || '').trim();
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

      await page.screenshot({ path: `${prefix}_draft_composer.png` });

      await page.screenshot({ path: `${prefix}_final_draft.png` });

      // Click final Schedule
      console.log("Clicking final 'Schedule' button...");
      let clickedScheduleFinal = false;
      for (let retry = 0; retry < 10; retry++) {
        clickedScheduleFinal = await page.evaluate(() => {
          const btns = Array.from(document.querySelectorAll('button, div[role="button"], span[role="button"]')).filter(el => {
            const txt = (el.innerText || el.textContent || '').trim();
            const r = el.getBoundingClientRect();
            return (txt === 'Schedule' || txt.includes('Schedule')) && r.width > 0 && r.height > 0 && !el.disabled;
          });
          if (btns.length > 0) {
            const r = btns[0].getBoundingClientRect();
            const x = r.left + r.width / 2;
            const y = r.top + r.height / 2;
            const target = document.elementFromPoint(x, y) || btns[0];
            target.click();
            return { x, y };
          }
          return null;
        });

        if (clickedScheduleFinal) {
          if (clickedScheduleFinal.x) await page.mouse.click(clickedScheduleFinal.x, clickedScheduleFinal.y);
          console.log("Clicked final Schedule button successfully!");
          break;
        }
        await new Promise(r => setTimeout(r, 1000));
      }
      if (!clickedScheduleFinal) throw new Error("Could not find final 'Schedule' button in composer modal");
      
      console.log("Success! Waiting 6s for scheduling process to complete...");
      await new Promise(r => setTimeout(r, 6000));

      const isClosed = await page.evaluate(() => {
        function findEl(root, sel) {
          if (!root) return null;
          const el = root.querySelector(sel);
          if (el) return el;
          const walker = document.createTreeWalker(root, NodeFilter.SHOW_ELEMENT, null, false);
          let node;
          while (node = walker.nextNode()) {
            if (node.shadowRoot) {
              const found = findEl(node.shadowRoot, sel);
              if (found) return found;
            }
          }
          return null;
        }
        return !findEl(document.body, '.ql-editor');
      });
      if (!isClosed) {
        console.log("Composer editor still open after scheduling, sending Escape key...");
        await page.keyboard.press('Escape');
        await new Promise(r => setTimeout(r, 2000));
      }
      
      console.log(`✓ Successfully scheduled Post ${post.id}/${posts.length}!`);

      // Checkpoint immediately — this post is now live in LinkedIn's scheduler.
      checkpoint.completed.push({
        id: post.id,
        type: post.type,
        date: post.date,
        time: post.time,
        scheduled_at: new Date().toISOString()
      });
      writeCheckpoint(checkpoint);
      console.log(`  checkpoint: ${checkpoint.completed.length}/${posts.length} recorded`);

      // Now, and only now, is this material genuinely spent.
      if (batchManifest && batchManifest.posts[post.id - 1]) {
        recordConsumption(batchManifest.posts[post.id - 1]);
      }
    }

    console.log(`\n${'='.repeat(60)}`);
    console.log(`✓ ALL ${posts.length} POSTS HAVE BEEN SCHEDULED SUCCESSFULLY!`);
    console.log(`${'='.repeat(60)}`);

    // Mark the batch complete BEFORE advancing the watermark, so a failure
    // between the two is visible rather than silent.
    checkpoint.status = 'complete';
    checkpoint.completed_at = new Date().toISOString();
    writeCheckpoint(checkpoint);

    try {
      const stateFile = path.join(__dirname, 'pipeline_state.json');
      const lastPost = posts[posts.length - 1];
      const parts = lastPost.date.split('/');
      const lastPostDate = new Date(
        parseInt(parts[2], 10), parseInt(parts[0], 10) - 1, parseInt(parts[1], 10));

      // The watermark is anchored to the next pillar-1 weekday, NOT to the last
      // post's date. A full 5-post batch ends Friday and rolls to Monday on its
      // own; a SHORT batch does not. Four posts end Thursday, so a last-post
      // watermark would start the next batch on Friday, publishing Monday's
      // ad-teardown on a Friday and every label after it wrong - permanently,
      // since nothing pulls it back. Short batches are not hypothetical; they
      // happened repeatedly in testing. So: advance to the day BEFORE the next
      // pillar-1 weekday, whatever the batch length.
      const wd = pillarOneWeekday();
      const anchorDay = wd === undefined ? 1 : wd;
      const nextAnchor = new Date(lastPostDate);
      do {
        nextAnchor.setDate(nextAnchor.getDate() + 1);
      } while (nextAnchor.getDay() !== anchorDay);
      const watermark = new Date(nextAnchor);
      watermark.setDate(watermark.getDate() - 1);
      const lastDateIso = isoDayOf(watermark);
      fs.writeFileSync(stateFile, JSON.stringify({
        last_scheduled_date: lastDateIso,
        last_updated: new Date().toISOString()
      }, null, 2));
      console.log(`Saved pipeline state memory: watermark ${lastDateIso}, so the `
        + `next batch starts ${isoDayOf(nextAnchor)} (${DAY_NAME[anchorDay]}).`);
      console.log(`  Last post in this batch: ${isoDayOf(lastPostDate)}. The `
        + `watermark is anchored to the next ${DAY_NAME[anchorDay]}, not to that `
        + `date, so a short batch cannot shift the schedule.`);
    } catch (e) {
      console.error("Error updating pipeline_state.json:", e);
    }
    console.log("\nSchedule Summary:");
    posts.forEach(p => {
      console.log(`  ${p.date} ${p.time}  ${p.type}${p.title ? "  — " + p.title : ""}`);
    });
    process.exit(0);

  } catch (err) {
    console.error("Automator Exception:", err);
    try {
      if (browser) {
        const errPages = await browser.pages();
        const errPage = errPages.find(p => p.url().includes('linkedin.com')) || errPages[0];
        if (errPage) {
          await errPage.screenshot({ path: path.join(__dirname, 'error_screenshot.png') });
          console.log("Saved error screenshot.");
        }
        await browser.close();
      }
    } catch (screenErr) {
      console.error("Failed to capture error screenshot:", screenErr);
    }
    process.exit(1);
  }
})();
