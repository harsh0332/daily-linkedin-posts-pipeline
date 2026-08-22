#!/usr/bin/env python3
"""Add one or more Meta Ad Library ads to the ad-teardown pool.

    python3 add_teardown.py <ad-library-url> [<url> ...]

Starts the adspy backend if it is not already listening, calls /api/extract,
reshapes the response into what sources_loader.load_ad_teardown() reads,
validates it, names the file, and reports how many Mondays are covered.

WHY THIS SCRIPT EXISTS
  1. The API nests scoring under a "score" key. days_running, why_it_works,
     watch_outs, verdict and stage all live in there, while the loader reads
     them at the TOP level. That mapping is encoded below so nobody has to
     rediscover it by diffing two files.
  2. DCO ads carry a template placeholder as `body` ("{{product.brand}}"),
     not copy any human sees. The real creative text is in cards[0]. Handled
     automatically, and announced when it fires.
  3. The adspy venv must NOT live under iCloud Drive. Files there get evicted
     to the cloud and reads time out (Errno 60), which makes uvicorn print its
     banner and never bind the socket. VENV_PY points outside iCloud.
"""
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request

BASE = os.path.dirname(os.path.abspath(__file__))
POOL = os.path.join(BASE, "sources", "ad_teardowns")
USED = os.path.join(BASE, "used_sources.json")
CONFIG = os.path.join(BASE, "pipeline_config.json")

ADSPY_DIR = os.path.expanduser("~/Desktop/adspy")
VENV_PY = os.path.expanduser("~/.venvs/adspy/bin/python")   # outside iCloud, deliberately
SERVER_LOG = "/tmp/adspy_server.log"
STARTUP_TIMEOUT_S = 60

# score{} -> top level. The loader reads these where the Flipkart file has them.
SCORE_TO_TOPLEVEL = ("days_running", "verdict", "stage", "why_it_works", "watch_outs")

# What load_ad_teardown() cannot do without.
REQUIRED = {
    "page_name":    "the advertiser's name",
    "body":         "the ad's own copy",
    "days_running": "integer; the only figure the post may cite",
    "is_active":    "true/false; stated as fact in the post",
}

TEMPLATE_RE = re.compile(r"^\s*\{\{.*\}\}\s*$")


def cfg_urls():
    try:
        a = (json.load(open(CONFIG)) or {}).get("adspy") or {}
    except Exception:
        a = {}
    base = a.get("base_url", "http://127.0.0.1:8000").rstrip("/")
    return base, base + a.get("extract_path", "/api/extract")


def health_ok(base, timeout=3):
    try:
        with urllib.request.urlopen(base + "/api/health", timeout=timeout) as r:
            return r.status == 200
    except Exception:
        return False


def ensure_server(base):
    if health_ok(base):
        print(f"adspy already listening at {base}")
        return True
    if not base.startswith(("http://127.0.0.1", "http://localhost")):
        print(f"FATAL: {base} is not responding and is not local, so it cannot be started here.")
        return False
    if not os.path.exists(VENV_PY):
        print(f"FATAL: {VENV_PY} does not exist.")
        print("  Build it OUTSIDE iCloud Drive:")
        print("    python3 -m venv ~/.venvs/adspy")
        print(f"    ~/.venvs/adspy/bin/pip install -r {ADSPY_DIR}/requirements.txt")
        return False
    if not os.path.isdir(ADSPY_DIR):
        print(f"FATAL: adspy not found at {ADSPY_DIR}")
        return False

    port = base.rsplit(":", 1)[-1] or "8000"
    print(f"adspy not responding. Starting it ({VENV_PY}, port {port})...")
    with open(SERVER_LOG, "ab") as log:
        subprocess.Popen(
            [VENV_PY, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", port],
            cwd=ADSPY_DIR, stdout=log, stderr=log, start_new_session=True)

    deadline = time.time() + STARTUP_TIMEOUT_S
    while time.time() < deadline:
        if health_ok(base, timeout=2):
            print(f"  up after {STARTUP_TIMEOUT_S - int(deadline - time.time())}s "
                  f"(verified by /api/health, not by the banner)")
            return True
        time.sleep(1)

    print(f"FATAL: adspy did not answer /api/health within {STARTUP_TIMEOUT_S}s.")
    print(f"  Last lines of {SERVER_LOG}:")
    try:
        for line in open(SERVER_LOG).read().splitlines()[-12:]:
            print("    " + line)
    except OSError:
        print("    (log unreadable)")
    print("  If it printed its banner but never bound the socket, the venv is")
    print("  probably evicted to iCloud - check for 'dataless' files:")
    print("    ls -lO ~/.venvs/adspy/lib/python*/site-packages/anthropic/_client.py")
    return False


def extract(url, endpoint):
    body = json.dumps({"url": url}).encode()
    req = urllib.request.Request(endpoint, data=body,
                                 headers={"Content-Type": "application/json"},
                                 method="POST")
    with urllib.request.urlopen(req, timeout=180) as r:
        return json.loads(r.read().decode())


def reshape(d):
    """API shape -> loader shape. Returns (ad, notes)."""
    notes = []
    ad = dict(d)
    score = ad.pop("score", None) or {}
    for k in SCORE_TO_TOPLEVEL:
        if k in score:
            ad[k] = score[k]
    if score:
        ad["score_meta"] = {k: v for k, v in score.items() if k not in SCORE_TO_TOPLEVEL}
        notes.append(f"flattened {len(SCORE_TO_TOPLEVEL)} field(s) out of score{{}}")

    body = (ad.get("body") or "").strip()
    if TEMPLATE_RE.match(body):
        card = (ad.get("cards") or [{}])[0]
        real = " ".join(x for x in (card.get("title"), card.get("body")) if x).strip()
        if real:
            ad["body_template"] = body
            ad["body"] = real
            notes.append(f"DCO ad: body was the placeholder {body!r}; used cards[0] "
                         f"as the real copy ({len(real)} chars) and kept the template "
                         f"in body_template")
        else:
            notes.append(f"DCO ad: body is the placeholder {body!r} and cards[0] "
                         f"has no usable text - this will fail validation")

    ad.pop("cached_at", None)
    ad.pop("cache_hit", None)
    ad.setdefault("formats", ["text", "carousel"])
    return ad, notes


def validate(ad):
    errs = []
    for f, why in REQUIRED.items():
        v = ad.get(f)
        if v is None or (isinstance(v, str) and not v.strip()):
            errs.append(f"missing '{f}' ({why})")
    if ad.get("days_running") is not None and not isinstance(ad["days_running"], int):
        errs.append(f"'days_running' must be an integer, got {type(ad['days_running']).__name__}")
    if TEMPLATE_RE.match((ad.get("body") or "").strip()):
        errs.append("'body' is still a template placeholder, not real copy")
    for f in ("why_it_works", "watch_outs"):
        if f in ad and not isinstance(ad[f], list):
            errs.append(f"'{f}' must be a list")
    return errs


def filename(ad):
    brand = re.sub(r"[^a-z0-9]+", "_", (ad.get("page_name") or "unknown").lower()).strip("_")
    return f"ad_{brand or 'unknown'}_{ad.get('ad_id') or 'noid'}.json"


def runway():
    used = {}
    if os.path.exists(USED):
        try:
            used = (json.load(open(USED)) or {}).get("ad-teardown", {}) or {}
        except Exception:
            pass
    import glob
    files = [os.path.basename(p) for p in glob.glob(os.path.join(POOL, "*.json"))]
    unused = [f for f in files if f not in used]
    return len(files), len(unused)


def main(urls):
    if not urls:
        print(__doc__)
        return 2
    base, endpoint = cfg_urls()
    if not ensure_server(base):
        return 1
    os.makedirs(POOL, exist_ok=True)

    added, failed = 0, 0
    for url in urls:
        print(f"\n--- {url}")
        try:
            raw = extract(url, endpoint)
        except urllib.error.HTTPError as e:
            print(f"  FAILED: HTTP {e.code} {e.reason}")
            try:
                print(f"    {e.read().decode()[:250]}")
            except Exception:
                pass
            failed += 1
            continue
        except Exception as e:
            print(f"  FAILED: {type(e).__name__}: {e}")
            failed += 1
            continue

        ad, notes = reshape(raw)
        for n in notes:
            print(f"  note: {n}")
        errs = validate(ad)
        if errs:
            print("  REFUSING TO WRITE - the loader would fail on this:")
            for e in errs:
                print(f"    - {e}")
            failed += 1
            continue

        name = filename(ad)
        path = os.path.join(POOL, name)
        if os.path.exists(path):
            print(f"  already in the pool: {name} (not overwritten)")
            continue
        with open(path, "w") as f:
            json.dump(ad, f, indent=2, ensure_ascii=False)
        print(f"  saved {name}")
        print(f"    {ad.get('page_name')} | {ad.get('days_running')} days | "
              f"active={ad.get('is_active')} | {len(ad.get('why_it_works') or [])} observations")
        added += 1

    total, unused = runway()
    print(f"\n{'='*58}")
    print(f"added {added}, failed {failed}")
    print(f"pool: {total} ad(s), {unused} unused")
    print(f"RUNWAY: {unused} Monday(s) covered"
          + ("" if unused else "  -- ad-teardown will SKIP Monday"))
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
