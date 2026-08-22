# linkedin-content

Fetches trending marketing and automation content from Reddit, finds shareable visuals, researches data for an infographic, and generates ready-to-publish LinkedIn posts. Output is posts only — no preamble, no explanations, no extra words.

---

## STEP 0 — Load the content doctrine (do this first)

```bash
cat ./content-doctrine.md
```

`content-doctrine.md` is the north star and overrides any older topic guidance in this file. Two hard rules before you pick anything:
- **The DROP list is banned.** No general tech/VC news with no marketing/automation utility, developer-only coding syntax, or generic startup advice.
- **Every topic must pass the 4-part topic filter** (Reach, Stakes, Altitude, Edge). We write for ambitious business owners (D2C brands, startups, agencies, and coaches) looking to scale traffic (Meta Ads) and automate operations (n8n, CRM, WhatsApp).

---

## STEP 1 — Fetch Reddit content via Apify (primary source)

Run this Bash command:

```bash
curl -s -X POST \
  "https://api.apify.com/v2/acts/trudax~reddit-scraper-lite/run-sync-get-dataset-items?token=YOUR_APIFY_API_KEY&timeout=120&memory=1024" \
  -H "Content-Type: application/json" \
  -d '{
    "startUrls": [
      {"url": "https://www.reddit.com/r/artificial/top/?t=week"},
      {"url": "https://www.reddit.com/r/ChatGPT/top/?t=week"},
      {"url": "https://www.reddit.com/r/singularity/top/?t=week"},
      {"url": "https://www.reddit.com/r/Futurology/top/?t=week"},
      {"url": "https://www.reddit.com/r/technology/top/?t=week"},
      {"url": "https://www.reddit.com/r/OpenAI/top/?t=week"}
    ],
    "maxItems": 80
  }'
```

If Apify returns an error, fall back immediately to these free Reddit JSON endpoints:
- https://www.reddit.com/r/artificial/top.json?limit=25&t=week&raw_json=1
- https://www.reddit.com/r/ChatGPT/top.json?limit=25&t=week&raw_json=1
- https://www.reddit.com/r/singularity/top.json?limit=25&t=week&raw_json=1
- https://www.reddit.com/r/Futurology/top.json?limit=20&t=week&raw_json=1
- https://www.reddit.com/r/technology/top.json?limit=20&t=week&raw_json=1
- https://www.reddit.com/r/OpenAI/top.json?limit=20&t=week&raw_json=1

---

## STEP 2 — Find a shareable image

Scan all fetched Reddit posts for one that contains a high-quality image. Prioritise images that are:
- Funnel diagrams, flowcharts, or workflow visualizations (e.g. n8n layouts)
- Screenshots of ad account dashboards, revenue growth, or CPL reductions
- Infographics with clear advertising or lead generation data

If no strong image is found on Reddit, use WebSearch to find one recent, shareable visual in the performance marketing or automation niche.

---

## STEP 3 — Research data for the infographic

Use WebSearch to find ONE concrete ranked dataset published or updated in 2025 or 2026. Target datasets with 6 to 10 comparable categories and specific numbers. Good targets:
- Meta Ads CPC or CTR benchmarks by industry
- n8n workflow automation time/cost savings for service businesses
- Lead generation funnel conversion rates across real estate, finance, or coaching
- WhatsApp open rates and conversions compared to email and SMS
- E-commerce customer acquisition costs (CAC) by ad platform

---

## STEP 4 — Select source material for each post type

From all gathered content, pick the single best match for each. **Every post type must use a different source thread or topic, and every one must pass the content-doctrine topic filter (Reach, Stakes, Altitude, Edge).** Reframe each around traffic scale, funnel optimization, n8n automation, or WhatsApp CRM systems.

- **COLLABORATIVE ARTICLE**: A critical take on how businesses fail at scaling paid traffic or operation automation — an ad spend waste mistake, a manual pipeline bottleneck, or a real case study of a business failing due to lack of systems.
- **POLL**: A performance marketing or automation dilemma business owners split on (e.g., Meta Ads CBO vs ABO, manual sales follow-up vs WhatsApp CRM automation, hiring agency vs building in-house ads team).
- **CAROUSEL**: A step-by-step scaling framework or automation workflow (e.g., "how we build a lead nurturing pipeline using n8n," "the 3 Meta Ads mistakes wasting ₹50k/month," "how to automate WhatsApp sales follow-ups").
- **INFOGRAPHIC**: Use the data found in Step 3. One striking metric-driven chart about ads, lead generation, or automation savings.

---

## STEP 5 — Write all 5 posts and generate the infographic

Apply every writing rule below without exception to every post.

---

## WRITING RULES — APPLY TO EVERY POST

### Voice and perspective
Write in third-person observer voice. The author is an expert performance marketer and automation consultant reporting on ad accounts, lead generation, and workflow systems. No "I" or "my" statements in the body prose (except for standard CTAs at the footer).

### Human realism (human-like imperfections)
- Mimic casual human writing habits: occasionally miss a comma or omit a full stop at the end of a line.
- Incorporate natural, conversational transitions or informal pivots ("wasting ad budget faster than" instead of "experiencing rapid budget depletion").
- Keep the style informal and conversational, avoiding overly polished, clinical sentence structures.

Good examples of the voice:
- "Most D2C brands scaling their ad spend make the same quiet budgeting mistake."
- "A common error in real estate lead generation is letting warm leads sit for 24 hours before follow-up."
- "The companies saving 20+ hours a week on CRM operations all deploy one specific workflow."

### Post structure
1. **Hook** — 1 or 2 lines. Surprising finding, metric, or common mistake.
2. **Pain point** — Specific frustration (ad budget burn, lead leakage, slow manual follow-ups).
3. **Actionable value** — Specific workflow, budget strategy, or setup step to apply.
4. **Dream picture** — Tangible outcome (lower CPL, higher ROAS, hours saved).
5. **Engagement question** — One pointed question that is easy to answer.
6. **CTA** — "Follow @harshchouksey for daily breakdowns on Meta Ads and automation." or "DM me 'SCALE' to build an automated growth engine."

### Hook styles
- **Curiosity**: "The way most agencies set up their [topic] is exactly why they stay stuck with [problem]."
- **Contrarian**: "Most people teaching [topic] online have never actually managed a ₹10L/month ad budget."
- **Transformation**: "[Metric] went from [low number] to [high number] in [time period]. Here is what actually moved it."
- **Question**: "What separates the D2C brands that [succeed] from the ones still stuck burning ad spend three years later?"
- **Story**: "A brand owner shared an n8n workflow this week that automated their entire lead-to-sale pipeline."

### Carousel hook styles
Use 6 to 8 words max on the cover slide. Maintain a curiosity gap: never give the answer on slide 1.
Read `./carousel-hook-log.json` before picking a hook style. The log tracks hook style history to enforce variety:
1. The style used in the **last run** is **banned** this run
2. If any style appears **3+ times in the last 7 entries**, it is also banned this run
3. Pick the most fitting non-banned style for today's topic

Examples:
- **Bold Claim**: "The ad setup costing you ₹50k/month."
- **Specific Result**: "0 to ₹10L/mo D2C scaling framework."
- **Mistake Call-Out**: "5 funnel mistakes killing your conversion."
- **Myth Buster**: "Why manual lead follow-up is killing sales."
- **Curiosity Gap**: "We cut lead costs by 60% with one node."
- **Number Reveal**: "7 n8n workflows to automate your agency."
- **Before-After**: "From 1.5x to 4.5x ROAS in 90 days."
- **Checklist Promise**: "The 10-point checklist for high-converting ads."
- **Framework Authority**: "The 3-step WhatsApp pipeline that converts."
- **Relatable Pain**: "Stop wasting money on unoptimized ads."

### Banned vocabulary
delve, underscore, vibrant, tapestry, interplay, intricate, garner, pivotal, showcase, foster, align with, landscape (abstractly), key (as adjective), leverages, encompasses, facilitates, utilized, commenced, subsequent to, prior to, in order to, stands as, serves as, is a testament to, plays a vital role, plays a significant role, plays a crucial role, enduring legacy, lasting impact, indelible mark, it's important to note, it's worth noting, no discussion would be complete without, moreover, furthermore, in addition, setting the stage for, marking a shift, evolving landscape, reflects broader trends, game-changer, supercharge, real results, real strategy, real conversations

---

## OUTPUT FORMAT

Output exactly this. Nothing before the first separator. Nothing after the last block.

━━━ COLLABORATIVE ARTICLE ━━━

[Complete thought piece, 1500 to 2000 characters. Sentence-case subheadings. Grounded in paid ads or automation systems. Full 6-part post structure embedded as flowing prose.]

━━━ POLL ━━━

[2 to 3 sentence setup caption that establishes the dilemma]

[Poll question as a single standalone line]

☐ [Option A]
☐ [Option B]
☐ [Option C]
☐ [Option D]

[One short line below that invites people to explain their vote in the comments]

━━━ CAROUSEL ━━━

Hook style used: [CAROUSEL_HOOK_STYLE]

Slide 1:
[Hook following the selected style. 6 to 8 words max. Curiosity gap.]

Slide 2:
[First point with a specific number or concrete fact. 2 to 3 sentences.]

Slide 3:
[Second point with a specific number or concrete fact. 2 to 3 sentences.]

Slide 4:
[Third point with a specific number or concrete fact. 2 to 3 sentences.]

Slide 5:
[Fourth point with a specific number or concrete fact. 2 to 3 sentences.]

Slide 6:
[Fifth point or the single insight that ties the whole carousel together. 2 to 3 sentences.]

Slide 7:
[Single CTA. "Follow @harshchouksey for more on paid ads and automation." or "DM 'SCALE' to automate your business."]

Caption:
[Hook line. Summary of the carousel. Engagement question. CTA. Max 4 lines total.]

━━━ MULTI-IMAGE POST ━━━

Image: [Direct URL to the image]

Caption:
[Hook line]
[2 to 3 sentences that add genuine insight beyond what the image shows]
[Engagement question]
[Single CTA]

━━━ INFOGRAPHIC ━━━

[Generate a complete, self-contained HTML file. Save it to ./linkedin-infographic.html. Then output the full HTML inline here as well.

The HTML must:
- Have zero external dependencies
- Use a system font stack
- Be designed at 1080x1080px for LinkedIn square format
- Use warm cream bg #F5EFE8, coral red #E63946, slate blue #6B6BB5
- Render a clean horizontal bar chart with labels and circles on the right
- Footer includes @harshchouksey credit

After saving the file, output a one-line note as part of this block only: "Open ./linkedin-infographic.html in a browser and screenshot it for LinkedIn." Then no further text.]
