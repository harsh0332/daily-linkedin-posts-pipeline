"""Phase 3: resolve each pillar to real material, or fail loudly.

PILLAR AND FORMAT ARE INDEPENDENT AXES.
A pillar says WHERE the material comes from. The format (carousel or text) comes
from format_mix, unchanged from Phase 1. Every item a source returns declares
which formats it can carry, and the resolver picks an item that matches the
slot's format. If a pillar has nothing that can carry the required format, the
run ABORTS naming the pillar and the format. It never swaps to another pillar:
a silent swap would mean Monday's ad teardown quietly becoming a second build
note, which is exactly the "whatever surfaced today" behaviour this replaces.
"""

import datetime
import glob
import json
import os
import re
import sys
import tomllib

import notes_loader

# Injected by generate_all_content at import time (circular otherwise).
LLM = None

BASE = os.path.dirname(os.path.abspath(__file__))
TEARDOWN_DIR = os.path.join(BASE, "sources", "ad_teardowns")
BENCHMARKS_PATH = os.path.join(BASE, "sources", "benchmarks.toml")
CHANGELOG_PATH = os.path.join(BASE, "changelog_data.json")
REDDIT_PATH = os.path.join(BASE, "reddit_data.json")


class PillarUnavailable(Exception):
    """One pillar could not produce material. The batch continues without it.

    Phase 3c: this used to sys.exit(1). Four of six measured runs lost all
    five posts because one pillar could not produce, and nothing is scheduled
    at generation time, so there was never anything to protect. The day is
    dropped, reported, and carried into the Slack review. The pillar is still
    never swapped for another: that would silently change what the batch is.
    """

    def __init__(self, pillar, title, detail=""):
        self.pillar = pillar
        self.title = title
        self.detail = detail
        super().__init__(f"{pillar}: {title}")


def _abort(pillar, title, detail=""):
    raise PillarUnavailable(pillar, title, detail)


def _fresh(iso_date, max_age_days):
    """True if the item carries a date within the window."""
    if not iso_date:
        return False
    try:
        d = datetime.date.fromisoformat(str(iso_date)[:10])
    except ValueError:
        return False
    return (datetime.date.today() - d).days <= max_age_days


def _supports(item_formats, wanted):
    f = [str(x).lower() for x in (item_formats or [])]
    return wanted in f or "either" in f


# ---------------------------------------------------------------- raw_notes --
def load_build_note(fmt, cfg, state):
    notes = notes_loader.load_notes()
    if not notes["projects"]:
        _abort("build-note",
               "raw_notes.toml has no usable projects.",
               f"  {notes['example_count']} example block(s) found - those are never used.\n"
               "  Add real projects before this pillar can write anything.")
    picked = notes_loader.select_angle(
        notes, state, fmt, cooldown=cfg.get("thesis_cooldown", 4),
        exclude_keys=state.get("_batch_keys", set()))
    if not picked:
        _abort("build-note",
               f"no angle in raw_notes.toml can carry format '{fmt}'.",
               "  Add \"%s\" to an angle's formats list." % fmt)
    project, angle, key = picked
    state.setdefault("_batch_keys", set()).add(key)
    return {
        "pillar": "build-note",
        "source": "raw_notes.toml",
        "reference": f"{project['id']}::{angle['id']}",
        "headline": angle["claim"],
        "material": "\n\n".join([
            "THESE ARE MY NOTES, NOT A SLIDE TEMPLATE. The headings below are "
            "how I filed the material. Never use them as slide labels and "
            "never echo them as words. A carousel that opens its slides with "
            "PROBLEM / BUILT / CHALLENGE / SOLUTION / RESULT / LESSON reads as "
            "a form someone filled in. Let each slide carry one beat of the "
            "story in plain sentences, so the slides read as consecutive "
            "thoughts rather than fields.",

            "WHOSE BUSINESS THIS IS. The client is a client. Their customers, "
            "their distributors, their dealers and their sales team are "
            "THEIRS, not mine. Never write \"our distributor\", \"our "
            "customers\" or \"our sales team\" about a client's business. I "
            "am the person who built the thing: say \"a distributor I built "
            "this for\", \"the client's sales team\", \"their dealers\". "
            "I may say \"we\" only about the work itself, and \"I\" is "
            "usually better. Name the sector, never the client.",

            "NO MAGNITUDE I DID NOT RECORD. Describe what happened in the "
            "terms below and no stronger. If the notes say a distributor got "
            "more messages than they could handle, that is a volume problem, "
            "not a measured increase: \"surged\", \"doubled\", \"exploded\", "
            "\"skyrocketed\" and the like assert a size of change nobody "
            "measured, and are rejected in code. \"More than they could "
            "handle\" is the claim. Keep it.",

            f"THE SITUATION: {project['problem'].strip()}",
            "NAME WHAT YOU BUILT, EVERY TIME. \"I built a solution\", \"I "
            "created a system\", \"I put together a tool\" name nothing and "
            "are rejected as unverifiable, because nothing in the notes says "
            "\"a solution\". Say the actual thing and the actual stack: \"I "
            "built a WhatsApp automation on n8n\". The specifics below are "
            "the post's whole value; a vague paraphrase throws them away.",

            f"WHAT I BUILT: {project['built'].strip()}",
            f"WHAT SURPRISED ME: {project['surprise'].strip()}",
            f"WHAT CHANGED: {project['changed'].strip()}",
            f"THE ANGLE FOR THIS POST: {angle['detail'].strip()}",
        ]),
        "attested": notes_loader.attested_details(project, angle),
        "angle_key": key,
        "thesis": angle.get("thesis"),
        "sector": project.get("sector", ""),
    }


def _adspy_url(cfg):
    a = (cfg or {}).get("adspy") or {}
    return (a.get("base_url", "http://localhost:8000").rstrip("/")
            + a.get("extract_path", "/api/extract"))


# ------------------------------------------------------------- ad teardown --
def _is_day_count(text):
    """True for observations that restate how long the ad has run.

    That fact is supplied once, already wrapped in its citation. Leaving a
    bare "34 days live" in the observation list gave the model an uncited
    copy of the same number, which is what it reached for.
    """
    return bool(re.search(r"\b\d+\s*days?\b", text, re.I))


def _observable_half(text):
    """Keep the observable fact, drop adspy's scoring opinion.

    scoring.py emits "FACT - OPINION" pairs:
        "Body copy 202 chars - in the 80-300 range that converts on Meta"
        "6-card carousel - letting Meta pick the winner"
    The right-hand side is a heuristic from Harsh's own tool. Telling the
    model not to treat it as evidence was not enough: it came back as "it
    stays within the effective 80-300 character range". So the opinion never
    reaches the model at all, and the threshold it carries goes with it.
    """
    return re.split(r"\s*[\u2014\u2013-]\s+", (text or "").strip(), maxsplit=1)[0].strip()


def load_ad_teardown(fmt, cfg, state):
    files = sorted(glob.glob(os.path.join(TEARDOWN_DIR, "*.json")))
    if not files:
        _abort("ad-teardown",
               "no ad JSON found.",
               f"  Looked in: {TEARDOWN_DIR}\n"
               "  Feed it from your own adspy extractor:\n"
               f"    curl -s -X POST {_adspy_url(cfg)} \\\n"
               "      -H 'Content-Type: application/json' \\\n"
               "      -d '{\"url\":\"<meta ad library url>\"}' \\\n"
               f"      > {os.path.join('sources','ad_teardowns','<name>.json')}\n"
               "  This pipeline deliberately does NOT drive Ad Library itself:\n"
               "  it shares a Chrome session with LinkedIn.")
    usable = []
    for path in files:
        try:
            ad = json.load(open(path))
        except Exception as e:
            _abort("ad-teardown", f"{os.path.basename(path)} is not valid JSON.", f"  {e}")
        formats = ad.get("formats") or ["text", "carousel"]
        if not _supports(formats, fmt):
            continue
        usable.append((path, ad))
    if not usable:
        _abort("ad-teardown", f"no ad can carry format '{fmt}'.")

    # 2026-08-21: de-duplication. This pillar had none, and the pool holds one
    # fixture, so it re-published the same Flipkart teardown on 17 and 21 August
    # - same ad, same 34 days, same 202 characters. It now refuses to repeat.
    used = state.get("_used_sources", {})
    seen = (used.get("ad-teardown") or {})
    unused = [(pth, a) for pth, a in usable if os.path.basename(pth) not in seen]
    if not unused:
        _abort("ad-teardown",
               f"every ad in the pool has already been torn down.",
               f"  Pool: {len(usable)} ad(s) in {TEARDOWN_DIR}\n"
               f"  Already used: {', '.join(sorted(seen)) or 'none'}\n"
               "\n"
               "  This pillar will NOT republish a teardown. Add a new ad JSON:\n"
               f"    curl -s -X POST {_adspy_url(cfg)} \\\n"
               "      -H 'Content-Type: application/json' \\\n"
               "      -d '{\"url\":\"<meta ad library url>\"}' \\\n"
               "      > sources/ad_teardowns/<name>.json\n"
               "  One teardown a week means you need one new ad a week. Keeping\n"
               "  4-6 in the pool gives you a month of runway.")
    path, ad = unused[0]
    days = ad.get("days_running")
    year = datetime.date.today().year
    body = (ad.get("body") or "").strip()
    return {
        "pillar": "ad-teardown",
        "source": "Meta Ad Library",
        "reference": os.path.basename(path),
        "source_key": os.path.basename(path),
        "headline": f"Ad teardown: {ad.get('page_name', 'unnamed advertiser')}",
        "material": "\n".join(filter(None, [
            f"ADVERTISER: {ad.get('page_name', '')}",
            f"AD COPY: {body[:600]}",
            f"CTA: {ad.get('cta_text') or ad.get('cta_type') or ''}",
            f"STILL ACTIVE: {ad.get('is_active')}",
            "",
            "HOW TO WRITE THIS POST. It has two registers. Keep them in "
            "separate sentences. Mixing them in one sentence is the single "
            "error that has rejected every failed draft of this pillar.",
            "",
            "REGISTER 1, OBSERVABLE FACT. What the Meta Ad Library actually "
            "publishes: the creative, the placements, the format, the ad's own "
            "copy, the date it started running and whether it is still live. "
            "A factual sentence states the fact and ends. It carries no "
            "verdict.",
            (f"  The one fact that MUST carry its citation is how long it has "
             f"run, because it is a number. Use this sentence, or one that "
             f"keeps the source, the number and the year together:\n"
             f'    "The Meta Ad Library shows this creative has been running '
             f'{days} days as of {datetime.date.today().year}."\n'
             f'  Writing "it has been running {days} days" or "has been '
             f'active {days} days" without naming the Meta Ad Library and '
             f'{year} in that same sentence is REJECTED. This is the single '
             f"most common way this pillar fails.\n"
             f"  If that sentence does not fit where you want it, use the "
             f"no-number form instead and keep the fact:\n"
             f'    "This ad has been running for over a month."\n'
             f"  Those are the ONLY two ways to state longevity. Any third "
             f"phrasing that contains the number is rejected. Do not put the "
             f"number in your hook.")
            if days else "",
            "  The structural facts below need no citation. State them plainly.",
            "",
            "REGISTER 2, YOUR READ, IN FIRST PERSON. This is Harsh's opinion, "
            "and it is the reason anyone would read the post. A teardown with "
            "no opinion is pointless. You do not need a source to hold an "
            "opinion, but you must own it: write 'I'.",
            "  GOOD: \"I'd change the opening line.\"",
            "  GOOD: \"This reads bottom-of-funnel to me.\"",
            "  GOOD: \"I think the CTA is doing most of the work here.\"",
            "  GOOD: \"If it were mine, I'd test opening with the offer.\"",
            "  You may say a long run suggests the advertiser keeps choosing "
            "to pay for it. That is your read, and it is allowed.",
            "  Never attribute your read to the Ad Library, to research, to "
            "data, to studies or to experts. Those are checked and rejected.",
            "",
            "THE ERROR IS PUTTING BOTH IN ONE SENTENCE:",
            "  BAD:  \"...running 34 days, a testament to its effectiveness.\"",
            "  BAD:  \"...active for 34 days, shining a light on sustained "
            "engagement.\"",
            "  BAD:  \"The Ad Library confirms its longevity and "
            "effectiveness.\"",
            f'  GOOD: "The Meta Ad Library shows this creative has been '
            f'running {days} days as of {year}. I read that as the advertiser '
            f'choosing to keep paying for it."',
            "  Two sentences. Fact, then read.",
            "",
            "THE AD LIBRARY PUBLISHES NO spend, impressions, ROAS, engagement, "
            "conversions or verdict of any kind. It does not rate, rank, "
            "confirm, validate or recognise an ad's effectiveness or "
            "performance. Never write a sentence that credits it with any of "
            "those.",
            "",
            "STRUCTURE OF THE AD, observed. Describe these in your own words. "
            "They are observations, not findings, not research, and carry no "
            "thresholds you may quote as established:",
            "\n".join(f"  - {_observable_half(x.get('text',''))}"
                       for x in (ad.get("why_it_works") or [])
                       if _observable_half(x.get("text", ""))
                       and not _is_day_count(_observable_half(x.get("text", "")))),
            f"WHAT I'D WATCH: {'; '.join(ad.get('watch_outs') or [])}"
            if ad.get("watch_outs") else "",
            "",
            "DO NOT REPRODUCE ANY FIGURE THAT APPEARS IN THE AD COPY ITSELF "
            "(discount percentages, prices, offer amounts). Describe the offer "
            "in words instead: 'a steep percentage-off hook' rather than the "
            "number. Those figures belong to the advertiser, are not sourced "
            "by you, and will be rejected.",
        ])),
        "attested": [],
        "angle_key": None,
        "thesis": None,
        "sector": "",
    }


def _short_metric(metric):
    """A readable name for the figure, taken from the TOML entry.

    2026-08-21: the suggested opening line hardcoded the word "conversion".
    When de-duplication rotated to the cost-per-click entry the post still
    opened "Most people quoting a Facebook Ads conversion benchmark..." while
    shipping $1.72 CPC. The phrase now comes from the metric field, so it is
    correct for whatever figure is in the slot.
    """
    first = str(metric or "").split(",")[0].strip()
    first = re.sub(r"^(?:median|average|mean|typical)\s+", "", first, flags=re.I)
    first = re.sub(r"\s+across all industries$", "", first, flags=re.I)
    return first or "benchmark"


# ---------------------------------------------------------------- benchmark --
def load_benchmark(fmt, cfg, state):
    if not os.path.exists(BENCHMARKS_PATH):
        _abort("benchmark",
               "sources/benchmarks.toml is missing.",
               "  This pillar needs a real figure from an allowlisted source.\n"
               "  There is no honest way to automate it: the allowlisted\n"
               "  publishers have no stable feed, so figures are pasted in by\n"
               "  hand. A manual step is fine; an invented statistic is not.")
    try:
        with open(BENCHMARKS_PATH, "rb") as f:
            data = tomllib.load(f)
    except tomllib.TOMLDecodeError as e:
        _abort("benchmark", "sources/benchmarks.toml is not valid TOML.", f"  {e}")

    allowed = {s.lower() for s in data.get("allowed_sources", [])}
    items = data.get("benchmark", [])
    problems, usable = [], []
    for i, b in enumerate(items, 1):
        label = b.get("id") or f"#{i}"
        for field in ("id", "source", "year", "figure", "metric", "context"):
            if not str(b.get(field, "")).strip():
                problems.append(f"benchmark '{label}': missing '{field}'")
        if b.get("source") and str(b["source"]).lower() not in allowed:
            problems.append(
                f"benchmark '{label}': source '{b['source']}' is not on the allowlist {sorted(allowed)}")
        if b.get("used") is True:
            continue
        if _supports(b.get("formats") or ["text"], fmt):
            usable.append(b)
    if problems:
        _abort("benchmark", f"{len(problems)} problem(s) in benchmarks.toml.",
               "\n".join(f"    - {p}" for p in problems))
    if not usable:
        _abort("benchmark",
               f"no unused benchmark can carry format '{fmt}'.",
               "  Add one, or set used = false on an existing entry.")

    used = state.get("_used_sources", {})
    seen = (used.get("benchmark") or {})
    fresh_b = [x for x in usable if x.get("id") not in seen]
    if not fresh_b:
        _abort("benchmark",
               "every benchmark figure has already been published.",
               f"  Pool: {len(usable)} entry/entries carrying '{fmt}'\n"
               f"  Already used: {', '.join(sorted(seen)) or 'none'}\n"
               "\n"
               "  The `used = false` field in benchmarks.toml was never written\n"
               "  by anything - nothing in the codebase opens that file for\n"
               "  writing. Usage is tracked in used_sources.json instead.\n"
               "  Add a new [[benchmark]] block by hand from an allowlisted\n"
               "  publisher. Weekly use means roughly 4-5 figures per month.")
    b = fresh_b[0]
    return {
        "pillar": "benchmark",
        "source": f"{b['source']} {b['year']}",
        "reference": b["id"],
        "source_key": b["id"],
        "headline": f"{b['metric']}: {b['figure']}",
        "material": "\n".join([
            f"FIGURE: {b['figure']}",
            f"METRIC: {b['metric']}",
            f"SOURCE: {b['source']}",
            f"YEAR: {b['year']}",
            f"CONTEXT: {b['context']}",
            f"DO NOT OPEN WITH THE BARE NUMBER. The temptation is a hook like "
            f"\"The {b['figure']} conversion rate everyone quotes?\" That is "
            f"rejected, because that sentence has the figure and no citation. "
            f"Open with the AGE instead, which is the interesting part and "
            f"needs no citation: \"Most people quoting a Facebook Ads "
            f"{_short_metric(b['metric'])} benchmark are quoting {b['year']}.\" Then give the "
            f"figure with its citation in the sentence that follows.",
            f"CITATION IS CHECKED PER SENTENCE, NOT PER POST. Every sentence "
            f"containing '{b['figure']}' must ALSO contain the word "
            f"'{b['source']}' and the year {b['year']}. Naming the source in "
            f"the next sentence does not pass. Write it as one sentence, e.g.: "
            f"\"{b['source']}'s {b['year']} sample put the {b['metric'].split(',')[0]} "
            f"at {b['figure']}.\" Then say whatever you want about it in the "
            f"sentences that follow, without repeating the number.",
            f"AGE OF THIS DATA: it was gathered in {b['year']}, which is "
            f"{datetime.date.today().year - int(b['year'])} years ago. NEVER "
            f"present it as current, recent, latest, up-to-date, or as "
            f"'{datetime.date.today().year}' data. The publisher's page may "
            f"carry a recent 'last updated' date; that refers to the article, "
            f"not the sample. State the year plainly.",
            "SURFACE THE SAMPLE PERIOD. The metric line above names the sample "
            "this figure came from. Say it in the post. A reader must be able "
            "to tell how old the number is without leaving the post. If the "
            "age of the figure is the interesting thing, say that outright.",
        ]),
        "attested": [],
        "angle_key": None,
        "thesis": None,
        "sector": "",
    }


# -------------------------------------------------------- reddit questions --
_Q_STOP = set("""
this that these those what when where which while with without your yours their
they them then than have has had been being from into over under about after
before some more most much many just like also them there here your you our
been will would could should must need needs want wants make makes made does
doing done very really quite even only ever else such same other another
anyone someone everyone something anything nothing because since though
although however still yet ever never always often usually maybe perhaps
""".split())


def _cwords(text):
    return {w for w in re.findall(r"[a-z]{4,}", (text or "").lower())
            if w not in _Q_STOP}


def _angle_match(question, proj, ang):
    """Overlap between what was asked and what Harsh actually has to say.

    Scored against the question's own vocabulary, not the angle's: a long
    angle should not win just by being long.
    """
    qw = _cwords(f"{question.get('title','')} {(question.get('selftext') or '')[:900]}")
    if not qw:
        return 0.0
    aw = _cwords(" ".join([
        ang.get("claim", ""), ang.get("detail", ""),
        proj.get("problem", ""), proj.get("built", ""),
        proj.get("surprise", ""), proj.get("changed", ""),
        proj.get("sector", ""),
    ]))
    return len(qw & aw) / len(qw)


MAX_QUESTIONS_OFFERED = 18   # questions put in front of the matcher at once


def _pick_question_and_angle(questions, pairs):
    """Choose one (question, project, angle) pairing, or None.

    Lexical overlap was measured as a shortlisting step over 51 questions x 35
    angles and discarded: scores ran 0.062-0.231, median 0.125, and the highest
    scoring pair was "Is there a outage today?" against an angle about Meta
    form submissions. A shortlist built from that is noise, so the whole set
    goes to the matcher and it picks the best pairing globally, or NONE.
    """
    if LLM is None:
        _abort("community-question",
               "no LLM available to match a question to your notes.")
    qs = questions[:MAX_QUESTIONS_OFFERED]
    q_menu = "\n".join(
        f"Q{i+1}. {q.get('title','').strip()}"
        + (f"\n     {(q.get('selftext') or '').strip()[:180]}" if q.get("selftext") else "")
        for i, q in enumerate(qs))
    a_menu = "\n".join(
        f"A{i+1}. {a['claim'].strip()}\n     {a['detail'].strip()[:170]}"
        for i, (p, a) in enumerate(pairs))
    ask = (
        f"QUESTIONS PEOPLE ASKED:\n{q_menu}\n\n"
        f"THINGS HARSH HAS ACTUALLY DONE:\n{a_menu}\n\n"
        "Pick the ONE question that Harsh can answer best using ONE of those "
        "things he did. The thing he did must genuinely address what was "
        "asked, so that his answer is a specific account of his own work "
        "rather than general advice. Sharing a loose theme is not a match: "
        "both mentioning 'ads', or 'clients', or 'leads', is not enough. "
        "Prefer a strong pairing on a less interesting question over a weak "
        "pairing on an interesting one. If nothing pairs well, say NONE.\n\n"
        f"Reply with exactly one line: 'Q<number> A<number>', or NONE.\n"
        f"The question number must be between 1 and {len(qs)}. The thing-he-did "
        f"number must be between 1 and {len(pairs)}. Do not reply with any "
        f"number outside those ranges."
    )
    sysp = ("You pair questions with first-hand experience. You are strict, "
            "and NONE is a perfectly good answer.")
    # One retry: an out-of-range reply is a formatting miss, not a considered
    # NONE, and treating it as NONE would abort the batch for the wrong reason.
    for attempt in (1, 2):
        raw = LLM(sysp, ask, max_tokens=16)
        if raw is None:
            # call_llm returns None only when the request itself failed
            # (rate limit, transport, HTTP error). That is not a judgement
            # about the notes, and reporting it as "no pairing found" would
            # blame the material for an outage. Observed in run 18: sustained
            # 429s produced an empty reply that was read as a considered NONE.
            _abort("community-question",
                   "the matcher call failed, so no pairing could be evaluated.",
                   "  This is NOT a finding that your notes have nothing to say.\n"
                   "  The API returned no response at all - see the 429 or HTTP\n"
                   "  error lines above. Re-run when the API is healthy; the\n"
                   "  pillar itself has not been assessed.")
        reply = raw.strip().upper()
        if reply.startswith("NONE"):
            return None
        m = re.search(r"Q\s*(\d+)\s*[, ]*\s*A\s*(\d+)", reply)
        if m:
            qi, ai = int(m.group(1)) - 1, int(m.group(2)) - 1
            if 0 <= qi < len(qs) and 0 <= ai < len(pairs):
                return qs[qi], pairs[ai][0], pairs[ai][1]
        print(f"  community-question: matcher reply {reply!r} unusable"
              f"{' - retrying once' if attempt == 1 else ' - treating as no match'}")
    return None


def load_reddit_question(fmt, cfg, state):
    if not os.path.exists(REDDIT_PATH):
        _abort("community-question", "reddit_data.json is missing.",
               "  Run fetch_reddit_rss.py first.")
    items = json.load(open(REDDIT_PATH))
    questions = [x for x in items if x.get("is_question")]
    if not questions:
        _abort("community-question",
               "no questions found in reddit_data.json.",
               f"  {len(items)} item(s) fetched, none of them phrased as a question.\n"
               "  This pillar answers a question someone actually asked.")

    # Phase 3b: the question alone gave the model nothing of Harsh's to answer
    # with, so it produced general advice. Every question must now be paired
    # with a real angle from raw_notes.toml. No pairing, no post.
    notes = notes_loader.load_notes()
    # 2026-08-21: this only ever excluded angles used EARLIER IN THE SAME BATCH.
    # It ignored used_angles.json entirely, so across runs it re-picked the same
    # angle and, because the pairing is angle-driven, the same question with it.
    # Verified by resolving twice with the angle recorded in between: identical
    # both times. History is now honoured, and the question itself is tracked in
    # used_sources.json so a question cannot come back under a different angle.
    used_in_batch = state.get("_batch_keys", set())
    used_angles = set(state.get("angles", {}) or {})
    used_q = set((state.get("_used_sources", {}).get("community-question") or {}))
    pairs = [(p, a) for p in notes["projects"] for a in p.get("angle", [])
             if {fmt, "either"} & {str(f).lower() for f in a.get("formats", [])}
             and f"{p['id']}::{a['id']}" not in used_in_batch
             and f"{p['id']}::{a['id']}" not in used_angles]
    questions = [q for q in questions
                 if (q.get("id") or q.get("title", "")[:40]) not in used_q]
    if not questions:
        _abort("community-question",
               "every fetched question has already been answered.",
               "  Re-run `python3 fetch_reddit_rss.py` for a fresh pull.")
    if not pairs:
        _abort("community-question",
               f"no angle in raw_notes.toml can carry format '{fmt}'.")

    # "Pick a different question rather than produce general advice": a NONE on
    # the first window is not the end, it means those questions had nothing to
    # pair with. Work through the rest before giving up.
    picked = None
    windows = 0
    for i in range(0, len(questions), MAX_QUESTIONS_OFFERED):
        window = questions[i:i + MAX_QUESTIONS_OFFERED]
        windows += 1
        picked = _pick_question_and_angle(window, pairs)
        if picked:
            break
        print(f"  community-question: no pairing in questions "
              f"{i+1}-{i+len(window)}, trying the next ones")
    if not picked:
        _abort("community-question",
               f"none of the {len(questions)} question(s), offered in "
               f"{windows} window(s), can be answered from raw_notes.toml.",
               f"  {len(questions)} question(s) available, {len(pairs)} angle(s) "
               f"can carry '{fmt}'.\n"
               "  This pillar answers a real question with something you actually\n"
               "  did. Without a match it can only produce general advice, which\n"
               "  is what it was producing before. Add an angle that covers what\n"
               "  people are asking, or re-run fetch_reddit_rss.py for fresh\n"
               "  questions.")

    q, project, angle = picked
    key = f"{project['id']}::{angle['id']}"
    state.setdefault("_batch_keys", set()).add(key)
    return {
        "pillar": "community-question",
        "source": f"r/{q.get('subreddit','').lstrip('r/')} (question) + raw_notes.toml",
        "reference": f"{q.get('id') or q.get('title','')[:24]} <- {key}",
        "source_key": q.get("id") or q.get("title", "")[:40],
        "headline": q.get("title", ""),
        "material": "\n".join([
            f"THE QUESTION PEOPLE ARE ASKING: {q.get('title','')}",
            f"CONTEXT: {(q.get('selftext') or '')[:600]}",
            "",
            "ANSWER IT FROM THIS, WHICH HARSH ACTUALLY DID. This is the point "
            "of the post. Do not answer in general terms; answer by describing "
            "what happened here and what it implies for the person asking.",
            f"PROBLEM: {project['problem'].strip()}",
            f"BUILT: {project['built'].strip()}",
            f"SURPRISE: {project['surprise'].strip()}",
            f"CHANGED: {project['changed'].strip()}",
            f"THE ANGLE: {angle['detail'].strip()}",
            "",
            "WRITE THE ANSWER. Never quote the person, never name them, never "
            "cite a username, a subreddit or a forum as a source. Paraphrase "
            "the question in your own words and answer it.",
            "THE ASKER'S SITUATION IS NOT YOURS. Describe what THEY are facing "
            "in the second or third person: \"someone coming back to Meta Ads "
            "after two years\", \"if you are seeing this\". Never write "
            "their circumstances as your own first-person experience. \"Since "
            "the last time I ran campaigns\" is a fabricated claim about "
            "Harsh and is rejected in code. The only first-person material you "
            "have is the project described above; 'I' belongs to that and "
            "nothing else.",
            "DO NOT REPRODUCE ANY FIGURE FROM THE QUESTION (their budget, their "
            "CPL, their lead count). Those are one stranger's numbers, they are "
            "not sourced, and they will be rejected. Describe the situation in "
            "words: 'a few thousand a month with almost nothing to show for it' "
            "rather than the number.",
        ]),
        "attested": notes_loader.attested_details(project, angle),
        "angle_key": key,
        "thesis": angle.get("thesis"),
        "sector": project.get("sector", ""),
    }


HOUSEKEEPING_RE = re.compile(
    r"^\s*(?:\*\*[^*]+:\*\*\s*)?(?:"
    r"bump\b|update\s+dependenc|upgrade\s+dependenc|chore\b|deps?\b|"
    r"pnpm\s+override|dependabot|version\s+bump|release\s+\d|"
    r"send\s+n8n\s+version"
    r")", re.I)


def _substantive_bullets(body):
    """Changelog bullets that are a real change, not version housekeeping.

    Also drops the auto-generated HTML the feed appends (cubic.dev review
    buttons and their URLs), which would otherwise reach the model and risk a
    link leaking into the post body.
    """
    text = re.split(r"<!--", str(body or ""))[0]
    out = []
    for raw in re.findall(r"^\*\s+(.+)$", text, re.M):
        # Strip markdown links and any bare URL. The trailing-anchor pattern
        # this replaced left "([#35212](https://github.com/...))" in place,
        # and a URL reaching the model risks find_external_links rejecting the
        # post for a link it copied out of the source material.
        b = re.sub(r"\(\[[^\]]*\]\([^)]*\)\)", "", raw)
        b = re.sub(r"\[[^\]]*\]\([^)]*\)", "", b)
        b = re.sub(r"https?://\S+", "", b)
        b = re.sub(r"\s*\(\s*\)\s*$", "", b).strip()
        if not b or HOUSEKEEPING_RE.match(b):
            continue
        out.append(b)
    return out


# ---------------------------------------------------------------- changelog --
def load_changelog(fmt, cfg, state):
    max_age = cfg.get("source_max_age_days", 14)
    if not os.path.exists(CHANGELOG_PATH):
        _abort("update-or-hot-take", "changelog_data.json is missing.",
               "  Run fetch_changelogs.py first.")
    items = json.load(open(CHANGELOG_PATH))
    dated = [x for x in items if x.get("date")]
    undated = len(items) - len(dated)
    fresh = [x for x in dated if _fresh(x["date"], max_age)]
    if not fresh:
        newest = max((x["date"] for x in dated), default="none")
        _abort("update-or-hot-take",
               f"no changelog item within {max_age} days.",
               f"  {len(items)} item(s), {undated} without a date (refused).\n"
               f"  Newest dated item: {newest}\n"
               "  Anything fed to the planner as current must carry its own date.")
    used = state.get("_used_sources", {})
    seen = (used.get("update-or-hot-take") or {})
    unused_c = [x for x in fresh if (x.get("id") or x.get("title","")[:40]) not in seen]
    # 2026-08-21: a dependency-bump release has no story in it. n8n@1.123.70
    # carried four "Bump adm-zip / tar / undici" lines and one real fix, and the
    # deck led with the bumps: "This update bumps adm-zip, tar, and undici
    # versions." Housekeeping bullets are stripped from the material, and a
    # release with nothing left is skipped rather than written thin.
    substantive = []
    for x in unused_c:
        real = _substantive_bullets(x.get("body"))
        if real:
            x = dict(x, _real_bullets=real)
            substantive.append(x)
    # Richest release first, most recent as the tiebreak. Taking fresh[0] gave
    # n8n@1.123.70, which survives the housekeeping filter on a single obscure
    # bullet ("Stop scheduled poll ticks from releasing the activation's
    # expression isolate") while n8n@2.35.0 in the same window has seven real
    # fixes. "The next genuinely substantive one" means the one with something
    # in it, not merely the first that is not pure housekeeping.
    substantive.sort(key=lambda x: (len(x["_real_bullets"]), str(x.get("date") or "")),
                     reverse=True)
    if not substantive:
        _abort("update-or-hot-take",
               "no release in the window has anything substantive in it.",
               f"  {len(unused_c)} unused release(s) inside the {max_age}-day window,\n"
               "  all of them dependency bumps or version housekeeping.\n"
               "  A bump release has no story, so the day is skipped rather than\n"
               "  padded. Re-run `python3 fetch_changelogs.py` for newer releases.")
    unused_c = substantive
    if not unused_c:
        _abort("update-or-hot-take",
               "every dated release in the window has already been written about.",
               f"  {len(fresh)} release(s) inside the {max_age}-day window\n"
               f"  Already used: {', '.join(sorted(seen)) or 'none'}\n"
               "\n"
               "  Re-run `python3 fetch_changelogs.py` to pull newer releases.\n"
               "  If nothing new has shipped, this pillar has nothing honest to\n"
               "  say and the day is skipped rather than repeating a release.")
    c = unused_c[0]
    return {
        "pillar": "update-or-hot-take",
        "source": f"{c.get('source','')} changelog, {c.get('date','')}",
        "reference": c.get("id") or c.get("title", "")[:40],
        "source_key": c.get("id") or c.get("title", "")[:40],
        "headline": c.get("title", ""),
        "material": "\n".join([
            f"WHAT CHANGED: {c.get('title','')}",
            "WHAT IS ACTUALLY IN THIS RELEASE (housekeeping and dependency "
            "bumps have been removed; these are the only changes worth writing "
            "about):\n" + "\n".join(f"  - {b}" for b in c.get("_real_bullets", [])[:6]),
            f"SOURCE: {c.get('source','')}  DATE: {c.get('date','')}",
            "Take a position on it. Do not relay the release notes.",
            "",
            "YOU HAVE NOT USED THIS RELEASE. All you have is the changelog "
            "entry above. Do not write that you ran it, tried it, tested it, "
            "upgraded to it, navigated it, saw its effect firsthand, or used "
            "it in your own workflows. None of that is in the material and it "
            "is rejected in code. Nothing here is first-person experience.",
            # 2026-08-21: format_mix moved to 3 carousel + 2 text, which puts
            # this pillar in a carousel slot. The material was written for prose
            # and gave the model no slide structure, so it had nothing to build
            # seven slides from. A changelog CAN carry a deck - "what shipped /
            # what it does / where it bites / what to check" is a real seven-beat
            # story - but the beats have to be named or the slides come out as
            # padding.
            ("SEVEN SLIDES, ONE BEAT EACH. This is a carousel, not a paragraph "
             "cut into pieces. Use this structure:\n"
             "  Slide 1  The claim. A declarative statement of 6-8 words about "
             "what this change means. Not the release number.\n"
             "  Slide 2  What shipped. Name the release and the change in plain "
             "words. State it and stop.\n"
             "  Slide 3  What it actually does. The mechanism, one step at a "
             "time. Explain it to someone who runs this in production.\n"
             "  Slide 4  Where this bites. The concrete setup in which the old "
             "behaviour was a problem. Describe the situation, not a customer.\n"
             "  Slide 5  What went wrong before it. What the old behaviour cost "
             "you, mechanically. No invented incident, no invented numbers.\n"
             "  Slide 6  What to check in your own setup. One specific thing a "
             "reader can go and look at today.\n"
             "  Slide 7  The take. First person, one line, your opinion.\n"
             "Each slide is one or two short sentences. If a slide only restates "
             "the one before it, the post does not have enough in it - say less "
             "rather than padding.")
            if fmt == "carousel" else
            "WHAT THIS POST IS: what changed, and what it means for someone "
            "running this in production. Explain the mechanism and say plainly "
            "why it matters or does not. An opinion about the change is "
            "welcome and should be first person, \"I think this matters "
            "because ...\". An opinion is not the same as a claim to have "
            "used it.",
            "  Good: \"Per-hop TLS options matter the moment your requests "
            "pass through more than one proxy, because a setting applied once "
            "at the edge was never reaching the later hops.\"",
            "  Bad:  \"I recently navigated this update within my own "
            "workflows and saw firsthand how it helps.\"",
        ]),
        "attested": [],
        "angle_key": None,
        "thesis": None,
        "sector": "",
    }


RESOLVERS = {
    "raw_notes": load_build_note,
    "ad_teardown": load_ad_teardown,
    "benchmark": load_benchmark,
    "reddit_questions": load_reddit_question,
    "changelog": load_changelog,
}


def resolve_pillar(pillar, fmt, cfg, state):
    fn = RESOLVERS.get(pillar["source"])
    if not fn:
        _abort(pillar["id"], f"no resolver for source '{pillar['source']}'.")
    item = fn(fmt, cfg, state)
    item["pillar_id"] = pillar["id"]
    item["day"] = pillar["day"]
    item["format"] = fmt
    return item
