# PHASE-2-REPORT.md

Voice, marker format and carousel content. Applied 2026-08-09. Companion to [`PIPELINE-AUDIT.md`](PIPELINE-AUDIT.md), [`PHASE-0-REPORT.md`](PHASE-0-REPORT.md) and [`PHASE-1-REPORT.md`](PHASE-1-REPORT.md).

**Scope honoured:** `posts_per_batch`, `format_mix`, `time_slots`, the horizon and every Phase 0/1 guard are unchanged. `pipeline_state.json`, `used_topics.json` and `chrome-session/` untouched. The pipeline was never run against LinkedIn; Chrome was never opened. Five live generation runs were made against the OpenAI API in isolated scratch directories with their own `used_topics.json` copies.

**Baseline:** `5802a70` (end of Phase 1).

---

## ⚠️ Read this before the first live run

**The pipeline is not expected to produce a full batch in its current state, and that is by design.**

On the last measured run, **4 of 5 posts would abort** on the unverifiable-claims check. That number is not a defect and should not be tuned away. It is the checker reporting that ~80% of what this pipeline writes has nothing true behind it.

Told to write in first person with a concrete specific, and given a Reddit thread and nothing about Harsh's actual work, the model has two options: invent something, or produce nothing. Between those, producing nothing wins every time. A blocked batch costs one run and is visible. A fabricated client result publishes permanently — the `$60 MRR` carousel from the old fallback is still on the feed, which is the reason this standard exists.

**Phase 3 must supply real material** (`raw_notes.txt` currently holds only commented-out examples). Until it does, expect aborts.

---

## Task 1 — Marker format pinned

`generate_all_content.py`. The carousel and infographic prompts previously said only *"Format clearly labeled with … CAROUSEL CAPTION:"*, and the model emitted a bolded marker ~59% of the time.

Both prompts now carry an explicit MARKER FORMAT block showing the exact plain-text shape, with correct/wrong examples. The `Slide N:` markers were pinned too, not just the caption ones — slide 1's text becomes the LinkedIn document title, so leaving that family loose would have fixed half the problem.

**Normalisation on both consumers was kept.** 12 references in `schedule_all_posts.cjs`, 15 in `send_to_slack.py`. The prompt is the belt; the normalisers are the braces.

---

## Task 2 — Hard-coded carousel content removed

Full inventory taken before any change.

### Removed

| # | Was | Now |
|---|---|---|
| A1 | Slide 1 card: `⚡ 2026 AI BLUEPRINT` / `Autonomous AI Ops` on every carousel | `{{S1_CARD_LABEL}}` / `{{S1_CARD_TEXT}}` from the slide's own fields |
| A2 | Slide 6 card: `KEY TAKEAWAY` / `NATIVE AI OPERATING SYSTEM` / `Connect tools once · Automate 24/7` | `{{S6_CARD_*}}` from the slide's own fields |
| A3 | `THE LESSON` fixed label on slide 7 | `{{S7_LABEL}}`, the carousel's topic category |
| A4 | Fallback strings — a complete unrelated SaaS story | **Deleted.** Missing fields now abort |
| B1 | `color = "#5E6AD2"` hard-coded | `pipeline_config.json` → `brand_color` |

### A4 was the serious one

The fallbacks were a real story about someone else's business — *"5x MRR in seven days"*, *"A founder was stuck at $60 MRR for months… Revenue jumped to $300 MRR"* — rendered into a carousel published under Harsh's name whenever a field came through empty.

**All three archived carousels would have aborted under the new rule:** 1, 7 and 11 missing fields respectively — 19 empty fields across 19 slides. Carousel 2 shipped with the `$60 MRR` line as its slide 1 subtitle.

`require_slide_val()` collects every missing field and aborts naming slide and field. `generate_carousel_today.py` went from 188 to 96 lines.

### Kept deliberately

`SWIPE →`, `harsh chouksey / 2026`, the slide numbers, the fonts and the background are brand furniture and carry no topic claim.

### Not fixed — logged as the top Phase 3 item

**B6: the fixed layout.** Templates map 1→1, 2→2, 3→3, 4→2, 5→3, 6→6, 7→7 for *every* carousel. `FORMATS.md` documents six formats with a decision tree and **none is implemented**. A case study, a myth-buster and a listicle all render through the same seven-slide skeleton. This is the real "every carousel looks the same" problem. **B7:** two fixed Unsplash images are downloaded every run and discarded.

---

## Task 3 — Voice

### voice-profile.md is now live code

It is read at runtime and everything after `## RULES` is inserted into the system prompt. The hand-transcribed `writing_rules` string is deleted. Fails closed: missing file, no `## RULES` section, or a section under 200 characters all abort rather than generating with no voice constraints.

`content-doctrine.md` remains unread — out of scope, logged.

### The carousel-JSON prompt

The prompt already named **all 46 fields**; coverage was never the problem. Measured fill rates were 45/46, 39/46 and 36/46, and **17 of 18 failures were present-but-empty strings**, not missing keys. Added an explicit "every field is required, no empty strings" instruction plus a `FIELD RULES` block giving each field a job, a length and a good/bad example. Safety net: validate, retry once **naming the exact empty fields**, then abort. Never saves a partial.

### Evidence for the rules

**No per-post engagement data exists in the repo** (audit §7.4), so "worst-performing" could not be isolated. With ~half of 65 posts at zero engagement and 2 outperformers, all 66 archived posts were treated as the underperforming corpus.

| Phrasing | Posts | | Phrasing | Posts |
|---|---|---|---|---|
| "curious" | 12 (18%) | | "not just / isn't just" | 8 (12%) |
| "seamless" | 9 (13%) | | "let's dive/explore/unpack" | 5 (7%) |
| "here's the/how" | 7 (10%) | | "elevate", "dive into", "transform*" | 4 each |

Rhetorical-question openings: **12 of 66 (18%)**.

**The finding that shaped everything: 9 of 17 already-banned words still appeared.** The existing ~70-word list was not being followed.

---

## Task 4 — Hook mapping

Style was fixed by slot. Measured what each produced:

| Style | n | Question-form hooks |
|---|---|---|
| Curiosity Gap | 4 | **3 (75%)** |
| Case Study | 4 | **3 (75%)** |
| Tool Spotlight | 4 | **3 (75%)** |
| Specific Result | 4 | 0 |
| Myth Buster | 4 | 0 |
| Hot Take | 4 | 1 (25%) |

Three of six styles were structurally biased toward the opening the new rules ban.

| Slot | Was | Now |
|---|---|---|
| CAROUSEL 1 | Curiosity Gap | **Myth Buster** |
| TEXT 1 | Case Study | **Build Note** |
| CAROUSEL 2 | Specific Result | **Benchmark Check** |
| TEXT 2 | Tool Spotlight | **Hot Take** |
| TEXT 3 | Hot Take | **Teardown** |

`Specific Result` was replaced because its *name* instructed the model to produce a number, and it generated `$200K sales` and `35% boost` with no source. `Benchmark Check` requires a figure from outside Harsh's own unverifiable claims.

---

## Task 5 — Five live runs, and what they proved

| Run | Change under test | Outcome |
|---|---|---|
| 1 | New rules, prompt-only | Banned words in 4/5 posts; a fabricated source shipped; topics echoed template strings |
| 2 | Ban list enforced in code, whole-post retry | Aborted. The rewrite removed `journey` and introduced `Curious` |
| 3 | Tier 1/2 split, sentence-level repair | Batch completed. **3 of 4 repairs were synonym swaps** |
| 4 | `robust` demoted | Batch completed. `game changer` unhyphenated and `4:1` both slipped |
| 5 | Vocabulary demoted to advisory, repair removed | Batch completed, carousels filled first-time. **8 fabricated claims across 3 of 5 posts** |

### The lesson

**Grammatical and structural constraints bound. Word lists did not — at 70 items, at 33, and at 10.**

Declarative hooks: 5/5 on every run. Carousel field validation: works. Figure sourcing: works. Vocabulary enforcement: three attempts, three failures of a different kind each time.

**Run 3 was decisive.** The sentence-level repair produced `seamlessly` → `effortlessly` (a disguise, not an improvement) and, on the figure check, deleted `₹10,000/day → ₹70,000/week` — the clearest worked example in the batch — because deleting satisfies the checker and marking it hypothetical takes effort. **Every checker creates the same incentive: the cheapest way to pass is to say less.**

So the instruments were re-sorted by what they are actually for.

---

## The final split

### Hard — enforced in code, aborts, no repair, no retry

| Check | Rationale |
|---|---|
| **Unverifiable first-person claims** | `I recently helped`, `we found that`, `our client`, `I've seen`, `this approach boosted`, and the same family. Nothing in the pipeline knows whether these are true |
| **Sources outside the allowlist** | WordStream/LocaliQ, Databox, Triple Whale, Meta newsroom / Meta for Business, Statista. A username, subreddit or forum handle is never a source |
| **Figures** | Must carry an allowlisted source **and** a year in the same sentence, or open with a literal hypothetical marker (`Say you're`, `Imagine a`, `Take a brand`, `Suppose`) |
| **Carousel field completeness** | Validate, one retry naming the empty fields, then abort |
| **External links** | None in the post body |

These stop the pipeline publishing something that would have to be answered for. That is worth a failed batch.

### Advisory — logged, quoted in Slack, never blocking

The entire vocabulary list (34 terms) and mid-body rhetorical questions. Written to `review_flags.json` and shown in the Slack review header with the offending line quoted, so judgement sits with a human rather than a regex.

### Removed

The sentence-level repair, in full.

---

## Measured abort rate

Against run 5's output, with the claims checker active:

| Post | Verdict |
|---|---|
| 1. CAROUSEL 1 | passes |
| 2. TEXT 1 | **aborts** — 4 claims (`I recently helped a D2C client…`) |
| 3. CAROUSEL 2 | **aborts** — `'WizardOfEcommerce' Reddit post` cited as a source |
| 4. TEXT 2 | **aborts** — 3 claims (`I've seen how…`, `when we tightened…`) |
| 5. TEXT 3 | **aborts** — 1 claim (`I recently took on…`) |

**4 of 5. Batch completion probability ≈ 0.**

False-positive checks pass: mechanism descriptions, marked hypotheticals and allowlisted citations are all clean.

---

## Carried into Phase 3

| # | Item |
|---|---|
| **1** | **Supply real material.** `raw_notes.txt` holds only commented-out examples, yet the planner treats it as highest priority. This is the blocker for every abort above |
| **2** | **B6 — carousel layout is fixed.** Six formats documented, none implemented. Every carousel renders identically |
| 3 | B7 — two Unsplash images downloaded and discarded every run |
| 4 | `content-doctrine.md` still unread by the pipeline |
| 5 | Advisory list has boundary gaps by design (`leveraging` does not match `leverage`). Not worth chasing — that race does not end |
| 6 | Everything still open from the Phase 1 register, including the test-run watermark trap (item 27) and the stale watermark |

---

## Rollback

```bash
git reset --hard 5802a70
```

To keep the structural work and drop only the voice rules, edit `voice-profile.md` — it is the live source, and changing it changes behaviour without touching code.
