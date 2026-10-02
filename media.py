"""Stages 2-4 helpers.
tts:        ElevenLabs -> edge-tts -> Gemini TTS, normalised to 44.1 kHz mono wav (+0.2 s pad)
duration:   ffprobe seconds
gen_image:  Cloudflare Workers AI FLUX (CF_ACCOUNT_ID, CF_API_TOKEN) -> Together AI -> Hugging Face Inference (HF_TOKEN) -> None
stock_clip: AI image if given -> Pexels -> Pixabay -> Wikimedia Commons photo -> None; stills get a pan-zoom clip
words:      Groq Whisper word timings"""
import asyncio
import base64
import os
import re
import sys
import time
from pathlib import Path

import httpx
from dotenv import load_dotenv

from presets import COMMUNITIES, LANGUAGES
from render import H, W, XFADE_SEC, _run, duration  # noqa: F401  (duration re-exported: pipeline calls media.duration)

load_dotenv()
UA = {"User-Agent": "qoneqt-video-factory/1.0 (hackathon demo)"}  # Wikimedia refuses generic agents


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
    if r.status_code != 200:
        raise RuntimeError(f"HTTP {r.status_code} {' '.join(r.text.split())[:200]}")
    part = r.json()["candidates"][0]["content"]["parts"][0]["inlineData"]
    data = base64.b64decode(part["data"])
    if "wav" in part["mimeType"]:
        tmp.write_bytes(data)
    else:  # audio/L16;codec=pcm;rate=24000 -> wrap raw PCM
        raw = tmp.with_suffix(".pcm")
        raw.write_bytes(data)
        _run(["ffmpeg", "-y", "-loglevel", "error", "-f", "s16le", "-ar", "24000", "-ac", "1", "-i", str(raw), "-f", "wav", str(tmp)])


EDGE_RATE = "+12%"  # edge voices read a touch slow for shorts; measured pace lives in presets.LANGUAGES[lang]["wps"]


def _tts_edge(text, preset, tmp):
    import edge_tts
    asyncio.run(edge_tts.Communicate(text, preset["voice_edge"], rate=EDGE_RATE).save(str(tmp)))


# ponytail: Gemini TTS free tier is a handful of requests/day, so unlimited edge-tts goes before it
TTS_CHAIN = [("elevenlabs", _tts_eleven), ("edge", _tts_edge), ("gemini", _tts_gemini)]


def tts(text, community, out_wav, language="en"):
    """Synthesise text into a normalised wav at out_wav. Returns the engine name that spoke.
    The edge-tts voice comes from the language table (by the community's gender); ElevenLabs and Gemini voices are per community."""
    preset = dict(COMMUNITIES[community], voice_edge=LANGUAGES[language]["voice_edge"][COMMUNITIES[community]["gender"]])
    out_wav = Path(out_wav)
    errors = []
    for name, fn in TTS_CHAIN:
        tmp = out_wav.with_suffix(f".{name}.raw")
        for attempt in range(2):  # one retry per engine: edge-tts drops a request now and then, and a fallback engine means a second voice mid-video
            try:
                fn(text, preset, tmp)
                _normalize(tmp, out_wav)
                return name
            except Exception as e:  # the job json records which engine spoke
                msg = " ".join(str(e).split())[:160]
                errors.append(f"{name}: {msg}")
                print(f"tts[{name}] try {attempt + 1}: {type(e).__name__}: {msg}", file=sys.stderr)
                if re.search(r"\b4\d\d\b|no ELEVENLABS", msg):
                    break  # auth/quota: retrying the same engine will not help
                time.sleep(1)
    raise RuntimeError("all TTS engines failed: " + " | ".join(errors))


# ---------- visuals ----------

def _download(url, dst):
    with httpx.stream("GET", url, timeout=120, follow_redirects=True, headers=UA) as r:
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


HF_IMAGE_MODEL = os.environ.get("HF_IMAGE_MODEL", "black-forest-labs/FLUX.1-schnell")
IMAGE_SUFFIX = ". Vertical 9:16 composition, photographic, cinematic soft light, no text, no watermark, no logo"
_image_down = {}  # provider -> time it answered 401/402/403; skipped for DOWN_FOR seconds, not for the whole demo day
DOWN_FOR = 600


def _img_hf(prompt, out_png):
    token = os.environ.get("HF_TOKEN")
    if not token:
        raise RuntimeError("no HF_TOKEN")
    from huggingface_hub import InferenceClient
    InferenceClient(token=token, timeout=120).text_to_image(prompt, model=HF_IMAGE_MODEL, width=768, height=1344).save(out_png)
    return f"AI image, {HF_IMAGE_MODEL} via Hugging Face"


def _img_together(prompt, out_png):
    """Together AI's free FLUX.1-schnell tier (rate limited, no card). Untested here: no key on this machine."""
    key = os.environ.get("TOGETHER_API_KEY")
    if not key:
        raise RuntimeError("no TOGETHER_API_KEY")
    r = httpx.post("https://api.together.xyz/v1/images/generations", timeout=120,
                   headers={"Authorization": f"Bearer {key}"},
                   json={"model": "black-forest-labs/FLUX.1-schnell-Free", "prompt": prompt, "width": 720, "height": 1280,
                         "steps": 4, "n": 1, "response_format": "b64_json"})
    r.raise_for_status()
    Path(out_png).write_bytes(base64.b64decode(r.json()["data"][0]["b64_json"]))
    return "AI image, FLUX.1-schnell via Together AI"


def _img_cloudflare(prompt, out_png):
    """Cloudflare Workers AI FLUX.1-schnell (free 10k neurons/day, ~2-3 s an image, verified 2 Oct 2026).
    Square 1024 output; the Ken Burns cover-crop makes it 9:16."""
    acct, token = os.environ.get("CF_ACCOUNT_ID"), os.environ.get("CF_API_TOKEN")
    if not (acct and token):
        raise RuntimeError("no CF_ACCOUNT_ID/CF_API_TOKEN")
    r = httpx.post(f"https://api.cloudflare.com/client/v4/accounts/{acct}/ai/run/@cf/black-forest-labs/flux-1-schnell",
                   timeout=120, headers={"Authorization": f"Bearer {token}"}, json={"prompt": prompt, "steps": 4})
    r.raise_for_status()
    Path(out_png).write_bytes(base64.b64decode(r.json()["result"]["image"]))
    return "AI image, FLUX.1-schnell via Cloudflare Workers AI"


# ponytail: Cloudflare is the only keyed free tier verified working; the others are fallbacks that skip themselves without a key.
IMAGE_CHAIN = [("cloudflare", _img_cloudflare), ("together", _img_together), ("huggingface", _img_hf)]


def gen_image(prompt, out_png):
    """AI still for a scene. Cloudflare Workers AI FLUX first, then Together AI, then Hugging Face, and the whole chain
    a second time after a pause: most failures seen are transient 500s. Returns a credit line, or None. Never raises."""
    for attempt in range(2):
        for name, fn in IMAGE_CHAIN:
            if time.time() - _image_down.get(name, 0) < DOWN_FOR:
                continue
            try:
                return fn(prompt + IMAGE_SUFFIX, out_png)
            except Exception as e:
                msg = " ".join(str(e).split())
                # auth/quota trouble: rest the provider; a 429 from parallel scenes is left for the second pass
                if any(code in msg for code in ("401", "402", "403", "no HF_TOKEN", "no TOGETHER", "no CF_")):
                    _image_down[name] = time.time()
                print(f"image[{name}] try {attempt + 1} {prompt[:40]!r}: {type(e).__name__}: {msg[:140]}", file=sys.stderr)
        if all(time.time() - _image_down.get(n, 0) < DOWN_FOR for n, _ in IMAGE_CHAIN):
            break  # every provider is resting; no point pausing
        time.sleep(2)
    return None


WM_API = "https://commons.wikimedia.org/w/api.php"
NOT_PHOTO = ("internet archive", "scan", "illustration", "drawing", "engraving", "painting", "advertis", "poster", "map", "diagram", "logo", "clipart")


def _wikimedia(query, min_sec):
    """Wikimedia Commons photo search, no key. Tries the CC0 Unsplash mirror first, then the plain query,
    then relaxes it word by word. Returns (image url, credit line)."""
    words = query.split()
    # LLM queries end in the noun ("hand journal coffee"), so relax toward the tail; Unsplash mirror first at every step
    forms = [query] + ([" ".join(words[-2:])] if len(words) > 2 else []) + ([words[-1]] if len(words) > 1 else [])
    tries = [f"{f} unsplash" for f in forms] + forms[:1]
    for q in dict.fromkeys(tries):
        for attempt in range(2):
            r = httpx.get(WM_API, headers=UA, timeout=30, params={
                "action": "query", "generator": "search", "gsrsearch": f"filetype:bitmap {q}", "gsrnamespace": 6,
                "gsrlimit": 8, "prop": "imageinfo", "iiprop": "url|size|mime|extmetadata", "iiurlwidth": 1600, "format": "json"})
            if r.status_code == 429 and attempt == 0:
                time.sleep(6)  # Commons rate limit: back off once
                continue
            break
        r.raise_for_status()
        pages = sorted(r.json().get("query", {}).get("pages", {}).values(), key=lambda p: p.get("index", 99))
        for p in pages:
            ii = p["imageinfo"][0]
            if ii.get("mime") != "image/jpeg" or ii["width"] < 1000 or ii["height"] < 700:
                continue  # skip diagrams, icons, tiny scans
            em = ii.get("extmetadata", {})
            blob = " ".join(em.get(k, {}).get("value", "") for k in ("Artist", "Categories", "ObjectName", "ImageDescription")).lower()
            if any(t in blob for t in NOT_PHOTO):
                continue  # book scans, drawings, adverts: Commons has millions and they read as clip art
            artist = re.sub(r"<[^>]+>", "", em.get("Artist", {}).get("value", "")).strip() or "Wikimedia Commons"
            lic = em.get("LicenseShortName", {}).get("value", "")
            return ii.get("thumburl") or ii["url"], f"{artist} ({lic}) via Wikimedia Commons"
    raise LookupError(f"wikimedia: nothing for {query!r}")


def _still_to_clip(img, sec, out_mp4, zoom_in=True):
    """Photo -> W x H clip with a slow Ken Burns zoom so the scene moves."""
    n = max(2, int(round(sec * 30)))
    z = f"1+0.12*on/{n}" if zoom_in else f"1.12-0.12*on/{n}"
    big_w, big_h = int(W * 1.25), int(H * 1.25)  # zoom peaks at 1.12x, so 1.25x source stays sharp
    _run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(img), "-vf",
          f"scale={big_w}:{big_h}:force_original_aspect_ratio=increase,crop={big_w}:{big_h},"
          f"zoompan=z='{z}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={n}:s={W}x{H}:fps=30,format=yuv420p",
          "-frames:v", str(n), "-c:v", "libx264", "-preset", "veryfast", "-crf", "23", str(out_mp4)])


SPLIT_MIN_SEC = 4.0  # scenes at least this long cut from still A to still B halfway; set past 60 to switch the split off for a demo


def _split_clip(image, image_b, sec, out_mp4, zoom_in):
    """Two stills for one scene: A for the first half zooming one way, B for the rest (plus the crossfade tail) zooming
    the other, joined with a hard cut. The snap mid-sentence is what keeps thumbs still."""
    half = sec / 2
    a, b = out_mp4.with_name(f"{out_mp4.stem}a.mp4"), out_mp4.with_name(f"{out_mp4.stem}b.mp4")
    _still_to_clip(image, half, a, zoom_in=zoom_in)
    _still_to_clip(image_b, sec - half + XFADE_SEC, b, zoom_in=not zoom_in)
    lst = out_mp4.with_suffix(".txt")
    lst.write_text(f"file '{a.name}'\nfile '{b.name}'\n")
    # same encoder settings on both halves, so the concat demuxer joins them without a re-encode
    _run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", lst.name, "-c", "copy", out_mp4.name], cwd=out_mp4.parent)


def stock_clip(query, min_sec, out_mp4, image=None, credit=None, image_b=None):
    """Get one visual for the scene as an mp4 at out_mp4, min_sec plus the crossfade tail long. AI stills win when given:
    with two of them and a scene of SPLIT_MIN_SEC or more the clip cuts from image to image_b halfway through.
    Returns {'source': 'ai'|'pexels'|'pixabay'|'wikimedia', 'credit': str, 'split': bool}, or None when every source failed."""
    out_mp4 = Path(out_mp4)
    need = min_sec + XFADE_SEC  # the tail is what the crossfade into the next scene eats; a still must not loop back during it
    zoom_in = sum(map(ord, query)) % 2 == 0
    stills = [s for s in (image, image_b) if s]
    if len(stills) == 2 and min_sec >= SPLIT_MIN_SEC:
        try:
            _split_clip(stills[0], stills[1], min_sec, out_mp4, zoom_in)
            return {"source": "ai", "credit": credit or "AI image", "split": True}
        except Exception as e:
            print(f"a/b split failed for {query!r}: {e}", file=sys.stderr)
    if stills:
        try:
            _still_to_clip(stills[0], need, out_mp4, zoom_in=zoom_in)
            return {"source": "ai", "credit": credit or "AI image", "split": False}
        except Exception as e:
            print(f"ai still -> clip failed for {query!r}: {e}", file=sys.stderr)
    for name, fn in (("pexels", _pexels), ("pixabay", _pixabay)):
        try:
            _download(fn(query, need), out_mp4)
            return {"source": name, "credit": f"{name} stock video", "split": False}
        except Exception:
            continue
    for attempt in range(2):  # Commons occasionally times out; one retry rescues most scenes
        try:
            url, credit = _wikimedia(query, need)
            img = out_mp4.with_suffix(".jpg")
            _download(url, img)
            _still_to_clip(img, need, out_mp4, zoom_in=zoom_in)
            return {"source": "wikimedia", "credit": credit, "split": False}
        except Exception as e:
            print(f"wikimedia {query!r} attempt {attempt + 1}: {type(e).__name__}: {str(e)[:120]}", file=sys.stderr)
            time.sleep(2)
    return None  # ponytail: Commons video derivatives would be the next source to add


# ---------- captions ----------

def words(wav, language="en", prompt=""):
    """Word timings via Groq Whisper: [{'word','start','end'}, ...] in seconds. Telling Whisper the language
    stops it guessing wrong on short Hindi and Hinglish clips; giving it the spoken script as `prompt` keeps the
    script's spelling and names, so timings land on the right words."""
    data = {"model": "whisper-large-v3-turbo", "response_format": "verbose_json",
            "language": LANGUAGES[language]["whisper"], "timestamp_granularities[]": "word"}
    if prompt:
        data["prompt"] = prompt
    with open(wav, "rb") as f:
        r = httpx.post("https://api.groq.com/openai/v1/audio/transcriptions", timeout=120,
                       headers={"Authorization": f"Bearer {os.environ['GROQ_API_KEY']}"}, data=data,
                       files={"file": ("voice.wav", f, "audio/wav")})
    r.raise_for_status()
    return [{"word": w["word"].strip(), "start": float(w["start"]), "end": float(w["end"])}
            for w in r.json().get("words", []) if w["word"].strip()]


if __name__ == "__main__":
    # python media.py [community] [language]  -> voice + stock clip + whisper check (run with ELEVENLABS_API_KEY= to spare quota)
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
