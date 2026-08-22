import os
import sys
import re
import urllib.request
import ssl
import json

from config_loader import load_config

def ensure_valid_images():
    assets_dir = "./carousel-routine/temp/carousel-branded/assets"
    os.makedirs(assets_dir, exist_ok=True)
    
    # Fallback mappings for onboarding/conversion themes
    fallbacks = {
        "hero-ui.png": "https://images.unsplash.com/photo-1460925895917-afdab827c52f?auto=format&fit=crop&w=1080&q=80",
        "interface.png": "https://images.unsplash.com/photo-1551288049-bebda4e38f71?auto=format&fit=crop&w=1080&q=80"
    }
    
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    
    for filename, url in fallbacks.items():
        file_path = os.path.join(assets_dir, filename)
        is_valid = False
        
        if os.path.exists(file_path):
            size = os.path.getsize(file_path)
            if size > 10000:
                try:
                    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                        header = f.read(100)
                        if not ("<html" in header.lower() or "<!doctype" in header.lower()):
                            is_valid = True
                except Exception:
                    is_valid = True
                    
        if not is_valid:
            print(f"Asset '{filename}' is missing or invalid. Downloading fallback from {url}...")
            try:
                req = urllib.request.Request(
                    url, 
                    headers={"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}
                )
                with urllib.request.urlopen(req, context=ctx) as response:
                    with open(file_path, "wb") as f:
                        f.write(response.read())
                print(f"Successfully downloaded fallback for '{filename}'.")
            except Exception as e:
                print(f"Error downloading fallback for {filename}: {e}")

# Run asset verification first
ensure_valid_images()

skill_path = "./skills/branded-carousel/SKILL.md"
with open(skill_path, "r") as f:
    content = f.read()

# Extract templates
t1 = re.search(r"TEMPLATE 1.*?```html(.*?)```", content, re.DOTALL).group(1)
t2 = re.search(r"TEMPLATE 2 & 4.*?```html(.*?)```", content, re.DOTALL).group(1)
t3 = re.search(r"TEMPLATE 3 & 5.*?```html(.*?)```", content, re.DOTALL).group(1)
t6 = re.search(r"TEMPLATE 6.*?```html(.*?)```", content, re.DOTALL).group(1)
t7 = re.search(r"TEMPLATE 7.*?```html(.*?)```", content, re.DOTALL).group(1)

# The slide 1 and slide 6 image slots are filled with branded cards rather than
# photos. Phase 2: their text now comes from the slide's own model-written
# fields. They previously carried fixed marketing copy - "2026 AI BLUEPRINT",
# "Autonomous AI Ops", "NATIVE AI OPERATING SYSTEM" - on every carousel
# regardless of topic.
t1 = re.sub(
    r'<img[^>]*class="s1-image"[^>]*>',
    '<div style="width: 320px; min-height: 160px; background: linear-gradient(135deg, {{BRAND_COLOR}}, #1A1D20); border-radius: 24px; padding: 28px; color: white; display: flex; flex-direction: column; justify-content: center; box-shadow: 0 20px 40px rgba(0,0,0,0.15);">'
    '<div style="font-size: 13px; font-weight: 800; letter-spacing: 2px; text-transform: uppercase; color: rgba(255,255,255,0.85);">{{S1_CARD_LABEL}}</div>'
    '<div style="font-size: 32px; font-weight: 900; font-family: \'Instrument Serif\', serif; font-style: italic; margin-top: 6px; color: #FFFFFF;">{{S1_CARD_TEXT}}</div>'
    '</div>',
    t1
)

t6 = re.sub(
    r'<img[^>]*class="s6-image"[^>]*>',
    '<div style="width: 380px; min-height: 240px; background: #FFFFFF; border: 3px solid {{BRAND_COLOR}}; border-radius: 28px; padding: 32px; display: flex; flex-direction: column; justify-content: center; box-shadow: 0 20px 40px rgba(0,0,0,0.08);">'
    '<div style="font-size: 14px; font-weight: 800; letter-spacing: 2px; text-transform: uppercase; color: {{BRAND_COLOR}};">{{S6_CARD_LABEL}}</div>'
    '<div style="font-size: 30px; font-weight: 900; color: #111; margin-top: 10px; line-height: 1.1;">{{S6_CARD_TEXT}}</div>'
    '<div style="font-size: 18px; font-weight: 600; color: #666; margin-top: 10px;">{{S6_CARD_SUB}}</div>'
    '</div>',
    t6
)

json_file = sys.argv[1] if len(sys.argv) > 1 else "./carousel_data.json"
out_dir = sys.argv[2] if len(sys.argv) > 2 else "./carousel-routine/temp/carousel-branded"
os.makedirs(out_dir, exist_ok=True)

# Phase 2: one brand colour, one place. Was a hard-coded literal here, which
# overrode every palette documented in skills/branded-carousel/FORMATS.md.
# Deliberately NOT per-carousel and NOT model-chosen: a consistent colour is
# brand furniture, and a palette per topic makes every carousel look like a
# different account.
color = load_config().get("brand_color", "#5E6AD2")

# Load dynamic carousel data if exists
json_data = {}
if os.path.exists(json_file):
    try:
        with open(json_file) as f:
            json_data = json.load(f)
            print(f"Loaded dynamic carousel slide data from {json_file}")
    except Exception as e:
        print(f"Error loading {json_file}: {e}")

# ---- Phase 2: required fields, no invented fallbacks -------------------------
# Every value below MUST come from the model-written carousel JSON. The previous
# fallbacks were a complete, unrelated story about someone else's business
# ("5x MRR in seven days", "a founder was stuck at $60 MRR for months") which
# rendered into a carousel published under Harsh's name whenever a field came
# through empty - and fields DO come through empty. Those strings are deleted.
#
# A blank card is bad. Invented numbers attributed to a real person are far
# worse, and a neutral placeholder that reads as real content is the same
# failure in a new costume. So: collect every missing field, then abort.
MISSING_FIELDS = []


def require_slide_val(slide_num, key):
    slide_obj = json_data.get(str(slide_num), json_data.get(slide_num, {}))
    if not isinstance(slide_obj, dict):
        slide_obj = {}
    val = slide_obj.get(key)
    if val is None or str(val).strip() == "":
        MISSING_FIELDS.append((str(slide_num), key))
        return ""
    return str(val)


data = {
    "1": (t1, {
        "{{BRAND_COLOR}}": color,
        "{{HEADER_LABEL}}": require_slide_val("1", "HEADER_LABEL"),
        "{{HOOK_PART_1}}": require_slide_val("1", "HOOK_PART_1"),
        "{{HOOK_PART_2}}": require_slide_val("1", "HOOK_PART_2"),
        "{{HOOK_EMPHASIS}}": require_slide_val("1", "HOOK_EMPHASIS"),
        "{{SUBTITLE}}": require_slide_val("1", "SUBTITLE"),
    }),
    "2": (t2, {
        "{{BRAND_COLOR}}": color,
        "{{PILL_LABEL}}": require_slide_val("2", "PILL_LABEL"),
        "{{SLIDE_NUM}}": "02",
        "{{EYEBROW}}": require_slide_val("2", "EYEBROW"),
        "{{HEADLINE_PART_1}}": require_slide_val("2", "HEADLINE_PART_1"),
        "{{HEADLINE_PART_2}}": require_slide_val("2", "HEADLINE_PART_2"),
        "{{HEADLINE_EMPHASIS}}": require_slide_val("2", "HEADLINE_EMPHASIS"),
        "{{SUBHEAD}}": require_slide_val("2", "SUBHEAD"),
        "{{BODY_TEXT}}": require_slide_val("2", "BODY_TEXT"),
    }),
    "3": (t3, {
        "{{BRAND_COLOR}}": color,
        "{{HEADER_LABEL}}": require_slide_val("3", "HEADER_LABEL"),
        "{{SLIDE_NUM}}": "03",
        "{{HUGE_STAT}}": require_slide_val("3", "HUGE_STAT"),
        "{{CIRCLE_WORD_1}}": require_slide_val("3", "CIRCLE_WORD_1"),
        "{{CIRCLE_WORD_2}}": require_slide_val("3", "CIRCLE_WORD_2"),
        "{{HEADLINE_PART_1}}": require_slide_val("3", "HEADLINE_PART_1"),
        "{{HEADLINE_PART_2}}": require_slide_val("3", "HEADLINE_PART_2"),
        "{{HEADLINE_EMPHASIS}}": require_slide_val("3", "HEADLINE_EMPHASIS"),
        "{{BODY_TEXT}}": require_slide_val("3", "BODY_TEXT"),
    }),
    "4": (t2, {
        "{{BRAND_COLOR}}": color,
        "{{PILL_LABEL}}": require_slide_val("4", "PILL_LABEL"),
        "{{SLIDE_NUM}}": "04",
        "{{EYEBROW}}": require_slide_val("4", "EYEBROW"),
        "{{HEADLINE_PART_1}}": require_slide_val("4", "HEADLINE_PART_1"),
        "{{HEADLINE_PART_2}}": require_slide_val("4", "HEADLINE_PART_2"),
        "{{HEADLINE_EMPHASIS}}": require_slide_val("4", "HEADLINE_EMPHASIS"),
        "{{SUBHEAD}}": require_slide_val("4", "SUBHEAD"),
        "{{BODY_TEXT}}": require_slide_val("4", "BODY_TEXT"),
    }),
    "5": (t3, {
        "{{BRAND_COLOR}}": color,
        "{{HEADER_LABEL}}": require_slide_val("5", "HEADER_LABEL"),
        "{{SLIDE_NUM}}": "05",
        "{{HUGE_STAT}}": require_slide_val("5", "HUGE_STAT"),
        "{{CIRCLE_WORD_1}}": require_slide_val("5", "CIRCLE_WORD_1"),
        "{{CIRCLE_WORD_2}}": require_slide_val("5", "CIRCLE_WORD_2"),
        "{{HEADLINE_PART_1}}": require_slide_val("5", "HEADLINE_PART_1"),
        "{{HEADLINE_PART_2}}": require_slide_val("5", "HEADLINE_PART_2"),
        "{{HEADLINE_EMPHASIS}}": require_slide_val("5", "HEADLINE_EMPHASIS"),
        "{{BODY_TEXT}}": require_slide_val("5", "BODY_TEXT"),
    }),
    "6": (t6, {
        "{{BRAND_COLOR}}": color,
        "{{HEADER_LABEL}}": require_slide_val("6", "HEADER_LABEL"),
        "{{HUGE_STAT}}": require_slide_val("6", "HUGE_STAT"),
        "{{HEADLINE_PART_1}}": require_slide_val("6", "HEADLINE_PART_1"),
        "{{HEADLINE_PART_2}}": require_slide_val("6", "HEADLINE_PART_2"),
        "{{HEADLINE_EMPHASIS}}": require_slide_val("6", "HEADLINE_EMPHASIS"),
        "{{SUBHEAD}}": require_slide_val("6", "SUBHEAD"),
        "{{BODY_TEXT}}": require_slide_val("6", "BODY_TEXT"),
    }),
    "7": (t7, {
        "{{BRAND_COLOR}}": color,
        "{{S7_LABEL}}": require_slide_val("1", "HEADER_LABEL"),
        "{{HEADLINE_PART_1}}": require_slide_val("7", "HEADLINE_PART_1"),
        "{{HEADLINE_PART_2}}": require_slide_val("7", "HEADLINE_PART_2"),
        "{{HEADLINE_EMPHASIS}}": require_slide_val("7", "HEADLINE_EMPHASIS"),
        "{{SUBHEAD}}": require_slide_val("7", "SUBHEAD"),
    }),
}

# The image-replacement cards on slides 1 and 6 are filled from the slide's own
# model-written fields, not from fixed marketing copy.
data["1"][1]["{{S1_CARD_LABEL}}"] = data["1"][1]["{{HEADER_LABEL}}"]
data["1"][1]["{{S1_CARD_TEXT}}"] = data["1"][1]["{{HOOK_EMPHASIS}}"]
data["6"][1]["{{S6_CARD_LABEL}}"] = data["6"][1]["{{HEADER_LABEL}}"]
data["6"][1]["{{S6_CARD_TEXT}}"] = data["6"][1]["{{HEADLINE_EMPHASIS}}"]
data["6"][1]["{{S6_CARD_SUB}}"] = data["6"][1]["{{SUBHEAD}}"]

if MISSING_FIELDS:
    label = os.path.basename(json_file)
    print("=" * 64)
    print("FATAL: carousel data is incomplete - refusing to render.")
    print(f"  Source: {json_file}")
    print(f"  {len(MISSING_FIELDS)} required field(s) missing or empty:")
    for slide, key in MISSING_FIELDS:
        print(f"    slide {slide}: {key}")
    print("")
    print("  Rendering would previously have substituted invented placeholder")
    print("  content about an unrelated business. Those strings are gone, and")
    print("  a carousel is not published with fabricated detail.")
    print("  Re-run generation for this carousel, or fix the JSON by hand.")
    print("=" * 64)
    sys.exit(1)

for slide_num, (template, replacements) in data.items():
    html = template
    for k, v in replacements.items():
        html = html.replace(k, str(v) if v is not None else "")
    with open(f"{out_dir}/slide-0{slide_num}.html", "w") as f:
        f.write(html)

print("Generated 7 HTML slides successfully in temp/carousel-branded.")
