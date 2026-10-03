"""Stage 1: topic + community + language + duration -> validated plan dict. Also topic suggestions fed by Google Trends.
Chain: Groq gpt-oss-120b -> Groq qwen3.8-27b -> Gemini 3.5-flash-lite. Bad JSON gets one guided retry per model."""
import json
import math
import os
import re
import sys
import time
import xml.etree.ElementTree as ET

import httpx
from dotenv import load_dotenv

from .presets import COMMUNITIES, LANGUAGES, with_keys

load_dotenv()

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent"
CHAIN = [("groq", "openai/gpt-oss-120b"), ("groq", "qwen/qwen3.8-27b"), ("gemini", "gemini-3.5-flash-lite")]
MAX_TOKENS = {"qwen/qwen3.8-27b": 1000}  # Groq free tier caps qwen at 1000 output tokens a minute; a bigger ask is refused before it runs
UA = {"User-Agent": "qoneqt-video-factory/1.0 (hackathon demo)"}
FORMULAS = ("question", "bold_claim", "number", "myth", "story", "warning")
BEATS = ("hook", "context", "rehook", "twist", "payoff")
POSTS = ("youtube_title", "youtube_description", "instagram")
BANNED_OPENERS = ("did you know", "in this video", "today we", "have you ever wondered", "welcome to",
                  "kya aap jaante", "kya aapko pata", "क्या आप जानते", "क्या आपको पता")
# (?!\w) not \b: the Hindi openers end in combining vowel signs, which \w does not match, so \b never fires there
_BANNED = re.compile("|".join(re.escape(o) + r"(?!\w)" for o in BANNED_OPENERS), re.I)

VERDICTS = ("ok", "fixed", "blocked")

# ponytail: the hook is never softened; return a replacement hook (and patch hooks + scene 1) if invented hook stats become a problem
REVIEW_SYSTEM = """You are the publishing editor for the Qoneqt Global Feed, an Indian community app. A short-video script is
about to be produced. Review it and return ONLY a JSON object:
{"verdict": "ok" | "fixed" | "blocked", "notes": ["..."], "changes": [{"scene": 1, "narration": "..."}]}
Most scripts need no change: verdict "ok", notes [], changes [].
"fixed": rewrite only the lines that need it. Soften a claim that is false or cannot be verified ("studies suggest",
drop an invented number). Soften medical, legal or financial certainty into a suggestion. A rewritten narration keeps
its language, its meaning and its length (within three words) and never changes the opening hook line of scene 1.
notes: one short English line per change, at most five. changes: the full new narration of each changed scene, scenes
numbered from 1.
"blocked": only content no mainstream platform would publish: hate or harassment toward a group, sexual content,
encouragement of self-harm, instructions for violence or crime, communal or political incitement, clearly defamatory claims
about a named real person (an unverified negative claim about a person is "fixed"). A false or risky claim alone is
"fixed", never "blocked". notes: one line saying why. changes [].
"""

TRANSLATE_SYSTEM = """You adapt a finished script for a {duration} second vertical short video into another language for the
Qoneqt Global Feed. You get the script's words as a JSON object. Return ONLY the same JSON object with the same keys,
every value rewritten in {language}. Keep the same number of hooks and scenes, in the same order.
Rules:
- Adapt, do not transliterate: it must read like a script written for this audience in this language.
- hook is your translation of the source's hook, identical to the text of the hooks[] entry it translates. Scene 1 narration must begin with that text, word for word.
- Every field you rewrite, the hook and the titles included, is written in {language}; never leave one in the source language.
- Each narration is 1-2 spoken sentences, at most 25 words. Total across all scenes: {words_lo}-{words_hi} words
  (this language is spoken at its own pace, so the total differs from the source).
- Never open a hook with "Did you know", "In this video", "Today we", "Have you ever wondered", "Welcome to",
  "Kya aap jaante hain", "Kya aapko pata hai", "क्या आप जानते हैं" or "क्या आपको पता है".
- Write numbers as spoken words. Each title is a 2-5 word on-screen headline.
- youtube_title: at most 70 characters, no hashtags. youtube_description: 1-3 lines ending with three hashtags.
  instagram: 1-3 lines, emoji welcome, no hashtags.
"""
KEEP_SCENE = ("beat", "query", "image_prompt", "image_prompt_b")  # a sibling reuses the source's stills, so these never change

SYSTEM = """You write scripts for {duration} second vertical short videos for the Qoneqt Global Feed.
Return ONLY a JSON object with exactly these keys:
{{
 "hooks": [{{"text": "...", "formula": "...", "score": 1-10, "why": "..."}}, ...]   (exactly 3 candidate opening lines)
 "hook": "..."                                     (the text of the highest-scoring hook, copied exactly)
 "scenes": [{{"beat": "...", "narration": "...", "title": "...", "query": "...", "image_prompt": "...", "image_prompt_b": "..."}}, ...]   ({scenes_lo} to {scenes_hi} scenes)
 "caption": "..."                                  (1-3 lines of post text for Qoneqt, no hashtags inside)
 "hashtags": ["#...", ...]                         (3 to 8 items, each starting with #)
 "posts": {{"youtube_title": "...", "youtube_description": "...", "instagram": "..."}}
}}
Hooks:
- The three hooks use three different formulas, from: question (a question the viewer needs answered), bold_claim
  (a surprising statement), number (a specific figure), myth (a belief everyone holds that is wrong), story (drop the
  viewer into a moment), warning (what goes wrong if they scroll past). score is 1-10 for scroll-stopping power.
  why is one sentence, at most 20 words, on why that opener stops this community's scroll.
- Never open a hook with "Did you know", "In this video", "Today we", "Have you ever wondered", "Welcome to",
  "Kya aap jaante hain", "Kya aapko pata hai", "क्या आप जानते हैं" or "क्या आपको पता है". Ask something sharper instead.
Scenes:
- Scene 1 narration must begin with the hook, word for word.
- beat is the scene's job, in this order: hook (scene 1: the hook line, then one sentence of stakes), context (what is
  going on), rehook (a line that promises the best part is still coming, like "but the real reason is stranger"),
  twist (the surprising turn or the real answer), payoff (the takeaway, then a last line that loops back to the hook
  or asks for comments). With fewer than five scenes drop rehook, then context. With more than five, repeat context
  or twist, never hook or payoff.
- Each narration is 1-2 spoken sentences, at most 25 words. Total across all scenes: {words_lo}-{words_hi} words.
- Each title is a 2-5 word on-screen headline for its scene, in the same language as the narration.
- Write numbers as spoken words (say "two thousand", not "2000").
- Each query is 2-4 plain English words naming something visual and generic that a stock-video site has,
  e.g. "city traffic night", "woman laptop cafe", "runner sunrise road". Never brand names, never abstract nouns.
  Always English, even when the narration is not.
- Each image_prompt is 15-40 English words describing ONE vertical image for the scene and starts with a
  shot type: "Wide shot:", "Close-up:", "Portrait:", "Action shot:" or "Aftermath:". Consecutive scenes use different
  shot types. Concrete and literal: subject, setting, light, mood. No text inside the image, no brand names.
- image_prompt_b is the same moment from a different shot type, 15-40 English words, so the video can cut between the
  two pictures mid-sentence.
Posts:
- youtube_title: at most 70 characters, no hashtags. youtube_description: 1-3 lines ending with three hashtags.
  instagram: 1-3 lines in the narration's language, emoji welcome, no hashtags.
"""

SUGGEST_SYSTEM = """You suggest topics for 15-60 second vertical videos on the Qoneqt Global Feed, a community-first Indian social app.
Return ONLY a JSON object: {"topics": ["...", "...", "...", "...", "...", "..."]} with exactly 6 topics.
Rules:
- Each topic is one specific video idea in 4-12 words: a question, a claim, a list, or a how-to. No hashtags, no numbering, no quotes.
- When trending searches are given, 3 or 4 topics must be inspired by trends that genuinely fit the community.
  Skip trends that do not fit, and skip trends written in a language other than English or the requested language.
- The remaining topics are evergreen ideas this community always engages with.
- Every topic stays on the community's subject, like its example topics (never repeat an example). A trend that does not fit is skipped, never bent to fit.
- Write every topic in the requested language."""


def budget(duration, wps=2.4):
    """(scenes_lo, scenes_hi, words_lo, words_hi) for a target spoken length in seconds. Pure; unit-tested.
    About 7 s per scene and `wps` spoken words per second (per language in presets); every window keeps scenes under the 25-word cap."""
    n = math.ceil(duration / 7)
    return max(3, n - 1), min(9, n + 1), round(duration * wps * 0.85), round(duration * wps * 1.15)


def _user_prompt(topic, preset, lang):
    return (f"Topic: {topic}\nCommunity: {preset['label']}\nTone: {preset['tone']}\n"
            f"Language for narration, titles and caption: {lang['instruction']}\nCaption style: {preset['caption_style']}\n"
            "Return the JSON now.")


def validate_plan(p, scenes=(5, 7)):
    """Raise ValueError naming the first rule broken. scenes = allowed (lo, hi) scene count. Pure; unit-tested."""
    def bad(msg):
        raise ValueError(msg)
    lo, hi = scenes
    if not isinstance(p, dict):
        bad("plan must be a JSON object")
    if not isinstance(p.get("hook"), str) or not p["hook"].strip():
        bad("hook missing")
    hooks = p.get("hooks")
    if not isinstance(hooks, list) or len(hooks) != 3:
        bad("need exactly 3 hooks")
    for i, h in enumerate(hooks, 1):
        text = h.get("text") if isinstance(h, dict) else None
        if not isinstance(text, str) or not text.strip():
            bad(f"hook {i}: text missing")
        if _BANNED.match(text.strip()):
            # the retry has to name the list: without it, models rewrite "क्या आप जानते" into the same opener again
            bad(f"hook {i}: starts with a banned opener; never begin with {', '.join(BANNED_OPENERS)}")
        if h.get("formula") not in FORMULAS:
            bad(f"hook {i}: formula must be one of {', '.join(FORMULAS)}")
        if type(h.get("score")) not in (int, float) or not 1 <= h["score"] <= 10:  # type(), not isinstance: bool is an int
            bad(f"hook {i}: score must be a number from 1 to 10")
        if not isinstance(h.get("why"), str) or not 1 <= len(h["why"].split()) <= 30:
            bad(f"hook {i}: why must be 1-30 words")
    if p["hook"].strip() not in [h["text"].strip() for h in hooks]:
        bad("hook must be the text of one of the three hooks")
    sc = p.get("scenes")
    if not isinstance(sc, list) or not lo <= len(sc) <= hi:
        bad(f"need {lo}-{hi} scenes")
    for i, s in enumerate(sc, 1):
        n = s.get("narration") if isinstance(s, dict) else None
        q = s.get("query") if isinstance(s, dict) else None
        t = s.get("title") if isinstance(s, dict) else None
        if not isinstance(n, str) or not n.strip():
            bad(f"scene {i}: narration missing")
        cap = 40 if i == 1 else 25  # scene 1 may carry a swapped-in longer hook
        if len(n.split()) > cap:
            bad(f"scene {i}: narration over {cap} words")
        if not isinstance(t, str) or not 1 <= len(t.split()) <= 8:
            bad(f"scene {i}: title must be 1-8 words")
        if not isinstance(q, str) or not 1 <= len(q.split()) <= 4:
            bad(f"scene {i}: query must be 1-4 words")
        if not q.isascii():
            bad(f"scene {i}: query must be ASCII English")
        if s.get("beat") not in BEATS:
            bad(f"scene {i}: beat must be one of {', '.join(BEATS)}")
        for key in ("image_prompt", "image_prompt_b"):
            ip = s.get(key)
            if ip is not None and (not isinstance(ip, str) or len(ip.split()) > 60):
                bad(f"scene {i}: {key} must be a string under 60 words")
    if sc[0]["beat"] != "hook":
        bad("scene 1 beat must be hook")
    if sc[-1]["beat"] != "payoff":
        bad("last scene beat must be payoff")
    if not isinstance(p.get("caption"), str) or not p["caption"].strip():
        bad("caption missing")
    tags = p.get("hashtags")
    if not isinstance(tags, list) or not 3 <= len(tags) <= 10:
        bad("need 3-10 hashtags")
    if any(not isinstance(t, str) or not t.strip().startswith("#") or " " in t.strip() for t in tags):
        bad("hashtags must start with # and contain no spaces")
    posts = p.get("posts")
    if not isinstance(posts, dict) or any(not isinstance(posts.get(k), str) or not posts[k].strip() for k in POSTS):
        bad(f"posts must have {', '.join(POSTS)}")
    if len(posts["youtube_title"]) > 100:
        bad("youtube_title over 100 characters")


def validate_topics(p):
    """Raise ValueError unless p is {'topics': [3-8 non-empty strings]}. Pure; unit-tested."""
    t = p.get("topics") if isinstance(p, dict) else None
    if not isinstance(t, list) or not 3 <= len(t) <= 8 or any(not isinstance(x, str) or not x.strip() for x in t):
        raise ValueError("need topics: a list of 3-8 non-empty strings")

def validate_review(r, n):
    """Raise ValueError unless r is a review of an n-scene plan. Pure; unit-tested."""
    def bad(msg):
        raise ValueError(msg)
    if not isinstance(r, dict) or r.get("verdict") not in VERDICTS:
        bad(f"verdict must be one of {', '.join(VERDICTS)}")
    notes, changes = r.get("notes"), r.get("changes")
    if not isinstance(notes, list) or len(notes) > 8 or any(not isinstance(x, str) for x in notes):
        bad("notes must be a list of at most 8 strings")
    if not isinstance(changes, list):
        bad("changes must be a list")
    for c in changes:
        i = c.get("scene") if isinstance(c, dict) else None
        if type(i) is not int or not 1 <= i <= n:  # type(), not isinstance: bool is an int
            bad(f"change scene must be a number from 1 to {n}")
        t = c.get("narration")
        if not isinstance(t, str) or not t.strip():
            bad(f"change {i}: narration missing")
        cap = 40 if i == 1 else 25
        if len(t.split()) > cap:
            bad(f"change {i}: narration over {cap} words")
    if r["verdict"] == "fixed" and not changes:
        bad("verdict fixed needs at least one change")


def apply_review(p, r):
    """Fold a validated review into the plan: the listed narrations are replaced and p['review'] records the verdict and notes.
    A blocked verdict raises, so the job fails at the plan stage before an image or a voice line is spent."""
    notes = [x.strip() for x in r["notes"] if x.strip()]
    if r["verdict"] == "blocked":
        raise RuntimeError("blocked by the safety review: " + ("; ".join(notes) or "unsafe content"))
    done = 0
    for c in r["changes"]:
        t = c["narration"].strip()
        if c["scene"] == 1 and not t.startswith(p["hook"]):
            notes.append("scene 1 left as written to keep the hook")  # the hook overlay needs scene 1 to open with the hook
            continue
        p["scenes"][c["scene"] - 1]["narration"] = t
        done += 1
    # the reviewer flagged something even when the only fix was skipped, so it never reads as clean
    p["review"] = {"verdict": "fixed" if r["changes"] else "ok", "notes": notes, "changed": done}
    return p


def review(p, language="en"):
    """Safety and claim review of a plan: one cold LLM call. Returns the plan with p['review'] and any softened narration;
    raises RuntimeError when the script is blocked. A dead model chain never blocks a demo: the plan comes back marked 'skipped'."""
    script = "\n".join(f"{i}. {sc['narration']}" for i, sc in enumerate(p["scenes"], 1))
    base = [{"role": "system", "content": REVIEW_SYSTEM},
            {"role": "user", "content": f"Language: {LANGUAGES[language]['instruction']}\nHook: {p['hook']}\nScript:\n{script}\nReturn the JSON now."}]
    try:
        r = _ask(base, lambda q: validate_review(q, len(p["scenes"])), temperature=0.2)
    except RuntimeError as e:
        print(f"review skipped: {str(e)[:120]}", file=sys.stderr)
        p["review"] = {"verdict": "skipped", "notes": [str(e)[:80]]}
        return p
    return apply_review(p, r)


def _parse(text):
    """Tolerate code fences and prose around the JSON object."""
    text = re.sub(r"```(?:json)?", "", text)
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end < 0:
        raise ValueError("no JSON object in response")
    return json.loads(text[start:end + 1])


def _call_groq(model, messages, temperature):
    def post(key):
        r = httpx.post(GROQ_URL, timeout=60,
                       headers={"Authorization": f"Bearer {key}"},
                       json={"model": model, "messages": messages, "temperature": temperature, "max_tokens": MAX_TOKENS.get(model, 4000),
                             "reasoning_effort": "low", "response_format": {"type": "json_object"}})
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"]

    return with_keys(post, "GROQ_API_KEY")


def _call_gemini(model, messages, temperature):
    system = "\n".join(m["content"] for m in messages if m["role"] == "system")
    convo = "\n\n".join(f"{m['role'].upper()}: {m['content']}" for m in messages if m["role"] != "system")
    def post(key):
        r = httpx.post(GEMINI_URL.format(m=model), params={"key": key}, timeout=60,
                       json={"systemInstruction": {"parts": [{"text": system}]},
                             "contents": [{"parts": [{"text": convo}]}],
                             "generationConfig": {"responseMimeType": "application/json", "temperature": temperature}})
        r.raise_for_status()
        return r.json()["candidates"][0]["content"]["parts"][0]["text"]

    return with_keys(post, "GEMINI_API_KEY")


def _ask(base, validate, temperature=0.8):
    """Run the model chain on `base` messages until one returns JSON that passes `validate`; adds p['model'].
    Bad JSON or failed validation -> one guided retry on the same model; provider trouble -> next model."""
    last = None
    for provider, model in CHAIN:
        call = _call_groq if provider == "groq" else _call_gemini
        msgs = list(base)
        for _attempt in range(2):
            raw = ""  # call() itself can raise ValueError (a non-JSON body) before raw is set
            try:
                raw = call(model, msgs, temperature)
                p = _parse(raw)
                validate(p)
                p["model"] = model
                return p
            except ValueError as e:
                last = e
                msgs = base + [{"role": "assistant", "content": raw},
                               {"role": "user", "content": f"Rejected: {e}. Return the corrected JSON object only."}]
            except (httpx.HTTPError, KeyError, IndexError) as e:
                last = e
                time.sleep(2)
                break
    raise RuntimeError(f"every model failed: {last}")


def plan(topic, community="general", language="en", duration=30):
    preset, lang = COMMUNITIES[community], LANGUAGES[language]
    lo, hi, wlo, whi = budget(duration, lang["wps"])
    system = SYSTEM.format(duration=duration, scenes_lo=lo, scenes_hi=hi, words_lo=wlo, words_hi=whi)
    base = [{"role": "system", "content": system}, {"role": "user", "content": _user_prompt(topic, preset, lang)}]
    p = _ask(base, lambda q: validate_plan(q, (lo, hi)))
    p["hook"] = p["hook"].strip()  # the UI picks the chosen hook by exact text match
    p["hashtags"] = list(dict.fromkeys(t.strip() for t in p["hashtags"] + preset["hashtags"]))
    return p


def _merge(q, src):
    """Copy the visual and structural fields of the source plan over a translation, so the model can only change words.
    Runs before validation, so a model that renames a query or a beat is corrected rather than retried."""
    if isinstance(q, dict):
        if isinstance(q.get("scenes"), list):
            for s, o in zip(q["scenes"], src["scenes"]):
                if isinstance(s, dict):
                    s.update({k: o.get(k) for k in KEEP_SCENE})
        if isinstance(q.get("hooks"), list):
            for h, o in zip(q["hooks"], src["hooks"]):
                if isinstance(h, dict):
                    h.update(formula=o["formula"], score=o["score"])
        q["hashtags"] = src["hashtags"]
        if "review" in src:
            q["review"] = src["review"]
    return q


def translate(src, language, duration=30):
    """The source plan in another language: words rewritten by the model, visuals, structure, hashtags and review copied
    from `src`. Validated like a fresh plan with the scene count pinned, so the sibling's stills line up."""
    lang = LANGUAGES[language]
    n = len(src["scenes"])
    _, _, wlo, whi = budget(duration, lang["wps"])
    system = TRANSLATE_SYSTEM.format(duration=duration, language=lang["instruction"], words_lo=wlo, words_hi=whi)
    # only the words: _merge puts back everything else, and the English image prompts were half the tokens (Groq TPM, qwen's cap)
    body = {"hooks": [{"text": h["text"], "why": h["why"]} for h in src["hooks"]], "hook": src["hook"],
            "scenes": [{"narration": s["narration"], "title": s["title"]} for s in src["scenes"]],
            "caption": src["caption"], "posts": src["posts"]}
    k = [h["text"].strip() for h in src["hooks"]].index(src["hook"].strip())  # the user may have picked a lower-scoring hook
    base = [{"role": "system", "content": system},
            {"role": "user", "content": f"Script:\n{json.dumps(body, ensure_ascii=False)}\nReturn the JSON now."}]
    script = re.compile(f"[{lang['script']}]" if lang["script"] else "[ऀ-૿]")

    def check(q):
        validate_plan(_merge(q, src), (n, n))
        if q["hook"].strip() != q["hooks"][k]["text"].strip():
            raise ValueError(f"hook must be your translation of hook {k + 1}, the same text as hooks[{k}].text")
        texts = [("hook", q["hook"])] + [(f"scene {i} {key}", s[key]) for key in ("narration", "title") for i, s in enumerate(q["scenes"], 1)]
        for where, t in texts:
            # models leave the hook in English: an Indic target needs its script in every line, a Roman one none at all
            if bool(script.search(t)) != bool(lang["script"]):
                raise ValueError(f"{where} is not in {lang['label']}: write every hook, narration and title in {lang['instruction']}")
        if not q["scenes"][0]["narration"].strip().startswith(q["hook"].strip()):  # the hook overlay and the first spoken line must agree
            raise ValueError("scene 1 narration must begin with the hook, word for word")
    p = _ask(base, check, temperature=0.5)
    p["hook"] = p["hook"].strip()
    return p


# ---------- suggestions ----------

TRENDS_URL = "https://trends.google.com/trending/rss?geo=IN"
_trends_cache = (0.0, [])  # (fetched_at, titles); ponytail: one process, one cache


def trends():
    """Top Google Trends India search titles, no key needed, cached 10 minutes. [] on any failure."""
    global _trends_cache
    at, titles = _trends_cache
    if time.time() - at < 600:
        return titles
    try:
        r = httpx.get(TRENDS_URL, headers=UA, timeout=10)
        r.raise_for_status()
        titles = [t for t in ((it.findtext("title") or "").strip() for it in ET.fromstring(r.content).iter("item")) if t][:10]
    except Exception as e:
        print(f"trends: {type(e).__name__}: {str(e)[:120]}", file=sys.stderr)
        titles = []
    _trends_cache = (time.time(), titles)
    return titles


def _suggest_prompt(preset, lang, trend_titles, trends_only=False):
    tr = "\n".join(f"- {t}" for t in trend_titles) or "(none available right now)"
    rule = ("Every topic must be inspired by one of the trending searches below that fits the community; "
            "if fewer than six fit, fill the rest with evergreen ideas.\n") if trends_only and trend_titles else ""
    return (f"Community: {preset['label']}\nTone: {preset['tone']}\nExample topics: {'; '.join(preset['examples'])}\n{rule}"
            f"Trending searches in India right now:\n{tr}\n"
            f"Language: write every topic in {lang['instruction']}. This is mandatory.\nReturn the JSON now.")


IMAGE_SYSTEM = """You write single-image posts for the Qoneqt Global Feed, a community-first Indian social app. One picture
with a short headline drawn on it, and the post text under it. Return ONLY a JSON object with exactly these keys:
{"headline": "...", "image_prompt": "...", "query": "...", "caption": "...", "hashtags": ["#...", ...], "alt": "..."}
Rules:
- headline: 3-8 words drawn large on the picture. A sharp claim, question or number that stops the scroll. No hashtags,
  no emoji. Never open with "Did you know", "Kya aap jaante hain" or "क्या आप जानते हैं".
- image_prompt: 20-45 English words describing ONE portrait picture: subject, setting, light, mood. Keep the top third
  of the frame calm and uncluttered (sky, wall, soft background), because the headline sits there. No text, letters,
  brand names or logos in the picture.
- query: 2-4 plain English words naming something visual and generic a stock photo site has, e.g. "woman laptop cafe".
- caption: 2-4 short lines of post text that deliver the value the headline promises: the fact, tip or answer, then a
  question that invites comments. Emoji welcome, no hashtags inside.
- hashtags: 3 to 8 items, each starting with #.
- alt: one plain English sentence describing the picture for people who cannot see it.
The headline and caption are written in the requested language; image_prompt, query and alt are always English."""


def validate_image_plan(p, script=None):
    """Raise ValueError naming the first rule broken. script: regex range the headline and caption must use. Pure; unit-tested."""
    if not isinstance(p, dict):
        raise ValueError("not a JSON object")
    for k in ("headline", "image_prompt", "query", "caption", "alt"):
        if not isinstance(p.get(k), str) or not p[k].strip():
            raise ValueError(f"{k} missing")
    if not 2 <= len(p["headline"].split()) <= 10:  # a little slack on the prompt's 3-8: Hindi runs longer
        raise ValueError("headline must be 3-8 words")
    if _BANNED.match(p["headline"].strip()):
        raise ValueError(f"headline must not open with any of: {', '.join(BANNED_OPENERS)}")
    tags = p.get("hashtags")
    if not isinstance(tags, list) or not 3 <= len(tags) <= 8 or any(not isinstance(t, str) or not t.startswith("#") for t in tags):
        raise ValueError("hashtags must be 3-8 strings starting with #")
    if script and not all(re.search(f"[{script}]", p[k]) for k in ("headline", "caption")):
        raise ValueError("headline and caption must be written in the requested language's script")


def image_plan(topic, community="general", language="en"):
    """Topic -> headline, picture prompt, post text, hashtags and alt text for one image post (~3 s)."""
    preset, lang = COMMUNITIES[community], LANGUAGES[language]
    base = [{"role": "system", "content": IMAGE_SYSTEM},
            {"role": "user", "content": f"Topic: {topic}\nCommunity: {preset['label']}\nTone: {preset['tone']}\n"
                                        f"Language for headline and caption: {lang['instruction']}\n"
                                        f"Caption style: {preset['caption_style']}\nReturn the JSON now."}]
    p = _ask(base, lambda q: validate_image_plan(q, lang["script"]))
    p["headline"] = p["headline"].strip()
    p["hashtags"] = list(dict.fromkeys(t.strip() for t in p["hashtags"] + preset["hashtags"]))
    return p


def review_post(p, language="en"):
    """llm.review on an image post, wrapped as a plan: scene 1 is the headline (the hook, never rewritten) and every caption
    line is a scene of its own, so a softened claim replaces only its line and the rest, line breaks included, stay.
    A blocked post raises."""
    lines = [x.strip() for x in p["caption"].split("\n") if x.strip()]
    r = review({"hook": p["headline"], "scenes": [{"narration": p["headline"]}] + [{"narration": x} for x in lines]}, language)
    p["caption"] = "\n".join(sc["narration"] for sc in r["scenes"][1:])
    p["review"] = r["review"]
    return p


def suggest(community="general", language="en", trends_only=False):
    """{'topics': [6 ideas], 'trends': [titles used]}; 3-4 ideas ride today's trends, or all of them with trends_only."""
    preset, lang = COMMUNITIES[community], LANGUAGES[language]
    tr = trends()
    base = [{"role": "system", "content": SUGGEST_SYSTEM}, {"role": "user", "content": _suggest_prompt(preset, lang, tr, trends_only)}]
    p = _ask(base, validate_topics, temperature=1.0)
    return {"topics": [x.strip() for x in p["topics"]][:6], "trends": tr}


if __name__ == "__main__":
    # python llm.py "chai vs coffee" hinglish_fun hinglish 15   |   python llm.py suggest tech hi
    if sys.argv[1:2] == ["suggest"]:
        print(json.dumps(suggest(*sys.argv[2:4]), indent=2, ensure_ascii=False))
        sys.exit()
    topic = sys.argv[1] if len(sys.argv) > 1 else "why sleep matters"
    community = sys.argv[2] if len(sys.argv) > 2 else "general"
    language = sys.argv[3] if len(sys.argv) > 3 else "en"
    duration = int(sys.argv[4]) if len(sys.argv) > 4 else 30
    out = plan(topic, community, language, duration)
    print(json.dumps(out, indent=2, ensure_ascii=False))
    words = sum(len(s["narration"].split()) for s in out["scenes"])
    lo, hi, wlo, whi = budget(duration, LANGUAGES[language]["wps"])
    print(f"\n{len(out['scenes'])} scenes (want {lo}-{hi}), {words} words (want {wlo}-{whi}), model={out['model']}")
