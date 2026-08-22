#!/usr/bin/env python3
"""Validate sources/ad_teardowns/ and report how much runway the pool has.

Read-only. Run:  python3 validate_ad_pool.py

Checks every JSON file for the fields load_ad_teardown() actually reads, then
cross-references used_sources.json so you can see how many teardowns are left
before the ad-teardown pillar starts skipping Mondays.
"""
import glob
import json
import os
import sys

BASE = os.path.dirname(os.path.abspath(__file__))
POOL = os.path.join(BASE, "sources", "ad_teardowns")
USED = os.path.join(BASE, "used_sources.json")

# Fields load_ad_teardown() reads. Missing REQUIRED means the post cannot be
# written honestly; missing OPTIONAL only makes it thinner.
REQUIRED = {
    "page_name":    "the advertiser's name, used in the headline",
    "body":         "the ad's own copy - the post has nothing to describe without it",
    "days_running": "an integer; the only figure the post may cite, and it must "
                    "carry a Meta Ad Library citation",
    "is_active":    "true/false; stated as fact in the post",
}
OPTIONAL = {
    "cta_text":     "or cta_type - the closing CTA",
    "cta_type":     "fallback if cta_text is absent",
    "why_it_works": "list of {text}; the 'FACT - opinion' lines, opinion half stripped",
    "watch_outs":   "list of strings; feeds the 'what I'd watch' beat",
    "formats":      "list; defaults to [text, carousel] if absent",
}


def check(path):
    name = os.path.basename(path)
    try:
        ad = json.load(open(path))
    except Exception as e:
        return name, [f"not valid JSON: {e}"], []
    if not isinstance(ad, dict):
        return name, ["top level is not a JSON object"], []

    errs, warns = [], []
    for f, why in REQUIRED.items():
        v = ad.get(f)
        if v is None or (isinstance(v, str) and not v.strip()):
            errs.append(f"missing REQUIRED '{f}' ({why})")
    d = ad.get("days_running")
    if d is not None and not isinstance(d, int):
        errs.append(f"'days_running' must be an integer, got {type(d).__name__}")
    if not (ad.get("cta_text") or ad.get("cta_type")):
        warns.append("no cta_text or cta_type")
    for f in ("why_it_works", "watch_outs"):
        if f in ad and not isinstance(ad[f], list):
            errs.append(f"'{f}' must be a list")
    if not ad.get("why_it_works"):
        warns.append("no why_it_works - the deck loses its structural observations")
    fmts = ad.get("formats")
    if fmts is not None and not isinstance(fmts, list):
        errs.append("'formats' must be a list")
    return name, errs, warns


def main():
    if not os.path.isdir(POOL):
        print(f"FATAL: {POOL} does not exist.")
        return 1
    files = sorted(glob.glob(os.path.join(POOL, "*.json")))
    if not files:
        print(f"Pool is EMPTY: no .json files in {POOL}")
        return 1

    used = {}
    if os.path.exists(USED):
        try:
            used = (json.load(open(USED)) or {}).get("ad-teardown", {}) or {}
        except Exception as e:
            print(f"warning: used_sources.json unreadable ({e}); "
                  f"treating every ad as unused.\n")

    valid, invalid, unused = [], [], []
    print(f"Checking {len(files)} file(s) in sources/ad_teardowns/\n")
    for p in files:
        name, errs, warns = check(p)
        mark = "USED " + used[name] if name in used else "unused"
        if errs:
            invalid.append(name)
            print(f"  [INVALID] {name}  ({mark})")
            for e in errs:
                print(f"              {e}")
        else:
            valid.append(name)
            print(f"  [ok]      {name}  ({mark})")
            if name not in used:
                unused.append(name)
        for w in warns:
            print(f"              note: {w}")

    print()
    print(f"  valid:            {len(valid)}")
    print(f"  invalid:          {len(invalid)}")
    print(f"  already used:     {len([n for n in valid if n in used])}")
    print(f"  USABLE RUNWAY:    {len(unused)} teardown(s) left")
    if unused:
        weeks = len(unused)
        print(f"                    at one Monday a week, that is {weeks} week(s).")
    else:
        print("                    ad-teardown will SKIP Monday until you add one.")
    return 1 if invalid else 0


if __name__ == "__main__":
    sys.exit(main())
