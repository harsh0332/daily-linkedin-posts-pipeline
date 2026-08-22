import os
import re
import sys
import json
import urllib.request
import urllib.parse
import datetime

from config_loader import load_config

# Phase 1: single source of truth (asserts on startup).
CONFIG = load_config()
WEEKDAYS_ONLY = bool(CONFIG.get("weekdays_only"))


def today_in_timezone():
    """Calendar date in the configured timezone, not the machine's local date.
    Mirror of todayInTimezone() in schedule_all_posts.cjs."""
    try:
        from zoneinfo import ZoneInfo
        return datetime.datetime.now(ZoneInfo(CONFIG["timezone"])).date()
    except Exception:
        return datetime.date.today()

# Read token and channel from .env
slack_token = None
channel = "C0BL8CKFMEU"  # Default fallback
if os.path.exists(".env"):
    with open(".env") as f:
        for line in f:
            if line.startswith("SLACK_BOT_TOKEN="):
                slack_token = line.strip().split("=", 1)[1]
            elif line.startswith("SLACK_CHANNEL_ID="):
                channel = line.strip().split("=", 1)[1]

if not slack_token:
    print("Error: SLACK_BOT_TOKEN not found in .env")
    exit(1)

date_str = datetime.date.today().isoformat()
date_compact = date_str.replace("-", "")

def send_slack_message(text):
    print(f"Sending message (length: {len(text)})...")
    url = "https://slack.com/api/chat.postMessage"
    headers = {
        "Authorization": f"Bearer {slack_token}",
        "Content-Type": "application/json; charset=utf-8"
    }
    payload = {
        "channel": channel,
        "text": text,
        "unfurl_links": False,
        "unfurl_media": False
    }
    req = urllib.request.Request(
        url, 
        data=json.dumps(payload).encode("utf-8"), 
        headers=headers,
        method="POST"
    )
    try:
        with urllib.request.urlopen(req) as res:
            resp = json.loads(res.read().decode("utf-8"))
            if not resp.get("ok"):
                print(f"Error sending message: {resp.get('error')}")
            else:
                print("Message sent successfully.")
    except Exception as e:
        print(f"Exception sending message: {e}")

def upload_slack_file(file_path, file_name, initial_comment):
    if not file_path or not os.path.exists(file_path):
        print(f"Error: file not found: {file_path}")
        return

    print(f"Uploading file: {file_name} ({os.path.getsize(file_path)} bytes)...")
    
    # 1. Get upload URL
    url = "https://slack.com/api/files.getUploadURLExternal"
    headers = {
        "Authorization": f"Bearer {slack_token}",
        "Content-Type": "application/x-www-form-urlencoded"
    }
    data = urllib.parse.urlencode({
        "filename": file_name,
        "length": os.path.getsize(file_path)
    }).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    
    try:
        with urllib.request.urlopen(req) as res:
            resp = json.loads(res.read().decode("utf-8"))
            if not resp.get("ok"):
                print(f"Error getting upload URL: {resp.get('error')}")
                return
            upload_url = resp.get("upload_url")
            file_id = resp.get("file_id")
    except Exception as e:
        print(f"Exception getting upload URL: {e}")
        return

    # 2. Upload file data
    print("Uploading file data to URL...")
    try:
        with open(file_path, "rb") as f:
            file_data = f.read()
        
        # Use multipart/form-data logic or raw POST
        # Slack files.getUploadURLExternal accepts raw file data as POST body
        req = urllib.request.Request(
            upload_url,
            data=file_data,
            method="POST"
        )
        with urllib.request.urlopen(req) as res:
            # Check response code
            if res.status != 200:
                print("Error uploading raw file data")
                return
            print("File data uploaded successfully.")
    except Exception as e:
        print(f"Exception uploading file data: {e}")
        return

    # 3. Complete upload
    print("Completing upload...")
    url = "https://slack.com/api/files.completeUploadExternal"
    headers = {
        "Authorization": f"Bearer {slack_token}",
        "Content-Type": "application/json; charset=utf-8"
    }
    payload = {
        "files": [{"id": file_id, "title": file_name}],
        "channel_id": channel,
        "initial_comment": initial_comment
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST"
    )
    try:
        with urllib.request.urlopen(req) as res:
            resp = json.loads(res.read().decode("utf-8"))
            if not resp.get("ok"):
                print(f"Error completing upload: {resp.get('error')}")
            else:
                print(f"File upload completed: {file_name}")
    except Exception as e:
        print(f"Exception completing upload: {e}")

# ============================================================================
# Phase 0: structural post parser + review gate
#
# The generator (generate_all_content.py) writes each post as:
#
#     ==================================================
#     <N>. <SLOT NAME>          <- e.g. "1. CAROUSEL 1", "4. TEXT 1"
#     ==================================================
#     <post body>
#
# We therefore parse STRUCTURALLY (separator run + a "<digits>." header line)
# rather than matching a fixed list of slot names. Slot names are free to
# change in Phase 1 without breaking this file. The type-detection rules below
# are a deliberate mirror of schedule_all_posts.cjs parseTodayPosts(), so what
# Slack shows is what the scheduler will actually do.
# ============================================================================

# Mirrors schedule_all_posts.cjs: content.split(/={10,}/) and /^\d+\./
SEPARATOR_RE = re.compile(r"={10,}")
HEADER_RE = re.compile(r"^\s*(\d+)\.\s*(\S.*?)\s*$")


def detect_type(header):
    """Mirror of schedule_all_posts.cjs:186-188."""
    h = header.lower()
    if "carousel" in h:
        return "carousel"
    if "infographic" in h:
        return "infographic"
    if "poll" in h:
        return "poll"
    return "regular"


def parse_posts(path):
    with open(path) as f:
        content = f.read()

    sections = SEPARATOR_RE.split(content)
    parsed = []
    i = 0
    while i < len(sections):
        sec = sections[i].strip()
        if not sec:
            i += 1
            continue
        header = sec.split("\n")[0].strip()
        m = HEADER_RE.match(header)
        if m:
            body = (sections[i + 1] if i + 1 < len(sections) else "").strip()
            if body:
                parsed.append({
                    "index": len(parsed) + 1,
                    "header": header,
                    "slot": m.group(2),
                    "type": detect_type(header),
                    "body": body,
                })
                i += 1  # skip the body section
        i += 1
    return parsed


# Read the SAME file the scheduler reads, so the review reflects reality.
SOURCE_FILE = "linkedin_posts_today.txt"
if not os.path.exists(SOURCE_FILE):
    fallback = f"linkedin_posts_{date_compact}.txt"
    if os.path.exists(fallback):
        SOURCE_FILE = fallback
    else:
        print("=" * 64)
        print("FATAL: no generated posts file found.")
        print(f"  Looked for: linkedin_posts_today.txt and {fallback}")
        print("  Nothing was sent to Slack.")
        print("=" * 64)
        sys.exit(1)

posts = parse_posts(SOURCE_FILE)

if not posts:
    print("=" * 64)
    print("FATAL: parsed 0 posts from " + SOURCE_FILE)
    print("  The file exists but no '<N>. <NAME>' headers separated by '====='")
    print("  lines were found. The generator's output format may have changed.")
    print("  Nothing was sent to Slack.")
    print("=" * 64)
    sys.exit(1)

print(f"Parsed {len(posts)} posts from {SOURCE_FILE}")


# ---- Predicted schedule -----------------------------------------------------
# Slack delivery runs BEFORE scheduling, so these are the slots the scheduler
# WILL use. Phase 1: derived from pipeline_config.json, the same file the
# scheduler reads — no longer a hand-maintained mirror.
SCHEDULE_SLOTS = []
for _day in range(CONFIG["batch_horizon_days"]):
    for _time in CONFIG["time_slots"]:
        if len(SCHEDULE_SLOTS) >= CONFIG["posts_per_batch"]:
            break
        SCHEDULE_SLOTS.append((_day, _time))


def predicted_start_date():
    """Best-effort mirror of the scheduler's start-date logic. Display only."""
    offset_env = os.environ.get("START_DATE_OFFSET")
    if offset_env is not None:
        try:
            off = int(offset_env)
            if off >= 0:
                return today_in_timezone() + datetime.timedelta(days=off)
        except ValueError:
            return None
        return None
    try:
        with open("pipeline_state.json") as f:
            last = json.load(f).get("last_scheduled_date")
        y, m, d = (int(x) for x in str(last).split("-"))
        return datetime.date(y, m, d) + datetime.timedelta(days=1)
    except Exception:
        return None


start_date = predicted_start_date()


def build_slot_dates(start, count):
    """One date per scheduled slot, in order.

    This is the single place the preview maps slot index -> calendar date.
    The scheduling window is read off the ends of this list, never from a
    hard-coded day offset. Mirror of the scheduler's own day-filling loop.
    """
    if start is None:
        return []
    dates = []
    day = 0
    guard = 0
    while len(dates) < count and guard < 400:
        guard += 1
        d = start + datetime.timedelta(days=day)
        day += 1
        # Mirror of the scheduler: weekends are skipped entirely.
        if WEEKDAYS_ONLY and d.weekday() >= 5:
            continue
        for _ in CONFIG["time_slots"]:
            if len(dates) >= count:
                break
            dates.append(d)
    return dates


SLOT_DATES = build_slot_dates(start_date, min(len(posts), len(SCHEDULE_SLOTS)))


def slot_for(idx):
    """idx is 1-based. Returns 'Sat 08 Aug 2026 at 9:00 AM' or a fallback."""
    if idx - 1 >= len(SCHEDULE_SLOTS):
        return f"not scheduled (beyond the {len(SCHEDULE_SLOTS)}-slot window)"
    _day_offset, time_str = SCHEDULE_SLOTS[idx - 1]
    if idx - 1 >= len(SLOT_DATES):
        return f"{time_str} (date unavailable — check pipeline_state.json)"
    d = SLOT_DATES[idx - 1]
    return f"{d.strftime('%a %d %b %Y')} at {time_str}"


# Extract Carousel & Infographic captions from the first post of each type.
# (`posts` is now a list of dicts, not the old string-keyed dict. Upload calls
# below are unchanged; only the caption lookup was rewired.)
def first_body(post_type):
    for p in posts:
        if p["type"] == post_type:
            return p["body"]
    return ""


# The model emits marker lines inconsistently: "CAROUSEL CAPTION:",
# "**CAROUSEL CAPTION:**" and "*CAROUSEL CAPTION:*" all occur in the archives.
# Normalise a line by stripping markdown emphasis and surrounding whitespace
# before matching, so every variant parses identically.
#
# ⚠ KNOWN DUPLICATION: identical normalisation exists in JavaScript at
#   schedule_all_posts.cjs:160-322 (MARKDOWN_EMPHASIS / stripEmphasis /
#   normaliseMarker / markerRemainder / extractCaption). The two must stay in
#   sync or this preview will disagree with what is actually published.
#   Collapse into one shared definition when this pipeline gets a config layer.
MARKDOWN_EMPHASIS = "*_` \t"


def normalise_marker(line):
    """'  **CAROUSEL CAPTION:**  ' -> 'CAROUSEL CAPTION:'"""
    return line.strip().strip(MARKDOWN_EMPHASIS).strip()


def marker_remainder(line, marker):
    """Text after `marker` on the same line, or None if the line does not start
    with it. Mirror of markerRemainder() in schedule_all_posts.cjs, including
    the requirement that the marker be followed by ':'."""
    norm = normalise_marker(line)
    target = str(marker).upper().rstrip(":")
    if not norm.upper().startswith(target):
        return None
    after = norm[len(target):]
    m = re.match(r"^[\s*_`]*:+", after)
    if not m:
        return None
    return after[m.end():].strip(MARKDOWN_EMPHASIS).strip()


def is_marker(line, *markers):
    """True if the line IS one of the markers, ignoring emphasis/whitespace."""
    n = normalise_marker(line).upper().rstrip(":")
    return any(n == m.upper().rstrip(":") for m in markers)


def extract_caption(body, marker, stop_marker=None):
    """Capture every line after the marker line, ignoring markdown emphasis."""
    if not body:
        return ""
    caption_lines = []
    capture = False
    for line in body.split("\n"):
        if not capture and is_marker(line, marker, "Caption"):
            capture = True
            continue
        if capture and stop_marker and is_marker(line, stop_marker):
            break
        if capture:
            caption_lines.append(line)
    # strip() alone cannot remove a leading '*', so strip emphasis explicitly
    return "\n".join(caption_lines).strip().strip(MARKDOWN_EMPHASIS).strip()



# ---- Phase 1: carousel index + preview ---------------------------------------
CAROUSEL_IDX_RE = re.compile(r"CAROUSEL\s*(\d+)", re.I)


def carousel_index(header):
    """Per-format index from the header, the SAME source the scheduler uses
    (schedule_all_posts.cjs: header.match(/CAROUSEL\\s*(\\d+)/i))."""
    m = CAROUSEL_IDX_RE.search(header or "")
    return int(m.group(1)) if m else 1


def slide_text(body, n):
    """Text of 'Slide n' — the remainder on the marker line, else the next
    non-empty line. Emphasis-tolerant, like every other marker read."""
    lines = body.split("\n")
    for i, line in enumerate(lines):
        norm = normalise_marker(line)
        if re.match(rf"^slide\s*{n}\b", norm, re.I):
            after = re.sub(rf"^slide\s*{n}\s*[:\-]?\s*", "", norm, flags=re.I).strip()
            after = after.strip(MARKDOWN_EMPHASIS).strip().strip('"\'')
            if after:
                return after
            for nxt in lines[i + 1:]:
                t = normalise_marker(nxt).strip().strip('"\'')
                if t:
                    return t
            return ""
    return ""


def count_slides(body):
    return len(set(re.findall(r"slide\s*(\d+)", normalise_marker(body), re.I)))


def carousel_preview(body, pdf_name):
    """Hook + slide 1 + full caption. Slides 2-N collapse to one pointer line.

    Slide 1's hook becomes the LinkedIn document title - the largest text on the
    post in the feed - so it must be visible before approval. Slides 2-N only
    ever reach the PDF, which is attached separately, so printing them in full
    was more than half the review message for content that cannot be acted on.
    """
    hook = ""
    for line in body.split("\n"):
        rem = marker_remainder(line, "Hook text:")
        if rem is None:
            rem = marker_remainder(line, "Hook:")
        if rem:
            hook = rem.strip('"\'')
            break
    s1 = slide_text(body, 1)
    total = count_slides(body)
    caption = extract_caption(body, "CAROUSEL CAPTION:", stop_marker="Slide 1:")
    hidden = max(total - 1, 0)

    parts = []
    parts.append(f"*Doc title:* {hook}" if hook else "*Doc title:* _(no Hook line — will fall back to caption text)_")
    if s1:
        parts.append(f"*Slide 1:* {s1}")
    parts.append(
        f"_… slides 2-{total} ({hidden} more) are in the attached PDF → {pdf_name}_"
        if hidden else f"_PDF → {pdf_name}_"
    )
    parts.append("")
    parts.append("*Caption (this is the post text that publishes):*")
    parts.append(caption or "_(no caption found)_")
    return "\n".join(parts)
# ------------------------------------------------------------------------------

TYPE_LABEL = {
    "carousel": "CAROUSEL (PDF)",
    "infographic": "INFOGRAPHIC (image)",
    "poll": "POLL",
    "regular": "TEXT",
}

# ---- Send the review batch --------------------------------------------------
counts = {}
for p in posts:
    counts[p["type"]] = counts.get(p["type"], 0) + 1
mix = ", ".join(f"{v} {k}" for k, v in sorted(counts.items()))

# Window is read off the REAL first and last slot, never a fixed day offset.
window = "schedule unavailable"
if SLOT_DATES:
    first, last = SLOT_DATES[0], SLOT_DATES[-1]
    window = (
        last.strftime("%a %d %b %Y")
        if first == last
        else f"{first.strftime('%a %d %b')} to {last.strftime('%a %d %b %Y')}"
    )

# ---- Phase 2: review flags surfaced with the offending line quoted -----------
# Vocabulary and mid-body questions are matters of taste, so the code logs them
# and Harsh decides here. Only safety checks (unsourced figures, external links,
# carousel completeness) ever block a batch.
review_note = ""
try:
    if os.path.exists("review_flags.json"):
        _rf = json.load(open("review_flags.json"))
        if _rf:
            blocks = []
            nw = sum(len(e.get("wording", [])) for e in _rf)
            nq = sum(len(e.get("questions", [])) for e in _rf)
            for e in _rf:
                lines = [f"*{e['post']}*"]
                for w in e.get("wording", []):
                    lines.append(f"  • `{w['found']}` — {w['line'][:110]}")
                for q in e.get("questions", []):
                    lines.append(f"  • _mid-body question_ — {q[:110]}")
                blocks.append("\n".join(lines))
            review_note = ("\n\n_Review notes ({} wording, {} question(s)) — not blocking, your call:_\n"
                           .format(nw, nq) + "\n".join(blocks))
except Exception as _e:
    print(f"Could not read review_flags.json: {_e}")

# ---- Phase 3c: a short batch must announce itself ---------------------------
# One pillar failing no longer kills the batch, so the gap has to be visible
# here, before anything is posted, or a missing day would pass unnoticed.
missing_note = ""
try:
    if os.path.exists("missing_days.json"):
        _md = json.load(open("missing_days.json"))
        if _md:
            lines = [f"  • *{m['day']}* — `{m['pillar']}` ({m['format']}): {m['reason']}"
                     for m in _md]
            missing_note = (
                f"\n\n:warning: *SHORT BATCH — {len(_md)} day(s) missing.*\n"
                + "\n".join(lines)
                + "\nThese pillars produced nothing, so no post was written for "
                  "them. The posts below shift up to fill the earliest slots, so "
                  "the calendar has no gap: it is the *content* for these pillars "
                  "that is missing, not a blank day.\n"
                  "Fix the pillar or accept the short week."
            )
except Exception as _e:
    print(f"Could not read missing_days.json: {_e}")

# ---- Phase 3f: rejected posts are visible in the review ---------------------
# A rejected post no longer kills the batch, so the gap has to be named here or
# a missing day would look like a normal short week.
rejected_note = ""
try:
    if os.path.exists("rejected_posts.json"):
        _rp = json.load(open("rejected_posts.json"))
        if _rp:
            lines = [f"  • *{r['post']}* — `{r['pillar']}`: {'; '.join(r['reasons'])}"
                     for r in _rp]
            rejected_note = (
                f"\n\n:no_entry: *{len(_rp)} post(s) REJECTED by the hard checks "
                f"and not included below.*\n" + "\n".join(lines)
                + "\nNothing was retried and no check was relaxed. The drafts are "
                  "in `rejected_posts/` if you want to see what was written."
            )
except Exception as _e:
    print(f"Could not read rejected_posts.json: {_e}")

header_msg = (
    f"📅 *LinkedIn Content Drop — {date_str}*\n"
    f"*{len(posts)} posts* for review ({mix}).\n"
    f"Scheduling window: *{window}*\n"
    f"Source: `{SOURCE_FILE}`\n"
    f"_Review before the scheduler runs. Assets attached below._"
    + missing_note
    + rejected_note
    + review_note
)
send_slack_message(header_msg)

for p in posts:
    label = TYPE_LABEL.get(p["type"], p["type"].upper())
    if p["type"] == "carousel":
        idx = carousel_index(p["header"])
        p["carousel_index"] = idx
        detail = carousel_preview(p["body"], f"carousel-{idx}.pdf")
    else:
        detail = p["body"]
    msg = (
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"*POST {p['index']} of {len(posts)}  ·  {label}*\n"
        f"🗓  {slot_for(p['index'])}\n"
        f"_slot: {p['slot']}_\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"{detail}"
    )
    send_slack_message(msg)

# Upload the Text Posts PDF
posts_pdf_path = f"linkedin_posts_{date_compact}.pdf"
upload_slack_file(
    posts_pdf_path,
    f"linkedin_posts_{date_compact}.pdf",
    # Derived from the batch actually parsed, so it cannot go stale again.
    f"━━━ DAILY TEXT POSTS PDF — {date_str} ━━━\n\nContains all {len(posts)} LinkedIn posts ({mix}) formatted for easy reading."
)

# Upload the raw Text Posts file for the auto-scheduler bot
posts_txt_path = f"linkedin_posts_{date_compact}.txt"
upload_slack_file(
    posts_txt_path,
    f"linkedin_posts_{date_compact}.txt",
    f"━━━ RAW TEXT DRAFTS — {date_str} ━━━\n\nFor bot auto-scheduling consumption."
)

# Upload PDF and PNG Infographic
pdf_dir = f"./carousel-routine/output/{date_str}/carousel-branded"
png_path = f"./linkedin-infographic-{date_compact}.png"

infographic_caption = extract_caption(
    first_body("infographic"), "INFOGRAPHIC CAPTION:"
)


# ---- Phase 1: one PDF per carousel, resolved by per-format index -------------
# Previously a single PDF was uploaded regardless of how many carousels the
# batch contained, so with 2 carousels one was approved and the other published
# unseen. Resolution mirrors schedule_all_posts.cjs exactly: the dated output
# subdirectory first, then the slack_downloads copy.
def resolve_carousel_pdf(idx):
    sub = os.path.join(pdf_dir, f"carousel-{idx}")
    if os.path.isdir(sub):
        pdfs = sorted(fn for fn in os.listdir(sub) if fn.endswith(".pdf"))
        if pdfs:
            return os.path.join(sub, pdfs[0])
    fallback = os.path.join("slack_downloads", f"carousel-{idx}.pdf")
    return fallback if os.path.exists(fallback) else None


carousel_posts = [p for p in posts if p["type"] == "carousel"]
missing_pdfs = []

for p in carousel_posts:
    idx = p.get("carousel_index") or carousel_index(p["header"])
    caption = extract_caption(p["body"], "CAROUSEL CAPTION:", stop_marker="Slide 1:")
    resolved = resolve_carousel_pdf(idx)
    if resolved is None:
        missing_pdfs.append((p["index"], idx))
        continue
    upload_slack_file(
        resolved,
        os.path.basename(resolved),
        f"━━━ CAROUSEL PDF {idx} of {len(carousel_posts)} — post {p['index']} ━━━\n\n{caption}"
    )

# Say so loudly rather than silently uploading fewer files than there are
# carousels. The scheduler will refuse to run in this state anyway.
if missing_pdfs:
    lines = [
        "🚨 *CAROUSEL PDF MISSING — do not run the scheduler*",
        f"{len(missing_pdfs)} of {len(carousel_posts)} carousel PDFs could not be found:",
    ]
    for post_no, idx in missing_pdfs:
        lines.append(f"  • post {post_no} → expected `carousel-{idx}.pdf` (checked `{pdf_dir}/carousel-{idx}/` and `slack_downloads/`)")
    lines.append("")
    lines.append("_The carousel build step probably did not run. The scheduler will abort rather than publish a carousel without its document._")
    send_slack_message("\n".join(lines))
    print(f"WARNING: {len(missing_pdfs)} carousel PDF(s) missing: {missing_pdfs}")
else:
    print(f"All {len(carousel_posts)} carousel PDF(s) resolved and uploaded.")
# ------------------------------------------------------------------------------

# Upload individual slide PNGs
if os.path.exists(pdf_dir):
    slide_pngs = sorted([fn for fn in os.listdir(pdf_dir) if fn.startswith("slide-") and fn.endswith(".png")])
    for slide_fn in slide_pngs:
        slide_path = os.path.join(pdf_dir, slide_fn)
        slide_num = slide_fn.split("-")[1].split(".")[0]
        upload_slack_file(
            slide_path,
            slide_fn,
            f"Slide {slide_num} of {len(slide_pngs)}"
        )

# Only attempt the infographic upload if the batch actually contains one.
# With format_mix.infographic = 0 this would otherwise log "file not found"
# every run and mask a genuine missing-asset error later.
if counts.get("infographic", 0) > 0:
    upload_slack_file(
        png_path,
        "linkedin-infographic.png",
        f"━━━ INFOGRAPHIC ━━━\n\n{infographic_caption}"
    )
else:
    print("No infographic in this batch (format_mix.infographic = 0) — skipping that upload.")

print("All daily LinkedIn publication steps completed successfully.")

