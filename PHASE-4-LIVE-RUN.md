# PHASE-4-LIVE-RUN.md

First live run checklist. Written 2026-08-13 (Thursday).

Companion to [`PIPELINE-AUDIT.md`](PIPELINE-AUDIT.md) and the phase reports.
Nothing in this file has been executed — Chrome opens on your machine and you
run every command yourself.

**Context assumed:** LinkedIn's scheduled queue is empty (you confirmed it), all
previous 4-per-day posts have already published, and the pipeline has never run
live.

---

## Step 1 — `last_scheduled_date`

### Set it to `2026-08-16`

```json
{
  "last_scheduled_date": "2026-08-16",
  "last_updated": "2026-08-04T14:34:51.762Z"
}
```

Leave `last_updated` alone; nothing reads it, and the scheduler overwrites it
when the batch completes.

### Resulting batch

The scheduler takes `last_scheduled_date + 1 day` as the start, then fills
weekday slots at `9:30 AM` Asia/Kolkata until the batch is full
(`schedule_all_posts.cjs:641-654`).

`2026-08-16` is a Sunday, so the start is **Monday 2026-08-17**:

| Post | Pillar | Format | Date | Day |
|---|---|---|---|---|
| 1 | `ad-teardown` | carousel | 2026-08-17 | Monday |
| 2 | `benchmark` | text | 2026-08-18 | Tuesday |
| 3 | `build-note` | carousel | 2026-08-19 | Wednesday |
| 4 | `community-question` | text | 2026-08-20 | Thursday |
| 5 | `update-or-hot-take` | text | 2026-08-21 | Friday |

### Why Sunday and not something else

**Posts are assigned to slots positionally** — `posts.forEach((p, idx) => { p.date
= schedule[idx].date })` at `schedule_all_posts.cjs:672`. The pillars are declared
Mon→Fri in `pipeline_config.json`, but nothing checks that post 1 actually lands
on a Monday. If the batch starts mid-week, Monday's ad teardown posts on a Friday
and the pillar day labels become decorative.

Starting Monday 2026-08-17 is the only choice that makes the labels true.

**This is now enforced.** Guard D (added 2026-08-13) aborts before anything is
scheduled if post 1 would not land on pillar 1's declared weekday, and the
watermark is anchored so it cannot drift afterwards — see "Monday anchoring"
below.

Two other values are worth knowing about:

- `2026-08-13` (today) → starts Friday 08-14 → post 1 on a Friday → **Guard D
  aborts.** Before Guard D this would have scheduled happily with every day
  label wrong.
- `2026-08-14` → starts Saturday 08-15; the weekend is skipped, so post 1 still
  lands Monday 08-17 and it passes. Same dates as the recommendation, but by
  accident of the weekend skip rather than by intent. Use `2026-08-16`.

### Monday anchoring — why a short batch can no longer shift the schedule

A five-post batch ends Friday, so `last_post + 1` rolls to the weekend and the
next batch starts Monday on its own. **A short batch does not.** Four posts end
Thursday; a last-post watermark would start the next batch on Friday, publishing
Monday's ad teardown on a Friday — and because each watermark is derived from
the batch before it, nothing ever pulls it back. Short batches are not
hypothetical; they happened repeatedly in testing.

So the watermark is no longer the last post's date. After scheduling, it
advances to **the day before the next pillar-1 weekday**, whatever the batch
length:

| Batch | Last post | Watermark written | Next batch starts |
|---|---|---|---|
| 5 posts | Fri 2026-08-21 | `2026-08-23` | Mon 2026-08-24 |
| 4 posts | Thu 2026-08-20 | `2026-08-23` | Mon 2026-08-24 |
| 3 posts | Wed 2026-08-19 | `2026-08-23` | Mon 2026-08-24 |
| 2 posts | Tue 2026-08-18 | `2026-08-23` | Mon 2026-08-24 |
| 1 post | Mon 2026-08-17 | `2026-08-23` | Mon 2026-08-24 |

Every length converges on the same value.

### What breaks if it is too far back

**Nothing schedules — the run aborts safely.** Guard C
(`schedule_all_posts.cjs:618-628`) requires the computed start to be **tomorrow
or later**, and refuses to clamp:

```
FATAL: computed batch start date is not in the future.
  Computed start:   2026-08-08
  Earliest allowed: 2026-08-14 (tomorrow)
  Not clamping. Fix pipeline_state.json or START_DATE_OFFSET and re-run.
```

**The file's current value of `2026-08-07` is exactly this case** — it would
compute a start of 2026-08-08 (a Saturday, already past) and abort. You must
change it; the run cannot proceed on today's value.

This is the safe direction to be wrong in. Nothing is posted, nothing is
consumed, and you re-run after fixing the date.

### What breaks if it is too far forward

**Most far-forward values now abort, but the dangerous ones still succeed.**
Guard C only enforces a floor, not a ceiling. Guard D catches the rest by
accident of the weekday check:

- `2026-09-30` → starts Thursday 10-01 → post 1 on a Thursday → **Guard D
  aborts.** Safe.
- `2026-10-04` (a Sunday) → starts Monday 10-05 → **passes**, and you get a batch
  scheduled 5–9 October.

So the failure mode is narrower than it was, but not closed: any Sunday still
schedules a full batch on the Monday after it. Nobody notices until the content
is stale — the WordStream post says "9 years ago", the n8n post is about a
release from August, and the ad teardown's "34 days as of 2026" will be wrong by
then.

It no longer compounds, though. The watermark is anchored to the next Monday
after the batch, so a batch scheduled in October advances the watermark into
October and stays there — wrong, but not drifting further each run. You fix it by
editing the file once.

There is also a practical ceiling: LinkedIn caps how far ahead a post can be
scheduled. I have not verified the current limit, so do not push the start date
months out to test that boundary — use Step 2's protocol, which is designed for
it.

---

## Step 2 — Test run, far-future dates

### The trap this protocol exists for

`START_DATE_OFFSET` overrides the start date (Guard A,
`schedule_all_posts.cjs:551-566`) **but it does not suppress the state write.**
The write at `schedule_all_posts.cjs:1364-1374` is unconditional:

```js
fs.writeFileSync(stateFile, JSON.stringify({
  last_scheduled_date: lastDateIso,
  ...
```

So a test run at `START_DATE_OFFSET=60` leaves `last_scheduled_date` at
**2026-10-16**. If you then do the real run without restoring, Guard C passes,
and your "first real batch" schedules to 19–23 October.

The restore in this protocol is not optional.

### 2a. Generate the content (touches nothing on LinkedIn)

```bash
python3 fetch_reddit_rss.py
```

```bash
python3 generate_all_content.py
```

```bash
cp linkedin_posts_$(date +%Y%m%d).txt linkedin_posts_today.txt
```

```bash
NODE_PATH=./carousel-routine/node_modules node build_carousel_today.cjs
```

`cap_infographic_today.js` is in `run_pipeline.py` but `format_mix.infographic`
is `0`, so there is nothing for it to build. Skip it.

```bash
python3 send_to_slack.py
```

**Generate once.** Steps 2 and 5 schedule the *same* generated content — the
test proves the mechanics, then you delete the test posts and schedule the batch
you already reviewed. Regenerating between them would burn a second set of
topics and angles, and put content in front of LinkedIn that you never read.

### 2b. Back up everything the run writes

```bash
mkdir -p state-backups && cp pipeline_state.json "state-backups/pipeline_state.json.pre-test-$(date +%Y%m%d-%H%M%S)" && ls -1 state-backups/ | tail -3
```

Note the exact filename it prints — you need it in 2d.

`state-backups/` is gitignored, so this never enters version control.

### 2c. Run the scheduler only, with a far-future offset

```bash
START_DATE_OFFSET=60 NODE_PATH=./carousel-routine/node_modules node schedule_all_posts.cjs
```

`60` puts the start at **Monday 2026-10-12**, giving test dates 12–16 October —
far enough that no test post can publish before you delete it, and comfortably
inside any plausible scheduling limit.

**The offset must land post 1 on a Monday**, or Guard D aborts. From today,
offsets 2, 3, 4 and 60 pass; 1, 5, 6, 7 and 61 abort. If you change the offset,
change it in multiples of 7 from 60 — `53`, `67`, `74` all stay on a Monday.

Expect near the top:

```
START_DATE_OFFSET=60 set — overriding pipeline_state.json.
Batch start date: 2026-10-12 — date guards passed.
```

If you see the Guard C abort instead, the offset was not read — check for a typo
before anything else.

### 2d. Restore, immediately after the run ends

Do this before doing anything else, including reviewing the queue.

```bash
cp state-backups/pipeline_state.json.pre-test-<STAMP> pipeline_state.json && cat pipeline_state.json
```

Replace `<STAMP>` with the filename from 2b. Confirm it prints
`"last_scheduled_date": "2026-08-16"`.

```bash
rm -f schedule_checkpoint.json && ls schedule_checkpoint.json 2>/dev/null || echo "checkpoint cleared"
```

The checkpoint must go too. On startup the scheduler refuses to run on top of an
unfinished batch (`schedule_all_posts.cjs:738-770`) and **will not auto-resume**.
A completed run leaves `status: 'complete'`, which does not block — but if the
test aborts partway, the leftover checkpoint blocks the real run until you clear
it.

---

## Step 3 — Reading the Slack review

The message is assembled in `send_to_slack.py`. Read it in this order.

### Stop immediately if you see

**`:warning: SHORT BATCH — N day(s) missing.`**
A pillar produced nothing. The message names the pillar and the reason. Fix the
pillar or accept a short week — but decide deliberately, do not schedule past it
without reading why.

**`:no_entry: N post(s) REJECTED by the hard checks and not included below.`**
A post failed a hard check and was dropped. The batch continues by design, but
you are about to schedule fewer posts than you think. The drafts are in
`rejected_posts/` if you want to see what was written.

**A carousel with no PDF attached.** Each carousel should arrive as a separate
PDF upload. A loud missing-file message instead means the PDF was not built, and
`schedule_all_posts.cjs:492` will abort the scheduling run when it cannot find
the asset — better to catch it here.

**Fewer posts listed than you expect.** The header states the count. Five posts,
two carousel and three text.

### Read every post in full, and stop on any of these

- **A figure you cannot source.** The checkers allow a figure only with an
  allowlisted publisher and year in the same sentence, or an explicit
  hypothetical marker. If a number appears without either, a checker has a gap —
  do not publish it and tell me.
- **A claim about your work you did not make.** Anything asserting a result,
  a test, or hands-on use that is not in `raw_notes.toml`.
- **Anything that reads like the instruction file.** The echo checker blocks the
  12 examples in `voice-profile.md`, but only those exact strings.
- **The Ad Library credited with a verdict.** It publishes days running,
  placements, format and active status. It does not rate effectiveness.

### Not a reason to stop

Advisory flags. The review lists wording notes (`curious`, `leverage`,
`seamless`…) and mid-body rhetorical questions, quoted with the offending line.
These are yours to judge — Phase 2 measured that enforcing them in code only
makes the model swap a synonym. Weak CTAs are in the same category: rule 11 is
advisory by decision, so `"Share your thoughts!"` will pass. Fix it by hand in
LinkedIn if it bothers you.

Known cosmetic issues in the current batch, already accepted: a `revampied`
typo in post 4, and `34-day-running` in post 1's caption stating the figure with
the Ad Library named but no year.

---

## Step 4 — Deleting the test posts

Do this before Step 5. Two identical batches in the queue is the one outcome
this whole protocol exists to prevent.

**I could not verify LinkedIn's current UI from here**, so treat the labels below
as approximate and trust what you see on screen.

1. Open LinkedIn and start a new post (the composer).
2. In the composer there is a clock / scheduling control. Opening it shows the
   list of scheduled posts.
3. You are looking for **five posts dated 12–16 October 2026, all at 9:30 AM**.
   Those dates are the tell — nothing else in your queue should be in October.
4. Delete all five. Each has its own delete or trash control in that list.
5. Confirm the list is empty before leaving the screen.

If the composer route does not show them, look under your profile's posts and
activity for a scheduled section. If you cannot find them at all, **stop and do
not run Step 5** — an undeleted test batch will publish in October.

Cross-check against the scheduler's own output: the test run printed a
`Schedule Summary:` block listing every date, time and title. Match the queue to
that list.

---

## Step 5 — The real run

Only after Step 4 shows an empty October queue, and `pipeline_state.json` reads
`2026-08-16`.

### Pre-flight

```bash
cat pipeline_state.json && ls schedule_checkpoint.json 2>/dev/null || echo "no checkpoint — good"
```

Must show `"last_scheduled_date": "2026-08-16"` and no checkpoint file.

### Command

```bash
NODE_PATH=./carousel-routine/node_modules node schedule_all_posts.cjs
```

**Scheduler only — do not run `run_pipeline.py`.** It would regenerate the
content from step 1, burning a fresh set of topics and replacing the batch you
reviewed in Slack with one you have not read.

No `START_DATE_OFFSET` this time. Its absence is what makes the scheduler read
`pipeline_state.json`.

### What to check in the log

**1. The start date, near the top:**

```
Batch start date: 2026-08-17 — date guards passed.
```

If it says anything else, `Ctrl-C` immediately. There should be no
`START_DATE_OFFSET=... set` line — if there is, the variable is still exported in
your shell, and the batch is going to October again.

**2. The `DOC_TITLE_MAX` probe**, on the first carousel, after the document
uploads. This is read-only and changes nothing
(`schedule_all_posts.cjs:1075-1084`). One of two lines:

```
Document title maxLength confirmed: 58
```

`DOC_TITLE_MAX = 58` was a measured guess. This confirms it.

```
⚠ LinkedIn title maxLength is <N>, but DOC_TITLE_MAX is 58 — update the constant.
```

**This is informational, not an error — let the run continue.** Titles are
truncated to 58 before typing, so a larger real cap only means titles are shorter
than they need to be, and a smaller one would already have been caught by the
verify-title step. Note the number and tell me; it is a one-line constant change
for the next batch.

If neither line appears, the probe threw and was swallowed — also worth telling
me, though it blocks nothing.

**3. The `Hook:` line reaching the document title.** Before running, check what
the generator produced:

```bash
grep -n "^Hook:" linkedin_posts_$(date +%Y%m%d).txt
```

Two lines, one per carousel. For the reviewed batch these are
`Flipkart Ad Teardown: The Essentials` and
`Bot loops: Fixing with reasoning, not models`.

Then in the scheduler log, for each carousel:

```
Document title typed (36/58 chars): Flipkart Ad Teardown: The Essentials
```

The typed title must match the `Hook:` line. This is the path that published a
literal `**` on six carousels before Phase 0b, and the placeholder string
`A declarative statement, 6-8 words, never a question` before the Phase 3 hook
fix. **If the title is a fragment of the caption, an asterisk, or an instruction,
stop the run** — the hook extraction has regressed.

**4. Per-post progress**, five times:

```
Scheduling Post <n>/5 (<type>): Date=..., Time=9:30 AM
✓ Successfully scheduled Post <n>/5!
  checkpoint: <n>/5 recorded
```

If it dies partway, the checkpoint records exactly which posts are already live.
Do not re-run blind — the startup guard will stop you and print the list.

**5. The finish:**

```
✓ ALL 5 POSTS HAVE BEEN SCHEDULED SUCCESSFULLY!
Saved pipeline state memory: watermark 2026-08-23, so the next batch starts 2026-08-24 (Monday).
  Last post in this batch: 2026-08-21. The watermark is anchored to the next Monday, not to that date, so a short batch cannot shift the schedule.
```

Then a `Schedule Summary:` listing all five dates, times and titles. Check it
against the table in Step 1.

Note the watermark is `2026-08-23`, **not** `2026-08-21` — that is the Monday
anchoring, and it is the same value a four-post batch would have written.

### Afterwards

```bash
cat pipeline_state.json
```

Should read `"last_scheduled_date": "2026-08-23"`. That makes the next batch
start Monday 2026-08-24 with no manual edit, and it would read the same even if
this batch had been short.

Verify the five posts in LinkedIn's scheduled queue: 17–21 August, 9:30 AM,
two carousels with their PDFs and three text posts.
