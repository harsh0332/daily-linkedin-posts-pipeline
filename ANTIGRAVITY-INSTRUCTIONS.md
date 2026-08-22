# Instructions for Antigravity — LinkedIn content pipeline

Paste this in whole. It is the operating procedure for every scheduling run.

Project root: `/Users/harshchouksey/Desktop/daily-linkedin-posts-pipeline`

---

## The rule

**Never generate or schedule a batch without running preflight first.**

Pillars skip silently when their supply runs out. Preflight is the only thing
that catches that *before* the run instead of on the morning a post fails to
appear.

---

## Every run, in this order

### 1. Preflight

```bash
python3 preflight.py
```

- **Exit 0** — every day is supplied. Go to step 4.
- **Exit 1** — at least one day would skip. Go to step 2.
- **Exit 2** — config or a data file is broken. Stop. Show Harsh the output.

### 2. Refresh what needs no input from him

If preflight printed a **WHAT I CAN FIX WITHOUT YOU** section, run:

```bash
python3 preflight.py --refresh
```

That runs the Reddit and changelog fetches itself and re-checks. Do not ask
Harsh about these — they need nothing from him.

### 3. Relay the asks and WAIT

If preflight printed a **WHAT I NEED FROM YOU** section, show it to Harsh
**verbatim**. Do not summarise it, do not soften it, do not guess at what he
would want. It already says exactly what is needed, for example:

```
AD POOL EMPTY — Monday will skip.
  Give me 4 Meta Ad Library links and I'll add them.
  Pick ads that have been running 3+ weeks. Any D2C brand.
```

Then **stop and wait for his reply.** Do not proceed to generation.

When he sends ad links:

```bash
python3 add_teardown.py "<url1>" "<url2>" "<url3>" "<url4>"
```

Pass them all in one command. The script starts the adspy backend itself if it
is not running — do not start it yourself, and do not use `curl`.

If it refuses to write a file, it names the missing field. Report that line
verbatim. Do not hand-edit anything in `sources/ad_teardowns/`.

For benchmark figures, he will paste the numbers; add them to
`sources/benchmarks.toml` following the existing entries, and keep `year` as
the year the DATA was gathered, not the year the page was edited.

Then **re-run `python3 preflight.py`** and only continue on exit 0.

### 4. Run the pipeline

```bash
python3 run_pipeline.py
```

It runs preflight itself as step 0 and stops if anything would skip, so it is
safe to run directly.

If Harsh has explicitly said he accepts a short batch:

```bash
python3 run_pipeline.py --accept-short
```

Never pass `--accept-short` on your own initiative.

---

## The monthly top-up habit

Preflight prints a runway in weeks per pillar.

**If any pillar is under 2 weeks, ask for a month's worth at once** rather than
one at a time. One ad covers one Monday, so a month is 4 links. Asking four
times in four weeks is four interruptions where one would do.

Phrase it as preflight does: what is needed, how many, and what makes a good
one. For ads: running 3+ weeks, any D2C brand.

---

## Checking supply on its own

```bash
python3 validate_ad_pool.py
```

Reports how many teardowns are valid, how many are already used, and how many
Mondays are covered.

---

## Things that will waste your time if you do not know them

- **The adspy backend must run from `~/.venvs/adspy`**, never from a venv
  inside `~/Desktop`. iCloud evicts files there and reads time out, which
  makes uvicorn print its startup banner and never actually listen.
  `add_teardown.py` and `run.sh` both already point at the right one.
- **`carousel-routine/node_modules` is a symlink** to
  `~/.node_modules/carousel-routine/node_modules`, outside iCloud, for the same
  reason. If you run `npm install` from `carousel-routine`, npm deletes the
  symlink and the eviction problem comes back. Install from the target
  directory instead.
- **Do not edit `used_topics.json`, `used_angles.json`, `used_sources.json` or
  `pipeline_state.json` by hand.** Consumption is recorded by the scheduler
  after a post is genuinely on LinkedIn's queue. Writing them early marks
  material as spent for posts that never published.
- **Do not put content into `linkedin_posts_today.txt` directly.** Everything
  published goes through `generate_all_content.py` so the hard checks run.
