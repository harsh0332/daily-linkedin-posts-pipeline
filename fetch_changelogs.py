"""Phase 3: official changelogs for the Friday pillar, each carrying its own date.

Replaces ai_news_data.json, which had been stale since 2026-07-25 and was still
being fed to the planner labelled "Fresh AI & Marketing News".

FETCHED AUTOMATICALLY
  n8n releases - GitHub's public releases API. Real JSON, real published_at.

PASTED BY HAND (sources/changelog_manual.toml)
  Meta newsroom / Meta for Business, and the WhatsApp Cloud API changelog.
  Neither publishes a stable machine-readable feed. Scraping them from this
  pipeline is not worth the surface, and inventing a date is worse than having
  none, so they are manual with an explicit date field.

Every item carries `date`. sources_loader refuses anything older than
source_max_age_days, and refuses anything with no date at all.
"""

import datetime
import json
import os
import ssl
import sys
import tomllib
import urllib.request

from config_loader import load_config

CONFIG = load_config()
MAX_AGE = CONFIG.get("source_max_age_days", 14)
MANUAL_PATH = os.path.join("sources", "changelog_manual.toml")

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

items = []

# ---- n8n release notes, GitHub public API ----------------------------------
try:
    req = urllib.request.Request(
        "https://api.github.com/repos/n8n-io/n8n/releases?per_page=10",
        headers={"User-Agent": "LinkedInPipelineBot/1.0", "Accept": "application/vnd.github+json"})
    with urllib.request.urlopen(req, context=ctx, timeout=30) as r:
        for rel in json.loads(r.read().decode()):
            if rel.get("draft"):
                continue
            items.append({
                "id": f"n8n-{rel.get('tag_name')}",
                "source": "n8n",
                "title": f"n8n {rel.get('tag_name')}",
                "body": (rel.get("body") or "")[:1500],
                "date": (rel.get("published_at") or "")[:10] or None,
            })
    print(f"n8n releases fetched: {len([i for i in items if i['source']=='n8n'])}")
except Exception as e:
    print(f"WARNING: could not fetch n8n releases: {e}")

# ---- manual entries --------------------------------------------------------
if os.path.exists(MANUAL_PATH):
    try:
        with open(MANUAL_PATH, "rb") as f:
            manual = tomllib.load(f)
    except tomllib.TOMLDecodeError as e:
        print("=" * 64)
        print(f"FATAL: {MANUAL_PATH} is not valid TOML.\n  {e}")
        print("=" * 64)
        sys.exit(1)
    for i, m in enumerate(manual.get("entry", []), 1):
        missing = [k for k in ("id", "source", "title", "date") if not str(m.get(k, "")).strip()]
        if missing:
            print("=" * 64)
            print(f"FATAL: {MANUAL_PATH} entry #{i} is missing {missing}.")
            print("  Every item fed to the planner as current must carry its own date.")
            print("=" * 64)
            sys.exit(1)
        items.append({k: m.get(k) for k in ("id", "source", "title", "body", "date")})
    print(f"Manual entries loaded: {len(manual.get('entry', []))}")
else:
    print(f"No {MANUAL_PATH} (optional).")

undated = [i for i in items if not i.get("date")]
for i in undated:
    print(f"  refusing undated item: {i.get('id')}")
items = [i for i in items if i.get("date")]

today = datetime.date.today()
fresh = [i for i in items
         if (today - datetime.date.fromisoformat(i["date"])).days <= MAX_AGE]
items.sort(key=lambda i: i["date"], reverse=True)

with open("changelog_data.json", "w") as f:
    json.dump(items, f, indent=2)

print(f"Saved {len(items)} dated item(s); {len(fresh)} within {MAX_AGE} days -> changelog_data.json")
if not fresh:
    print(f"NOTE: nothing is within {MAX_AGE} days. The Friday pillar will abort,")
    print("      which is correct: a month-old release is not an update.")
