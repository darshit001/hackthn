# Competitor notes: text → reel projects (read 2 Oct 2026)

What the READMEs and code of similar projects actually do, plus what we can borrow.

## Open-source repos

### MoneyPrinterTurbo — https://github.com/harry0703/MoneyPrinterTurbo
- ~128k stars, MIT, Python, very active. The market leader.
- Topic → LLM script → search terms → stock (Pexels/Pixabay/local/AI video) → TTS → subtitles → BGM → MoviePy render.
- LLMs via litellm (OpenAI, Claude, Gemini, DeepSeek, Ollama…). TTS: Edge (free default), Azure, Gemini, ElevenLabs, Kokoro, voice cloning (VoxCPM).
- Captions: Edge-TTS word timestamps (free, fast) or faster-whisper. Subtitle font/pos/colour/outline/rounded bg configurable; `word_by_word` + `pop_spring` animation.
- Transitions: Shuffle, Fade, Slide, Zoom. BGM random/local/AI-generated with volume. Voice-rate. Preview voice before render.
- Batch via JSON manifest (100 tasks, continues on failure), `--stop-at` stage, multiple variants per topic, 9:16 / 16:9 / 1:1, direct publish to TikTok/IG/YT.
- UI: Streamlit + FastAPI + CLI + Docker + Colab.
- Weak: ad-heavy README, BGM ripped from YouTube, keyword-only stock matching (no relevance check), heavy.

### ShortGPT — https://github.com/RayVentura/ShortGPT
- ~8k stars, MIT, Python, stale since Feb 2025.
- Engines: short, long video, translation/dubbing (transcribe → translate → re-voice → caption), Reddit-story and facts templates.
- OpenAI-only LLM, ElevenLabs/EdgeTTS, Pexels + Bing images, whisper-timestamped captions, MoviePy. Gradio UI, Docker.
- Standout: "Editing Markup Language" (edit steps as LLM-readable JSON), watermark, YouTube metadata.
- Weak: unmaintained, OpenAI lock-in, torch + Docker heavy.

### OpenReels — https://github.com/tsensei/OpenReels
- ~206 stars, MIT, TypeScript (Remotion), v0.17.
- Research (web search) → Script ("DirectorScore" JSON with emotional arc) → TTS w/ word timestamps → visuals → music → captions → Remotion → **AI critic scores the video and re-runs below threshold**.
- **Vision-verified stock**: a VLM rejects off-topic stock clips and retries, then falls back to AI.
- 7 caption styles (spring-animated karaoke), 14 visual "archetypes" (anime, infographic, documentary, comic…), transitions (crossfade/slide/wipe/flip).
- Cost estimate + confirm before spending, actual cost after. `--dry-run`, `--score` replay saved plan without re-researching, `--direction` creative brief, `--platform` target.
- Web UI streams stages live with storyboard + gallery + cost breakdown.
- Weak: good visuals/music (Veo, Kling, Imagen, Lyria) are paid; Docker needs big shm.

### ai-shorts-generator — https://github.com/AbdullahNaveed/ai-shorts-generator
- 12 stars, MIT, Python, "weekend project".
- Topic/backlog → OpenAI JSON script → **semantic clip library: reuse a past clip if similar enough, else generate and store** → gpt-4o-mini-tts → faster-whisper captions → ffmpeg (Ken Burns, music ducking, watermark, outro).
- Flask review dashboard: approve/regenerate script with notes, swap clip per scene, choose music + volume, copy captions.
- Per-platform copy (YT title/desc, TikTok, X caption, hashtags). Writer persona presets. Branded 3 s outro with spoken CTA.
- Weak: OpenAI-dependent, no auto-post.

### SaarD00 AI-Youtube-Shorts-Generator — https://github.com/SaarD00/AI-Youtube-Shorts-Generator
- 231 stars, MIT, Python.
- Gemini picks a "trending" topic (actually invented, no real trends) → 8–9 scenes Hook → Context → Mechanism → Twist → Outro, each with `visual_1`, `visual_2`, `mood` → edge-tts → 2 Pexels clips per scene.
- Standout: **A/B split: two visuals per sentence, switching mid-sentence** for retention. Random `xfade` transitions. Mascot/avatar clip injected into a random scene. Prompt forces literal stock keywords.
- Weak: no captions, no music, no batch, fragile JSON.

### YumCut — https://github.com/IgorShadurin/app.yumcut.com
- 886 stars, **PolyForm Noncommercial**, TypeScript/Next.js full SaaS.
- Phased daemon: script → validate → audio → validate → Whisper → metadata → captions → images → video parts → main.
- Standout: `autoApproveScript` / `autoApproveAudio` (**approve gates before render**), multi-language versions of one project, templates (art + voice + music style), creation/avoidance guidance fields, ducked BGM, sparkles overlay, watermark, per-language subscribe CTA clip, lip-sync characters, scheduled YouTube auto-upload, bearer-key API with token-cost quote.
- Weak: very heavy (MySQL, RunPod, 3 extra repos), noncommercial licence.

### shortrocity — https://github.com/unconv/shortrocity
- 267 stars, no licence, Python, stale (2024).
- GPT-4 alternating `[image]` / `Narrator:` lines → ElevenLabs/OpenAI TTS → DALL-E 3 1024×1792 → OpenCV 1 s crossfades → Captacity karaoke captions.
- Standout: Whisper run **per sentence with the known text as prompt** → very accurate timings. JSON caption style file (font, stroke, highlight, shadow).
- Weak: all paid APIs, no Ken Burns, no music.

### auto-shorts — https://github.com/alamshafil/auto-shorts
- 336 stars, MIT, TS/npm, abandoned (learning project).
- Standout: **video-type templates**: TTS story, topic/facts, text-message story, quiz, would-you-rather, ranking. Zero-key local default (Ollama + system TTS). Edit JSON before render (`genVideoWithJson`). Background-video + music toggles.
- Weak: abandoned, LLM JSON breaks, heavy native deps.

### Prompt2Shorts — https://github.com/maheshpaulj/prompt2shorts
- 19 stars, MIT, Next.js. **Never compiles a final video** (still "future"). Keys exposed client-side. Nothing to borrow.

### AI_short_video_generator — https://github.com/kolligopinath/AI_short_video_generator
- 37 stars, no licence, abandoned 2023 prototype. davinci-003 + ElevenLabs + square DALL-E + MoviePy; hardcoded keys; no captions. Nothing to borrow.

### Unreal History Bot (youtube-shorts-generator) — https://github.com/poyrazemun/youtube-shorts-generator
- 8 stars, MIT, Python 3.12, CI, runs a real live channel, built with Claude Code.
- Claude generates 25 topics, **scores virality 1–10, keeps ≥7, dedupes vs past uploads**.
- **5 hook formulas** (SHOCKING_FACT, FALSE_ASSUMPTION…), bans "Did you know" / "In [year]" openers. **5-beat structure: hook, context, rehook, twist, loopable ending.** Per-beat shot types (wide, close-up, portrait…) so images differ.
- **Fact-check pass** (Haiku + DuckDuckGo) and **content-safety check** before spending on images.
- `--script-check` pause to hand-edit, `--manual-images`, 3 style presets, per-step caching/resume, `cost.json` ledger, `--dry-run`.
- YouTube Data API upload with real SRT caption track + es/pt/hi/id localized titles. **Analytics loop**: views by hook type feed the next topic prompt.
- Weak: static slideshow (no motion), single niche, CLI only.

### SamurAIGPT AI-Youtube-Shorts-Generator — https://github.com/SamurAIGPT/AI-Youtube-Shorts-Generator
- ~5.2k stars, MIT. Long video → clips (Opus Clip alternative), not text-to-video.
- Reusable ideas: each output gets **score + hook + one-line "why it works"**, editable virality rubric (hooks, emotional peaks, opinion bombs, revelations, quotables…), prompt tuned per content type, `--output-json`.

### Ryan Banze article — https://dev.to/ryanboscobanze/ai-powered-shorts-generator-building-automated-karaoke-style-video-pipelines-in-google-colab-480d
- Colab PoC. Footage first: Gemini Vision describes the clip → LLM writes narration to fit. **LLM picks the TTS voice by mood.** WhisperX karaoke. Edge → gTTS → pyttsx3 fallback.

## Commercial products

### HeyGen — https://www.heygen.com/en-au/tool/ai-reel-generator
- Prompt/script/blog/URL/PDF/audio → storyboard → style preset → refine with "editing prompts" → MP4.
- Avatars, voice clone, lip-sync dubbing in 175+ languages, **beat-synced cuts**, product-URL → reel, **batch variants for A/B testing hooks/CTAs**, platform safe zones.

### VEED — https://dhl.veed.io/tools/ai-video/ai-reel-generator
- Prompt or **suggested prompts** → **editable script** → pick avatar/voice/music/caption style → **swap footage per scene** → export. Brand kit (logo, colours). Faceless templates ("Did you know", tutorial, quotes).

### Vidu — https://www.vidu.com/ai-reel-generator
- Generative video model (text/image/reference → clip), trend animation templates. A clip generator, not a reel pipeline.

### Creatomate — https://creatomate.com/how-to/automate-faceless-instagram-reels
- Template with placeholders + bulk CSV / Zapier / Make / REST API. One design across all videos, animated word subtitles, posts to IG via Make.

### ReelsMakerAI — https://reelsmakerai.com (G2 page blocked)
- Prompt/script/URL → video. **"Automated series" with daily auto-posting** to YT/TikTok. Visual style presets (Realistic, Collage, Cinematic, Digital Art), 68+ voices, 50+ languages, viral subtitle styles, brand kits, consistent characters, free hashtag/thumbnail tools.

## What we already have (no need to copy)
Hook-first scripting with 3 scored hooks · Google Trends India topic ideas (real, unlike SaarD00) · EN/HI/Hinglish ·
community presets · karaoke captions via Whisper · AI stills with Ken Burns → stock → Wikimedia fallback · ducked BGM ·
Qoneqt end card · batch mode · fallback at every stage · per-scene credits · ₹0 running cost.
