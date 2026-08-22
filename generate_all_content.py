"""Daily LinkedIn content generator.

PROVIDER IS CONFIGURED, NOT HARD-CODED. `llm.base_url`, `llm.model` and
`llm.api_key_env` in pipeline_config.json are the only declarations; switch
provider or model there, never in this file. The key VALUE is never loaded
into config, logged or printed - only the variable NAME lives in config.

Current setting is Mesh (an OpenAI-compatible proxy) serving openai/gpt-4o.
The response shape is standard OpenAI: choices[0].message.content, with usage
carrying prompt_tokens/completion_tokens. Verified against the live endpoint
before the switch, so no parsing change was needed.

NAMING HISTORY, because it cost real debugging time twice. This file was
generate_all_content_gemini.py with a call_gemini() function and error
strings naming OpenRouter, while calling OpenAI directly. A billing 429 from
OpenAI sent Harsh to check his Gemini quota. It was renamed to
generate_all_content.py / call_llm(), then renamed again to this
provider-neutral name once the provider became configurable. The function is
call_llm(). Do not put a provider name in either again.
"""
import json
import re
import urllib.request
import ssl
import sys
import os
import datetime
import time
import traceback

from config_loader import load_config, build_slot_sequence
import notes_loader

# ---- Phase 1: single source of truth -----------------------------------------
# load_config() asserts on startup that format_mix sums to posts_per_batch and
# that the horizon x slots can hold the batch. It aborts non-zero on mismatch.
CONFIG = load_config()
POSTS_PER_BATCH = CONFIG["posts_per_batch"]
BATCH_HORIZON_DAYS = CONFIG["batch_horizon_days"]
FORMAT_MIX = CONFIG["format_mix"]
SLOT_SEQUENCE = build_slot_sequence(CONFIG)
GENERATE_PERFORMANCE_POSTS = bool(CONFIG.get("generate_performance_posts"))
print(
    f"Config: {POSTS_PER_BATCH} posts over {BATCH_HORIZON_DAYS} days | "
    f"mix { {k: v for k, v in FORMAT_MIX.items() if v} } | tz {CONFIG.get('timezone')}"
)
# ------------------------------------------------------------------------------

# TLS. This connection carries the API key, so the certificate is verified.
# Until Phase 3e this was check_hostname=False / verify_mode=CERT_NONE, which
# disabled verification entirely; with a proxy in the path that is worse, not
# better, because the key is presented to whatever answers the hostname.
ctx = ssl.create_default_context()

# ---- Phase 3e: provider comes from pipeline_config.json ----------------------
LLM_BASE_URL = CONFIG["llm"]["base_url"].rstrip("/")
LLM_MODEL = CONFIG["llm"]["model"]
LLM_KEY_ENV = CONFIG["llm"]["api_key_env"]
url = f"{LLM_BASE_URL}/chat/completions"


def _read_key(var_name):
    """Read the key from .env, then the process environment. Never logged."""
    if os.path.exists("./.env"):
        with open("./.env") as f:
            hits = [ln for ln in f if ln.startswith(f"{var_name}=")]
        if len(hits) > 1:
            print("=" * 64)
            print(f"FATAL: {var_name} appears {len(hits)} times in .env.")
            print("  Which one wins is an accident of file order. Remove the")
            print("  duplicates, leaving the one you intend to use.")
            print("=" * 64)
            sys.exit(1)
        if hits:
            val = hits[0].strip().split("=", 1)[1].strip().strip('"').strip("'")
            if val:
                return val
    return (os.environ.get(var_name) or "").strip() or None


api_key = _read_key(LLM_KEY_ENV)
if not api_key:
    print("=" * 64)
    print(f"FATAL: {LLM_KEY_ENV} is missing or empty.")
    print(f"  pipeline_config.json -> llm.api_key_env names it as the key for")
    print(f"  {LLM_BASE_URL}. Add it to .env, or point api_key_env at the")
    print("  variable that actually holds the key.")
    print("=" * 64)
    sys.exit(1)

print(f"Provider: {LLM_BASE_URL} | model {LLM_MODEL} | key from {LLM_KEY_ENV}")

headers = {
    "Authorization": f"Bearer {api_key}",
    "Content-Type": "application/json"
}

# Error codes that no amount of retrying will fix.
FATAL_ERROR_CODES = {
    "unauthorized", "invalid_api_key", "authentication_error",
    "model_not_found", "insufficient_quota", "credit_balance_exhausted",
    "billing_hard_limit_reached", "account_deactivated", "permission_denied",
}
BILLING_MARKERS = ("no credits", "insufficient_quota", "exceeded your current quota",
                   "billing", "credit_balance", "payment required", "quota")


def _describe_api_error(status, raw_body):
    """Work out WHICH LAYER failed and what it said.

    With a proxy in the path a 4xx can come from the proxy itself (bad key at
    Mesh, model not on Mesh's roster) or be relayed from the provider behind it
    (OpenAI out of quota). Mesh's own errors are flat {code, message}; a relayed
    provider error carries provider-shaped fields (an OpenAI-style `type`, or a
    nested error / provider / upstream key). Returns
    (layer, code, message, request_id, fatal).
    """
    try:
        body = json.loads(raw_body)
    except Exception:
        return ("unknown", None, (raw_body or "")[:300], None,
                status in (401, 403, 404))
    err = body.get("error")
    if not isinstance(err, dict):
        err = body if isinstance(body, dict) else {}
    request_id = body.get("request_id") or body.get("id")

    upstream = None
    for key in ("error", "provider_error", "upstream_error", "upstream", "provider", "metadata"):
        nested = err.get(key)
        if isinstance(nested, dict):
            upstream = nested
            break
    # An OpenAI-style `type` is the other tell: Mesh's own errors do not use it.
    if upstream is None and err.get("type"):
        upstream = err

    src = upstream if upstream is not None else err
    layer = "upstream provider" if upstream is not None else "Mesh"
    code = str(src.get("code") or src.get("type") or "").strip() or None
    message = str(src.get("message") or src.get("error") or "").strip() or (raw_body or "")[:300]

    blob = f"{code} {message}".lower()
    fatal = (
        status in (401, 403)
        or (code and code.lower() in FATAL_ERROR_CODES)
        or (status == 404 and "model" in blob)
        or any(m in blob for m in BILLING_MARKERS)
    )
    return (layer, code, message, request_id, fatal)


def call_llm(system_prompt, prompt, max_tokens=4000):
    payload = {
        "model": LLM_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt}
        ],
        "max_tokens": max_tokens
    }

    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST"
    )

    for attempt in range(5):
        try:
            with urllib.request.urlopen(req, context=ctx) as res:
                resp = json.loads(res.read().decode("utf-8"))
                if resp and resp.get("choices"):
                    return resp["choices"][0]["message"]["content"]
                print(f"{LLM_BASE_URL} returned an unexpected response shape: "
                      f"{str(resp)[:300]}")
        except urllib.error.HTTPError as e:
            raw = ""
            try:
                raw = e.read().decode("utf-8")
            except Exception:
                pass
            layer, code, message, request_id, fatal = _describe_api_error(e.code, raw)
            if fatal:
                print("=" * 64)
                print(f"FATAL: request rejected by the {layer}. Retrying cannot fix it.")
                print(f"  HTTP {e.code}" + (f"  code: {code}" if code else ""))
                print(f"  {message}")
                if request_id:
                    print(f"  request_id: {request_id}")
                if layer == "upstream provider":
                    print(f"  This came from the provider BEHIND {LLM_BASE_URL},")
                    print(f"  not from the proxy. Check that provider's account.")
                elif e.code in (401, 403):
                    print(f"  The key in {LLM_KEY_ENV} was rejected by {LLM_BASE_URL}.")
                print("=" * 64)
                return None
            if e.code == 429 or e.code >= 500:
                wait = 10 * (attempt + 1)
                where = f"{layer} " if layer != "unknown" else ""
                print(f"{where}HTTP {e.code} (transient). Retrying in {wait}s...")
                time.sleep(wait)
            else:
                print(f"HTTP {e.code} from {layer}: {message}")
                if request_id:
                    print(f"  request_id: {request_id}")
                break
        except Exception as e:
            traceback.print_exc()
            print(f"Error calling {LLM_BASE_URL}: {e}")
            break
        time.sleep(2)
    return None

# Load context data for references
reddit_posts = []
if os.path.exists("./reddit_data.json"):
    with open("./reddit_data.json") as f:
        reddit_posts = json.load(f)[:15]

# Phase 3: ai_news_data.json is no longer read. It had been stale since
# 2026-07-25 and was still being fed to the planner labelled "Fresh AI &
# Marketing News". The Friday pillar now uses dated official changelogs.

# ---- Phase 2: writing rules are LOADED, not transcribed -----------------------
# They used to be a hand-copied string here, so editing voice-profile.md changed
# nothing. The file is now the single source and is read at runtime; everything
# after the "## RULES" heading is sent to the model verbatim.
VOICE_PROFILE_PATH = "./voice-profile.md"


def load_writing_rules(path=VOICE_PROFILE_PATH):
    if not os.path.exists(path):
        print("=" * 64)
        print("FATAL: voice-profile.md is missing.")
        print(f"  Expected: {path}")
        print("  It holds the live writing rules. Generation cannot proceed")
        print("  without them - posts would be written with no voice constraints.")
        print("=" * 64)
        sys.exit(1)
    text = open(path).read()
    marker = "\n## RULES"
    if marker not in text:
        print("=" * 64)
        print("FATAL: voice-profile.md has no '## RULES' section.")
        print("  Everything after that heading is the live prompt text.")
        print("=" * 64)
        sys.exit(1)
    rules = text.split(marker, 1)[1].strip()
    if len(rules) < 200:
        print("=" * 64)
        print(f"FATAL: voice-profile.md '## RULES' section is only {len(rules)} chars.")
        print("  That is too short to be the real rules. Refusing to generate")
        print("  with effectively no voice constraints.")
        print("=" * 64)
        sys.exit(1)
    return rules


writing_rules = load_writing_rules()


# ---- Phase 2: banned vocabulary is ENFORCED IN CODE, not just instructed -----
# The prompt has carried a ban list twice - 70 items, then 33 derived from this
# account's own archives - and both were ignored. A live run put banned words in
# 4 of 5 posts. Word lists in prompts do not bind; the carousel field validator
# does. So the list is now also parsed out of voice-profile.md and checked after
# generation, with the offending words named on the retry.
def _parse_term_list(rules_text, marker):
    """Terms live on a single line starting with an explicit marker, so parsing
    is deterministic and cannot drift when the prose around it is edited."""
    m = re.search(rf"^\s*{marker}\s*:(.+)$", rules_text, re.M)
    if not m:
        print(f"WARNING: could not find '{marker}:' in voice-profile.md.")
        return []
    return sorted({t.strip().lower().rstrip(".") for t in m.group(1).split(",") if t.strip()},
                  key=len, reverse=True)


# Vocabulary is ADVISORY ONLY since Phase 2. Three runs showed code-enforced
# word choice produces synonym swaps and deletions, never better writing. Hard
# checks below are reserved for things that could be published and defended:
# unsourced figures and external links.
ADVISORY_TERMS = _parse_term_list(writing_rules, "AVOID TERMS")
NOT_JUST_RE = re.compile(r"\b(?:it'?s|its|this is)\s+not\s+just\b.{0,60}?\bit'?s\b", re.I)
URL_RE = re.compile(r"https?://\S+|\bwww\.\S+", re.I)
print(f"Advisory vocabulary: {len(ADVISORY_TERMS)} terms (logged, never blocking).")


# ---- Phase 2: unverifiable first-person claims and non-allowlisted sources ---
# HARD checks. Rule 4a was prompt-only and a live run produced 8 fabricated
# claims across 3 of 5 posts, plus a Reddit username cited as a source. Told to
# be first-person and specific with nothing true to work from, the model invents.
# Between inventing and producing nothing, producing nothing wins: a blocked
# batch costs a run, a fabricated client result sits on the feed permanently.
# No repair and no retry here - rewriting would only relocate the fabrication.
CLAIM_PATTERNS = [
    (r"\bI\s+(?:recently\s+|just\s+)?(?:helped|built|set up|took on|ran|tested|implemented|migrated|wired|designed|rebuilt|shipped|deployed|launched|rolled out|connected|automated|replaced|fixed)\b",
     "first-person build/result claim"),
    (r"\bwe\s+(?:recently\s+|just\s+)?(?:helped|built|set up|took on|ran|tested|implemented|migrated|wired|designed|tightened|switched|cut|reduced|increased|boosted|scaled|found|observed|noticed|shipped|deployed|launched|rolled out|connected|automated|replaced|fixed)\b",
     "first-person build/result claim"),
    (r"\bI'?ve\s+seen\b", "unverifiable personal observation"),
    (r"\bin\s+(?:our|my)\s+(?:testing|tests|experience)\b", "unverifiable personal testing"),
    (r"\b(?:our|my|a|one)\s+(?:D2C\s+|B2B\s+|e-?commerce\s+)?client(?:'?s)?\b", "client reference"),
    (r"\bthis\s+(?:approach|strategy|setup|system|change|workflow)\s+(?:specifically\s+)?(?:boosted|improved|increased|reduced|cut|allowed|led to|delivered)\b",
     "asserted outcome"),
    (r"\bperformance was (?:noticeably|significantly|markedly)\b", "asserted outcome"),
    (r"\bbenefit(?:ed|ted) (?:remarkably|significantly|noticeably)\b", "asserted outcome"),
    (r"\bour data shows\b|\bwe found that\b", "asserted finding"),
    # Phase 3f: post 5 of the Mesh batch wrote "I recently navigated this update
    # within my own workflows, and saw firsthand ...". Nothing in a changelog
    # says Harsh ran anything. These cover the verbs that assert hands-on use.
    (r"\bI'?(?:ve)?\s+(?:recently\s+|just\s+|already\s+)?(?:navigated|tried|"
     r"trialled|trialed|adopted|applied|upgraded|patched|integrated|configured|"
     r"switched|rolled)\b",
     "invented hands-on experience"),
    (r"\b(?:saw|seen|experienced|witnessed)\s+(?:this\s+)?firsthand\b",
     "invented firsthand experience"),
    (r"\bin\s+(?:my|our)\s+own\s+(?:workflows?|stack|setup|account|pipeline)\b",
     "invented hands-on experience"),
    (r"\bwe\s+(?:recently\s+|just\s+)?(?:navigated|upgraded|patched|"
     r"integrated|configured|adopted|applied)\b",
     "invented hands-on experience"),
    # Phase 3 dry run: "We realized the need for this when our previous
    # configurations ran into TLS inconsistencies, causing delays and errors"
    # passed every check. It asserts a first-person operational history that
    # was never supplied. These close that gap; they widen the checker, they
    # do not relax it.
    (r"\bwe\s+(?:realized|realised|discovered|learned|learnt|hit|ran into|"
     r"kept hitting|started|stopped|moved|migrated)\b",
     "unverifiable first-person history"),
    (r"\bin\s+(?:our|my)\s+(?:setup|stack|case|workflow|pipeline|"
     r"configuration|environment|account)\b",
     "unverifiable first-person setup claim"),
    (r"\bour\s+(?:previous|current|existing|old)\s+\w+",
     "unverifiable first-person setup claim"),
]

# A username, subreddit or forum handle is never a source.
HANDLE_RE = re.compile(
    r"\b(?:u/|r/)\w+"
    r"|'[A-Za-z][A-Za-z0-9_]*(?:Of|_)[A-Za-z0-9_]+'"
    r"|\bReddit\s+(?:post|thread|user|comment)\b"
    r"|\bforum\s+(?:post|thread)\b",
    re.I,
)
# Phase 3 fix: this used to match the phrase alone, case-insensitively, so
# "based on the nuanced information provided" was flagged as citing an
# unallowlisted source. It now requires a PROPER-NOUN-SHAPED source after the
# phrase (optionally quoted), so ordinary prose no longer fires. Deliberately
# NOT re.I - the capital letter is the signal that a source is being named.
ATTRIB_RE = re.compile(
    r"\b(?:[Aa]ccording to|[Bb]ased on|[Aa]s reported by|[Cc]ited by|[Ss]ource:"
    r"|[Ss]tudy by|[Ss]urvey by|[Rr]esearch by|[Pp]er)\s+"
    r"(?:the\s+)?[\"'‘“]?"
    r"([A-Z][A-Za-z0-9&.\-]*(?:\s+[A-Z][A-Za-z0-9&.\-]*)*)"
)


# Phase 3: PROVENANCE. The checker previously had no way to tell an invented
# claim from a true one, so it rejected both. It is now given the attested
# details from raw_notes.toml for the angle being written, and a first-person
# claim passes only if it stays close to something Harsh actually wrote down.
# This makes the checker STRICTER, not looser: unattested claims still fail,
# and now attested ones must also stay faithful to the source rather than
# embellishing it.
_STOPWORDS = {
    "the", "and", "that", "this", "with", "from", "they", "them", "then", "than",
    "have", "has", "had", "was", "were", "been", "being", "into", "over", "when",
    "what", "which", "their", "there", "here", "would", "could", "should", "about",
    "after", "before", "because", "while", "your", "you", "our", "we", "it", "its",
    "for", "not", "but", "are", "all", "any", "one", "two", "more", "most", "some",
}
# Calibrated by measurement, not guessed. Against real raw_notes material:
#   invented claims (from earlier runs) scored 0.00 - 0.17
#   true claims traceable to the notes  scored 0.40 - 1.00
# 0.30 sits in that gap with margin either side. 0.60 was the initial guess and
# was tuned on near-verbatim text; real generation paraphrases, so it produced
# false positives on claims that WERE attested. This is a correction of a
# mis-calibration, not a loosening: invention still scores far below it.
CLAIM_ANCHOR_RATIO = 0.30


def _content_words(text):
    return {w for w in re.findall(r"[a-z0-9]{4,}", str(text).lower()) if w not in _STOPWORDS}


# Phase 3f: crude suffix stemming was tried here to rescue "I built a solution
# using n8n ..." (scored 0.20 against attested notes containing "building" and
# "automation"). Measured, it did NOT rescue that sentence (still 0.20) and it
# lifted two invented claims ABOVE the threshold - "In our testing, response
# times improved dramatically" went 0.38 and "Clients consistently tell me ..."
# went 0.33. Strictly worse, so it was reverted. The real defect was in the
# draft: "a solution" names nothing. The fix is at the source, telling the
# build-note pillar to name what was built.


def _is_attested(sentence, attested):
    """True if the sentence stays close to one attested detail."""
    if not attested:
        return False
    words = _content_words(sentence)
    if not words:
        return False
    corpus = _content_words(" ".join(attested))
    overlap = len(words & corpus) / len(words)
    return overlap >= CLAIM_ANCHOR_RATIO


def find_unverifiable_claims(text, attested=None):
    """Formulaic first-person claims not traceable to attested material."""
    out = []
    for sent in _sentences(text):
        for rx, label in CLAIM_PATTERNS:
            m = re.search(rx, sent, re.I)
            if m:
                if _is_attested(sent, attested):
                    break  # traceable to raw_notes.toml - permitted
                out.append((sent.strip(), m.group(0).strip(), label))
                break
    return out


# Outcome verbs. "conversion opportunities skyrocketed" survived the sentence
# level check because the rest of the sentence overlapped attested text. The
# magnitude word is the claim, so the magnitude word itself has to trace to
# the notes, not merely its neighbours.
OUTCOME_WORDS = [
    "skyrocket", "skyrocketed", "skyrocketing",
    "double", "doubled", "doubling", "triple", "tripled", "tripling",
    "quadruple", "quadrupled", "halve", "halved",
    "transform", "transformed", "transforming",
    "revolutionise", "revolutionised", "revolutionize", "revolutionized",
    "explode", "exploded", "exploding", "soar", "soared", "soaring",
    "surge", "surged", "surging", "spike", "spiked", "spiking",
    "plummet", "plummeted", "plunge", "plunged",
    "skyrockets", "multiplied", "tenfold", "overnight",
]
OUTCOME_RE = re.compile(r"\b(" + "|".join(OUTCOME_WORDS) + r")\b", re.I)
# Shared prefix so "doubled" is attested by "double" in the notes and vice
# versa, without letting an unrelated word satisfy it.
_OUTCOME_STEMS = {w: w[:6] for w in OUTCOME_WORDS}


# 2026-08-21: narrowed after a false positive cost a post. "I transformed the
# website into a comprehensive sales tool, not just a brochure" was rejected,
# but raw_notes.toml says "A website built as a sales tool rather than a
# brochure" - the draft was a faithful paraphrase. "transformed X into Y"
# describes a change of FORM; it asserts no magnitude. "conversion
# opportunities skyrocketed" asserts a RESULT. The "into" construction is what
# separates them, so it is exempted and nothing else is.
TRANSFORM_INTO_RE = re.compile(
    r"\b(?:transform(?:ed|s|ing)?|turn(?:ed|s|ing)?|convert(?:ed|s|ing)?|"
    r"rebuil[dt]|remade?)\b[^.;]{0,60}?\binto\b", re.I)


def find_invented_outcomes(text, attested=None):
    """Magnitude claims whose magnitude word is not in the attested material.

    Distinct from find_unverifiable_claims: attestation is checked on the
    outcome word, not the sentence. A sentence can sit comfortably inside
    attested territory and still smuggle in a magnitude nobody recorded.
    """
    corpus = " ".join(attested or []).lower()
    out = []
    for sent in _sentences(text):
        for m in OUTCOME_RE.finditer(sent):
            word = m.group(1).lower()
            if _OUTCOME_STEMS[word] in corpus:
                continue  # the magnitude itself is in the notes
            # "transformed the website into a sales tool" = describing what was
            # built, not claiming a result. Only the transform family can take
            # this exemption, and only with an explicit "into".
            if word.startswith(("transform", "turn", "convert", "rebuil", "remade", "remake")) \
                    and TRANSFORM_INTO_RE.search(sent):
                continue
            out.append((sent.strip(), m.group(1), "outcome not in your notes"))
            break
    return out


# Phase 3f: the voice profile's own examples were being published. Post 4 of the
# Mesh batch opened with "Most Meta ad accounts I audit are testing creative when
# the landing page is the problem" - verbatim the Good: example under rule 3. The
# claims checker could not catch it: "accounts I audit" is positioning, not a
# claim, and nothing in raw_notes.toml says it. So the examples are matched
# directly. Deterministic, no heuristics: the file is right here.
_EXAMPLE_MIN_LEN = 40


def _load_profile_examples(path=VOICE_PROFILE_PATH):
    """Every quoted example in the rules, normalised for comparison."""
    try:
        raw = open(path, encoding="utf-8").read()
    except OSError:
        return []
    if "## RULES" in raw:
        raw = raw.split("## RULES", 1)[1]
    # Anchor each example to its own Good:/Bad: marker. Scanning the whole file
    # for quoted spans mis-pairs quotes across unrelated prose and drags in
    # table text, which is what the first version of this did.
    out = []
    for span in re.findall(r'(?:Good|Bad):\s*"(.*?)"', raw, re.S | re.I):
        norm = _normalise_example(span)
        if len(norm) >= _EXAMPLE_MIN_LEN:
            out.append((norm, re.sub(r"\s+", " ", span).strip()))
    return out


def _normalise_example(text):
    t = re.sub(r"\s+", " ", str(text)).strip().lower()
    t = t.replace("\u2019", "'").replace("\u2018", "'")
    t = re.sub(r"[^a-z0-9' ]+", "", t)
    return re.sub(r"\s+", " ", t).strip()


PROFILE_EXAMPLES = _load_profile_examples()


def find_profile_echoes(text):
    """Sentences lifted from the voice profile's illustrative examples."""
    if not PROFILE_EXAMPLES:
        return []
    body = _normalise_example(text)
    hits = []
    for norm, original in PROFILE_EXAMPLES:
        if norm and norm in body:
            hits.append((original, "example text from voice-profile.md"))
    return hits


# 2026-08-21: the voice samples are deliberately OUTSIDE find_profile_echoes so
# they cannot forbid Harsh's own sentences. That left nothing enforcing "do not
# reuse these", and a caption came back as "I connected Claude AI directly to
# our Meta Ads account..." against the sample "I connected Claude AI directly to
# my Meta Ads account." - my -> our and nothing else. This catches that without
# blocking a genuine paraphrase: it measures how much of a SAMPLE SENTENCE is
# reproduced in order, so swapping one word still scores ~0.9 while rewriting
# the thought scores far lower.
import difflib

VOICE_SAMPLES = [
    "I connected Claude AI directly to my Meta Ads account. Here's what changed.",
    "Everyone talks about ROAS.",
    "Most D2C brands don't have a Meta Ads problem. They have a follow-up problem.",
]
SAMPLE_REUSE_RATIO = 0.80
_MIN_SAMPLE_TOKENS = 4


def _tokens(text):
    return re.findall(r"[a-z0-9']+", _normalise_example(text))


def _reproduced_fraction(sample_tokens, post_tokens):
    """Fraction of the sample reproduced in order, across all matching runs."""
    if not sample_tokens:
        return 0.0
    sm = difflib.SequenceMatcher(a=sample_tokens, b=post_tokens, autojunk=False)
    matched = sum(blk.size for blk in sm.get_matching_blocks())
    return matched / len(sample_tokens)


def find_sample_reuse(text):
    """A voice sample reproduced with only trivial edits."""
    post_tokens = _tokens(text)
    if not post_tokens:
        return []
    hits = []
    for sample in VOICE_SAMPLES:
        for sent in _sentences(sample):
            st = _tokens(sent)
            if len(st) < _MIN_SAMPLE_TOKENS:
                continue
            ratio = _reproduced_fraction(st, post_tokens)
            if ratio >= SAMPLE_REUSE_RATIO:
                hits.append((sent.strip(), f"{ratio:.0%} of a voice sample reused"))
                break
    return hits


# Soft benefit claims. Vague, unfalsifiable, and not in the notes - but they are
# a matter of taste rather than a fabrication, so they are LOGGED for the Slack
# review and never block. Harsh judges these himself.
SOFT_OUTCOME_RE = re.compile(
    r"\b(?:boost(?:ing|ed|s)?|enhanc(?:ing|ed|es)?|improv(?:ing|ed|es)?|"
    r"strengthen(?:ing|ed|s)?|deepen(?:ing|ed|s)?|maximis(?:ing|ed)?|"
    r"maximiz(?:ing|ed)?|driv(?:ing|es)\s+better|"
    r"leading\s+to\s+(?:better|deeper|more|higher|stronger)|"
    r"result(?:ing|ed)\s+in\s+(?:better|more|higher)|"
    r"ensuring\s+(?:better|more|higher))\b", re.I)


def find_soft_outcomes(text):
    out = []
    for sent in _sentences(text):
        m = SOFT_OUTCOME_RE.search(sent)
        if m:
            out.append({"found": m.group(0).strip(), "line": sent.strip()[:160]})
    return out


def find_bad_sources(text, attested=None):
    """Attribution to anything outside the allowlist, or to a handle.

    Phase 3f false positive: "Leads flowed in and CPL was impressive, according
    to Ads Manager" was rejected as an unallowed source. Ads Manager is Harsh's
    own account tooling and the phrase is in raw_notes.toml verbatim ("Ads
    Manager was telling me the campaign was working"). The allowlist exists to
    stop a FIGURE being hung on a publisher nobody can check; it was never
    meant to stop him describing what his own dashboard showed.

    So a named source is permitted when BOTH hold:
      - the name appears in the attested material for this post, and
      - the sentence carries no figure.
    A figure keeps rule 4b in full: it still needs an allowlisted publisher and
    a year, which find_unsourced_figures checks independently. Nothing is
    relaxed for anything the notes do not already contain.
    """
    corpus = " ".join(attested or []).lower()
    out = []
    for sent in _sentences(text):
        low = sent.lower()
        h = HANDLE_RE.search(sent)
        if h:
            out.append((sent.strip(), h.group(0).strip(), "handle or forum cited as a source"))
            continue
        m = ATTRIB_RE.search(sent)
        if not m:
            continue
        if any(src in low for src in ALLOWED_SOURCES):
            continue
        named = _normalise_example(m.group(0))
        # The matched span is like "according to Ads Manager"; test the name.
        name = re.sub(r"^(?:according to|per|based on|via|source[:]?)\s+", "",
                      named).strip()
        if name and corpus and name in corpus and not FIGURE_RE.search(sent):
            continue  # first-party tool, in the notes, and no figure attached
        out.append((sent.strip(), m.group(0), "source not on the allowlist"))
    return out


AUTHORITY_PATTERNS = [
    (r"\bresearch(?:ers)?\s+(?:shows?|suggests?|indicates?|says?|proves?|"
     r"confirms?|finds?|found|has shown|have shown)\b", "research shows"),
    (r"\b(?:studies|the studies)\s+(?:show|shows|suggest|indicate|prove|"
     r"confirm|find|found|have shown)\b", "studies show"),
    (r"\ba study\s+(?:shows?|suggests?|found|proves?|confirms?)\b", "a study shows"),
    (r"\b(?:the\s+)?data\s+(?:shows?|suggests?|indicates?|proves?|"
     r"confirms?|says?|tells us)\b", "data shows"),
    (r"\b(?:the\s+)?(?:stats|statistics|numbers)\s+(?:show|shows|suggest|"
     r"indicate|prove|say)\b", "statistics show"),
    (r"\bexperts?\s+(?:agree|say|says|recommend|suggest|note|advise)\b", "experts agree"),
    (r"\bit'?s\s+(?:proven|well[- ]documented|widely known|a known fact|"
     r"common knowledge)\b", "it's proven"),
    (r"\bproven\s+to\s+\w+", "proven to"),
    (r"\b(?:benchmarks?|industry\s+(?:data|research|studies|benchmarks?))\s+"
     r"(?:show|shows|suggest|indicate|say)\b", "benchmarks show"),
    (r"\bevidence\s+(?:shows?|suggests?|indicates?)\b", "evidence shows"),
    (r"\bknown\s+to\s+(?:convert|perform|work|win)\b", "known to convert"),
    (r"\bthe\s+sweet\s+spot\s+that\s+\w+\s+(?:shows?|says?)\b", "sweet spot that X shows"),
]
AUTHORITY_RES = [(re.compile(p, re.I), label) for p, label in AUTHORITY_PATTERNS]

# The Meta Ad Library publishes days running, active status, creative and
# placements. It does not publish, rate or "recognise" performance. Crediting
# it with a verdict is an unsourced authority claim wearing a real name.
ADLIB_RE = re.compile(r"\b(?:meta\s+)?ad\s+library\b", re.I)
ADLIB_OVERREACH_RE = re.compile(
    r"\b(?:effectiveness|effective|performance|performing|success|successful|"
    r"results|conversions?|converts?|roas|spend|impressions|engagement|"
    r"winning|wins|best[- ]performing|quality|proves?|validates?)\b", re.I)


DASH_RANGE_RE = re.compile(r"(?<=\d)\s*[\u2014\u2013]\s*(?=\d)")
DASH_RE = re.compile(r"\s*[\u2014\u2013]\s*")


def strip_em_dashes(text):
    """Replace em/en dashes with ordinary punctuation, deterministically.

    Rule 8 bans em-dashes. Blocking on them would make the model rewrite the
    sentence and it might lose the good line, so this is a post-processing
    pass: meaning is untouched, only punctuation changes. The hard checks are
    then run on the stripped text, which is also what gets published.

    A dash between two digits is a numeric range and becomes a hyphen.
    Everything else becomes a comma.
    """
    out = DASH_RANGE_RE.sub("-", text)
    out = DASH_RE.sub(", ", out)
    out = re.sub(r",\s*,+", ", ", out)          # ", ," from a pre-existing comma
    out = re.sub(r"\s+,", ",", out)             # space before comma
    out = re.sub(r",\s*([.!?;:])", r"\1", out)  # ", ." at a clause end
    out = re.sub(r",\s*$", ".", out, flags=re.M)  # dash ended the line
    return out


def find_authority_claims(text):
    """Appeals to unnamed authority. Hard-fails unless the same sentence
    names an allowed source.

    Phase 3 dry run: adspy's own scoring line "Body copy 202 chars, in the
    80-300 range that converts on Meta" came out as "the sweet spot that
    research shows converts on Meta", and the Ad Library was credited with
    recognising an ad's "longevity and effectiveness". Same failure class as
    an invented source, with no name attached to check.
    """
    hits = []
    for sent in _sentences(text):
        low = sent.lower()
        if any(src in low for src in ALLOWED_SOURCES):
            # A named allowed source carries the claim; the figure checker
            # separately requires a year alongside any number.
            if not (ADLIB_RE.search(sent) and ADLIB_OVERREACH_RE.search(sent)):
                continue
            hits.append((sent.strip(), "Ad Library credited with a verdict it does not publish"))
            continue
        for rx, label in AUTHORITY_RES:
            m = rx.search(sent)
            if m:
                hits.append((sent.strip(), label))
                break
    return hits


def find_advisory(text):
    """Wording worth a human glance. Returns {term: (matched_text, line)}."""
    hits = {}
    for term in ADVISORY_TERMS:
        lead = r"\b" if term[:1].isalnum() else ""
        tail = r"\b" if term[-1:].isalnum() else ""
        for m in re.finditer(lead + re.escape(term) + tail, text, re.I):
            line = next((l.strip() for l in text.split("\n") if m.group(0) in l), "")
            hits.setdefault(term, (m.group(0), line))
    m = NOT_JUST_RE.search(text)
    if m:
        hits.setdefault("it's not just X, it's Y", (m.group(0)[:60], m.group(0)))
    return hits


SLIDE_1_RE = re.compile(
    r"^[\s>*_`]*slide\s*1[\s*_`]*:\s*(.*)$", re.I)


def extract_slide_1(body):
    """Return the text of the carousel's first slide, or "" if absent.

    Tolerates the markdown emphasis the model sometimes adds around markers
    ("**Slide 1:**"), matching how schedule_all_posts.cjs parses them. The
    slide text may sit on the marker line or on the line below it.
    """
    lines = body.splitlines()
    for i, line in enumerate(lines):
        m = SLIDE_1_RE.match(line)
        if not m:
            continue
        # Strip emphasis BEFORE testing for content. "**Slide 1:**" leaves a
        # trailing "**" here, which is non-empty but carries no text; treating
        # it as the hook is the same defect that published a literal "**" on
        # six carousels in Phase 0b.
        rest = _strip_emphasis(m.group(1)).strip('"').strip()
        if rest:
            return rest
        for follow in lines[i + 1:]:
            cand = _strip_emphasis(follow).strip('"').strip()
            if cand:
                return cand
        return ""
    return ""


def _strip_emphasis(text):
    return re.sub(r"^[\s*_`]+|[\s*_`]+$", "", text).strip()


MARKER_LINE_RE = re.compile(
    r"^\s*(?:\*\*|__|\*|_)?\s*(Hook(?:\s*text)?|Slide\s*\d+|CAROUSEL CAPTION|"
    r"INFOGRAPHIC CAPTION)\s*(?:\*\*|__|\*|_)?\s*:", re.I)


def opening_line(text):
    """The first line a reader actually sees.

    A carousel's checked text starts with the "Slide 1:" marker, and the
    "Hook: " line is prepended further downstream, so the opening has to be
    found by skipping marker lines rather than taking lines[0].
    """
    for raw in str(text or "").split("\n"):
        line = raw.strip()
        if not line:
            continue
        m = MARKER_LINE_RE.match(line)
        if m:
            rest = line[m.end():].strip().strip('"').strip()
            if rest:
                return rest          # "Slide 1: Some hook text"
            continue                 # bare marker, text is on the next line
        return line.strip('"').strip()
    return ""


def find_opening_question(text):
    """Rule 3: the opening line must be a statement, never a question.

    2026-08-21: this was stated in voice-profile.md and enforced nowhere.
    find_midbody_questions deliberately starts at lines[1:], so the hook - the
    one line that decides whether the post travels - was the only line never
    checked. Harsh's own archive: 18% of posts opened with a question and they
    were the weakest performers, so this blocks rather than warns.
    """
    first = opening_line(text)
    if not first:
        return []
    sents = list(_sentences(first)) or [first]   # _sentences is a generator
    if sents[0].rstrip().endswith("?"):
        return [sents[0].strip()]
    return []


def find_midbody_questions(text):
    """Questions after the opening line. Weak filler, not a blocker."""
    out = []
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    for line in lines[1:]:
        if re.match(r"^(Hook|Slide \d|CAROUSEL CAPTION|INFOGRAPHIC CAPTION)\b", line, re.I):
            continue
        for sent in _sentences(line):
            if sent.rstrip().endswith("?"):
                out.append(sent.strip())
    return out


def find_external_links(text):
    return sorted({m.group(0) for m in URL_RE.finditer(text)})


# ---- Phase 2: figures must be sourced or explicitly marked hypothetical -----
# Deterministic check on markers, never a guess at intent. A fabricated-but-cited
# source ("Socialbakers 2026") is worse than no figure: it looks checkable.
ALLOWED_SOURCES = [
    "wordstream", "localiq", "databox", "triple whale",
    "meta newsroom", "meta for business",
    "statista",
    # Phase 3 addition, approved: figures from the Ad Teardown pillar come from
    # the Meta Ad Library (days_running, active status). Public and checkable -
    # anyone can open the ad. Added because the pillar cannot state how long an
    # ad has run without it, NOT to make more posts pass.
    "meta ad library", "ad library",
]

HYPOTHETICAL_MARKERS = [
    "say you're", "say you are", "say a ",
    "imagine a ", "imagine you're", "imagine you are",
    "take a brand", "take a business",
    "suppose ",
]

FIGURE_RE = re.compile(
    r"(?<![\w])("
    r"\d[\d,]*\.?\d*\s?%"
    r"|[₹$£€]\s?\d[\d,]*\.?\d*\s?(?:[LkKMCr]+)?"
    r"|\d+(?:\.\d+)?\s?[xX](?![\w])"
    r"|\d[\d,]*\s?(?:hours?|hrs?|minutes?|mins?|seconds?|secs?|days?|weeks?|months?)(?![\w])"
    r"|\d{1,3}(?:,\d{3})+"
    r")"
)
YEAR_RE = re.compile(r"\b(19|20)\d{2}\b")


def _sentences(text):
    for raw in re.split(r"(?<=[.!?])\s+|\n+", text):
        t = raw.strip()
        if t:
            yield t


def find_unsourced_figures(text):
    """Sentences with a figure but neither an allowed source + year nor a
    hypothetical marker. Returns [(sentence, [figures])]."""
    bad = []
    for sent in _sentences(text):
        figs = [m.group(0).strip() for m in FIGURE_RE.finditer(sent)]
        if not figs:
            continue
        low = sent.lower().lstrip("\"'“‘ -•*_")
        if any(low.startswith(mk) for mk in HYPOTHETICAL_MARKERS):
            continue
        if any(src in low for src in ALLOWED_SOURCES) and YEAR_RE.search(sent):
            continue
        bad.append((sent, figs))
    return bad
# ------------------------------------------------------------------------------

# ------------------------------------------------------------------------------

print(f"Loaded writing rules from {VOICE_PROFILE_PATH} ({len(writing_rules)} chars).")
# ------------------------------------------------------------------------------

system_prompt_main = f"""You are Harsh Chouksey's AI copywriter. Write a single, highly engaging LinkedIn post based on the instructions, reframing the topic around performance marketing, ads, funnels, or operations automation.
{writing_rules}
"""

# 1. Initialize/Load used_topics.json
used_topics_file = "./used_topics.json"
used_topics = []
if os.path.exists(used_topics_file):
    try:
        with open(used_topics_file, "r") as f:
            used_topics = json.load(f)
    except Exception as e:
        print(f"Error loading used_topics.json: {e}")
else:
    # Initial seed of topics used in the first run to prevent repetition
    used_topics = [
        "Lead leakage in service businesses / 2-minute WhatsApp n8n notifications",
        "In-house ads team vs Performance Marketing Agency for early stage",
        "Shifting from manual spreadsheets to automated n8n workflows",
        "Lead response delay vs booking rates (5 minutes vs 30 minutes)",
        "n8n's new advanced AI Agent Node",
        "Meta Advantage+ algorithms, n8n CRM nodes, WhatsApp rates, LinkedIn B2B ad costs",
        "Meta Advantage+ Creative automation variation pros/cons",
        "n8n Conversions API (CAPI) Integration",
        "Automating WhatsApp sales pipelines using n8n",
        "Hiring a video editor before you understand direct-response scripting",
        "How to build a lead-scoring n8n workflow"
    ]
    with open(used_topics_file, "w") as f:
        json.dump(used_topics, f, indent=2)

# Load context data
raw_notes = ""
if os.path.exists("./raw_notes.txt"):
    try:
        with open("./raw_notes.txt") as f:
            raw_notes = f.read().strip()
    except Exception as e:
        print(f"Error loading raw_notes.txt: {e}")

reddit_posts = []
if os.path.exists("./reddit_data.json"):
    try:
        with open("./reddit_data.json") as f:
            reddit_posts = json.load(f)
    except Exception as e:
        print(f"Error loading reddit_data.json: {e}")


# Prepare the planning prompt
# ---- Phase 1: batch shape comes from pipeline_config.json --------------------
# Per-slot descriptor strings are UNCHANGED prompt wording, kept here as data so
# the skeleton can be built for whatever mix the config asks for. Which slots
# appear, and in what order, is decided entirely by the config.
SLOT_TEMPLATES = {
    "carousel": [
        # slot 1 - Myth Buster. 0/4 question hooks in the archives.
        [("topic", "REPLACE THIS with the specific subject of the post, drawn from the Reddit or news items supplied below. A real subject, never a format name."),
         ("hook_style", "Myth Buster"),
         ("slide_1_hook", "Hook text (6-8 words max, a declarative statement, never a question)"),
         ("prompt_details", "Name the widely-held belief being challenged on slide 1. Slides 2-6: why it fails in practice, and what to do instead. Slide 7 CTA.")],
        # slot 3 - Benchmark Check. Replaces "Specific Result", whose name
        # instructed the model to produce a number and which generated
        # "$200K sales" and "35% boost" with no source. The figure must come
        # from outside Harsh's own unverifiable claims.
        [("topic", "REPLACE THIS with the specific subject of the post, drawn from the Reddit or news items supplied below. A real subject, never a format name."),
         ("hook_style", "Benchmark Check"),
         ("slide_1_hook", "Hook text (6-8 words max, a declarative statement, never a question)"),
         ("prompt_details", "Build the carousel around ONE published industry benchmark. Name the source organisation and the year in the slide text itself. Slides 2-6: what the figure means for a business like the reader's, and what to change because of it. Never present a figure about Harsh's own clients or campaigns as data. If no benchmark can be named with its source, use no number at all. Slide 7 CTA.")],
        # slot 5 if carousel count ever rises to 3.
        [("topic", "REPLACE THIS with the specific subject of the post, drawn from the Reddit or news items supplied below. A real subject, never a format name."),
         ("hook_style", "Teardown"),
         ("slide_1_hook", "Hook text (6-8 words max, a declarative statement, never a question)"),
         ("prompt_details", "Take one mechanism apart: how it works, where it breaks. Slides 2-6 follow the sequence. Operational detail rather than outcome claims. Slide 7 CTA.")],
    ],
    "infographic": [
        [("topic", "Infographic #1 Data Metric"),
         ("prompt_details", "Details of the specific 2025/2026 data points, categories, and metrics to use.")],
        [("topic", "Infographic #2 Benchmark Data"),
         ("prompt_details", "Details of the specific benchmark data and breakdown.")],
        [("topic", "Infographic #3 Time Saved / CPL Data"),
         ("prompt_details", "Details of specific metrics and chart breakdown.")],
    ],
    "poll": [
        [("topic", "Poll #1 Topic"),
         ("question", "A short engaging question (max 140 chars)"),
         ("options", ["Option 1 (max 30 chars)", "Option 2 (max 30 chars)", "Option 3 (max 30 chars)", "Option 4 (max 30 chars)"]),
         ("prompt_details", "Additional details on setup and explanation.")],
        [("topic", "Poll #2 Operational Choice"),
         ("question", "A short engaging question (max 140 chars)"),
         ("options", ["Option 1 (max 30 chars)", "Option 2 (max 30 chars)", "Option 3 (max 30 chars)", "Option 4 (max 30 chars)"]),
         ("prompt_details", "Additional details on setup and explanation.")],
    ],
    "text": [
        # slot 2 - Build Note. Replaces "Case Study" (75% question hooks, and
        # it invited invented client stories).
        [("topic", "REPLACE THIS with the specific subject of the post, drawn from the Reddit or news items supplied below. A real subject, never a format name."),
         ("archetype", "Build Note"),
         ("prompt_details", "Something actually wired up: which tools, how they connect, what it does now that it did not before. Concrete configuration over outcome claims. No invented client results. Open with a declarative statement. Specific DM CTA.")],
        # slot 4 - Hot Take. Lowest question rate of the text archetypes.
        [("topic", "REPLACE THIS with the specific subject of the post, drawn from the Reddit or news items supplied below. A real subject, never a format name."),
         ("archetype", "Hot Take"),
         ("prompt_details", "A position, stated plainly in the first line and then defended. Not a question, not a teaser. Specific DM CTA.")],
        # slot 5 - Teardown. Replaces "Tool Spotlight" (75% question hooks,
        # and it read as promotion).
        [("topic", "REPLACE THIS with the specific subject of the post, drawn from the Reddit or news items supplied below. A real subject, never a format name."),
         ("archetype", "Teardown"),
         ("prompt_details", "How one mechanism works and where it breaks. Operational detail, step by step. No invented numbers. Open with a declarative statement. Specific DM CTA.")],
    ],
}


def _render_slot(position, fmt, index):
    variants = SLOT_TEMPLATES.get(fmt)
    if not variants:
        raise SystemExit(f"FATAL: no slot template for format '{fmt}' (check pipeline_config.json)")
    fields = variants[min(index - 1, len(variants) - 1)]
    key = f"{position}. {fmt.upper()} {index}"
    parts = []
    for k, v in fields:
        if isinstance(v, list):
            inner = ", ".join(json.dumps(x) for x in v)
            parts.append(f'    "{k}": [{inner}]')
        else:
            parts.append(f'    "{k}": {json.dumps(v)}')
    return f'  "{key}": {{\n' + ",\n".join(parts) + "\n  }"


def _render_skeleton(sequence):
    slots = [_render_slot(i + 1, fmt, idx) for i, (fmt, idx) in enumerate(sequence)]
    return "{\n" + ",\n".join(slots) + "\n}"


PLAN_SKELETON = _render_skeleton(SLOT_SEQUENCE)

# ---- Phase 3: the plan comes from PILLARS, not from a planning LLM call ------
# Topic selection used to be an LLM call over "whatever Reddit surfaced today",
# which produced a peer audience (18% IT services, 15% advertising, 4% founders)
# and, when it had nothing, invented. Each weekday now has a fixed pillar with a
# real source. The plan is built in code from what those sources actually
# returned, so there is nothing for the model to invent at the topic stage.
#
# Pillar and format stay independent: the pillar decides the SOURCE, the format
# comes from format_mix exactly as in Phase 1.
import sources_loader

sources_loader.LLM = call_llm  # matcher for community-question; circular if imported there

PILLARS = CONFIG.get("pillars") or []
angle_state = notes_loader.load_used_angles()
# 2026-08-21: what each pillar has already CONSUMED, as opposed to which angle
# it used. Carried on the same state dict under a private key so it reaches the
# loaders; save_used_angles() strips "_" keys, so it never lands in the wrong
# file. Written to used_sources.json after the batch, for saved posts only.
source_state = notes_loader.load_used_sources()
angle_state["_used_sources"] = source_state

print("")
print(f"Resolving {len(PILLARS)} pillars to real material...")
content_plan = {}
pillar_items = {}

skipped_pillars = []

for position, (pillar, (fmt, per_format_idx)) in enumerate(zip(PILLARS, SLOT_SEQUENCE), 1):
    try:
        item = sources_loader.resolve_pillar(pillar, fmt, CONFIG, angle_state)
    except sources_loader.PillarUnavailable as exc:
        # One pillar failing costs one day, not the batch.
        skipped_pillars.append({
            "day": pillar.get("day", "?"),
            "pillar": pillar.get("id", exc.pillar),
            "format": fmt,
            "reason": exc.title,
            "detail": exc.detail.strip(),
        })
        print(f"  {pillar.get('day','?'):4} {pillar.get('id','?'):20} {fmt:9} "
              f"** SKIPPED: {exc.title}")
        continue
    slot_key = f"{position}. {fmt.upper()} {per_format_idx}"
    variants = SLOT_TEMPLATES.get(fmt, [])
    tmpl = dict(variants[min(per_format_idx - 1, len(variants) - 1)]) if variants else {}

    val = {
        "topic": item["headline"],
        "prompt_details": item["material"],
    }
    if "hook_style" in tmpl:
        val["hook_style"] = tmpl["hook_style"]
    if "archetype" in tmpl:
        val["archetype"] = tmpl["archetype"]

    content_plan[slot_key] = val
    pillar_items[slot_key] = item
    print(f"  {item['day']}  {item['pillar_id']:20} {fmt:9} <- {item['source']}"
          f"  [{item['reference']}]")

if not content_plan:
    print("=" * 64)
    if skipped_pillars:
        print("FATAL: every pillar failed, so there is nothing to write.")
        for sk in skipped_pillars:
            print(f"  {sk['day']} {sk['pillar']}: {sk['reason']}")
            if sk["detail"]:
                print(sk["detail"])
    else:
        print("FATAL: no pillars configured, so there is nothing to write.")
    print("=" * 64)
    sys.exit(1)

if skipped_pillars:
    print("")
    print("-" * 64)
    print(f"SHORT BATCH: {len(content_plan)} of {len(PILLARS)} days will be "
          f"written. {len(skipped_pillars)} pillar(s) produced nothing:")
    for sk in skipped_pillars:
        print(f"  {sk['day']}  {sk['pillar']} ({sk['format']}): {sk['reason']}")
    print("  Nothing is scheduled at generation time, so the rest of the batch")
    print("  is unaffected. The missing day(s) are carried into the Slack")
    print("  review so the gap is visible before anything is posted.")
    print("-" * 64)
    with open("missing_days.json", "w") as f:
        json.dump(skipped_pillars, f, indent=2)
else:
    # Never leave a stale file behind to be read by the next run's review.
    if os.path.exists("missing_days.json"):
        os.remove("missing_days.json")
print("")
# ------------------------------------------------------------------------------

posts_to_generate = []
for post_id, val in content_plan.items():
    topic = val.get("topic", "")
    details = val.get("prompt_details", "")

    # NOTE (Phase 0): the topic is deliberately NOT recorded here. It is carried
    # on the item below and written to used_topics.json only after its post has
    # been generated AND saved to disk. See the write after the generation loop.

    # Phase 0b: carousels only. Carried onto the item so the planner's hook can
    # be surfaced in the post body as a "Hook: " line (see the generation loop).
    slide_1_hook = ""

    if "POLL" in post_id:
        question = val.get("question", "Choose the best option:")
        options = val.get("options", [])
        opt_str = "\n".join([f"☐ {opt}" for opt in options])
        prompt = f"""Write a POLL post.
Topic: {topic}
Details: {details}
Question: {question}
Options:
{opt_str}
Provide the Setup, the Question, the 4 Options, and an Explanation prompt. Do not include any title.
"""
    elif "CAROUSEL" in post_id:
        hook_style = val.get("hook_style", "Curiosity Gap")
        prompt = f"""Write a CAROUSEL post content.
Topic: {topic}
Chosen Hook Style: {hook_style}
Details: {details}

SLIDE 1 IS THE HOOK, AND IT IS A SENTENCE. Write it in Harsh's voice, exactly
like the samples in the writing rules: a flat declarative claim, roughly 6 to 14
words, ordinary words, no wind-up, never a question.

It must be a SENTENCE, not a title. A title has a colon in it, or starts with an
-ing word, or names a topic instead of making a claim. All three are wrong here:
  Wrong: "Flipkart's Carousel Ad: Breaking Down the Myth"
  Wrong: "Enhancing proxy security with specific TLS settings"
  Right: "Flipkart has run the same ad for over a month."
  Right: "Your proxy was only checking TLS at the front door."
If you can put a full stop at the end and it reads as something a person would
say out loud, it is a sentence. If it reads like a headline on a slide deck,
rewrite it.

Do not think about the LinkedIn document title while writing this. That is
derived separately, downstream, and is not your problem.

MARKER FORMAT. Emit every marker as plain text on its own line, exactly as
shown. Never bold, italicise or wrap a marker in asterisks, underscores or
backticks. Never add numbering, quotes or extra punctuation around a marker.

Slide 1:
[hook text]

Slide 2:
[text]

(continue through Slide 7)

CAROUSEL CAPTION:
[the caption that will be published as the post body]

Correct:   CAROUSEL CAPTION:
Wrong:     **CAROUSEL CAPTION:**   *CAROUSEL CAPTION:*   __CAROUSEL CAPTION:__
"""
    elif "INFOGRAPHIC" in post_id:
        prompt = f"""Write an INFOGRAPHIC caption.
Topic: {topic}
Details: {details}
Provide the hook, key insights, and a clear description of the data. Do not include titles.

MARKER FORMAT. Emit the marker as plain text on its own line, exactly as shown.
Never bold, italicise or wrap it in asterisks, underscores or backticks.

INFOGRAPHIC CAPTION:
[the caption that will be published as the post body]

Correct:   INFOGRAPHIC CAPTION:
Wrong:     **INFOGRAPHIC CAPTION:**   *INFOGRAPHIC CAPTION:*
"""
    else:
        archetype = val.get("archetype", "Insight")
        prompt = f"""Write a LinkedIn post.
Topic: {topic}
Archetype: {archetype}
Details: {details}
Start directly with the hook. No titles. Do not include headers.
"""
    _item = pillar_items.get(post_id, {})
    posts_to_generate.append({
        "id": post_id,
        "topic": topic,
        "hook": slide_1_hook,
        "prompt": prompt,
        "attested": _item.get("attested") or [],
        "pillar": _item.get("pillar_id"),
        "source": _item.get("source"),
        "angle_key": _item.get("angle_key"),
        "source_key": _item.get("source_key"),
        "pillar_id": _item.get("pillar_id"),
        "thesis": _item.get("thesis"),
    })

generated_posts = {}
REVIEW_FLAGS = []
rejected_posts_log = []
saved_ids = set()
all_output_text = ""
generated_topics = []

print(f"Generating {len(posts_to_generate)} Main Posts...")
for item in posts_to_generate:
    print(f"Generating {item['id']}...")
    # Generate, then ENFORCE the ban list in code. One rewrite naming the exact
    # offending terms; abort if the rewrite still violates.
    # Generate once. NO sentence-level repair: three runs showed it swaps a
    # synonym ("seamlessly" -> "effortlessly") or deletes the sentence, and in
    # one case removed the best worked example in the batch. Code cannot improve
    # writing. It can only stop something being published that would have to be
    # defended - and those are the only checks that block.
    result = call_llm(system_prompt_main, item["prompt"], max_tokens=4000)
    if not result:
        print(f"Error: Failed to generate {item['id']}.")
        print("used_topics.json was NOT updated — no topic is burned for a post "
              "that was never produced.")
        sys.exit(1)

    # HARD CHECKS - safety, not taste. Worth a failed batch. No repair, no retry:
    # rewriting an unverifiable claim only relocates the fabrication.
    # Rule 8 is enforced by rewriting, not by rejection: strip the dashes,
    # then run every hard check against the text that will actually publish.
    dashes = len(DASH_RE.findall(result))
    if dashes:
        result = strip_em_dashes(result)
        print(f"  {item['id']}: {dashes} em-dash(es) replaced with commas")

    authority = find_authority_claims(result)
    echoes = find_profile_echoes(result)
    reuse = find_sample_reuse(result)
    open_q = find_opening_question(result)
    bad_figures = find_unsourced_figures(result)
    links = find_external_links(result)
    claims = find_unverifiable_claims(result, item.get("attested"))
    outcomes = find_invented_outcomes(result, item.get("attested"))
    bad_sources = find_bad_sources(result, item.get("attested"))
    if (bad_figures or links or claims or bad_sources or authority
            or outcomes or echoes or reuse or open_q):
        print("=" * 64)
        print(f"FATAL: {item['id']} would publish something indefensible.")
        if claims:
            print("  Unverifiable claims about Harsh's own work (nothing in this")
            print("  pipeline knows whether these are true):")
            for sent, matched, label in claims:
                print(f"    - [{label}] \"{matched}\"")
                print(f"        in: {sent[:92]}")
        if open_q:
            print("  The opening line is a QUESTION. Rule 3 requires a statement:")
            print(f"    - \"{open_q[0][:96]}\"")
            print("    18% of this account's archive opened with a question and")
            print("    those were its weakest posts. Rewrite it as a flat claim.")
        if reuse:
            print("  A voice SAMPLE was reused almost verbatim. The samples show")
            print("  you how Harsh writes; they are already published, so reusing")
            print("  the wording republishes an old line. Write a new sentence:")
            for original, label in reuse:
                print(f"    - [{label}] \"{original[:88]}\"")
        if echoes:
            print("  Text lifted from voice-profile.md's illustrative examples")
            print("  (those examples are not material about Harsh):")
            for original, label in echoes:
                print(f"    - \"{original[:100]}\"")
        if outcomes:
            print("  Outcome claims whose magnitude is not in raw_notes.toml:")
            for sent, matched, label in outcomes:
                print(f"    - [{label}] \"{matched}\"")
                print(f"        in: {sent[:92]}")
        if authority:
            print("  Appeals to authority with no named source (nothing in this")
            print("  pipeline knows what research, data or experts say):")
            for sent, label in authority:
                print(f"    - [{label}]")
                print(f"        in: {sent[:92]}")
        if bad_sources:
            print("  Sources outside the allowlist:")
            for sent, matched, label in bad_sources:
                print(f"    - [{label}] {matched}")
                print(f"        in: {sent[:92]}")
        if bad_figures:
            print("  Figures with no allowed source and year, and no hypothetical marker:")
            for sent, figs in bad_figures:
                print(f"    - {', '.join(figs)}  in: {sent[:88]}")
        if links:
            print("  External links in the post body:")
            for u in links:
                print(f"    - {u}")
        print("")
        # The rejected draft is written out so a failed batch is still
        # inspectable. It is NOT saved to linkedin_posts_today.txt and can
        # never be scheduled - the scheduler only ever reads that file.
        os.makedirs("rejected_posts", exist_ok=True)
        safe = re.sub(r"[^A-Za-z0-9]+", "_", item["id"]).strip("_")
        rej = os.path.join("rejected_posts", f"{safe}.txt")
        with open(rej, "w") as _f:
            _f.write(f"REJECTED: {item['id']}\npillar: {item.get('pillar')}\n"
                     f"source: {item.get('source')}\n{'-'*60}\n{result}\n")
        print(f"  Draft written to {rej} for inspection (never schedulable).")
        print("  Skipping this post and continuing with the rest of the batch.")
        print("  It is not saved and used_topics.json was NOT updated for it.")
        print("=" * 64)
        # Phase 3f: a rejected post used to sys.exit(1). In the Mesh batch that
        # threw away three posts that had already passed, for the same reason a
        # failed pillar used to throw away the batch. Nothing is scheduled at
        # generation time, so there is nothing to protect. NO retry and NO
        # checker is relaxed: the draft is rejected exactly as before, it just
        # no longer takes its siblings with it.
        reasons = []
        if echoes:
            reasons.append("text lifted from voice-profile.md examples")
        if claims:
            reasons.append(f"unverifiable claim: \"{claims[0][1]}\"")
        if outcomes:
            reasons.append(f"invented outcome: \"{outcomes[0][1]}\"")
        if authority:
            reasons.append(f"appeal to authority: {authority[0][1]}")
        if bad_sources:
            reasons.append(f"source outside the allowlist: {bad_sources[0][1]}")
        if bad_figures:
            reasons.append(f"unsourced figure: {', '.join(bad_figures[0][1])}")
        if links:
            reasons.append("external link in the body")
        rejected_posts_log.append({
            "post": item["id"],
            "pillar": item.get("pillar"),
            "source": item.get("source"),
            "reasons": reasons,
            "draft": rej,
        })
        continue

    # ADVISORY - logged and surfaced in the Slack review. Never blocking.
    adv = find_advisory(result)
    qs = find_midbody_questions(result)
    soft = find_soft_outcomes(result)
    if adv or qs or soft:
        REVIEW_FLAGS.append({
            "post": item["id"],
            "wording": [{"term": t, "found": v[0], "line": v[1]} for t, v in sorted(adv.items())],
            "questions": qs,
            "soft_outcomes": soft,
        })
        bits = []
        if adv:
            bits.append(f"{len(adv)} wording note(s): {', '.join(v[0] for v in adv.values())}")
        if qs:
            bits.append(f"{len(qs)} mid-body question(s)")
        if soft:
            bits.append(f"{len(soft)} soft outcome claim(s): "
                        + ", ".join(x["found"] for x in soft[:3]))
        print(f"  {item['id']}: {'; '.join(bits)} (for review, not blocking)")

    generated_posts[item["id"]] = result
    if item["topic"]:
        generated_topics.append(item["topic"])

    body = result.strip()

    # Phase 0b: surface the planner's slide_1_hook as a "Hook: " line so the
    # scheduler can use it as the LinkedIn document title instead of falling
    # back to truncated caption text. Written ABOVE the post body, therefore
    # above the "CAROUSEL CAPTION:" marker, so it is never captured into the
    # published caption. Carousels only; no other post type is touched.
    # Phase 3 fix: the hook is taken from the model's actual Slide 1, not from
    # the plan. Until now the plan injected the literal string "A declarative
    # statement, 6-8 words, never a question", which was written into the post
    # as the Hook line and would have been typed as the LinkedIn document
    # title. Slide 1 IS the hook, so read it back out of the generated post.
    if "CAROUSEL" in item["id"]:
        hook = extract_slide_1(body)
        if not hook:
            print("=" * 64)
            print(f"REJECTED: {item['id']} produced no readable 'Slide 1:' line,")
            print("  so there is no hook to use as the document title.")
            print("  Skipping this post; the rest of the batch continues.")
            print("=" * 64)
            generated_posts.pop(item["id"], None)
            if item["topic"] and item["topic"] in generated_topics:
                generated_topics.remove(item["topic"])
            rejected_posts_log.append({
                "post": item["id"], "pillar": item.get("pillar"),
                "source": item.get("source"),
                "reasons": ["no readable 'Slide 1:' line, so no document title"],
                "draft": None,
            })
            continue
        body = f"Hook: {hook}\n\n{body}"

    all_output_text += "==================================================\n"
    all_output_text += f"{item['id']}\n"
    all_output_text += "==================================================\n"
    all_output_text += body + "\n\n"
    saved_ids.add(item["id"])
    time.sleep(1)

# Write output text files
# Every post rejected means there is no batch. Writing an empty file here would
# hand the scheduler a file it would read as "no posts"; the Phase 0 empty-batch
# guard would catch it, but the honest place to stop is here, before anything is
# written and before any topic or angle is recorded.
if not saved_ids:
    print("=" * 64)
    print("FATAL: every post in this batch was rejected. Nothing is saved.")
    for r in rejected_posts_log:
        print(f"  {r['post']} ({r['pillar']}): {'; '.join(r['reasons'])}")
    print("  used_topics.json and used_angles.json were NOT updated, so no")
    print("  topic or angle is burned. Drafts are in rejected_posts/.")
    print("=" * 64)
    sys.exit(1)

date_compact = datetime.date.today().isoformat().replace("-", "")
with open("linkedin_posts_today.txt", "w") as f:
    f.write(all_output_text)
with open(f"linkedin_posts_{date_compact}.txt", "w") as f:
    f.write(all_output_text)
print(f"{len(saved_ids)} of {len(posts_to_generate)} Main Posts saved to "
      f"linkedin_posts_{date_compact}.txt")
if rejected_posts_log:
    print("-" * 64)
    print(f"{len(rejected_posts_log)} post(s) rejected by the hard checks and "
          f"NOT saved:")
    for r in rejected_posts_log:
        print(f"  {r['post']} ({r['pillar']}): {'; '.join(r['reasons'])}")
    print("  No checker was relaxed and nothing was retried. The drafts are in")
    print("  rejected_posts/ and are carried into the Slack review.")
    print("-" * 64)
    with open("rejected_posts.json", "w") as f:
        json.dump(rejected_posts_log, f, indent=2)
elif os.path.exists("rejected_posts.json"):
    os.remove("rejected_posts.json")

# Tier-2 hits go to the Slack review so a human decides, not the code.
with open("review_flags.json", "w") as f:
    json.dump(REVIEW_FLAGS, f, indent=2)
print(f"Review flags: {len(REVIEW_FLAGS)} post(s) with wording or question notes -> review_flags.json")

# ---- Phase 0: record used topics AFTER their posts exist on disk -------------
# Previously this write happened before the generation loop, so a failure at
# post 4 still burned all 11 topics for posts that were never produced.
# Phase 3: record which raw_notes angle was used, so the next batch draws a
# different one. Recorded only after the posts are on disk, same ordering
# principle as used_topics.json.
# 2026-08-21: CONSUMPTION MOVED TO SCHEDULING TIME.
# Generating a draft used to burn the pool: used_topics, used_angles and
# used_sources were written here, the moment a post reached disk. But a post on
# disk is not a post on LinkedIn - publishing happens later, in
# schedule_all_posts.cjs, and a draft that is never scheduled still consumed a
# benchmark figure, a Reddit question and two angles on 2026-08-21.
#
# So this step now only DECLARES what each saved post would consume. The
# scheduler records it per post, immediately after that post is actually on
# LinkedIn's queue, next to the checkpoint write. Nothing is marked used until
# it is live.
manifest = {
    "generated_at": datetime.datetime.now().isoformat(timespec="seconds"),
    "source_file": "linkedin_posts_today.txt",
    "posts": [],
}
for _it in posts_to_generate:
    if _it["id"] not in saved_ids:
        continue  # rejected: it consumes nothing
    manifest["posts"].append({
        "id": _it["id"],
        "topic": _it.get("topic") or "",
        "angle_key": _it.get("angle_key"),
        "thesis": _it.get("thesis"),
        "pillar_id": _it.get("pillar_id"),
        "source_key": _it.get("source_key"),
    })
with open("batch_manifest.json", "w") as f:
    json.dump(manifest, f, indent=2)
print(f"batch_manifest.json written: {len(manifest['posts'])} post(s) declare what")
print("  they will consume. NOTHING is marked used yet - schedule_all_posts.cjs")
print("  records each one only once it is on LinkedIn's queue.")
for m in manifest["posts"]:
    bits = [b for b in (m["angle_key"], m["source_key"]) if b]
    print(f"    {m['id']}: {', '.join(bits) if bits else 'topic only'}")

# -----------------------------------------------------------------------------

# Now generate Carousel JSONs for all 3 Carousel posts
# Mirror of the fields require_slide_val() demands in generate_carousel_today.py.
# If the renderer's requirements change, change this too - the renderer is the
# authority and will abort independently if they drift apart.
CAROUSEL_REQUIRED_FIELDS = {
    "1": ["HEADER_LABEL", "HOOK_PART_1", "HOOK_PART_2", "HOOK_EMPHASIS", "SUBTITLE"],
    "2": ["PILL_LABEL", "EYEBROW", "HEADLINE_PART_1", "HEADLINE_PART_2", "HEADLINE_EMPHASIS", "SUBHEAD", "BODY_TEXT"],
    "3": ["HEADER_LABEL", "HUGE_STAT", "CIRCLE_WORD_1", "CIRCLE_WORD_2", "HEADLINE_PART_1", "HEADLINE_PART_2", "HEADLINE_EMPHASIS", "BODY_TEXT"],
    "4": ["PILL_LABEL", "EYEBROW", "HEADLINE_PART_1", "HEADLINE_PART_2", "HEADLINE_EMPHASIS", "SUBHEAD", "BODY_TEXT"],
    "5": ["HEADER_LABEL", "HUGE_STAT", "CIRCLE_WORD_1", "CIRCLE_WORD_2", "HEADLINE_PART_1", "HEADLINE_PART_2", "HEADLINE_EMPHASIS", "BODY_TEXT"],
    "6": ["HEADER_LABEL", "HUGE_STAT", "HEADLINE_PART_1", "HEADLINE_PART_2", "HEADLINE_EMPHASIS", "SUBHEAD", "BODY_TEXT"],
    "7": ["HEADLINE_PART_1", "HEADLINE_PART_2", "HEADLINE_EMPHASIS", "SUBHEAD"],
}

RETRY_SUFFIX = """

YOUR PREVIOUS ATTEMPT LEFT THESE EXACT FIELDS EMPTY:
{fields}

Fill every one of them with a non-empty value that obeys the FIELD RULES above.
Re-read the length and shape rule for each named field before answering. Every
other field must also remain non-empty. Output only JSON.
"""

carousel_keys = [k for k in generated_posts.keys() if "CAROUSEL" in k]
for idx, key in enumerate(carousel_keys, 1):
    print(f"Generating Carousel JSON #{idx} ({key})...")
    carousel_json_prompt = f"""
You are Harsh Chouksey's AI visual content designer.
Based on the generated Carousel post below, generate the structured JSON configuration for the Carousel slides.

Post Content:
{generated_posts.get(key, "")}

Format your output as a single valid JSON object. Do NOT wrap it in any markdown code block, and do NOT include any other text before or after the JSON.

EVERY FIELD IS REQUIRED. Do not omit a key. Do not emit an empty string, a
null, or a placeholder like "N/A" or "-". If you are unsure what to put in a
field, write something true and specific about this post's topic. A missing or
empty field aborts the build and the carousel is not published.

FIELD RULES. Each field has a job, a length, and a shape. Single generic words
are a failure: a card reading "CONTENT" or "TECH" says nothing.

  HEADER_LABEL / PILL_LABEL / EYEBROW
    Job: the section label at the top of the slide.
    Length: 2 to 4 words, UPPERCASE, 10-28 characters.
    Good: "LEAD RESPONSE TIME"  "META ADS BUDGET"  "THE BOTTLENECK"
    Bad:  "TECH"  "CONTENT"  "STRATEGY"        (one vague word)

  HOOK_PART_1 / HOOK_PART_2 / HEADLINE_PART_1 / HEADLINE_PART_2
    Job: the headline, split across two lines that read as one sentence.
    Length: 3 to 6 words each, 18-40 characters each.
    Good: "We cut cost per lead" + "by 60% in three weeks"
    Bad:  "Success" + "story"                  (not a sentence)

  HOOK_EMPHASIS / HEADLINE_EMPHASIS
    Job: the one phrase set in italic serif at the end of the headline.
    Length: 1 to 3 words, 4-24 characters. No full stop, the template adds one.
    Good: "in three weeks"  "60% lower"  "WhatsApp"
    Bad:  "SUCCESS"  "CONTENT"  "Wrong"        (vague, or the whole point lost)

  HUGE_STAT
    Job: one figure shown very large.
    Length: 2-8 characters, a number with its unit.
    Good: "9.21x"  "₹50k"  "2 min"  "45%"
    Bad:  "a lot"  "high"  ""                  (not a figure)

  CIRCLE_WORD_1 / CIRCLE_WORD_2
    Job: two words in a circle that annotate the stat above.
    Length: one word each, 3-10 characters, UPPERCASE.
    Good: "LOWER" + "CPL"      "AUTO" + "REPLY"
    Bad:  "GOOD" + "RESULT"                    (says nothing about the stat)

  SUBTITLE
    Job: the setup line under the slide 1 hook.
    Length: 1 to 2 sentences, 80-200 characters.
    Good: "A real estate client was losing half their leads to slow follow-up.
           We wired Meta lead forms into WhatsApp and replies went out in 60 seconds."
    Bad:  "This is about lead automation."     (no specific detail)

  SUBHEAD
    Job: one sentence that lands the slide's point.
    Length: 30-120 characters. A full sentence, not a fragment.
    Good: "The longer a lead sits, the colder it gets."
    Bad:  "Completely."  "Yes."                (a fragment, not a sentence)

  BODY_TEXT
    Job: the supporting detail at the bottom of the slide.
    Length: 1 to 2 sentences, 60-180 characters.
    Good: "Manual follow-up meant leads waited 40 minutes on average. The
           automated route answers in under one."
    Bad:  "It works better."                   (no mechanism, no number)

Do not invent client names, revenue figures or case-study outcomes. Use the
detail supplied in the post content above. If the post content has no number,
do not manufacture one for HUGE_STAT: use a figure that appears in the post, or
describe the change in words within the length limit.

Your JSON must strictly follow this structure:
{{
  "1": {{
    "HEADER_LABEL": "WORKFLOW AUTOMATION",
    "HOOK_PART_1": "0 to ₹10L/mo",
    "HOOK_PART_2": "lead nurture scaling",
    "HOOK_EMPHASIS": "LEAD NURTURE",
    "SUBTITLE": "How a startup replaced manual spreadsheets with n8n pipelines."
  }},
  "2": {{
    "PILL_LABEL": "THE PROBLEM",
    "EYEBROW": "MANUAL BOARDS",
    "HEADLINE_PART_1": "Leads rot on CRM",
    "HEADLINE_PART_2": "spreadsheets for days",
    "HEADLINE_EMPHASIS": "CRM",
    "SUBHEAD": "The longer a lead sits, the colder it gets.",
    "BODY_TEXT": "Hiring manual SDRs burns ad budget."
  }},
  "3": {{
    "HEADER_LABEL": "THE SOLUTION",
    "HUGE_STAT": "2 Min",
    "CIRCLE_WORD_1": "AUTO",
    "CIRCLE_WORD_2": "REPLY",
    "HEADLINE_PART_1": "Connect Meta leads",
    "HEADLINE_PART_2": "directly to n8n pipelines",
    "HEADLINE_EMPHASIS": "N8N",
    "BODY_TEXT": "Trigger automated WhatsApp messages instantly."
  }},
  "4": {{
    "PILL_LABEL": "LEAD SCORING",
    "EYEBROW": "AI FILTER",
    "HEADLINE_PART_1": "Score leads before",
    "HEADLINE_PART_2": "routing to sales",
    "HEADLINE_EMPHASIS": "SCORE",
    "SUBHEAD": "Identify the high-intent buyers.",
    "BODY_TEXT": "AI nodes qualify leads automatically."
  }},
  "5": {{
    "HEADER_LABEL": "WhatsApp CRM",
    "HUGE_STAT": "60%",
    "CIRCLE_WORD_1": "LOWER",
    "CIRCLE_WORD_2": "CPL",
    "HEADLINE_PART_1": "Auto-nurture leads with",
    "HEADLINE_PART_2": "WhatsApp conversation flows",
    "HEADLINE_EMPHASIS": "WHATSAPP",
    "BODY_TEXT": "Personalized chat funnels build trust."
  }},
  "6": {{
    "HEADER_LABEL": "THE RESULTS",
    "HUGE_STAT": "30 Hrs",
    "HEADLINE_PART_1": "Save time and scale",
    "HEADLINE_PART_2": "ad campaign budgets",
    "HEADLINE_EMPHASIS": "SCALE",
    "SUBHEAD": "Systematic scaling beats manual operations.",
    "BODY_TEXT": "Automated data feedback optimizes ads."
  }},
  "7": {{
    "HEADLINE_PART_1": "Scale traffic and",
    "HEADLINE_PART_2": "automate lead systems",
    "HEADLINE_EMPHASIS": "SCALE",
    "SUBHEAD": "Follow @harshchouksey or DM 'SCALE' to build an automated growth engine."
  }}
}}
"""
    # ---- Phase 2: validate, retry once, never save a partial carousel --------
    # The renderer requires all 46 fields. Measured across the last archived run
    # the model filled 45/46, 39/46 and 36/46 - the failure mode being
    # present-but-empty strings, not missing keys. The FIELD RULES block above is
    # the primary fix; this is the safety net.
    def _strip_fence(t):
        t = (t or "").strip()
        if t.startswith("```json"):
            t = t[7:]
        elif t.startswith("```"):
            t = t[3:]
        if t.endswith("```"):
            t = t[:-3]
        return t.strip()

    def _empty_fields(obj):
        bad = []
        for sl, keys in CAROUSEL_REQUIRED_FIELDS.items():
            slide = obj.get(sl) or {}
            if not isinstance(slide, dict):
                bad.append((sl, "<slide missing>"))
                continue
            for k in keys:
                v = slide.get(k)
                if v is None or str(v).strip() == "":
                    bad.append((sl, k))
        return bad

    c_data = None
    missing = None
    for attempt in (1, 2):
        raw = call_llm("You are a JSON writer. Only output raw JSON.",
                          carousel_json_prompt if attempt == 1 else carousel_json_prompt + RETRY_SUFFIX.format(
                              fields="\n".join(f"  - slide {sl}: {k}" for sl, k in (missing or []))),
                          max_tokens=4000)
        if not raw:
            print(f"Carousel JSON #{idx}: no response on attempt {attempt}.")
            continue
        try:
            candidate = json.loads(_strip_fence(raw))
        except Exception as e:
            print(f"Carousel JSON #{idx}: unparseable on attempt {attempt}: {e}")
            continue
        missing = _empty_fields(candidate)
        if not missing:
            c_data = candidate
            break
        print(f"Carousel JSON #{idx}: attempt {attempt} left {len(missing)} field(s) empty"
              + (" - retrying once." if attempt == 1 else "."))

    if c_data is None:
        print("=" * 64)
        print(f"FATAL: carousel {idx} JSON incomplete after 2 attempts.")
        if missing:
            print(f"  {len(missing)} required field(s) still empty:")
            for sl, k in missing:
                print(f"    slide {sl}: {k}")
        print("  Not saving a partial carousel: the renderer would abort anyway,")
        print("  and a half-filled carousel must never reach LinkedIn.")
        print("=" * 64)
        sys.exit(1)

    with open(f"./carousel_data_{idx}.json", "w") as f:
        json.dump(c_data, f, indent=2)
    if idx == 1:
        with open("./carousel_data.json", "w") as f:
            json.dump(c_data, f, indent=2)
    print(f"Saved carousel_data_{idx}.json (all {sum(len(v) for v in CAROUSEL_REQUIRED_FIELDS.values())} fields present).")
    # --------------------------------------------------------------------------

# Now generate Infographic JSONs for all 3 Infographic posts
infographic_keys = [k for k in generated_posts.keys() if "INFOGRAPHIC" in k]
for idx, key in enumerate(infographic_keys, 1):
    print(f"Generating Infographic JSON #{idx} ({key})...")
    infographic_json_prompt = f"""
You are Harsh Chouksey's AI visual content designer.
Based on the generated Infographic post below, generate the structured JSON configuration for the Infographic.

Post Content:
{generated_posts.get(key, "")}

Format your output as a single valid JSON object. Do NOT wrap it in any markdown code block, and do NOT include any other text before or after the JSON.
Your JSON must strictly follow this structure:
{{
  "title_main": "Lead Response Time Vs",
  "title_span": "Booking Rates",
  "subtitle": "How instant automated follow-ups affect sales booking conversions.",
  "badge": "📊 PIPELINE CONVERSIONS",
  "date_label": "2025 Lead Gen Report",
  "takeaway_num": "5 Mins",
  "takeaway_text": "is the critical threshold. Contacting leads within 5 minutes yields a 391% higher booking rate.",
  "source": "Source: Industry Benchmark | @harshchouksey",
  "bars": [
    {{ "label": "Under 5 Minutes (Auto-WhatsApp) - 95%", "value": "95%", "color": "#E63946" }},
    {{ "label": "5 to 10 Minutes - 55%", "value": "55%", "color": "#D9785B" }},
    {{ "label": "10 to 30 Minutes - 25%", "value": "25%", "color": "#E8A33D" }},
    {{ "label": "Over 30 Minutes - 10%", "value": "10%", "color": "#5E6AD2" }}
  ]
}}
"""
    infographic_json_str = call_llm("You are a JSON writer. Only output raw JSON.", infographic_json_prompt, max_tokens=4000)
    if infographic_json_str:
        infographic_json_str = infographic_json_str.strip()
        if infographic_json_str.startswith("```json"):
            infographic_json_str = infographic_json_str[7:]
        elif infographic_json_str.startswith("```"):
            infographic_json_str = infographic_json_str[3:]
        if infographic_json_str.endswith("```"):
            infographic_json_str = infographic_json_str[:-3]
        infographic_json_str = infographic_json_str.strip()
        try:
            info_data = json.loads(infographic_json_str)
            with open(f"./infographic_data_{idx}.json", "w") as f:
                json.dump(info_data, f, indent=2)
            if idx == 1:
                with open("./infographic_data.json", "w") as f:
                    json.dump(info_data, f, indent=2)
            print(f"Saved infographic_data_{idx}.json successfully!")
        except Exception as e:
            print(f"Error parsing Infographic JSON #{idx}: {e}")

# ---- Performance posts (disabled by default since Phase 1) -------------------
# Generated every run, written to performance_posts_<date>.txt, and read by
# NOTHING: the scheduler reads linkedin_posts_today.txt and so does the Slack
# gate. They cost ~40% of each run's LLM calls, and because this block runs last
# and exits non-zero on failure, one unpublishable post could abort the whole
# pipeline AFTER topics were already burned into used_topics.json.
#
# The block below is intact and unmodified - unused, not unavailable. Flip
# generate_performance_posts in pipeline_config.json to re-enable it.
if not GENERATE_PERFORMANCE_POSTS:
    print("Performance posts disabled (generate_performance_posts = false). Skipping - no performance_posts_*.txt will be written.")
else:
    # Now generate the 5 Performance posts
    print("Generating 5 Performance Posts...")
    performance_system_prompt = f"""You are Harsh Chouksey's Performance Engine. Write 5 report-driven posts reverse-engineered from actual analytics.
    {writing_rules}
    """

    perf_posts_list = [
        {
            "id": "1. FOUNDER PSYCHOLOGY CONTRARIAN",
            "prompt": f"""Write the FOUNDER PSYCHOLOGY CONTRARIAN performance post.
    Topic: Stop testing 50 ad creatives when your landing page conversion rate is under 1.5%. Explain that most brand owners burn money on Meta Ads trying to fix their messaging, when the real culprit is a friction-filled signup funnel. Fix your landing page first.
    Start directly with the hook. No titles.
    """
        },
        {
            "id": "2. LOADED POLL",
            "prompt": f"""Write the LOADED POLL performance post.
    Topic: "What is the best way to scale Meta ad accounts in 2026?"
    Question: What is the most reliable bidding strategy to scale Meta Ads budget without spikes in lead cost?
    Options:
    ☐ Advantage+ Shopping Campaigns (ASC)
    ☐ ABO campaigns with strict cost caps
    ☐ CBO campaigns with broad targeting
    ☐ Manual bidding on granular segments
    Provide Setup, Question, Options, and Explanation. No titles.
    """
        },
        {
            "id": "3. AI NEWS + IMPLICATIONS",
            "prompt": f"""Write the AI NEWS + IMPLICATIONS performance post.
    Topic: Meta's updated Conversions API (CAPI) feedback loops.
    Implication: D2C brands are learning that browser-based pixel tracking is no longer sufficient. Server-side event sync is now the baseline. If your CRM isn't pushing purchase data back to Meta within 1 hour, you're overpaying for clicks.
    Start directly with the hook. No titles.
    """
        },
        {
            "id": "4. STORY CAROUSEL",
            "prompt": f"""Write the STORY CAROUSEL performance post content.
    Topic: Automating real estate leads.
    Slide 1: "We cut lead costs by 45%"
    Slides 2-6: Case study of how a real estate agency spent thousands on manual follow-ups, losing half their leads. We built an n8n pipeline that synced Facebook leads to WhatsApp CRM in 60 seconds, saving 20 hours/week and scaling bookings.
    Slide 7: "Systems beat manual speed every time."
    CAROUSEL CAPTION: [prose caption]
    No titles. Format clearly labeled.
    """
        },
        {
            "id": "5. DATA VISUAL + HOOK",
            "prompt": f"""Write the DATA VISUAL + HOOK performance post.
    Topic: "Leads grow cold after 5 minutes."
    Caption: Explain that companies blame ad creative quality for poor conversions, but the real culprit is lead response delay. Focus on instant n8n follow-ups to save ad budget.
    Start directly with the hook. No titles.
    """
        }
    ]

    print("Generating 5 Performance Posts sequentially...")
    performance_posts_text = ""
    for item in perf_posts_list:
        print(f"Generating {item['id']}...")
        result = call_llm(performance_system_prompt, item["prompt"], max_tokens=4000)
        if not result:
            print(f"Error: Failed to generate {item['id']}.")
            sys.exit(1)
        
        performance_posts_text += "==================================================\n"
        performance_posts_text += f"{item['id']}\n"
        performance_posts_text += "==================================================\n"
        performance_posts_text += result.strip() + "\n\n"
        time.sleep(1)

    with open(f"performance_posts_{date_compact}.txt", "w") as f:
        f.write(performance_posts_text)
    print(f"5 Performance Posts saved to performance_posts_{date_compact}.txt")
# ------------------------------------------------------------------------------

print("\n--- Content Generation Completed Successfully ---")
