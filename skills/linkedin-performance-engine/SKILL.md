---
name: linkedin-performance-engine
description: Generates 5 LinkedIn posts modeled on @harshchouksey's OWN top-performing analytics — marketing/automation contrarian, loaded poll, AI-news-with-marketing-implications, story carousel, and data-visual-with-hook.
allowed-tools: WebFetch, WebSearch, Bash, Read, Write
---

# LinkedIn Performance Engine (Marketing & Automation Focus)

You generate the **5 report-driven posts** for the daily batch. Unlike the other engines, every archetype here is reverse-engineered from **@harshchouksey's actual LinkedIn analytics**. The brief is simple: do more of exactly what already worked on your account.

The five archetypes, in priority order:

1.  **Marketing & Automation Contrarian** (text) — Challenges comfortable myths about Meta Ads or business automation.
2.  **Loaded Poll** (text) — High-engagement interactive dilemmas (e.g. ad spend vs funnel design).
3.  **AI News + Business Implications** (text) — AI updates analyzed specifically for lead gen and conversions.
4.  **Story-based Carousel** (visual) — Real client case studies, ad/automation metrics, and swipeable workflows.
5.  **Data Visual + Hook** (visual) — One striking marketing/leads stat paired with a sharp practitioner interpretation.

---

## PHASE 0 — Bootstrap

### 0A: Load the content doctrine + voice profile

```bash
cat ./content-doctrine.md
cat ./voice-profile.md 2>/dev/null
cat ./commands/linkedin-content.md 2>/dev/null
```

**`content-doctrine.md` is the north star** — it sets the lane: Meta Ads, lead generation, funnels, n8n automation, and CRM workflows for D2C brands, coaches, and agencies.

Write in the declarative, observational `@harshchouksey` LinkedIn voice. Key formatting rules from `commands/linkedin-content.md` apply in full:
- **No em-dashes anywhere.**
- Banned vocabulary list applies in full.
- Banned LinkedIn patterns apply in full.
- Specific numbers over adjectives.

### 0B: Load deduplication state

```bash
cat ./linkedin_posts_$(date +%Y%m%d).txt 2>/dev/null
cat ./ai_news_posts_$(date +%Y%m%d).txt 2>/dev/null
cat ./performance-run-log.json 2>/dev/null || echo "[]"
cat ./infographic-run-log.json 2>/dev/null || echo "[]"
```

Avoid topic overlap. Make sure every post has a unique subject (16 unique subjects across the full daily batch).

---

## PHASE 1 — Select 5 distinct topics (MANDATORY before writing)

Pick one subject per archetype:

```
PERFORMANCE TOPIC SELECTION:
1. MARKETING CONTRARIAN    → [the romanticized belief being challenged] — angle: [one phrase]
2. LOADED POLL              → [the dilemma] — 4 emotionally-loaded options
3. AI NEWS + IMPLICATIONS   → [story] from [source] — business angle: [one phrase]
4. STORY CAROUSEL           → [case study / real numbers] — format: [HOW_THEY_DID_IT / DATA_STORY]
5. DATA VISUAL + HOOK       → [dataset] — format: [from illustration-formats]
```

**Zero-overlap check:**
- None of the 5 may share a subject with already written posts (16 unique subjects total).
- The contrarian belief must not be in the last 14 entries of `performance-run-log.json`. The poll topic must not be in the last 14 entries.

---

## PHASE 2 — Write the 5 posts

Apply all voice and formatting rules.

---

### Archetype 1 — Marketing & Automation Contrarian (text)
**Formula**: Challenge a widely-held marketing/automation belief → validate the reader's quiet frustration → end with a reframe + question.
**Structure**:
- Hook (3 to 8 words. A bold, declarative claim challenging a myth).
- The Belief (Name what everyone tells brands or agency owners).
- The Uncomfortable Truth (Why this belief fails in practice).
- Validation (Name the quiet frustration the reader feels).
- Reframe (What to do instead, backed by metrics).
- Question (A debate prompt).
- CTA: "Follow @harshchouksey for daily breakdowns on Meta Ads and automation." or "DM me 'SCALE' to build an automated growth engine."

---

### Archetype 2 — Loaded Poll (text)
**Formula**: State a hot-button business dilemma → ask "which one hits closest?" → make all four options emotionally loaded.
**Structure**:
- Setup (2 to 3 sentences framing a real ad scaling or automation dilemma).
- Poll Question (e.g. "Which ad bottleneck is killing your growth right now?").
- Option A, B, C, D (Genuinely felt, emotionally loaded positions).
- Closing line inviting comments.

---

### Archetype 3 — AI News + Implications (text)
**Formula**: State the news fact → give 2-3 concrete implications for ad spend, funnels, or operations → end with a debate question.
**Structure**:
- Hook (The news stated plainly. Under 120 characters).
- What Happened (1-2 sentences. No jargon).
- What it means for you (2-3 implications, using "•" bullet points).
- Debate Question.
- CTA to follow @harshchouksey.

---

### Archetype 4 — Story-based Carousel (visual)
**Build**: Reuse the existing **branded-carousel** skill.
1. Pick the format (e.g., `HOW_THEY_DID_IT` case study of a client campaign, ad creative test, or n8n workflow).
2. Run the branded-carousel engine (`./skills/branded-carousel/SKILL.md`) with a distinct output directory:
   - `CAROUSEL_DIR = ./carousel-routine`
   - Render to subdir `carousel-performance`
3. Write a caption following the carousel-caption rules, ending with a CTA pointing to `@harshchouksey` or `"DM 'SCALE'"`.

---

### Archetype 5 — Data Visual + Hook (visual)
**Build**: Reuse the existing **illustration-formats** skill.
1. Find one fresh marketing or workflow dataset (e.g., ad CPC benchmarks, n8n time savings).
2. Generate the HTML to `./linkedin-performance-infographic.html`.
3. Screenshot to `./linkedin-performance-infographic-$(date +%Y%m%d).png` at 1080×1080.
4. Write a caption where the hook is a striking stat and the body is a sharp interpretation.

---

## PHASE 3 — Self-check
Verify: no em-dashes, no banned vocabulary, correct CTAs, no topic overlaps.

---

## PHASE 4 — Output + save

Print all 5 posts in this format, then save to `./performance_posts_$(date +%Y%m%d).txt`:

```
═══════════════════════════════════════════════
LINKEDIN PERFORMANCE ENGINE — [DATE] (Meta Ads & Automation Focus)
═══════════════════════════════════════════════

━━━ PERF 1 — MARKETING CONTRARIAN ━━━
[full post text]
Belief challenged: [one line]

━━━ PERF 2 — LOADED POLL ━━━
[full post text with 4 options]
Dilemma: [one line]

━━━ PERF 3 — AI NEWS + IMPLICATIONS ━━━
[full post text]
Story: [one line] | Source: [url]

━━━ PERF 4 — STORY CAROUSEL ━━━
[caption text]
Carousel topic: [one line] | Format: [X] | Hook style: [X]
PDF: ./carousel-routine/output/[DATE]/carousel-performance/*.pdf

━━━ PERF 5 — DATA VISUAL + HOOK ━━━
[caption text]
Dataset: [one line] | Format: [X]
PNG: ./linkedin-performance-infographic-[DATE].png
═══════════════════════════════════════════════
```
