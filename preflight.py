#!/usr/bin/env python3
"""Check every pillar's supply BEFORE a batch is generated.

    python3 preflight.py            # report only
    python3 preflight.py --refresh  # also run the fetches that need no input
    python3 preflight.py --json     # machine-readable, for a wrapper

Exit codes:
    0  every day in the coming batch will produce a post
    1  at least one day would skip  (a wrapper should stop and ask)
    2  something is structurally broken (bad config, unreadable file)

It reuses sources_loader's own helpers rather than reimplementing the
selection rules, so the verdict cannot drift from what the run will do.
"""
import argparse
import datetime
import glob
import json
import os
import subprocess
import sys
import tomllib

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)

import config_loader          # noqa: E402
import notes_loader           # noqa: E402
import sources_loader as SL   # noqa: E402

WEEKS_LOW = 2   # below this, ask for a month at once rather than one at a time


def age_days(path):
    if not os.path.exists(path):
        return None
    mt = datetime.datetime.fromtimestamp(os.path.getmtime(path))
    return (datetime.datetime.now() - mt).days


# ---------------------------------------------------------------- pillars --
def check_ad_teardown(cfg, used, fmt):
    seen = used.get("ad-teardown", {}) or {}
    files = sorted(glob.glob(os.path.join(SL.TEARDOWN_DIR, "*.json")))
    usable = []
    for p in files:
        try:
            ad = json.load(open(p))
        except Exception:
            continue
        if not SL._supports(ad.get("formats") or ["text", "carousel"], fmt):
            continue
        usable.append(os.path.basename(p))
    unused = [f for f in usable if f not in seen]
    return {
        "left": len(unused), "pool": len(usable),
        "detail": f"{len(files)} file(s) in sources/ad_teardowns/",
        "ask": ("AD POOL EMPTY — Monday will skip.\n"
                "  Give me 4 Meta Ad Library links and I'll add them.\n"
                "  Pick ads that have been running 3+ weeks. Any D2C brand.")
        if not unused else
        ("AD POOL LOW — {n} left, about {n} week(s).\n"
         "  Send 4 Meta Ad Library links and I'll top it up for the month.\n"
         "  Ads running 3+ weeks. Any D2C brand.").format(n=len(unused)),
        "self_fix": None,
    }


def check_benchmark(cfg, used, fmt):
    seen = used.get("benchmark", {}) or {}
    try:
        data = tomllib.load(open(SL.BENCHMARKS_PATH, "rb"))
    except Exception as e:
        return {"left": 0, "pool": 0, "detail": f"benchmarks.toml unreadable: {e}",
                "ask": "sources/benchmarks.toml is unreadable — fix it before running.",
                "self_fix": None, "broken": True}
    entries = data.get("benchmark", []) or []
    usable = [b for b in entries
              if b.get("used") is not True
              and SL._supports(b.get("formats") or ["text"], fmt)]
    unused = [b for b in usable if b.get("id") not in seen]
    return {
        "left": len(unused), "pool": len(usable),
        "detail": f"{len(entries)} entry/entries in sources/benchmarks.toml",
        "ask": ("BENCHMARK POOL EMPTY — Tuesday will skip.\n"
                "  Paste 4 figures from an allowlisted publisher (WordStream,\n"
                "  LocaliQ, Databox, Triple Whale, Statista, Meta newsroom) with\n"
                "  the metric, the year the DATA was gathered, and the sample.\n"
                "  I'll add them to sources/benchmarks.toml.")
        if not unused else
        ("BENCHMARK POOL LOW — {n} left.\n"
         "  Paste 4 more figures from an allowlisted publisher when convenient."
         ).format(n=len(unused)),
        "self_fix": None,
    }


def check_changelog(cfg, used, fmt):
    seen = used.get("update-or-hot-take", {}) or {}
    max_age = cfg.get("source_max_age_days", 14)
    stale = age_days(SL.CHANGELOG_PATH)
    try:
        items = json.load(open(SL.CHANGELOG_PATH))
    except Exception as e:
        return {"left": 0, "pool": 0, "detail": f"changelog_data.json unreadable: {e}",
                "ask": None,
                "self_fix": ("python3 fetch_changelogs.py", "changelog_data.json is missing"),
                "broken": True}
    fresh = [x for x in items if x.get("date") and SL._fresh(x["date"], max_age)]
    unused = [x for x in fresh
              if (x.get("id") or x.get("title", "")[:40]) not in seen]
    substantive = [x for x in unused if SL._substantive_bullets(x.get("body"))]
    self_fix = None
    if stale is not None and stale > 2:
        self_fix = ("python3 fetch_changelogs.py",
                    f"changelog_data.json is {stale} days old")
    return {
        "left": len(substantive), "pool": len(fresh),
        "detail": (f"{len(items)} release(s), {len(fresh)} inside the {max_age}-day "
                   f"window, {len(unused) - len(substantive)} of those are "
                   f"dependency-only bumps"),
        "ask": ("NO SUBSTANTIVE RELEASE — Friday will skip.\n"
                "  Nothing in the window has anything in it but dependency bumps.\n"
                "  Nothing for you to do; a new release has to ship.")
        if not substantive else None,
        "self_fix": self_fix,
    }


def check_community_question(cfg, used, fmt):
    seen = used.get("community-question", {}) or {}
    stale = age_days(SL.REDDIT_PATH)
    try:
        items = json.load(open(SL.REDDIT_PATH))
    except Exception as e:
        return {"left": 0, "pool": 0, "detail": f"reddit_data.json unreadable: {e}",
                "ask": None,
                "self_fix": ("python3 fetch_reddit_rss.py", "reddit_data.json is missing"),
                "broken": True}
    questions = [q for q in items if q.get("is_question")]
    unused = [q for q in questions
              if (q.get("id") or q.get("title", "")[:40]) not in seen]
    self_fix = None
    if stale is not None and stale > 2:
        self_fix = ("python3 fetch_reddit_rss.py",
                    f"reddit_data.json is {stale} days old")
    return {
        "left": len(unused), "pool": len(questions),
        "detail": (f"{len(questions)} question(s) fetched"
                   + (f", data {stale} day(s) old" if stale is not None else "")),
        "ask": ("NO UNUSED QUESTIONS — Thursday will skip.\n"
                "  Nothing for you to do; run the Reddit fetch (below).")
        if not unused else None,
        "self_fix": self_fix,
        "soft": True,   # a pairing still has to be found at run time
    }


def check_build_note(cfg, used, fmt):
    state = notes_loader.load_used_angles()
    used_angles = set(state.get("angles", {}) or {})
    try:
        notes = notes_loader.load_notes()
    except SystemExit:
        return {"left": 0, "pool": 0, "detail": "raw_notes.toml failed to parse",
                "ask": "raw_notes.toml does not parse — fix it before running.",
                "self_fix": None, "broken": True}
    pairs = [(p, a) for p in notes["projects"] for a in p.get("angle", [])
             if SL._supports(a.get("formats"), fmt)]
    unused = [(p, a) for p, a in pairs
              if f"{p['id']}::{a['id']}" not in used_angles]
    return {
        "left": len(unused), "pool": len(pairs),
        "detail": f"{len(pairs)} angle(s) can carry '{fmt}', {len(used_angles)} used overall",
        "ask": ("NO UNUSED ANGLES — Wednesday will skip.\n"
                "  Add a project or angle to raw_notes.toml.")
        if not unused else None,
        "self_fix": None,
    }


CHECKS = {
    "ad-teardown": check_ad_teardown,
    "benchmark": check_benchmark,
    "update-or-hot-take": check_changelog,
    "community-question": check_community_question,
    "build-note": check_build_note,
}


def run(refresh=False, as_json=False):
    try:
        cfg = config_loader.load_config()
    except SystemExit:
        print("PREFLIGHT: pipeline_config.json failed validation. Nothing checked.")
        return 2
    seq = config_loader.build_slot_sequence(cfg)
    used = notes_loader.load_used_sources()
    pillars = cfg.get("pillars") or []

    results, self_fixes = [], []
    for pillar, (fmt, _idx) in zip(pillars, seq):
        fn = CHECKS.get(pillar["id"])
        r = ({"left": 0, "pool": 0, "detail": "no preflight check for this pillar",
              "ask": None, "self_fix": None, "unknown": True}
             if not fn else fn(cfg, used, fmt))
        r.update(id=pillar["id"], day=pillar.get("day", "?"), fmt=fmt)
        results.append(r)
        if r.get("self_fix"):
            self_fixes.append(r["self_fix"])

    if refresh and self_fixes:
        print("REFRESHING what needs no input from you")
        for cmd, why in dict.fromkeys(self_fixes):
            print(f"  {why} -> {cmd}")
            subprocess.run(cmd, shell=True, cwd=BASE)
        print("  re-checking...\n")
        return run(refresh=False, as_json=as_json)

    if as_json:
        print(json.dumps({"results": results,
                          "will_skip": [r["id"] for r in results if r["left"] == 0]},
                         indent=2))
        return 1 if any(r["left"] == 0 for r in results) else 0

    # ---- report ----
    print("=" * 66)
    print(f"PREFLIGHT  {datetime.date.today()}   {len(pillars)} pillars, "
          f"mix {[f'{k}:{v}' for k, v in cfg['format_mix'].items() if v]}")
    print("=" * 66)
    print(f"\n  {'day':4} {'pillar':22} {'fmt':9} {'left':>5}  {'weeks':>5}  supply")
    print("  " + "-" * 72)
    for r in results:
        weeks = r["left"]                      # one item per week
        flag = "SKIP " if r["left"] == 0 else "     "
        print(f"  {r['day']:4} {r['id']:22} {r['fmt']:9} {r['left']:>5}  "
              f"{weeks:>5}  {flag}{r['detail']}")

    will_post = [r for r in results if r["left"] > 0]
    will_skip = [r for r in results if r["left"] == 0]

    print(f"\n  COMING BATCH: {len(will_post)} of {len(results)} days will produce a post.")
    for r in results:
        mark = "post" if r["left"] > 0 else "SKIP"
        why = "" if r["left"] > 0 else "  <- " + (r["ask"] or "pool empty").splitlines()[0]
        print(f"    {r['day']:4} {r['id']:22} {mark}{why}")
    if any(r.get("soft") and r["left"] > 0 for r in results):
        print("\n  Note: community-question also needs a question that PAIRS with one of")
        print("  your angles. Supply being non-zero does not guarantee a pairing.")

    asks = [r for r in results if r["ask"]]
    if asks:
        print("\n" + "-" * 66)
        print("  WHAT I NEED FROM YOU")
        print("-" * 66)
        for r in asks:
            print("\n  " + r["ask"].replace("\n", "\n  "))

    if self_fixes:
        print("\n" + "-" * 66)
        print("  WHAT I CAN FIX WITHOUT YOU")
        print("-" * 66)
        for cmd, why in dict.fromkeys(self_fixes):
            print(f"  {why}")
            print(f"    {cmd}")
        print("\n  Run all of these automatically:")
        print("    python3 preflight.py --refresh")

    low = [r for r in results if 0 < r["left"] < WEEKS_LOW and r["ask"]]
    if low:
        print(f"\n  Runway under {WEEKS_LOW} weeks on: "
              + ", ".join(r["id"] for r in low))
        print("  Worth topping up a month at once rather than one at a time.")

    print("\n" + "=" * 66)
    if will_skip:
        print(f"  VERDICT: {len(will_skip)} pillar(s) would SKIP. "
              f"Fix the asks above, or accept a short batch.")
    else:
        print("  VERDICT: every day is supplied. Safe to generate.")
    print("=" * 66)
    return 1 if will_skip else 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser(add_help=True)
    ap.add_argument("--refresh", action="store_true",
                    help="run the fetches that need no input from you, then re-check")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    a = ap.parse_args()
    sys.exit(run(refresh=a.refresh, as_json=a.json))
