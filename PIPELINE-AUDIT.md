# PIPELINE-AUDIT.md

Read-only architecture audit of `daily-linkedin-posts-pipeline`.
Audit date: 2026-08-07. No files were modified, created, moved or deleted except this report. No pipeline step, script, build or network call was executed.

**Credential note:** `.env` exists at the project root. Only variable NAMES are reported anywhere in this document. No values were printed or copied.

---

## 1. REPO MAP

### 1.1 Directory tree (2–3 levels, excluding `node_modules/`, `chrome-session/` internals)

```
daily-linkedin-posts-pipeline/
├── .env                              # secrets (names only listed below)
├── .env.example
├── README.md                         # pipeline documentation (partly stale)
├── content-doctrine.md               # topic north-star
├── voice-profile.md                  # writing voice rules
├── help.txt                          # (16 KB, older notes)
├── raw_notes.txt                     # manual client-win input for the planner
│
├── run_pipeline.py                   # ★ THE ENTRY POINT (7 shell steps)
│
├── commands/
│   └── linkedin-content.md           # Reddit post writing rules + output format
├── daily-linkedin-posts/
│   └── SKILL.md                      # master agent orchestration skill (10 steps)
├── skills/
│   ├── branded-carousel/
│   │   ├── SKILL.md                  # carousel design system + 5 HTML slide templates
│   │   └── FORMATS.md                # 6 carousel format templates + decision tree
│   ├── illustration-formats/SKILL.md # 5 infographic formats + decision tree
│   ├── linkedin-ai-news-engine/SKILL.md      # 7 AI-news archetypes
│   └── linkedin-performance-engine/SKILL.md  # 5 analytics-driven archetypes
│
├── fetch_reddit_rss.py               # ★ ACTIVE Reddit source (RSS)
├── fetch_reddit_apify.py             # alternate source (Apify actor) — not wired in
├── fetch_reddit_fallback.py          # alternate source (Reddit .json) — not wired in
├── fetch_reddit_puppeteer.cjs/.js/_core.cjs  # alternate browser scrape — not wired in
├── fetch_ai_news_rss.py              # AI news RSS — NOT called by run_pipeline.py
│
├── generate_all_content.py    # ★ ACTIVE generator (11 posts + 5 perf + JSONs)
├── generate_posts_via_openrouter.py  # legacy generator — not wired in
├── generate_posts_via_anthropic.py   # legacy generator — not wired in
├── generate_ai_news.py / _part2.py   # legacy — not wired in
├── generate_carousel_today.py        # ★ slide HTML renderer (called by build script)
├── generate_infographic_today.py     # legacy infographic HTML writer — not wired in
├── generate_daily_paper.py           # newspaper HTML/PDF compiler — not wired in
├── correct_posts.py                  # post-hoc LLM editor — not wired in
├── write_today_data.py               # legacy combiner — not wired in
│
├── build_carousel_today.cjs          # ★ ACTIVE carousel builder (PNG + PDF)
├── build_carousel*.cjs/.py           # older variants — not wired in
├── cap_infographic_today.js          # ★ ACTIVE infographic renderer (3 PNGs)
├── cap_infographic*.cjs/.js/.py      # older variants — not wired in
│
├── send_to_slack.py                  # ★ ACTIVE Slack delivery (see §12 — parser stale)
├── send_slack_message.py, slack_deliver*.py, slack_send_*.py  # legacy
├── check_slack_for_posts.py          # legacy
│
├── schedule_all_posts.cjs            # ★ ACTIVE LinkedIn scheduler (1134 lines)
├── schedule_four_posts.cjs / _other_posts.cjs / _post3.cjs / _post4.cjs  # legacy
├── schedule_meta_mcp_post.cjs        # one-off
├── delete_all_scheduled.cjs          # ⚠ deletes ALL scheduled posts, no date guard
├── edit_scheduled_posts.cjs, verify_scheduled_posts.cjs, get_scheduled_contents.cjs
├── inspect_*.cjs                     # DOM inspection helpers
├── login_linkedin.cjs                # opens LinkedIn with the saved profile
├── post_urgent_*.cjs (5 files)       # one-off "post right now" scripts
│
├── aigen_image.py                    # Gemini image generation — not wired in
├── fetch_carousel_image.py           # image sourcing — not wired in
│
├── pipeline_state.json               # ★ STATE: last scheduled date
├── used_topics.json                  # ★ STATE: topic de-dup memory (76 strings)
├── reddit_data.json                  # cache: 80 fetched Reddit items
├── ai_news_data.json                 # cache: 27 news items (stale, 2026-07-25)
├── carousel_data.json, carousel_data_{1,2,3}.json      # slide copy for 3 carousels
├── infographic_data.json, infographic_data_{1,2,3}.json # chart data for 3 infographics
├── linkedin_posts_today.txt          # ★ scheduler input (11 posts)
├── linkedin_posts_YYYYMMDD.txt       # dated archive of the same
├── performance_posts_YYYYMMDD.txt    # 5 performance posts (Slack/manual only)
├── linkedin-infographic-template.html # ★ infographic base template
├── linkedin-infographic-{1,2,3}.html/.png  # rendered infographics
├── linkedin-infographic-YYYYMMDD.png # dated copy of infographic #1
├── error_screenshot.png              # last scheduler crash screenshot
│
├── carousel-routine/
│   ├── package.json                  # puppeteer ^25.3.0, node >=18
│   ├── node_modules/
│   ├── brand-kit.html                # 49 KB brand design system
│   ├── output/YYYY-MM-DD/carousel-branded/   # ★ generated PDFs + slide PNGs
│   ├── temp/carousel-branded-{1,2,3}/        # intermediate slide HTML
│   ├── render.js, render-pdf.js, compile_pdf.js, screenshot_all.js  # legacy renderers
│   ├── cap_infographic*.js (8 variants)      # legacy
│   ├── capture_source.js             # site screenshot helper
│   └── schedule_linkedin.js          # legacy scheduler
│
├── chrome-session/                   # ★ Puppeteer Chrome profile = LinkedIn login
├── slack_downloads/                  # 81 files: run screenshots + carousel PDFs
├── sample-outputs/                   # frozen 2026-06-12 example run
├── screenshots/                      # empty
├── user_uploads/, fresh_clinic_uploads/  # one-off manual assets
└── daily-linkedin-posts/, commands/, skills/  # (see above)
```

### 1.2 File count and approximate LOC

| Measure | Count |
|---|---|
| Total files (excl. `node_modules/`, `chrome-session/`) | 518 |
| Python files | 50 (~6,287 lines) |
| JS/CJS files | 61 (~9,614 lines at depth ≤2) |
| Markdown docs | 10 (~2,816 lines) |
| PNG / PDF / HTML artefacts | 237 / 32 / 86 |
| JSON data + state | 18 |

Roughly **16,000 lines of executable code**, of which the active pipeline path is about **2,900 lines** (`run_pipeline.py` 45, `fetch_reddit_rss.py` 79, `generate_all_content.py` 597, `generate_carousel_today.py` 189, `build_carousel_today.cjs` 75, `cap_infographic_today.js` 86, `send_to_slack.py` 291, `schedule_all_posts.cjs` 1,134). The remaining ~80% is superseded variants and one-off scripts.

### 1.3 Package / dependency files

- **`carousel-routine/package.json`** — the only dependency manifest. Single dependency: `puppeteer ^25.3.0`. `engines.node >= 18`. Scripts `render` / `render-pdf` point at legacy renderers not used by the active path.
- **No root `package.json`** — root `.cjs`/`.js` scripts resolve modules via `NODE_PATH=./carousel-routine/node_modules`, set inline in `run_pipeline.py:28` and `:31,37`.
- **No `requirements.txt`, no virtualenv.** All Python uses stdlib only (`urllib.request`, `json`, `ssl`, `xml.etree`, `datetime`, `subprocess`). No `requests`, no `openai` SDK — HTTP is hand-rolled.

**What the stack tells you:** Node + Puppeteer for all rendering and browser automation; Python stdlib for all fetching, LLM calls and Slack; no framework, no test suite, no linter, no CI, no lockfile at root.

### 1.4 Environment variables (NAMES ONLY)

Present in `.env`: `SLACK_BOT_TOKEN`, `SLACK_CHANNEL_ID`, `OPENAI_API_KEY`, `APIFY_API_KEY`, `SCRAPINGDOG_API_KEY`.

Declared in `.env.example` but **absent from `.env`**: `OPENROUTER_API_KEY`, `ANTHROPIC_TOKEN`, `GEMINI_API_KEY`.

Consequence: every script that reads `OPENROUTER_API_KEY` (`generate_posts_via_openrouter.py`, `correct_posts.py`), `ANTHROPIC_API_KEY` (`generate_posts_via_anthropic.py`) or `GEMINI_API_KEY` (`aigen_image.py`) exits immediately. Only the `OPENAI_API_KEY` path runs.

### 1.5 Documentation that describes intended behaviour

**`README.md`** — describes a 5-phase pipeline producing 16 posts/day (4 Reddit + 7 AI news + 5 performance), lists every script by role, gives a manual step-by-step run order, a post-schedule table, and a deduplication-rules section. It is **partly stale**: it documents `OPENROUTER_API_KEY`/`ANTHROPIC_API_KEY` as the LLM keys (actual: `OPENAI_API_KEY`), it references six state/log files that do not exist (see §7.6), and its post-schedule table lists post types that no longer match what the generator emits (see §6.3). Its most useful surviving content is the explicit **cadence caveat** (README.md:230-232): the analytics report recommends ≤7 posts/week while the pipeline produces 16/day, and that contradiction is recorded as *deliberately deferred, not resolved*.

**`content-doctrine.md`** — the topic north star. Persona: Meta Ads expert + AI automation consultant. Audience: D2C brands scaling past ₹10L/mo, B2B/service businesses, solopreneurs. A 4-part topic filter (Reach, Stakes, Altitude, Edge), a DROP list (no general AI news relay, no developer-only coding, no generic startup advice, no plain feature relay) and an AMPLIFY list (n8n workflow layouts, Meta Ads strategies, real ROI metrics, lead-to-sale automations, AI agents for ops).

**`voice-profile.md`** — writing voice: authority-driven, declarative, blunt-but-helpful, analytical. Rules: declarative hooks under 120 chars, sentence-case headings, no em-dashes globally, prose over bullets, direct openings, three standard CTAs. Full banned-vocabulary and banned-LinkedIn-pattern lists.

**`daily-linkedin-posts/SKILL.md`** — the 10-step agent orchestration procedure (Apify fetch → infographic research → 4 Reddit posts → branded carousel → infographic screenshot → run-log writes → 7 AI news posts → 5 performance posts → Slack messages → Slack file uploads). This describes the **agent-driven** workflow, which is a different execution path from `run_pipeline.py` (see §2.4).

**`commands/linkedin-content.md`** — Reddit post writing rules, 6-part post structure, 5 hook styles, 10 carousel hook styles, banned vocabulary, and the exact output format with `━━━` section separators.

**Skill files** for the AI-news engine, performance engine, carousel formats and illustration formats — each a procedure with scoring rules, archetypes and output templates. Reproduced where relevant in §4 and §5.

**Two doc/code contradictions worth flagging now:** `skills/illustration-formats/SKILL.md:67` and `skills/branded-carousel/FORMATS.md` still specify the **`@founderswing`** brand handle and a "future of work / AI impact" topic lane, while `content-doctrine.md`, `voice-profile.md` and the active generator all specify **`@harshchouksey`** and a Meta-Ads/n8n lane. The carousel HTML templates are read from `skills/branded-carousel/SKILL.md` at runtime by `generate_carousel_today.py:54-63`, so that file is live code, not just docs.

---

## 2. ENTRY POINTS & EXECUTION FLOW

### 2.1 The entry point

**`run_pipeline.py`** — 45 lines. `main()` at line 15 is the function that starts the run. There is no CLI argument parsing, no config file, no flags. It is invoked as:

```bash
python3 run_pipeline.py
```

`run_step(description, command)` (line 5) is a thin wrapper: it prints a banner, runs the command through `subprocess.run(command, shell=True)`, and on any non-zero exit code prints an error and calls `sys.exit(returncode)`. **Every step is fail-fast and there is no retry, no rollback and no resume.**

### 2.2 What happens when you give Antigravity a prompt — end to end

Antigravity (the agent) is the operator, not a component. There is no code in this repo that receives an agent prompt. The agent's role is to decide *which* of the two paths below to run and to run it as a shell command. Traced end to end for the scripted path:

1. **Trigger.** The agent runs `python3 run_pipeline.py` (or the individual steps). Nothing is scheduled; nothing watches a queue.
2. **Step 1 — Fetch** (`run_pipeline.py:19`): `python3 fetch_reddit_rss.py`. Loops 10 subreddit RSS feeds, parses Atom entries, writes **`reddit_data.json`** (overwrite). Note this step's description says "Reddit RSS & AI News Data" but it does **not** fetch AI news — `fetch_ai_news_rss.py` is never called (see §3.5).
3. **Step 2 — Generate** (`run_pipeline.py:22`): `python3 generate_all_content.py`.
   - 3a. Loads `used_topics.json`, `raw_notes.txt`, `reddit_data.json`, `ai_news_data.json`.
   - 3b. **Planning call** → one LLM call returns a JSON plan for 11 posts (fixed slot structure: 3 carousels, 3 infographics, 2 polls, 3 text).
   - 3c. Appends every planned topic to `used_topics.json` and **writes it immediately, before any post is generated** (line 343).
   - 3d. **11 writing calls**, one per post, sequential, 1s apart. Any single failure → `sys.exit(1)`.
   - 3e. Writes `linkedin_posts_today.txt` and `linkedin_posts_YYYYMMDD.txt`.
   - 3f. **3 carousel-JSON calls** → `carousel_data_{1,2,3}.json` (+ `carousel_data.json` for #1).
   - 3g. **3 infographic-JSON calls** → `infographic_data_{1,2,3}.json` (+ `infographic_data.json`).
   - 3h. **5 performance-post calls** (hard-coded topics) → `performance_posts_YYYYMMDD.txt`.
   - Total: **23 LLM calls per run.**
4. **Step 3 — Copy** (`run_pipeline.py:25`): `cp linkedin_posts_$(date +%Y%m%d).txt linkedin_posts_today.txt`, suffixed `|| true` so it cannot fail the run. (Redundant — step 2 already wrote both.)
5. **Step 4 — Carousels** (`run_pipeline.py:28`): `node build_carousel_today.cjs`. For each of 3 carousels: shells out to `python3 generate_carousel_today.py <json> <tempdir>` to write 7 slide HTML files, screenshots each at 1080×1080 @2x, assembles an HTML page of the 7 PNGs, prints it to PDF, and copies the PDF to `slack_downloads/carousel-{idx}.pdf`.
6. **Step 5 — Infographics** (`run_pipeline.py:31`): `node cap_infographic_today.js`. For each of 3 datasets: fills `linkedin-infographic-template.html` with `infographic_data_{idx}.json`, serves it on `localhost:876{1,2,3}`, screenshots 1080×1080 → `linkedin-infographic-{idx}.png`.
7. **Step 6 — Slack** (`run_pipeline.py:34`): `python3 send_to_slack.py`. Posts text messages and uploads PDF/PNG files to the Slack channel.
8. **Step 7 — Schedule** (`run_pipeline.py:37`): `node schedule_all_posts.cjs`. Launches a **non-headless** Chrome with the saved `chrome-session/` profile, parses `linkedin_posts_today.txt` into 11 post objects, computes dates from `pipeline_state.json`, and drives LinkedIn's composer once per post: open composer → attach poll/document/image → type caption → open schedule modal → set date and time → Next → Schedule. After all 11 succeed, it rewrites `pipeline_state.json`.
9. **Final published post.** The pipeline does **not** publish. It hands 11 posts to **LinkedIn's own native scheduler**; LinkedIn publishes them at the stored times over the following three days. The pipeline has no further involvement and never reads back what happened.

### 2.3 Architecture pattern

**A linear, fail-fast shell pipeline (a chain of scripts) orchestrated by one Python driver.** It is not an agent loop, not a task queue, not a DAG. State is passed between stages exclusively through files on disk. Two stages (`build_carousel_today.cjs` → `generate_carousel_today.py`) nest a second process, so the shape is a chain with one shell-out, not a tree.

### 2.4 The second, parallel execution path

`daily-linkedin-posts/SKILL.md` describes a **different** pipeline that the agent executes step by step itself: Apify for Reddit, WebSearch for infographic datasets, the agent writing the posts directly (not `generate_all_content.py`), the branded-carousel skill for slides, Slack MCP for messages, and run-logs (`carousel-hook-log.json`, `infographic-run-log.json`, `performance-run-log.json`) that the scripted path never touches and which do not exist on disk.

Both paths write to the same output files. Which one ran on a given day is not recorded anywhere. Evidence on disk (`carousel_data_*.json`, `infographic_data_*.json`, `pipeline_state.json`, all dated 2026-08-04) indicates the **scripted path via `run_pipeline.py` is the one in current use**; the SKILL.md path's distinctive artefacts (the three run-log JSONs, `ai_news_posts_*.txt`) are absent.

### 2.5 Scheduler / cron / watcher

**None.** `crontab -l` returns "no crontab for harshchouksey". `~/Library/LaunchAgents` contains only Adobe and Google updater agents — nothing referencing this project. There is no file watcher, no daemon, no GitHub Action (no `.github/`), and no `.git` directory at all.

**Every run is manually triggered.** The only automatic scheduling in the system is LinkedIn's own, after `schedule_all_posts.cjs` has handed posts over.

---

## 3. CONTENT SOURCING (the Reddit layer)

### 3.1 Active source: `fetch_reddit_rss.py`

This is the only fetcher `run_pipeline.py` calls.

**Subreddits — exactly as configured (`fetch_reddit_rss.py:14`):**

```python
subreddits = ["facebookads", "PPC", "n8n", "Ecommerce", "SaaS", "marketing", "entrepreneur", "startups", "Automation", "artificial"]
```

**URL pattern (`fetch_reddit_rss.py:22`):**

```python
url = f"https://www.reddit.com/r/{sub}/top/.rss?t=week&limit=20"
```

**Sorting / time filter:** `top`, `t=week`, `limit=20` per subreddit. Hard-coded in the f-string; there is no config knob.

**Request behaviour:** a per-subreddit User-Agent `LinkedInPipelineBot/1.0 (by /u/harshchouksey; sub={sub})` (line 25-26 — note this **overwrites** the browser User-Agent defined at line 15-17, which is dead code). SSL verification is disabled (`ctx.verify_mode = ssl.CERT_NONE`, line 12). 3 attempts per subreddit with 4s/8s/12s backoff, then a flat 3s sleep between subreddits.

### 3.2 Filters that decide a topic is worth posting

**There are no numeric filters at the fetch layer.** The only exclusion is:

```python
if not title or title.startswith("/u/"):
    continue
```

(`fetch_reddit_rss.py:54-55` — drops empty titles and user-profile entries.)

There is **no score threshold, no comment threshold, no keyword allow-list, no keyword deny-list, and no recency limit** beyond `t=week` in the URL. Critically, engagement metrics are **fabricated** (`fetch_reddit_rss.py:61-62`):

```python
"ups": 100,
"num_comments": 10,
```

Every item is written with `ups: 100` and `num_comments: 10` regardless of its real score, because RSS does not expose them. Any downstream logic that appears to weigh engagement is weighing constants.

The real filtering is **entirely delegated to the LLM planner** in `generate_all_content.py`, which is asked to avoid `used_topics.json` and follow the doctrine. It is a soft, unverified instruction — no code checks the result.

### 3.3 Candidate volume per run

- Requested: 10 subreddits × 20 = **200 candidates maximum**.
- Actually retrieved on the last run: **80 items**, from only 4 subreddits — `r/facebookads` 20, `r/PPC` 20, `r/SaaS` 20, `r/startups` 20. The other six (`n8n`, `Ecommerce`, `marketing`, `entrepreneur`, `Automation`, `artificial`) returned nothing and were silently skipped after their 3 retries.
- Passed to the planner: `reddit_posts[:20]` (`generate_all_content.py:261`) — **the first 20 items only**, which in the last run means all 20 are from `r/facebookads` alone.
- Surviving to posts: **11 topics**, chosen by the LLM.

So the effective funnel is 200 requested → 80 fetched → **20 seen by the model** → 11 used. The `[:15]` slice at line 82 is dead (the variable is reassigned at line 159).

### 3.4 Other sources besides Reddit

| Source | File | Wired into `run_pipeline.py`? |
|---|---|---|
| Reddit RSS | `fetch_reddit_rss.py` | **Yes** — step 1 |
| Reddit via Apify actor `trudax~reddit-scraper-lite` | `fetch_reddit_apify.py` | No (different subreddit list: entrepreneur, startups, artificial, SideProject, ChatGPT, passive_income; `maxItems: 80`) |
| Reddit `.json` endpoints | `fetch_reddit_fallback.py` | No (same 6 subs as Apify, `t=week`) |
| Reddit via Puppeteer | `fetch_reddit_puppeteer.cjs/.js/_core.cjs` | No |
| **AI news RSS** — TechCrunch AI + VentureBeat AI | `fetch_ai_news_rss.py:13-16` | **No** — never invoked |
| **`raw_notes.txt`** — manual client wins | read at `generate_all_content.py:151-157` | **Yes**, highest planner priority |
| `ai_news_data.json` | read at `generate_all_content.py:167-173` | **Yes**, but the file is only ever refreshed by manually running `fetch_ai_news_rss.py` |
| WebSearch for infographic datasets | `daily-linkedin-posts/SKILL.md` STEP 2B | Agent path only |
| ScrapingDog (X/Twitter research) | `skills/linkedin-ai-news-engine/SKILL.md:37` | Agent path only, 4 calls/run budget |

**The AI-news gap is material:** `ai_news_data.json` was last written 2026-07-25 and is fed to the planner on every run as "Fresh AI & Marketing News". As of this audit it is 13 days stale and getting staler with every run.

**`raw_notes.txt`** currently contains only commented-out example lines, so the planner receives it as effectively empty:

```
# Drop any quick bullet points or client win notes here before running the pipeline.
# Example:
# - Scaled a D2C fashion brand past 25L/mo using n8n WhatsApp abandoned cart flows.
# - Fixed lead response lag for a B2B SaaS client, reducing cost-per-qualified-lead by 35%.
```

### 3.5 How a raw Reddit item becomes a post idea

**Stage 1 — normalisation** (`fetch_reddit_rss.py:57-65`). Each Atom entry becomes:

```json
{
  "subreddit": "r/facebookads",
  "title": "$255,692.00 In Sales With $27,733.32 Ad Spend (9.21 ROAS) In The Last 9 Days...",
  "selftext": "Good day, Redditors. \nI'm continuing to write a weekly update...",
  "ups": 100,
  "num_comments": 10,
  "url": "https://www.reddit.com/r/facebookads/comments/...",
  "image_url": null
}
```

`selftext` is the entry's `<content>` with `<p>/<br>/<div>` converted to newlines and all other tags stripped; `image_url` is the first `<img src>` found in that content, else `null`.

**Stage 2 — planning.** The first 20 of these objects are serialised into the planner's user prompt alongside `used_topics.json`, `raw_notes.txt` and 15 news items. One LLM call returns a JSON plan. Each Reddit item is not mapped 1:1 to a post — the model is instructed to *reframe* whatever it picks "around performance marketing, ads, funnels, or operations automation".

**Stage 3 — plan slot.** The output for one post looks like:

```json
"1. CAROUSEL 1": {
  "topic": "Carousel #1 Workflow Topic",
  "hook_style": "Curiosity Gap",
  "slide_1_hook": "Hook text (6-8 words max)",
  "prompt_details": "Details for slides 2-6 (case study flow) and slide 7 CTA."
}
```

**Stage 4 — per-post prompt.** `topic`, `prompt_details` and the type-specific fields are interpolated into one of four prompt shapes (§4.3) and sent as a second LLM call.

**Stage 5 — output.** The returned text is written into `linkedin_posts_today.txt` under a `====`-delimited header (`1. CAROUSEL 1`, `2. INFOGRAPHIC 1`, …). That file is the sole input to the scheduler.

**The Reddit URL, subreddit and image are dropped at stage 2.** Nothing downstream of the planner links a post back to its source thread, so there is no source attribution and no way to check after the fact which thread produced which post.

---

## 4. CONTENT GENERATION

### 4.1 Models called, and where

| Model | Endpoint | File | Function | Calls per run |
|---|---|---|---|---|
| **`gpt-4o`** | `https://api.openai.com/v1/chat/completions` | `generate_all_content.py:28,37` | `call_llm()` (line 34) | **23** |

That is the entire active model surface. No Gemini, no OpenRouter, no Anthropic call is made.

> **RESOLVED in Phase 3d (2026-08-13).** At audit time the naming was misleading in three places: the file was `generate_all_content_gemini.py`, the function was `call_gemini()`, and every error message said "OpenRouter" — three providers named in one file that talks to a fourth. All three were renamed. **Superseded by Phase 3e (2026-08-13):** the provider is now configurable (`llm.base_url` / `llm.model` / `llm.api_key_env` in `pipeline_config.json`), so the file and function are provider-neutral: `generate_all_content.py` and `call_llm()`. The live provider is Mesh, an OpenAI-compatible proxy, serving `openai/gpt-4o`.

The 23 calls break down as: 1 planning + 11 posts + 3 carousel JSON + 3 infographic JSON + 5 performance posts.

**Request parameters (`generate_all_content.py:35-42`):**

```python
payload = {
    "model": "gpt-4o",
    "messages": [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": prompt}
    ],
    "max_tokens": max_tokens
}
```

`max_tokens=4000` for every call. **No `temperature`, no `top_p`, no `seed`, no `response_format` is ever set** — the API default temperature (1.0) applies to all 23 calls including the two that must return parseable JSON.

**Retry (`generate_all_content.py:51-76`):** 5 attempts. On HTTP 429 it sleeps `10 * (attempt+1)` seconds (10/20/30/40/50) and retries. On **any other HTTP error it `break`s immediately** — no retry. On any non-HTTP exception it prints a traceback and `break`s. Returns `None` on exhaustion, which the callers treat as fatal.

Dormant model paths, not reachable with the current `.env`: `generate_posts_via_openrouter.py` (OpenRouter), `generate_posts_via_anthropic.py` (Anthropic), `correct_posts.py` (OpenRouter), `aigen_image.py` (Gemini image models).

### 4.2 Shared writing rules — VERBATIM

`generate_all_content.py:90-117`. This block is interpolated into both the main system prompt and the performance system prompt.

```
WRITING RULES:
1. Conversational First-Person Founder Voice ("I", "We", "Harsh Chouksey"). Write directly as Harsh Chouksey sharing real breakdown scenarios, client case studies, and hands-on performance marketing / n8n workflow implementations.
2. Grounded, results-driven tone. Emphasize actual metrics, time saved, and campaign conversions.
3. No technical developer jargon: explain things simply for business owners and founders scaling past ₹10L/mo.
4. No em-dashes anywhere. Use normal commas, semicolons, or periods instead.
5. Do NOT include any headline, title, or header for the posts (like 'Headline: ...' or bold title lines). Start the content of the post directly with its first sentence/hook.
6. Post structure: Pain Hook (1-2 lines) -> Technical Teardown -> Practical Solution (n8n/Meta/WhatsApp) -> Proof Metrics -> High-Intent Lead CTA.
7. Banned words (NEVER USE ANY): delve, underscore, vibrant, tapestry, interplay, intricate, garner, pivotal, showcase, foster, align with, landscape, key (as adjective), leverages, encompasses, facilitates, utilized, commenced, subsequent to, prior to, in order to, stands as, serves as, is a testament to, plays a vital role, plays a significant role, plays a crucial role, enduring legacy, lasting impact, indelible mark, it's important to note, it's worth noting, no discussion would be complete without, moreover, furthermore, in addition, setting the stage for, marking a shift, evolving landscape, reflects broader trends, game-changer, supercharge, real results, real strategy, real conversations, disruptive, hustle, grind, crush it, synergy, paradigm shift, thought leader, go viral, revolutionary, groundbreaking, unprecedented, cutting-edge, state-of-the-art, next-generation, empower, unlock, journey, ecosystem, world-class, comprehensive, curated, innovative, transformative, passionate, excited to share.
8. Banned LinkedIn patterns:
   - "No X. No Y. Just Z."
   - "It's not just about X. It's about Y."
   - "If you're serious about X, [do this]"
   - "And here's the kicker"
   - "X changed everything"
   - "Enter:"
   - "The best part? [short answer]"
   - Email sign-off language ("To your success")
9. Banned contrast constructions:
   - "This isn't about X, it's about Y"
   - "Not because of X. But because of Y."
   - "Rather than X, do Y"
   - "But rather"
   - "Not just X, but also Y"
   - "Not only X, but Y"
10. Varied sentence lengths. Specific numbers over adjectives. Short punchy lines (under 12 words) with plenty of whitespace.
11. High-Intent Client Lead CTA: Include a clear DM action trigger in at least 50% of posts (e.g., "DM me 'SCALE' to get our 3-node n8n workflow blueprint", "DM me 'AUDIT' to review your lead response pipeline").
```

### 4.3 Main writing system prompt — VERBATIM

`generate_all_content.py:119-121`. `{writing_rules}` expands to the block above.

```
You are Harsh Chouksey's AI copywriter. Write a single, highly engaging LinkedIn post based on the instructions, reframing the topic around performance marketing, ads, funnels, or operations automation.
{writing_rules}
```

### 4.4 Planning system prompt — VERBATIM

`generate_all_content.py:176-251`. This is the prompt that decides all 11 topics, the format mix and the hook styles.

```
You are Harsh Chouksey's Chief Content Planner. Your job is to select 11 completely fresh, highly relevant marketing and operations automation topics for the next 3 days' LinkedIn posts.
Aapka niche hai: Meta Ads scaling, n8n workflow automation, WhatsApp sales CRM funnels, D2C conversions, and AI business agents.

You must choose topics based on:
1. Harsh's Raw Notes / Recent Client Wins (HIGHEST PRIORITY if present)
2. Fresh Reddit startup/business posts (provided below)
3. Fresh AI and marketing news (provided below)
4. Content Doctrine Guidelines (Meta Ads, n8n, WhatsApp CRM, funnels, AI agents).

CRITICAL RULES:
1. You MUST NOT choose any topic that is similar to the already used topics list. Avoid repetition! Every topic must be fresh.
2. High-Intent Client Lead CTAs: At least 50% of the posts must include a direct lead magnet trigger (e.g. "DM me 'AUDIT'", "DM me 'CAPI'", "DM me 'WORKFLOW'").
3. Humanized Founder Voice: Write from Harsh Chouksey's perspective using real numbers, specific tech stacks (n8n, Meta Ads, WhatsApp API), and first-person case studies.

Generate a JSON object containing the plan for the 11 posts. Output ONLY the JSON. No markdown wrappers.
The JSON must have the following structure:
{
  "1. CAROUSEL 1": {
    "topic": "Carousel #1 Workflow Topic",
    "hook_style": "Curiosity Gap",
    "slide_1_hook": "Hook text (6-8 words max)",
    "prompt_details": "Details for slides 2-6 (case study flow) and slide 7 CTA."
  },
  "2. INFOGRAPHIC 1": {
    "topic": "Infographic #1 Data Metric",
    "prompt_details": "Details of the specific 2025/2026 data points, categories, and metrics to use."
  },
  "3. POLL 1": {
    "topic": "Poll #1 Topic",
    "question": "A short engaging question (max 140 chars)",
    "options": ["Option 1 (max 30 chars)", "Option 2 (max 30 chars)", "Option 3 (max 30 chars)", "Option 4 (max 30 chars)"],
    "prompt_details": "Additional details on setup and explanation."
  },
  "4. TEXT 1": {
    "topic": "Direct-Response Case Study",
    "archetype": "Case Study",
    "prompt_details": "Pain hook, technical teardown, proof metrics, DM magnet CTA."
  },
  "5. CAROUSEL 2": {
    "topic": "Carousel #2 Scaling Guide",
    "hook_style": "Specific Result",
    "slide_1_hook": "Hook text (6-8 words max)",
    "prompt_details": "Details for slides 2-6 (framework flow) and slide 7 CTA."
  },
  "6. INFOGRAPHIC 2": {
    "topic": "Infographic #2 Benchmark Data",
    "prompt_details": "Details of the specific benchmark data and breakdown."
  },
  "7. POLL 2": {
    "topic": "Poll #2 Operational Choice",
    "question": "A short engaging question (max 140 chars)",
    "options": ["Option 1 (max 30 chars)", "Option 2 (max 30 chars)", "Option 3 (max 30 chars)", "Option 4 (max 30 chars)"],
    "prompt_details": "Additional details on setup and explanation."
  },
  "8. TEXT 2": {
    "topic": "Tool Spotlight / Unfair Advantage",
    "archetype": "Tool Spotlight",
    "prompt_details": "Automation workflow breakdown, specific numbers, DM magnet CTA."
  },
  "9. CAROUSEL 3": {
    "topic": "Carousel #3 Playbook",
    "hook_style": "Myth Buster",
    "slide_1_hook": "Hook text (6-8 words max)",
    "prompt_details": "Details for slides 2-6 and slide 7 CTA."
  },
  "10. INFOGRAPHIC 3": {
    "topic": "Infographic #3 Time Saved / CPL Data",
    "prompt_details": "Details of specific metrics and chart breakdown."
  },
  "11. TEXT 3": {
    "topic": "Contrarian Hot Take",
    "archetype": "Hot Take",
    "prompt_details": "Contrarian opinion on direct-response scripting/scaling, DM magnet CTA."
  }
}
```

### 4.5 Planning user prompt — VERBATIM

`generate_all_content.py:253-265`.

```
Already Used Topics (DO NOT REPEAT):
{json.dumps(used_topics, indent=2)}

Harsh's Raw Notes / Recent Client Wins (PRIORITIZE THESE IF PRESENT):
{raw_notes if raw_notes else "None provided for this run."}

Fresh Reddit Posts:
{json.dumps(reddit_posts[:20], indent=2)}

Fresh AI & Marketing News:
{json.dumps(ai_news[:15], indent=2)}
```

### 4.6 The four per-post user prompt templates — VERBATIM

`generate_all_content.py:301-336`. Selection is by substring match on the plan key (`"POLL" in post_id`, `"CAROUSEL" in post_id`, `"INFOGRAPHIC" in post_id`, else the text branch).

**POLL** (line 305):

```
Write a POLL post.
Topic: {topic}
Details: {details}
Question: {question}
Options:
{opt_str}
Provide the Setup, the Question, the 4 Options, and an Explanation prompt. Do not include any title.
```

`opt_str` is built at line 304 as `"\n".join([f"☐ {opt}" for opt in options])` — the `☐` prefix is what the scheduler's poll parser later keys on.

**CAROUSEL** (line 316):

```
Write a CAROUSEL post content.
Topic: {topic}
Chosen Hook Style: {hook_style}
Slide 1 Hook: "{slide_1_hook}"
Details: {details}
Format clearly labeled with Slide 1, Slide 2, etc. and CAROUSEL CAPTION:
```

**INFOGRAPHIC** (line 324):

```
Write an INFOGRAPHIC caption.
Topic: {topic}
Details: {details}
Provide the hook, key insights, and a clear description of the data. Do not include titles. Format clearly labeled with INFOGRAPHIC CAPTION:
```

**TEXT / default** (line 331):

```
Write a LinkedIn post.
Topic: {topic}
Archetype: {archetype}
Details: {details}
Start directly with the hook. No titles. Do not include headers.
```

### 4.7 Performance-post system prompt and the 5 hard-coded prompts — VERBATIM

System prompt (`generate_all_content.py:523-525`):

```
You are Harsh Chouksey's Performance Engine. Write 5 report-driven posts reverse-engineered from actual analytics.
{writing_rules}
```

The five user prompts (`generate_all_content.py:527-575`) are **fully hard-coded — the topics are literal strings in the source and are identical on every single run.** They ignore `used_topics.json`, Reddit, news and `raw_notes.txt` entirely.

```
Write the FOUNDER PSYCHOLOGY CONTRARIAN performance post.
Topic: Stop testing 50 ad creatives when your landing page conversion rate is under 1.5%. Explain that most brand owners burn money on Meta Ads trying to fix their messaging, when the real culprit is a friction-filled signup funnel. Fix your landing page first.
Start directly with the hook. No titles.
```

```
Write the LOADED POLL performance post.
Topic: "What is the best way to scale Meta ad accounts in 2026?"
Question: What is the most reliable bidding strategy to scale Meta Ads budget without spikes in lead cost?
Options:
☐ Advantage+ Shopping Campaigns (ASC)
☐ ABO campaigns with strict cost caps
☐ CBO campaigns with broad targeting
☐ Manual bidding on granular segments
Provide Setup, Question, Options, and Explanation. No titles.
```

```
Write the AI NEWS + IMPLICATIONS performance post.
Topic: Meta's updated Conversions API (CAPI) feedback loops.
Implication: D2C brands are learning that browser-based pixel tracking is no longer sufficient. Server-side event sync is now the baseline. If your CRM isn't pushing purchase data back to Meta within 1 hour, you're overpaying for clicks.
Start directly with the hook. No titles.
```

```
Write the STORY CAROUSEL performance post content.
Topic: Automating real estate leads.
Slide 1: "We cut lead costs by 45%"
Slides 2-6: Case study of how a real estate agency spent thousands on manual follow-ups, losing half their leads. We built an n8n pipeline that synced Facebook leads to WhatsApp CRM in 60 seconds, saving 20 hours/week and scaling bookings.
Slide 7: "Systems beat manual speed every time."
CAROUSEL CAPTION: [prose caption]
No titles. Format clearly labeled.
```

```
Write the DATA VISUAL + HOOK performance post.
Topic: "Leads grow cold after 5 minutes."
Caption: Explain that companies blame ad creative quality for poor conversions, but the real culprit is lead response delay. Focus on instant n8n follow-ups to save ad budget.
Start directly with the hook. No titles.
```

Output goes to `performance_posts_YYYYMMDD.txt` only. These 5 posts are **never scheduled to LinkedIn** — `schedule_all_posts.cjs` reads `linkedin_posts_today.txt`, which does not contain them. README.md:228 confirms this is known and intentional.

### 4.8 Carousel JSON generation prompt — VERBATIM

`generate_all_content.py:377-448`. System prompt is the literal string `"You are a JSON writer. Only output raw JSON."`.

```
You are Harsh Chouksey's AI visual content designer.
Based on the generated Carousel post below, generate the structured JSON configuration for the Carousel slides.

Post Content:
{generated_posts.get(key, "")}

Format your output as a single valid JSON object. Do NOT wrap it in any markdown code block, and do NOT include any other text before or after the JSON.
Your JSON must strictly follow this structure:
{
  "1": {
    "HEADER_LABEL": "WORKFLOW AUTOMATION",
    "HOOK_PART_1": "0 to ₹10L/mo",
    "HOOK_PART_2": "lead nurture scaling",
    "HOOK_EMPHASIS": "LEAD NURTURE",
    "SUBTITLE": "How a startup replaced manual spreadsheets with n8n pipelines."
  },
  "2": {
    "PILL_LABEL": "THE PROBLEM",
    "EYEBROW": "MANUAL BOARDS",
    "HEADLINE_PART_1": "Leads rot on CRM",
    "HEADLINE_PART_2": "spreadsheets for days",
    "HEADLINE_EMPHASIS": "CRM",
    "SUBHEAD": "The longer a lead sits, the colder it gets.",
    "BODY_TEXT": "Hiring manual SDRs burns ad budget."
  },
  "3": {
    "HEADER_LABEL": "THE SOLUTION",
    "HUGE_STAT": "2 Min",
    "CIRCLE_WORD_1": "AUTO",
    "CIRCLE_WORD_2": "REPLY",
    "HEADLINE_PART_1": "Connect Meta leads",
    "HEADLINE_PART_2": "directly to n8n pipelines",
    "HEADLINE_EMPHASIS": "N8N",
    "BODY_TEXT": "Trigger automated WhatsApp messages instantly."
  },
  "4": {
    "PILL_LABEL": "LEAD SCORING",
    "EYEBROW": "AI FILTER",
    "HEADLINE_PART_1": "Score leads before",
    "HEADLINE_PART_2": "routing to sales",
    "HEADLINE_EMPHASIS": "SCORE",
    "SUBHEAD": "Identify the high-intent buyers.",
    "BODY_TEXT": "AI nodes qualify leads automatically."
  },
  "5": {
    "HEADER_LABEL": "WhatsApp CRM",
    "HUGE_STAT": "60%",
    "CIRCLE_WORD_1": "LOWER",
    "CIRCLE_WORD_2": "CPL",
    "HEADLINE_PART_1": "Auto-nurture leads with",
    "HEADLINE_PART_2": "WhatsApp conversation flows",
    "HEADLINE_EMPHASIS": "WHATSAPP",
    "BODY_TEXT": "Personalized chat funnels build trust."
  },
  "6": {
    "HEADER_LABEL": "THE RESULTS",
    "HUGE_STAT": "30 Hrs",
    "HEADLINE_PART_1": "Save time and scale",
    "HEADLINE_PART_2": "ad campaign budgets",
    "HEADLINE_EMPHASIS": "SCALE",
    "SUBHEAD": "Systematic scaling beats manual operations.",
    "BODY_TEXT": "Automated data feedback optimizes ads."
  },
  "7": {
    "HEADLINE_PART_1": "Scale traffic and",
    "HEADLINE_PART_2": "automate lead systems",
    "HEADLINE_EMPHASIS": "SCALE",
    "SUBHEAD": "Follow @harshchouksey or DM 'SCALE' to build an automated growth engine."
  }
}
```

### 4.9 Infographic JSON generation prompt — VERBATIM

`generate_all_content.py:474-499`. Same `"You are a JSON writer. Only output raw JSON."` system prompt.

```
You are Harsh Chouksey's AI visual content designer.
Based on the generated Infographic post below, generate the structured JSON configuration for the Infographic.

Post Content:
{generated_posts.get(key, "")}

Format your output as a single valid JSON object. Do NOT wrap it in any markdown code block, and do NOT include any other text before or after the JSON.
Your JSON must strictly follow this structure:
{
  "title_main": "Lead Response Time Vs",
  "title_span": "Booking Rates",
  "subtitle": "How instant automated follow-ups affect sales booking conversions.",
  "badge": "📊 PIPELINE CONVERSIONS",
  "date_label": "2025 Lead Gen Report",
  "takeaway_num": "5 Mins",
  "takeaway_text": "is the critical threshold. Contacting leads within 5 minutes yields a 391% higher booking rate.",
  "source": "Source: Industry Benchmark | @harshchouksey",
  "bars": [
    { "label": "Under 5 Minutes (Auto-WhatsApp) - 95%", "value": "95%", "color": "#E63946" },
    { "label": "5 to 10 Minutes - 55%", "value": "55%", "color": "#D9785B" },
    { "label": "10 to 30 Minutes - 25%", "value": "25%", "color": "#E8A33D" },
    { "label": "Over 30 Minutes - 10%", "value": "10%", "color": "#5E6AD2" }
  ]
}
```

### 4.10 Hook generation

**There is no separate hook-generation step and no separate hook LLM call.** Hooks are produced two ways, both one-shot:

1. **Carousel hooks** — the *planner* invents `slide_1_hook` ("6-8 words max") and `hook_style` in the same call that picks topics. Critically, `hook_style` is **pre-assigned per slot inside the planning prompt itself**: carousel 1 is always instructed toward `"Curiosity Gap"`, carousel 2 always `"Specific Result"`, carousel 3 always `"Myth Buster"` (§4.4). There is no rotation and no history check in the active path. The hook is then passed into the carousel writing prompt as `Slide 1 Hook: "{slide_1_hook}"`.
2. **Text/poll/infographic hooks** — no separate field at all. The writing rules say "Pain Hook (1-2 lines)" as structure item 6, and each prompt ends "Start directly with the hook." The hook is whatever the model's first line turns out to be.

The rich hook-rotation machinery exists but is **not connected to the running pipeline**: `commands/linkedin-content.md:119-136` defines 10 carousel hook styles and a ban rule ("style used in the last run is banned; any style appearing 3+ times in the last 7 entries is banned"), read from `carousel-hook-log.json`. That file **does not exist** and `generate_all_content.py` never opens it. `update_logs_today.py` would write it but is not called by `run_pipeline.py`, and when it does write, it hard-codes `"hook_style": "Story"` and `"carousel_format": "STORY"` regardless of what was actually used.

The 10 defined styles, for reference (`commands/linkedin-content.md:126-136`): Bold Claim, Specific Result, Mistake Call-Out, Myth Buster, Curiosity Gap, Number Reveal, Before-After, Checklist Promise, Framework Authority, Relatable Pain.

### 4.11 Post-type templates

Four types exist in the active pipeline. **Video is not supported anywhere in the codebase.**

| Type | Count/run | Prompt template | Asset | Scheduler branch |
|---|---|---|---|---|
| **Carousel** | 3 | §4.6 CAROUSEL | multi-page PDF | `schedule_all_posts.cjs:786` — "Add a document" |
| **Infographic** (single image) | 3 | §4.6 INFOGRAPHIC | 1080×1080 PNG | `schedule_all_posts.cjs:914` — "Add media" |
| **Poll** | 2 | §4.6 POLL | native LinkedIn poll | `schedule_all_posts.cjs:641` — "Create a poll" |
| **Text** ("regular") | 3 | §4.6 TEXT | none | falls through, caption only |
| **Video** | — | none | — | none |

The type is decided in the scheduler by substring matching the header line (`schedule_all_posts.cjs:186-188`):

```javascript
const type = header.toLowerCase().includes('carousel') ? 'carousel' :
             header.toLowerCase().includes('infographic') ? 'infographic' :
             header.toLowerCase().includes('poll') ? 'poll' : 'regular';
```

Anything unrecognised silently becomes a plain text post.

### 4.12 Length, tone and brand-voice control

**Length control:** essentially none. `max_tokens=4000` is the only ceiling, and it is a hard truncation, not a target. The writing rules ask for "Short punchy lines (under 12 words)"; the AI-news skill specifies "Posts 1-6 (150-300 words), Post 7 (under 120 words)" but that skill is not part of the scripted path. **No code measures or enforces any character or word count on generated posts.** The only length enforcement anywhere is in the scheduler, truncating poll fields to fit LinkedIn's UI (`schedule_all_posts.cjs:212-214` question → 140 chars; `:220-222` options → 30 chars).

**Tone / brand voice:** three files govern voice, but only one is actually loaded at runtime.

- `voice-profile.md` — **quoted in full in §1.5 above; reproduced verbatim here as the brand-voice file:**

```markdown
# Voice Profile: Harsh Chouksey

This profile defines the writing voice, tone, vocabulary rules, and style constraints for all LinkedIn content generated by the pipeline.

## 1. Writing Persona & Tone
*   **Persona**: An experienced growth consultant who sits at the intersection of performance marketing (Meta Ads) and operations (n8n automation). He is not a theoretician or general news aggregator; he is a practitioner who builds real systems.
*   **Tone**: Authority-driven, declarative, specific, and direct. Excitement is earned, not manufactured.
*   **Tone Targets**:
    *   *Blunt but helpful*: Challenges romanticized marketing/automation ideas with real numbers.
    *   *Analytical*: Prefers breakdown numbers, time savings, and CPL/ROAS metrics over vague adjectives.
    *   *Relatable & Human*: Writes like a senior builder talking to a peer over coffee. Uses casual transitions and contractions (don't, it's, you'll).

---

## 2. Style & Formatting Rules
*   **Declarative Hooks**: Hooks must be 1-2 lines, under 120 characters, and make the reader stop scrolling by pointing to a specific problem or metric.
*   **Sentence Case Headings**: Heading labels or slide text should always use sentence case (e.g. "Three setup errors costing you leads" instead of "Three Setup Errors Costing You Leads").
*   **No em-dashes**: Banned globally. Use commas, periods, or semicolons instead.
*   **Flowing Prose over Bullets**: Use bullets only when describing sequential workflow steps (like n8n node logic). Otherwise, keep ideas flowing in paragraphs.
*   **Direct Openings**: Never start with generic titles, headlines, or greetings ("Hey guys", "Headline: ..."). Start directly with the hook.
*   **CTAs (Call to Actions)**:
    *   Standard text posts: "Follow @harshchouksey for daily breakdowns on Meta Ads and automation."
    *   Consulting / Lead-gen posts: "DM me 'SCALE' and let's build an automated growth engine for your business."
    *   Engagement post variants: "Repost to help a founder scaling their ads."

---

## 3. Banned Vocabulary
Avoid standard AI-writing filler words and corporate jargon.
*   *Filler Words*: delve, underscore, vibrant, tapestry, interplay, intricate, garner, pivotal, showcase, foster, landscape (abstractly), key (as adjective), leverages, encompasses, facilitates, utilized.
*   *Hype Jargon*: game-changer, supercharge, revolutionary, groundbreaking, unprecedented, cutting-edge, state-of-the-art, next-generation, synergy, paradigm shift, thought leader, go viral.
*   *Hustle Cliches*: grind, crush it, hustle.
*   *LinkedIn Patterns*:
    *   "No X. No Y. Just Z."
    *   "It's not just about X. It's about Y."
    *   "If you're serious about X, [do this]"
    *   "And here's the kicker"
    *   "X changed everything"
    *   "Enter:"
    *   "The best part? [short answer]"
    *   Email sign-off language ("To your success").
```

- `content-doctrine.md` — **reproduced verbatim:**

```markdown
# Content Doctrine: Harsh Chouksey's LinkedIn

This is the north star content doctrine that governs every post, carousel, infographic, and news item in the LinkedIn posting pipeline. All content must pass through this doctrine before being generated or scheduled.

## 1. Core Positioning
*   **Persona**: Meta Ads Expert & AI Automation Consultant.
*   **Value Proposition**: Helping D2C brands, startups, agencies, and coaches scale their traffic and automate their operations to reduce cost per lead, improve ROAS, and eliminate manual work.
*   **The Intersection**: Meta Ads & Paid Traffic + Workflow Automation (n8n, CRM, WhatsApp).

---

## 2. Target Audience
*   **D2C & E-commerce Brands**: Scaling past ₹10L/month looking for better ROAS and conversion funnels.
*   **B2B / Service Businesses**: Agencies, coaches, real estate, and finance companies needing consistent, qualified leads without manual follow-up.
*   **Ambitious Business Owners / Solopreneurs**: Looking to save 20-30 hours per week of business operations through AI agents and intelligent workflows.

---

## 3. Topic Filters (The 4-Part Filter)
Every post topic must meet all four criteria:
1.  **Reach**: Relevant to e-commerce, lead generation, or business operations.
2.  **Stakes**: Connected to sales, lead costs (CPL), revenue growth, or time savings.
3.  **Altitude**: Focuses on strategic design, systems thinking, and automation architecture (e.g. "building a growth engine" rather than raw Python code syntax).
4.  **Edge**: Grounded in real results, workflow diagrams (like n8n), or actual Meta Ads strategies.

---

## 4. DROP List (Strictly Banned Content)
*   **NO General AI news relay**: Cut dry reports on general tech company acquisitions, VC funding announcements (unless they directly affect marketing spend), or new general AI model releases with no direct marketing or automation utility.
*   **NO Developer-Only coding**: Avoid raw code snippets, terminal command syntax, model weights, or CUDA configurations. Keep it to n8n node structures and workflow logic.
*   **NO Generic Startup Advice**: Drop generic equity tips, VC pitch advice, or general motivational hustle posts.
*   **NO Plain relay of features**: Do not just list tool features. Reframe every tool around its marketing benefit or operational time savings.

---

## 5. AMPLIFY List (Highly Encouraged Content)
*   **n8n Workflow Layouts**: Screenshots or descriptions of actual workflows (e.g., WhatsApp + CRM integrations).
*   **Meta Ads strategies**: Budgeting hacks, targeting changes, ad creative A/B testing, and landing page optimization.
*   **Real ROI & Metrics**: Use hard numbers: "reduced cost per lead by 60%", "improved ROAS from 2x to 4.5x", "saved 22 hours/week".
*   **Lead-to-Sale Automations**: CRM syncing, lead auditing, conversational WhatsApp pipelines.
*   **AI Agents for Ops**: Using AI agents to automate customer follow-up, qualify leads, or generate ad creatives.
```

**Important mechanical detail:** neither of these two files is ever read by `generate_all_content.py`. The script's comment at line 89 says *"Shared writing instructions based on content-doctrine.md and voice-profile.md"* — the rules were **transcribed by hand into the source** as the `writing_rules` string. Editing `content-doctrine.md` or `voice-profile.md` therefore has **zero effect on the scripted pipeline**. They only take effect on the agent-driven SKILL.md path, which `cat`s them.

### 4.13 Quality gates, scoring and retries

**In the active scripted pipeline: none.** There is no banned-word check, no em-dash check, no length check, no doctrine check, no duplicate check, no scoring, and no regeneration-on-failure. Whatever `gpt-4o` returns for a post is written to disk verbatim and later typed into LinkedIn verbatim. The only retry is transport-level (5 attempts, 429-only backoff) in `call_llm`, and the only rejection path is `sys.exit(1)` when a call returns nothing at all.

Two JSON-shaped calls have soft parse handling: carousel/infographic JSON is stripped of markdown fences (lines 451-458, 502-509) and `json.loads`d inside a `try`; on failure it prints `Error parsing Carousel JSON #N` and **continues**, leaving the previous run's `carousel_data_N.json` in place. This is a silent-stale-asset path (see §12).

Quality gates that exist only in the unused agent path: `skills/linkedin-ai-news-engine/SKILL.md` PHASE 2C 15-point scoring rubric (Recency 3 / Wow factor 3 / Accessibility 3 / Specificity 3 / Audience relevance 3) and PHASE 4 self-check list; `skills/linkedin-performance-engine/SKILL.md` PHASE 3 self-check; `daily-linkedin-posts/SKILL.md` Step 3A zero-overlap check.

The only *validation* in the whole run is in the scheduler, and it validates the browser DOM rather than content quality — poll options non-blank (`schedule_all_posts.cjs:766-768`), document title non-blank (`:859-861`), caption length ≥ 5 chars (`:1011-1013`). Each throws and aborts the entire scheduling run.

---

## 5. IMAGE & CAROUSEL GENERATION

### 5.1 How images are produced

**In the active pipeline, no image model is called.** Both visual types are **template renderers**: HTML files filled with LLM-written JSON copy, screenshotted by headless Chrome via Puppeteer.

| Visual | Renderer | Template source | Output |
|---|---|---|---|
| Carousel (7 slides) | `build_carousel_today.cjs` → `generate_carousel_today.py` | HTML templates extracted from `skills/branded-carousel/SKILL.md` | 7 PNGs + 1 PDF per carousel, ×3 |
| Infographic | `cap_infographic_today.js` | `linkedin-infographic-template.html` | 1080×1080 PNG, ×3 |

Both launch Puppeteer with `headless: 'shell'`. Carousel: viewport 1080×1080 at `deviceScaleFactor: 2` (`build_carousel_today.cjs:26`). Infographic: 1080×1080 at `deviceScaleFactor: 1` (`cap_infographic_today.js:21`), served over a throwaway `http.createServer` on port `8760 + idx` so webfonts load.

**Image-model code exists but is not wired in:**

- `aigen_image.py` — Google Gemini image generation, default model `gemini-3-pro-image` with fallback to `gemini-2.5-flash-image`. Requires `GEMINI_API_KEY`, **which is not in `.env`**, so it cannot run today. Not referenced by any active script.
- `fetch_carousel_image.py` — image sourcing helper, not wired in.

### 5.2 Image prompt templates — VERBATIM

There are exactly three image-prompt artefacts in the repo.

**(a) `aigen_image.py:12-15` — the brand suffix appended to every prompt** (dormant; `GEMINI_API_KEY` absent):

```python
BRAND = (" Premium editorial illustration for a LinkedIn carousel. Warm cream background (#F8F7F3). "
         "One muted indigo-purple accent (#5E6AD2). Flat modern vector style, clean geometric shapes, "
         "generous negative space, sophisticated magazine aesthetic. Portrait 4:5 composition. "
         "No text, no words, no letters, no logos, no watermark.")
```

The caller passes a free-text prompt as `sys.argv[1]`; the final prompt is `prompt + BRAND`. `generationConfig` is `{"responseModalities": ["TEXT", "IMAGE"]}`. There is no stored library of prompts to feed it — the prompt is whatever the operator types on the command line.

**(b) `skills/branded-carousel/SKILL.md:161-167` — TIER 3 AI-generated product mockup** (agent path, last-resort only):

```
Prompt: "Professional UI screenshot of [PRODUCT_NAME] by [COMPANY_NAME].
[Describe the exact interface based on PAGE_CONTENT — terminal, design canvas, chat interface, etc.]
Dark background [BRAND_BG]. [BRAND_PRIMARY] accent colors.
Real interface elements — not decorative. 1080x1080. No company logos or text."
```

Guarded by `SKILL.md:159`: *"⚠️ Only use this if Tiers 1 and 2 have both genuinely failed. Log the failure clearly in the Phase 6 report."*

**(c) `generate_carousel_today.py:13-16` — hard-coded Unsplash fallback URLs** (this is the one that actually executes):

```python
fallbacks = {
    "hero-ui.png": "https://images.unsplash.com/photo-1460925895917-afdab827c52f?auto=format&fit=crop&w=1080&q=80",
    "interface.png": "https://images.unsplash.com/photo-1551288049-bebda4e38f71?auto=format&fit=crop&w=1080&q=80"
}
```

`ensure_valid_images()` (line 8) downloads these into `./carousel-routine/temp/carousel-branded/assets` if missing or under 10,000 bytes, checking the first 100 bytes for `<html`/`<!doctype` to detect error pages. **These are two fixed stock photos, identical on every run, for every topic.**

**However — these images are then discarded.** `generate_carousel_today.py:66-76` regex-replaces the `<img class="s1-image">` and `<img class="s6-image">` elements in templates 1 and 6 with inline CSS gradient cards, and templates 2/3/5/7 have no image slot filled with real assets. The replacement cards contain **hard-coded copy unrelated to the day's topic**:

```html
<!-- slide 1 replacement, generate_carousel_today.py:68 -->
<div style="...">⚡ 2026 AI BLUEPRINT</div>
<div style="...">Autonomous AI Ops</div>

<!-- slide 6 replacement, generate_carousel_today.py:74 -->
<div style="...">KEY TAKEAWAY</div>
<div style="...">NATIVE AI OPERATING SYSTEM</div>
<div style="...">Connect tools once · Automate 24/7</div>
```

So the shipped carousels contain the literal strings "2026 AI BLUEPRINT", "Autonomous AI Ops" and "NATIVE AI OPERATING SYSTEM" on slides 1 and 6 of **every carousel, every day**, regardless of topic. The Unsplash download still runs each time and its output is unused.

This directly contradicts `skills/branded-carousel/SKILL.md:51` (*"REAL ASSETS ARE NON-NEGOTIABLE… Every slide that can show a real screenshot must show one"*), `:214` (*"HARD RULE: If hero-ui.png is missing or invalid (<10KB), do NOT proceed to Phase 3"*), and `FORMATS.md` (*"Real image present on minimum 4 of 7 slides"*). The three-tier image sourcing strategy in SKILL.md Phase 1 (Tier 1 Playwright `capture_source.js` → Tier 2 curl of `og:image`/`twitter:image` → Tier 3 AI generation) belongs to the agent path and never executes in the scripted path.

### 5.3 How carousels are built

**Fixed at 7 slides.** The count is hard-coded in three independent places, all of which must agree:

- `build_carousel_today.cjs:39` — `for (let i = 1; i <= 7; i++)` screenshot loop
- `build_carousel_today.cjs:48` — `for (let i = 1; i <= 7; i++)` PDF assembly loop
- `generate_carousel_today.py:104-176` — the `data` dict has exactly keys `"1"`–`"7"`

**Three carousels per run**, `build_carousel_today.cjs:28` — `for (let idx = 1; idx <= 3; idx++)`, with `if (!fs.existsSync(jsonFile) && idx > 1) continue;` so carousels 2 and 3 are skipped if their JSON is missing but carousel 1 is attempted regardless.

**Layout / template files.** Templates are extracted at runtime by regex from `skills/branded-carousel/SKILL.md` (`generate_carousel_today.py:54-63`):

```python
skill_path = "./skills/branded-carousel/SKILL.md"
with open(skill_path, "r") as f:
    content = f.read()

t1 = re.search(r"TEMPLATE 1.*?```html(.*?)```", content, re.DOTALL).group(1)
t2 = re.search(r"TEMPLATE 2 & 4.*?```html(.*?)```", content, re.DOTALL).group(1)
t3 = re.search(r"TEMPLATE 3 & 5.*?```html(.*?)```", content, re.DOTALL).group(1)
t6 = re.search(r"TEMPLATE 6.*?```html(.*?)```", content, re.DOTALL).group(1)
t7 = re.search(r"TEMPLATE 7.*?```html(.*?)```", content, re.DOTALL).group(1)
```

Five templates cover seven slides:

| Slide | Template | Layout (per `skills/branded-carousel/SKILL.md`) |
|---|---|---|
| 1 | TEMPLATE 1 | Top header, huge central stat + headline, bottom-left square image (replaced by gradient card) |
| 2 | TEMPLATE 2 & 4 | Large faded image top half; eyebrow + headline + subhead bottom half |
| 3 | TEMPLATE 3 & 5 | No image. Huge number left, thick brand-coloured circle with context text right |
| 4 | TEMPLATE 2 & 4 | (reuse of slide-2 layout) |
| 5 | TEMPLATE 3 & 5 | (reuse of slide-3 layout) |
| 6 | TEMPLATE 6 | 420px image card (replaced by white bordered takeaway card) |
| 7 | TEMPLATE 7 | No image. Large centred text, divider line, black pill button |

**These regexes are a hard dependency: renaming a heading in `skills/branded-carousel/SKILL.md` from "TEMPLATE 2 & 4" to anything else makes `re.search(...).group(1)` raise `AttributeError` on `None` and kills the build step.**

**Brand colour is hard-coded**, overriding all the palette options documented in `FORMATS.md` (`generate_carousel_today.py:82-83`):

```python
# Linear Purple Color
color = "#5E6AD2"
```

**Copy substitution.** `get_slide_val(slide_num, key, fallback)` (line 95) pulls each `{{PLACEHOLDER}}` from `carousel_data_{idx}.json`, falling back to a hard-coded default string if the key is missing, `None` or empty. Those defaults are a complete, unrelated SaaS onboarding story ("5x MRR in seven days", "A founder was stuck at $60 MRR for months…"). **If the carousel JSON fails to parse or a key is missing, the slide silently renders that stale onboarding narrative instead of today's topic.**

**Build sequence** (`build_carousel_today.cjs`):

1. `execSync('python3 generate_carousel_today.py <json> <tempdir>')` → 7 HTML files in `carousel-routine/temp/carousel-branded-{idx}/slide-0{1..7}.html`
2. Navigate `file://` to each slide, `page.screenshot()` → `output/{YYYY-MM-DD}/carousel-branded/carousel-{idx}/slide-0{i}.png`
3. Build `carousel.html`: seven `<img>` tags at 1080×1080 with `page-break-after: always`
4. `page.pdf({ width: 1080, height: 1080, printBackground: true })` → `output/{YYYY-MM-DD}/carousel-branded/linkedin-carousel-{idx}.pdf`
5. Copy to `slack_downloads/carousel-{idx}.pdf`; for idx 1 also `slack_downloads/carousel-{YYYYMMDD}.pdf`

Note step 4 builds the PDF **from the rendered PNGs**, satisfying the rule in `daily-linkedin-posts/SKILL.md:191` and `branded-carousel/SKILL.md:835` that the PDF must never be re-rendered from HTML.

### 5.4 How infographics are built

`cap_infographic_today.js` loads `linkedin-infographic-template.html` once, then for `idx` 1..3 reads `infographic_data_{idx}.json` and does nine `String.replace()` substitutions (lines 48-57): `{{BADGE}}`, `{{DATE_LABEL}}`, `{{TITLE_MAIN}}`, `{{TITLE_SPAN}}`, `{{SUBTITLE}}`, `{{BAR_ROWS}}`, `{{TAKEAWAY_NUM}}`, `{{TAKEAWAY_TEXT}}`, `{{SOURCE}}`.

`{{BAR_ROWS}}` is generated from the `bars` array (lines 36-46) — one `.bar-row` per entry, where **the CSS bar width is the `value` string used literally**:

```javascript
<div class="bar-fill" style="width: ${bar.value}; background-color: ${bar.color || '#5E6AD2'};"></div>
```

So `value` must be a valid CSS length (e.g. `"95%"`). A model returning `95` or `"95 percent"` produces a zero-width or broken bar with no error.

Only **RANKED_BARS** is implemented. The other four formats documented in `skills/illustration-formats/SKILL.md` (DONUT_BREAKDOWN, TIMELINE_SHIFT, COMPARISON_SPLIT, HERO_NUMBER) and its selection decision tree have **no renderer** — the template is a fixed horizontal bar chart, and `update_logs_today.py:60` hard-codes `"format": "RANKED_BARS"` when logging.

The template's own palette (`linkedin-infographic-template.html`): background `#F8F7F3`, badge `#5E6AD2`, `Plus Jakarta Sans` + `Instrument Serif` loaded from Google Fonts via `@import`. Bar colours come from the JSON, defaulting to `#5E6AD2`. Note this differs from the `#F5EFE8` / `#E63946` palette specified in `skills/illustration-formats/SKILL.md:43-49` and in `commands/linkedin-content.md:210`.

**Network dependency:** the template `@import`s Google Fonts. `cap_infographic_today.js:71` awaits `document.fonts.ready` before screenshotting, so an offline or blocked run silently renders in a fallback system font rather than failing.

### 5.5 Where generated assets are stored

| Asset | Path | Overwritten each run? |
|---|---|---|
| Slide HTML (intermediate) | `carousel-routine/temp/carousel-branded-{1,2,3}/slide-0{1..7}.html` | Yes |
| Slide PNGs | `carousel-routine/output/{YYYY-MM-DD}/carousel-branded/carousel-{idx}/slide-0{i}.png` | No — date-partitioned |
| Carousel PDFs | `carousel-routine/output/{YYYY-MM-DD}/carousel-branded/linkedin-carousel-{idx}.pdf` | No — date-partitioned |
| Carousel PDFs (scheduler + Slack copy) | `slack_downloads/carousel-{idx}.pdf` and `slack_downloads/carousel-{YYYYMMDD}.pdf` | **`carousel-{idx}.pdf` yes — overwritten every run** |
| Infographic HTML | `linkedin-infographic-{1,2,3}.html` (project root) | Yes |
| Infographic PNGs | `linkedin-infographic-{1,2,3}.png` (project root) | **Yes — overwritten every run** |
| Infographic dated copy (#1 only) | `linkedin-infographic-{YYYYMMDD}.png` | No |
| Run screenshots | `slack_downloads/post_{id}_{type}_{stage}.png` | Yes, per post id |
| Crash screenshot | `error_screenshot.png` (project root) | Yes |
| Downloaded stock images | `carousel-routine/temp/carousel-branded/assets/{hero-ui,interface}.png` | Only if invalid/missing |

Date partitioning uses timezone-corrected local date (`build_carousel_today.cjs:7-11`, `cap_infographic_today.js:23-26`): `new Date(today.getTime() - offset*60*1000).toISOString().slice(0,10)`.

**The three current-run infographic PNGs and the `carousel-{idx}.pdf` copies are the files the scheduler uploads, and they are destroyed by the next run.** Only carousel #1's PDF and infographic #1's PNG get dated archive copies; carousels/infographics 2 and 3 exist as dated files only inside `carousel-routine/output/{date}/`, and the infographic 2/3 PNGs have no dated copy anywhere.

---

## 6. SCHEDULING & PUBLISHING

### 6.1 How the schedule window is computed

All logic is in `parseTodayPosts()`, `schedule_all_posts.cjs:278-338`. It is **not** a "3 days ahead of today" calculation — it is a **continuous chain from the last scheduled date**, with three precedence levels:

```javascript
let startDateObj;
const stateFile = path.join(__dirname, 'pipeline_state.json');
if (process.env.START_DATE_OFFSET !== undefined) {
  const offset = parseInt(process.env.START_DATE_OFFSET, 10);
  startDateObj = new Date();
  startDateObj.setDate(startDateObj.getDate() + offset);
} else if (fs.existsSync(stateFile)) {
  try {
    const stateData = JSON.parse(fs.readFileSync(stateFile, 'utf8'));
    if (stateData.last_scheduled_date) {
      const parts = stateData.last_scheduled_date.split('-');
      if (parts.length === 3) {
        const lastDate = new Date(parseInt(parts[0], 10), parseInt(parts[1], 10) - 1, parseInt(parts[2], 10));
        startDateObj = new Date(lastDate);
        startDateObj.setDate(startDateObj.getDate() + 1);
      }
    }
  } catch (e) {
    console.error("Error reading pipeline_state.json:", e);
  }
}

if (!startDateObj) {
  startDateObj = new Date();
}

const day1 = new Date(startDateObj);
const day2 = new Date(startDateObj); day2.setDate(day2.getDate() + 1);
const day3 = new Date(startDateObj); day3.setDate(day3.getDate() + 2);
```

Precedence: **`START_DATE_OFFSET` env var** (days from today, overrides everything) → **`pipeline_state.json.last_scheduled_date + 1 day`** → **today**.

Dates are formatted `MM/DD/YYYY` (`schedule_all_posts.cjs:308-313`) to match LinkedIn's US-locale date input.

**Worked example from current state.** `pipeline_state.json` holds `"last_scheduled_date": "2026-08-07"`, written on 2026-08-04. The next run therefore starts at **2026-08-08** and covers 08-08, 08-09, 08-10 — three days beginning four days after the last run's execution date. The "3-day-ahead" behaviour is emergent from running roughly every three days, not enforced by code.

**There is no guard against the past.** No code compares `startDateObj` to today. If `pipeline_state.json` is deleted, renamed, emptied, or has a malformed `last_scheduled_date`, `startDateObj` silently falls back to **today** — and the 9:00 AM / 12:00 PM slots will already be in the past for any run started after 9am, which LinkedIn will reject mid-run. See §7.5 and §12.

### 6.2 Posts per day, times, and where they are configured

`schedule_all_posts.cjs:319-331` — a literal array, positionally mapped to the 11 parsed posts:

```javascript
const schedule = [
  { date: date1, time: '9:00 AM' },
  { date: date1, time: '12:00 PM' },
  { date: date1, time: '3:00 PM' },
  { date: date1, time: '6:00 PM' },
  { date: date2, time: '9:00 AM' },
  { date: date2, time: '12:00 PM' },
  { date: date2, time: '3:00 PM' },
  { date: date2, time: '6:00 PM' },
  { date: date3, time: '9:00 AM' },
  { date: date3, time: '12:00 PM' },
  { date: date3, time: '3:00 PM' }
];

posts.forEach((p, idx) => {
  if (schedule[idx]) {
    p.date = schedule[idx].date;
    p.time = schedule[idx].time;
  }
});
```

- **Posts per day:** 4, 4, 3 (11 total).
- **Times:** 9:00 AM, 12:00 PM, 3:00 PM, 6:00 PM. Day 3 has no 6:00 PM slot.
- **Where configured:** hard-coded in this array only. There is **no config file, no env var, no CLI flag** for posting times or posts-per-day.
- **Timezone:** none is set anywhere. Times are typed as literal strings into LinkedIn's UI, so they are interpreted in **the timezone of the logged-in LinkedIn account**, not the machine's. README calls them IST. The code has no timezone awareness at all.
- **Silent truncation:** `if (schedule[idx])` means a 12th or later post is parsed, kept in the array, and then scheduled **with `date`/`time` undefined** — it is not dropped. It would reach the schedule modal and fail there.

Note that "16 posts/day" in the README refers to *generated* posts (11 + 5 performance). The scheduler handles **11 posts spread over 3 days ≈ 3.7 posts/day**; the 5 performance posts go to Slack only.

### 6.3 How the format mix is decided

**By a fixed rotation, encoded in the planning prompt's JSON skeleton — not by a rule engine and not randomly.** The planner is required to return exactly these 11 keys in this order (`generate_all_content.py:192-250`), and `generate_all_content.py:293` iterates `content_plan.items()` in that order, writing headers in that order, which the scheduler then maps positionally onto the time slots:

| Slot | Header written | Type detected | Day | Time |
|---|---|---|---|---|
| 1 | `1. CAROUSEL 1` | carousel | 1 | 9:00 AM |
| 2 | `2. INFOGRAPHIC 1` | infographic | 1 | 12:00 PM |
| 3 | `3. POLL 1` | poll | 1 | 3:00 PM |
| 4 | `4. TEXT 1` | regular | 1 | 6:00 PM |
| 5 | `5. CAROUSEL 2` | carousel | 2 | 9:00 AM |
| 6 | `6. INFOGRAPHIC 2` | infographic | 2 | 12:00 PM |
| 7 | `7. POLL 2` | poll | 2 | 3:00 PM |
| 8 | `8. TEXT 2` | regular | 2 | 6:00 PM |
| 9 | `9. CAROUSEL 3` | carousel | 3 | 9:00 AM |
| 10 | `10. INFOGRAPHIC 3` | infographic | 3 | 12:00 PM |
| 11 | `11. TEXT 3` | regular | 3 | 3:00 PM |

Verified against the live `linkedin_posts_today.txt`, whose headers are exactly these 11 strings.

**Mix per run: 3 carousels, 3 infographics, 2 polls, 3 text. Identical every run.** The archetype assigned to each text slot is also fixed by the prompt: TEXT 1 = "Case Study", TEXT 2 = "Tool Spotlight", TEXT 3 = "Hot Take". Same for carousel hook styles (§4.10).

**The README's schedule table (README.md:214-227) is stale** — it describes Day 1 as Carousel/Infographic/Collaborative Article/Poll and Days 2-3 as seven AI-news archetypes. That reflects an older generator. The table above is what the current code produces.

Two coupling risks follow from this design: the mix is defined in a **prompt string** in the Python file, but the day/time mapping is defined by **array position** in the JS file, and the type is derived by **substring-matching the header text**. All three must stay in sync, and nothing verifies that they do.

### 6.4 How publishing actually happens

**Via LinkedIn's own native scheduler, driven through the real LinkedIn web UI.** The pipeline never calls the LinkedIn API and never posts live. It fills in LinkedIn's composer and clicks LinkedIn's "Schedule" button; LinkedIn stores and later publishes the post.

**Library:** Puppeteer (`schedule_all_posts.cjs:1` — `require('puppeteer')`, resolved via `NODE_PATH=./carousel-routine/node_modules`, version `^25.3.0`).

**Browser launch (`schedule_all_posts.cjs:551-559`):**

```javascript
browser = await puppeteer.launch({
  headless: false,
  userDataDir: path.join(__dirname, 'chrome-session'),
  defaultViewport: null,
  args: ['--start-maximized']
});
const pages = await browser.pages();
const page = pages[0] || await browser.newPage();
await page.setViewport({ width: 1280, height: 1200 });
```

Three things follow: it runs **non-headless** (a visible Chrome window opens and must not be interfered with for the ~10-minute run); authentication is the **persisted Chrome profile in `chrome-session/`**, not credentials in code; and it reuses the first existing tab rather than opening a clean one.

The one-off `post_urgent_*.cjs` scripts are the exception — they publish immediately rather than scheduling. They are not part of `run_pipeline.py`.

### 6.5 Exact selector / interaction sequence with LinkedIn's UI

Every element lookup goes through shadow-DOM-piercing helpers (`schedule_all_posts.cjs:6-111`): `getElementShadow` / `waitForSelectorShadow` walk `document.body` with a `TreeWalker`, recursing into every `shadowRoot`; `clickNativelyShadow` finds an element via a serialised finder function, scrolls it into view, tries `el.click()`, and on failure dispatches a manual `pointerdown → mousedown → focus → pointerup → mouseup → click` sequence. `clickNativelyShadowRetry` re-attempts for up to 15s.

**Per-post sequence** (loop at `schedule_all_posts.cjs:565`):

1. **Navigate** — `page.goto('https://www.linkedin.com/feed/', { waitUntil: 'domcontentloaded', timeout: 30000 })`, wrapped in try/catch so a timeout is logged and ignored. Wait 4000 ms.
2. **Hide messaging overlays** — inject a `<style>` setting `display: none !important` on `.msg-overlay-container, [class*="msg-overlay"], #msg-overlay`.
3. **Close stray composers** — find any button whose `aria-label`/text contains `Dismiss`, or `aria-label === 'close'`, or `className` contains `close-button`; click it. Wait 2000 ms.
4. **Open composer** — click the element matching: `tagName === 'BUTTON' || role="button" || aria-label="Start a post"`, **and** `innerText` contains `'Start a post'`. Throws `Could not find 'Start a post' button` on failure.
5. **Wait for editor** — `waitForSelectorShadow(page, '.ql-editor, [contenteditable="true"]', 15000)`. Wait 1000 ms.
6. **Attachment branch** (by post type):

   **Poll** (`:641`)
   - Click button with `aria-label`/text containing `More` → wait 1500 ms
   - Click button with `aria-label`/text containing `Create a poll` → wait 2000 ms
   - Fill question: `textarea.polls-detour__question-field, textarea[placeholder*="commute"], textarea[id*="question"]`, typed with `page.keyboard.type`
   - Find option inputs via `input[id*="poll-option"]` (shadow-recursive); focus + type options 1 and 2
   - For options 3 and 4: click a button whose text contains `Add option`, wait 1500 ms, re-query inputs, focus + type
   - **Validation:** re-read every `input[id*="poll-option"]` value; if any is `""`, throw `Validation Failed: Some poll option inputs are blank in React state/DOM!`
   - Screenshot `post_{id}_poll_filled.png`
   - Click the enabled, visible, non-`vjs-`-class button whose trimmed text is exactly `Done` (retry up to 15s) → wait 2000 ms

   **Carousel** (`:786`)
   - Click button matching `aria-label` contains `Add a document`, else text contains `Add a document`, else text contains `document`. If not found: click `More`, wait 1500 ms, retry the same three matchers
   - Find the first `INPUT[type=file]` by walking shadow roots; `fileInput.uploadFile(post.assetPath)` → wait 4000 ms
   - Fill title: `input.document-title-form__title-input, input[placeholder*="title to your document"]`
   - **Validation:** re-read that input; if blank, throw `Validation Failed: Document title input is blank!`
   - Screenshot `post_{id}_carousel_doc_uploaded.png`
   - **Poll for upload completion:** up to 60 × 1s iterations waiting for a visible, non-disabled `Done` button (checks `disabled`, `aria-disabled="true"`, and `className` containing `disabled`). Throw `Upload timed out or Done button was not enabled.` after 60s
   - Click `Done` → wait 3000 ms

   **Infographic** (`:914`)
   - Click button matching `aria-label` contains `Add media`, else text contains `Add media`, else text contains `Photo`, else `aria-label` contains `Photo`
   - Find `INPUT[type=file]`; `uploadFile(post.assetPath)` → wait 4000 ms
   - Screenshot `post_{id}_infographic_image_uploaded.png`
   - Click the enabled visible button whose text is exactly `Next` **or** `Done` → wait 3000 ms

   **Regular** — no attachment step.

7. **Fill caption** (`:964`) — focus `.ql-editor, [contenteditable="true"]`; clear via `document.execCommand('selectAll')` + `execCommand('delete')`; wait 1000 ms; then type **paragraph by paragraph**, pressing `Enter` between lines with 150 ms pauses (`post.caption.split('\n')`); wait 2000 ms.
8. **Validate caption** — read `.ql-editor` `innerText`; if absent or `< 5` chars, throw `Validation Failed: Post caption in editor is blank or too short!`. Screenshot `post_{id}_{type}_draft_composer.png`.
9. **Open schedule modal** (`:1019`) — this is the most fragile selector in the file. It scopes to `.share-box, .artdeco-modal, [role="dialog"]`, finds the button whose text is exactly `Post`, and clicks **`postBtn.previousElementSibling`** — i.e. the clock icon is identified purely by DOM adjacency to the Post button. Fallback: any button whose `aria-label` contains `Schedule`. Wait 3000 ms.
10. **Set date** (`:1034`) — `fillFieldShadow` on `input[placeholder*="Date"], input[aria-label*="date"], input[id*="date"]` with `MM/DD/YYYY`. The fill routine is: `focus()` + `select()` → wait 500 ms → `Backspace` → wait 500 ms → type → `Enter` → `Escape` → `Tab` → wait 1000 ms.
11. **Set time** (`:1040`) — strip a leading `0` from the time string, then `fillTimeComboboxShadow` on `input[placeholder*="Time"], input[aria-label*="time"], input[id*="time"], input[role="combobox"]`: `focus()` + `select()` → `Backspace` → type → **wait 1500 ms for the suggestion list** → `ArrowDown` → `Enter` → wait 1000 ms. Screenshot `post_{id}_{type}_schedule_settings.png`.
12. **Next** (`:1046`) — click the button whose trimmed text is exactly `Next`. Wait 3000 ms. Screenshot `post_{id}_{type}_final_draft.png`.
13. **Schedule** (`:1058`) — click the button whose trimmed text is exactly `Schedule`. Wait 6000 ms.
14. **Confirm closed** (`:1068`) — check that no `.ql-editor` remains in the DOM; if one does, press `Escape` and wait 2000 ms. Log `✓ Successfully scheduled Post {id}/{n}!`.

**After the loop:** write `pipeline_state.json` (§7.5), print a hard-coded summary that still names June 13-15 2026 dates and the obsolete post types (`:1112-1114`), then `process.exit(0)`.

**Note on the success check.** Step 14 is the only post-schedule verification, and it only asserts that the composer closed. **No code ever confirms that LinkedIn actually accepted the date/time or that the post appears in the scheduled-posts list.** A post that lands with the wrong time — or that LinkedIn silently rejected — is still logged as `✓ Successfully scheduled`.

---

## 7. STATE & MEMORY

### 7.1 Where the record of what has been posted lives

There is **no database, no sheet, and no per-post record of what was published.** State is three small files plus a browser profile. Critically:

**Nothing in this repo records that a post was published, or which posts exist on LinkedIn.** The system's entire memory of "what has already been posted" consists of (a) a single date string, and (b) a flat list of topic strings. The authoritative record of scheduled posts lives inside **LinkedIn's own scheduled-posts UI**, which this pipeline writes to and never reads back.

| Store | Path | Format | Role |
|---|---|---|---|
| **Scheduling watermark** | `pipeline_state.json` | JSON object | The only date-continuity memory |
| **Topic memory** | `used_topics.json` | JSON array of strings | The only de-duplication memory |
| **LinkedIn session** | `chrome-session/` | Chrome user-data dir | Authentication; ~50 subdirs |
| Content archive | `linkedin_posts_YYYYMMDD.txt` | Text, `====`-delimited | Human/audit record of what was generated |
| Scheduler input | `linkedin_posts_today.txt` | same | Consumed by `schedule_all_posts.cjs` |
| Fetch cache | `reddit_data.json`, `ai_news_data.json` | JSON array | Inputs to the planner |
| Asset copy | `carousel_data_{1,2,3}.json`, `infographic_data_{1,2,3}.json` | JSON object | Inputs to renderers |
| Visual proof | `slack_downloads/post_*.png` | PNG | Per-step screenshots of the last run |

### 7.2 `pipeline_state.json` — exact schema

**Current contents, verbatim (no personal data present):**

```json
{
  "last_scheduled_date": "2026-08-07",
  "last_updated": "2026-08-04T14:34:51.762Z"
}
```

| Field | Type | Meaning | Written by | Read by |
|---|---|---|---|---|
| `last_scheduled_date` | `string`, `YYYY-MM-DD` | The date of the **last (11th) post** in the batch just scheduled. The next run starts at this date **+ 1 day**. | `schedule_all_posts.cjs:1103-1106` | `schedule_all_posts.cjs:284-298` |
| `last_updated` | `string`, ISO-8601 UTC | Wall-clock time the file was written. **Informational only — no code reads it.** | `schedule_all_posts.cjs:1105` | nothing |

Written with `JSON.stringify(..., null, 2)` — a full overwrite, never a merge.

**Derivation of `last_scheduled_date` (`schedule_all_posts.cjs:1100-1102`):**

```javascript
const lastPost = posts[posts.length - 1];
const parts = lastPost.date.split('/');
const lastDateIso = `${parts[2]}-${parts[0].padStart(2, '0')}-${parts[1].padStart(2, '0')}`;
```

It converts the last post's `MM/DD/YYYY` back to `YYYY-MM-DD`. Note it uses `posts[posts.length - 1]` — **the last element of the array, not the maximum date.** If the batch ever contains more than 11 posts, the extras carry `date === undefined` and this line throws inside its try/catch, leaving the watermark unadvanced.

**This is the single most load-bearing file in the system.** Two fields, 87 bytes, and it is the only thing preventing the next run from scheduling on top of the current one.

### 7.3 `used_topics.json` — exact schema

**Shape: a flat JSON array of free-text topic strings.** No objects, no dates, no ids, no post-type, no source URL, no run grouping. Currently **76 entries**, appended across all runs since inception, never pruned.

```json
[
  "Lead leakage in service businesses / 2-minute WhatsApp n8n notifications",
  "In-house ads team vs Performance Marketing Agency for early stage",
  "n8n's new advanced AI Agent Node",
  "Meta Advantage+ Creative automation variation pros/cons",
  "AI Agents in PPC",
  "WhatsApp CRM Funnels Cheat Sheet",
  "Achieving 9.21 ROAS with Focused Meta Strategies",
  "Re-Thinking Direct-Response Scripting"
]
```

(Eight representative entries from the live file; the full 77 are in the file itself. No personal data appears in any entry.)

**Seeding.** If the file is absent, `generate_all_content.py:132-148` recreates it with **11 hard-coded seed topics** and writes it immediately. So deleting the file does not produce an empty memory — it produces a specific 11-item memory from mid-2026, silently discarding the other 66 entries.

**Read** (`generate_all_content.py:126-131`) — loaded into the planner's user prompt as `Already Used Topics (DO NOT REPEAT)`. Note the `except` on line 130 catches a parse error, prints it, and **leaves `used_topics = []`** — a corrupt file degrades silently to "no memory at all" rather than failing the run.

**Write** (`generate_all_content.py:297-299, 342-344`):

```python
# Save topic into used_topics memory
if topic and topic not in used_topics:
    used_topics.append(topic)
...
# Save the updated used_topics list
with open(used_topics_file, "w") as f:
    json.dump(used_topics, f, indent=2)
```

De-dup on append is **exact string equality only** (`topic not in used_topics`).

### 7.4 Scheduled vs published vs failed

**The system does not track these states.** There is no status field anywhere. What can be inferred, and how:

| Question | Can the system answer it? |
|---|---|
| Which posts are scheduled? | Only by opening LinkedIn's UI, or by running `get_scheduled_contents.cjs` / `verify_scheduled_posts.cjs` manually. Not stored. |
| Which posts were published? | **No.** Nothing reads LinkedIn back. |
| Which posts failed? | **No.** A crash writes `error_screenshot.png` and exits 1; nothing records which post index failed. |
| How did a post perform? | **No.** No metrics are collected anywhere in the codebase. |

The closest thing to a run ledger is the screenshot set in `slack_downloads/` — files named `post_{id}_{type}_{stage}.png`. Because they are written per post id and overwritten each run, the presence of `post_7_*.png` but absence of `post_8_*.png` is the *de facto* way to tell where a run died. That is an artefact, not a designed mechanism.

### 7.5 De-duplication mechanism

**It is a simple seen-list of topic strings, enforced by the LLM, not by code.**

- **Not hash-based.** No hashing anywhere.
- **Not ID-based.** Reddit post ids and permalinks are discarded at the planning stage (§3.5); nothing keys off a source id.
- **Not semantic.** No embeddings, no similarity scoring, no fuzzy matching.
- **It is a seen-list**, injected as text into the planning prompt, with the model asked: *"You MUST NOT choose any topic that is similar to the already used topics list. Avoid repetition! Every topic must be fresh."*

The only *code-enforced* check is the exact-string membership test on append (`topic not in used_topics`), which prevents a duplicate **entry in the list** but does nothing to prevent a duplicate **post** — "AI Agents in PPC" and "AI Agents in Ad Targeting" are both in the live file, and both were written.

**Two structural weaknesses in the current design:**

1. **The list only grows.** At 76 entries it is already a large prompt block; there is no pruning, no windowing, and no recency weighting. Every entry is treated as equally banned forever.
2. **Topics are marked used before they are written.** `used_topics.json` is written at line 343, *before* the 11 generation calls at line 350. If generation fails at post 4, the run exits — but all 11 topics are already burned and will never be selectable again, even though 8 posts were never produced.

**Cross-post de-duplication within a batch** (no two posts covering the same story) is likewise only a prompt instruction, in the planner. No code compares the 11 generated posts to each other.

**The de-dup machinery described in README.md:236-241 does not exist in the running system.** Carousel hook rotation, infographic 30-day topic bans, and performance-post 14-run bans all read log files that are absent (§7.7).

### 7.6 The guard that keeps the pipeline off past posts

**There is no explicit guard.** No code anywhere compares a computed schedule date to the current date, and no code enumerates or filters existing LinkedIn posts by date.

The protection is entirely **implicit and forward-only**, and consists of one line pair (`schedule_all_posts.cjs:291-293`):

```javascript
startDateObj = new Date(lastDate);
startDateObj.setDate(startDateObj.getDate() + 1);
```

Because every batch begins the day *after* the last batch ended, and because the scheduler only ever creates new posts (it never opens, edits or deletes an existing one), past posts are never touched. The safety property is "always move forward from the watermark", not "refuse to touch the past".

**This guard fails open in three ways:**

1. **Missing or unreadable state file** — `if (!startDateObj) { startDateObj = new Date(); }` (`:300-302`). Delete, rename or corrupt `pipeline_state.json` and the batch targets **today**, putting 9:00 AM / 12:00 PM / 3:00 PM in the past for most run times.
2. **Malformed date** — the `parts.length === 3` check (`:289`) is the only validation. A value like `"2026-08"` or `""` leaves `startDateObj` undefined → falls through to today.
3. **`START_DATE_OFFSET`** (`:280-284`) — accepts any integer including negatives, with no lower bound. `START_DATE_OFFSET=-5` schedules five days into the past.

There is also **no collision check**: if a batch is run twice without the watermark advancing (e.g. the first run crashed at post 10), the second run re-schedules posts 1-11 onto dates that already hold posts. Nothing detects or prevents that.

The one script that *can* touch existing posts, `delete_all_scheduled.cjs`, has **no date guard at all** — its loop (lines 130-208) repeatedly clicks the delete control and confirms, counting deletions, with no filtering by date, content or index. It deletes every scheduled post it can reach, past-dated or not.

### 7.7 Write ordering and crash behaviour

| State write | When, relative to the side effect | File:line |
|---|---|---|
| `used_topics.json` | **Before** generation — topics burned up front | `generate_all_content.py:343` |
| `linkedin_posts_*.txt` | After all 11 posts generated | `:367-370` |
| `carousel_data_*.json` | After each carousel JSON call | `:461-465` |
| `infographic_data_*.json` | After each infographic JSON call | `:512-516` |
| `pipeline_state.json` | **After all 11 posts are scheduled** | `schedule_all_posts.cjs:1098-1110` |

**Crash semantics, stage by stage:**

- **Crash during fetch (step 1):** `reddit_data.json` is written only at the end (`fetch_reddit_rss.py:75-76`), so a crash leaves the *previous* run's data intact. The pipeline aborts. Safe.
- **Crash during generation (step 2):** `used_topics.json` is already updated with all 11 topics — **permanently burned**. `linkedin_posts_today.txt` still holds the **previous run's 11 posts**. If someone then runs step 7 alone, the previous batch gets scheduled again onto new dates.
- **Partial JSON parse failure:** carousel/infographic JSON errors are caught and skipped, leaving the **previous run's** `carousel_data_N.json` on disk. Step 4 then renders yesterday's slides with today's caption. No error surfaces past a log line.
- **Crash during scheduling (step 7):** this is the significant one. Posts are scheduled **one at a time, each immediately live in LinkedIn's scheduler**, but `pipeline_state.json` is written **only after all 11 succeed**. A failure at post 8 means: 7 posts are really scheduled on LinkedIn, the watermark still points at the *previous* batch's end date, and a re-run will schedule all 11 posts starting on the same dates as the 7 that already exist — producing duplicates on days 1 and 2. There is no resume, no per-post checkpoint, and no idempotency key.

**Net:** state is written *before* the effect in generation (over-burns topics) and *after* the effect in scheduling (under-records completed work). Neither stage is transactional, and the failure modes of the two are opposite.

`run_pipeline.py` compounds this: `sys.exit(returncode)` on the first non-zero step means a step-7 failure stops the run with LinkedIn already partially written, and the operator has no built-in way to resume from post 8.

### 7.8 Files and stores that must NOT be deleted or reformatted without migration

**Tier 1 — deleting or reformatting these breaks scheduling or de-duplication:**

| File / dir | Why | Failure mode if lost/changed |
|---|---|---|
| **`pipeline_state.json`** | Sole scheduling watermark | Falls back to **today** → posts scheduled into the past mid-run; or, if hand-edited wrong, collides with existing scheduled posts |
| **`used_topics.json`** | Sole de-dup memory (76 entries) | Silently reseeded to 11 hard-coded 2026 topics; repeat topics resume immediately. A parse error degrades to "no memory" without failing |
| **`chrome-session/`** | Persisted LinkedIn login for Puppeteer | Scheduler cannot authenticate; every run fails at "Start a post". Requires a manual re-login (`login_linkedin.cjs`). **Contains live session cookies — treat as a credential store** |
| **`.env`** | All API keys | Generation, Slack delivery and Apify all abort |

**Tier 2 — deleting these breaks the current run in flight:**

| File | Why |
|---|---|
| `linkedin_posts_today.txt` | The scheduler's only input. Missing → `parseTodayPosts()` returns `null` → **the scheduler silently falls back to 11 hard-coded June 2026 posts** and schedules those (see §12) |
| `slack_downloads/carousel-{1,2,3}.pdf` | The carousel asset path the scheduler resolves to in practice |
| `linkedin-infographic-{1,2,3}.png` | The infographic asset paths |
| `linkedin-infographic-template.html` | Infographic renderer aborts with an explicit error |
| `skills/branded-carousel/SKILL.md` | **Live code** — carousel HTML templates are regex-extracted from it at runtime. Renaming any `TEMPLATE N` heading crashes the build |

**Tier 3 — historical/archive, safe to lose but unrecoverable:**

`linkedin_posts_YYYYMMDD.txt`, `performance_posts_YYYYMMDD.txt`, `carousel-routine/output/{date}/`, `linkedin-infographic-YYYYMMDD.png`, `slack_downloads/post_*.png`, `sample-outputs/`.

**Format constraints to preserve if any of these are edited:**

- `pipeline_state.json` — `last_scheduled_date` must be exactly `YYYY-MM-DD` with three `-`-separated parts, else the guard falls through to today.
- `used_topics.json` — must remain a **flat JSON array of strings**. Converting it to an array of objects (to add dates or types) breaks `json.dumps` readability in the prompt and, more importantly, breaks the `topic not in used_topics` membership test at line 298, which would then always append.
- `linkedin_posts_today.txt` — headers must match `/^\d+\./` and must contain the substrings `CAROUSEL`, `INFOGRAPHIC` or `POLL` to be typed correctly; sections must be separated by runs of **≥10 `=` characters**; poll options must be prefixed with `☐`, `[ ]`, `•` or `-`; carousel captions must follow a literal `CAROUSEL CAPTION:` marker; infographic captions a literal `INFOGRAPHIC CAPTION:` marker.

### 7.9 State files referenced in documentation that do not exist

These are read by `README.md`, `daily-linkedin-posts/SKILL.md` and `commands/linkedin-content.md`, and are **absent from disk**:

| Missing file | Referenced by | Consequence |
|---|---|---|
| `carousel-hook-log.json` | README:146; SKILL.md:153-163, 4E; linkedin-content.md:121 | Carousel hook rotation never happens; styles are fixed per slot |
| `infographic-run-log.json` | README:147; SKILL.md:57-69, 5B | 30-day infographic topic de-dup never happens |
| `performance-run-log.json` | README:148; performance-engine SKILL.md:44 | 14-run contrarian/poll de-dup never happens (moot — those posts are hard-coded) |
| `scheduled_history.json` | README:149 | No scheduled-post history exists |
| `founderswing_linkedin_content_report.md` | README:76; performance-engine premise | The "report-driven" performance posts have no report to read |
| `ai_news_posts_YYYYMMDD.txt` | SKILL.md STEP 6 | Never produced by the scripted path |

The agent-path steps that would create the first three (`daily-linkedin-posts/SKILL.md` 4E and 5B) use `try/except (FileNotFoundError, json.JSONDecodeError): log = []`, so they would create them on first use rather than fail. `update_logs_today.py` also creates two of them — but it is not called by `run_pipeline.py`, and when it runs it writes `"hook_style": "Story"` and `"format": "RANKED_BARS"` as constants, so the logs it produces would not reflect reality.

---

## 8. CONFIGURATION SURFACE

**There is no configuration file.** Every knob below is a literal in source code. The only runtime inputs are `.env` (5 keys), `raw_notes.txt` (free text), and one environment variable (`START_DATE_OFFSET`).

### 8.1 Configuration table

| Knob | Current value | File & line | What changing it affects |
|---|---|---|---|
| **Posts per day** | 4 / 4 / 3 | `schedule_all_posts.cjs:319-331` | Positional array; adding/removing entries changes which posts land on which day. Must stay length-11 or posts silently get `undefined` dates |
| **Posting times** | `9:00 AM`, `12:00 PM`, `3:00 PM`, `6:00 PM` | `schedule_all_posts.cjs:320-330` | Strings typed into LinkedIn's time combobox. Format must match what LinkedIn's autocomplete accepts |
| **Scheduling horizon** | 3 days (`day1`, `day2`, `day3`) | `schedule_all_posts.cjs:304-306` | Three `Date` objects; a 4th day requires a new variable + new array rows |
| **Schedule start date** | `pipeline_state.json.last_scheduled_date + 1 day` | `schedule_all_posts.cjs:284-298` | The only forward-only guard |
| **Schedule start override** | unset | env `START_DATE_OFFSET`, read at `schedule_all_posts.cjs:280` | Days from today; **accepts negatives**, no bounds check |
| **Total posts generated** | 11 (+5 performance) | `generate_all_content.py:192-250` (plan skeleton) | Changing the count means editing the JSON skeleton in the prompt **and** the schedule array **and** anything positional downstream |
| **Format mix** | 3 carousel / 3 infographic / 2 poll / 3 text | `generate_all_content.py:192-250` (key names) | Determined purely by the 11 key names in the planning prompt |
| **Slot → hook style** | Carousel 1 `Curiosity Gap`, 2 `Specific Result`, 3 `Myth Buster` | `generate_all_content.py:195, 216, 237` | Fixed per slot in the prompt skeleton; no rotation |
| **Slot → archetype** | TEXT 1 `Case Study`, TEXT 2 `Tool Spotlight`, TEXT 3 `Hot Take` | `generate_all_content.py:212, 232, 247` | Same |
| **Subreddit list** | `facebookads, PPC, n8n, Ecommerce, SaaS, marketing, entrepreneur, startups, Automation, artificial` | `fetch_reddit_rss.py:14` | The active source list |
| **Reddit sort / window / limit** | `top`, `t=week`, `limit=20` | `fetch_reddit_rss.py:22` (f-string) | Inside the URL; no separate variables |
| **Reddit retry / backoff** | 3 attempts, `(n+1)*4`s; 3s between subs | `fetch_reddit_rss.py:28, 68, 71` | Fetch resilience and total runtime |
| **Fake engagement values** | `ups: 100`, `num_comments: 10` | `fetch_reddit_rss.py:61-62` | Constants written for every item; any score-based logic is meaningless |
| **Reddit items shown to planner** | 20 | `generate_all_content.py:261` (`reddit_posts[:20]`) | The real candidate pool |
| **News items shown to planner** | 15 | `generate_all_content.py:264` (`ai_news[:15]`) | Reads a file nothing refreshes |
| **Model** | `gpt-4o` | `generate_all_content.py:37` | All 23 calls |
| **API endpoint** | `https://api.openai.com/v1/chat/completions` | `generate_all_content.py:28` | Provider |
| **API key variable** | `OPENAI_API_KEY` | `generate_all_content.py:19` | Read by exact string prefix match on `.env` lines |
| **Temperature** | **not set** (API default) | — | No sampling control exists to change |
| **max_tokens** | 4000 | `generate_all_content.py:35-41` (default arg, line 34) | Hard ceiling on every response |
| **LLM retries / 429 backoff** | 5 attempts; `10*(n+1)`s on 429 only | `generate_all_content.py:51, 62` | Non-429 errors get zero retries |
| **Inter-call delay** | 1s | `generate_all_content.py:363, 590` | Pacing between post generations |
| **Brand voice rules** | inline `writing_rules` string | `generate_all_content.py:90-117` | **The live voice config.** `voice-profile.md` / `content-doctrine.md` are NOT read by this script |
| **Banned words list** | inline, rule 7 | `generate_all_content.py:98` | Prompt-level only; never verified |
| **CTA / DM triggers** | `DM me 'SCALE'` / `'AUDIT'`, `@harshchouksey` | `generate_all_content.py:116, 187`; `voice-profile.md:22-24` | Prompt guidance only |
| **Performance post topics** | 5 hard-coded literal topics | `generate_all_content.py:527-575` | Identical every run; ignores all data sources |
| **Carousel count** | 3 | `build_carousel_today.cjs:28` | Loop bound |
| **Slides per carousel** | 7 | `build_carousel_today.cjs:39, 48`; `generate_carousel_today.py:104-176` | Must match in all three places |
| **Carousel brand colour** | `#5E6AD2` | `generate_carousel_today.py:83` | Overrides every palette in `FORMATS.md` |
| **Carousel canvas / scale** | 1080×1080, `deviceScaleFactor: 2` | `build_carousel_today.cjs:26` | Output resolution |
| **Carousel template source** | `./skills/branded-carousel/SKILL.md` | `generate_carousel_today.py:54` | Regex-extracted at runtime |
| **Carousel slide fallback copy** | Full SaaS-onboarding story | `generate_carousel_today.py:104-176` | Rendered whenever a JSON key is missing |
| **Slide 1 / 6 image replacement copy** | `2026 AI BLUEPRINT` / `Autonomous AI Ops` / `NATIVE AI OPERATING SYSTEM` | `generate_carousel_today.py:68, 74` | Appears on every carousel regardless of topic |
| **Stock image URLs** | 2 fixed Unsplash URLs | `generate_carousel_today.py:13-16` | Downloaded then discarded |
| **Image validity threshold** | 10,000 bytes | `generate_carousel_today.py:28` | Re-download trigger |
| **Infographic count** | 3 | `cap_infographic_today.js:28` | Loop bound |
| **Infographic canvas / scale** | 1080×1080, `deviceScaleFactor: 1` | `cap_infographic_today.js:21, 74` | Output resolution |
| **Infographic ports** | `8760 + idx` → 8761-8763 | `cap_infographic_today.js:67` | Local server; collides if those ports are in use |
| **Infographic template** | `linkedin-infographic-template.html` | `cap_infographic_today.js:9` | The only implemented format (RANKED_BARS) |
| **Infographic default bar colour** | `#5E6AD2` | `cap_infographic_today.js:43` | Used when JSON omits `color` |
| **Slack channel** | `SLACK_CHANNEL_ID` from `.env`, **fallback literal `C0BL8CKFMEU`** | `send_to_slack.py:9, 15-16` | Where content lands. Two other channel ids appear in docs: `C0BL8CKFMEU` (`daily-linkedin-posts/SKILL.md:9`) and `C0AVBBTD529` (`:341`) |
| **Slack token variable** | `SLACK_BOT_TOKEN` | `send_to_slack.py:13` | Exact-prefix match on `.env` |
| **Browser headless mode** | `headless: false` (scheduler) / `'shell'` (renderers) | `schedule_all_posts.cjs:552`; `build_carousel_today.cjs:17`; `cap_infographic_today.js:17` | Scheduler needs a visible desktop session |
| **Chrome profile path** | `./chrome-session` | `schedule_all_posts.cjs:553` | LinkedIn auth |
| **Scheduler viewport** | 1280×1200 | `schedule_all_posts.cjs:559` | Affects which LinkedIn controls render |
| **Upload wait timeout** | 60 × 1s | `schedule_all_posts.cjs:868` | Carousel PDF upload ceiling |
| **Per-step sleeps** | 150–6000 ms, ~20 literals | `schedule_all_posts.cjs` throughout | The main determinant of run duration and flakiness |
| **NODE_PATH** | `./carousel-routine/node_modules` | `run_pipeline.py:28, 31, 37` | How root `.cjs` files resolve `puppeteer` |

### 8.2 Hard-coded in logic — requires a code change, not a config change

Everything in the table above is a code change. These are the ones where the change is **structural** rather than a one-value edit:

1. **Posts per day and posting times** — the `schedule` array couples day, time and post *index* in one literal. Changing posts/day changes which post type lands at which time, because type is decided by position (§6.3).
2. **The format mix** — encoded as **key names inside a prompt string** in Python, consumed by **substring matching on header text** in JavaScript. Changing the mix means editing a prompt skeleton, and the type detection at `schedule_all_posts.cjs:186-188` must still recognise the new header names.
3. **Number of posts (11)** — appears independently in: the planning prompt skeleton, the schedule array length, the carousel loop bound (3), the infographic loop bound (3), and `send_to_slack.py`'s header-matching chain. Five places, no shared constant.
4. **The 5 performance post topics** — pure literals in the source with no data input.
5. **Hook styles and archetypes per slot** — literals inside the planning prompt; no rotation mechanism is connected.
6. **Brand voice** — lives in `generate_all_content.py:90-117`, *not* in `voice-profile.md`. The markdown files are documentation for the agent path only.
7. **Carousel slide count (7)** — three independent loop/dict bounds that must agree.
8. **Brand colour `#5E6AD2`** — one literal that overrides the entire documented palette system.
9. **Slide 1/6 replacement copy** — topic-independent text baked into a regex replacement.
10. **Timezone** — not represented anywhere. Times are strings; the effective timezone is whatever the LinkedIn account is set to.
11. **The scheduler's 11-post hard-coded fallback batch** (`schedule_all_posts.cjs:354-545`) — ~190 lines of June 2026 content with an absolute asset path under `/Users/prithal/...` that does not exist on this machine.
12. **Slack channel fallback `C0BL8CKFMEU`** — a literal default that silently applies if `SLACK_CHANNEL_ID` is missing from `.env`.

---

## 9. ERROR HANDLING & LOGS

### 9.1 What happens when a step fails

**Pipeline driver — crash.** `run_pipeline.py:10-13`: `subprocess.run(command, shell=True)`, then any non-zero return code prints `❌ ERROR: Step '{description}' failed with exit code {n}.` and `sys.exit(returncode)`. No retry, no skip, no cleanup, no resume. One exception: step 3's `cp` is suffixed `2>/dev/null || true` so it can never fail.

**Fetch (`fetch_reddit_rss.py`) — skip.** Per-subreddit try/except with 3 attempts and 4/8/12s backoff. After 3 failures the subreddit is **silently skipped and the loop continues**; the script still exits 0 and still writes `reddit_data.json`. This is why the last run produced 80 items from 4 subreddits instead of 200 from 10, with nothing surfacing as an error. **A run in which every subreddit fails writes an empty `reddit_data.json` and exits 0**, and the pipeline proceeds to generate posts from no source data.

**Generation (`generate_all_content.py`) — mixed:**
- Missing `OPENAI_API_KEY` → `exit(1)` (line 25).
- LLM call: 5 attempts, `10*(n+1)`s backoff **on HTTP 429 only**; any other HTTP status or exception `break`s immediately and returns `None`.
- Planning returns `None` → `sys.exit(1)`. Planning JSON unparseable → prints raw response, `sys.exit(1)`.
- Any of the 11 post calls returns `None` → `sys.exit(1)`.
- Any of the 5 performance calls returns `None` → `sys.exit(1)`.
- **Carousel/infographic JSON parse failure → caught, logged, and skipped** (lines 468, 519). The run continues and the stale previous JSON is reused. This is the only silent-corruption path in generation.
- File reads (`used_topics`, `raw_notes`, `reddit_data`, `ai_news_data`) are all wrapped in try/except that print and continue with an empty default.

**Carousel build (`build_carousel_today.cjs`) — crash.** No try/catch anywhere. `execSync` on `generate_carousel_today.py` throws on non-zero exit; a missing template regex, a `page.goto` timeout (15s) or a screenshot failure all propagate as an unhandled rejection and a non-zero exit. `if (!fs.existsSync(jsonFile) && idx > 1) continue;` skips carousels 2-3 if their JSON is missing, but **carousel 1 is attempted even when `carousel_data_1.json` is absent** — `generate_carousel_today.py` then renders entirely from its hard-coded fallback copy.

**Infographic build (`cap_infographic_today.js`) — mixed.** Missing template → explicit error + `process.exit(1)` (line 11-13). Missing per-index JSON → `continue` (idx > 1) or falls back to `infographic_data.json`, else `continue`. Malformed JSON → unhandled throw.

**Slack (`send_to_slack.py`) — swallow everything.** Every network operation is wrapped in try/except that prints and returns. `upload_slack_file` returns early on a missing file with `Error: file not found: {path}`. Slack API `ok: false` responses are printed, not raised. The script **always exits 0**, so `run_pipeline.py` proceeds to scheduling even if nothing reached Slack. One hard failure exists: the unguarded `open(f"linkedin_posts_{date_compact}.txt")` at line 141 throws `FileNotFoundError` if generation ran on a different calendar day.

**Scheduling (`schedule_all_posts.cjs`) — crash, mid-batch.** The entire 11-post loop is inside one try/catch (`:549-1133`). Any thrown error — a missing button, a failed validation, an upload timeout — aborts the whole run at that post. The catch block screenshots the LinkedIn tab to `error_screenshot.png`, closes the browser, and `process.exit(1)`. **Posts already scheduled stay scheduled; `pipeline_state.json` is not updated** (§7.7). Navigation is the only forgiving step: `page.goto` failures are caught and logged as `Navigation timeout/error, continuing` and the loop proceeds anyway.

Within a post, three sub-steps have local tolerance: poll options 3 and 4 are each wrapped in try/catch that logs `Ignored click error for option N` / `Failed to fill option N` and continues — but the blank-value validation at `:766-768` then throws anyway if the option did not land. The "Add a document" button has a two-tier retry (direct, then via the `More` menu).

### 9.2 Where logs go and what is logged

**There is no logging framework, no log file, and no log rotation.** Everything is `print()` / `console.log()` to **stdout of the terminal that launched the run**. If the terminal closes, the run's history is gone.

What is logged:

- `run_pipeline.py` — a banner per step (`STEP:` + `COMMAND:`), and the error line on failure.
- `fetch_reddit_rss.py` — the URL per subreddit, `✓ Found N entries in r/{sub}`, each retry with its wait, and a final `Saved N posts`.
- `generate_all_content.py` — the 11-line plan summary (`- {post_id}: {topic}`), `Generating {id}...` per post, each JSON save, each parse error, and rate-limit notices.
- `build_carousel_today.cjs` / `cap_infographic_today.js` — per-carousel/infographic progress and output paths.
- `send_to_slack.py` — message length per send, file size per upload, and Slack's error string on failure.
- `schedule_all_posts.cjs` — the most verbose: a banner per post (`Scheduling Post {id}/{n} ({type}): Date=..., Time=...`), each UI step, the matched element's tag/class/text from `clickNativelyShadow`, poll option values found in the DOM, document title value, caption length, and `✓ Successfully scheduled Post {id}/{n}!`.

**Visual logs are the durable artefact.** `schedule_all_posts.cjs` writes screenshots to `slack_downloads/post_{id}_{type}_{stage}.png` at five stages (`_filled`, `_doc_uploaded`, `_image_uploaded`, `_draft_composer`, `_schedule_settings`, `_final_draft`) — 81 files currently. Plus `error_screenshot.png` at the project root on crash. These are overwritten each run, so only the most recent run is inspectable.

**Not logged anywhere:** which post index failed (only visible via the screenshot set), LLM token usage or cost, which Reddit thread produced which post, LinkedIn's confirmation of a scheduled post, and any timestamp on any log line.

### 9.3 Rate limiting, backoff, and LinkedIn-detection avoidance

**Rate limiting / backoff that exists:**

| Where | Mechanism |
|---|---|
| Reddit RSS | 3 attempts, 4/8/12s backoff; flat 3s between subreddits (`fetch_reddit_rss.py:68-71`) |
| Reddit `.json` fallback | 1s between URLs, comment `# Be nice to Reddit` (`fetch_reddit_fallback.py:55`) |
| Reddit User-Agent | Identifies itself: `LinkedInPipelineBot/1.0 (by /u/harshchouksey; sub={sub})` (`fetch_reddit_rss.py:25-26`) |
| OpenAI | 5 attempts, 10/20/30/40/50s backoff **on 429 only** (`generate_all_content.py:62`) |
| OpenAI pacing | 1s between post generations (`:363, 590`) |
| Apify (dormant) | 5s status polling loop (`fetch_reddit_apify.py:63`) |
| Slack | **None** — no delay between ~15 messages and ~10 file uploads |
| LinkedIn | **No rate limiting of any kind** |

**LinkedIn-detection avoidance — what exists and what does not.**

There is **no anti-detection code**: no stealth plugin (`puppeteer-extra-plugin-stealth` is not installed — the only dependency is plain `puppeteer`), no user-agent spoofing, no `navigator.webdriver` patching, no proxy, no randomised timing, and no jitter. Every delay is a fixed literal.

What incidentally reduces automation signal:

1. **A real, persistent Chrome profile** (`userDataDir: './chrome-session'`) rather than a fresh incognito context — cookies, history and device fingerprint stay stable across runs.
2. **`headless: false`** — a real visible browser window with a real renderer.
3. **`page.keyboard.type()` for all text**, which emits genuine per-character key events rather than setting `value` directly, plus paragraph-by-paragraph typing with 150 ms pauses (`schedule_all_posts.cjs:979-989`).
4. **Full page reload to `/feed/` between every post** with a 4s settle — slow, but human-plausible pacing.
5. **Native `el.click()` first**, falling back to a synthetic pointer/mouse event sequence only when that fails.

What increases exposure: 11 composer sessions back to back with no randomisation, identical inter-step delays every run, and file uploads via direct `input[type=file]` manipulation. Two behaviours are explicitly adversarial to the page rather than merely automated — the injected stylesheet that force-hides `.msg-overlay-container` (`:582-593`) and the `document.querySelectorAll('.msg-overlay-container, …').forEach(el => el.remove())` inside `clickNativelyShadow` (`:42-44`), which deletes LinkedIn's own DOM nodes before every click.

**Practical consequence:** the pipeline's LinkedIn safety rests entirely on a persistent logged-in profile and slow fixed pacing. A session expiry, a checkpoint challenge, or a CAPTCHA produces no specific handling — the run fails at "Could not find 'Start a post' button" and exits 1.

---

## 10. GIT HISTORY

### 10.1 Last 20 commits

**Not available — this project is not a git repository.** `git status` returns:

```
fatal: not a git repository (or any of the parent directories): .git
```

There is no `.git` directory, no `.gitignore`, and no remote. There is no commit history, no blame, no branches, no tags, and **no way to recover a file that is overwritten or deleted**. Nothing in this section can be answered from version control.

Two consequences worth stating plainly for a project about to be changed:

1. **There is no rollback.** Editing `generate_all_content.py` or `schedule_all_posts.cjs` destroys the previous version. The same applies to `used_topics.json` and `pipeline_state.json`.
2. **`.env` is unprotected.** With no `.gitignore` in place, initialising a repository here would stage `.env` (5 live API keys) and `chrome-session/` (live LinkedIn session cookies) by default.

### 10.2 Which files change most often

Reconstructed from filesystem mtimes, since no commit history exists. Grouping by modification date reveals the run cadence — 2026-06-21/24, 07-24, 07-25, 07-26, 07-27, 07-29, 08-01, 08-04.

**Changed on essentially every run (data/state, machine-written):**

| File | Last modified |
|---|---|
| `reddit_data.json` | 2026-08-04 19:42 |
| `used_topics.json` | 2026-08-04 19:42 |
| `linkedin_posts_today.txt` / `linkedin_posts_YYYYMMDD.txt` | 2026-08-04 19:43-19:45 |
| `carousel_data{,_1,_2,_3}.json` | 2026-08-04 19:44 |
| `infographic_data{,_1,_2,_3}.json` | 2026-08-04 19:44 |
| `performance_posts_YYYYMMDD.txt` | 2026-08-04 19:45 |
| `linkedin-infographic-{1,2,3}.{html,png}` | 2026-08-04 19:53 |
| `carousel-routine/output/{date}/`, `carousel-routine/temp/` | 2026-08-04 19:54 |
| `error_screenshot.png` | 2026-08-04 19:55 |
| `slack_downloads/` | 2026-08-04 20:04 |
| `pipeline_state.json` | 2026-08-04 20:04 |
| `chrome-session/` | 2026-08-04 21:07 |

**Source files actually edited over the project's life** (most-recently-touched first — these are the ones under active development):

| File | Last modified | Signal |
|---|---|---|
| `schedule_all_posts.cjs` | 2026-08-04 19:55 | Edited during the most recent run — the hottest code file |
| `generate_carousel_today.py` | 2026-08-01 01:56 | |
| `run_pipeline.py` | 2026-08-01 02:02 | |
| `cap_infographic_today.js` | 2026-07-25 01:55 | |
| `generate_all_content.py` | 2026-07-25 01:57 | |
| `fetch_reddit_rss.py` | 2026-07-25 01:52 | |
| `linkedin-infographic-template.html` | 2026-07-25 00:57 | |
| `send_to_slack.py` | 2026-07-24 00:13 | Stale relative to the generator it parses (see §12) |
| `daily-linkedin-posts/SKILL.md` | 2026-07-24 00:07 | |
| `login_linkedin.cjs` | 2026-07-24 00:12 | |
| `content-doctrine.md`, `voice-profile.md`, `commands/linkedin-content.md` | 2026-06-24 00:14-00:17 | Not touched in ~6 weeks |
| `README.md`, and ~40 legacy scripts | 2026-06-21 23:51 | Bulk timestamp — never edited since |

The `2026-06-21 23:51` bulk timestamp on ~40 files (all the legacy fetchers, generators, schedulers and Slack scripts) indicates a copy/move operation, not individual edits. Those files have been dormant since.

**Read as change-frequency:** the active pipeline is 8 files, and 3 of them (`schedule_all_posts.cjs`, `generate_carousel_today.py`, `run_pipeline.py`) account for all source changes in the last two weeks.

### 10.3 TODO / FIXME / HACK comments

A case-sensitive and case-insensitive grep for `TODO`, `FIXME`, `HACK` and `XXX` across all `.py`, `.js`, `.cjs`, `.md` and `.json` files (excluding `node_modules/`, `chrome-session/`, `slack_downloads/`) returns **zero matches**.

There are no TODO, FIXME, HACK or XXX markers anywhere in the codebase.

That absence is not evidence of completeness. The equivalent signals are carried in prose and in code comments instead, and these are the ones worth reading as open items:

**README.md:228** — the performance posts are generated but not wired to the scheduler:
> "**Note:** The 5 report-driven performance posts (STEP 7) are **delivered to Slack for review/manual posting but are not yet wired into the LinkedIn auto-scheduler.** Scheduling them automatically is a separate task. See the cadence caveat below."

**README.md:232** — an explicitly deferred, unresolved contradiction:
> "The performance posts were added per an explicit "add on top" decision; the volume-reduction recommendation is intentionally **deferred, not resolved.** Revisit whether to cut overall cadence before scaling output further."

**`generate_all_content.py:133`** — a seed list that only exists to paper over a missing file:
```python
# Initial seed of topics used in the first run to prevent repetition
```

**`generate_carousel_today.py:65`** — an acknowledged workaround for broken image handling:
```python
# Replace fragile image elements in t1 and t6 with sleek branded CSS badge cards
```

**`generate_carousel_today.py:182`** — a defensive re-substitution guarding against a known templating bug:
```python
# Correct template 3 & 5 replacement bugs if any (e.g. circle word 2)
```

**`send_to_slack.py:186`** — a step that was disabled in place rather than removed:
```python
print("Daily newspaper HTML and PDF already generated successfully. Skipping generation step.")
```
The comment above it still says "Generate interactive newspaper HTML and PDF first so we can upload it", but no generation happens; the `print` is the whole implementation.

**`send_to_slack.py:91-92`** — an uncertainty note left in the upload path:
```python
# Use multipart/form-data logic or raw POST
# Slack files.getUploadURLExternal accepts raw file data as POST body
```

**`schedule_all_posts.cjs:348-351`** — a header block describing behaviour that no longer matches the code below it:
```javascript
// ==========================================
// ALL 11 POSTS — 4 per day across 3 days
// Schedule: 9:00 AM, 12:00 PM, 3:00 PM, 6:00 PM IST
// ==========================================
```

---

## 11. CHANGE SURFACE MAP

Risk ratings below are **risk to existing state** — the chance that the change corrupts `pipeline_state.json` / `used_topics.json` / `chrome-session/`, or causes duplicate or mis-dated posts on LinkedIn. A change can be large in effort and still LOW risk to state.

### a) Reducing posts per day and changing posting times

**Risk to existing state: MEDIUM**

| File | Function / location | Change |
|---|---|---|
| `schedule_all_posts.cjs` | `parseTodayPosts()` — `schedule` array, `:319-331` | Rewrite the array: fewer rows, new time strings |
| `schedule_all_posts.cjs` | `parseTodayPosts()` — `:304-306` | Add/remove `dayN` variables if the horizon changes |
| `generate_all_content.py` | planning prompt skeleton, `:192-250` | Reduce the number of plan keys to match, or accept surplus posts |
| `schedule_all_posts.cjs` | `:1112-1114` | Stale summary strings |
| `README.md` | `:212-232` | Already stale |

**Why MEDIUM, not LOW.** Three specific traps:

1. **Surplus posts are not dropped.** `posts.forEach((p, idx) => { if (schedule[idx]) {...} })` (`:333-338`) leaves any post beyond the array length with `date`/`time` **undefined**. That post still enters the scheduling loop, still opens a composer, still uploads its asset, and fails at the date field — after LinkedIn has already been written to. If you shorten the schedule array without shortening the generated batch, the run will partially succeed and then crash.
2. **`last_scheduled_date` is derived from `posts[posts.length - 1].date`** (`:1100-1102`), not from the schedule array. With surplus posts present, that is `undefined.split('/')` → throws inside the try/catch → **the watermark is never written**, and the next run re-schedules onto the same dates.
3. **Type-to-slot coupling.** Reducing 4 posts/day to 3 shifts every post type onto a different time slot, because position determines both (§6.3).

**Safe sequencing:** change the plan skeleton first (so the batch size matches), then the schedule array, then run once with `START_DATE_OFFSET` set to a far-future value and delete the test posts manually, before letting it touch the real watermark.

### b) Replacing Reddit sourcing with a different topic source

**Risk to existing state: LOW**

| File | Function / location | Change |
|---|---|---|
| new file (or `fetch_reddit_rss.py`) | whole script | Write the new fetcher; emit the same object shape |
| `run_pipeline.py` | `main()`, `:19` | Point step 1 at the new script |
| `generate_all_content.py` | `:159-165`, `:261` | Path and slice if the filename changes |

**Contract to preserve.** The planner consumes `reddit_data.json` as a JSON array serialised straight into the prompt. Only `title` and `selftext` carry real signal — `ups` and `num_comments` are the fabricated constants `100` and `10` (§3.2), and `url`/`image_url`/`subreddit` are dropped after planning. A replacement source needs only:

```json
[{ "subreddit": "...", "title": "...", "selftext": "...", "ups": 100, "num_comments": 10, "url": "...", "image_url": null }]
```

Realistically `title` + `selftext` suffice; the rest can be stubbed.

**Why LOW.** Nothing downstream of the planner touches source data, and no state file records provenance. `used_topics.json` and `pipeline_state.json` are untouched. The main hazard is silent: `fetch_reddit_rss.py` currently exits 0 even when every fetch fails (§9.1), so a new fetcher that inherits that pattern will let the pipeline generate 11 posts from an empty array without any error. Fail loudly on an empty result.

**Note:** `ai_news_data.json` is a second, independent input at `:167-173` and `:264` that nothing refreshes. Replacing Reddit does not address it.

### c) Adding a fixed content-pillar rotation instead of trend-driven topics

**Risk to existing state: LOW–MEDIUM**

| File | Function / location | Change |
|---|---|---|
| `generate_all_content.py` | planning system prompt, `:176-251` | Replace or constrain topic selection with pillar assignment |
| `generate_all_content.py` | planning user prompt, `:253-265` | Feed the pillar list and the pillar-rotation position |
| `generate_all_content.py` | `:296-299`, `:342-344` | Decide what gets written to `used_topics.json` under a pillar model |
| new file | — | A pillar-rotation state file (there is no precedent to follow) |

**The real decision is what happens to `used_topics.json`.** Under a pillar model the same pillar recurs by design, which is exactly what the current de-dup memory forbids. Three options with different risk:

- Keep `used_topics.json` recording the *specific angle* within a pillar (not the pillar name) — LOW risk, no format change, memory keeps working.
- Add a separate `pillar_rotation.json` — LOW risk, additive; note nothing else in the repo creates or reads such a file, and the three existing log files it would resemble are all missing (§7.9).
- Restructure `used_topics.json` into objects with a `pillar` field — **MEDIUM risk**: this breaks the `topic not in used_topics` membership test at `:298`, which would then never match and append unbounded duplicates. Requires migrating all 77 existing entries, with no git history to fall back on.

The rotation machinery already described in the docs (`carousel-hook-log.json` rotation rules in `commands/linkedin-content.md:119-136`) is a working design to copy from, but it has never actually run (§7.9), so treat it as a spec, not as tested code.

### d) Rewriting the post-writing prompt templates and brand voice

**Risk to existing state: LOW** (but the highest chance of *silently* wrong output)

| File | Function / location | Change |
|---|---|---|
| `generate_all_content.py` | `writing_rules`, `:90-117` | **The live brand voice.** Edit here |
| `generate_all_content.py` | `system_prompt_main`, `:119-121` | Main writing system prompt |
| `generate_all_content.py` | `performance_system_prompt`, `:523-525` | Performance system prompt |
| `generate_all_content.py` | `:301-336` | The four per-post prompt templates |
| `generate_all_content.py` | `:377-448`, `:474-499` | Carousel/infographic JSON prompts |
| `voice-profile.md`, `content-doctrine.md` | whole files | Documentation + agent path only |

**The critical fact: editing `voice-profile.md` or `content-doctrine.md` changes nothing in the running pipeline.** Neither file is opened by `generate_all_content.py`; the rules were transcribed by hand into `writing_rules` (§4.12). A voice rewrite that only touches the markdown will appear to succeed and produce identical output. Either edit the Python string, or add a loader that reads the markdown — but do not assume the markdown is live.

**Output-format constraints that must survive any prompt rewrite** (these are parsed downstream, not merely stylistic):

- Poll options must be prefixed `☐` (or `[ ]`, `•`, `-`) — `schedule_all_posts.cjs:198`
- Carousel captions must follow a literal `CAROUSEL CAPTION:` line — `:227`
- Infographic captions must follow a literal `INFOGRAPHIC CAPTION:` line — `:266`
- Carousel hook lines are found via `Hook text:` or `Hook:` — `:234`
- Section headers must match `/^\d+\./` and contain `CAROUSEL` / `INFOGRAPHIC` / `POLL` — `:179, 186-188`

Break any of these and the post still schedules, just with the wrong caption, a missing title, or as the wrong post type. Nothing errors.

**Also worth knowing:** the poll question is extracted as the last non-empty line before the first `☐` (`:203-211`), which currently captures the literal prefix `"Question: "` in the question text. Any prompt rewrite is an opportunity to fix or entrench that.

`used_topics.json` and `pipeline_state.json` are untouched by this change.

### e) Adding a lead-capture CTA layer (comment-keyword / DM trigger)

**Risk to existing state: LOW**

| File | Function / location | Change |
|---|---|---|
| `generate_all_content.py` | `writing_rules` rule 11, `:116` | Already specifies DM triggers; extend/parameterise |
| `generate_all_content.py` | planning prompt CRITICAL RULE 2, `:187` | Already mandates lead magnets in ≥50% of posts |
| `generate_all_content.py` | `:301-336` | Add a CTA slot to each per-post template if you want deterministic placement |
| `generate_carousel_today.py` | slide 7 defaults, `:169-175` | Carousel CTA slide |
| `generate_all_content.py` | `:441-446` | Slide 7 CTA in the carousel JSON prompt |

**The scaffolding already exists.** Rule 11 currently reads: *"Include a clear DM action trigger in at least 50% of posts (e.g., "DM me 'SCALE' to get our 3-node n8n workflow blueprint", "DM me 'AUDIT' to review your lead response pipeline")"*, and the planner is told to use `DM me 'AUDIT'`, `'CAPI'`, `'WORKFLOW'`. So this is largely a prompt-tuning change, not new architecture.

**What is genuinely absent, and is the harder half of the request:** there is **no capture side**. Nothing in this repo reads LinkedIn comments, reads DMs, matches a keyword, or records a lead. That would be an entirely new component with a new state store, new LinkedIn UI automation (or the LinkedIn API), and its own auth. It shares nothing with the existing code except the `chrome-session/` profile — and note that any new automation using that same profile increases the automated-activity load on one LinkedIn session (§9.3).

Enforcement is also worth flagging: "at least 50% of posts" is a prompt instruction that **no code verifies**. If CTA presence matters commercially, a post-generation check on `linkedin_posts_today.txt` would be the first quality gate in the pipeline.

`used_topics.json` and `pipeline_state.json` are untouched.

### f) Changing the format mix and adding personal/case-study post types

**Risk to existing state: HIGH**

| File | Function / location | Change |
|---|---|---|
| `generate_all_content.py` | planning skeleton, `:192-250` | The 11 key names — this *is* the format mix |
| `generate_all_content.py` | prompt dispatch, `:301-336` | The `if "POLL" in post_id / "CAROUSEL" / "INFOGRAPHIC" / else` chain |
| `generate_all_content.py` | `:374`, `:471` | `carousel_keys` / `infographic_keys` substring filters |
| `schedule_all_posts.cjs` | `parseTodayPosts()`, `:186-188` | Type detection by header substring |
| `schedule_all_posts.cjs` | attachment branches, `:641`, `:786`, `:914` | One branch per attachment type |
| `schedule_all_posts.cjs` | `schedule` array, `:319-331` | Position determines which type lands at which time |
| `build_carousel_today.cjs` | `:28` | Carousel count loop bound |
| `cap_infographic_today.js` | `:28` | Infographic count loop bound |
| `send_to_slack.py` | `:145-177` | Header-matching chain (already broken — §12) |

**Why HIGH.** The format mix is expressed **five times, in three languages, with no shared constant**: as key names in a Python prompt string, as substring filters in Python, as a substring switch in JavaScript, as loop bounds in two more JavaScript files, and as array position for scheduling. Changing the mix means changing all of them consistently, and **every mismatch fails silently rather than loudly**:

- A header the scheduler does not recognise becomes a **plain text post** — the asset is simply never attached, and the run reports success.
- Generating 4 carousels while `build_carousel_today.cjs` loops to 3 produces a post whose `assetPath` does not exist → `uploadFile` throws **mid-batch**, after earlier posts are already live on LinkedIn, and the watermark is never written (§7.7).
- Changing counts shifts every type onto a different time slot.

**Adding a new type** (e.g. "personal story", "case study") is lower risk if it needs **no attachment** — a new `TEXT`-style key falls through to the `else` branch in both the prompt dispatch and the scheduler's type detection, and works with no scheduler change at all. That is the cheap path. A type needing a *new attachment kind* requires a new branch at `schedule_all_posts.cjs:640-962` and new LinkedIn selectors, which is where the real cost sits.

**Video is not supported anywhere** — there is no code path, no selector, and no renderer for it.

State risk specifically: `used_topics.json` format is unaffected, but the mid-batch crash mode above is the single most likely way to end up with duplicate LinkedIn posts.

### g) Adding a per-post performance logger that reads back LinkedIn metrics

**Risk to existing state: LOW to build, HIGH to retrofit correctly**

**Nothing to modify — this component does not exist.** There is no metrics code, no analytics reader, and no post-identity record anywhere in the repo.

| Concern | Current situation |
|---|---|
| Post identity | **None.** No LinkedIn post URN/URL is ever captured. Posts are identified only by array index within a run |
| Published record | **None.** Nothing confirms a post was published (§7.4) |
| Read-back path | **None.** No script reads LinkedIn analytics |
| The report the docs assume | `founderswing_linkedin_content_report.md` — **missing** (§7.9). The "report-driven" performance engine has never had a report to read |

**The blocking prerequisite is post identity.** To attribute a metric to a post you must first know which LinkedIn post corresponds to which generated post, and that link is destroyed today. The natural insertion point is `schedule_all_posts.cjs` immediately after step 13 (the final `Schedule` click, `:1058-1066`): capture the resulting post URN/URL and write a record. That is an additive change to a file that is otherwise the most fragile in the repo, and it must be inside the existing try block without introducing a new throw — an exception there would abort the batch mid-run.

Files that would be touched: `schedule_all_posts.cjs` (post-schedule hook), plus a **new** state file, plus a new reader script, plus `run_pipeline.py` for a new step. Reading back metrics also means driving LinkedIn's analytics UI with the same `chrome-session/` profile — more automated activity on one session (§9.3).

**Why HIGH to retrofit correctly:** every post scheduled before this change is unattributable forever, and the "3 days ahead" scheduling window means metrics for a post are only meaningful several days after the run that created it — so the logger must be a separate, independently-triggered pass with its own state, not a step inside `run_pipeline.py`. Designing it as step 8 of the existing linear pipeline would read metrics for posts that have not been published yet.

---

## 12. RISKS & GOTCHAS

### 12.1 The things most likely to break the pipeline if changed carelessly

**1. `pipeline_state.json` — the 87-byte file that prevents duplicate posting.**
Delete it, rename it, empty it, or malform `last_scheduled_date`, and `startDateObj` silently falls back to **today** (`schedule_all_posts.cjs:300-302`). Posts then target time slots that have already passed. There is no validation beyond `parts.length === 3` and no warning.

**2. Mid-batch scheduler crash leaves LinkedIn and local state disagreeing.**
Posts go live in LinkedIn's scheduler one at a time, but the watermark is written only after all 11 succeed (§7.7). A failure at post 8 leaves 7 real scheduled posts and an unadvanced watermark; re-running duplicates them. This is the highest-probability real-world failure, and there is no resume, no checkpoint, and no idempotency key.

**3. The scheduler's hard-coded fallback batch.**
`schedule_all_posts.cjs:354-545`: if `linkedin_posts_today.txt` is missing, `parseTodayPosts()` returns `null` and the script schedules **11 hard-coded posts from June 2026** — about Mistral's valuation, SpaceX's listing, and founder isolation. It logs `No linkedin_posts_today.txt found. Using default hardcoded fallback.` and proceeds. Those posts reference `@founderswing` (the old brand) and point at an absolute asset path on a different machine: `/Users/prithal/3d website/linkedin-automation-routine/slack_downloads/linkedin-carousel-2026-06-12.pdf`. **A missing input file causes off-brand, year-old content to be scheduled rather than an error.**

**4. `used_topics.json` reseeding.**
Delete it and `generate_all_content.py:132-148` recreates it with 11 hard-coded seed topics — you lose 65 of 76 entries and repeat topics resume. A JSON parse error is worse: the `except` at line 130 leaves `used_topics = []`, so the run proceeds with **no de-duplication memory at all** and still overwrites the file at line 343 with only that run's topics.

**5. `skills/branded-carousel/SKILL.md` is executable, not documentation.**
`generate_carousel_today.py:59-63` extracts five HTML templates by regex on the headings `TEMPLATE 1`, `TEMPLATE 2 & 4`, `TEMPLATE 3 & 5`, `TEMPLATE 6`, `TEMPLATE 7`. Renaming, reordering or reformatting any of those headings — or changing a ` ```html ` fence — makes `re.search(...).group(1)` raise `AttributeError: 'NoneType'` and kills the build. Nothing signals that this markdown file is load-bearing code.

**6. `chrome-session/` is the only credential for LinkedIn.**
Deleting it, or opening the same profile in another Chrome instance while the scheduler runs, breaks authentication. It also contains **live session cookies** and should be treated as a secret — particularly relevant given there is no `.gitignore` (§10.1).

**7. Format-mix changes fail silently across five uncoordinated definitions** (§11f).

**8. `delete_all_scheduled.cjs` has no date guard.**
Its loop (`:130-208`) deletes every scheduled post it can reach, with no filtering by date, content or count. There is no dry-run and no confirmation prompt. Running it to "clean up a bad batch" also destroys any correctly scheduled posts.

### 12.2 Fragile assumptions

**LinkedIn UI selectors — the single largest external dependency.**
The most fragile is the schedule-modal opener (`schedule_all_posts.cjs:1019-1028`), which finds the button whose text is exactly `Post` and clicks **`postBtn.previousElementSibling`**. The clock icon is identified purely by DOM adjacency; any change to LinkedIn's button order breaks it, and the fallback (`aria-label` contains `Schedule`) may not exist. Beyond that, the code depends on exact English button text — `'Start a post'`, `'Done'`, `'Next'`, `'Schedule'`, `'Add option'`, `'Create a poll'`, `'Add a document'`, `'Add media'` — plus LinkedIn-internal class names (`.ql-editor`, `.polls-detour__question-field`, `input[id*="poll-option"]`, `input.document-title-form__title-input`, `.share-box`, `.artdeco-modal`). **A LinkedIn locale other than English, or any A/B-tested label change, breaks the run.**

**Timing assumptions.** Roughly 20 fixed `setTimeout` literals (150 ms to 6000 ms) stand in for readiness checks. The 1500 ms wait for the time-combobox suggestion list followed by a blind `ArrowDown` + `Enter` (`:151-155`) is the most consequential: if suggestions load slowly, `ArrowDown` selects the wrong entry and **the post is scheduled at the wrong time with no error** — the run still logs success. On a slow network or loaded machine, the failure mode is silent mis-scheduling, not a crash.

**Timezone handling — absent.** No timezone is set, converted or validated anywhere. Times are literal strings typed into LinkedIn's UI, so they are interpreted in the LinkedIn account's timezone while dates are computed from the **local machine's** clock (`new Date()`). README calls the times IST. If the machine's timezone and the LinkedIn account's timezone ever diverge, dates and times drift relative to each other. Separately, `build_carousel_today.cjs:7-11` and `cap_infographic_today.js:23-26` apply a manual `getTimezoneOffset()` correction before `toISOString()` for output directories, while `schedule_all_posts.cjs:261` uses **raw `new Date().toISOString()`** for the infographic date-fallback filename — the two conventions disagree near midnight UTC.

**Date-crossing assumption.** `send_to_slack.py:141` opens `linkedin_posts_{today}.txt` unguarded. Runs that start before midnight and reach Slack after midnight throw `FileNotFoundError`. Given observed run times of ~19:42-20:04 this is not currently triggered, but the pipeline has no protection against it.

**Hard-coded absolute paths.** `/Users/prithal/3d website/linkedin-automation-routine/...` appears in the scheduler's fallback batch — a path from a different user on a different machine.

**Network assumptions.** SSL verification is disabled in every Python fetcher (`ctx.verify_mode = ssl.CERT_NONE`). The infographic template loads Google Fonts over the network and `cap_infographic_today.js:71` awaits `document.fonts.ready`, so a blocked font request renders a fallback font silently. Ports 8761-8763 must be free.

**Reddit fetch fragility.** RSS is unauthenticated and rate-limited; the last run silently lost 6 of 10 subreddits, and only the first 20 items reach the planner — currently all from a single subreddit (§3.3).

**Asset path resolution.** `schedule_all_posts.cjs:245-253` looks for carousel PDFs in `carousel-routine/output/{date}/carousel-branded/carousel-{idx}/`, but `build_carousel_today.cjs:55` writes them one level up, in `carousel-branded/`. The `carousel-{idx}/` subdirectory contains only slide PNGs. **In practice every run falls back to `slack_downloads/carousel-{idx}.pdf`** — which works, because the build script copies there, but the primary lookup path has never succeeded. If someone "fixes" the copy step without fixing the lookup, uploads break.

### 12.3 Unfinished, dead, or contradictory code

**`send_to_slack.py` is parsing a format that no longer exists.**
Its header chain (`:145-177`) matches `1. COLLABORATIVE ARTICLE`, `2. POLL`, `3. CAROUSEL`, `4. INFOGRAPHIC`, `5. POST 1` … `11. POST 7`. The generator writes `1. CAROUSEL 1`, `2. INFOGRAPHIC 1`, `3. POLL 1`, `4. TEXT 1`, `5. CAROUSEL 2` … `11. TEXT 3`. **Not one header matches.** Consequently `posts` stays empty, `collaborative_article` / `poll` / `post_1..7` are never populated, and Slack receives the header message and file uploads but **none of the 11 post texts**. It also uploads `linkedin_posts_{date}.pdf`, which nothing in the current pipeline generates. The script exits 0 throughout, so nothing surfaces. This is the clearest live defect found.

**Roughly 80% of the codebase is dead.** Not reachable from `run_pipeline.py`: 5 alternate Reddit fetchers, `fetch_ai_news_rss.py` (yet its stale output is still fed to the planner every run), 5 legacy generators, `correct_posts.py`, `write_today_data.py`, `update_logs_today.py`, `generate_daily_paper.py`, `aigen_image.py`, 5 legacy scheduler variants, 5 `post_urgent_*.cjs`, ~8 `cap_infographic*` variants, 4 `build_carousel*` variants, and all the legacy Slack senders. Several are near-identical `.js`/`.cjs` pairs.

**Two parallel pipelines with no marker of which one ran** (§2.4). `daily-linkedin-posts/SKILL.md` describes a fundamentally different workflow (Apify, WebSearch, agent-written posts, Slack MCP, three run-log files) writing to the same output paths.

**Naming that actively misled.** ~~`generate_all_content_gemini.py` calls OpenAI's `gpt-4o`; its function is `call_gemini()`; its error messages all say "OpenRouter". Three different providers named in one file that talks to a fourth.~~ **Fixed in Phase 3d (2026-08-13)**, after the name cost debugging time twice: an OpenAI billing 429 sent Harsh to check his Gemini quota. Now `generate_all_content.py` / `call_llm()`, with the provider read from `pipeline_config.json` and a file header recording the whole naming history so it cannot recur.

**Documented features that are not implemented:**
- Carousel hook rotation — 10 styles and ban rules defined; log file missing; styles fixed per slot in the prompt.
- Infographic format selection — 5 formats and a decision tree defined; only RANKED_BARS has a renderer; `update_logs_today.py:60` hard-codes `"RANKED_BARS"`.
- Carousel format selection — 6 formats defined in `FORMATS.md`; the renderer uses one fixed 7-slide layout and one hard-coded colour.
- Infographic 30-day and performance 14-run de-duplication — log files missing.
- The three-tier real-image sourcing strategy — the scripted path downloads two fixed Unsplash photos and then discards them (§5.2).
- `founderswing_linkedin_content_report.md` — the report the "report-driven" performance engine is built around does not exist.

**Brand and audience contradictions across live files.**
`skills/illustration-formats/SKILL.md:67` mandates `@founderswing` in every infographic footer; `FORMATS.md` and `illustration-formats/SKILL.md:10` define the topic lane as "AI's impact on work, income, skills, and the future" and explicitly rule out marketing-ops content. `content-doctrine.md`, `voice-profile.md` and the live generator all specify `@harshchouksey` and a Meta-Ads/n8n lane. `README.md:5` describes the account as "the Varun Mayya of LinkedIn" for "ambitious generalists". `README.md:3` says "Founders Wing"; `carousel-routine/package.json` says "Founders Wing daily LinkedIn carousel renderer". `correct_posts.py` is built to insert "FounderWing" mentions. The scheduler's fallback posts sign off `Follow @founderswing`. **Three brand identities coexist in files that are all still loaded or reachable.**

**Volume contradiction, acknowledged and unresolved.** README.md:230-232 records that the analytics report recommends **≤7 posts/week** while the pipeline produces 16/day, and states the reduction is *"intentionally deferred, not resolved."*

**Smaller dead or contradictory details:**
- `fetch_reddit_rss.py:15-17` defines a browser User-Agent that is immediately overwritten at `:24-26`.
- `generate_all_content.py:79-87` loads `reddit_posts[:15]` and `ai_news[:12]`, then both variables are reassigned at `:159` and `:167`.
- `run_pipeline.py:19` is labelled "Fetching Fresh Reddit RSS & AI News Data" but fetches no news.
- `run_pipeline.py:25` copies a file that step 2 already wrote to both names.
- `send_to_slack.py:185-186` replaces the newspaper-generation step with a `print` claiming it already succeeded.
- `send_to_slack.py:225` looks for `startup-strategy-carousel.pdf`, a filename nothing produces.
- `schedule_all_posts.cjs:1112-1114` prints a summary naming June 13-15 2026 and post types the generator no longer emits.
- `generate_carousel_today.py:182-184` applies a defensive re-substitution for `{{CIRCLE_WORD_2}}` to work around a templating bug rather than fixing it.
- The poll question parser (`schedule_all_posts.cjs:203-211`) captures the literal prefix `"Question: "` as part of the question text sent to LinkedIn.

### 12.4 Summary of the state that must not break

Three artefacts carry all continuity in this system, and none of them is backed up or version-controlled:

1. **`pipeline_state.json`** — 2 fields, 87 bytes. The only thing preventing duplicate and past-dated posting.
2. **`used_topics.json`** — 76 strings. The only thing preventing topic repetition.
3. **`chrome-session/`** — the only LinkedIn credential, and a secret.

Everything else in the repo is either regenerable, archival, or dead.

---

*End of audit. No files were modified, created, deleted, moved or renamed except this report. No pipeline step, script, build or network call was executed. No credential values were read, printed or copied.*
