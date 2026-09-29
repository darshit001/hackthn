# Qoneqt Video Factory — Design Spec

Date: 2026-09-29 · Status: approved by user in brainstorming session

## 1. Context

- Event: Qoneqt × CTRL FREAK 2026 (HackBriven). "Qoneqt AI Challenge — Part 2: Build an LLM-Powered Content Pipeline for Qoneqt."
- Brief: turn a topic / prompt / idea / trend into a ready-to-publish video for the Qoneqt Global Feed. LLM for hook, script, scene plan; multimodal / media tooling for visuals and video. Must be a repeatable pipeline, not one generation.
- Judging: "what you actually build and ship." Required: public GitHub repo, live deployment, demo video, at least one generated video published on the Global Feed.
- Round 2 (PPT, PDF ≤ 10 MB): due 30 Sep 2026 11:59 IST. Judged on innovation, feasibility, problem understanding, presentation.
- Round 3 (finale, live demo + Q&A): 4 Oct 2026, 8 h offline, Ahmedabad.
- Qoneqt facts (web research, 29 Sep): Global Feed is a public group at qoneqt.com/networks/global-feed; reels are called Qlips; no public posting API (publish is a manual upload); feed content is English and Hinglish; no official video spec published.

## 2. Goal and non-goals

Goal: a web app where a user enters one or many topics, picks a Qoneqt community preset, and gets back vertical short videos (1080×1920, 30–45 s) with AI script, AI voice, stock visuals, word-pop captions, and a ready-to-paste post caption + hashtags.

Non-goals (for this hackathon): automatic posting to Qoneqt (no API), user accounts, persistent job history, AI-generated video clips (paid), background-music licensing work, trend ingestion (may be added as a small "suggest topics" button only if time remains after 1 Oct).

## 3. Constraints

- Zero budget. Only free tiers: Groq (LLM, Whisper), ElevenLabs (voice, 10k chars/month ≈ 15 videos), Gemini (fallback voice, fallback LLM), Pexels / Pixabay (stock video), edge-tts (last-resort voice).
- Build window: tonight + tomorrow morning for demo + deck; 1–3 Oct for deploy polish.
- Host: Hugging Face Docker Space (free, 2 vCPU, ffmpeg allowed, no request timeout for background work). Port 7860.
- Stack: Python 3.11+, FastAPI, ffmpeg. Single HTML page, vanilla JS. No frontend build step.

## 4. Pipeline

One job = one topic + one community preset → one mp4. Five stages, sequential, run by one background worker thread.

| # | Stage | Input → Output | Primary | Fallback |
|---|---|---|---|---|
| 1 | Plan | topic, preset → Plan JSON | Groq `openai/gpt-oss-120b`, `reasoning_effort: low`, JSON mode | Groq `qwen/qwen3.8-27b`, then Gemini `gemini-3.5-flash-lite` |
| 2 | Voice | each scene narration → audio + duration | ElevenLabs `eleven_flash_v2_5`, premade voice from preset (only while the key is set and quota remains) | Gemini `gemini-3.8-flash-tts` (voice from preset, default Kore), then `edge-tts` |
| 3 | Visuals | each scene query + duration → mp4 clip | Pexels video search, portrait orientation | Pixabay, then ffmpeg gradient card with the scene text |
| 4 | Captions | concatenated voice wav → word timings → .ass | Groq `whisper-large-v3-turbo`, `timestamp_granularities[]=word` | Even word spacing across scene duration from script text |
| 5 | Render | clips + voice + .ass → mp4 + thumb.jpg + meta.json | ffmpeg | none (ffmpeg is local) |

Stage progress is written to the job record after each stage so the UI can show it.

### 4.1 Plan JSON contract

```json
{
  "hooks": [{"text": "...", "score": 8}, {"text": "...", "score": 6}, {"text": "...", "score": 9}],
  "hook": "the highest-scoring hook text",
  "scenes": [
    {"narration": "one or two sentences, max 25 words", "query": "2-4 English words for stock search"}
  ],
  "caption": "post text for Qoneqt, 1-3 lines, in preset language",
  "hashtags": ["#tag1", "#tag2"]
}
```

Validation (pure function, unit-tested): `hook` non-empty; 5 ≤ len(scenes) ≤ 7; each narration ≤ 25 words and non-empty; each query 1–4 words, ASCII; caption non-empty; 3 ≤ len(hashtags) ≤ 10, each starting with `#`. Scene 1 narration must begin with the hook text (LLM is instructed to do this). On failure: one retry with the validation error appended to the prompt; second failure → job fails at stage "plan".

### 4.2 Community presets (`presets.py`)

A dict keyed by slug. Fields: `label`, `tone` (one sentence injected into the prompt), `language` (`en` or `hinglish`), `voice_eleven` (premade voice id), `voice_gemini`, `voice_edge`, `caption_style` (one sentence), `hashtags` (base list, always appended). Initial set:

- `general` — Global Feed default, clear neutral English, curiosity hooks.
- `tech` — punchy, one concrete fact per scene, Hindi-free English.
- `fitness` — energetic, imperative, second person.
- `motivation` — warm, story-led, one takeaway line at the end.
- `finance` — plain-English money tips, numbers spelled clearly for TTS.
- `hinglish_fun` — Hinglish (Roman script), playful, Indian references; edge voice `en-IN-NeerjaNeural`.

Adding a preset = adding one dict entry. No code change elsewhere.

### 4.3 Render spec

- Canvas 1080×1920, 30 fps, H.264 (`libx264`, `-preset veryfast`, `-crf 23`), AAC 128k, `+faststart`.
- Per scene: input clip scaled to cover 1080×1920 then center-cropped; trimmed to the scene's voice duration + 0.15 s; if the clip is shorter it is looped (`-stream_loop -1`).
- Scenes concatenated (concat demuxer on pre-normalized intermediates). Voice track is the concatenation of scene wavs; each scene's clip duration equals its wav duration so audio and video stay aligned.
- Captions burned with `subtitles=captions.ass`. Style: Noto Sans Bold 72 px, white with 4 px dark outline, bottom-center alignment with `MarginV` ≈ 600 (text sits at about 65 % of height, above the app's UI overlay). Words grouped 3–4 per line; the active word is highlighted via ASS karaoke tags (`\k`) with the preset accent color.
- Thumbnail: frame at 1.0 s → `id.jpg`.
- `id.json` contains hook, caption, hashtags, scenes, durations, models used.
- Aspect ratio lives in one constant (`W, H = 1080, 1920`) so a square variant is a one-line change if Qoneqt prefers it.

## 5. Code layout

```
qoneqt-video-factory/
├── app.py             FastAPI app, job store, worker thread, static + /out serving
├── pipeline.py        make_video(topic, community, progress) → result dict; CLI smoke test
├── llm.py             plan(topic, preset) → dict; validate_plan(dict) → None | raises
├── media.py           tts(text, preset) → wav path; duration(path) → float; stock_clip(query, min_sec) → mp4 path | None; words(wav) → [{word,start,end}]
├── render.py          subtitles(words_per_scene, preset) → .ass path; compose(scene_clips, voice_wav, ass, out_id) → paths
├── presets.py         COMMUNITIES dict
├── static/index.html  single page UI
├── tests/test_llm.py  unit test for validate_plan (no network)
├── Dockerfile         python:3.11-slim + ffmpeg + fonts-noto-core
├── requirements.txt   fastapi, uvicorn[standard], groq, google-genai, edge-tts, httpx, python-dotenv
├── .env.example       GROQ_API_KEY= GEMINI_API_KEY= ELEVENLABS_API_KEY= PEXELS_API_KEY= PIXABAY_API_KEY=
├── .gitignore         .env, out/, __pycache__/, *.pyc, .venv/
└── README.md          what/why, architecture diagram, run locally, deploy to HF, publish to Qoneqt
```

Module rule: one public function per stage, everything else private. Each module has a `__main__` block that exercises it alone against the real API, so a stage can be debugged in isolation.

## 6. Job model and HTTP API

Job record (in-memory dict, keyed by 8-char id): `id, topic, community, status (queued|running|done|failed), stage (plan|voice|visuals|captions|render|null), created, result {video_url, thumb_url, hook, caption, hashtags} | null, error | null`.

- `GET /` → `static/index.html`
- `GET /presets` → `[{slug, label}]`
- `POST /generate` body `{topics: [str], community: str}` → `{job_ids: [str]}` (one job per non-empty topic line, max 10 per request)
- `GET /jobs` → all jobs, newest first (drives the batch view)
- `GET /jobs/{id}` → one job record
- `GET /out/{file}` → static files from `out/` (mp4, jpg, json)

Worker: a single `threading.Thread` consuming a `queue.Queue`. Serialises ffmpeg so two renders never fight for the Space's 2 vCPUs. Batch mode is simply N queued jobs.

## 7. UI (`static/index.html`)

One page, dark theme in Qoneqt's purple. Top: textarea (one topic per line), community `<select>` filled from `/presets`, Generate button. Below: a card per job showing topic, preset, stage progress (5 step dots), and when done: `<video>` player (9:16, max-height 70 vh), hook, caption, hashtags, and a "Copy post text" button (hook + caption + hashtags to clipboard) plus a Download link. Polls `/jobs` every 2 s while any job is queued or running. No framework, no build.

## 8. Failure handling

- Every network call: 60 s timeout (TTS 90 s), one retry with 2 s backoff, then next fallback in the chain. Chains are listed in §4.
- Plan validation failure: one guided retry, then job fails with the validation message.
- Visual fallback card is generated by ffmpeg (`color=` source + `drawtext` of the scene narration) so a render never blocks on stock availability.
- Caption fallback: if Whisper fails, word timings are synthesised by spreading the script words evenly across each scene's measured wav duration.
- Any uncaught exception marks the job `failed` with `stage` and `error` string; partial files remain in `out/<id>/` for debugging.
- ElevenLabs: any 401/402/429 (quota, blocked voice, missing permission) falls through to Gemini TTS silently; the job JSON records which engine spoke each scene.
- Gemini TTS response: honour `inlineData.mimeType`. If `audio/wav` write bytes as-is; if `audio/L16;rate=24000` wrap via ffmpeg (`-f s16le -ar 24000 -ac 1`).
- Secrets only via environment (`python-dotenv` loads `.env` locally; HF Space secrets in production). `.env` is gitignored.

## 9. Checks

- `tests/test_llm.py`: `validate_plan` accepts a good plan and rejects each violation (too few scenes, long narration, bad hashtag, non-ASCII query). Pure, no network. Run with `python -m pytest -q` or `python tests/test_llm.py`.
- Module self-checks: `python llm.py "why sleep matters" tech` prints a validated plan; `python media.py` synthesises one line, fetches one clip, transcribes; `python render.py` renders a 2-scene sample from fixtures in `out/`.
- End-to-end smoke: `python pipeline.py "why sleep matters" tech` must produce `out/<id>.mp4` that `ffprobe` reports as 1080×1920 with an audio stream and duration between 20 and 60 s. This runs before every deploy.

## 10. Deployment

- Local: `python -m venv .venv && . .venv/bin/activate && pip install -r requirements.txt && uvicorn app:app --reload`.
- Docker: `python:3.11-slim`, `apt-get install -y ffmpeg fonts-noto-core`, `EXPOSE 7860`, `CMD uvicorn app:app --host 0.0.0.0 --port 7860`.
- Hugging Face Space (SDK: Docker). Secrets: `GROQ_API_KEY`, `GEMINI_API_KEY`, `ELEVENLABS_API_KEY`, `PEXELS_API_KEY`, `PIXABAY_API_KEY`. One local repo, two remotes (`origin` = GitHub public, `hf` = Space).
- Publishing to Qoneqt: manual. Download mp4 from the app, upload as a Qlip/post in the Global Feed, paste the copied post text. README documents this with screenshots.

## 11. Deliverables and timeline

| When | Deliverable |
|---|---|
| Tonight (29 Sep) | `llm.py`, `media.py`, `render.py`, `pipeline.py`, tests, first real mp4 via the smoke command |
| 30 Sep 07:00–10:00 | `app.py`, `static/index.html`, local run, screenshots, 7-slide PDF deck (template from organiser email), submit before 11:59 IST |
| 1–3 Oct | HF Space live, GitHub public with README + architecture diagram, 2-min demo video, one video posted to Global Feed, batch and preset polish, optional "suggest topics" button |
| 4 Oct | Finale live demo |

Deck outline (7 slides, per organiser template): Title · Problem + gap · Solution · Architecture + stack · Key features (community presets, word-pop captions, batch mode, self-scored hooks, fallback chains) · Impact + feasibility (₹0 run cost on free tiers, ~30 videos/hour on Pexels limits) · Demo + conclusion.

## 12. Deliberate shortcuts (ponytail ledger)

Each is marked in code with a `# ponytail:` comment naming the ceiling and the upgrade path.

- In-memory job store, lost on restart → Redis or SQLite if history is ever needed.
- Ephemeral `out/` on the Space → HF persistent volume or S3 if videos must survive restarts.
- Single worker thread → per-job subprocess pool if a bigger Space is available.
- No background music → bundle one CC0 track and mix at −18 dB if time remains.
- No auth, no rate limiting on `/generate` beyond max 10 topics per request → acceptable for a demo URL shared with judges.

## 13. Open items

- Pexels API key (user to create at pexels.com/api). Pipeline falls back to gradient cards until then.
- Team name, team ID, college name for slide 1.
- Groq Orpheus TTS is optional; requires terms acceptance in the Groq console.
- Qoneqt video spec is unverified; 1080×1920 assumed, constant kept in one place.
