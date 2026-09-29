---
title: Qoneqt Video Factory
emoji: 🎬
colorFrom: purple
colorTo: blue
sdk: docker
app_port: 7860
pinned: false
---

# Qoneqt Video Factory

Topic in, Qoneqt Global Feed short out. An LLM-powered pipeline that turns a topic, idea, or trend into a
publish-ready vertical video with AI script, AI voice, stock visuals, and word-pop captions. Built for the
Qoneqt × CTRL FREAK 2026 challenge ("Build an LLM-Powered Content Pipeline for Qoneqt").

- Live app: _coming soon_
- Demo video: _coming soon_
- Published on Qoneqt Global Feed: _coming soon_

## How it works

```
 topic + community preset
        │
        ▼
 ┌─────────────┐   Groq gpt-oss-120b (fallback: qwen, Gemini)
 │ 1. PLAN     │   3 scored hooks → best hook, 5-7 scenes (narration, stock query, image prompt), caption, hashtags
 └──────┬──────┘
        ▼
 ┌─────────────┐   Pollinations FLUX (keyed), fallback Hugging Face FLUX.1-schnell, one 9:16 still per scene
 │ 2. IMAGES   │   (skipped when no image provider is available; visuals then use stock photos)
 └──────┬──────┘
        ▼
 ┌─────────────┐   ElevenLabs (fallback: edge-tts, Gemini TTS), one wav per scene
 │ 3. VOICE    │
 └──────┬──────┘
        ▼
 ┌─────────────┐   AI still → Ken Burns clip; else Pexels/Pixabay clip if keyed; else Wikimedia Commons photo; else gradient card
 │ 4. VISUALS  │
 └──────┬──────┘
        ▼
 ┌─────────────┐   Groq Whisper word timestamps → ASS karaoke captions (active word in accent colour)
 │ 5. CAPTIONS │
 └──────┬──────┘
        ▼
 ┌─────────────┐   ffmpeg: cover-crop to 1080×1920, concat, voice, burn captions, thumbnail
 │ 6. RENDER   │
 └──────┬──────┘
        ▼
 out/<id>/<id>.mp4 + .jpg + .json (hook, caption, hashtags, per-scene credits → "Copy post text")
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
Pollinations (pollinations.ai, API key for FLUX stills), Hugging Face (huggingface.co/settings/tokens, fallback stills; needs "Make calls to Inference Providers").
Visuals need no key: Wikimedia Commons photos (CC licensed, credits recorded per scene in the job JSON).
Pexels and Pixabay keys are optional upgrades for real stock video (Pexels paused new keys in Sep 2026).

## Deploy to Hugging Face Spaces

1. Create a Space, SDK = Docker, hardware = CPU basic (free).
2. Settings → Variables and secrets → add `GROQ_API_KEY`, `GEMINI_API_KEY`, `ELEVENLABS_API_KEY`, `POLLINATIONS_API_KEY`, `HF_TOKEN`, and optionally `PEXELS_API_KEY`, `PIXABAY_API_KEY`.
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
ElevenLabs free tier covers about 20 videos a month, after which edge-tts takes over automatically.
