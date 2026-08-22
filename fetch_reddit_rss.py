"""Fetch Reddit as QUESTIONS people are asking, not as news (Phase 3).

Three things were wrong before and are fixed here:
  1. Only the first 20 of ~80 fetched items ever reached the planner. No
     truncation now - the selector filters, the fetcher does not.
  2. Per-subreddit failures were silent. On the last run 6 of 10 subreddits
     returned nothing and the script still exited 0. Failures are now counted
     and the run aborts if too few subreddits responded.
  3. `ups` and `num_comments` were written as the constants 100 and 10 for
     every item, because RSS does not expose them. Any downstream logic that
     looked like it weighed engagement was weighing a constant. They are now
     null, and the reason is recorded on every item.
"""

import html
import json
import re
import ssl
import sys
import time
import urllib.request
import xml.etree.ElementTree as ET

from config_loader import load_config

CONFIG = load_config()
SUBREDDITS = CONFIG.get("reddit_subreddits") or []
MIN_ITEMS = CONFIG.get("reddit_min_items", 15)

# The community pillar consumes exactly ONE question per run. The previous run
# fetched 150 items and used 1, while getting 429-ed on two subreddits - one of
# them r/facebookads, the one that matters most. So: fetch fewer, wait longer,
# and back off properly on 429 rather than hammering.
PER_SUB_LIMIT = CONFIG.get("reddit_per_sub_limit", 25)
SUB_DELAY_SECONDS = CONFIG.get("reddit_delay_seconds", 8)
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36 "
      "LinkedInPipelineBot/1.0 (by /u/harshchouksey)")

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

# A question someone is actually asking, not a news headline.
QUESTION_OPENERS = (
    "how", "what", "why", "when", "where", "which", "who", "should", "is ",
    "are ", "can ", "do ", "does ", "did ", "has ", "have ", "any", "anyone",
    "would", "could", "will ", "am i", "help",
)


def looks_like_question(title):
    t = (title or "").strip().lower()
    if not t:
        return False
    if t.endswith("?"):
        return True
    return t.startswith(QUESTION_OPENERS)


all_posts = []
ok_subs, failed_subs = [], []

for sub in SUBREDDITS:
    url = f"https://www.reddit.com/r/{sub}/top/.rss?t=week&limit={PER_SUB_LIMIT}"
    print(f"Fetching r/{sub} ...")
    req = urllib.request.Request(url, headers={
        "User-Agent": UA,
        "Accept": "application/atom+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-GB,en;q=0.9",
    })
    got = 0
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, context=ctx) as response:
                root = ET.fromstring(response.read())
                ns = {"atom": "http://www.w3.org/2005/Atom"}
                for entry in root.findall("atom:entry", ns):
                    title_el = entry.find("atom:title", ns)
                    title = title_el.text if title_el is not None else ""
                    if not title or title.startswith("/u/"):
                        continue
                    link_el = entry.find("atom:link", ns)
                    link = link_el.attrib.get("href", "") if link_el is not None else ""
                    content_el = entry.find("atom:content", ns)
                    raw = content_el.text if content_el is not None else ""
                    clean = ""
                    if raw:
                        dec = html.unescape(raw)
                        dec = re.sub(r"<(?:p|br|div)[^>]*>", "\n", dec)
                        clean = re.sub(r"<[^>]+>", "", dec).strip()
                    updated_el = entry.find("atom:updated", ns)
                    all_posts.append({
                        "subreddit": f"r/{sub}",
                        "title": title.strip(),
                        "selftext": clean,
                        "url": link,
                        "date": (updated_el.text or "")[:10] if updated_el is not None else None,
                        "is_question": looks_like_question(title),
                        # RSS does not expose score or comment count. These were
                        # previously written as the constants 100 and 10.
                        "ups": None,
                        "num_comments": None,
                        "engagement_note": "not available via RSS - do not weigh",
                    })
                    got += 1
                break
        except urllib.error.HTTPError as e:
            # 429 needs a real wait, not 4 seconds. Everything else backs off
            # normally.
            wait = (30 if e.code == 429 else 4) * (attempt + 1)
            label = "rate limited (429)" if e.code == 429 else f"HTTP {e.code}"
            print(f"  attempt {attempt+1} for r/{sub}: {label}. Waiting {wait}s...")
            time.sleep(wait)
        except Exception as e:
            wait = (attempt + 1) * 4
            print(f"  attempt {attempt+1} failed for r/{sub}: {e}. Retrying in {wait}s...")
            time.sleep(wait)
    if got:
        ok_subs.append((sub, got))
    else:
        failed_subs.append(sub)
    time.sleep(SUB_DELAY_SECONDS)

questions = [p for p in all_posts if p["is_question"]]
print("")
print(f"Subreddits responding: {len(ok_subs)}/{len(SUBREDDITS)}")
for sub, n in ok_subs:
    print(f"  r/{sub}: {n} items")
if failed_subs:
    print(f"  FAILED (returned nothing): {', '.join('r/' + s for s in failed_subs)}")
print(f"Total items: {len(all_posts)}  |  phrased as questions: {len(questions)}")

if len(all_posts) < MIN_ITEMS:
    print("=" * 64)
    print(f"FATAL: only {len(all_posts)} item(s) fetched, minimum is {MIN_ITEMS}.")
    if failed_subs:
        print(f"  Subreddits that returned nothing: {', '.join(failed_subs)}")
    print("  Previously this exited 0 with a near-empty file and the pipeline")
    print("  generated posts from almost no source data.")
    print("=" * 64)
    sys.exit(1)

if not questions:
    print("=" * 64)
    print("FATAL: no item is phrased as a question.")
    print("  The community pillar answers a question someone actually asked.")
    print("=" * 64)
    sys.exit(1)

# Questions first, so the selector sees them without the fetcher truncating.
all_posts.sort(key=lambda p: (not p["is_question"],))
with open("./reddit_data.json", "w") as f:
    json.dump(all_posts, f, indent=2)
print(f"Saved {len(all_posts)} items ({len(questions)} questions) to reddit_data.json")
