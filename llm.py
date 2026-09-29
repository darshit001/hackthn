"""Stage 1: topic + community preset -> validated plan dict.
Chain: Groq gpt-oss-120b -> Groq qwen3.8-27b -> Gemini 3.5-flash-lite. Bad JSON gets one guided retry per model."""
import json
import os
import re
import sys
import time

import httpx
from dotenv import load_dotenv

from presets import COMMUNITIES

load_dotenv()

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent"
CHAIN = [("groq", "openai/gpt-oss-120b"), ("groq", "qwen/qwen3.8-27b"), ("gemini", "gemini-3.5-flash-lite")]

SYSTEM = """You write scripts for 30-45 second vertical short videos for the Qoneqt Global Feed.
Return ONLY a JSON object with exactly these keys:
{
 "hooks": [{"text": "...", "score": 1-10}, ...]   (exactly 3 candidate opening lines, scored for scroll-stopping power)
 "hook": "..."                                     (the text of the highest-scoring hook)
 "scenes": [{"narration": "...", "query": "...", "image_prompt": "..."}, ...]   (5 to 7 scenes)
 "caption": "..."                                  (1-3 lines of post text, no hashtags inside)
 "hashtags": ["#...", ...]                         (3 to 8 items, each starting with #)
}
Rules:
- Scene 1 narration must begin with the hook, word for word.
- Each narration is 1-2 spoken sentences, at most 25 words. Total across all scenes: 70-110 words.
- Write numbers as spoken words (say "two thousand", not "2000").
- Each query is 2-4 plain English words naming something visual and generic that a stock-video site has,
  e.g. "city traffic night", "woman laptop cafe", "runner sunrise road". Never brand names, never abstract nouns.
- Each image_prompt is 15-40 words describing ONE photographic vertical image for the scene: subject, setting,
  light, mood. Concrete and literal, no text or words inside the image, no brand names.
- The last scene ends with a one-line takeaway or an invitation to comment.
"""


def _user_prompt(topic, preset):
    lang = ("Hinglish written in Roman script (a natural mix of Hindi and English, the way young Indians text)"
            if preset["language"] == "hinglish" else "English")
    return (f"Topic: {topic}\nCommunity: {preset['label']}\nTone: {preset['tone']}\n"
            f"Language for narration and caption: {lang}\nCaption style: {preset['caption_style']}\n"
            "Return the JSON now.")


def validate_plan(p):
    """Raise ValueError naming the first rule broken. Pure; unit-tested."""
    def bad(msg):
        raise ValueError(msg)
    if not isinstance(p, dict):
        bad("plan must be a JSON object")
    if not isinstance(p.get("hook"), str) or not p["hook"].strip():
        bad("hook missing")
    scenes = p.get("scenes")
    if not isinstance(scenes, list) or not 5 <= len(scenes) <= 7:
        bad("need 5-7 scenes")
    for i, s in enumerate(scenes, 1):
        n = s.get("narration") if isinstance(s, dict) else None
        q = s.get("query") if isinstance(s, dict) else None
        if not isinstance(n, str) or not n.strip():
            bad(f"scene {i}: narration missing")
        if len(n.split()) > 25:
            bad(f"scene {i}: narration over 25 words")
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


def _parse(text):
    """Tolerate code fences and prose around the JSON object."""
    text = re.sub(r"```(?:json)?", "", text)
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end < 0:
        raise ValueError("no JSON object in response")
    return json.loads(text[start:end + 1])


def _call_groq(model, messages):
    r = httpx.post(GROQ_URL, timeout=60,
                   headers={"Authorization": f"Bearer {os.environ['GROQ_API_KEY']}"},
                   json={"model": model, "messages": messages, "temperature": 0.8, "max_tokens": 2000,
                         "reasoning_effort": "low", "response_format": {"type": "json_object"}})
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"]


def _call_gemini(model, messages):
    system = "\n".join(m["content"] for m in messages if m["role"] == "system")
    convo = "\n\n".join(f"{m['role'].upper()}: {m['content']}" for m in messages if m["role"] != "system")
    r = httpx.post(GEMINI_URL.format(m=model), params={"key": os.environ["GEMINI_API_KEY"]}, timeout=60,
                   json={"systemInstruction": {"parts": [{"text": system}]},
                         "contents": [{"parts": [{"text": convo}]}],
                         "generationConfig": {"responseMimeType": "application/json", "temperature": 0.8}})
    r.raise_for_status()
    return r.json()["candidates"][0]["content"]["parts"][0]["text"]


def plan(topic, community="general"):
    preset = COMMUNITIES[community]
    base = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": _user_prompt(topic, preset)}]
    last = None
    for provider, model in CHAIN:
        call = _call_groq if provider == "groq" else _call_gemini
        msgs = list(base)
        for _attempt in range(2):
            try:
                raw = call(model, msgs)
                p = _parse(raw)
                validate_plan(p)
                p["hashtags"] = list(dict.fromkeys(t.strip() for t in p["hashtags"] + preset["hashtags"]))
                p["model"] = model
                return p
            except ValueError as e:  # bad JSON or failed validation -> one guided retry on the same model
                last = e
                msgs = base + [{"role": "assistant", "content": raw},
                               {"role": "user", "content": f"Rejected: {e}. Return the corrected JSON object only."}]
            except (httpx.HTTPError, KeyError, IndexError) as e:  # provider trouble -> next model
                last = e
                time.sleep(2)
                break
    raise RuntimeError(f"plan failed on every model: {last}")


if __name__ == "__main__":
    topic = sys.argv[1] if len(sys.argv) > 1 else "why sleep matters"
    community = sys.argv[2] if len(sys.argv) > 2 else "general"
    out = plan(topic, community)
    print(json.dumps(out, indent=2, ensure_ascii=False))
    words = sum(len(s["narration"].split()) for s in out["scenes"])
    print(f"\n{len(out['scenes'])} scenes, {words} words, model={out['model']}")
