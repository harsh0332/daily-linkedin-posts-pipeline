# PHASE-1-REPORT.md

Cadence, format mix and single config source. Applied 2026-08-09. Companion to [`PIPELINE-AUDIT.md`](PIPELINE-AUDIT.md) and [`PHASE-0-REPORT.md`](PHASE-0-REPORT.md).

**Scope honoured:** no prompt wording, `writing_rules`, voice file, hook style or tone instruction was changed. The pipeline was never run; Chrome was never opened; LinkedIn was never touched. All testing ran in a session scratchpad with Puppeteer stubbed and network calls blocked.

**Baseline:** `05e6c25` (end of Phase 0b). Phase 1 is five commits, `02bc40a` → this one.

---

## Task 1 — One source of truth (committed separately, values unchanged)

`02bc40a`. The format mix was expressed in five places and the posting schedule in six, across three languages, with every mismatch failing silently.

| New file | Purpose |
|---|---|
| `pipeline_config.json` | posts per batch, horizon, weekdays flag, format order, format mix, time slots, timezone |
| `config_loader.py` / `config_loader.cjs` | one loader per language, same file, identical startup assertions |

Consumers, none of which now declare a value:

| File | Was | Now |
|---|---|---|
| `generate_all_content.py` | 58-line hard-coded JSON skeleton | Built from config via round-robin over `format_order` |
| `schedule_all_posts.cjs` | 11-entry literal `schedule` array | Filled day by day from `time_slots` |
| `send_to_slack.py` | Hand-maintained mirror | Derived from the same file |
| `build_carousel_today.cjs` | `idx <= 3` | `format_mix.carousel` |
| `cap_infographic_today.js` | `idx <= 3` | `format_mix.infographic` |

**Proof nothing changed:** the rendered planning prompt is **byte-identical**, 3,587 chars, sha256 `3b33b476…` before and after. The schedule produced the same 4/4/3 pattern and slot order. The Slack dry run matched Phase 0's output exactly.

Per-slot descriptor strings ("Carousel #1 Workflow Topic", "Curiosity Gap", …) are unchanged prompt wording, moved into a `SLOT_TEMPLATES` data structure so the skeleton can be built for any mix.

---

## Task 2 — The new numbers

`fadc0d7`. `pipeline_config.json` only, plus two zero-count guards.

| Knob | Was | Now |
|---|---|---|
| `posts_per_batch` | 11 | **5** |
| `batch_horizon_days` | 3 | **7** |
| `weekdays_only` | — | **true** |
| `format_mix` | 3 carousel / 3 infographic / 2 poll / 3 text | **2 carousel / 0 infographic / 0 poll / 3 text** |
| `time_slots` | 9:00 / 12:00 / 15:00 / 18:00 | **9:30 AM** |
| `timezone` | present, unused | **Asia/Kolkata**, used |

Resulting slot order: **CAROUSEL, TEXT, CAROUSEL, TEXT, TEXT**.

The rationale (median 51 impressions, ~half of posts with zero engagement, 8 polls → 9 reactions and 2 comments, infographics lowest-reach, carousels strongest) is recorded in the config file itself.

**Zero counts verified end to end. Nothing deleted; both formats are unused, not unavailable.**

- Generator: skeleton renders 5 slots, no `INFOGRAPHIC` or `POLL` keys, 2 carousel JSONs, 0 infographic JSONs.
- `cap_infographic_today.js`: returns **before** launching Chrome. Verified with a stub that exits 9 if `launch()` is reached — it never was.
- `build_carousel_today.cjs`: same guard for symmetry; with count 2 it proceeds normally.
- Scheduler: 2 carousel + 3 regular; poll and infographic branches never entered.
- Slack: reviews 5 posts; infographic upload skipped with an explicit log line.

---

## Task 3 — Everything that assumed 11

`e2d40ca`. Listed in full before any change, split by severity.

### Category A — wrong behaviour

| Location | Fix |
|---|---|
| `send_to_slack.py` window | Was `start + timedelta(days=2)`, a silent mirror of the old 3-day horizon. It showed `Fri 21 to Sun 23 Aug` while scheduling through **Tue 25**. Now derived from `build_slot_dates()` and read off the real first and last slot. |
| `send_to_slack.py` infographic upload | Attempted even at count 0, logging `file not found` every run and masking a genuine missing-asset error later. Now skipped with an explicit message. |

### Category B — stale output and comments, all now derived

Three `11 posts` log lines in the generator; `beyond the 11-post window`; the daily-PDF Slack caption; the `ALL 11 POSTS / 4 per day / 3 days` comment block; the run banner's stale parenthetical; and the end-of-run summary that printed **June 13–15** dates and eight obsolete post types (now prints the actual scheduled posts).

### Position independence — confirmed

The old "carousel first each day" pattern is gone and **nothing depended on it**. A carousel's PDF index comes from the header (`/CAROUSEL\s*(\d+)/i`), never from array position:

```
pos 1  carousel → carousel-1.pdf   (header "1. CAROUSEL 1")
pos 3  carousel → carousel-2.pdf   (header "3. CAROUSEL 2")
```

### New drift guard

The carousel index is derived twice and independently — from the header in the scheduler, and from a per-format counter in the generator/builder. They agreed by construction and nothing enforced it; Phase 2 rewrites the generator, which is exactly when they could drift. The scheduler now verifies the resolved PDF exists and **aborts** naming the header, the derived index and the expected filename. It does not fall back to another index's file: a carousel published without its PDF is worse than a failed run.

Verified in three states — no PDFs (aborts on `"1. CAROUSEL 1"`), both present (passes), only `carousel-1.pdf` present (aborts naming **`"3. CAROUSEL 2"`**).

---

## Task 4 — Weekday-only scheduling and explicit timezone

`c441272`. Weekends are skipped entirely, so a batch covers the next 5 weekday slots whatever day the run happens on.

```
batch starts Mon 17 Aug  ->  Mon 17  Tue 18  Wed 19  Thu 20  Fri 21   ✓
batch starts Tue 18 Aug  ->  Tue 18  Wed 19  Thu 20  Fri 21  Mon 24   ✓
batch starts Wed 19 Aug  ->  Wed 19  Thu 20  Fri 21  Mon 24  Tue 25   ✓
batch starts Thu 20 Aug  ->  Thu 20  Fri 21  Mon 24  Tue 25  Wed 26   ✓
batch starts Fri 21 Aug  ->  Fri 21  Mon 24  Tue 25  Wed 26  Thu 27   ✓
batch starts Sat 22 Aug  ->  Mon 24  Tue 25  Wed 26  Thu 27  Fri 28   ✓
batch starts Sun 23 Aug  ->  Mon 24  Tue 25  Wed 26  Thu 27  Fri 28   ✓
```

Zero weekend hits in all seven cases.

**Guard C still holds.** A watermark yielding today aborts; one yielding tomorrow passes. Weekend-skipping only ever moves the first real slot *later*, never earlier — conservative in the safe direction.

**Two additions beyond the literal ask, both approved:**

1. **Window-capacity assert after the fill loop.** Without it a too-narrow horizon leaves trailing posts with `undefined` date/time and fails mid-run, after earlier posts are already live — the exact failure Phase 0's checkpoint exists to contain.
2. **The loader's capacity rule is weekday-aware**, using the worst-case weekday count across all seven possible start days, computed by simulation rather than a formula that could be subtly wrong. A 7-day window always yields exactly 5 weekdays. `batch_horizon_days: 5` now correctly aborts: `capacity 3 < 5 posts`.

**Timezone — register item 13 closed.** `"today"` is now the calendar date in `Asia/Kolkata` in both languages (`Intl.DateTimeFormat` / `zoneinfo`), falling back to system local with a warning. This is the one place it matters: Guard C compares the batch start against tomorrow.

---

## Task 5 — Full dry run

| Check | Result |
|---|---|
| Format assertions on mismatch | All three fire in both languages: mix sums to 6 vs 5; horizon 5 → capacity 3; unknown format missing from `format_order` |
| Phase 0 guards, real `pipeline_state.json` | **Guard C aborts** — watermark `2026-08-07` → start `2026-08-08`, earliest allowed `2026-08-10`. Correct; the watermark is stale (see the protocol) |
| Phase 0 guards, corrected watermark | Passes. Missing state, corrupt JSON, malformed date, missing posts file, carousel drift, interrupted checkpoint — all abort correctly |
| State files | `.env`, `pipeline_state.json`, `used_topics.json`, `linkedin_posts_today.txt`, `chrome-session/` all byte-identical |

### Review-message readability — two fixes applied

The first full dry run was **6 messages, 5,997 chars**. The three text posts were fine at 9 lines each; the carousels dumped all seven slides plus the caption (21–27 lines), and more than half that volume was content that only ever reaches the PDF.

**Fix 1 — carousel preview.** Now shows the `Hook:` line (which becomes the LinkedIn document title, the largest text in the feed, so it must be seen before approval), slide 1's text, and the **full caption**, with slides 2–N collapsed to one pointer line:

```
*Doc title:* Why cut a winning product?
*Slide 1:* Why cut a winning product?
_… slides 2-7 (6 more) are in the attached PDF → carousel-1.pdf_

*Caption (this is the post text that publishes):*
Curiosity piqued? Discover why cutting a 'winning' product might actually…
```

**Fix 2 — one PDF per carousel (a genuine defect, not a polish item).** A single PDF was uploaded regardless of how many carousels the batch contained, so with 2 carousels one would be approved and the other published unseen — and carousels are where every Phase 0 bug turned up. Resolution now mirrors the scheduler exactly (dated output subdirectory, then `slack_downloads/`), one upload per carousel, captioned `CAROUSEL PDF 1 of 2 — post 1`.

If a PDF for an expected index is missing, Slack gets a **loud message** rather than silently fewer files:

```
🚨 *CAROUSEL PDF MISSING — do not run the scheduler*
1 of 2 carousel PDFs could not be found:
  • post 3 → expected `carousel-2.pdf` (checked `…/carousel-2/` and `slack_downloads/`)
```

Implementing this surfaced that Python's `is_marker()` is an *equality* test, so a `Hook: <text>` line never matched. Added `marker_remainder()`, the Python mirror of the JS `markerRemainder()`, including the colon-separator requirement. Verified identical on all four cases, including rejecting `"Hooks that convert are short"`.

**Result: 6 messages, 4,843 chars** (−19%); carousel messages roughly halved. Threading was considered and rejected — it adds a tap on mobile.

---

## Task 6 — Live test protocol (manual; not executed)

> Work top to bottom. Steps 1–3 are prerequisites; do not skip step 2.

### Step 0 — Scheduled queue: already clear

You confirmed LinkedIn's scheduled queue is **empty** — all old 4/day posts have published, nothing pending. So there is no old-cadence backlog to collide with the new schedule, and no queue to clear. Nothing to do here; recorded so the assumption is explicit.

If that ever stops being true, check `linkedin.com/feed/` → *Start a post* → clock icon → *View all scheduled posts* before running.

### Step 1 — Set the watermark

**Why it needs changing:** `pipeline_state.json` currently reads `last_scheduled_date: 2026-08-07`. The batch start is `watermark + 1` = `2026-08-08`, which is in the past, so Guard C aborts every run. This is the guard working correctly, not a fault.

**The rule:** set `last_scheduled_date` to **the day before you want the first post**, and it must be **≥ today's date in IST** (otherwise the start is not in the future and Guard C aborts).

**The simplest correct value: today's IST date.** The first post then lands tomorrow, and if tomorrow is a weekend the first slot rolls forward to Monday automatically.

| If you run on | Set `last_scheduled_date` to | First batch lands |
|---|---|---|
| Sun 2026-08-09 | `2026-08-09` | Mon 10, Tue 11, Wed 12, Thu 13, Fri 14 Aug |
| Mon 2026-08-10 | `2026-08-10` | Tue 11, Wed 12, Thu 13, Fri 14, Mon 17 Aug |
| Fri 2026-08-14 | `2026-08-14` | Mon 17, Tue 18, Wed 19, Thu 20, Fri 21 Aug |

Edit the file by hand, changing only that field:

```bash
python3 - <<'EOF'
import json
p = "pipeline_state.json"
s = json.load(open(p))
s["last_scheduled_date"] = "2026-08-09"   # <-- the day BEFORE your first post
json.dump(s, open(p, "w"), indent=2)
print(s)
EOF
```

**Getting it wrong is asymmetric — this matters:**

- **Too far in the past** (e.g. leaving it at `2026-08-07`): Guard C aborts, nothing is scheduled, no damage. You simply cannot run until you fix it. **Safe.**
- **Too far in the future** (e.g. `2026-12-01`): **no guard fires.** The batch schedules into December, the posts sit in LinkedIn's queue for months, and the watermark then advances to December so *every subsequent run* schedules further out still. Recovery means deleting the scheduled posts in LinkedIn **and** manually resetting the watermark. **This is the dangerous direction.**

**Self-sustaining afterwards:** the scheduler writes the last post's date back to the watermark. After a Mon–Fri batch it holds Friday's date, so a run the following weekend starts Saturday and rolls to Monday — a clean weekly Mon–Fri cadence with no manual edits.

### Step 2 — Back up the watermark before any test run

⚠️ **A test run advances the real watermark.** `schedule_all_posts.cjs` writes `last_scheduled_date` from the last scheduled post unconditionally — it does not know the run was a test. With `START_DATE_OFFSET=60` the watermark ends up ~2 months out, and the next real run inherits that.

```bash
cp pipeline_state.json state-backups/pipeline_state.pre-test.json
```

Restore it immediately after the test (step 4).

### Step 3 — The test run

```bash
START_DATE_OFFSET=60 python3 run_pipeline.py
```

60 days puts the batch ~2 months out, far from any real date, and clear of the empty queue.

**What you should see in Slack:**

- A header: `*5 posts* for review (2 carousel, 3 regular)` and a scheduling window ~2 months out, **Monday–Friday only**
- Five post messages, numbered `POST 1 of 5` … `POST 5 of 5`, in the order **CAROUSEL, TEXT, CAROUSEL, TEXT, TEXT**
- Each carousel showing `*Doc title:*` with real hook text (not `_(no Hook line …)_`), `*Slide 1:*`, the pointer line, and the full caption
- **Two** carousel PDF uploads: `CAROUSEL PDF 1 of 2 — post 1` and `CAROUSEL PDF 2 of 2 — post 3`
- **No** infographic upload, and no poll

**What indicates failure:**

| Symptom | Meaning |
|---|---|
| 🚨 `CAROUSEL PDF MISSING` | The carousel build step did not run. Do not proceed; the scheduler will abort anyway |
| Any weekend date in the window | Weekday logic failed — stop and report |
| `_(no Hook line — will fall back to caption text)_` | The generator did not emit a `Hook:` line; titles will be truncated caption text |
| Fewer than 5 posts, or a poll/infographic appearing | Config and generator disagree |
| `FATAL:` anywhere | Read the message; it names the file and the expected value |

### Step 4 — Clean up the test posts

Because the queue was empty beforehand, the **only** things scheduled will be your 5 test posts.

Manually, which is the safe route: LinkedIn → *Start a post* → clock icon → *View all scheduled posts* → delete all five.

`delete_all_scheduled.cjs` exists and would do it in one go, but **it has no date guard and deletes every scheduled post it can reach**. That is acceptable *only* in this specific window, while the queue contains nothing but your test posts. Never use it once real posts are queued.

Then restore the watermark:

```bash
cp state-backups/pipeline_state.pre-test.json pipeline_state.json
cat pipeline_state.json
```

Also clear the checkpoint so the next run does not see an old batch:

```bash
rm -f schedule_checkpoint.json
```

### Step 5 — The first real run

Set the watermark per step 1, then:

```bash
python3 run_pipeline.py
```

No `START_DATE_OFFSET`. Review Slack **before** the scheduler step reaches LinkedIn.

### Step 6 — What to check in the run log

Two things Phase 0b left open, both answered by the first real run:

1. **The `maxLength` probe.** During each carousel's document-title step the scheduler reads LinkedIn's real limit. Look for either:
   - `Document title maxLength confirmed: 58` — `DOC_TITLE_MAX` is right, nothing to do
   - `⚠ LinkedIn title maxLength is N, but DOC_TITLE_MAX is 58 — update the constant` — change `DOC_TITLE_MAX` at `schedule_all_posts.cjs:268` to `N`

   Also check `Document title typed (NN/58 chars):` — the number before the slash is the real title length.

2. **The first `Hook:` line on disk.** `slide_1_hook` was never persisted before Phase 0b, so hook lengths were only ever estimated from proxies (25–33 chars). Confirm it is now real:

   ```bash
   grep -n "^Hook: " linkedin_posts_$(date +%Y%m%d).txt
   awk '/^Hook: /{print length($0)-6, $0}' linkedin_posts_$(date +%Y%m%d).txt
   ```

   Every value should be comfortably under 58. If any exceeds it, the title truncation logic handles it, but tell me — it means the `6-8 words max` planning instruction is slipping.

3. **Checkpoint completeness.** After the run:

   ```bash
   python3 -c "import json; d=json.load(open('schedule_checkpoint.json')); print(d['status'], len(d['completed']), 'of', d['total_posts'])"
   ```

   Expect `complete 5 of 5`. Anything else means the batch was interrupted and the next run will refuse to start until you resolve it.

---

## Task 8 — Disable unread performance-post generation

Added after Task 7, once the facts were established.

### What they actually were

`generate_all_content.py` was the **only** writer of `performance_posts_<date>.txt`. A full-repo grep found **no reader in any executable code**:

| Consumer | Reads |
|---|---|
| `schedule_all_posts.cjs` | `linkedin_posts_today.txt` — only |
| `send_to_slack.py` | `linkedin_posts_today.txt`, falling back to the dated file — only |
| `run_pipeline.py` | no step references it |

So they were **never published**, and the Phase 1 volume reduction was real: 5 posts per batch, one per weekday. They were also entirely outside the config — a hard-coded 5-element Python literal with five fixed topics unchanged since June, invisible to `format_mix`, `time_slots` and every startup assertion.

### Two reasons to cut, one of them a real availability risk

1. **~40% of every run produced a file nothing reads.** That share *rose* when Phase 1 cut the main batch: 5 of 23 calls (22%) before, 5 of 13 (38%) after.
2. **A post that can never be published could abort the entire batch.** The block ran **last** and had `sys.exit(1)` on failure — after `linkedin_posts_today.txt`, `used_topics.json` and the carousel JSONs were all written. One failed performance post therefore exited non-zero, `run_pipeline.py` aborted at step 2, and steps 3–7 never ran: no carousels built, nothing to Slack, nothing scheduled — with topics already burned.

### The change

New config flag, defaulted off, the same "unused not unavailable" pattern used for polls and infographics:

```json
"generate_performance_posts": false
```

The 74-line block is **intact and unmodified**, wrapped in `if not GENERATE_PERFORMANCE_POSTS: … else:`. With the flag off it prints one line and writes nothing. Flipping the flag to `true` restores the previous behaviour exactly — verified.

### Measured saving

| | Calls | Prompt chars |
|---|---|---|
| Flag **on** (old behaviour) | 13 | 39,414 |
| Flag **off** (new default) | **8** | **23,002** |
| Saving | **−5 calls (−38%)** | **−16,412 chars (−42%)** |

### Downstream verified with the flag off

- Generator exits **0** — `run_pipeline.py` step 2 completes, so steps 3–7 run.
- No `performance_posts_*.txt` is written.
- Slack gate unaffected: parses 5 posts, `2 carousel, 3 regular`, both PDFs resolved.
- Scheduler unaffected: parses 5 posts, `carousel, regular, carousel, regular, regular`.
- No code path expects the file to exist.

### Archives kept

The five existing `performance_posts_2026*.txt` files are untouched on disk and still git-tracked, as history.

---

## Carried into Phase 2

Line numbers verified against the working tree at this commit.

### Closed by Phase 1

| Was | Now |
|---|---|
| #4 — posting schedule in six places | **Closed.** One config file; every consumer reads it |
| #6 — format mix in five uncoordinated places | **Closed.** Derived from `format_mix` + `format_order` |
| #7 — stale `ALL 11 POSTS / 4 per day` comment | **Closed.** Replaced with a pointer to the config |
| #8 — end-of-run summary with June 13–15 dates | **Closed.** Prints the actual scheduled posts |
| #13 — no timezone handling | **Closed.** `Asia/Kolkata` explicit in both languages |
| #21 — poll truncation silent | **Moot.** Polls are at count 0 (code intact) |
| Single carousel PDF uploaded | **Closed.** One per carousel, with loud reporting of any missing |
| #18 — 5 hard-coded performance posts generated every run | **Closed.** Behind `generate_performance_posts: false`. They were never published; ~40% of run cost removed, and the abort-the-whole-batch path with it |

### Still open

| # | Item | Location |
|---|---|---|
| 1 | **Marker format not pinned in the prompt.** The model bolds `**CAROUSEL CAPTION:**` ~59% of the time. Both consumers tolerate it; the cause is prompt wording. | `generate_all_content.py:357` |
| 2 | **`content-doctrine.md` and `voice-profile.md` are not read by the pipeline.** The live voice is the `writing_rules` string. Editing the markdown changes nothing. | `generate_all_content.py:106-133` |
| 3 | **`skills/branded-carousel/SKILL.md` is executable**, not documentation — slide templates are regex-extracted from its `TEMPLATE N` headings at runtime. | `generate_carousel_today.py:54-63` |
| 5 | **Marker normalisation duplicated across JS and Python**, now three functions deep. Reciprocal `⚠ KNOWN DUPLICATION` comments name each other. | `schedule_all_posts.cjs:198` ↔ `send_to_slack.py:335` |
| 9 | `README.md` describes a generator that no longer exists and references six state files that do not exist. **Now also wrong about cadence and mix.** | `README.md:212-241` |
| 10 | `skills/illustration-formats/SKILL.md` mandates `@founderswing` and a "future of work" lane, contradicting the doctrine. Three brand identities coexist. | `skills/illustration-formats/SKILL.md:10,67` |
| 11 | **`DOC_TITLE_MAX = 58` still unverified.** The probe now exists; the first real run answers it. | `schedule_all_posts.cjs:268`, probe at `:1075` |
| 12 | `TITLE_MIN_CLAUSE = 20` is a judgement call. | `schedule_all_posts.cjs:281` |
| 14 | **`delete_all_scheduled.cjs` has no date guard** — deletes every scheduled post it can reach. Safe only while the queue is empty. | `delete_all_scheduled.cjs:130-208` |
| 15 | **`ai_news_data.json` is stale** (2026-07-25) and nothing refreshes it, yet it is fed to the planner every run as "Fresh AI & Marketing News". | `generate_all_content.py`; `fetch_ai_news_rss.py` never called |
| 16 | **Carousel PDF primary lookup never succeeds** — the scheduler looks in `…/carousel-N/`, the builder writes one level up. Every run falls back to `slack_downloads/`. Both sides now assert, so a "fix" to one alone fails loudly instead of silently. | `schedule_all_posts.cjs:472`; `build_carousel_today.cjs:55,66` |
| 17 | **Dead Slack upload path**: `linkedin_posts_{date}.pdf` is never generated. | `send_to_slack.py:508-511` |
| 19 | Only `RANKED_BARS` implemented of 5 documented infographic formats. Moot while count is 0. | `cap_infographic_today.js` |
| 20 | **Carousel slides 1 and 6 carry hard-coded topic-independent copy** — `2026 AI BLUEPRINT`, `NATIVE AI OPERATING SYSTEM` — on every carousel. Two Unsplash images downloaded each run and discarded. **Now 40% of output.** | `generate_carousel_today.py:66-76`, `:13-16` |
| 22 | Option A residual: a scheduler crash can record a topic whose post never went live. Safe direction. | `generate_all_content.py` |
| 23 | Unhandled edge case: an unclosed *double* quote mid-title. | `schedule_all_posts.cjs:290-303` |
| **27** | **New — a test run advances the real watermark.** `START_DATE_OFFSET` overrides the start date but the state write is unconditional, so a test leaves the watermark ~2 months out. Worked around in the protocol by backing up and restoring; a real fix would skip the state write when the offset is set. | `schedule_all_posts.cjs:1370` |
| **29** | **If performance posts ever come back, they must go through the config and the format assertions** — as entries in `format_mix` with their own slot templates, not as a hard-coded Python literal outside every guard. The old shape had five fixed topics, no de-duplication against `used_topics.json`, no slot, no time, and no assertion; nothing would have caught it drifting. | `generate_all_content.py:586-660` (block, disabled) |
| **28** | **New — `build_carousel_today.cjs:77` copies only carousel 1** to the dated archive (`carousel-{dateStr}.pdf`). Carousel 2 has no dated copy, so it is unrecoverable once `slack_downloads/carousel-2.pdf` is overwritten next run. | `build_carousel_today.cjs:77` |

**Item 20 is the one I would raise first for Phase 2.** Carousels are now 2 of 5 posts and the strongest-performing format, and every one currently ships with `2026 AI BLUEPRINT` and `NATIVE AI OPERATING SYSTEM` baked into slides 1 and 6 regardless of topic.

---

## Rollback

Undo all of Phase 1, keeping Phase 0 and 0b:

```bash
git reset --hard 05e6c25
```

Undo a single task, e.g. the new numbers only:

```bash
git revert --no-edit fadc0d7
```

Revert to the old cadence without touching code — edit `pipeline_config.json` back to `posts_per_batch: 11`, `batch_horizon_days: 3`, `weekdays_only: false`, the four original time slots, and the 3/3/2/3 mix. The startup assertions will confirm it adds up.
