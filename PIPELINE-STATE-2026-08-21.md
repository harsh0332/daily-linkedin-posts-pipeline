# PIPELINE-STATE-2026-08-21.md

Read-only survey of the project as it stands on 2026-08-21, after changes made
by Antigravity in the same folder. Nothing was modified to produce this
document. Every claim below comes from the files on disk, not from memory.

**Baseline:** `10eb671` — "fix: follow LinkedIn's redesigned composer".

---

## 0. Git first

**There are no commits after `10eb671`.** `HEAD` is still my last commit. Every
change described here is uncommitted working-tree state.

`git diff --stat 10eb671`:

| File | Lines | What it is |
|---|---|---|
| `schedule_all_posts.cjs` | 452 | Scheduling step reordered (see §1) |
| `skills/branded-carousel/SKILL.md` | 533 | Rewritten; **one line is corrupted** (§7) |
| `linkedin_posts_today.txt` | 109 | Content replaced by hand (§4) |
| `carousel_data_1.json` / `_2.json` | 184 | Rebuilt for the new content |
| `schedule_checkpoint.json` | 51 | A completed 5-post run (§5) |
| `pipeline_state.json` | 4 | Watermark advanced (§5) |
| `used_topics.json` | 8 | +6 topics added by hand (§4) |

Untracked, all created 2026-08-21 13:33–13:37:

| File | Purpose |
|---|---|
| `get_linkedin_token.cjs` | OAuth flow, localhost:3000 callback |
| `linkedin_api_client.cjs` | Text / image / document publish helpers |
| `linkedin_api_credentials.json` | **Live client_secret + access_token** |
| `post_test_to_linkedin.cjs` | One-off image post (§2, §4) |
| `meta_ad_infographic.html`, `render_meta_ad_infographic.cjs`, `meta_comment_to_dm_architecture.png` | Assets for that one-off post |
| `missing_days.json` | Left by the 2026-08-20 generator run |

The mtime sweep (git-independent) agrees with git and adds one thing git could
not show: **`.env` was modified at 13:34**, the same minute the credentials JSON
was written.

---

## 1. Publishing path — the browser path still runs

**`schedule_all_posts.cjs` is not orphaned. It is the only thing the pipeline
publishes with, and it ran successfully this morning.**

`run_pipeline.py` is **unchanged**. Step 7 is still:

```
NODE_PATH=./carousel-routine/node_modules node schedule_all_posts.cjs
```

**There is no dispatcher and no flag.** A repo-wide grep for
`linkedin_api_client` returns exactly two files: the client itself and
`post_test_to_linkedin.cjs`. No pipeline file imports it. Nothing chooses
between a browser path and an API path, because the API path is not connected
to anything.

### What Antigravity changed in the scheduler

The scheduling block was not deleted — it was **moved earlier**. It now sets the
date and time on the clean composer *before* attaching the document, rather than
after. Given that "Start a post" now navigates to `/sharing/compose`, doing the
schedule first on a clean page is a defensible reordering.

My 2026-08-20 fixes all survive: the `Expand content types` lookup, the
`Document` anchor lookup, the shadow-aware upload, the navigation-tolerant
`waitForSelectorShadow`, and the anchor-aware `Done`.

### Proof it worked

`schedule_checkpoint.json` records a **completed** run:

```
status: complete   started 2026-08-21T07:41:10Z   finished 07:44:51Z
5 of 5 posts scheduled:
  1 carousel  08/24/2026 9:30 AM      3 carousel  08/26/2026 9:30 AM
  2 regular   08/25/2026 9:30 AM      4 regular   08/27/2026 9:30 AM
                                      5 regular   08/28/2026 9:30 AM
```

So there are **five posts sitting in your LinkedIn scheduled queue for 24–28
August**, two of them carousels, put there by the browser path.

The API files were created at **13:33–13:37, roughly six hours after** that
successful run. The API work is a later, separate experiment.

---

## 2. Carousels

### In the pipeline: still a real PDF document upload

Nothing about the carousel path changed. `run_pipeline.py` step 4 builds PDFs
with `build_carousel_today.cjs`, and `schedule_all_posts.cjs` uploads the PDF
into LinkedIn's "Share a document" dialog. **Carousels have not become images.**
The 08/24 and 08/26 posts were scheduled as `type: carousel` and the document
upload code is intact.

### Your premise about the API is not what the code says

`linkedin_api_client.cjs` contains `publishDocumentPost()`, which does a proper
three-step document flow:

1. `POST /rest/documents?action=initializeUpload`
2. `PUT` the PDF binary to the returned upload URL
3. `POST /rest/posts` with `content.media.id` set to the document URN

So the API *does* expose document upload, at least as this code uses it.
**However — nothing has ever called it.** `publishDocumentPost` has zero callers.
It is untested against your account and your token. Do not treat it as working.

The only API call that appears to have actually run is `publishImagePost`, from
`post_test_to_linkedin.cjs`.

### A timing anomaly worth checking manually

This is an inference from timestamps, not something I could confirm:

- The scheduling run finished at **07:44**.
- `carousel-routine/output/2026-08-21/…/linkedin-carousel-1.pdf` and `-2.pdf`
  were built at **13:26** — nearly six hours *later*.
- `linkedin_posts_today.txt` and both `carousel_data_*.json` were rewritten at
  **12:49**, also after the run.

At 07:41 the `2026-08-21` output directory did not exist yet, so the scheduler's
PDF lookup would have fallen through to `slack_downloads/carousel-N.pdf`, which
at that moment still held the **2026-08-20** files (1.05 MB / 1.07 MB). The
Aug-21 PDFs are 3.4 MB.

**Likely consequence: the two carousels scheduled for 24 and 26 August carry the
20 August artwork, not the Zomato/lead-form content now sitting in
`linkedin_posts_today.txt`.** I cannot see your scheduled queue, so please open
those two scheduled posts and confirm which deck is attached before they go out.

---

## 3. Guards — all still active, all still only in the browser path

Every guard is present in `schedule_all_posts.cjs`, and the checkpoint proves
two of them ran correctly today.

| Guard | Status | Evidence |
|---|---|---|
| Guard A (`START_DATE_OFFSET` sane) | active | present |
| Guard B (malformed state) | active | present |
| Guard C (past-date, no clamping) | active | present |
| Guard D (post 1 must be Monday) | active | 08/24/2026 is a Monday — it passed |
| Monday-anchored watermark | **active and demonstrably working** | last post Fri 08-28 → watermark `2026-08-30` (Sunday) → next batch starts Mon 08-31 |
| Per-post checkpoint | **active and working** | 5 entries with individual `scheduled_at` stamps |
| Empty-batch guard | active | `"There is no fallback batch"` still present |
| Carousel PDF existence assert | active | `fs.existsSync(post.assetPath)` still present |
| `DOC_TITLE_MAX` probe | active | still logs confirm/⚠ on the title field |

Two notes:

- **`DOC_TITLE_SELECTOR` is now dead code.** It is still declared, but the title
  step was rewritten to use its own inline finder. The finder is still
  shadow-DOM aware, so behaviour is fine; the constant is simply unused, and the
  diagnostic dump I had attached to that step is gone.
- **The API path has none of these guards.** No date logic, no checkpoint, no
  state, no asset assert. See §4.

---

## 4. What still feeds it — and what bypassed it

### The generation half is untouched

Every file is byte-identical to my last commit:

`generate_all_content.py`, `sources_loader.py`, `notes_loader.py`,
`config_loader.py`, `voice-profile.md`, `raw_notes.toml`,
`pipeline_config.json`, `send_to_slack.py`.

All six hard checkers are still defined and still wired in:
`find_unverifiable_claims`, `find_unsourced_figures`, `find_authority_claims`,
`find_invented_outcomes`, `find_profile_echoes`, `find_bad_sources`.

### But today's content never went through any of it

This is the finding that matters most in this section.

- The generator's own outputs — `review_flags.json`, `rejected_posts.json`,
  `used_angles.json`, `reddit_data.json` — are **all stamped 2026-08-20 19:25–19:26**.
- There is **no `linkedin_posts_20260821.txt`**. The generator writes one on
  every run. It was not run on 21 August.
- `linkedin_posts_today.txt` was rewritten at **12:49 on 21 August** with content
  that does not come from your pillars: Zomato dynamic retargeting, two-step
  Meta lead-form filtering, n8n + "Claude 3.5 Sonnet" lead routing, UGC hook
  architecture.

So the current batch file was **authored directly, bypassing the generator, the
pillar rotation, `raw_notes.toml`, `voice-profile.md`, all six hard checkers and
the Slack review gate.** Those components are all still present and correct —
they were simply stepped around.

Spot-checking that content against the checkers that would have run: slide 2 of
carousel 1 reads *"Active for 42 days in 2026 campaigns"* — a figure with no
allowed source named in the sentence, which `find_unsourced_figures` rejects.

### The one API post that appears to have gone out

`post_test_to_linkedin.cjs` publishes a hardcoded image post. Its text contains:

- *"burning 40%+ of your ad budget"*
- *"+340% higher lead-to-conversation rate"*
- *"-38% reduction in Cost Per Qualified Acquisition"*

None of these are in `raw_notes.toml`. Every one of them is the exact shape
`find_unsourced_figures` and `find_invented_outcomes` were built to stop. The
post also carries `lifecycleState: 'PUBLISHED'` — **it publishes immediately,
with no scheduling and no review**.

`used_topics.json` gained *"The High-Converting Comment-to-DM Pipeline (Meta Ads
Speed-to-Lead)"* at 13:40, three minutes after that script was last touched,
which is strong evidence it ran and published. I cannot verify from here whether
the post is live — please check your feed.

---

## 5. State

**`pipeline_state.json` is still the watermark, and `schedule_all_posts.cjs` is
still the only writer.**

```json
{ "last_scheduled_date": "2026-08-30",
  "last_updated": "2026-08-21T07:44:51.064Z" }
```

Written by the 07:44 run. Monday anchoring behaved exactly as designed: the last
post was Friday 28 August, and the watermark is the Sunday before the next
Monday, so the next batch starts **Monday 31 August** with no manual edit.

| File | Last written | By what |
|---|---|---|
| `pipeline_state.json` | 08-21 07:44 | scheduler, correctly |
| `schedule_checkpoint.json` | 08-21 07:44 | scheduler, status `complete` |
| `used_topics.json` | 08-21 13:40 | **by hand — 6 topics appended** |
| `used_angles.json` | 08-20 19:26 | generator, **not updated since** |

**These two have diverged.** `used_topics.json` gained six entries that no
generator run produced, while `used_angles.json` never moved. The angle cooldown
and thesis rotation therefore believe nothing has been used since 20 August. The
next real generator run will draw angles as if the last four days did not happen.

The API path writes no state at all.

---

## 6. The three changes you want to make

Good news: **none of them are affected by the API work**, because the API path is
not wired into generation. All three land in files that are untouched since my
last commit.

### 6a. Add your own writing as voice examples

**File: `voice-profile.md`** (live code — read at runtime into every system
prompt).

**There is a trap here, and it is mine.** `find_profile_echoes()` in
`generate_all_content.py` parses every line matching `Good:` / `Bad:` out of the
RULES section and **rejects any post containing that text**. It currently
extracts 12 examples. If you paste your own posts in as `Good:` examples, the
checker will treat your own sentences as forbidden text and reject any draft that
reuses them — which is the opposite of what you want from a voice sample.

Samples need to go in under a different heading that the echo parser does not
match, and the parser or the prompt needs to distinguish "don't copy this
wording" examples from "write like this" samples. This is a real design decision,
not a paste job. Flagging it, not fixing it.

### 6b. `format_mix` 2 carousel + 3 text → 3 + 2

**File: `pipeline_config.json`.** Validated by `config_loader.py` and
`config_loader.cjs` (mix must sum to `posts_per_batch`, which stays 5).

I simulated the change in memory without writing it. Only one slot moves:

```
Mon  ad-teardown          carousel -> carousel
Tue  benchmark            text     -> text
Wed  build-note           carousel -> carousel
Thu  community-question   text     -> text
Fri  update-or-hot-take   text     -> carousel   <-- changes
```

Two consequences to think about:

- **The Friday changelog pillar would have to produce a seven-slide carousel.**
  `load_changelog()` does not filter by format at all — it will accept the
  carousel slot without complaint — but its material is written for a text post
  ("what changed and what it means") and gives the model no slide structure.
- `build_carousel_today.cjs` would need `carousel_data_3.json`. The generator is
  config-driven and should emit it, but that path has never run with three
  carousels.

Supply is fine: `raw_notes.toml` has 21 carousel-capable angles.

### 6c. CTA asks for a comment before the DM

**File: `voice-profile.md`, rule 11** (line 198), plus the `Good:`/`Bad:` example
pair under it.

Rule 11 is **advisory only** — nothing enforces it in code. So this is a pure
prompt change with no checker to update. Note that editing the example lines
under it also changes what `find_profile_echoes` blocks, since it reads them.

---

## 7. Things that look broken — reported, not fixed

1. **`linkedin_api_credentials.json` is not gitignored.** It holds a live
   `client_secret` and a 350-character `access_token` (valid ~60 days from
   2026-08-21). A `git add -A` would commit working LinkedIn credentials. `.env`
   *is* ignored; this file is not.
2. **The same credentials exist twice** — in that JSON and in `.env` as
   `LINKEDIN_CLIENT_ID` / `LINKEDIN_CLIENT_SECRET` / `LINKEDIN_ACCESS_TOKEN` /
   `LINKEDIN_PERSON_URN`. Two copies to rotate, two chances to leak.
3. **`skills/branded-carousel/SKILL.md` line 455 is corrupted**:
   `This is a premium, hig### TEMPLATE 1 — Hook Slide (slide-01.html)` — a
   truncated sentence spliced into a heading, and the colour-palette section it
   introduced was deleted. This does **not** affect the pipeline:
   `build_carousel_today.cjs` never reads `SKILL.md`; it reads
   `carousel_data_N.json`. The file is used by the agent-driven scripts
   (`generate_branded_carousel.py` and friends), which `run_pipeline.py` does not
   call.
4. **`used_topics.json` and `used_angles.json` have diverged** (§5).
5. **`DOC_TITLE_SELECTOR` is dead code** in `schedule_all_posts.cjs`.
6. **The API client has no scheduling.** All three publish functions hardcode
   `lifecycleState: 'PUBLISHED'`. There is no date parameter anywhere. If the API
   path is ever adopted for the daily batch, the entire scheduling design —
   watermark, Guards A–D, checkpoint — has no equivalent and posts would go out
   the moment the script runs.
7. **Nothing is committed.** A successful production run, a live token, and a
   reordered scheduler all exist only in the working tree.

---

## Summary in one paragraph

The pipeline still publishes through Puppeteer, and it worked: five posts,
including two carousels, were scheduled to 24–28 August this morning, with every
Phase 0–3 guard intact and the Monday-anchored watermark advancing correctly to
`2026-08-30`. The LinkedIn API work is a genuine, functional client but it is an
island — nothing imports it except a one-off script that published a hardcoded
image post containing invented performance figures, bypassing all six hard
checkers. The generation half of the pipeline is byte-identical to my last
commit and fully intact; today's batch simply went around it, with content hand-
written straight into `linkedin_posts_today.txt`. The two most urgent items are
the ungitignored credentials file and confirming which PDF is actually attached
to the carousels already scheduled for Monday and Wednesday.
