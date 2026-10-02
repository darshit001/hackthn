# Finale Intake and Polish Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add language, duration and trend-fed topic suggestions to the intake, and make every video faster to produce, never blank, and finished with a hook title and Qoneqt end card.

**Architecture:** Language and duration become job options that flow `app.py → pipeline.py → llm.plan / media.tts / media.words`; a `LANGUAGES` table in `presets.py` owns voices, Whisper codes and prompt wording. Scene images and voices are produced in small thread pools. All on-screen text (captions, hook, text-card titles, outro) goes through one ASS overlay mechanism burned by the existing subtitles filter, so no new ffmpeg pass and no new memory pressure.

**Tech Stack:** Python 3.11, FastAPI, httpx, edge-tts, ffmpeg/libass, Groq (gpt-oss-120b, Whisper), Gemini fallback, Google Trends India RSS (stdlib `xml.etree`), pytest. No new dependencies.

Spec: `docs/superpowers/specs/2026-10-02-finale-intake-and-polish-design.md`.

Run every command from the repo root with the venv active: `cd /home/darshit/Desktop/hthn && . .venv/bin/activate`.
Conserve the ElevenLabs quota during smoke runs with `ELEVENLABS_API_KEY=` (empty) so edge-tts speaks.

---

## File map

| File | Change |
|---|---|
| `presets.py` | add `DURATIONS`, `LANGUAGES`; communities get `gender`, lose `voice_edge`; `language` now means default chip |
| `llm.py` | `budget()`, templated `SYSTEM`, scene `title`, `validate_plan(p, scenes)`, shared `_ask()`, `trends()`, `validate_topics()`, `suggest()`, `plan(topic, community, language, duration)` |
| `media.py` | `tts(..., language)` picks the edge voice by language + gender; `words(wav, language)`; `gen_image` runs the chain twice |
| `render.py` | `ass_text()`, `OUTRO`, `OUTRO_SEC`, `subtitles(..., overlays)`, `compose` appends the end card |
| `pipeline.py` | new signature, thread pools, padded voice track, overlays, meta fields, CLI args |
| `app.py` | `/presets` shape, `/generate` options, `/suggest` |
| `static/index.html` | suggestion row, language and duration chips, meta lines, retry payload |
| `tests/test_llm.py`, `tests/test_render.py`, new `tests/test_app.py` | unit tests |
| `README.md` | options and Hindi |

---

### Task 1: Language and duration tables in presets

**Files:**
- Modify: `presets.py`

- [ ] **Step 1: Replace the module with the new tables**

Replace the whole of `presets.py` with:

```python
"""Community presets and language table. Adding a community or a language = adding one dict entry.
voice_eleven ids are ElevenLabs premade voices usable on the free API (Sarah, George, Brian verified 29 Sep 2026);
eleven_flash_v2_5 is multilingual, so the same voice speaks Hindi. gender picks the edge-tts voice from LANGUAGES.
language on a community is only the default language chip in the UI. accent is RRGGBB for the highlighted caption word."""

DURATIONS = [15, 30, 45, 60]

LANGUAGES = {
    "en": dict(
        label="English", whisper="en",
        instruction="English",
        voice_edge={"f": "en-IN-NeerjaNeural", "m": "en-IN-PrabhatNeural"},
    ),
    "hi": dict(
        label="हिन्दी", whisper="hi",
        instruction="Hindi in Devanagari script, simple everyday spoken Hindi; write every number as Hindi words",
        voice_edge={"f": "hi-IN-SwaraNeural", "m": "hi-IN-MadhurNeural"},
    ),
    "hinglish": dict(
        label="Hinglish", whisper="hi",
        instruction="Hinglish written in Roman script (a natural mix of Hindi and English, the way young Indians text)",
        voice_edge={"f": "en-IN-NeerjaNeural", "m": "en-IN-PrabhatNeural"},
    ),
}

COMMUNITIES = {
    "general": dict(
        label="Global Feed (General)",
        tone="Clear, friendly, curiosity-driven for a broad Indian audience. One surprising fact or idea per scene.",
        language="en",
        caption_style="Two short lines: a bold claim or question, then an invitation to comment.",
        hashtags=["#Qoneqt", "#GlobalFeed"],
        voice_eleven="EXAVITQu4vr4xnSDxMaL",  # Sarah
        voice_gemini="Kore",
        gender="f",
        accent="FFE500",
    ),
    "tech": dict(
        label="Tech & AI",
        tone="Punchy and concrete. One real fact, number, or tool per scene. No hype words.",
        language="en",
        caption_style="One-line insight, then 'Save this for later.'",
        hashtags=["#Tech", "#AI", "#Qoneqt"],
        voice_eleven="JBFqnCBsd6RMkjVDRZzb",  # George
        voice_gemini="Charon",
        gender="m",
        accent="00E5FF",
    ),
    "fitness": dict(
        label="Fitness & Health",
        tone="Energetic coach voice. Second person, imperative, short sentences.",
        language="en",
        caption_style="One challenge line, then ask viewers to tag a friend.",
        hashtags=["#Fitness", "#Health", "#Qoneqt"],
        voice_eleven="nPczCjzI2devNBz1zQrb",  # Brian
        voice_gemini="Puck",
        gender="m",
        accent="39FF14",
    ),
    "motivation": dict(
        label="Motivation",
        tone="Warm, story-led, builds to one takeaway line at the end.",
        language="en",
        caption_style="One quotable line, then ask what viewers are working on.",
        hashtags=["#Motivation", "#Mindset", "#Qoneqt"],
        voice_eleven="EXAVITQu4vr4xnSDxMaL",  # Sarah
        voice_gemini="Kore",
        gender="f",
        accent="FFB300",
    ),
    "finance": dict(
        label="Money & Finance",
        tone="Plain money tips for young Indians. Spell every number out in words for the narrator.",
        language="en",
        caption_style="One actionable tip, then 'Not financial advice.'",
        hashtags=["#Finance", "#MoneyTips", "#Qoneqt"],
        voice_eleven="JBFqnCBsd6RMkjVDRZzb",  # George
        voice_gemini="Charon",
        gender="m",
        accent="00FF9C",
    ),
    "hinglish_fun": dict(
        label="Hinglish Fun",
        tone="Playful, desi references, light humour, the way young Indians talk to friends.",
        language="hinglish",
        caption_style="One funny line, then 'Comment karo agar relate kiya.'",
        hashtags=["#Hinglish", "#Desi", "#Qoneqt"],
        voice_eleven="nPczCjzI2devNBz1zQrb",  # Brian
        voice_gemini="Kore",
        gender="m",
        accent="FF2D95",
    ),
}
```

- [ ] **Step 2: Confirm nothing else still reads `voice_edge` from a community**

Run: `grep -n "voice_edge\|\[\"language\"\]\|\['language'\]" *.py`
Expected: hits only in `presets.py` and in `media.py:_tts_edge` (`preset["voice_edge"]`, fixed in Task 4) and `llm.py:_user_prompt` (`preset["language"]`, fixed in Task 2).

- [ ] **Step 3: Commit**

```bash
git add presets.py
git commit -m "Presets: LANGUAGES and DURATIONS tables, gender per community

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 2: Plan stage takes language and duration

**Files:**
- Modify: `llm.py`
- Test: `tests/test_llm.py`

- [ ] **Step 1: Write the failing tests**

In `tests/test_llm.py`, change the import line and `good()`, and add the new tests:

```python
import pytest
from llm import validate_plan, _parse, budget, validate_topics


def good():
    return {
        "hooks": [{"text": "a", "score": 5}, {"text": "b", "score": 6}, {"text": "c", "score": 7}],
        "hook": "Ever wonder why you feel tired?",
        "scenes": [{"narration": f"Sentence number {i} goes here.", "title": f"Point {i}", "query": "city night"} for i in range(5)],
        "caption": "Sleep more.",
        "hashtags": ["#sleep", "#health", "#Qoneqt"],
    }
```

Add to the `test_bad_plan_rejected` parametrize list:

```python
    (lambda p: p["scenes"][0].update(title=""), "title"),
    (lambda p: p["scenes"][0].pop("title"), "title"),
    (lambda p: p["scenes"][0].update(title=" ".join(["w"] * 9)), "title"),
```

Append these tests at the end of the file:

```python
@pytest.mark.parametrize("duration,expected", [
    (15, (3, 4, 31, 41)),
    (30, (4, 6, 61, 83)),
    (45, (6, 8, 92, 124)),
    (60, (8, 9, 122, 166)),
])
def test_budget_windows(duration, expected):
    assert budget(duration) == expected


def test_validate_plan_honours_scene_range():
    p = good()  # 5 scenes
    validate_plan(p, scenes=(3, 5))
    with pytest.raises(ValueError, match="3-4 scenes"):
        validate_plan(p, scenes=(3, 4))


def test_validate_topics():
    validate_topics({"topics": ["a", "b", "c"]})
    for bad in ({"topics": []}, {"topics": ["a", " ", "c"]}, {"topics": "a"}, [], {"topics": ["x"] * 9}):
        with pytest.raises(ValueError, match="topics"):
            validate_topics(bad)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python -m pytest tests/test_llm.py -q`
Expected: ImportError on `budget` (collection fails).

- [ ] **Step 3: Rewrite `llm.py`**

Replace the whole file with:

```python
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


def budget(duration):
    """(scenes_lo, scenes_hi, words_lo, words_hi) for a target spoken length in seconds. Pure; unit-tested.
    About 7 s per scene and 2.4 spoken words per second; every window keeps scenes under the 25-word cap."""
    n = math.ceil(duration / 7)
    return max(3, n - 1), min(9, n + 1), round(duration * 2.4 * 0.85), round(duration * 2.4 * 1.15)


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
    lo, hi, wlo, whi = budget(duration)
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


def _suggest_prompt(preset, lang, trend_titles):
    tr = "\n".join(f"- {t}" for t in trend_titles) or "(none available right now)"
    return (f"Community: {preset['label']}\nTone: {preset['tone']}\nLanguage: {lang['instruction']}\n"
            f"Trending searches in India right now:\n{tr}\nReturn the JSON now.")


def suggest(community="general", language="en"):
    """{'topics': [6 ideas], 'trends': [titles used]}; 3-4 ideas ride today's trends when the feed is up."""
    preset, lang = COMMUNITIES[community], LANGUAGES[language]
    tr = trends()
    base = [{"role": "system", "content": SUGGEST_SYSTEM}, {"role": "user", "content": _suggest_prompt(preset, lang, tr)}]
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
    lo, hi, wlo, whi = budget(duration)
    print(f"\n{len(out['scenes'])} scenes (want {lo}-{hi}), {words} words (want {wlo}-{whi}), model={out['model']}")
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python -m pytest tests/test_llm.py -q`
Expected: all pass (the existing 12 parametrised cases plus 3 title cases, 4 budget cases, 2 new tests).

- [ ] **Step 5: Live check one plan per language (free Groq calls)**

Run:
```bash
python llm.py "chai vs coffee" hinglish_fun hinglish 15 | tail -3
python llm.py "why sleep matters" tech hi 30 | tail -3
python llm.py "5 AI tools every student should know" tech en 60 | tail -3
```
Expected: each prints `N scenes (want lo-hi), W words (want wlo-whi), model=openai/gpt-oss-120b` with N inside the window. Hindi output shows Devanagari narration and titles. Words may sit slightly outside the window; that is informational.

- [ ] **Step 6: Commit**

```bash
git add llm.py tests/test_llm.py
git commit -m "Plan stage: language and duration budget, scene titles, trend-fed topic suggestions

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 3: API: presets shape, generate options, suggest endpoint

**Files:**
- Modify: `app.py`
- Create: `tests/test_app.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_app.py`:

```python
from fastapi.testclient import TestClient

import app as appmod

client = TestClient(appmod.app)  # no `with`: lifespan (worker thread) is not started, which these tests do not need


def test_presets_has_three_lists():
    p = client.get("/presets").json()
    assert p["durations"] == [15, 30, 45, 60]
    assert {x["slug"] for x in p["languages"]} == {"en", "hi", "hinglish"}
    assert next(c for c in p["communities"] if c["slug"] == "hinglish_fun")["language"] == "hinglish"


def test_generate_rejects_bad_options():
    assert client.post("/generate", json={"topics": ["a"], "language": "fr"}).status_code == 400
    assert client.post("/generate", json={"topics": ["a"], "duration": 20}).status_code == 400
    assert client.post("/generate", json={"topics": ["a"], "community": "nope"}).status_code == 400


def test_generate_queues_job_with_options(monkeypatch):
    monkeypatch.setattr(appmod.Q, "put", lambda jid: None)  # keep the job out of the (unstarted) worker queue
    r = client.post("/generate", json={"topics": ["chai vs coffee"], "community": "hinglish_fun", "language": "hinglish", "duration": 15})
    assert r.status_code == 200
    j = client.get(f"/jobs/{r.json()['job_ids'][0]}").json()
    assert (j["language"], j["duration"], j["status"]) == ("hinglish", 15, "queued")


def test_suggest_validates_and_proxies(monkeypatch):
    assert client.get("/suggest", params={"community": "x"}).status_code == 400
    monkeypatch.setattr(appmod.llm, "suggest", lambda c, l: {"topics": ["a", "b", "c"], "trends": []})
    assert client.get("/suggest", params={"community": "tech", "language": "hi"}).json()["topics"] == ["a", "b", "c"]
    def boom(c, l):
        raise RuntimeError("every model failed")
    monkeypatch.setattr(appmod.llm, "suggest", boom)
    assert client.get("/suggest").status_code == 503
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python -m pytest tests/test_app.py -q`
Expected: failures: `/presets` returns a list (KeyError on `"durations"`), bad options return 200, `/suggest` 404.

- [ ] **Step 3: Update `app.py`**

Change the imports:

```python
import llm
import pipeline
from presets import COMMUNITIES, DURATIONS, LANGUAGES
```

Change the worker call inside `_worker`:

```python
            meta = pipeline.make_video(job["topic"], job["community"], progress, job_id=jid,
                                       language=job["language"], duration=job["duration"])
```

Replace `GenerateIn`, `presets()` and `generate()`:

```python
class GenerateIn(BaseModel):
    topics: list[str] = Field(min_length=1, max_length=10)
    community: str = "general"
    language: str = "en"
    duration: int = 30


@app.get("/presets")
def presets():
    return {"communities": [{"slug": k, "label": v["label"], "language": v["language"]} for k, v in COMMUNITIES.items()],
            "languages": [{"slug": k, "label": v["label"]} for k, v in LANGUAGES.items()],
            "durations": DURATIONS}


@app.get("/suggest")
def suggest(community: str = "general", language: str = "en"):
    if community not in COMMUNITIES or language not in LANGUAGES:
        raise HTTPException(400, "unknown community or language")
    try:
        return llm.suggest(community, language)
    except Exception as e:  # every model down: the user can still type a topic
        raise HTTPException(503, f"suggestions unavailable: {str(e)[:120]}")


@app.post("/generate")
def generate(body: GenerateIn):
    if body.community not in COMMUNITIES or body.language not in LANGUAGES or body.duration not in DURATIONS:
        raise HTTPException(400, "unknown community, language or duration")
    ids = []
    for t in body.topics:
        t = t.strip()[:200]
        if not t:
            continue
        jid = secrets.token_hex(4)
        with LOCK:
            JOBS[jid] = {"id": jid, "topic": t, "community": body.community, "language": body.language,
                         "duration": body.duration, "status": "queued", "stage": None, "created": time.time(),
                         "result": None, "error": None}
        Q.put(jid)
        ids.append(jid)
    if not ids:
        raise HTTPException(400, "no topics")
    return {"job_ids": ids}
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python -m pytest tests/test_app.py -q`
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add app.py tests/test_app.py
git commit -m "API: language and duration options, /suggest endpoint, structured /presets

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 4: Media: language-aware voice and Whisper, two image passes

**Files:**
- Modify: `media.py`

- [ ] **Step 1: Update the import and `tts`**

Change the presets import at the top of `media.py`:

```python
from presets import COMMUNITIES, LANGUAGES
```

Replace `tts`:

```python
def tts(text, community, out_wav, language="en"):
    """Synthesise text into a normalised wav at out_wav. Returns the engine name that spoke.
    The edge-tts voice comes from the language table (by the community's gender); ElevenLabs and Gemini voices are per community."""
    preset = dict(COMMUNITIES[community], voice_edge=LANGUAGES[language]["voice_edge"][COMMUNITIES[community]["gender"]])
    out_wav = Path(out_wav)
    errors = []
    for name, fn in TTS_CHAIN:
        tmp = out_wav.with_suffix(f".{name}.raw")
        try:
            fn(text, preset, tmp)
            _normalize(tmp, out_wav)
            return name
        except Exception as e:  # ponytail: any failure -> next engine; the job json records which engine spoke
            errors.append(f"{name}: {str(e)[:160]}")
    raise RuntimeError("all TTS engines failed: " + " | ".join(errors))
```

- [ ] **Step 2: Make `gen_image` run the chain twice**

Replace `gen_image`:

```python
def gen_image(prompt, out_png):
    """AI still for a scene. Pollinations FLUX (keyed) first, Hugging Face Inference second, and the whole chain
    a second time after a pause: most failures seen are transient 500s. Returns a credit line, or None. Never raises."""
    for attempt in range(2):
        for name, fn in IMAGE_CHAIN:
            if name in _image_down:
                continue
            try:
                return fn(prompt + IMAGE_SUFFIX, out_png)
            except Exception as e:
                msg = " ".join(str(e).split())
                if any(code in msg for code in ("401", "402", "403", "429", "no POLLINATIONS", "no HF_TOKEN")):
                    _image_down.add(name)
                print(f"image[{name}] try {attempt + 1} {prompt[:40]!r}: {type(e).__name__}: {msg[:140]}", file=sys.stderr)
        if len(_image_down) == len(IMAGE_CHAIN):
            break  # every provider is out for this process; no point pausing
        time.sleep(2)
    return None
```

- [ ] **Step 3: Pass the language to Whisper**

Replace `words`:

```python
def words(wav, language="en"):
    """Word timings via Groq Whisper: [{'word','start','end'}, ...] in seconds. Telling Whisper the language
    stops it guessing wrong on short Hindi and Hinglish clips."""
    with open(wav, "rb") as f:
        r = httpx.post("https://api.groq.com/openai/v1/audio/transcriptions", timeout=120,
                       headers={"Authorization": f"Bearer {os.environ['GROQ_API_KEY']}"},
                       data={"model": "whisper-large-v3-turbo", "response_format": "verbose_json",
                             "language": LANGUAGES[language]["whisper"], "timestamp_granularities[]": "word"},
                       files={"file": ("voice.wav", f, "audio/wav")})
    r.raise_for_status()
    return [{"word": w["word"].strip(), "start": float(w["start"]), "end": float(w["end"])}
            for w in r.json().get("words", []) if w["word"].strip()]
```

- [ ] **Step 4: Update the self-check to exercise Hindi**

Replace the `__main__` block:

```python
if __name__ == "__main__":
    # python media.py [community] [language]  -> voice + stock clip + whisper check, edge-tts only to spare quota
    d = Path("out/_selfcheck")
    d.mkdir(parents=True, exist_ok=True)
    community = sys.argv[1] if len(sys.argv) > 1 else "general"
    language = sys.argv[2] if len(sys.argv) > 2 else "en"
    text = {"hi": "नमस्ते, यह क्यूनेक्ट वीडियो फैक्ट्री की आवाज़ की जाँच है।"}.get(language, "Hello from the Qoneqt video factory. This is a voice check.")
    eng = tts(text, community, d / "voice.wav", language)
    sec = duration(d / "voice.wav")
    print(f"tts engine={eng} duration={sec:.2f}s")
    assert 2 < sec < 8, sec
    src = stock_clip("city traffic night", sec, d / "clip.mp4")
    print(f"stock={src}" + ("" if src else " (every source failed -> pipeline will draw a card)"))
    if src:
        print(f"clip duration={duration(d / 'clip.mp4'):.1f}s")
    ws = words(d / "voice.wav", language)
    print(f"whisper words={len(ws)} first={ws[:3]}")
    assert len(ws) >= 5, ws
    print("MEDIA OK")
```

- [ ] **Step 5: Run the self-check in English and Hindi**

Run:
```bash
ELEVENLABS_API_KEY= python media.py general en
ELEVENLABS_API_KEY= python media.py tech hi
```
Expected: both end with `MEDIA OK`; the Hindi run prints `tts engine=edge` and Devanagari Whisper words.

- [ ] **Step 6: Run the unit tests and commit**

Run: `python -m pytest -q`
Expected: all pass.

```bash
git add media.py
git commit -m "Media: edge voice by language and gender, Whisper language hint, second image pass

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 5: Render: overlays and end card

**Files:**
- Modify: `render.py`
- Test: `tests/test_render.py`

- [ ] **Step 1: Write the failing tests**

Change the import line in `tests/test_render.py` and append the tests:

```python
from render import ass_time, ass_color, chunk, align, ass_text, subtitles, OUTRO, OUTRO_SEC
```

```python
def test_ass_text_neutralises_markup():
    assert ass_text("a {b} c\\d\ne") == "a (b) c/d\\Ne"


def test_subtitles_writes_overlays(tmp_path):
    words = [w("hello", 0.0, 0.5), w("world", 0.5, 1.0)]
    overlays = [(0.0, 2.5, "Big hook", "Hook"), (3.0, 7.0, "Scene title", "Title"), (10.0, 12.0, OUTRO, "Outro")]
    text = subtitles(words, "general", tmp_path / "c.ass", overlays).read_text()
    assert "Style: Hook," in text and "Style: Title," in text and "Style: Outro," in text
    assert "Dialogue: 1,0:00:00.00,0:00:02.50,Hook,,0,0,0,,{\\fad(200,200)}Big hook" in text
    assert "Dialogue: 1,0:00:03.00,0:00:07.00,Title,,0,0,0,,{\\fad(150,150)}Scene title" in text
    assert "Dialogue: 1,0:00:10.00,0:00:12.00,Outro,,0,0,0,,{\\fad(300,0)}" in text and "Qoneqt" in text
    assert "HELLO" in text  # captions still there


def test_compose_appends_end_card(monkeypatch, tmp_path):
    import render
    cmds = []
    monkeypatch.setattr(render, "_run", lambda cmd, cwd=None: cmds.append(cmd))
    render.compose([(None, 1.0), (None, 2.0)], tmp_path / "voice.wav", tmp_path / "captions.ass", tmp_path, "x")
    assert (tmp_path / "concat.txt").read_text() == "file 'scene0.mp4'\nfile 'scene1.mp4'\nfile 'outro.mp4'\n"
    outro = next(c for c in cmds if c[-1] == str(tmp_path / "outro.mp4"))
    assert f"d={OUTRO_SEC:.3f}" in " ".join(outro)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python -m pytest tests/test_render.py -q`
Expected: ImportError on `ass_text`.

- [ ] **Step 3: Add the overlay mechanism and end card to `render.py`**

Add after `FONT`:

```python
OUTRO_SEC = 2.0  # branded end card; pipeline pads the voice track by the same amount so -shortest keeps lengths equal
VIOLET = "6B3DF0"  # Qoneqt brand violet, used by the outro and the UI
```

Add after `ass_color`:

```python
def ass_text(s):
    """User text -> safe ASS dialogue text: braces would open override blocks and a backslash would start a tag,
    so they become parens and a slash; newlines become hard breaks. ponytail: libass escape sequences vary by version."""
    return str(s).replace("\\", "/").replace("{", "(").replace("}", ")").replace("\n", "\\N")


OUTRO = f"{{\\fs140\\b1\\c{ass_color(VIOLET)}}}Qoneqt{{\\r}}\\NFollow for more"
FX = {"Hook": "{\\fad(200,200)}", "Title": "{\\fad(150,150)}", "Outro": "{\\fad(300,0)}"}
```

Replace `subtitles`:

```python
def subtitles(words, community, out_ass, overlays=()):
    """Write an ASS file: one Dialogue per caption chunk with karaoke \\k per word so the active word lights up in the
    accent colour, plus overlays [(start, end, ass_text, style)] on layer 1: Hook (top), Title (upper third), Outro (centre).
    Everything on screen goes through libass so Devanagari shapes correctly and no extra ffmpeg pass is needed."""
    accent = ass_color(COMMUNITIES[community]["accent"])
    fmt = ("Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, "
           "Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding")
    white, black, shadow = "&H00FFFFFF", "&H00000000", "&H80000000"
    lines = [
        "[Script Info]", "ScriptType: v4.00+", f"PlayResX: {W}", f"PlayResY: {H}", "WrapStyle: 0", "",
        "[V4+ Styles]", fmt,
        f"Style: Cap,{FONT},88,{accent},{white},{black},{shadow},-1,0,0,0,100,100,0,0,1,5,2,2,60,60,{int(H * 0.32)},1",
        f"Style: Hook,{FONT},72,{white},{white},{black},{shadow},-1,0,0,0,100,100,0,0,1,4,2,8,80,80,{int(H * 0.18)},1",
        f"Style: Title,{FONT},96,{accent},{white},{black},{shadow},-1,0,0,0,100,100,0,0,1,4,2,8,80,80,{int(H * 0.30)},1",
        f"Style: Outro,{FONT},64,{white},{white},{black},{shadow},-1,0,0,0,100,100,0,0,1,4,2,5,80,80,0,1",
        "",
        "[Events]", "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
    ]
    for ch in chunk(words):
        parts = []
        for i, x in enumerate(ch):
            nxt = ch[i + 1]["start"] if i + 1 < len(ch) else ch[-1]["end"]
            parts.append(f"{{\\k{max(1, int(round((nxt - x['start']) * 100)))}}}{ass_text(x['word']).upper()}")
        lines.append(f"Dialogue: 0,{ass_time(ch[0]['start'])},{ass_time(ch[-1]['end'] + 0.05)},Cap,,0,0,0,,{' '.join(parts)}")
    for start, end, text, style in overlays:
        lines.append(f"Dialogue: 1,{ass_time(start)},{ass_time(end)},{style},,0,0,0,,{FX.get(style, '')}{text}")
    Path(out_ass).write_text("\n".join(lines) + "\n", encoding="utf-8")
    return Path(out_ass)
```

In `compose`, after the `for` loop that builds `parts` and before `concat.txt` is written, add the end card:

```python
    card(OUTRO_SEC, job_dir / "outro.mp4")
    parts.append("outro.mp4")
```

Update the `__main__` self-check so it exercises overlays: replace the `ass = ...` and `mp4, jpg = ...` lines with

```python
    overlays = [(0.0, 2.0, ass_text("Word-pop captions, now with a hook"), "Hook"), (2.0, 4.0, ass_text("Scene title card"), "Title"),
                (4.0, 4.0 + OUTRO_SEC, OUTRO, "Outro")]
    ass = subtitles(words, "general", d / "captions.ass", overlays)
    _run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono", "-t", f"{4 + OUTRO_SEC}", "-c:a", "pcm_s16le", "voice.wav"], cwd=d)
    mp4, jpg = compose([(None, 2.0), (None, 2.0)], d / "voice.wav", ass, d, "sample")
```

(and delete the earlier `_run([... anullsrc ... "-t", "4" ...])` line so silence is generated once, at the padded length).

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python -m pytest tests/test_render.py -q`
Expected: all pass, including the two pre-existing ffmpeg flag tests.

- [ ] **Step 5: Run the render self-check and look at frames**

Run:
```bash
python render.py
ffmpeg -loglevel error -y -i out/_selfcheck/sample.mp4 -vf "fps=1,scale=270:480,tile=6x1" -frames:v 1 out/_selfcheck/strip.jpg
```
Expected: `RENDER OK -> out/_selfcheck/sample.mp4 ...`; the strip shows the hook at the top in frames 1-2, the yellow title in frames 3-4, and a violet "Qoneqt / Follow for more" card in the last two. Open `out/_selfcheck/strip.jpg` to confirm.

- [ ] **Step 6: Commit**

```bash
git add render.py tests/test_render.py
git commit -m "Render: ASS overlays for hook, text-card titles and Qoneqt end card

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 6: Pipeline: options, thread pools, padded voice, overlays

**Files:**
- Modify: `pipeline.py`

- [ ] **Step 1: Rewrite `pipeline.py`**

Replace the whole file with:

```python
"""Orchestrates one job through the six stages. CLI doubles as the end-to-end smoke test:
    python pipeline.py "why sleep matters" tech en 30"""
import json
import secrets
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import llm
import media
import render

OUT = Path(__file__).parent / "out"
STAGES = ["plan", "images", "voice", "visuals", "captions", "render"]


def make_video(topic, community="general", progress=lambda stage: None, job_id=None, language="en", duration=30):
    """Returns the meta dict that is also written to out/<id>/<id>.json. Raises on unrecoverable failure."""
    job_id = job_id or secrets.token_hex(4)
    d = OUT / job_id
    d.mkdir(parents=True, exist_ok=True)
    t0 = time.time()

    progress("plan")
    p = llm.plan(topic, community, language, duration)
    scenes = p["scenes"]

    progress("images")  # AI still per scene, 3 at a time (Pollinations takes that on the keyed endpoint); None -> stock later
    with ThreadPoolExecutor(3) as pool:
        ai_credits = list(pool.map(lambda a: media.gen_image(a[1].get("image_prompt") or a[1]["query"], d / f"gen{a[0]}.png"), enumerate(scenes)))
    images = [(d / f"gen{i}.png", cr) if cr else None for i, cr in enumerate(ai_credits)]

    progress("voice")  # 2 at a time: the ElevenLabs free tier allows 2 concurrent; a third 429s into a second voice mid-video
    wavs = [d / f"voice{i}.wav" for i in range(len(scenes))]
    with ThreadPoolExecutor(2) as pool:
        engines = list(pool.map(lambda a: media.tts(a[0]["narration"], community, a[1], language), zip(scenes, wavs)))
    secs = [media.duration(w) for w in wavs]
    (d / "voices.txt").write_text("".join(f"file '{w.name}'\n" for w in wavs))
    # silence under the end card keeps the voice track as long as the video, so -shortest cuts nothing
    media._run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", "voices.txt",
                "-af", f"apad=pad_dur={render.OUTRO_SEC}", "-c:a", "pcm_s16le", "voice.wav"], cwd=d)

    progress("visuals")  # sequential: ffmpeg work on 2 vCPUs, more processes would only fight for cores and memory
    clips, sources, credits = [], [], []
    for i, (sc, sec) in enumerate(zip(scenes, secs)):
        c = d / f"clip{i}.mp4"
        img = images[i]
        src = media.stock_clip(sc["query"], sec, c, image=img[0] if img else None, credit=img[1] if img else None)
        clips.append((c if src else None, sec))
        sources.append(src["source"] if src else "card")
        credits.append(src["credit"] if src else "")

    progress("captions")
    bounds, t = [], 0.0
    for sec in secs:
        bounds.append((t, t + sec))
        t += sec
    try:
        timed = media.words(d / "voice.wav", language)
    except Exception:  # ponytail: Whisper down -> align() spreads script words evenly
        timed = []
    words = render.align([s["narration"] for s in scenes], bounds, timed)
    overlays = [(0.0, min(2.5, bounds[0][1]), render.ass_text(p["hook"]), "Hook")]
    overlays += [(s, e, render.ass_text(sc["title"]), "Title") for sc, (s, e), (clip, _) in zip(scenes, bounds, clips) if clip is None]
    overlays.append((t, t + render.OUTRO_SEC, render.OUTRO, "Outro"))
    ass = render.subtitles(words, community, d / "captions.ass", overlays)

    progress("render")
    render.compose(clips, d / "voice.wav", ass, d, job_id)

    meta = {
        "id": job_id, "topic": topic, "community": community, "language": language, "target": duration,
        "hook": p["hook"], "caption": p["caption"], "hashtags": p["hashtags"],
        "scenes": [dict(sc, seconds=round(s, 2), voice=e, visual=v, credit=cr) for sc, s, e, v, cr in zip(scenes, secs, engines, sources, credits)],
        "credits": [cr for cr in credits if cr],
        "duration": round(sum(secs), 2), "llm": p["model"], "whisper_words": len(timed),
        "image_model": next((cr.split(", ", 1)[1] for _, cr in filter(None, images)), None),
        "seconds_to_make": round(time.time() - t0, 1),
        "video": f"/out/{job_id}/{job_id}.mp4", "thumb": f"/out/{job_id}/{job_id}.jpg",
    }
    (d / f"{job_id}.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False))
    return meta


if __name__ == "__main__":
    topic = sys.argv[1] if len(sys.argv) > 1 else "why sleep matters"
    community = sys.argv[2] if len(sys.argv) > 2 else "general"
    language = sys.argv[3] if len(sys.argv) > 3 else "en"
    duration = int(sys.argv[4]) if len(sys.argv) > 4 else 30
    m = make_video(topic, community, progress=lambda s: print(f"[{s}]", flush=True), language=language, duration=duration)
    print(json.dumps(m, indent=2, ensure_ascii=False))
    mp4 = OUT / m["id"] / f"{m['id']}.mp4"
    probe = json.loads(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=codec_type,width,height:format=duration", "-of", "json", mp4],
                                      capture_output=True, text=True, check=True).stdout)
    streams = probe["streams"]
    assert any(s["codec_type"] == "audio" for s in streams), "no audio stream"
    v = next(s for s in streams if s["codec_type"] == "video")
    assert (v["width"], v["height"]) == (render.W, render.H), (v["width"], v["height"])
    assert abs(m["duration"] - duration) <= 0.3 * duration, f"spoke {m['duration']}s for a {duration}s target"
    total = float(probe["format"]["duration"])
    assert abs(total - (m["duration"] + render.OUTRO_SEC)) < 0.5, f"video {total}s vs speech {m['duration']}s + {render.OUTRO_SEC}s card"
    print(f"SMOKE OK -> {mp4}  ({m['duration']}s speech for {duration}s target, made in {m['seconds_to_make']}s)")
```

- [ ] **Step 2: Unit tests still pass**

Run: `python -m pytest -q`
Expected: all pass.

- [ ] **Step 3: End-to-end smoke, one per language, edge-tts only**

Run (each takes 1-2 minutes; they hit Groq, Pollinations, Wikimedia, Whisper, all free):
```bash
ELEVENLABS_API_KEY= python pipeline.py "chai vs coffee" hinglish_fun hinglish 15 | tail -2
ELEVENLABS_API_KEY= python pipeline.py "सुबह जल्दी कैसे उठें" motivation hi 30 | tail -2
ELEVENLABS_API_KEY= python pipeline.py "5 AI tools every student should know" tech en 60 | tail -2
```
Expected: each ends `SMOKE OK -> out/<id>/<id>.mp4 (Xs speech for Ys target, made in Zs)` with Z well under the ~130-190 s seen before. If the duration assertion fails for one language by more than 20 % in both directions of testing, add `wps=<measured words / measured seconds>` to that entry in `LANGUAGES` and use `LANGUAGES[language].get("wps", 2.4)` inside `budget()` by giving `budget` a `wps=2.4` keyword argument that `plan()` passes.

- [ ] **Step 4: Look at the Hindi output**

Run:
```bash
ID=$(ls -t out | head -1); ffmpeg -loglevel error -y -i out/$ID/$ID.mp4 -vf "fps=1/4,scale=270:480,tile=8x1" -frames:v 1 out/$ID/strip.jpg
```
Open `out/<ID>/strip.jpg`. Expected: Devanagari hook at the top of the first frame, Devanagari captions mid-frame, no hollow "tofu" boxes, violet Qoneqt card last. If boxes appear, libass is not falling back to the Devanagari face: add `font="Noto Sans Devanagari"` to `LANGUAGES["hi"]` and give `subtitles()` a `font=FONT` keyword that `pipeline.py` passes as `font=presets.LANGUAGES[language].get("font", render.FONT)`, using it in the four `Style:` lines in place of `{FONT}`.

- [ ] **Step 5: Commit**

```bash
git add pipeline.py presets.py llm.py render.py
git commit -m "Pipeline: language and duration options, parallel images and voice, titled cards, end card

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 7: UI: suggestion row, language and duration chips

**Files:**
- Modify: `static/index.html`

- [ ] **Step 1: Add CSS for the suggestion row**

After the `.chips input:focus-visible+span{...}` rule, add:

```css
.suggest{display:grid;gap:8px}
.suggest .row{display:flex;flex-wrap:wrap;gap:10px;align-items:center}
.ideas{display:flex;flex-wrap:wrap;gap:8px}
.ideas:empty{display:none}
.idea{border:2px dashed var(--violet);background:var(--white);color:var(--ink);border-radius:999px;padding:7px 14px;cursor:pointer;font-weight:600;text-align:left}
.idea:hover{background:var(--mist-2)}
.idea:disabled{border-style:solid;border-color:var(--mist);color:var(--ink-2);cursor:default}
```

- [ ] **Step 2: Add the controls to the form**

Replace the form's inner markup (keep `<form id="intake" ...>`):

```html
    <label for="topics" class="hint" id="intake-title">One topic per line. Each line becomes one video.</label>
    <textarea id="topics" class="topics" rows="4" placeholder="why sleep matters&#10;5 AI tools every student should know&#10;chai vs coffee"></textarea>
    <div class="suggest">
      <div class="row">
        <button type="button" class="btn quiet" id="suggest">Suggest topics</button>
        <span class="status" id="suggest-status">Fresh ideas for the chosen community and language, mixed with what India is searching today.</span>
      </div>
      <div class="ideas" id="ideas"></div>
    </div>
    <fieldset class="chips" id="communities"><legend>Community</legend></fieldset>
    <fieldset class="chips" id="languages"><legend>Language</legend></fieldset>
    <fieldset class="chips" id="durations"><legend>Length</legend></fieldset>
    <div class="go">
      <button type="submit" class="btn" id="start" disabled>Start</button>
      <span class="status" id="intake-status"></span>
    </div>
```

- [ ] **Step 3: Build chip rows from `/presets`**

Replace the `fetch("/presets")...` block with:

```js
function chips(el, name, items, checked) {
  el.insertAdjacentHTML("beforeend", items.map(x =>
    `<label class="chip"><input type="radio" name="${name}" value="${x.slug}"${String(x.slug) === String(checked) ? " checked" : ""}${x.language ? ` data-language="${x.language}"` : ""}><span>${esc(x.label)}</span></label>`).join(""));
}

fetch("/presets").then(r => r.json()).then(p => {
  p.communities.forEach(x => labels[x.slug] = LABEL[x.slug] || x.label);
  p.languages.forEach(x => labels[x.slug] = x.label);
  chips($("#communities"), "community", p.communities.map(x => ({...x, label: label(x.slug)})), p.communities[0].slug);
  chips($("#languages"), "language", p.languages, "en");
  chips($("#durations"), "duration", p.durations.map(d => ({slug: d, label: `${d} s`})), 30);
});

// a community with a non-English default (Hinglish Fun) pulls the language chip along; any change clears stale ideas
$("#intake").addEventListener("change", e => {
  if (e.target.name === "community" && e.target.dataset.language && e.target.dataset.language !== "en") {
    const l = document.querySelector(`input[name=language][value="${e.target.dataset.language}"]`);
    if (l) l.checked = true;
  }
  if (e.target.name === "community" || e.target.name === "language") $("#ideas").innerHTML = "";
});

$("#suggest").onclick = async () => {
  const fd = new FormData($("#intake")), b = $("#suggest"), st = $("#suggest-status");
  b.disabled = true; b.textContent = "Thinking…"; st.textContent = "";
  try {
    const r = await fetch(`/suggest?community=${encodeURIComponent(fd.get("community") || "general")}&language=${encodeURIComponent(fd.get("language") || "en")}`);
    if (!r.ok) throw new Error(await r.text());
    const s = await r.json();
    $("#ideas").innerHTML = s.topics.map(t => `<button type="button" class="idea" data-idea="${esc(t)}">${esc(t)}</button>`).join("");
    st.textContent = s.trends.length ? "Click one to add it. Some ride today's Google Trends India." : "Click one to add it.";
  } catch (_) { st.textContent = "Could not fetch suggestions. Type a topic instead."; }
  b.disabled = false; b.textContent = "Suggest topics";
};
```

- [ ] **Step 4: Send the options and handle idea clicks and retries**

In `$("#intake").onsubmit`, replace the `const community = ...` line and the fetch body:

```js
  const fd = new FormData(e.target);
  const body = {topics, community: fd.get("community") || "general", language: fd.get("language") || "en", duration: +fd.get("duration") || 30};
  $("#start").disabled = true;
  const r = await fetch("/generate", {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify(body)});
```

In the document click handler, add before the `copy` branch:

```js
  const idea = e.target.closest("button[data-idea]");
  if (idea) {
    const cur = lines();
    if (!cur.includes(idea.dataset.idea)) { $("#topics").value = [...cur, idea.dataset.idea].join("\n"); $("#topics").dispatchEvent(new Event("input")); }
    idea.disabled = true;
    return;
  }
```

In the `retry` branch, replace the fetch body with `JSON.stringify(j)` (the stored object now carries all four fields).

In `render()`, change the failed/active row's `data-retry` payload and the meta text:

```js
    const err = j.status === "failed"
      ? `<span class="err">${esc(j.error || "Something went wrong.")} <button type="button" class="btn quiet" data-retry='${esc(JSON.stringify({topics: [j.topic], community: j.community, language: j.language, duration: j.duration}))}'>Try again</button></span>` : "";
    return `<div class="job"><div class="who"><strong>${esc(j.topic)}</strong><small>${esc(label(j.community))}, ${esc(label(j.language))}, ${j.duration} s, ${state}</small>${err}</div>${rail(j)}</div>`;
```

and in the done card:

```js
        <p class="meta">${esc(label(j.community))}, ${esc(label(j.language))}. Asked for ${j.duration} s, spoke ${Math.round(m.duration)} s, made in ${Math.round(m.seconds_to_make)} s with the ${esc(voice)} voice.</p>
```

Update the masthead line to mention the new controls:

```html
    <p>Type a topic or pick a suggestion, choose the community, language and length. Get a Global Feed short with a voice, visuals, word-by-word captions and the post text.</p>
```

- [ ] **Step 5: Check it in a browser**

Run: `uvicorn app:app --port 7860` (background) and open http://localhost:7860.
Expected: three chip rows under the textarea; "Suggest topics" fills 6 dashed chips within a few seconds; clicking one appends it to the textarea and enables "Start 1 video"; choosing "Hinglish Fun" flips the language chip to Hinglish; starting a 15 s job shows "Hinglish Fun, Hinglish, 15 s" on the line and a done card with the end card visible at the tail of the video. Take `docs/screens/ui-v3-desktop.png` with the Playwright MCP (`browser_take_screenshot`) for the README.

- [ ] **Step 6: Commit**

```bash
git add static/index.html docs/screens/ui-v3-desktop.png
git commit -m "UI: topic suggestions, language and length chips, options on job rows

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 8: Docker memory check

**Files:** none modified unless the check fails.

- [ ] **Step 1: Build the image and run a 60 s Hindi job under 1 GB**

```bash
docker build -t qvf .
docker run --rm --memory=1g --env-file .env -e ELEVENLABS_API_KEY= -e FFMPEG_THREADS=2 qvf \
  python pipeline.py "सुबह जल्दी कैसे उठें" motivation hi 60 | tail -3
```
Expected: `SMOKE OK ...`, no `ffmpeg exit -9`. In a second terminal, `docker stats --no-stream` during the render stage should show well under 1 GB (previous baseline: 550 MB peak).

- [ ] **Step 2: If the peak is above ~850 MB**

The only new concurrent work is the image and voice pools, which are network bound, so this is unexpected. Drop the images pool to `ThreadPoolExecutor(2)` in `pipeline.py` and re-run. Record the measured peak in the commit message.

---

### Task 9: Docs

**Files:**
- Modify: `README.md`
- Modify: `docs/superpowers/specs/2026-10-02-finale-intake-and-polish-design.md` (one sentence)

- [ ] **Step 1: Update the README**

Replace the opening paragraph and the pipeline diagram's first two boxes, the local-run block, the presets paragraph and the layout table:

Intro:
```markdown
Topic in, Qoneqt Global Feed short out. An LLM-powered pipeline that turns a topic, idea, or trend into a
publish-ready vertical video with AI script, AI voice, AI or stock visuals, word-pop captions, a hook title
and a Qoneqt end card. Pick the community, the language (English, Hindi, Hinglish) and the length (15-60 s),
or let it suggest topics from what India is searching today. Built for the Qoneqt × CTRL FREAK 2026 challenge.
```

Diagram header lines:
```
 topic + community + language + length        ("Suggest topics": Google Trends India -> Groq -> 6 ideas)
```
and the plan box:
```
 │ 1. PLAN     │   3 scored hooks → best hook, N scenes sized to the length (narration, title, stock query, image prompt), caption, hashtags
```
images box: `3 scenes at a time`; voice box: `2 at a time`; render box: `… burn captions + hook + end card, thumbnail`.

Local run:
```bash
python pipeline.py "why sleep matters" tech en 30   # end-to-end smoke test → out/<id>/<id>.mp4
python llm.py suggest tech hi                       # topic suggestions for a community + language
```

Presets paragraph:
```markdown
`presets.py` holds six community presets (tone, hashtags, voices, caption colour) and a `LANGUAGES` table
(English, Hindi, Hinglish: prompt wording, edge-tts voices by gender, Whisper code). Adding either is one dict entry.
```

Layout table: `presets.py | community presets, languages, durations`; `llm.py | plan stage, topic suggestions, Google Trends, JSON validation, Groq → Gemini chain`; `render.py | ASS captions and overlays (hook, titles, end card), ffmpeg composition`.

- [ ] **Step 2: Fix the one stale sentence in the spec**

In the spec, replace

```
`validate_plan(p, scenes=(5, 7))` takes the allowed scene range; everything else is unchanged. The word
total is reported in the retry message when outside the window but not rejected (TTS pacing varies).
```
with
```
`validate_plan(p, scenes=(5, 7))` takes the allowed scene range; everything else is unchanged. The word
total is not enforced (TTS pacing varies); the smoke test measures real spoken seconds instead.
```

- [ ] **Step 3: Commit**

```bash
git add README.md docs/superpowers/specs/2026-10-02-finale-intake-and-polish-design.md
git commit -m "Docs: language, length and suggestion options

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

## Self-review against the spec

- UI section 1: Task 7 covers textarea, suggestion row (button, chips, Thinking…, failure text, clearing on change), community → Hinglish chip, language and duration chips, meta lines, retry payload. `/presets` shape: Task 3.
- Plan section 2: `LANGUAGES`/`DURATIONS`/`gender`: Task 1. `budget`, templated `SYSTEM`, `title`, `validate_plan(p, scenes)`, Whisper language: Tasks 2 and 4. Pacing tuning path: Task 6 step 3.
- Production section 3: pools of 3 and 2, sequential visuals, two image passes, overlay mechanism with the three styles, end card + `apad`, thumbnail unchanged: Tasks 4, 5, 6. Memory check: Task 8.
- Suggestions section 4: `trends()` cached, `suggest()`, `/suggest` with 400/503: Tasks 2 and 3.
- Testing: unit tests in Tasks 2, 3, 5; live checks in Tasks 2, 4, 6, 7, 8.
- Names used consistently: `budget`, `validate_plan(p, scenes)`, `validate_topics`, `_ask`, `trends`, `suggest`, `tts(text, community, out_wav, language)`, `words(wav, language)`, `ass_text`, `OUTRO`, `OUTRO_SEC`, `FX`, `subtitles(words, community, out_ass, overlays)`, `make_video(..., language, duration)`.
