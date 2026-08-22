# PHASE-3-REPORT.md

Pillar rotation and real content sources. Applied 2026-08-13. Companion to [`PIPELINE-AUDIT.md`](PIPELINE-AUDIT.md), [`PHASE-0-REPORT.md`](PHASE-0-REPORT.md), [`PHASE-1-REPORT.md`](PHASE-1-REPORT.md) and [`PHASE-2-REPORT.md`](PHASE-2-REPORT.md).

**Scope honoured:** `posts_per_batch`, `format_mix`, `time_slots`, the horizon and every Phase 0/1 guard are unchanged. `pipeline_state.json`, `used_topics.json` and `chrome-session/` untouched. The pipeline was never run against LinkedIn; Chrome was never opened. Generation ran live against the OpenAI API in isolated scratch directories.

**Baseline:** `66be8d1` (end of Phase 2).

---

## ✅ State on commit: the dry run completed, 5/5 on first attempt

The full five-pillar batch generated end to end for the first time since Phase 2
introduced the hard checks. **No post was rejected.** Two defects were found by
reading the output, not by the checkers, and both were fixed before this commit.

| Day | Pillar | Format | Source |
|---|---|---|---|
| Mon | `ad-teardown` | carousel | Meta Ad Library (`ad_1020562504191672.json`) |
| Tue | `benchmark` | text | WordStream 2017 (`wordstream-fb-cvr-all-industries`) |
| Wed | `build-note` | carousel | `raw_notes.toml` (`seed-whatsapp-agronomist`) |
| Thu | `community-question` | text | r/PPC, paraphrased as a question |
| Fri | `update-or-hot-take` | text | n8n changelog, dated 2026-08-12 |

---

## Task 1 — raw_notes as a first-class input

**`raw_notes.toml`** holds twelve real projects. TOML via stdlib `tomllib`, so malformed input fails with a parser error and a line number rather than being silently skipped.

```
✓ 12 projects, 0 example blocks, 2 theses
✓ 35 angles — text 35, carousel 21
✓ detail length: min 132, median 211, max 310
```

**35 angles at one Build Note per week is roughly 35 weeks before any reuse.**

Validation aborts and names the project on: TOML syntax errors, missing required fields, duplicate project or angle ids, `detail` under 40 chars, `formats` not a list, and a `thesis` referencing an undeclared id.

**Thesis handling.** Six of the twelve share *lead-quality-over-volume*. The original proposal was to use a thesis once; the implemented design rate-limits it instead (`thesis_cooldown = 4`). A position is built by restating it with different evidence and destroyed by restating it with none. 25 of 35 angles are untagged, so the cooldown rarely binds.

Rotation state lives in a **new** `used_angles.json`. `used_topics.json` is untouched.

---

## Provenance — the change that made real material usable

Phase 2's claims checker blocked `I recently helped`, `we designed`, `our client` — exactly the sentences a real build note is made of. It had no way to tell *invented because it had nothing* from *true because Harsh wrote it down*, so it rejected both.

It is now given the attested details for the angle being written, and a first-person claim passes only if it stays close to one. **Unattested claims still fail.** This makes the checker stricter, not looser: it now also rejects embellishment of attested material.

### Threshold: calibrated, not relaxed

| | Value |
|---|---|
| **Old** | `CLAIM_ANCHOR_RATIO = 0.60` |
| **New** | `CLAIM_ANCHOR_RATIO = 0.30` |

0.60 was a guess, tuned against near-verbatim text I wrote myself. Real generation paraphrases, so it produced **false positives on claims that were genuinely attested**. Measured against real `raw_notes` material:

```
invented claims (from Phase 2 runs) : 0.00 – 0.17
true claims traceable to the notes  : 0.40 – 1.00
```

A clean gap. 0.30 sits in the middle with margin either side. Verified after the change: faithful paraphrase passes, `We deployed a system that tripled our client bookings overnight` still fails, `I recently helped a D2C client…` still fails.

**A finding worth recording:** my first provenance test was invalid and I nearly reported it as a pass. Two cases "passed" not because provenance worked but because `We shipped` was not in `CLAIM_PATTERNS` at all. Eight verbs were missing (`shipped`, `deployed`, `launched`, `rolled out`, `connected`, `automated`, `replaced`, `fixed`). Added, test rewritten, 6/6.

---

## Task 2 — Pillar rotation

| Day | Pillar | Source |
|---|---|---|
| Mon | ad-teardown | Meta Ad Library, via your `adspy` |
| Tue | benchmark | allowlisted publishers, manual |
| Wed | build-note | `raw_notes.toml` |
| Thu | community-question | Reddit, as questions |
| Fri | update-or-hot-take | official changelogs |

In `pipeline_config.json` with startup assertions: `len(pillars)` must equal `posts_per_batch`, every `source` must be one the resolver knows, and every entry needs `day`/`id`/`source`.

**Pillar and format are independent axes.** A pillar says *where the material comes from*; the format still comes from `format_mix`. Every source item declares which `formats` it can carry, the resolver matches the slot's format, and a pillar with nothing that fits **aborts naming the pillar and the format**. It never swaps to another pillar — a silent swap would be the "whatever surfaced today" behaviour this phase removes.

**The planning LLM call is gone.** Topics are built in code from what the sources returned, so there is nothing to invent at the topic stage. Live run topics: a real Flipkart ad, the agronomist bot's looping problem, a real r/PPC question, n8n 2.34.5.

---

## Task 3 — Reddit repurposed

Three defects fixed:

| Was | Now |
|---|---|
| Only the first 20 of ~80 items reached the planner | No truncation; the selector filters, the fetcher does not |
| Per-subreddit failures silent — 6 of 10 returned nothing and it exited 0 | Failures counted and named; aborts below `reddit_min_items` |
| `ups: 100`, `num_comments: 10` written as constants for every item | **`null`**, with `"engagement_note": "not available via RSS - do not weigh"` |

**On the constants:** RSS genuinely does not expose score or comment count. Rather than substitute a number, the fields are null and say why. Any downstream logic that looked like it weighed engagement was weighing a constant.

Selection is now questions — title ends in `?` or opens with an interrogative.

**Subreddit list (config):** `PPC`, `facebookads`, `EntrepreneurRideAlong`, `IndianStartups`, `smallbusiness` — as specified. The old list was 10 practitioner-heavy subs, which is where the 18% IT services / 15% advertising / 4% founders audience came from.

**Rate limiting.** First run: 3/5 subs, `r/facebookads` and `r/IndianStartups` 429-ed. Fixed with a browser-shaped user-agent, `reddit_delay_seconds = 8` between subs, and a real 429 backoff (30s/60s/90s instead of 4s). Result: **5/5 subreddits, 125 items, 51 questions**.

**On volume:** the pillar consumes exactly **one** question per run. Fetching 150 to use 1 while getting rate-limited was the wrong trade, so `reddit_per_sub_limit` dropped 50 → 25. 51 questions is still far more than needed; it is headroom for the de-duplication to have choices, not waste.

Posts never quote the asker, never name them, never cite a username — and the source now also forbids reproducing **the asker's own figures**, which blocked a run when a post echoed a stranger's `$2k/month budget`.

---

## Task 4 — Stale news removed, dated sources added

`ai_news_data.json` was stale since 2026-07-25 and still fed to the planner labelled "Fresh AI & Marketing News". **Removed from the planner entirely.**

`fetch_changelogs.py`:
- **n8n** — GitHub's public releases API. Real JSON, real `published_at`. 10 dated releases fetched, all within the window.
- **Meta newsroom / WhatsApp Cloud API** — manual, in `sources/changelog_manual.toml`. Neither publishes a stable machine-readable feed. Scraping them is not worth the surface, and inventing a date is worse than having none.

**Freshness window: `source_max_age_days = 14`.** Two weeks is the point where a platform changelog stops being an update. Items with no date at all are refused outright, and the refusal is logged.

---

## Task 5 — The two pillars that needed design

### Ad teardown — feeds from your own `adspy`

`adspy` already does exactly this: `POST /api/extract` returns normalised ad JSON, and `scoring.py` adds `days_running`, `stage`, `why_it_works`, `watch_outs`, `verdict`. Verified on a real fixture: **Flipkart, 34 days, Strong Performer**.

The pipeline reads a **drop directory**, `sources/ad_teardowns/*.json`. It does **not** drive Ad Library itself — it shares a Chrome session with LinkedIn and no scraping surface was added.

```bash
curl -s -X POST http://localhost:8000/api/extract \
  -H 'Content-Type: application/json' \
  -d '{"url":"<meta ad library url>"}' \
  > sources/ad_teardowns/<name>.json
```

**Allowlist addition (approved):** `Meta Ad Library` added to `ALLOWED_SOURCES`, because the pillar cannot state how long an ad has run without it. Public and checkable — anyone can open the ad. Scoped to what Meta actually publishes: **days running and active status**. Meta publishes no spend, impressions or ROAS for commercial ads, and the source material says so explicitly, so a post claiming reach "from the Ad Library" would be a fabrication wearing a real source's name.

### Benchmark — manual, and that is the honest answer

None of the allowlisted publishers offers a stable machine-readable feed. A fabricated-but-cited source is worse than no figure — Phase 2 already caught `Socialbakers 2026`, which may not exist. So figures are pasted by hand and the loader refuses any source not on the allowlist.

**The pillar aborts until you supply one. It was not seeded with a placeholder.**

Required shape in `sources/benchmarks.toml` — every field required:

```toml
[[benchmark]]
id      = "wordstream-cpl-home-services-2026"   # unique, stable
source  = "WordStream"        # must appear in allowed_sources at the top of the file
year    = 2026                # integer
figure  = "9.2%"              # exactly as it should appear in the post
metric  = "median Facebook Ads conversion rate, home services"
context = """
What this means for the reader and what to change because of it.
"""
formats = ["text", "carousel"]
used    = false               # set true once posted, so it is not reused
```

`allowed_sources` at the top of the file: WordStream, LocaliQ, Databox, Triple Whale, Meta newsroom, Meta for Business, Statista, Meta Ad Library.

---

## `ATTRIB_RE` — false-positive fix

```python
# BEFORE — matched the phrase alone, case-insensitively.
# "based on the nuanced information provided" was flagged as citing a source.
ATTRIB_RE = re.compile(
    r"\b(?:according to|based on the|as reported by|cited by|source:|study by|survey by|research by)\b",
    re.I)

# AFTER — requires a proper-noun-shaped source after the phrase.
# Deliberately NOT re.I: the capital letter is the signal a source is named.
ATTRIB_RE = re.compile(
    r"\b(?:[Aa]ccording to|[Bb]ased on|[Aa]s reported by|[Cc]ited by|[Ss]ource:"
    r"|[Ss]tudy by|[Ss]urvey by|[Rr]esearch by|[Pp]er)\s+"
    r"(?:the\s+)?[\"'‘“]?"
    r"([A-Z][A-Za-z0-9&.\-]*(?:\s+[A-Z][A-Za-z0-9&.\-]*)*)")
```

7/7 on test, including both required cases:

| Sentence | Result |
|---|---|
| `…how to reply based on the nuanced information provided by the farmer.` | **passes** (was a false positive) |
| `Based on the 'WizardOfEcommerce' Reddit post in 2023…` | **still fails** |
| `According to Socialbakers 2026, 85% of top ads are videos.` | still fails |
| `According to Statista 2025, 40% of D2C spend goes to Meta.` | passes |
| `I sorted the leads based on the budget they gave us.` | passes |

---

## Task 6 — Dry run, honestly

Four consecutive live runs, each stopped by a different leak. **No fabrication ever reached output.**

| Run | Blocked on | Nature |
|---|---|---|
| 1 | `34 days live` | real leak — no source in the sentence |
| 2 | `up to 80% off` | the **advertiser's own** ad copy |
| 3 | `$2k/month budget` | the **Reddit asker's** number |
| 4 | `based on the nuanced information` | **false positive** in `ATTRIB_RE` |

Runs 1–3 were fixed at the **source**, by instructing each loader what construction satisfies the checkers — never by loosening a checker. Run 4 was a genuine defect in my Phase 2 regex.

**On the run before last, posts 1 and 2 passed every hard check.** That is the first time since Phase 2 that any post has cleared them.

Rejected drafts are now written to `rejected_posts/` for inspection. They are never saved to `linkedin_posts_today.txt` and can never be scheduled — the scheduler only ever reads that file.

**Not done:** a complete 5-post batch. Tuesday needs a benchmark figure; the other four have material and the machinery resolves all four.

---

## Two defects the checkers did not catch

Both were found by reading the generated batch. Neither was a checker weakening.

### 1. The carousel hook was a literal instruction string

`generate_all_content.py` set `slide_1_hook` to the constant
`"A declarative statement, 6-8 words, never a question"`, fed it to the model as
if it were a real hook, then wrote it into the post as the `Hook:` line. The
scheduler types that line as the **LinkedIn document title** — the largest text
on a published carousel. Both carousels in the previous run carried it.

This was introduced in Phase 3 itself, when the pillar-driven plan replaced the
planning LLM call that used to write a real hook.

**Fix:** the hook is now read back out of the model's actual `Slide 1:` line,
which is what the hook always was. If a carousel has no readable slide 1, the
batch aborts rather than publishing an untitled or placeholder-titled document.
The extractor strips markdown emphasis *before* testing for content — `**Slide
1:**` leaves a bare `**`, the same defect class that published a literal `**` on
six live carousels in Phase 0b.

Titles produced after the fix: `Flipkart Ad Strategy: Consistent Longitudinal
Success` and `A bot must not push products hard`.

### 2. The claims checker had a first-person-history gap

This sentence passed every hard check:

> "We realized the need for this when our previous configurations ran into TLS
> inconsistencies, causing delays and errors in automated processes."

Nothing in the source material said any of that. `CLAIM_PATTERNS` covered
`we found`/`we observed` but not `we realized`, `in our setup`, or `our previous
X`. Three patterns were **added** — the checker was widened, not relaxed.

Verified against the attested build-note sentences so it does not fire on
material that genuinely came from `raw_notes.toml`: `I built a WhatsApp
automation on n8n`, `We moved the reasoning steps out of the model`, and `The bot
got stuck in loops` all still pass.

---

## What the hard checks still do not cover

The batch passes every check and still breaks three rules that `voice-profile.md`
states as absolute. These are **stated but unenforced**:

| Rule | Status | Evidence in this batch |
|---|---|---|
| 8 — no em-dashes | not enforced anywhere | 3 occurrences |
| 7 — banned constructions | only `it's not just X, it's Y` is detected, and only as an advisory | *"This isn't just a minor fix—it's a game-changer"* |
| 2 — every post needs one concrete specific | not enforced | post 4 (`community-question`) is entirely general advice, no first-person detail |

Two further judgement issues worth a human's eye, neither mechanical:

- **Post 1** turned `why_it_works` from the adspy scoring output — *"Body copy 202
  chars, in the 80-300 range that converts on Meta"* — into *"the sweet spot that
  **research shows** converts on Meta."* The figure is real (the ad body is
  exactly 202 characters), but a scoring heuristic was promoted to cited
  research. Also *"Meta Ad Library 2026 recognizes its longevity and
  effectiveness"* — the Ad Library reports neither.
- **Post 4** is the weakest of the five. `community-question` supplies a question
  but no material of Harsh's own, so the model has nothing specific to write
  from. That is a pillar design limit, not a checker failure.

Whether rules 2, 7 and 8 get hard enforcement is a live decision, not an
oversight: Phase 2 deliberately **demoted** word-level enforcement to advisory
after measuring that it only made the model swap synonyms. Em-dashes and fixed
constructions are punctuation and syntax rather than word choice, so they would
not behave the same way — but reversing that call is yours.

---

## Benchmark figures are 2017 and need replacing

`sources/benchmarks.toml` holds two WordStream figures (9.21% median conversion
rate, $1.72 median CPC), both from a sample of 256 US accounts advertising
between **November 2016 and January 2017**. The publisher's page header shows a
2026 "Last Updated" date; that refers to the article, not the sample. The `year`
field records **when the data was gathered**.

The loader now passes the age of the figure and the sample period into the
prompt, forbids presenting it as current, and requires the source and year in the
**same sentence** as the figure. Result: the post led with *"Most marketers
quoting the benchmark for Facebook Ads are using data from nearly a decade ago"*
and named the sample in full.

**Follow-up:** replace both with fresher figures when the current report is
pulled. Until then Tuesday knowingly runs on a 2017 number, framed as historical.

---

## Phase 3d — the generator now says which provider it calls

The audit flagged this and it stayed unfixed through three phases. It has now
cost debugging time twice, most recently sending Harsh to check a Gemini quota
over an OpenAI billing error.

**Confirmed by inspection and a live probe, before renaming anything:**

| | |
|---|---|
| Endpoint | `https://api.openai.com/v1/chat/completions` |
| Model string sent | `gpt-4o` |
| Key variable | `OPENAI_API_KEY` (value never printed) |
| 429 provenance | `x-request-id: req_4d00…`, `server: cloudflare`, `error.type: insufficient_quota`, `error.code: credit_balance_exhausted` — from `api.openai.com`, not Google |

No Google endpoint is reachable from this path. `generativelanguage.googleapis.com`
appears only in `aigen_image.py` and `generate_posts_via_openrouter.py`, both
dormant: `GEMINI_API_KEY` is absent from `.env`, as the audit recorded.

**Renamed:**

- `generate_all_content_gemini.py` → `generate_all_content.py` (via `git mv`, history preserved)
- `call_gemini()` → `call_llm()`
- Three error strings saying "OpenRouter" → "OpenAI"
- A file header now states the endpoint, model and key variable outright

Every reference updated in the same pass: `run_pipeline.py`, `send_to_slack.py`,
`sources_loader.py`, `schedule_all_posts.cjs`, `pipeline_config.json`,
`voice-profile.md`, `PIPELINE-AUDIT.md` and all four phase reports. A repo-wide
grep for the old symbols returns only the two lines in the new file's header
that record what it used to be called.

The two audit findings about the misleading naming were rewritten rather than
left in place: a blanket replace had made them assert that the *correct* names
were misleading. They now read as historical findings marked resolved.

Verified after the rename: `run_pipeline.py` invokes the new filename, the
scheduler's empty-batch message names it, and the generator runs through pillar
resolution to the same billing failure as before. Behaviour is unchanged.

---

## Phase 3e — provider is configuration, and the name is provider-neutral

**Provider switched to Mesh, verified before anything was changed.** A live
probe against `https://api.meshapi.ai/v1/chat/completions` with `openai/gpt-4o`
returned HTTP 200 with `choices[0].message.content` and `usage` carrying
`prompt_tokens` / `completion_tokens`. The shape is standard OpenAI, so the
parsing genuinely needed no change. Model echoed back: `gpt-4o-2024-08-06`.

`gpt-4o` is kept deliberately. Every prompt here was tuned against it over
roughly 19 runs; changing provider and model together would make a failed dry
run uninterpretable.

**Provider lives in `pipeline_config.json`, not in code:**

```json
"llm": { "base_url": "https://api.meshapi.ai/v1",
         "model": "openai/gpt-4o", "api_key_env": "MESH_API_KEY" }
```

`config_loader.py` validates all three, requires `https`, rejects a `base_url`
that already ends in `/chat/completions`, and rejects whitespace in the key
variable name. Only the variable NAME is in config; the key value is never
loaded into config, so nothing that dumps `cfg` can leak it.

**Renamed again, provider-neutral.** `generate_all_content_openai.py` →
`generate_all_content.py`, `call_openai()` → `call_llm()`. The file header now
records the full naming history (Gemini → OpenAI → neutral) so the mistake
cannot recur. Every reference updated across code and all five documents.

**Error taxonomy, with layer attribution.** With a proxy in the path a 4xx can
come from Mesh or be relayed from the provider behind it. Mesh's own errors are
flat `{code, message}`; a relayed provider error carries provider-shaped fields
(an OpenAI-style `type`, or a nested `error`/`provider_error`/`upstream`).
Measured against six envelopes:

| Case | Attributed to | Retried |
|---|---|---|
| Mesh `unauthorized` (401) | Mesh | no — fatal |
| Mesh `model_not_found` (404) | Mesh | no — fatal |
| Upstream `insufficient_quota` (429) | upstream provider | no — fatal |
| Upstream `rate_limit_exceeded` nested (502) | upstream provider | yes |
| Mesh `rate_limited` (429) | Mesh | yes |
| Mesh `service_unavailable` (503) | Mesh | yes |

A missing key exits in 0 seconds with no request. A rejected key is fatal on the
first response. `request_id` is printed whenever Mesh supplies one.

**TLS verification restored.** The request context was
`check_hostname = False` / `verify_mode = CERT_NONE`, which disabled certificate
verification on the connection that carries the API key. With a proxy in the
path that is worse, not better: the key is presented to whatever answers the
hostname. Now a default verified context.

**`OPENAI_API_KEY` removed from `.env`** only after a full batch generated
through Mesh. `.env` backed up to `state-backups/` first (gitignored); the
removal asserted that exactly one line matched and that `MESH_API_KEY` survived.

---

## Phase 3f — four fixes, and a fifth that measurement rejected

**1. The voice profile was publishing itself.** Post 4 of the Mesh batch opened
with the literal `Good:` example under rule 3. Fixed on both halves you named:

- `voice-profile.md` now opens its RULES with a block stating that every
  `Good:`/`Bad:` line is illustrative only, that its wording may never be
  reused, and that the claims inside the examples (auditing many accounts, a
  4-node workflow in use) are invented for the example and NOT true of you.
- `find_profile_echoes()` parses the examples straight out of the file and
  rejects any post containing one. 12 examples parsed. Deterministic substring
  match on normalised text, anchored to each `Good:`/`Bad:` marker — the first
  version scanned the whole file for quoted spans and mis-paired quotes across
  unrelated prose, dragging in table text.

Verified: the exact leak is blocked, the `'CAPI'` example is blocked, a
paraphrase of the same idea passes, and real post text passes.

**2. Invented hands-on experience.** Added `navigated`, `tried`, `trialled`,
`adopted`, `applied`, `upgraded`, `patched`, `integrated`, `configured`,
`switched`, `rolled`, plus `saw/seen/experienced firsthand` and `in my own
workflows`. The changelog pillar's material now states outright that you have
not used the release, and shows the difference between an opinion ("I think
this matters because…", which is welcome) and a claim to have run it. The Mesh
batch's post 5 now reads *"I think this matters because when your requests pass
through more than one proxy…"* — opinion, no fabricated usage.

**3. A rejected post no longer kills the batch.** Same treatment as an
unavailable pillar: the draft is rejected exactly as before, written to
`rejected_posts/`, and the run continues. No retry, no checker relaxed. Also:

- The saved count is now real (`3 of 5 Main Posts saved`), not the attempted count.
- A rejected post's topic and angle are **not** burned — only `saved_ids` are recorded.
- A missing `Slide 1:` is now a per-post rejection rather than a batch abort.
- If every post is rejected the run stops before writing anything, so the
  scheduler is never handed an empty batch file.
- `send_to_slack.py` leads with the rejected posts and their reasons.

Proven in run 4: 3 saved, 2 rejected, batch survived, `+3` topics recorded.

**4. build-note ownership and the label skeleton.** The `PROBLEM:` / `BUILT:`
labels came from the material's own field names, which the model echoed as slide
labels. Fields renamed to prose, with an explicit instruction that they are
notes and not a slide template. Added a block stating that the client's
distributors, dealers, customers and sales team are theirs, not yours, and that
you are the person who built the thing. Post 3 now opens *"The client's
distributor faced a challenge…"* and slides read as consecutive thoughts.

### The fifth issue, and why the fix was reverted

Run 5 rejected post 3 on `"I built"` — on the one pillar where that is true by
construction. The draft said *"I built a solution using n8n"*, which scored 0.20
against attested notes containing "building" and "automation": a real false
positive caused by exact-token matching.

Crude suffix stemming looked like the fix. Measured, it was worse:

| | before | after stemming |
|---|---|---|
| the target sentence (should pass) | 0.20 | **0.20 — not rescued** |
| "In our testing, response times improved dramatically" (invented) | below | **0.38 — now passes** |
| "Clients consistently tell me this is the best…" (invented) | below | **0.33 — now passes** |

It failed to fix the case it was written for and let two invented claims
through, so it was reverted and the reasoning left in the source. The actual
defect was in the draft: *"a solution"* names nothing. The build-note pillar now
requires you to name what was built and the stack. Post 3 says *"I built a
WhatsApp automation on n8n"* — 0.60 attested, and better writing.

### One checker correction

`find_bad_sources` rejected *"CPL was impressive, according to Ads Manager"*.
`raw_notes.toml:439` says *"Ads Manager was telling me the campaign was
working"* — your own tooling, in your own notes. The allowlist exists to stop a
FIGURE being hung on an uncheckable publisher, not to stop you describing your
own dashboard. It now permits a named source only when the name appears in the
attested material AND the sentence carries no figure. With a figure, rule 4b
applies in full. Verified: the false positive passes, `"According to Ads
Manager, the conversion rate was 9.4%"` is still blocked, and Socialbakers,
Hootsuite and the Reddit-handle case are all still blocked.

### Final dry run: 5 of 5 saved, none rejected on first attempt

Advisory flags only: `Curious`/`curious` wording on posts 3 and 5, one mid-body
question each on 1, 3 and 4.

**Defects the checkers still miss**, unfixed and reported:

- **`"We revampied creatives"`** in post 4. A typo; nothing checks spelling.
- **`"34-day-running"` evades the figure check.** `"It has been running 34
  days"` requires a citation; the hyphenated compound does not match, so post
  1's caption states the figure with the Ad Library named but no year. It is
  cited and true, so it is not a fabrication, but the check is inconsistent.
- **Weak CTAs.** Post 1's *"What would you tweak? Share your thoughts!"* and
  post 2's *"DM me if you're interested"* both break rule 11's specific-ask
  requirement, which is advisory only.

---

## Carried into Phase 4

| # | Item |
|---|---|
| **1** | **Supply one benchmark figure** to `sources/benchmarks.toml`. Tuesday cannot run without it |
| **2** | **B6 — carousel layout is fixed.** Six formats documented in `FORMATS.md`, none implemented. Explicitly out of scope for Phase 3 |
| 3 | Re-run the dry run end to end after the benchmark lands; the batch has never completed |
| 4 | `content-doctrine.md` still unread by the pipeline |
| 5 | B7 — two Unsplash images downloaded and discarded every run |
| 6 | Everything open from the Phase 1 register, including the test-run watermark trap (item 27) and the stale watermark — **the pipeline still has never run live** |
| 7 | Advisory vocabulary has boundary gaps by design (`leveraging` ≠ `leverage`). Not worth chasing |

---

## Rollback

```bash
git reset --hard 66be8d1
```

To keep the machinery and change only what it writes from, edit `raw_notes.toml`, `sources/benchmarks.toml` or `pipeline_config.json` — all three are live inputs and none requires a code change.
