"""Loader + validator for pipeline_config.json (Python side).

Mirror of config_loader.cjs. Both read the SAME file; neither re-declares any
value. If you change the validation rules here, change them there too.
"""

import json
import os
import sys

CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "pipeline_config.json")


def _abort(title, detail=""):
    print("=" * 64)
    print(f"FATAL: {title}")
    if detail:
        print(detail)
    print("Nothing has been generated or scheduled. Aborting.")
    print("=" * 64)
    sys.exit(1)


def min_weekdays_in_window(days):
    """Fewest Mon-Fri days in any window of `days` consecutive calendar days.

    Computed exactly by trying all seven possible start weekdays rather than
    with a formula, so it cannot be subtly wrong.
    """
    worst = None
    for start in range(7):  # 0 = Monday
        count = sum(1 for i in range(days) if (start + i) % 7 < 5)
        worst = count if worst is None else min(worst, count)
    return worst or 0


def load_config(path=None):
    p = path or CONFIG_PATH
    if not os.path.exists(p):
        _abort("pipeline_config.json is missing.", f"  Expected: {p}")
    try:
        with open(p) as f:
            cfg = json.load(f)
    except Exception as e:
        _abort("pipeline_config.json is not valid JSON.", f"  {e}")

    posts = cfg.get("posts_per_batch")
    horizon = cfg.get("batch_horizon_days")
    mix = cfg.get("format_mix") or {}
    order = cfg.get("format_order") or []
    slots = cfg.get("time_slots") or []

    if not isinstance(posts, int) or posts < 0:
        _abort("posts_per_batch must be a non-negative integer.", f"  Got: {posts!r}")
    if not isinstance(horizon, int) or horizon < 1:
        _abort("batch_horizon_days must be a positive integer.", f"  Got: {horizon!r}")
    if not isinstance(slots, list) or not slots:
        _abort("time_slots must be a non-empty list.", f"  Got: {slots!r}")

    # RULE 1 — the mix must add up to the batch size.
    total = sum(int(v) for v in mix.values())
    if total != posts:
        _abort(
            "format_mix does not sum to posts_per_batch.",
            f"  format_mix: {mix}\n"
            f"  sum: {total}\n"
            f"  posts_per_batch: {posts}\n"
            "  Fix pipeline_config.json so the two agree.",
        )

    # RULE 2 — there must be enough slots to place every post.
    # With weekdays_only, capacity is the WORST-CASE weekday count in a window
    # of `horizon` calendar days (worst case = the window starting on a Saturday).
    weekdays_only = bool(cfg.get("weekdays_only"))
    usable_days = min_weekdays_in_window(horizon) if weekdays_only else horizon
    capacity = usable_days * len(slots)
    if capacity < posts:
        _abort(
            "not enough posting slots for the batch.",
            f"  batch_horizon_days: {horizon}"
            + (f" (worst case {usable_days} weekdays)" if weekdays_only else "")
            + f"\n  time_slots: {len(slots)}\n"
            f"  capacity: {capacity}\n"
            f"  posts_per_batch: {posts}\n"
            "  Widen batch_horizon_days or add a time slot.",
        )

    # RULE 4 (Phase 3) — one pillar per post, and every source must be known.
    KNOWN_SOURCES = {"ad_teardown", "benchmark", "raw_notes",
                     "reddit_questions", "changelog"}
    pillars = cfg.get("pillars") or []
    if pillars:
        if len(pillars) != posts:
            _abort(
                "pillars does not match posts_per_batch.",
                f"  pillars: {len(pillars)}\n  posts_per_batch: {posts}\n"
                "  One pillar per post: a batch cannot have a post with no source.",
            )
        bad = [p_["source"] for p_ in pillars if p_.get("source") not in KNOWN_SOURCES]
        if bad:
            _abort("pillars reference unknown source(s).",
                   f"  Unknown: {bad}\n  Known: {sorted(KNOWN_SOURCES)}")
        missing_keys = [i for i, p_ in enumerate(pillars, 1)
                        if not all(p_.get(k) for k in ("day", "id", "source"))]
        if missing_keys:
            _abort("pillar entries missing day/id/source.", f"  Entry number(s): {missing_keys}")

    # RULE 3 — every format in the mix must appear in the ordering.
    missing = [k for k in mix if k not in order]
    if missing:
        _abort("format_order is missing formats present in format_mix.", f"  Missing: {missing}")

    # ---- Phase 3e: provider config -------------------------------------------
    # base_url, model and the key's variable NAME live here so the provider or
    # the model can be swapped without touching code. The key VALUE is never
    # loaded into config, so it cannot be logged by anything that dumps cfg.
    llm = cfg.get("llm")
    if not isinstance(llm, dict):
        _abort("llm block is missing from pipeline_config.json.",
               '  Expected: {"llm": {"base_url": ..., "model": ..., "api_key_env": ...}}')
    for field in ("base_url", "model", "api_key_env"):
        val = llm.get(field)
        if not isinstance(val, str) or not val.strip():
            _abort(f"llm.{field} must be a non-empty string.", f"  Got: {val!r}")
    if not llm["base_url"].startswith("https://"):
        _abort("llm.base_url must be https.",
               f"  Got: {llm['base_url']!r}\n"
               "  The API key is sent on this connection.")
    if llm["base_url"].rstrip("/").endswith("/chat/completions"):
        _abort("llm.base_url must be the API root, not the endpoint path.",
               f"  Got: {llm['base_url']!r}\n"
               "  The generator appends /chat/completions itself.")
    if llm["api_key_env"].strip() != llm["api_key_env"]:
        _abort("llm.api_key_env has surrounding whitespace.", f"  Got: {llm['api_key_env']!r}")

    return cfg


def build_slot_sequence(cfg):
    """Round-robin over format_order, skipping exhausted formats.

    carousel:3 infographic:3 poll:2 text:3 ->
      carousel, infographic, poll, text,
      carousel, infographic, poll, text,
      carousel, infographic,       text
    Returns [(format_name, per_format_index_starting_at_1), ...]
    """
    mix = dict(cfg["format_mix"])
    order = [f for f in cfg["format_order"] if mix.get(f, 0) > 0]
    remaining = {f: int(mix[f]) for f in order}
    counters = {f: 0 for f in order}
    seq = []
    while sum(remaining.values()) > 0:
        for f in order:
            if remaining[f] > 0:
                remaining[f] -= 1
                counters[f] += 1
                seq.append((f, counters[f]))
    return seq
