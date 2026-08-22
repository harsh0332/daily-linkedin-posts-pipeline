// Loader + validator for pipeline_config.json (Node side).
//
// Mirror of config_loader.py. Both read the SAME file; neither re-declares any
// value. If you change the validation rules here, change them there too.

const fs = require('fs');
const path = require('path');

const CONFIG_PATH = path.join(__dirname, 'pipeline_config.json');

function abortConfig(title, detail) {
  console.error('='.repeat(64));
  console.error(`FATAL: ${title}`);
  if (detail) console.error(detail);
  console.error('Nothing has been generated or scheduled. Aborting.');
  console.error('='.repeat(64));
  process.exit(1);
}

// Fewest Mon-Fri days in any window of `days` consecutive calendar days.
// Computed exactly by trying all seven possible start weekdays rather than with
// a formula, so it cannot be subtly wrong. Mirror of config_loader.py.
function minWeekdaysInWindow(days) {
  let worst = null;
  for (let start = 0; start < 7; start++) { // 0 = Monday
    let count = 0;
    for (let i = 0; i < days; i++) if ((start + i) % 7 < 5) count++;
    worst = worst === null ? count : Math.min(worst, count);
  }
  return worst || 0;
}

function loadConfig(configPath) {
  const p = configPath || CONFIG_PATH;
  if (!fs.existsSync(p)) {
    abortConfig('pipeline_config.json is missing.', `  Expected: ${p}`);
  }
  let cfg;
  try {
    cfg = JSON.parse(fs.readFileSync(p, 'utf8'));
  } catch (e) {
    abortConfig('pipeline_config.json is not valid JSON.', `  ${e && e.message ? e.message : e}`);
  }

  const posts = cfg.posts_per_batch;
  const horizon = cfg.batch_horizon_days;
  const mix = cfg.format_mix || {};
  const order = cfg.format_order || [];
  const slots = cfg.time_slots || [];

  if (!Number.isInteger(posts) || posts < 0) {
    abortConfig('posts_per_batch must be a non-negative integer.', `  Got: ${JSON.stringify(posts)}`);
  }
  if (!Number.isInteger(horizon) || horizon < 1) {
    abortConfig('batch_horizon_days must be a positive integer.', `  Got: ${JSON.stringify(horizon)}`);
  }
  if (!Array.isArray(slots) || slots.length === 0) {
    abortConfig('time_slots must be a non-empty array.', `  Got: ${JSON.stringify(slots)}`);
  }

  // RULE 1 — the mix must add up to the batch size.
  const total = Object.values(mix).reduce((a, b) => a + Number(b), 0);
  if (total !== posts) {
    abortConfig(
      'format_mix does not sum to posts_per_batch.',
      `  format_mix: ${JSON.stringify(mix)}\n` +
      `  sum: ${total}\n` +
      `  posts_per_batch: ${posts}\n` +
      '  Fix pipeline_config.json so the two agree.'
    );
  }

  // RULE 2 — there must be enough slots to place every post.
  // With weekdays_only, capacity is the WORST-CASE weekday count in a window of
  // `horizon` calendar days (worst case = the window starting on a Saturday).
  const weekdaysOnly = cfg.weekdays_only === true;
  const usableDays = weekdaysOnly ? minWeekdaysInWindow(horizon) : horizon;
  const capacity = usableDays * slots.length;
  if (capacity < posts) {
    abortConfig(
      'not enough posting slots for the batch.',
      `  batch_horizon_days: ${horizon}` +
      (weekdaysOnly ? ` (worst case ${usableDays} weekdays)` : '') +
      `\n  time_slots: ${slots.length}\n` +
      `  capacity: ${capacity}\n` +
      `  posts_per_batch: ${posts}\n` +
      '  Widen batch_horizon_days or add a time slot.'
    );
  }

  // RULE 3 — every format in the mix must appear in the ordering.
  const missing = Object.keys(mix).filter(k => order.indexOf(k) === -1);
  if (missing.length) {
    abortConfig('format_order is missing formats present in format_mix.', `  Missing: ${JSON.stringify(missing)}`);
  }

  return cfg;
}

// Round-robin over format_order, skipping exhausted formats.
// Returns [{ format, index }] where index is the per-format counter from 1.
function buildSlotSequence(cfg) {
  const mix = cfg.format_mix || {};
  const order = (cfg.format_order || []).filter(f => Number(mix[f] || 0) > 0);
  const remaining = {};
  const counters = {};
  order.forEach(f => { remaining[f] = Number(mix[f]); counters[f] = 0; });
  const seq = [];
  const left = () => order.reduce((a, f) => a + remaining[f], 0);
  while (left() > 0) {
    for (const f of order) {
      if (remaining[f] > 0) {
        remaining[f] -= 1;
        counters[f] += 1;
        seq.push({ format: f, index: counters[f] });
      }
    }
  }
  return seq;
}

module.exports = { loadConfig, buildSlotSequence, abortConfig, minWeekdaysInWindow, CONFIG_PATH };
