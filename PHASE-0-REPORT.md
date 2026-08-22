# PHASE-0-REPORT.md

Safety and visibility hardening, applied 2026-08-07. Companion to [`PIPELINE-AUDIT.md`](PIPELINE-AUDIT.md).

**Scope honoured:** no prompt template, `writing_rules` string, voice file, format mix, posting count, posting time, or scheduling horizon was changed. The pipeline was never run; no script that opens Chrome or touches LinkedIn was executed. All testing ran against copies in a session scratchpad with Puppeteer stubbed and network calls blocked.

**Baseline commit:** `5f43c80` — the pipeline exactly as audited, before any change below.

---

## Task 1 — Version control

`.gitignore` created **before** `git init`, so no secret ever entered the index.

| File | Change |
|---|---|
| `.gitignore` | **New**, 78 lines |

Ignored: `.env` / `.env.*` (with `!.env.example`), `chrome-session/`, `node_modules/`, `__pycache__/`, `*.pyc`, `state-backups/`, `carousel-routine/output/`, `carousel-routine/temp/`, `slack_downloads/`, `screenshots/`, generated `linkedin-infographic-*.png|html` (with `!linkedin-infographic-template.html`), `*_carousel.pdf`, `linkedin_posts_*.pdf`, `error_screenshot.png`, `urgent_error_screenshot.png`, `clinic_image_*.png`, `reddit_debug_body.html`, `*.log`, `logs/`, `.DS_Store`, and — per your instruction — `user_uploads/`, `fresh_clinic_uploads/`.

Deliberately **tracked**: `pipeline_state.json`, `used_topics.json`, `schedule_checkpoint.json`, `linkedin_posts_today.txt`, the dated `linkedin_posts_*.txt` / `performance_posts_*.txt` archives, and the `reddit_data.json` / `ai_news_data.json` caches. A comment block at the end of `.gitignore` records this so it is not undone by accident.

**Commit `5f43c80`** — 169 files, 28,224 insertions. Verified before committing: `git check-ignore` confirms `.env` and `chrome-session/` are excluded; `.env.example` was committed only after confirming all six keys are valueless placeholders (`grep -cE '^[A-Za-z_]+=.+'` → 0). Repo size dropped from 323M to ~20M staged.

---

## Task 2 — State backup

| File | Size |
|---|---|
| `state-backups/pipeline_state.20260807.json` | 87 B |
| `state-backups/used_topics.20260807.json` | 3,157 B |
| `state-backups/linkedin_posts_today.20260807.txt` | 10,857 B |

Copied with `cp -p`; each verified SHA-256-identical to its source. `chrome-session/` was **not** copied. `state-backups/` is gitignored.

---

## Task 3 — Fallback batch removed

The highest-priority defect from the audit: a missing `linkedin_posts_today.txt` caused the scheduler to schedule 11 hard-coded June-2026 posts signed `@founderswing`, referencing an asset path on a different machine (`/Users/prithal/...`).

**File: `schedule_all_posts.cjs`** (1,134 → 1,132 lines; **+30 / −196**)

| Location | Change |
|---|---|
| **160–171** | Missing-file branch: was `console.log("...Using default hardcoded fallback."); return null;` → now names the expected path and the script that produces it, then `process.exit(1)` |
| **421–430** | Parse-error catch: was `return null` → now prints the error, then `process.exit(1)` |
| **440–453** | Call site: `parseTodayPosts() \|\| [ …192 lines… ]` → `parseTodayPosts();` plus an empty-batch guard |

**192 lines of hard-coded post literals deleted.** Verified absent by grep: zero matches for `founderswing`, `/Users/prithal`, `06/13/2026`, `06/14/2026`, `06/15/2026`, `hardcoded fallback`. There is now no code path that can schedule content the pipeline did not just generate.

The empty-batch guard (kept at your instruction) closes a second silent path: a file that exists but parses to zero posts previously ran the loop zero times, then threw inside the existing try/catch while advancing state, and **exited 0 reporting success**.

---

## Task 4 — Past-date guards

**File: `schedule_all_posts.cjs`**, inside `parseTodayPosts()` — the old 25-line block at 285–309 is now 95 lines at **285–379**.

| Guard | Lines | Triggers on |
|---|---|---|
| **A** | 303–319 | `START_DATE_OFFSET` negative, or not an integer |
| **B** | 320–370 | `pipeline_state.json` missing, invalid JSON, absent/null `last_scheduled_date`, not `YYYY-MM-DD`, or not a real calendar date |
| **C** | 371–379 | Computed start date earlier than tomorrow, however it was derived |

All three route through a shared `abortSchedule()` that prints a framed `FATAL:` block, states "Nothing has been scheduled", and exits 1 — **before the browser launches**. The `if (!startDateObj) startDateObj = new Date()` fallback to today is deleted.

**Boundary semantics, as you specified:** the check is `atMidnight(startDateObj) < earliestAllowed` — strictly earlier than tomorrow aborts; **equal to tomorrow passes**. Your current `last_scheduled_date: 2026-08-07` yields a start of `2026-08-08`, evaluated as `2026-08-08 < 2026-08-08` → `false` → **PASSES**. Confirmed by direct evaluation against the real file and by end-to-end run.

---

## Task 5 — Crash safety / checkpointing

### 5a. Per-post checkpoint — `schedule_all_posts.cjs`

| Location | Change |
|---|---|
| **455–527** | `readCheckpoint()`, `writeCheckpoint()`, interrupted-batch startup guard, fresh checkpoint opened before the browser starts |
| **1074–1085** | Appends `{id, type, date, time, scheduled_at}` and writes to disk **immediately** after each `✓ Successfully scheduled` |
| **1090–1094** | Sets `status: "complete"` **before** `pipeline_state.json` is advanced, so a failure between the two is visible rather than silent |

`schedule_checkpoint.json` shape:

```json
{
  "status": "in_progress",
  "batch_start_date": "08/08/2026",
  "started_at": "2026-08-07T16:42:59.644Z",
  "source_file": "linkedin_posts_today.txt",
  "total_posts": 11,
  "planned":   [ { "id": 1, "type": "carousel", "date": "08/08/2026", "time": "9:00 AM" } ],
  "completed": [ { "id": 1, "type": "carousel", "date": "08/08/2026", "time": "9:00 AM",
                   "scheduled_at": "2026-08-07T16:43:12.001Z" } ]
}
```

On startup, an `in_progress` checkpoint with ≥1 completed post **aborts** and prints both lists — which posts are already live on LinkedIn and which are not — then exits 1. It does **not** auto-resume. `status: "complete"`, a checkpoint with zero completed posts, or no checkpoint at all all proceed normally. `schedule_checkpoint.json` is git-tracked (not ignored).

### 5b. `used_topics.json` write ordering — Option A

**This could not be done as literally worded, and we agreed Option A instead.** Topics exist only in `content_plan`, in memory in the Python generator, and are never persisted anywhere the Node scheduler can read. "Record a topic after its post is actually scheduled" would have required a new cross-process contract (a `pending_topics.json` staging file promoted by the scheduler) — coupling the generator to the scheduler immediately before Phase 1 rewrites the generator.

**File: `generate_all_content.py`** (597 → 612 lines; **+27 / −11**)

| Location | Change |
|---|---|
| **294–299** | `used_topics.append(topic)` removed from the planning loop |
| **337–359** | Topic carried on each item as `"topic": topic`; successful generations collected into `generated_topics`; the failure path now states explicitly that no topic was burned |
| **375–385** | The write moved to **after** `linkedin_posts_today.txt` is on disk — a topic is recorded only once its post durably exists |

**Chosen knowingly.** Option A fails in the safe direction: a burned topic with no live post costs a topic, whereas the reverse causes a duplicate post on LinkedIn. **The scheduler-crash gap is covered by `schedule_checkpoint.json` aborting for manual resume, not by `used_topics.json`** — so a scheduler crash can still leave a topic recorded whose post never went live. That is the accepted residual, and it is the safe direction.

Verified with a stubbed LLM (no network): failure at post 4 → exit 1, `used_topics.json` unchanged at its 2 pre-existing entries (previously it would have held 11 burned topics); all 11 succeed → grows 2 → 13.

---

## Task 6 — Slack review gate

The audit's clearest live defect: the parser matched headers (`1. COLLABORATIVE ARTICLE`, `2. POLL`, …) that the generator stopped writing. **Zero headers matched, so no post text had ever reached Slack**, and the script exited 0 either way.

**File: `send_to_slack.py`** (291 → 406 lines; **+140 / −199** against baseline)

| Location | Change |
|---|---|
| **1–7** | Added `re`, `sys` imports |
| **139–197** | **Structural** parser: split on `={10,}`, treat any `^\d+\.` line as a header, next section is the body. `detect_type()` mirrors `schedule_all_posts.cjs:186-188` |
| **202–214** | Reads `linkedin_posts_today.txt` — the same file the scheduler reads — falling back to the dated file, else exits 1 |
| **217–226** | Zero-post guard: `sys.exit(1)` with a clear error instead of exiting 0 |
| **229–278** | Predicted schedule: mirrors the scheduler's start-date logic and slot array, display only |
| **281–310** | Header summary + one labelled message per post |
| **343–375** | Upload captions rewired to the new list structure. **Upload calls themselves untouched** |

**Drift-proofing:** slot names are no longer matched at all. `1. CAROUSEL 1` can become `1. PERSONAL STORY` in Phase 1 and it still parses — only the `====` separator and the `N.` prefix matter, which is exactly what the generator emits and what the scheduler consumes.

**Result on the real file: 11 of 11 posts parsed** (previously 0). Dry-run output, network hard-blocked:

```
📅 *LinkedIn Content Drop — 2026-08-07*
*11 posts* for review (3 carousel, 3 infographic, 2 poll, 3 regular).
Scheduling window: *Sat 08 Aug to Mon 10 Aug 2026*
Source: `linkedin_posts_today.txt`
_Review before the scheduler runs. Assets attached below._

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
*POST 1 of 11  ·  CAROUSEL (PDF)*
🗓  Sat 08 Aug 2026 at 9:00 AM
_slot: CAROUSEL 1_
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

<full post body>
```

12 messages (1 header + 11 posts) and 4 file uploads.

---

## Task 6b — The published `**` defect (markdown marker mismatch)

Added after you reported that **six published carousel posts have a literal `**` as their first visible line**. Confirmed, root-caused, and partially fixed. Carousels are the highest-performing format, so this is the most damaging defect found in the project so far.

### The code path that published `**`

It is **not** `send_to_slack.py`. That file only made the Slack *preview* caption empty. The `**` reached LinkedIn through the **scheduler**:

| Step | File:line | What happens |
|---|---|---|
| 1 | `generate_all_content.py:321` | Prompt says `Format clearly labeled with ... CAROUSEL CAPTION:` — no format is pinned, so the model emits the marker bolded roughly 59% of the time |
| 2 | model output | Writes `**CAROUSEL CAPTION:**  ` instead of `CAROUSEL CAPTION:` |
| 3 | `schedule_all_posts.cjs:234` | `bodyLines.findIndex(line => line.includes('CAROUSEL CAPTION:'))` — `.includes()` **matches the bolded line**, so no error is raised |
| 4 | `schedule_all_posts.cjs:236` | `bodyLines[captionStart].split('CAROUSEL CAPTION:')[1]` returns **`"**  "`** — the trailing `**` and spaces of the bolded marker |
| 5 | `schedule_all_posts.cjs:238` | `[firstLine, ...remainingLines].join('\n').trim()` — `.trim()` removes whitespace but **cannot remove `*`**, so the caption keeps its `**  \n` prefix |
| 6 | `schedule_all_posts.cjs:~950` | `page.keyboard.type(post.caption)` types it into LinkedIn's composer, line by line |

Reproduced against the live `linkedin_posts_today.txt` by running the scheduler's extraction verbatim:

```
── 1. CAROUSEL 1
   marker line   : "**CAROUSEL CAPTION:**  "
   split()[1]    : "**  "
   FIRST 3 CHARS TYPED INTO LINKEDIN: "** "
── 5. CAROUSEL 2
   marker line   : "CAROUSEL CAPTION:"
   FIRST 3 CHARS TYPED INTO LINKEDIN: "Tes"      <- plain marker, clean
── 9. CAROUSEL 3
   marker line   : "**CAROUSEL CAPTION:**  "
   FIRST 3 CHARS TYPED INTO LINKEDIN: "** "
```

**Prevalence across the archives: 10 emphasised vs 7 plain** — the bug fires on roughly 3 in 5 carousels, which matches six bad posts over the observed run history.

**Not fixed yet, per your instruction.** The one-line change is at `schedule_all_posts.cjs:236-238`.

### What was fixed — `send_to_slack.py:353-394`

Replaced the two duplicated caption loops with a marker-normalising extractor. It strips markdown emphasis and whitespace from a candidate line **before** matching, rather than substring-matching:

```python
MARKDOWN_EMPHASIS = "*_` \t"

def normalise_marker(line):
    """'  **CAROUSEL CAPTION:**  ' -> 'CAROUSEL CAPTION:'"""
    return line.strip().strip(MARKDOWN_EMPHASIS).strip()

def is_marker(line, *markers):
    n = normalise_marker(line).upper().rstrip(":")
    return any(n == m.upper().rstrip(":") for m in markers)
```

`extract_caption()` also strips emphasis from the captured result, because `.strip()` alone cannot remove a leading `*` — the exact reason the scheduler's `.trim()` fails.

Verified: `CAROUSEL CAPTION:`, `**CAROUSEL CAPTION:**`, `*CAROUSEL CAPTION:*`, `__CAROUSEL CAPTION:__`, `` `CAROUSEL CAPTION:` ``, `**carousel caption:**`, and whitespace-padded forms all match identically. All three real carousels now extract clean (`'Cur'`, `'Tes'`, `'Bre'` — no leading `*`).

### Every other marker the generator writes — audit result

| Marker | Consumed at | Emphasised in archives | Status |
|---|---|---|---|
| `CAROUSEL CAPTION:` | `schedule_all_posts.cjs:234-238` → post caption | **10 of 17** | 🔴 **Actively publishing `**`** |
| `INFOGRAPHIC CAPTION:` | `schedule_all_posts.cjs:273-277` → post caption | 0 of 16 | 🟡 Identical `.includes()`+`.split()` code. Clean only by luck — one bolded emission publishes `**` |
| `Hook:` / `Hook text:` | `schedule_all_posts.cjs:241-242` → **LinkedIn document title** | 0 of 1 | 🟡 See below — separate live defect |
| Poll question | `schedule_all_posts.cjs:208-224` → poll question | 0 of 4 `Question:` | 🟡 See below — separate live defect |
| Poll options `☐` | `schedule_all_posts.cjs:205-208` | 0 | 🟡 Uses `startsWith('☐')`; an emphasised `**☐ Option**` would be **silently dropped**, losing a poll option |

**Two further live defects found while tracing, neither markdown-related:**

1. **Every carousel is published with the document title `"Branded Carousel"`.** `schedule_all_posts.cjs:241` looks for a line containing `Hook text:` or `Hook:`; the current generator prompt never emits one, so the fallback at `:242` always wins. Across all archives only **1** such line exists. That title is visible on the LinkedIn document card.
   Latent on top of this: if the model ever emits `**Hook:** "..."`, `split(':')[1]` yields `** "..."` and `.replace(/["']/g,'')` + `.trim()` leave `"** Why cut a winning product?"` — a `**` in the document title.

2. **Poll questions publish with a literal `"Question: "` prefix.** `schedule_all_posts.cjs:203-211` takes the last non-empty line before the first `☐` as the question, including its label. Live examples: `"Question: How do you prioritize AI agent training?"` and `"Question: Do you adjust ad budgets mid-week?"`. Both are already scheduled that way.

**Recommended sequencing (not done):** fix `schedule_all_posts.cjs:236-238` and `:275-277` with the same normalise-then-strip approach, fix the `Hook:`/title fallback at `:241-242`, and strip the `Question: ` label at `:203-211`. All four are in the publishing path, so they change what LinkedIn receives — deliberately deferred out of Phase 0.

---

## Task 7 — Verification

**11 of 11 guards correct**, run end-to-end against the final source with Puppeteer stubbed to exit 42 if reached:

| Case | Result |
|---|---|
| Input file missing / unreadable / zero valid headers | exit 1 ×3 |
| `START_DATE_OFFSET` = `-3` / `notanumber` | exit 1 ×2 |
| `pipeline_state.json` missing / `2026-13-45` / unparseable | exit 1 ×3 |
| Past date → `2025-01-02` | exit 1 |
| Interrupted checkpoint 7/11 / corrupt checkpoint | exit 1 ×2 |
| **Real watermark `2026-08-07` → start `2026-08-08`** | **exit 42 — reached browser launch, i.e. PASSES** |

**Protected files byte-identical** to the baseline taken before Task 2: `.env`, `pipeline_state.json`, `used_topics.json`, `linkedin_posts_today.txt`, and `chrome-session/` (path+size+mtime inventory hash across ~50 subdirs). No `schedule_checkpoint.json`, `__pycache__`, or `pending_topics.json` left in the project.

**Scope verified:** zero diff to `content-doctrine.md`, `voice-profile.md`, `commands/`, `skills/`, `daily-linkedin-posts/`. Zero prompt-text lines touched in the generator. The `schedule` array is byte-identical to the baseline commit — the 11 diff lines containing posting times were all **deletions** from the removed fallback batch.

---

## What I could not do, and why

1. **`used_topics.json` as literally specified.** Covered in Task 5b — impossible without a new cross-process contract; Option A chosen deliberately.
2. **No runtime proof of the happy path.** Every guard was proven, but no post was actually scheduled, because that requires opening Chrome and writing to LinkedIn. The first real run is still the first end-to-end test of the checkpoint write and the Slack send. Watch that run.
3. **The carousel PDF's Slack caption is still empty.** The generator emits `**CAROUSEL CAPTION:**` (markdown bold) on 2 of 3 carousels, but the extractor uses `startswith("CAROUSEL CAPTION:")`, which the `**` prefix defeats. This sits inside the upload path you told me not to change. One-word fix (`startswith` → `in`) whenever you want it. The scheduler is unaffected — it uses `.includes()`.

---

## Things to know before Phase 1

**Stale comment blocks left in place (you asked me to track these):**
- `schedule_all_posts.cjs:434-437` — `ALL 11 POSTS — 4 per day across 3 days / Schedule: 9:00 AM, 12:00 PM, 3:00 PM, 6:00 PM IST`. Now the only in-file description of the batch shape, and it is correct today but not authoritative.
- `schedule_all_posts.cjs:1109-1112` — the end-of-run summary still prints June 13–15 2026 dates and obsolete post types (Collaborative Article, Tool Spotlight, Weekly Roundup, Plain English, Unfair Advantage, Career/Income, Hot Take, Steal This).

**The posting schedule is now expressed in six places.** Task 6 added a sixth: `SCHEDULE_SLOTS` in `send_to_slack.py:233`, which mirrors the scheduler's array because Slack runs *before* scheduling and must predict the times. It is display-only — a mismatch shows a wrong time in Slack but can never change what is scheduled. When you change posting times in Phase 1, this is a candidate to collapse into a single shared config.

**Your watermark is on the boundary.** `last_scheduled_date: 2026-08-07` gives a start of `2026-08-08` = tomorrow, which clears Guard C by exactly one day. If you do not run the pipeline before tomorrow ends, that same watermark will start failing Guard C. That is correct behaviour — it means the watermark is stale — but it will look like the guards broke the pipeline. They did not.

**Audit correction.** `used_topics.json` holds **76** entries, not 77 — I miscounted array elements against file lines in the original audit. All six occurrences in `PIPELINE-AUDIT.md` are corrected. The file itself is unchanged.

**Unchanged pre-existing issues that will bite in Phase 1** (all detailed in `PIPELINE-AUDIT.md` §12):
- `content-doctrine.md` and `voice-profile.md` are **not read** by the running pipeline. The live voice is the `writing_rules` string at `generate_all_content.py:90-117`. Editing the markdown changes nothing.
- `skills/branded-carousel/SKILL.md` is **executable** — carousel HTML templates are regex-extracted from its `TEMPLATE N` headings at runtime. Renaming a heading breaks the build.
- The format mix is defined in five uncoordinated places across three languages; every mismatch fails silently.
- `delete_all_scheduled.cjs` still has **no date guard** and deletes every scheduled post it can reach. Untouched in Phase 0 — it is not part of `run_pipeline.py`, but it is a foot-gun if used to clean up a bad batch.
- `ai_news_data.json` is stale (2026-07-25) and nothing in `run_pipeline.py` refreshes it, yet it is fed to the planner every run as "Fresh AI & Marketing News".

---

## Phase 0b — Publishing-path marker normalisation and carousel title fallback

Scope: the four markers identified in Task 6b, plus the poll-question label. No other behaviour, format, cadence or prompt change.

### Shared normalisation, now in both languages

`schedule_all_posts.cjs:160-238` gained the JavaScript twin of the Python helpers added in Task 6b:

| JS (`schedule_all_posts.cjs`) | Python (`send_to_slack.py`) | Purpose |
|---|---|---|
| `MARKDOWN_EMPHASIS` (regex) | `MARKDOWN_EMPHASIS` (char set) | `*`, `_`, `` ` ``, whitespace |
| `stripEmphasis()` / `normaliseMarker()` | `normalise_marker()` | Strip emphasis from both ends |
| `markerRemainder()` / `isMarkerLine()` | `is_marker()` | Emphasis-insensitive marker match |
| `extractCaption()` | `extract_caption()` | Capture after marker, then strip emphasis |
| `isOptionLine()` | — | Emphasis-tolerant `☐` detection |
| `titleFromCaption()` / `stripWrappingQuotes()` | — | Title derivation |

Parity confirmed on identical inputs — `CAROUSEL CAPTION:`, `**…**`, `*…*`, `__…__`, `` `…` ``, padded and mixed-case all match in both languages. Reciprocal `⚠ KNOWN DUPLICATION` comments at `schedule_all_posts.cjs:167-171` and `send_to_slack.py:359-362` name the other site and flag this to be collapsed once the pipeline has a config layer.

### The five call sites

| # | Site | Before | After |
|---|---|---|---|
| 1 | `CAROUSEL CAPTION:` — caption | `.includes()` + `.split()` left `"**  "` at the head | `extractCaption()`; emphasis stripped from the result |
| 2 | `INFOGRAPHIC CAPTION:` — caption | Identically vulnerable | Same extractor |
| 3 | `Hook:` / `Hook text:` — document title | `split(':')[1]` (truncated at a second colon); fallback `"Branded Carousel"` always won | Slice at **first** colon; precedence Hook → first caption line → literal fallback |
| 4 | `☐` — poll options | `startsWith('☐')` dropped `**☐ A**` silently | `isOptionLine()` normalises first |
| 5 | Poll question | Published the literal `"Question: "` label | Label stripped, then emphasis re-stripped |

Site 5 needed a second fix found by synthetic testing: removing the label from `**Question:** X` leaves a dangling `**`, because the closing emphasis is no longer adjacent to a stripped edge. This is the *same* trailing-emphasis trap as the original defect.

`stripWrappingQuotes()` was added after the first title run produced `"isnt"`, `"Dont"`, `"Metas"` — the inherited `replace(/["']/g,'')` was destroying apostrophes. It now strips only wrapping quotes, straight and curly.

### Verified against the real archives (17 carousels, 12 polls, 17 infographics)

```
carousels    : 17   captions fixed (no longer start with '*'): 10
infographics : 17   captions still starting with '*'        : 0
polls        : 12   questions WITHOUT 'Question:' prefix    : 12/12
polls        : 12   with options dropped                    : 0
```

The 10 fixed carousels match exactly the 10 emphasised markers counted in Task 6b.

### Carousel titles — 58-character cap

**Limit: `DOC_TITLE_MAX = 58`** (`schedule_all_posts.cjs`). Set on the project owner's observation of the composer. **Not verifiable from this repo** — no run has ever captured the input's `maxLength` attribute, because every past run published the 16-character literal `"Branded Carousel"`, and verifying it directly would mean opening LinkedIn. A read-only probe was added at the title step: it logs the input's real `maxLength` and prints a warning if it differs from `DOC_TITLE_MAX`, so the next real run confirms or corrects the number. Changing it is a one-line edit.

Derivation, in order:

1. Hard cap 58, cut on a word boundary, **no ellipsis**.
2. If the source exceeds 58, prefer the **first complete clause** — first `.`, `!` or `?` followed by whitespace or end-of-string (so `9.21` and `₹10L/mo.` are not mistaken for clause ends), at least 20 characters in. `TITLE_MIN_CLAUSE = 20` prevents `"Bad data"` being taken from `"Bad data. It clouds judgment…"`.
3. Trailing punctuation, dangling conjunctions/articles/prepositions (`and, but, or, nor, so, yet, if, when, while, than, that, the, a, an, to, for, with, of, in, on, from, at, by, as, into, onto, about, over, under, via`) and an unclosed opening quote on the final word are all removed.
4. Precedence unchanged: Hook line → first caption line → `"Branded Carousel"`. The cap now applies to the Hook-line result too, which could previously exceed it.

### All 17 archived carousels, with character counts

All previously published as **`Branded Carousel`** (16 chars).

| # | Run | Len | New title |
|---|---|---|---|
| 1 | 20260624 | 33 | `0 to ₹10L/mo lead nurture scaling` |
| 2 | 20260724 | 44 | `0 to ₹10L/mo lead nurture scaling." Shifting` |
| 3 | 20260725 | 51 | `Built a WhatsApp funnel and wondering why sales are` |
| 4 | 20260725 | 53 | `Achieving a 200% ROI with Meta Ads isn't just a dream` |
| 5 | 20260725 | 55 | `Every day, I meet smart founders who hesitate to switch` |
| 6 | 20260726 | 42 | `Bad data can cost you more than just sales` |
| 7 | 20260726 | 57 | `Scaling Meta ads isn't about burning money till something` |
| 8 | 20260726 | 47 | `Relying on manual ad management is like playing` |
| 9 | 20260801 | 57 | `Frustration with ad performance is common, but it doesn't` |
| 10 | 20260801 | 57 | `Scaling Meta Ads using AI agents transformed our client's` |
| 11 | 20260801 | 30 | `Don't buy into AI hype for PPC` |
| 12 | 20260804 | 38 | `Curiosity piqued? Discover why cutting` |
| 13 | 20260804 | 52 | `Testing 300 unique ads was an eye-opener, with a 79%` |
| 14 | 20260804 | 52 | `Breaking the myth of ad quantity starts with smarter` |
| 15 | today | 38 | `Curiosity piqued? Discover why cutting` |
| 16 | today | 52 | `Testing 300 unique ads was an eye-opener, with a 79%` |
| 17 | today | 52 | `Breaking the myth of ad quantity starts with smarter` |

**0 of 17 exceed the cap.** Longest is 57.

### Honest quality assessment

**Only 4 of 17 read as standalone labels**: #1, #4, #6, #11. The other **13 remain sentence fragments** — `…why sales are`, `…till something`, `…but it doesn't`, `…our client's`, `…with a 79%`, `…with smarter`.

The cause is the source data, not the truncation logic: **not one** of the 17 caption first-lines is 58 characters or shorter, and only two contain a sentence break inside the first 58 characters. There is no complete clause to cut to, so rule 2 cannot fire and rule 1 takes over. No title logic can invent a short opening sentence that the caption does not have.

This is now a **caption-writing problem, not a parsing problem**, and it belongs to Phase 2: the carousel prompt does not ask for a short opening line, and `slide_1_hook` (already 6-8 words, exactly title-shaped) is generated but never written into the post body where the scheduler could find it. Wiring that hook into the output would give all 17 a clean title with no truncation at all.

#2 also carries a stray `."` from the caption's own text — genuine content, not a parsing artefact.

### Two regressions caught by verifying against real data

1. A first pass at rule 3 used a whole-string odd-quote count to detect unbalanced quotes. English apostrophes are unpaired by nature, so `"Don't buy into AI hype for PPC"` truncated to **`"Don"`** (3 chars), and `client's` / `isn't` titles lost everything after the apostrophe — 5 titles destroyed. Rewritten to inspect only the final word, and only when its opening quote is never closed.
2. An earlier pass at rule 3 (Phase 0b, first commit) used a blanket `replace(/["']/g,'')` that produced `isnt`, `Dont`, `Metas`. Replaced by `stripWrappingQuotes()`.

Both were invisible to synthetic tests and only appeared when run against the archives.

### slide_1_hook surfaced as the document title (root-cause fix)

The planner already produces `slide_1_hook` at 6-8 words — exactly title-shaped — but consumed it inline in the carousel prompt and never wrote it anywhere the scheduler could see. Truncated caption text was therefore the *only* title source. Fixed at the source.

**Generator — `generate_all_content.py`, three minimal edits:**

| Location | Change |
|---|---|
| **301-303** | `slide_1_hook = ""` initialised before the type branches (it was scoped inside the carousel branch only) |
| **345** | `"hook": slide_1_hook` carried on the item, alongside `"topic"` |
| **367-377** | For carousels only, the body is prefixed with `Hook: {slide_1_hook}` before being written |

The Hook line is written **above** the post body and therefore above the `CAROUSEL CAPTION:` marker, so it is never captured into the published caption — verified. No prompt wording changed, `slide_1_hook` is produced exactly as before, and no other post type is touched.

**Scheduler — one minimum change was required.** `markerRemainder()` matched any line merely *starting with* the marker text, with no colon required. That was harmless while no Hook line existed; it becomes dangerous the moment carousel bodies are searched for `Hook:`, because ordinary prose matches:

```
"Hook style used: Curiosity Gap"  -> matched, title would be "style used: Curiosity Gap"
"Hooks that convert are short"    -> matched, title would be "s that convert are short"
"Hooked readers stay longer"      -> matched, title would be "ed readers stay longer"
```

`markerRemainder()` now requires the marker to be followed by `:` (optionally wrapped in emphasis). All three are rejected; every real marker still matches. The Hook-line precedence itself needed no change.

**Two refinements to rule 3, flagged as deviations from the literal spec:**

- `?` and `!` are no longer stripped from the end of a title. Hooks are frequently questions, and `"Why cut a winning product"` reads worse than `"Why cut a winning product?"`. `.` `,` `;` `:` `-` and quotes are still stripped.
- A clause cut now keeps a closing `?` or `!` and still drops a closing `.`.

**End-to-end, generator → scheduler (LLM stubbed, no network):**

| slide_1_hook | Resulting title | Len | Truncated? |
|---|---|---|---|
| `Why cut a winning product?` | `Why cut a winning product?` | 26 | no |
| `300 unique ads, 79% success` | `300 unique ads, 79% success` | 27 | no |
| `More ads, more results? Wrong.` | `More ads, more results? Wrong` | 29 | no |

The Hook line did **not** leak into any caption, and a deliberately adversarial caption line (`"Hooks that convert are short and punchy…"`) correctly did **not** become the title.

**Truncation retained as fallback.** Re-running the same file with the `Hook: ` lines stripped falls back to caption-derived titles, exactly as before. The fallback is now the secondary path, not the primary one.

### Hook length distribution — how many will need truncating

**`slide_1_hook` is unrecoverable for past runs.** It lives only in the planner's in-memory `content_plan`, is consumed at `generate_all_content.py:319`, and is written to no file. The planner logs only `topic`. So the archived runs cannot show real hook values; from the next run onward they will be in `linkedin_posts_*.txt`.

The closest available proxies:

| Source | Values | Length |
|---|---|---|
| `carousel_data_{1,2,3}.json` (latest run, `HOOK_PART_1` + `HOOK_PART_2`) | `Why cut a winning product?` / `300 Unique Ads 79% success!` / `More ads, more results? Wrong.` | 26 / 27 / 30 |
| Rendered Slide-1 text across all archives (the model's rendering of the hook) | 14 cleanly extractable of 17 | **min 25, median 30, max 33** |

The other 3 of 17 are not measurable — the proxy extractor picked up *Slide 2* text where the Slide-1 line was formatted differently. They are extraction failures, not long hooks.

**Answer to the question: essentially none exceed 58.** Every measurable hook lands between 25 and 33 characters, roughly half the cap. The `6-8 words max` instruction in the planning prompt is holding, so no prompt constraint needs changing in Phase 2 for title length. Truncation should now fire rarely, and only when the planner omits `slide_1_hook` entirely.

### Verification

Phase 0 guards re-confirmed after the change: real state → passes to browser launch; missing state, past date, and missing posts file → exit 1. Slack gate still parses 11/11 with a populated carousel caption. `.env`, `pipeline_state.json`, `used_topics.json`, `linkedin_posts_today.txt` and `chrome-session/` all byte-identical. Pipeline never run; LinkedIn never touched.

### Still not fixed

The generator prompt at `generate_all_content.py:321` pins no marker format, which is why the model emits `**CAROUSEL CAPTION:**` ~59% of the time. Both consumers now tolerate it, but the root cause is a prompt change and therefore Phase 2.

---

## Phase 0b — final summary

Everything in Phase 0b, consolidated. Four commits: `c071352` (marker normalisation + title fallback), `8550818` (58-char cap), `25d1eed` (slide_1_hook surfacing), plus `67975fd` in Phase 0 (the Slack-side extractor).

### What changed, end to end

| Area | Before | After |
|---|---|---|
| Carousel caption | `**` published as the first visible line on ~59% of carousels | Emphasis-tolerant extraction; 10 of 17 archived carousels fixed |
| Infographic caption | Identically vulnerable, clean only by luck | Same extractor |
| Carousel document title | Always the literal `Branded Carousel` | `slide_1_hook` → caption first line → `Branded Carousel` |
| Poll options | `**☐ A**` silently dropped | `isOptionLine()` normalises first |
| Poll question | Published with a literal `Question: ` prefix | Label stripped, then emphasis re-stripped |
| Title length | Uncapped, then capped at 100 | `DOC_TITLE_MAX = 58` with clause-preferring truncation |

### slide_1_hook is now the primary title source

`generate_all_content.py` writes `Hook: {slide_1_hook}` above each carousel body — above the `CAROUSEL CAPTION:` marker, so it never leaks into the published caption. Three edits (`301-303`, `345`, `367-377`), carousels only. No prompt wording changed; `slide_1_hook` is produced exactly as before.

Verified end to end with a stubbed LLM: hooks of 26/27/29 characters became titles verbatim, with no truncation and no caption leakage. A deliberately adversarial caption line (`"Hooks that convert are short and punchy…"`) correctly did **not** become the title.

### The colon requirement — a necessary catch, not a deviation

`markerRemainder()` matched any line merely *starting with* the marker text. Harmless while no Hook line existed; the moment carousel bodies are searched for `Hook:`, ordinary prose hijacks the title:

```
"Hook style used: Curiosity Gap"  -> "style used: Curiosity Gap"
"Hooks that convert are short"    -> "s that convert are short"
"Hooked readers stay longer"      -> "ed readers stay longer"
```

The marker must now be followed by `:` (optionally emphasis-wrapped). All three rejected; every real marker still matches. Hook-line precedence itself needed no change.

### Punctuation rules (both approved)

- `?` and `!` are **not** stripped from a title's end — hooks are frequently questions, and `"Why cut a winning product"` reads worse than `"Why cut a winning product?"`.
- A clause cut keeps a closing `?` or `!`, still drops a closing `.`.
- `.` `,` `;` `:` `-` `–` `—` and quotes are still stripped, along with dangling conjunctions/articles/prepositions and an unclosed opening quote on the final word.

### Hook lengths — essentially none approach the cap

**`slide_1_hook` is unrecoverable for every past run.** It lives only in the planner's in-memory `content_plan`, is consumed at `generate_all_content.py:319`, and is written to no file; the planner logs only `topic`. **From the next run onward it will be in `linkedin_posts_*.txt` as a `Hook: ` line**, so this becomes measurable and diffable in git.

Proxy measurements available today:

| Source | Range |
|---|---|
| `carousel_data_{1,2,3}.json` (`HOOK_PART_1` + `HOOK_PART_2`, latest run) | 26 / 27 / 30 chars |
| Rendered Slide-1 text, all archives — 14 cleanly extractable of 17 | min 25, median 30, **max 33** |

The 3 unmeasurable rows are proxy-extractor failures (it captured *Slide 2* text where Slide 1 was formatted differently), not long hooks. Every measurable hook sits at roughly half the 58 cap, so the `6-8 words max` planning instruction is holding and **no Phase 2 prompt change is needed for title length**. Truncation should now fire only when the planner omits `slide_1_hook`.

### Regressions caught by verifying against real archives

Three, all invisible to synthetic tests:

1. A blanket `replace(/["']/g,'')` produced `isnt`, `Dont`, `Metas`.
2. A whole-string odd-quote check truncated `"Don't buy into AI hype for PPC"` to **`"Don"`** — English apostrophes are unpaired by nature. Five titles destroyed. Rewritten to inspect only the final word.
3. The `**Question:**` label strip left a dangling `**` — the same trailing-emphasis trap as the original defect, reintroduced in new code.

---

## Carried into Phase 1 and 2

Known, deliberately unfixed. Line numbers verified as of commit `25d1eed`.

### Root causes left in place

| # | Item | Location |
|---|---|---|
| 1 | **Marker format not pinned in the prompt.** The instruction is `Format clearly labeled with … CAROUSEL CAPTION:`, so the model bolds the marker ~59% of the time (10 of 17 archives). Both consumers now tolerate it; the cause is a prompt change. Same for the infographic marker. | `generate_all_content.py:325`, `:331` |
| 2 | **`content-doctrine.md` and `voice-profile.md` are not read by the pipeline.** The live brand voice is the `writing_rules` string in the generator. Editing the markdown changes nothing. | `generate_all_content.py:90-117` |
| 3 | **`skills/branded-carousel/SKILL.md` is executable, not documentation.** Carousel HTML templates are regex-extracted from its `TEMPLATE N` headings at runtime; renaming a heading throws `AttributeError` and kills the build. | `generate_carousel_today.py:54-63` |

### Duplication to collapse

| # | Item | Location |
|---|---|---|
| 4 | **Posting schedule expressed in six places**, no shared constant: the schedule array; the Slack preview mirror; the plan skeleton's 11 keys; the carousel loop bound; the infographic loop bound. | `schedule_all_posts.cjs:590`; `send_to_slack.py:233`; `generate_all_content.py:193-250`; `build_carousel_today.cjs:28`; `cap_infographic_today.js:28` |
| 5 | **Marker normalisation duplicated across JS and Python.** Reciprocal `⚠ KNOWN DUPLICATION` comments name each other. They must stay in sync or the Slack preview will disagree with what publishes. | `schedule_all_posts.cjs:160-322` ↔ `send_to_slack.py:353-393` |
| 6 | **Format mix defined in five uncoordinated places** across three languages; every mismatch fails silently (an unrecognised header becomes a plain text post with no asset). | see `PIPELINE-AUDIT.md` §11f |

### Stale text that misleads

| # | Item | Location |
|---|---|---|
| 7 | Comment block `ALL 11 POSTS — 4 per day across 3 days / Schedule: 9:00 AM, 12:00 PM, 3:00 PM, 6:00 PM IST` — correct today but not authoritative. | `schedule_all_posts.cjs:625-626` |
| 8 | End-of-run summary printing **June 13–15 2026** dates and obsolete post types (Collaborative Article, Tool Spotlight, Weekly Roundup, Plain English, Unfair Advantage, Career/Income, Hot Take, Steal This). | `schedule_all_posts.cjs:1309-1312` |
| 9 | `README.md` post-schedule table describes a generator that no longer exists; six referenced state/log files do not exist. | `README.md:212-241` |
| 10 | `skills/illustration-formats/SKILL.md` mandates `@founderswing` and a "future of work" topic lane, contradicting `content-doctrine.md`'s `@harshchouksey` / Meta-Ads lane. Three brand identities coexist. | `skills/illustration-formats/SKILL.md:67`, `:10` |

### Unverified assumptions

| # | Item | Location |
|---|---|---|
| 11 | **`DOC_TITLE_MAX = 58` is unverified.** No run ever captured the input's `maxLength`. A read-only probe now logs the real value and warns on mismatch — **check the first run's output**. | `schedule_all_posts.cjs:237`; probe at `:1007-1017` |
| 12 | `TITLE_MIN_CLAUSE = 20` is a judgement call to stop `"Bad data"` being taken from `"Bad data. It clouds judgment…"`. | `schedule_all_posts.cjs:250` |
| 13 | **No timezone handling anywhere.** Times are literal strings interpreted in the LinkedIn account's timezone, while dates come from the local machine clock. Two different date conventions exist near midnight UTC. | `schedule_all_posts.cjs:590-601`; `build_carousel_today.cjs:7-11` |

### Live defects outside Phase 0 scope

| # | Item | Location |
|---|---|---|
| 14 | **`delete_all_scheduled.cjs` has no date guard** — deletes every scheduled post it can reach, no dry-run, no confirmation. Foot-gun for "cleaning up a bad batch". | `delete_all_scheduled.cjs:130-208` |
| 15 | **`ai_news_data.json` is stale** (2026-07-25) and nothing in `run_pipeline.py` refreshes it, yet it is fed to the planner every run as "Fresh AI & Marketing News". | `generate_all_content.py:167-173`; `fetch_ai_news_rss.py` never called |
| 16 | **Carousel PDF primary lookup path never succeeds.** The scheduler looks in `…/carousel-branded/carousel-{idx}/` but the builder writes PDFs one level up; every run silently falls back to `slack_downloads/`. "Fixing" one side without the other breaks uploads. | `schedule_all_posts.cjs:441`; `build_carousel_today.cjs:55,66` |
| 17 | **Two dead Slack upload paths**: `linkedin_posts_{date}.pdf` is never generated, and the `startup-strategy-carousel.pdf` fallback name is never produced. Both log "file not found" and continue. | `send_to_slack.py:312-318`, `:337` |
| 18 | **The 5 performance posts have hard-coded topics** identical on every run, ignore all data sources, and are never scheduled to LinkedIn. | `generate_all_content.py:559-607` |
| 19 | **Only `RANKED_BARS` is implemented** of the 5 documented infographic formats; the decision tree has no renderer. | `cap_infographic_today.js`; `skills/illustration-formats/SKILL.md` |
| 20 | **Carousel slides 1 and 6 carry hard-coded topic-independent copy** — `2026 AI BLUEPRINT`, `Autonomous AI Ops`, `NATIVE AI OPERATING SYSTEM` — on every carousel. Two Unsplash images are downloaded each run and then discarded. | `generate_carousel_today.py:66-76`, `:13-16` |
| 21 | **Poll truncation is silent**: questions cut at 140 chars, options at 30, with `...` appended. | `schedule_all_posts.cjs:395`, `:403` |
| 22 | **Accepted residual from Option A**: a scheduler crash can leave a topic recorded in `used_topics.json` whose post never went live. Fails in the safe direction (costs a topic, never duplicates a post); the crash itself is caught by `schedule_checkpoint.json`. | `generate_all_content.py:375-385` |
| 23 | **Unhandled edge case**: an unclosed *double* quote mid-title (`She said "go now`) is not cleaned — the rule only fires when the final word itself opens the quote. Rare; no archive hits it. | `schedule_all_posts.cjs:259-272` |
| 24 | **Caption text quality caps title quality.** Not one archived caption first-line is ≤58 chars, and only two contain a sentence break within 58. Now mostly moot since `slide_1_hook` is the primary source, but the fallback still inherits it. | — |

### Operational

| # | Item |
|---|---|
| 25 | **The first real run is still the first end-to-end test.** Every guard and parser is verified against archives, but nothing has actually scheduled a post. Watch the first run for: the checkpoint write, the Slack send, the `maxLength` probe output, and the first `Hook: ` line appearing in `linkedin_posts_*.txt`. |
| 26 | **The watermark is stale.** `last_scheduled_date: 2026-08-07` clears Guard C by exactly one day. Once tomorrow passes it will start aborting — correctly, but it will look like the guards broke the pipeline. |

---

## Rollback

Undo **all** Phase 0 hardening and return to the pipeline exactly as audited:

```bash
git reset --hard 5f43c80
```

That restores the modified files to their pre-hardening state. It does **not** touch `pipeline_state.json`, `used_topics.json`, `chrome-session/` or `.env` (none were modified), and it does not delete `state-backups/` or `.gitignore`-excluded files.

To undo Phase 0b only, keeping the Phase 0 safety guards:

```bash
git revert --no-edit HEAD
```

To undo only one file, for example the Slack gate:

```bash
git checkout 5f43c80 -- send_to_slack.py
```

To remove version control entirely and return to an untracked working tree:

```bash
rm -rf .git
```
