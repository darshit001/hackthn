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

from presets import COMMUNITIES, LANGUAGES

load_dotenv()

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent"
CHAIN = [("groq", "openai/gpt-oss-120b"), ("groq", "qwen/qwen3.8-27b"), ("gemini", "gemini-3.5-flash-lite")]
UA = {"User-Agent": "qoneqt-video-factory/1.0 (hackathon demo)"}

SYSTEM = """You write scripts for {duration} second vertical short videos for the Qoneqt Global Feed.
Return ONLY a JSON object with exactly these keys:
{{
 "hooks": [{{"text": "...", "score": 1-10}}, ...]   (exactly 3 candidate opening lines, scored for scroll-stopping power)
 "hook": "..."                                     (the text of the highest-scoring hook)
 "scenes": [{{"narration": "...", "title": "...", "query": "...", "image_prompt": "..."}}, ...]   ({scenes_lo} to {scenes_hi} scenes)
 "caption": "..."                                  (1-3 lines of post text, no hashtags inside)
 "hashtags": ["#...", ...]                         (3 to 8 items, each starting with #)
}}
Rules:
- Scene 1 narration must begin with the hook, word for word.
- Each narration is 1-2 spoken sentences, at most 25 words. Total across all scenes: {words_lo}-{words_hi} words.
- Each title is a 2-5 word on-screen headline for its scene, in the same language as the narration.
- Write numbers as spoken words (say "two thousand", not "2000").
- Each query is 2-4 plain English words naming something visual and generic that a stock-video site has,
  e.g. "city traffic night", "woman laptop cafe", "runner sunrise road". Never brand names, never abstract nouns.
  Always English, even when the narration is not.
- Each image_prompt is 15-40 English words describing ONE photographic vertical image for the scene: subject, setting,
  light, mood. Concrete and literal, no text or words inside the image, no brand names.
- The last scene ends with a one-line takeaway or an invitation to comment.
"""

SUGGEST_SYSTEM = """You suggest topics for 15-60 second vertical videos on the Qoneqt Global Feed, a community-first Indian social app.
Return ONLY a JSON object: {"topics": ["...", "...", "...", "...", "...", "..."]} with exactly 6 topics.
Rules:
- Each topic is one specific video idea in 4-12 words: a question, a claim, a list, or a how-to. No hashtags, no numbering, no quotes.
- When trending searches are given, 3 or 4 topics must be inspired by trends that genuinely fit the community.
  Skip trends that do not fit, and skip trends written in a language other than English or the requested language.
- The remaining topics are evergreen ideas this community always engages with.
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
    sc = p.get("scenes")
    if not isinstance(sc, list) or not lo <= len(sc) <= hi:
        bad(f"need {lo}-{hi} scenes")
    for i, s in enumerate(sc, 1):
        n = s.get("narration") if isinstance(s, dict) else None
        q = s.get("query") if isinstance(s, dict) else None
        t = s.get("title") if isinstance(s, dict) else None
        if not isinstance(n, str) or not n.strip():
            bad(f"scene {i}: narration missing")
        if len(n.split()) > 25:
            bad(f"scene {i}: narration over 25 words")
        if not isinstance(t, str) or not 1 <= len(t.split()) <= 8:
            bad(f"scene {i}: title must be 1-8 words")
        if not isinstance(q, str) or not 1 <= len(q.split()) <= 4:
            bad(f"scene {i}: query must be 1-4 words")
        if not q.isascii():
            bad(f"scene {i}: query must be ASCII English")
        ip = s.get("image_prompt")
        if ip is not None and (not isinstance(ip, str) or len(ip.split()) > 60):
            bad(f"scene {i}: image_prompt must be a string under 60 words")
    if not isinstance(p.get("caption"), str) or not p["caption"].strip():
        bad("caption missing")
    tags = p.get("hashtags")
    if not isinstance(tags, list) or not 3 <= len(tags) <= 10:
        bad("need 3-10 hashtags")
    if any(not isinstance(t, str) or not t.strip().startswith("#") or " " in t.strip() for t in tags):
        bad("hashtags must start with # and contain no spaces")


def validate_topics(p):
    """Raise ValueError unless p is {'topics': [3-8 non-empty strings]}. Pure; unit-tested."""
    t = p.get("topics") if isinstance(p, dict) else None
    if not isinstance(t, list) or not 3 <= len(t) <= 8 or any(not isinstance(x, str) or not x.strip() for x in t):
        raise ValueError("need topics: a list of 3-8 non-empty strings")


def _parse(text):
    """Tolerate code fences and prose around the JSON object."""
    text = re.sub(r"```(?:json)?", "", text)
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end < 0:
        raise ValueError("no JSON object in response")
    return json.loads(text[start:end + 1])


def _call_groq(model, messages, temperature):
    r = httpx.post(GROQ_URL, timeout=60,
                   headers={"Authorization": f"Bearer {os.environ['GROQ_API_KEY']}"},
                   json={"model": model, "messages": messages, "temperature": temperature, "max_tokens": 2000,
                         "reasoning_effort": "low", "response_format": {"type": "json_object"}})
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"]


def _call_gemini(model, messages, temperature):
    system = "\n".join(m["content"] for m in messages if m["role"] == "system")
    convo = "\n\n".join(f"{m['role'].upper()}: {m['content']}" for m in messages if m["role"] != "system")
    r = httpx.post(GEMINI_URL.format(m=model), params={"key": os.environ["GEMINI_API_KEY"]}, timeout=60,
                   json={"systemInstruction": {"parts": [{"text": system}]},
                         "contents": [{"parts": [{"text": convo}]}],
                         "generationConfig": {"responseMimeType": "application/json", "temperature": temperature}})
    r.raise_for_status()
    return r.json()["candidates"][0]["content"]["parts"][0]["text"]


def _ask(base, validate, temperature=0.8):
    """Run the model chain on `base` messages until one returns JSON that passes `validate`; adds p['model'].
    Bad JSON or failed validation -> one guided retry on the same model; provider trouble -> next model."""
    last = None
    for provider, model in CHAIN:
        call = _call_groq if provider == "groq" else _call_gemini
        msgs = list(base)
        for _attempt in range(2):
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
    p["hashtags"] = list(dict.fromkeys(t.strip() for t in p["hashtags"] + preset["hashtags"]))
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
    return (f"Community: {preset['label']}\nTone: {preset['tone']}\n{rule}"
            f"Trending searches in India right now:\n{tr}\n"
            f"Language: write every topic in {lang['instruction']}. This is mandatory.\nReturn the JSON now.")


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
