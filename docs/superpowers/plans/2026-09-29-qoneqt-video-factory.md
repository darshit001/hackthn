# Qoneqt Video Factory Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A FastAPI web app that turns one or many topics plus a Qoneqt community preset into vertical 1080×1920 short videos with LLM script, AI voice, stock visuals, word-pop captions, and a ready-to-paste post text.

**Architecture:** Five sequential stages (plan → voice → visuals → captions → render), each a module with one public function and a fallback chain of free APIs. A single worker thread drains an in-memory job queue so ffmpeg never competes for the 2 vCPUs of a free Hugging Face Space. One static HTML page polls the job list.

**Tech Stack:** Python 3.11+, FastAPI + uvicorn, httpx (all API calls, no vendor SDKs), edge-tts, python-dotenv, ffmpeg/ffprobe (system), pytest. APIs: Groq (gpt-oss-120b, qwen3.8-27b, whisper-large-v3-turbo), ElevenLabs (eleven_flash_v2_5), Gemini (3.8-flash-tts, 3.5-flash-lite), Pexels, Pixabay.

**Spec:** `docs/superpowers/specs/2026-09-29-qoneqt-video-factory-design.md`

**Conventions for every task:**
- Work in `/home/darshit/Desktop/hthn` with the venv active: `. .venv/bin/activate`.
- `.env` already holds `GROQ_API_KEY`, `GEMINI_API_KEY`, `ELEVENLABS_API_KEY`. `PEXELS_API_KEY` / `PIXABAY_API_KEY` may be absent; the code must degrade to gradient cards, never crash.
- Never print or commit keys. `.env` is gitignored.
- Every commit message ends with the line `Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>`.
- Deliberate shortcuts are marked in code with `# ponytail:` comments naming the ceiling and the upgrade path.

---

## File map

| File | Responsibility |
|---|---|
| `presets.py` | `COMMUNITIES` dict: tone, language, voices per engine, caption style, base hashtags, accent colour |
| `llm.py` | `plan(topic, community) -> dict`, `validate_plan(dict)`, `_parse(text)`; Groq → Groq → Gemini chain |
| `media.py` | `tts(text, community, out_wav) -> engine`, `duration(path) -> float`, `stock_clip(query, min_sec, out_mp4) -> source|None`, `words(wav) -> list` |
| `render.py` | `W, H`, `ass_time`, `ass_color`, `align`, `chunk`, `subtitles(...)`, `card(...)`, `compose(...)` |
| `pipeline.py` | `make_video(topic, community, progress, job_id) -> meta dict`; CLI smoke test |
| `app.py` | FastAPI routes, job dict, worker thread |
| `static/index.html` | single-page UI |
| `tests/test_llm.py`, `tests/test_render.py` | unit tests for the pure functions |
| `Dockerfile`, `.dockerignore`, `requirements.txt`, `.env.example`, `README.md` | packaging and docs |

---

### Task 0: Scaffold, venv, presets

**Files:**
- Create: `requirements.txt`, `.env.example`, `.dockerignore`, `presets.py`, `tests/__init__.py`
- Modify: `.gitignore`
- Move: challenge PDF → `docs/challenge-brief.pdf`

- [ ] **Step 1: Create requirements and env example**

`requirements.txt`:
```
fastapi==0.115.*
uvicorn[standard]==0.30.*
httpx==0.27.*
edge-tts==6.1.*
python-dotenv==1.0.*
pytest==8.*
```

`.env.example`:
```
GROQ_API_KEY=
GEMINI_API_KEY=
ELEVENLABS_API_KEY=
PEXELS_API_KEY=
PIXABAY_API_KEY=
```

`.dockerignore`:
```
.env
.venv/
out/
.git/
.playwright-mcp/
docs/
__pycache__/
```

Append to `.gitignore`:
```
.playwright-mcp/
.pytest_cache/
```

- [ ] **Step 2: Create the venv and install**

Run:
```bash
cd /home/darshit/Desktop/hthn && python3 -m venv .venv && . .venv/bin/activate && pip install -q -r requirements.txt && python -c "import fastapi, httpx, edge_tts, dotenv; print('deps ok')"
```
Expected: `deps ok`

- [ ] **Step 3: Write `presets.py`**

```python
"""Community presets. Adding a community = adding one dict entry; nothing else changes.
voice_eleven ids are ElevenLabs premade voices usable on the free API (Sarah, George, Brian verified 29 Sep 2026).
accent is RRGGBB used for the highlighted caption word."""

COMMUNITIES = {
    "general": dict(
        label="Global Feed (General)",
        tone="Clear, friendly, curiosity-driven English for a broad Indian audience. One surprising fact or idea per scene.",
        language="en",
        caption_style="Two short lines: a bold claim or question, then an invitation to comment.",
        hashtags=["#Qoneqt", "#GlobalFeed"],
        voice_eleven="EXAVITQu4vr4xnSDxMaL",  # Sarah
        voice_gemini="Kore",
        voice_edge="en-IN-NeerjaNeural",
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
        voice_edge="en-US-GuyNeural",
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
        voice_edge="en-US-ChristopherNeural",
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
        voice_edge="en-US-AriaNeural",
        accent="FFB300",
    ),
    "finance": dict(
        label="Money & Finance",
        tone="Plain-English money tips for young Indians. Spell every number out in words for the narrator.",
        language="en",
        caption_style="One actionable tip, then 'Not financial advice.'",
        hashtags=["#Finance", "#MoneyTips", "#Qoneqt"],
        voice_eleven="JBFqnCBsd6RMkjVDRZzb",  # George
        voice_gemini="Charon",
        voice_edge="en-IN-PrabhatNeural",
        accent="00FF9C",
    ),
    "hinglish_fun": dict(
        label="Hinglish Fun",
        tone="Playful Hinglish in Roman script, mixing Hindi and English the way young Indians text. Desi references, light humour.",
        language="hinglish",
        caption_style="One funny Hinglish line, then 'Comment karo agar relate kiya.'",
        hashtags=["#Hinglish", "#Desi", "#Qoneqt"],
        voice_eleven="nPczCjzI2devNBz1zQrb",  # Brian
        voice_gemini="Kore",
        voice_edge="en-IN-NeerjaNeural",
        accent="FF2D95",
    ),
}
```

- [ ] **Step 4: Move the brief, create tests package, commit**

Run:
```bash
cd /home/darshit/Desktop/hthn && mv "Qoneqt × CTRL FREAK Challenge FINAL-kcx7b653opy3fxt9ogd3rk1hrr.pdf_20260928_113432_0000.pdf" docs/challenge-brief.pdf && mkdir -p tests && touch tests/__init__.py && python -c "from presets import COMMUNITIES; assert len(COMMUNITIES)==6; print('presets ok')"
git add requirements.txt .env.example .dockerignore .gitignore presets.py tests/__init__.py docs/challenge-brief.pdf
git commit -m "chore: scaffold, presets, challenge brief

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```
Expected: `presets ok`, one commit.

---

### Task 1: `llm.py` — plan generation with validation

**Files:**
- Create: `llm.py`, `tests/test_llm.py`

- [ ] **Step 1: Write the failing tests**

`tests/test_llm.py`:
```python
import pytest
from llm import validate_plan, _parse


def good():
    return {
        "hooks": [{"text": "a", "score": 5}, {"text": "b", "score": 6}, {"text": "c", "score": 7}],
        "hook": "Ever wonder why you feel tired?",
        "scenes": [{"narration": f"Sentence number {i} goes here.", "query": "city night"} for i in range(5)],
        "caption": "Sleep more.",
        "hashtags": ["#sleep", "#health", "#Qoneqt"],
    }


def test_good_plan_passes():
    validate_plan(good())


@pytest.mark.parametrize("mutate,msg", [
    (lambda p: p.update(scenes=p["scenes"][:4]), "5-7 scenes"),
    (lambda p: p.update(scenes=p["scenes"] * 2), "5-7 scenes"),
    (lambda p: p["scenes"][0].update(narration=" ".join(["word"] * 26)), "over 25 words"),
    (lambda p: p["scenes"][0].update(narration="   "), "narration missing"),
    (lambda p: p["scenes"][0].update(query="one two three four five"), "1-4 words"),
    (lambda p: p["scenes"][0].update(query="शहर रात"), "ASCII"),
    (lambda p: p.update(hashtags=["sleep", "#a", "#b"]), "start with #"),
    (lambda p: p.update(hashtags=["#a", "#b"]), "3-10 hashtags"),
    (lambda p: p.update(hook=""), "hook missing"),
    (lambda p: p.update(caption=""), "caption missing"),
])
def test_bad_plan_rejected(mutate, msg):
    p = good()
    mutate(p)
    with pytest.raises(ValueError, match=msg):
        validate_plan(p)


def test_parse_strips_fences_and_prose():
    assert _parse('Sure! ```json\n{"a": 1}\n``` done') == {"a": 1}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /home/darshit/Desktop/hthn && . .venv/bin/activate && python -m pytest tests/test_llm.py -q 2>&1 | tail -3`
Expected: `ModuleNotFoundError: No module named 'llm'`

- [ ] **Step 3: Write `llm.py`**

```python
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
 "scenes": [{"narration": "...", "query": "..."}, ...]   (5 to 7 scenes)
 "caption": "..."                                  (1-3 lines of post text, no hashtags inside)
 "hashtags": ["#...", ...]                         (3 to 8 items, each starting with #)
}
Rules:
- Scene 1 narration must begin with the hook, word for word.
- Each narration is 1-2 spoken sentences, at most 25 words. Total across all scenes: 70-110 words.
- Write numbers as spoken words (say "two thousand", not "2000").
- Each query is 2-4 plain English words naming something visual and generic that a stock-video site has,
  e.g. "city traffic night", "woman laptop cafe", "runner sunrise road". Never brand names, never abstract nouns.
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /home/darshit/Desktop/hthn && . .venv/bin/activate && python -m pytest tests/test_llm.py -q 2>&1 | tail -3`
Expected: `12 passed`

- [ ] **Step 5: Live self-check against Groq**

Run: `cd /home/darshit/Desktop/hthn && . .venv/bin/activate && python llm.py "why sleep matters" tech && python llm.py "chai vs coffee" hinglish_fun | tail -4`
Expected: two JSON plans printed; final lines like `6 scenes, 92 words, model=openai/gpt-oss-120b`. Hinglish narration is Roman-script Hinglish; queries are English.

- [ ] **Step 6: Commit**

```bash
cd /home/darshit/Desktop/hthn && git add llm.py tests/test_llm.py && git commit -m "feat: LLM plan stage with validation and Groq->Gemini fallback

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 2: `media.py` — voice, stock clips, word timings

**Files:**
- Create: `media.py`

No unit test: every function is a thin wrapper over a live API or ffmpeg. The `__main__` self-check is the test.

- [ ] **Step 1: Write `media.py`**

```python
"""Stages 2-4 helpers.
tts:        ElevenLabs -> Gemini TTS -> edge-tts, normalised to 44.1 kHz mono wav (+0.2 s pad)
duration:   ffprobe seconds
stock_clip: Pexels -> Pixabay -> None (caller draws a gradient card)
words:      Groq Whisper word timings"""
import asyncio
import base64
import os
import subprocess
import sys
from pathlib import Path

import httpx
from dotenv import load_dotenv

from presets import COMMUNITIES

load_dotenv()


def _run(cmd, cwd=None):
    subprocess.run(cmd, check=True, capture_output=True, cwd=cwd)


def duration(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
                         check=True, capture_output=True, text=True).stdout
    return float(out.strip())


def _normalize(src, dst):
    """Any audio -> 44.1 kHz mono s16 wav with 0.2 s trailing silence so scenes breathe."""
    _run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(src), "-af", "apad=pad_dur=0.2",
          "-ar", "44100", "-ac", "1", "-c:a", "pcm_s16le", str(dst)])


# ---------- voice ----------

def _tts_eleven(text, preset, tmp):
    key = os.environ.get("ELEVENLABS_API_KEY")
    if not key:
        raise RuntimeError("no ELEVENLABS_API_KEY")
    r = httpx.post(f"https://api.elevenlabs.io/v1/text-to-speech/{preset['voice_eleven']}",
                   params={"output_format": "mp3_44100_128"}, headers={"xi-api-key": key},
                   json={"text": text, "model_id": "eleven_flash_v2_5"}, timeout=90)
    r.raise_for_status()  # 401/402/429 (quota, blocked voice) -> next engine
    tmp.write_bytes(r.content)


def _tts_gemini(text, preset, tmp):
    r = httpx.post("https://generativelanguage.googleapis.com/v1beta/models/gemini-3.8-flash-tts:generateContent",
                   params={"key": os.environ["GEMINI_API_KEY"]}, timeout=90,
                   json={"contents": [{"parts": [{"text": text}]}],
                         "generationConfig": {"responseModalities": ["AUDIO"],
                                              "speechConfig": {"voiceConfig": {"prebuiltVoiceConfig": {"voiceName": preset["voice_gemini"]}}}}})
    r.raise_for_status()
    part = r.json()["candidates"][0]["content"]["parts"][0]["inlineData"]
    data = base64.b64decode(part["data"])
    if "wav" in part["mimeType"]:
        tmp.write_bytes(data)
    else:  # audio/L16;codec=pcm;rate=24000 -> wrap raw PCM
        raw = tmp.with_suffix(".pcm")
        raw.write_bytes(data)
        _run(["ffmpeg", "-y", "-loglevel", "error", "-f", "s16le", "-ar", "24000", "-ac", "1", "-i", str(raw), "-f", "wav", str(tmp)])


def _tts_edge(text, preset, tmp):
    import edge_tts
    asyncio.run(edge_tts.Communicate(text, preset["voice_edge"]).save(str(tmp)))


TTS_CHAIN = [("elevenlabs", _tts_eleven), ("gemini", _tts_gemini), ("edge", _tts_edge)]


def tts(text, community, out_wav):
    """Synthesise text into a normalised wav at out_wav. Returns the engine name that spoke."""
    preset = COMMUNITIES[community]
    out_wav = Path(out_wav)
    last = None
    for name, fn in TTS_CHAIN:
        tmp = out_wav.with_suffix(f".{name}.raw")
        try:
            fn(text, preset, tmp)
            _normalize(tmp, out_wav)
            return name
        except Exception as e:  # ponytail: any failure -> next engine; the job json records which engine spoke
            last = e
    raise RuntimeError(f"all TTS engines failed: {last}")


# ---------- visuals ----------

def _download(url, dst):
    with httpx.stream("GET", url, timeout=120, follow_redirects=True) as r:
        r.raise_for_status()
        with open(dst, "wb") as f:
            for chunk in r.iter_bytes(1 << 16):
                f.write(chunk)


def _pexels(query, min_sec):
    key = os.environ.get("PEXELS_API_KEY")
    if not key:
        raise RuntimeError("no PEXELS_API_KEY")
    r = httpx.get("https://api.pexels.com/videos/search", headers={"Authorization": key}, timeout=30,
                  params={"query": query, "orientation": "portrait", "size": "medium", "per_page": 8})
    r.raise_for_status()
    vids = r.json().get("videos", [])
    if not vids:
        raise LookupError(f"pexels: nothing for {query!r}")
    vids.sort(key=lambda v: (v["duration"] < min_sec, v["duration"]))  # long enough first, then shortest
    files = vids[0]["video_files"]
    tall = [f for f in files if (f.get("height") or 0) >= 1080]
    best = min(tall, key=lambda f: f["height"]) if tall else max(files, key=lambda f: f.get("height") or 0)
    return best["link"]


def _pixabay(query, min_sec):
    key = os.environ.get("PIXABAY_API_KEY")
    if not key:
        raise RuntimeError("no PIXABAY_API_KEY")
    r = httpx.get("https://pixabay.com/api/videos/", timeout=30,
                  params={"key": key, "q": query, "per_page": 8, "safesearch": "true"})
    r.raise_for_status()
    hits = r.json().get("hits", [])
    if not hits:
        raise LookupError(f"pixabay: nothing for {query!r}")
    hits.sort(key=lambda h: (h["duration"] < min_sec, h["duration"]))
    v = hits[0]["videos"]
    return (v.get("large") or v.get("medium") or v["small"])["url"]


def stock_clip(query, min_sec, out_mp4):
    """Download one stock clip for the query. Returns 'pexels' | 'pixabay', or None when every source failed."""
    for name, fn in (("pexels", _pexels), ("pixabay", _pixabay)):
        try:
            _download(fn(query, min_sec), out_mp4)
            return name
        except Exception:
            continue
    return None


# ---------- captions ----------

def words(wav):
    """Word timings via Groq Whisper: [{'word','start','end'}, ...] in seconds."""
    with open(wav, "rb") as f:
        r = httpx.post("https://api.groq.com/openai/v1/audio/transcriptions", timeout=120,
                       headers={"Authorization": f"Bearer {os.environ['GROQ_API_KEY']}"},
                       data={"model": "whisper-large-v3-turbo", "response_format": "verbose_json",
                             "timestamp_granularities[]": "word"},
                       files={"file": ("voice.wav", f, "audio/wav")})
    r.raise_for_status()
    return [{"word": w["word"].strip(), "start": float(w["start"]), "end": float(w["end"])}
            for w in r.json().get("words", []) if w["word"].strip()]


if __name__ == "__main__":
    d = Path("out/_selfcheck")
    d.mkdir(parents=True, exist_ok=True)
    community = sys.argv[1] if len(sys.argv) > 1 else "general"
    eng = tts("Hello from the Qoneqt video factory. This is a voice check.", community, d / "voice.wav")
    sec = duration(d / "voice.wav")
    print(f"tts engine={eng} duration={sec:.2f}s")
    assert 2 < sec < 8, sec
    src = stock_clip("city traffic night", sec, d / "clip.mp4")
    print(f"stock source={src}" + ("" if src else " (no key or no hit -> pipeline will draw a card)"))
    if src:
        print(f"clip duration={duration(d / 'clip.mp4'):.1f}s")
    ws = words(d / "voice.wav")
    print(f"whisper words={len(ws)} first={ws[:3]}")
    assert len(ws) >= 6, ws
    print("MEDIA OK")
```

- [ ] **Step 2: Live self-check**

Run: `cd /home/darshit/Desktop/hthn && . .venv/bin/activate && python media.py general`
Expected:
```
tts engine=elevenlabs duration=4.xx s
stock source=pexels          (or: stock source=None (no key ...) if PEXELS_API_KEY is not set yet)
whisper words=11 first=[{'word': 'Hello', ...
MEDIA OK
```

- [ ] **Step 3: Force the voice fallback once**

Run: `cd /home/darshit/Desktop/hthn && . .venv/bin/activate && ELEVENLABS_API_KEY=bad python media.py general | head -1`
Expected: `tts engine=gemini duration=...` (ElevenLabs 401 falls through silently).

- [ ] **Step 4: Commit**

```bash
cd /home/darshit/Desktop/hthn && git add media.py && git commit -m "feat: voice, stock clip, and whisper helpers with fallback chains

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 3: `render.py` — captions and ffmpeg composition

**Files:**
- Create: `render.py`, `tests/test_render.py`

- [ ] **Step 1: Write the failing tests**

`tests/test_render.py`:
```python
from render import ass_time, ass_color, chunk, align


def test_ass_time_formats_centiseconds():
    assert ass_time(0) == "0:00:00.00"
    assert ass_time(61.5) == "0:01:01.50"
    assert ass_time(3599.994) == "0:59:59.99"


def test_ass_color_is_bgr_with_zero_alpha():
    assert ass_color("FFE500") == "&H0000E5FF"
    assert ass_color("00E5FF") == "&H00FFE500"


def w(word, start, end):
    return {"word": word, "start": start, "end": end}


def test_chunk_splits_by_size_and_gap():
    words = [w("a", 0, .2), w("b", .2, .4), w("c", .4, .6), w("d", .6, .8), w("e", .8, 1.0),
             w("f", 2.0, 2.2), w("g", 2.2, 2.4)]
    got = chunk(words, size=4, max_gap=0.6)
    assert [[x["word"] for x in c] for c in got] == [["a", "b", "c", "d"], ["e"], ["f", "g"]]


def test_align_uses_script_spelling_when_counts_match():
    timed = [w("Hello", 0.2, 0.5), w("from", 0.5, 0.9), w("QNECT", 0.9, 1.5)]
    got = align(["Hello from Qoneqt"], [(0.0, 1.8)], timed)
    assert [x["word"] for x in got] == ["Hello", "from", "Qoneqt"]
    assert got[2]["start"] == 0.9


def test_align_spreads_evenly_when_whisper_is_empty():
    got = align(["one two three four"], [(2.0, 4.0)], [])
    assert [x["word"] for x in got] == ["one", "two", "three", "four"]
    assert got[0]["start"] == 2.0 and abs(got[-1]["end"] - 4.0) < 1e-9


def test_align_falls_back_to_whisper_words_on_big_mismatch():
    timed = [w(f"w{i}", i * 0.2, i * 0.2 + 0.2) for i in range(10)]
    got = align(["just two"], [(0.0, 2.0)], timed)
    assert len(got) == 10
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /home/darshit/Desktop/hthn && . .venv/bin/activate && python -m pytest tests/test_render.py -q 2>&1 | tail -3`
Expected: `ModuleNotFoundError: No module named 'render'`

- [ ] **Step 3: Write `render.py`**

```python
"""Stages 4-5: word-pop ASS captions and ffmpeg composition.
W, H is the single aspect-ratio knob for the whole project."""
import subprocess
from pathlib import Path

from presets import COMMUNITIES

W, H = 1080, 1920  # ponytail: one knob; set 1080, 1080 for a square feed variant
FONT = "Noto Sans"  # fontconfig substitutes (DejaVu Sans) when absent; Docker installs fonts-noto-core


def _run(cmd, cwd=None):
    subprocess.run(cmd, check=True, capture_output=True, cwd=cwd)


def ass_time(sec):
    cs = int(round(sec * 100))
    h, rem = divmod(cs, 360000)
    m, rem = divmod(rem, 6000)
    s, c = divmod(rem, 100)
    return f"{h}:{m:02d}:{s:02d}.{c:02d}"


def ass_color(rgb_hex):
    """'RRGGBB' -> ASS '&H00BBGGRR' (alpha 00 = opaque)."""
    r, g, b = rgb_hex[0:2], rgb_hex[2:4], rgb_hex[4:6]
    return f"&H00{b}{g}{r}".upper()


def align(scene_texts, scene_bounds, timed):
    """Give each scene's script words Whisper timings.
    scene_bounds: [(start, end)] seconds per scene on the full voice track. timed: Whisper words.
    Per scene: no Whisper words -> spread script words evenly; counts within 2 -> script spelling on Whisper
    timings; otherwise Whisper's own words. Returns a flat [{'word','start','end'}]."""
    out = []
    for text, (s, e) in zip(scene_texts, scene_bounds):
        script = text.split()
        got = [x for x in timed if s - 0.05 <= x["start"] < e - 0.05]
        if not got:
            step = (e - s) / max(len(script), 1)
            out += [{"word": x, "start": s + i * step, "end": s + (i + 1) * step} for i, x in enumerate(script)]
        elif abs(len(got) - len(script)) <= 2:
            n = min(len(got), len(script))
            # ponytail: on a 1-2 word count mismatch the trailing script words are dropped from captions only
            out += [{"word": script[i], "start": got[i]["start"], "end": got[i]["end"]} for i in range(n)]
        else:
            out += got
    return out


def chunk(words, size=4, max_gap=0.6):
    """Group words into caption lines of up to `size` words, breaking on pauses longer than max_gap."""
    chunks, cur = [], []
    for x in words:
        if cur and (len(cur) >= size or x["start"] - cur[-1]["end"] > max_gap):
            chunks.append(cur)
            cur = []
        cur.append(x)
    if cur:
        chunks.append(cur)
    return chunks


def subtitles(words, community, out_ass):
    """Write an ASS file: one Dialogue per chunk, karaoke \\k per word so the active word lights up in the accent colour."""
    accent = ass_color(COMMUNITIES[community]["accent"])
    lines = [
        "[Script Info]", "ScriptType: v4.00+", f"PlayResX: {W}", f"PlayResY: {H}", "WrapStyle: 2", "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, "
        "Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
        f"Style: Cap,{FONT},80,{accent},&H00FFFFFF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,5,2,2,60,60,{int(H * 0.32)},1",
        "",
        "[Events]", "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
    ]
    for ch in chunk(words):
        parts = []
        for i, x in enumerate(ch):
            nxt = ch[i + 1]["start"] if i + 1 < len(ch) else ch[-1]["end"]
            parts.append(f"{{\\k{max(1, int(round((nxt - x['start']) * 100)))}}}{x['word'].upper()}")
        lines.append(f"Dialogue: 0,{ass_time(ch[0]['start'])},{ass_time(ch[-1]['end'] + 0.05)},Cap,,0,0,0,,{' '.join(parts)}")
    Path(out_ass).write_text("\n".join(lines) + "\n", encoding="utf-8")
    return Path(out_ass)


def card(sec, out_mp4):
    """Fallback visual: slowly moving purple gradient. Captions carry the words."""
    _run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi",
          "-i", f"gradients=s={W}x{H}:c0=0x2A0E5C:c1=0x0B0416:speed=0.02:d={sec:.3f}",
          "-r", "30", "-pix_fmt", "yuv420p", "-c:v", "libx264", "-preset", "veryfast", "-t", f"{sec:.3f}", str(out_mp4)])


def _scene_video(src, sec, dst, cwd):
    """Loop/trim a clip to `sec`, cover-scale and centre-crop to W×H, drop its audio."""
    _run(["ffmpeg", "-y", "-loglevel", "error", "-stream_loop", "-1", "-i", str(src), "-t", f"{sec:.3f}", "-an",
          "-vf", f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},fps=30,setsar=1",
          "-c:v", "libx264", "-preset", "veryfast", "-crf", "23", "-pix_fmt", "yuv420p", dst], cwd=cwd)


def compose(scene_clips, voice_wav, ass, job_dir, out_id):
    """scene_clips: [(clip path or None, seconds)] in order. Writes <job_dir>/<out_id>.mp4 and .jpg. Returns (mp4, jpg)."""
    job_dir = Path(job_dir)
    parts = []
    for i, (clip, sec) in enumerate(scene_clips):
        dst = f"scene{i}.mp4"
        if clip is None:
            card(sec, job_dir / dst)
        else:
            _scene_video(clip, sec, dst, job_dir)
        parts.append(dst)
    (job_dir / "concat.txt").write_text("".join(f"file '{p}'\n" for p in parts))
    mp4, jpg = job_dir / f"{out_id}.mp4", job_dir / f"{out_id}.jpg"
    _run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", "concat.txt", "-i", str(voice_wav),
          "-vf", f"subtitles={Path(ass).name}", "-c:v", "libx264", "-preset", "veryfast", "-crf", "23", "-pix_fmt", "yuv420p",
          "-c:a", "aac", "-b:a", "128k", "-shortest", "-movflags", "+faststart", mp4.name], cwd=job_dir)
    _run(["ffmpeg", "-y", "-loglevel", "error", "-ss", "1", "-i", mp4.name, "-frames:v", "1", "-q:v", "3", jpg.name], cwd=job_dir)
    return mp4, jpg


if __name__ == "__main__":
    # Offline self-check: two gradient scenes, synthetic silence, fake word timings -> out/_selfcheck/sample.mp4
    d = Path("out/_selfcheck")
    d.mkdir(parents=True, exist_ok=True)
    _run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono", "-t", "4", "-c:a", "pcm_s16le", "voice.wav"], cwd=d)
    timed = [{"word": w, "start": i * 0.4, "end": i * 0.4 + 0.35} for i, w in enumerate("word pop captions light up one at a time".split())]
    words = align(["word pop captions light up", "one at a time"], [(0, 2), (2, 4)], timed)
    ass = subtitles(words, "general", d / "captions.ass")
    mp4, jpg = compose([(None, 2.0), (None, 2.0)], d / "voice.wav", ass, d, "sample")
    probe = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=codec_type,width,height", "-of", "csv=p=0", mp4],
                           capture_output=True, text=True, check=True).stdout
    print(probe.strip())
    assert f"video,{W},{H}" in probe and "audio" in probe, probe
    print(f"RENDER OK -> {mp4} {jpg}")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /home/darshit/Desktop/hthn && . .venv/bin/activate && python -m pytest tests -q 2>&1 | tail -3`
Expected: `18 passed`

- [ ] **Step 5: Offline render self-check, then eyeball a frame**

Run: `cd /home/darshit/Desktop/hthn && . .venv/bin/activate && python render.py && ffmpeg -y -loglevel error -ss 1.2 -i out/_selfcheck/sample.mp4 -frames:v 1 out/_selfcheck/frame.png && echo frame written`
Expected: `video,1080,1920` and `audio` lines, `RENDER OK`, then `frame written`. Open `out/_selfcheck/frame.png` (Read tool) and confirm big uppercase words on a purple gradient with one word in yellow, positioned in the lower third but not at the very bottom.

- [ ] **Step 6: Commit**

```bash
cd /home/darshit/Desktop/hthn && git add render.py tests/test_render.py && git commit -m "feat: word-pop ASS captions and ffmpeg composition

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 4: `pipeline.py` — orchestration and first real video

**Files:**
- Create: `pipeline.py`

- [ ] **Step 1: Write `pipeline.py`**

```python
"""Orchestrates one job through the five stages. CLI doubles as the end-to-end smoke test:
    python pipeline.py "why sleep matters" tech"""
import json
import secrets
import subprocess
import sys
import time
from pathlib import Path

import llm
import media
import render

OUT = Path(__file__).parent / "out"
STAGES = ["plan", "voice", "visuals", "captions", "render"]


def make_video(topic, community="general", progress=lambda stage: None, job_id=None):
    """Returns the meta dict that is also written to out/<id>/<id>.json. Raises on unrecoverable failure."""
    job_id = job_id or secrets.token_hex(4)
    d = OUT / job_id
    d.mkdir(parents=True, exist_ok=True)
    t0 = time.time()

    progress("plan")
    p = llm.plan(topic, community)

    progress("voice")
    wavs, engines = [], []
    for i, sc in enumerate(p["scenes"]):
        w = d / f"voice{i}.wav"
        engines.append(media.tts(sc["narration"], community, w))
        wavs.append(w)
    secs = [media.duration(w) for w in wavs]
    (d / "voices.txt").write_text("".join(f"file '{w.name}'\n" for w in wavs))
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", "voices.txt", "-c", "copy", "voice.wav"],
                   check=True, capture_output=True, cwd=d)

    progress("visuals")
    clips, sources = [], []
    for i, (sc, sec) in enumerate(zip(p["scenes"], secs)):
        c = d / f"clip{i}.mp4"
        src = media.stock_clip(sc["query"], sec, c)
        clips.append((c if src else None, sec))
        sources.append(src or "card")

    progress("captions")
    bounds, t = [], 0.0
    for sec in secs:
        bounds.append((t, t + sec))
        t += sec
    try:
        timed = media.words(d / "voice.wav")
    except Exception:  # ponytail: Whisper down -> align() spreads script words evenly
        timed = []
    words = render.align([s["narration"] for s in p["scenes"]], bounds, timed)
    ass = render.subtitles(words, community, d / "captions.ass")

    progress("render")
    render.compose(clips, d / "voice.wav", ass, d, job_id)

    meta = {
        "id": job_id, "topic": topic, "community": community,
        "hook": p["hook"], "caption": p["caption"], "hashtags": p["hashtags"],
        "scenes": [dict(sc, seconds=round(s, 2), voice=e, visual=v) for sc, s, e, v in zip(p["scenes"], secs, engines, sources)],
        "duration": round(sum(secs), 2), "llm": p["model"], "whisper_words": len(timed),
        "seconds_to_make": round(time.time() - t0, 1),
        "video": f"/out/{job_id}/{job_id}.mp4", "thumb": f"/out/{job_id}/{job_id}.jpg",
    }
    (d / f"{job_id}.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False))
    return meta


if __name__ == "__main__":
    topic = sys.argv[1] if len(sys.argv) > 1 else "why sleep matters"
    community = sys.argv[2] if len(sys.argv) > 2 else "general"
    m = make_video(topic, community, progress=lambda s: print(f"[{s}]", flush=True))
    print(json.dumps(m, indent=2, ensure_ascii=False))
    mp4 = OUT / m["id"] / f"{m['id']}.mp4"
    probe = json.loads(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=codec_type,width,height", "-of", "json", mp4],
                                      capture_output=True, text=True, check=True).stdout)["streams"]
    assert any(s["codec_type"] == "audio" for s in probe), "no audio stream"
    v = next(s for s in probe if s["codec_type"] == "video")
    assert (v["width"], v["height"]) == (render.W, render.H), (v["width"], v["height"])
    assert 20 <= m["duration"] <= 60, f"duration {m['duration']}s outside 20-60"
    print(f"SMOKE OK -> {mp4}")
```

- [ ] **Step 2: Run the end-to-end smoke test**

Run: `cd /home/darshit/Desktop/hthn && . .venv/bin/activate && python pipeline.py "why sleep matters" tech 2>&1 | tail -25`
Expected: `[plan] [voice] [visuals] [captions] [render]` then the meta JSON and `SMOKE OK -> out/<id>/<id>.mp4`. Typical `seconds_to_make` 60-120 on the laptop.

- [ ] **Step 3: Watch it**

Run: `cd /home/darshit/Desktop/hthn && ls out/*/*.mp4 | tail -1 && xdg-open $(ls -t out/*/*.mp4 | head -1) 2>/dev/null || true`
Also grab three frames for the deck: `ffmpeg -y -loglevel error -i <mp4> -vf "fps=1/8" out/_frames_%02d.png`. Check: captions readable, active word highlighted, no black bars, audio in sync with the highlighted word (within a beat).

- [ ] **Step 4: Second smoke in Hinglish**

Run: `cd /home/darshit/Desktop/hthn && . .venv/bin/activate && python pipeline.py "chai vs coffee" hinglish_fun 2>&1 | tail -3`
Expected: `SMOKE OK`. Confirms the Hinglish preset, a second voice, and ASCII-only queries hold under a different LLM output.

- [ ] **Step 5: Commit**

```bash
cd /home/darshit/Desktop/hthn && git add pipeline.py && git commit -m "feat: pipeline orchestration with end-to-end smoke test

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 5: `app.py` and `static/index.html` — web UI with batch queue

**Files:**
- Create: `app.py`, `static/index.html`

- [ ] **Step 1: Write `app.py`**

```python
"""FastAPI front: job dict + one worker thread + static UI.
ponytail: in-memory jobs (Redis/SQLite if history is ever needed); ephemeral out/ (HF persistent volume if videos must survive restarts)."""
import queue
import secrets
import threading
import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

import pipeline
from presets import COMMUNITIES

ROOT = Path(__file__).parent
pipeline.OUT.mkdir(exist_ok=True)
JOBS, LOCK, Q = {}, threading.Lock(), queue.Queue()


def _worker():
    while True:
        jid = Q.get()
        job = JOBS[jid]

        def progress(stage):
            with LOCK:
                job["status"], job["stage"] = "running", stage

        try:
            meta = pipeline.make_video(job["topic"], job["community"], progress, job_id=jid)
            with LOCK:
                job.update(status="done", stage=None, result=meta)
        except Exception as e:  # one bad job never kills the worker
            with LOCK:
                job.update(status="failed", error=f"{job['stage']}: {e}"[:500])


@asynccontextmanager
async def lifespan(_app):
    threading.Thread(target=_worker, daemon=True).start()  # ponytail: single worker = serialised ffmpeg on 2 vCPUs
    yield


app = FastAPI(title="Qoneqt Video Factory", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=ROOT / "static"), name="static")
app.mount("/out", StaticFiles(directory=pipeline.OUT), name="out")


class GenerateIn(BaseModel):
    topics: list[str] = Field(min_length=1, max_length=10)
    community: str = "general"


@app.get("/")
def index():
    return FileResponse(ROOT / "static" / "index.html")


@app.get("/presets")
def presets():
    return [{"slug": k, "label": v["label"]} for k, v in COMMUNITIES.items()]


@app.post("/generate")
def generate(body: GenerateIn):
    if body.community not in COMMUNITIES:
        raise HTTPException(400, "unknown community")
    ids = []
    for t in body.topics:
        t = t.strip()[:200]
        if not t:
            continue
        jid = secrets.token_hex(4)
        with LOCK:
            JOBS[jid] = {"id": jid, "topic": t, "community": body.community, "status": "queued",
                         "stage": None, "created": time.time(), "result": None, "error": None}
        Q.put(jid)
        ids.append(jid)
    if not ids:
        raise HTTPException(400, "no topics")
    return {"job_ids": ids}


@app.get("/jobs")
def jobs():
    with LOCK:
        return sorted(JOBS.values(), key=lambda j: -j["created"])


@app.get("/jobs/{jid}")
def job(jid: str):
    with LOCK:
        if jid not in JOBS:
            raise HTTPException(404, "no such job")
        return JOBS[jid]
```

- [ ] **Step 2: Write `static/index.html`**

```html
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Qoneqt Video Factory</title>
<style>
:root{--bg:#0b0416;--card:#160a2b;--line:#2d1b4e;--txt:#f3eefc;--mut:#a89cc4;--acc:#8b5cf6;--acc2:#c4b5fd;--err:#ff7b7b}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--txt);font:16px/1.5 system-ui,-apple-system,Segoe UI,Roboto,sans-serif}
.wrap{max-width:960px;margin:0 auto;padding:24px 16px}
h1{font-size:28px;margin:0 0 4px}h1 span{color:var(--acc2)}
.sub{color:var(--mut);margin:0 0 20px}
form{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:16px;display:grid;gap:12px}
textarea,select{width:100%;background:#0f0720;color:var(--txt);border:1px solid var(--line);border-radius:10px;padding:10px;font:inherit}
textarea{min-height:96px;resize:vertical}
.row{display:flex;gap:12px;flex-wrap:wrap;align-items:center}.row select{flex:1;min-width:200px}
button{background:var(--acc);color:#fff;border:0;border-radius:10px;padding:10px 18px;font:inherit;font-weight:600;cursor:pointer}
button.ghost{background:transparent;border:1px solid var(--line);color:var(--acc2)}
.jobs{display:grid;gap:16px;margin-top:24px}
.job{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:16px;display:grid;gap:12px}
@media(min-width:720px){.job.done{grid-template-columns:270px 1fr}}
.topic{font-weight:600}.meta{color:var(--mut);font-size:14px}
.steps{display:flex;gap:6px;margin-top:8px}.steps i{flex:1;height:6px;border-radius:3px;background:var(--line)}
.steps i.on{background:var(--acc)}.steps i.run{background:var(--acc2);animation:p 1s infinite alternate}
@keyframes p{to{opacity:.35}}
video{width:100%;max-height:70vh;border-radius:12px;background:#000;aspect-ratio:9/16}
.post{background:#0f0720;border:1px solid var(--line);border-radius:10px;padding:12px;white-space:pre-wrap;font-size:15px;margin-top:10px}
.tags{color:var(--acc2)}.err{color:var(--err)}
</style>
</head>
<body>
<div class="wrap">
  <h1>Qoneqt <span>Video Factory</span></h1>
  <p class="sub">Topic in, Global Feed short out. One topic per line for batch mode.</p>
  <form id="f">
    <textarea id="topics" placeholder="why sleep matters&#10;5 AI tools every student should know" required></textarea>
    <div class="row">
      <select id="community" aria-label="Community"></select>
      <button type="submit">Generate</button>
    </div>
  </form>
  <div class="jobs" id="jobs"></div>
</div>
<script>
const $ = s => document.querySelector(s);
const STAGES = ["plan", "voice", "visuals", "captions", "render"];
const posts = {};
let timer = null;

fetch("/presets").then(r => r.json()).then(p => {
  $("#community").innerHTML = p.map(x => `<option value="${x.slug}">${x.label}</option>`).join("");
});

$("#f").onsubmit = async e => {
  e.preventDefault();
  const topics = $("#topics").value.split("\n").map(s => s.trim()).filter(Boolean).slice(0, 10);
  const r = await fetch("/generate", {method: "POST", headers: {"Content-Type": "application/json"},
    body: JSON.stringify({topics, community: $("#community").value})});
  if (!r.ok) { alert(await r.text()); return; }
  $("#topics").value = "";
  poll();
};

$("#jobs").onclick = e => {
  const b = e.target.closest("button[data-copy]");
  if (!b) return;
  navigator.clipboard.writeText(posts[b.dataset.copy]).then(() => { b.textContent = "Copied"; });
};

function esc(s) { return String(s).replace(/[&<>"]/g, c => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;"}[c])); }

async function poll() {
  clearTimeout(timer);
  const jobs = await (await fetch("/jobs")).json();
  render(jobs);
  if (jobs.some(j => j.status === "queued" || j.status === "running")) timer = setTimeout(poll, 2000);
}

function render(jobs) {
  $("#jobs").innerHTML = jobs.map(j => {
    const idx = STAGES.indexOf(j.stage);
    const steps = STAGES.map((s, i) => {
      const cls = j.status === "done" || i < idx ? "on" : (i === idx && j.status === "running" ? "run" : "");
      return `<i class="${cls}" title="${s}"></i>`;
    }).join("");
    let info = `<div><div class="topic">${esc(j.topic)}</div>
      <div class="meta">${esc(j.community)} · ${j.status}${j.stage ? " · " + j.stage : ""}</div>
      <div class="steps">${steps}</div>${j.error ? `<div class="err">${esc(j.error)}</div>` : ""}`;
    if (j.status !== "done") return `<div class="job">${info}</div></div>`;
    const m = j.result;
    posts[j.id] = `${m.hook}\n\n${m.caption}\n\n${m.hashtags.join(" ")}`;
    return `<div class="job done">
      <video controls playsinline poster="${m.thumb}" src="${m.video}"></video>
      ${info}
        <div class="post">${esc(m.hook)}\n\n${esc(m.caption)}\n\n<span class="tags">${esc(m.hashtags.join(" "))}</span></div>
        <div class="row" style="margin-top:10px">
          <button type="button" class="ghost" data-copy="${j.id}">Copy post text</button>
          <a href="${m.video}" download><button type="button" class="ghost">Download mp4</button></a>
          <span class="meta">${m.duration}s video · made in ${m.seconds_to_make}s · voice ${esc(m.scenes[0].voice)}</span>
        </div>
      </div>
    </div>`;
  }).join("");
}
poll();
</script>
</body>
</html>
```

- [ ] **Step 3: Run the server and exercise the API**

Run in background: `cd /home/darshit/Desktop/hthn && . .venv/bin/activate && uvicorn app:app --port 7860 > out/uvicorn.log 2>&1 &`
Then:
```bash
sleep 2 && curl -s localhost:7860/presets | head -c 200 && echo && \
curl -s -X POST localhost:7860/generate -H "Content-Type: application/json" -d '{"topics":["3 habits of calm people",""],"community":"motivation"}' && echo && \
sleep 5 && curl -s localhost:7860/jobs | python3 -c "import sys,json;[print(j['id'],j['status'],j['stage']) for j in json.load(sys.stdin)]"
```
Expected: presets JSON; `{"job_ids":["xxxxxxxx"]}` (one id, the blank line was skipped); a job in `running` with a stage name. Poll again after ~90 s: `done`.

- [ ] **Step 4: Check the page in a browser and screenshot for the deck**

Open `http://localhost:7860`. Enter two topics, pick a community, Generate. Confirm: two cards appear, progress bars animate, the first finishes with an inline player, "Copy post text" copies hook + caption + hashtags, download works. Take screenshots (form, in-progress batch, finished card) into `docs/screens/`. Stop the server with `kill %1` or `pkill -f "uvicorn app:app"`.

- [ ] **Step 5: Commit**

```bash
cd /home/darshit/Desktop/hthn && git add app.py static/index.html && git commit -m "feat: FastAPI job queue and single-page UI with batch mode

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 6: Dockerfile, README, deploy

**Files:**
- Create: `Dockerfile`, `README.md`

- [ ] **Step 1: Write `Dockerfile`**

```dockerfile
FROM python:3.11-slim
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg fonts-noto-core && rm -rf /var/lib/apt/lists/*
# Hugging Face Spaces run as uid 1000; own the app dir so out/ is writable
RUN useradd -m -u 1000 user
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
RUN mkdir -p out && chown -R user:user /app
USER user
EXPOSE 7860
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "7860"]
```

- [ ] **Step 2: Build and run the container locally**

Run:
```bash
cd /home/darshit/Desktop/hthn && docker build -q -t qvf . && docker run -d --rm --name qvf -p 7861:7860 --env-file .env qvf && sleep 3 && curl -s localhost:7861/presets | head -c 80 && echo && \
curl -s -X POST localhost:7861/generate -H "Content-Type: application/json" -d '{"topics":["why cats sleep so much"],"community":"general"}' && echo && sleep 120 && curl -s localhost:7861/jobs | python3 -c "import sys,json;j=json.load(sys.stdin)[0];print(j['status'],j.get('error'))"; docker logs qvf | tail -5; docker stop qvf
```
Expected: presets JSON, a job id, then `done None`. This proves ffmpeg, fonts, and file permissions inside the image.

- [ ] **Step 3: Write `README.md`**

```markdown
# Qoneqt Video Factory

Topic in, Qoneqt Global Feed short out. An LLM-powered pipeline that turns a topic, idea, or trend into a
publish-ready vertical video with AI script, AI voice, stock visuals, and word-pop captions. Built for the
Qoneqt × CTRL FREAK 2026 challenge ("Build an LLM-Powered Content Pipeline for Qoneqt").

- Live app: <HF Space URL>
- Demo video: <YouTube / Drive link>
- Published on Qoneqt Global Feed: <post URL>

## How it works

```
 topic + community preset
        │
        ▼
 ┌─────────────┐   Groq gpt-oss-120b (fallback: qwen, Gemini)
 │ 1. PLAN     │   3 scored hooks → best hook, 5-7 scenes (narration + stock query), caption, hashtags
 └──────┬──────┘
        ▼
 ┌─────────────┐   ElevenLabs (fallback: Gemini TTS, edge-tts), one wav per scene
 │ 2. VOICE    │
 └──────┬──────┘
        ▼
 ┌─────────────┐   Pexels (fallback: Pixabay, gradient card), one portrait clip per scene
 │ 3. VISUALS  │
 └──────┬──────┘
        ▼
 ┌─────────────┐   Groq Whisper word timestamps → ASS karaoke captions (active word in accent colour)
 │ 4. CAPTIONS │
 └──────┬──────┘
        ▼
 ┌─────────────┐   ffmpeg: cover-crop to 1080×1920, concat, voice, burn captions, thumbnail
 │ 5. RENDER   │
 └──────┬──────┘
        ▼
 out/<id>/<id>.mp4 + .jpg + .json (hook, caption, hashtags → "Copy post text")
```

Every stage has a fallback chain so a flaky free API never kills a job. One worker thread serialises jobs;
batch mode is simply N queued topics.

## Community presets

`presets.py` holds six presets (General, Tech & AI, Fitness, Motivation, Finance, Hinglish Fun). A preset
sets the script tone, language, narrator voice per engine, caption style, base hashtags, and the caption
accent colour. Adding a community is one dict entry.

## Run locally

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt          # needs ffmpeg on PATH
cp .env.example .env                     # fill in keys (all free tiers)
python pipeline.py "why sleep matters" tech   # end-to-end smoke test → out/<id>/<id>.mp4
uvicorn app:app --reload --port 7860     # UI at http://localhost:7860
python -m pytest -q                      # unit tests for plan validation and caption logic
```

Keys: Groq (console.groq.com), Gemini (aistudio.google.com), ElevenLabs (elevenlabs.io, free tier),
Pexels (pexels.com/api), Pixabay (pixabay.com/api/docs, optional).

## Deploy to Hugging Face Spaces

1. Create a Space, SDK = Docker, hardware = CPU basic (free).
2. Settings → Variables and secrets → add `GROQ_API_KEY`, `GEMINI_API_KEY`, `ELEVENLABS_API_KEY`, `PEXELS_API_KEY`, `PIXABAY_API_KEY`.
3. `git remote add hf https://huggingface.co/spaces/<user>/<space>` then `git push hf main`.
4. Open the Space URL. `out/` is ephemeral on the free tier; download videos you want to keep.

## Publish to Qoneqt

Qoneqt has no public posting API, so publishing is a manual step: click **Download mp4**, click
**Copy post text**, open qoneqt.com → Global Feed → new post (or Qlip), upload the video, paste the text.

## Repo layout

| File | Role |
|---|---|
| `llm.py` | plan stage, JSON validation, Groq → Gemini chain |
| `media.py` | voice chain, stock clip chain, Whisper word timings |
| `render.py` | ASS karaoke captions, ffmpeg composition, aspect-ratio knob |
| `pipeline.py` | orchestration + CLI smoke test |
| `app.py` | FastAPI job queue and API |
| `static/index.html` | single-page UI |
| `presets.py` | community presets |
| `tests/` | unit tests for pure logic |

## Known limits (deliberate)

In-memory job list and ephemeral output (fine for a demo; Redis + persistent volume if needed). One worker.
ElevenLabs free tier covers about 15 videos a month, after which Gemini TTS takes over automatically.
```

- [ ] **Step 4: Commit and push to GitHub**

```bash
cd /home/darshit/Desktop/hthn && git add Dockerfile README.md && git commit -m "feat: Dockerfile for HF Spaces and README

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
# user creates the public repo, then:
git remote add origin https://github.com/<user>/qoneqt-video-factory.git && git push -u origin main
```

- [ ] **Step 5: Deploy to Hugging Face Spaces**

User creates the Space (Docker SDK) and adds the five secrets. Then:
```bash
cd /home/darshit/Desktop/hthn && git remote add hf https://huggingface.co/spaces/<user>/qoneqt-video-factory && git push hf main
```
Wait for the build log to show `Uvicorn running`. Open the Space, generate one video, download it. Fill the three links at the top of the README, commit, push to both remotes.

---

## Self-review against the spec

- §4 five stages with fallbacks → Tasks 1-4. §4.1 contract and validation → Task 1. §4.2 presets → Task 0. §4.3 render spec → Task 3 (`W,H`, cover-crop, concat, subtitles, thumbnail, json). §5 layout → file map. §6 job model + endpoints → Task 5. §7 UI → Task 5. §8 failure handling → chains in Tasks 1-2, card fallback and Whisper fallback in Tasks 3-4, worker try/except in Task 5, Gemini mime handling in Task 2. §9 checks → tests in Tasks 1 and 3, self-checks in every module, smoke in Task 4. §10 deploy → Task 6. §11 deck is a separate follow-up after Task 5 screenshots (not code). §12 ponytail comments present in `media.py`, `render.py`, `pipeline.py`, `app.py`.
- Names used consistently: `plan`, `validate_plan`, `_parse`, `tts`, `duration`, `stock_clip`, `words`, `align`, `chunk`, `subtitles`, `card`, `compose`, `make_video`, `OUT`, `W`, `H`, `COMMUNITIES`.
- Output path: `out/<id>/<id>.mp4` (spec §4.3 said `id.mp4`; the per-job folder from §8 wins so partial files stay together). Served at `/out/<id>/<id>.mp4`.
