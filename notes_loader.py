"""Loader, validator and angle-selector for raw_notes.toml (Phase 3).

raw_notes.toml is the only place the pipeline holds anything true about Harsh's
own work. Everything here fails loudly: a malformed entry aborts rather than
being skipped, because a silently-skipped project is indistinguishable from a
project that was never written down.

Selection draws ONE ANGLE, not a whole project, so a single project yields
several distinct posts. Angles are used before any is reused. A thesis (the
recurring lesson several projects share) is rate-limited by a cooldown rather
than consumed once: a position is built by restating it with different
evidence, but six posts making the same point in twelve is repetition.
"""

import datetime
import json
import os
import sys
import tomllib

NOTES_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "raw_notes.toml")
USED_ANGLES_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "used_angles.json")

REQUIRED_PROJECT_FIELDS = ["id", "sector", "problem", "built", "surprise", "changed"]
REQUIRED_ANGLE_FIELDS = ["id", "claim", "detail", "formats"]
MIN_DETAIL_CHARS = 40


def _abort(title, detail=""):
    print("=" * 64)
    print(f"FATAL: {title}")
    if detail:
        print(detail)
    print("Nothing has been generated. Aborting.")
    print("=" * 64)
    sys.exit(1)


def load_notes(path=None):
    """Parse and validate raw_notes.toml. Aborts on anything malformed."""
    p = path or NOTES_PATH
    if not os.path.exists(p):
        _abort(
            "raw_notes.toml is missing.",
            f"  Expected: {p}\n"
            "  It holds the only material the pipeline knows to be true.\n"
            "  Without it the Build Note pillar has nothing to write from.",
        )
    try:
        with open(p, "rb") as f:
            data = tomllib.load(f)
    except tomllib.TOMLDecodeError as e:
        _abort("raw_notes.toml is not valid TOML.", f"  {e}")

    theses = {t.get("id"): t for t in data.get("thesis", []) if isinstance(t, dict)}
    for tid, t in theses.items():
        if not tid or not str(t.get("statement", "")).strip():
            _abort("a [[thesis]] entry is missing 'id' or 'statement'.",
                   f"  Offending entry: {t}")

    projects = data.get("project", [])
    if not isinstance(projects, list):
        _abort("raw_notes.toml: [[project]] must be a list of tables.")

    problems = []
    usable = []
    seen_project_ids = set()

    for idx, proj in enumerate(projects, 1):
        pid = str(proj.get("id", "")).strip()
        label = pid or f"<project #{idx} with no id>"

        for field in REQUIRED_PROJECT_FIELDS:
            if not str(proj.get(field, "")).strip():
                problems.append(f"project '{label}': missing or empty '{field}'")

        if pid and pid in seen_project_ids:
            problems.append(f"project '{label}': duplicate id")
        seen_project_ids.add(pid)

        angles = proj.get("angle", [])
        if not angles:
            problems.append(f"project '{label}': no [[project.angle]] entries")

        seen_angle_ids = set()
        for a_idx, ang in enumerate(angles, 1):
            aid = str(ang.get("id", "")).strip()
            alabel = aid or f"<angle #{a_idx}>"
            for field in REQUIRED_ANGLE_FIELDS:
                if field == "formats":
                    if not isinstance(ang.get("formats"), list) or not ang.get("formats"):
                        problems.append(
                            f"project '{label}' angle '{alabel}': 'formats' must be a non-empty list, e.g. [\"text\", \"carousel\"]")
                elif not str(ang.get(field, "")).strip():
                    problems.append(f"project '{label}' angle '{alabel}': missing or empty '{field}'")
            if aid and aid in seen_angle_ids:
                problems.append(f"project '{label}': duplicate angle id '{aid}'")
            seen_angle_ids.add(aid)

            detail = str(ang.get("detail", "")).strip()
            if detail and len(detail) < MIN_DETAIL_CHARS:
                problems.append(
                    f"project '{label}' angle '{alabel}': 'detail' is {len(detail)} chars. "
                    f"It is the attested fact a post is allowed to state, so it needs at least "
                    f"{MIN_DETAIL_CHARS}.")

            th = str(ang.get("thesis", "")).strip()
            if th and th not in theses:
                problems.append(
                    f"project '{label}' angle '{alabel}': thesis '{th}' is not declared in any [[thesis]]")

        if proj.get("example") is True:
            continue  # template placeholder, validated but never used
        usable.append(proj)

    if problems:
        _abort(
            f"raw_notes.toml has {len(problems)} problem(s).",
            "\n".join(f"    - {p}" for p in problems)
            + "\n\n  Nothing is skipped silently: fix these and re-run.",
        )

    return {"theses": theses, "projects": usable,
            "example_count": len(projects) - len(usable)}


def load_used_angles(path=None):
    p = path or USED_ANGLES_PATH
    if not os.path.exists(p):
        return {"angles": {}, "theses": {}}
    try:
        with open(p) as f:
            d = json.load(f)
    except Exception as e:
        _abort("used_angles.json is not valid JSON.",
               f"  {e}\n  Delete it to start the rotation over, or fix it by hand.")
    d.setdefault("angles", {})
    d.setdefault("theses", {})
    return d


def save_used_angles(state, path=None):
    """Persist angle state. Keys starting with "_" are batch scratch (e.g.
    "_batch_keys", the set of angles already claimed during this run) and are
    never written: they are not history, and a set is not JSON anyway."""
    persist = {k: v for k, v in state.items() if not k.startswith("_")}
    with open(path or USED_ANGLES_PATH, "w") as f:
        json.dump(persist, f, indent=2, sort_keys=True)


# ---------------------------------------------------------------------------
# 2026-08-21: used_sources.json. Same shape as used_angles.json, but it records
# the SOURCE ITEM each pillar consumed - which ad was torn down, which benchmark
# figure shipped, which changelog release, which Reddit question.
#
# Why it exists: build-note rotated because select_angle() consults history.
# The other four pillars had no history at all and re-picked item [0] of a
# fixed pool every run. Measured on 2026-08-21 by resolving every pillar twice:
# ad-teardown, benchmark, update-or-hot-take and community-question all returned
# an identical item. The Flipkart teardown published on 17 August came back on
# the 21st, same ad, same 34 days, same 202 characters.
USED_SOURCES_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "used_sources.json")


def load_used_sources(path=None):
    p = path or USED_SOURCES_PATH
    if not os.path.exists(p):
        return {}
    try:
        data = json.load(open(p))
    except Exception as e:
        _abort("used_sources.json is not valid JSON.",
               f"  {e}\n"
               "  Fix or delete it. Deleting it means every pillar forgets what\n"
               "  it has already used and may repeat a post.")
    return data if isinstance(data, dict) else {}


def save_used_sources(state, path=None):
    persist = {k: v for k, v in state.items() if not k.startswith("_")}
    with open(path or USED_SOURCES_PATH, "w") as f:
        json.dump(persist, f, indent=2, sort_keys=True)


def record_source(state, pillar_id, source_key, when=None):
    """Mark one source item as consumed by one pillar."""
    if not pillar_id or not source_key:
        return
    stamp = (when or datetime.date.today()).isoformat()
    state.setdefault(pillar_id, {})[str(source_key)] = stamp


def source_used(used, pillar_id, source_key):
    return str(source_key) in (used.get(pillar_id) or {})


def _thesis_recent(state, thesis_id, cooldown):
    """True if this thesis was used within the last `cooldown` recorded posts."""
    if not thesis_id:
        return False
    all_uses = []
    for tid, stamps in state.get("theses", {}).items():
        for s in stamps:
            all_uses.append((s, tid))
    all_uses.sort(reverse=True)
    return thesis_id in {tid for _, tid in all_uses[:cooldown]}


def select_angle(notes, state, wanted_format, cooldown=4, exclude_keys=()):
    """Pick one unused angle that can carry `wanted_format`.

    Preference order:
      1. never-used angles whose thesis is outside the cooldown window
      2. never-used angles regardless of thesis
      3. least-recently-used angles (only once every angle has been used)
    Returns (project, angle, key) or None.
    """
    candidates = []
    for proj in notes["projects"]:
        for ang in proj.get("angle", []):
            fmts = [str(f).lower() for f in ang.get("formats", [])]
            if wanted_format not in fmts and "either" not in fmts:
                continue
            key = f"{proj['id']}::{ang['id']}"
            if key in exclude_keys:
                continue
            candidates.append((proj, ang, key))

    if not candidates:
        return None

    unused = [c for c in candidates if c[2] not in state["angles"]]
    if unused:
        fresh = [c for c in unused if not _thesis_recent(state, c[1].get("thesis"), cooldown)]
        pool = fresh or unused
        return pool[0]

    # every angle has been used at least once - fall back to least recent
    candidates.sort(key=lambda c: state["angles"].get(c[2], ""))
    return candidates[0]


def record_angle(state, key, thesis_id, when=None):
    stamp = (when or datetime.date.today()).isoformat()
    state["angles"][key] = stamp
    if thesis_id:
        state["theses"].setdefault(thesis_id, []).append(stamp)
    return state


def attested_details(project, angle):
    """The strings a post drawing on this angle is permitted to state as fact.

    This is what the Phase 2 claims checker is given so it can tell a true
    first-person claim from an invented one.
    """
    return [str(x).strip() for x in (
        angle.get("detail", ""), angle.get("claim", ""),
        project.get("problem", ""), project.get("built", ""),
        project.get("surprise", ""), project.get("changed", ""),
    ) if str(x).strip()]
