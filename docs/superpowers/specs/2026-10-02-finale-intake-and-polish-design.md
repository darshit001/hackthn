# Finale upgrade: language, duration, trending suggestions, faster and never-blank videos

Date: 2026-10-02. Builds on `2026-09-29-qoneqt-video-factory-design.md`. Target: the 4 Oct 2026 finale live demo.

## Goal

Make the intake a real creative control panel (prompt + language + duration + suggested topics) and make
every produced video look finished (no blank scenes, hook title, branded outro) in about a third of today's
time. Zero added cost: every new call stays on the free tiers already in use.

## Scope

In: language selector (English, Hindi, Hinglish), duration chips (15/30/45/60 s), LLM topic suggestions fed
by Google Trends India, parallel image and voice generation, never-blank scenes, hook title overlay, 2 s
Qoneqt end card.

Out (later, separate specs): background music, script editing before render, URL-to-video, Gujarati.

## 1. UI and API

### Intake form (`static/index.html`), top to bottom

1. Topic textarea, one topic per line (unchanged).
2. Suggestions row: a `Suggest topics` button and up to 6 chips. Clicking a chip appends the text as a new
   line in the textarea unless that line is already present. Button text is `Thinking…` while loading, and
   the row shows `Could not fetch suggestions` on failure. Chips are cleared when community or language
   changes, so stale suggestions never linger; the user clicks the button again.
3. Community chips (unchanged). Selecting `Hinglish Fun` also selects the Hinglish language chip; the user
   may change it afterwards.
4. Language chips: English, हिन्दी, Hinglish. Default English.
5. Duration chips: 15 s, 30 s, 45 s, 60 s. Default 30.
6. Start button (unchanged).

Every chip row is built from `GET /presets`, so `presets.py` stays the single source of truth.

Job rows and done cards: the meta line reads `Tech, Hindi, 30 s`. `Try again` reuses community, language and
duration. The done card shows the actual spoken length as before.

### API (`app.py`)

- `GET /presets` → `{"communities": [{slug,label,language}], "languages": [{slug,label}], "durations": [15,30,45,60]}`.
- `POST /generate` body `{topics, community="general", language="en", duration=30}`. 400 when community or
  language is unknown or duration not in `DURATIONS`.
- `GET /suggest?community=tech&language=hi` → `{"topics": [str...], "trends": [str...]}`; 503 with a short
  message when every LLM fails. See section 4.
- Job dict and `out/<id>/<id>.json` carry `language` and `duration`.

## 2. Plan stage

### `presets.py`

New table:

```python
DURATIONS = [15, 30, 45, 60]
LANGUAGES = {
    "en":       dict(label="English",  whisper="en",
                     instruction="English",
                     voice_edge={"f": "en-IN-NeerjaNeural", "m": "en-IN-PrabhatNeural"}),
    "hi":       dict(label="हिन्दी",   whisper="hi",
                     instruction="Hindi in Devanagari script, simple everyday spoken Hindi; write every number as Hindi words",
                     voice_edge={"f": "hi-IN-SwaraNeural", "m": "hi-IN-MadhurNeural"}),
    "hinglish": dict(label="Hinglish", whisper="hi",
                     instruction="Hinglish written in Roman script (a natural mix of Hindi and English, the way young Indians text)",
                     voice_edge={"f": "en-IN-NeerjaNeural", "m": "en-IN-PrabhatNeural"}),
}
```

Communities drop `voice_edge` and gain `gender` (`"f"` for Sarah presets, `"m"` for George and Brian).
`language` stays on each community but now only means *default language chip* (`"hinglish"` on
`hinglish_fun`, `"en"` elsewhere); `GET /presets` passes it through so the UI can preselect the chip.
`voice_eleven` and `voice_gemini` stay per community: ElevenLabs `eleven_flash_v2_5` is multilingual, so the
same voice speaks Hindi. Caption `accent` per community is unchanged.

### `llm.plan(topic, community, language="en", duration=30)`

Budget derived from duration:

- `n = math.ceil(duration / 7); scenes_lo = max(3, n - 1); scenes_hi = min(9, n + 1)`
  → 15 s: 3-4, 30 s: 4-6, 45 s: 6-8, 60 s: 8-9.
- `words_lo, words_hi = round(duration * 2.4 * 0.85), round(duration * 2.4 * 1.15)`
  → 15 s: 31-41, 30 s: 61-83, 45 s: 92-124, 60 s: 122-166.
  Every window keeps the per-scene average under the existing 25-word cap (worst case 60 s at 8 scenes: 21).

Both live in one pure function `llm.budget(duration) -> (scenes_lo, scenes_hi, words_lo, words_hi)`.

`SYSTEM` becomes a template: `"{duration} second"`, `"{scenes_lo} to {scenes_hi} scenes"`,
`"{words_lo}-{words_hi} words"` replace the hard-coded 30-45 / 5-7 / 70-110. The language sentence comes
from `LANGUAGES[language]["instruction"]` and applies to narration, caption and scene titles; `query`
stays ASCII English because it is a stock-search string; hashtags may be in either script.

Each scene gains `"title": "..."`: a 2-5 word on-screen headline in the chosen language. It is drawn only
when a scene has no visual (section 3) and is validated as a non-empty string of at most 8 words.

`validate_plan(p, scenes=(5, 7))` takes the allowed scene range; everything else is unchanged. The word
total is not enforced (TTS pacing varies); the smoke test measures real spoken seconds instead, and the
measured pace lives in `LANGUAGES[lang]["wps"]` (2.4 for English, 1.9 for Hindi and Hinglish on 2 Oct 2026).

Pacing factor 2.4 words/s is a starting point for all three languages. The end-to-end smoke run per
language measures real spoken seconds; if a language is off by more than 20 % the factor moves into
`LANGUAGES[lang]["wps"]`.

### Whisper

`media.words(wav, language)` sends `language=LANGUAGES[language]["whisper"]`. Hinglish uses `hi`: Whisper
then transcribes in Devanagari and `render.align()` keeps the script's Roman spelling whenever the word
counts are within 2, which is the common case.

## 3. Production and render

### Parallel scenes (`pipeline.py`)

`concurrent.futures.ThreadPoolExecutor`, stdlib:

- Images stage: 3 workers, one `media.gen_image` per scene.
- Voice stage: 2 workers. The ElevenLabs free tier allows 2 concurrent requests; a third would 429 and that
  scene alone would fall back to edge-tts, giving one video two voices.
- Visuals stage stays sequential: it is ffmpeg CPU work on 2 vCPUs with threads already capped, and more
  processes would only add memory pressure under the 1 GB limit.

Each scene writes only its own files; `tts` and `gen_image` hold no shared state apart from the
`_image_down` set (adding to a set is atomic in CPython). `edge_tts` uses `asyncio.run` per call, which is
fine in a worker thread. `future.result()` re-raises in the pipeline thread, so a failed job still reports
its stage. Stage order and the six UI stations do not change.

Expected: images ~60 s → ~20 s, voice ~18 s → ~9 s; a video goes from ~3 min to ~1-1.5 min.

### Never-blank scenes

1. `media.gen_image` runs the Pollinations → Hugging Face chain twice with a 2 s pause before the second
   pass; most failures seen so far were transient 500s.
2. A scene with no AI image, no stock clip and no Wikimedia photo still gets the gradient `card()`, but its
   `title` is drawn over it in large bold type for the whole scene (see overlays).

### One overlay mechanism (`render.py`)

`subtitles(words, community, out_ass, overlays=())` where each overlay is `(start, end, text, style)`.
Three new ASS styles join `Cap`:

| Style | Look | Use |
|---|---|---|
| `Hook` | white, 72 px, bold, 4 px dark outline, Alignment 8 (top centre), MarginV = 0.18·H, `\fad(200,200)` | hook text on scene 1 from 0 to min(2.5 s, end of scene 1) |
| `Title` | accent colour, 96 px, bold, dark outline, Alignment 5 (centre), MarginV = 0.30·H | text-card scenes, full scene span |
| `Outro` | line 1 `Qoneqt` 140 px in violet `6B3DF0`, line 2 `Follow for more` 64 px white, Alignment 5, `\fad(300,0)` | the 2 s end card |

All on-screen text goes through libass instead of ffmpeg `drawtext` because libass shapes Devanagari
conjuncts correctly, and because it adds no ffmpeg pass: the existing `subtitles=` filter burns everything.
Texts are escaped for ASS (`{`, `}`, `\` and newlines) before writing.

### End card and audio padding

`compose()` appends a 2 s `card()` to the concat list. The voices concat in `pipeline.py` adds
`-af apad=pad_dur=2` (re-encoding PCM instead of `-c copy`), so the voice track is exactly as long as the
video, `-shortest` still matches lengths, and the OOM-safe `-shortest_buf_duration 1` stays valid.

`meta["duration"]` keeps meaning spoken seconds; the mp4 is that plus 2. The thumbnail at 1 s now carries
the hook title.

### Memory

No new ffmpeg filter touches full-resolution frame buffers; overlays ride the existing subtitles filter and
the end card is one more small concat input. Verified inside the Docker image with `--memory=1g`, per the
Railway lesson.

## 4. Suggestions and trends (`llm.py`, `app.py`)

`llm.trends()` fetches `https://trends.google.com/trending/rss?geo=IN` with the project `User-Agent`,
parses `<item><title>` with `xml.etree` (stdlib) and returns up to 10 titles. Cached in a module variable
for 10 minutes. Any failure returns `[]`. Verified 2 Oct 2026: no key needed, 10 items, titles in mixed
scripts (English, Hindi, Tamil, Malayalam).

`llm.suggest(community, language)` sends the same Groq → Gemini chain one JSON request:

- System: "You suggest short-video topics for the Qoneqt Global Feed." Return `{"topics": [6 strings]}`.
- User: community label and tone, language instruction, the trend titles. Rules: 3-4 topics inspired by
  trends that fit the community (skip trends that do not fit or are in a language other than English or the
  chosen one), the rest evergreen for the community; each topic 4-12 words, specific, in the chosen language;
  no hashtags, no numbering.
- Temperature 1.0 so repeated clicks give different lists. Validation: 3-8 non-empty strings, else one guided
  retry per model like `plan()`.

`GET /suggest` returns `{"topics": [...], "trends": [...]}`; when trends are empty the LLM simply gets no
trend list and the response says `"trends": []`. When every model fails: 503 `"suggestions unavailable"`.

## Error handling summary

| Failure | Behaviour |
|---|---|
| Trends RSS down | suggestions without trends |
| All LLMs down on suggest | 503, UI message, user types topics |
| Image chain fails twice | stock → Wikimedia → titled text card |
| One scene's TTS fails on every engine | job fails at `voice` (as today) |
| Whisper fails | even spacing (as today) |
| Bad duration / language in request | 400 |

## Testing

Unit (`tests/`), pure logic only, pytest:

- `validate_plan` honours the given scene range and the new `title` rule.
- `budget(duration)` returns the scene and word windows in the table above for all four durations.
- `subtitles()` writes `Hook`, `Title` and `Outro` dialogues at the right times and escapes ASS specials.
- `compose()` appends a 2 s card to the concat list (monkeypatched `_run`).
- `suggest` validation accepts 6 strings and rejects empty or non-list output.
- `app`: `/generate` rejects bad language/duration; `/presets` has the three keys (FastAPI `TestClient`).

Runnable checks, free-tier cost accepted:

- `python llm.py "chai vs coffee" hinglish_fun hinglish 15` prints a plan with 3 scenes and titles.
- `python pipeline.py "<topic>" <community> <language> <duration>` once per language at 15 s and once at 60 s
  English; the smoke asserts spoken duration within ±30 % of the target and video length = spoken + 2 s.
- Docker: `docker run --memory=1g` on a 60 s Hindi job completes with no OOM kill.
- Hindi captions and hook render as real Devanagari, checked by eye on an extracted frame.

## Files touched

`presets.py`, `llm.py`, `media.py`, `pipeline.py`, `render.py`, `app.py`, `static/index.html`,
`tests/test_llm.py`, `tests/test_render.py`, new `tests/test_app.py`, `README.md` (new options, Hindi).
No new dependencies, no Dockerfile change (fonts-noto-core already ships Noto Sans Devanagari).
