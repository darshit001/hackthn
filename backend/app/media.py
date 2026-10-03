"""Stages 2-4 helpers.
tts:        ElevenLabs -> edge-tts -> Gemini TTS, normalised to 44.1 kHz mono wav (+0.2 s pad)
duration:   ffprobe seconds
gen_image:  Cloudflare Workers AI FLUX (CF_ACCOUNT_ID, CF_API_TOKEN) -> Together AI -> Hugging Face Inference (HF_TOKEN) -> None
restyle:    the user's photo in better clothes and light (FLUX.2 klein, Cloudflare); gen_image(ref=) puts that person in a scene
presenter_clip / bubble_clip: that photo talking full-screen or in a bubble (LeapTalk -> MoDA, free ZeroGPU Spaces)
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

from .presets import COMMUNITIES, LANGUAGES, OUTFITS, STYLES, with_keys
from .render import H, INTERMEDIATE, W, XFADE_SEC, _run, duration  # noqa: F401  (duration re-exported: pipeline calls media.duration)

load_dotenv()
UA = {"User-Agent": "qoneqt-video-factory/1.0 (hackathon demo)"}  # Wikimedia refuses generic agents


def _normalize(src, dst):
    """Any audio -> 44.1 kHz mono s16 wav with 0.2 s trailing silence so scenes breathe."""
    _run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(src), "-af", "apad=pad_dur=0.2",
          "-ar", "44100", "-ac", "1", "-c:a", "pcm_s16le", str(dst)])


# ---------- voice ----------

def _tts_eleven(text, preset, tmp):
    def post(key):
        r = httpx.post(f"https://api.elevenlabs.io/v1/text-to-speech/{preset['voice_eleven']}",
                       params={"output_format": "mp3_44100_128"}, headers={"xi-api-key": key},
                       json={"text": text, "model_id": "eleven_flash_v2_5"}, timeout=90)
        r.raise_for_status()  # 401/402/429 (quota, blocked voice) -> next key, then the next engine
        return r.content

    tmp.write_bytes(with_keys(post, "ELEVENLABS_API_KEY"))


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
IMAGE_SUFFIX = ". Vertical 9:16 composition, no text, no watermark, no logo"  # the look (presets.STYLES) leads the prompt
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
    def post(acct, token):
        r = httpx.post(f"https://api.cloudflare.com/client/v4/accounts/{acct}/ai/run/@cf/black-forest-labs/flux-1-schnell",
                       timeout=120, headers={"Authorization": f"Bearer {token}"}, json={"prompt": prompt, "steps": 4})
        r.raise_for_status()
        return base64.b64decode(r.json()["result"]["image"])

    Path(out_png).write_bytes(with_keys(post, "CF_ACCOUNT_ID", "CF_API_TOKEN"))
    return "AI image, FLUX.1-schnell via Cloudflare Workers AI"


# ponytail: Cloudflare is the only keyed free tier verified working; the others are fallbacks that skip themselves without a key.
IMAGE_CHAIN = [("cloudflare", _img_cloudflare), ("together", _img_together), ("huggingface", _img_hf)]


def gen_image(prompt, out_png, style="photo", ref=None):
    """AI still for a scene in the given look (presets.STYLES). Cloudflare Workers AI FLUX first, then Together AI, then
    Hugging Face, and the whole chain a second time after a pause: most failures seen are transient 500s.
    ref: the user's restyled photo; FLUX.2 puts that person in the scene, and the plain chain is the fallback.
    Returns a credit line, or None. Never raises."""
    full = f"{STYLES[style][1]}. {prompt}{IMAGE_SUFFIX}"
    if ref and time.time() - _image_down.get("flux2", 0) >= DOWN_FOR:
        try:
            model = flux2(f"{STYLES[style][1]}. The person from image 0, with the same face, hair and outfit, is the main "
                          f"subject of this scene: {prompt}{IMAGE_SUFFIX}", ref, out_png)
            return f"AI image with you, FLUX.2 {model.split('-', 2)[2]} via Cloudflare Workers AI"
        except Exception as e:
            if any(code in str(e) for code in ("401", "402", "403", "429")):
                _image_down["flux2"] = time.time()
    for attempt in range(2):
        for name, fn in IMAGE_CHAIN:
            if time.time() - _image_down.get(name, 0) < DOWN_FOR:
                continue
            try:
                return fn(full, out_png)
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


SPLIT_MIN_SEC = 4.0  # scenes at least this long cut from still A to still B halfway (the second still is generated either way)


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


# ---------- you in the video ----------
# FLUX.2 klein on Cloudflare takes reference images under 512 px. Measured 3 Oct 2026: 9B ~10 s and keeps the face
# closest, but costs ~1,410 neurons a 9:16 image (7 a day on a free account); 4B costs ~160. So 9B restyles the user's
# photo once and 4B puts that person into the middle scenes' pictures.
# The talking face comes from free ZeroGPU Spaces (LeapTalk ~4 GPU-s a scene, then MoDA). A free account gets ~3.5
# GPU-minutes per rolling 24 h, so HF_TOKEN, _2, _3 rotate on a quota error, then one anonymous try.

RESTYLE_MODELS, SCENE_MODELS = ["flux-2-klein-9b", "flux-2-klein-4b"], ["flux-2-klein-4b"]
REF_SIDE = 512  # FLUX.2 refuses bigger references
PORTRAIT = (768, 1344)  # the presenter photo is 9:16; its top square (HEAD) holds the head and is what talks
FEATHER = 120  # px over which the talking square fades into the still portrait, so no seam shows
BUBBLE, BUBBLE_X, BUBBLE_Y, RING = 400, W - 400 - 56, 600, 10  # talking bubble over a middle scene, top right under the hook
_face_down = {}  # Space -> time every token was out of quota or the Space was down; skipped for DOWN_FOR seconds


def ref_png(src, out_png):
    _run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(src), "-vf",
          f"scale={REF_SIDE}:{REF_SIDE}:force_original_aspect_ratio=decrease", "-frames:v", "1", str(out_png)])
    return Path(out_png)


def head_png(portrait, out_png):
    w = PORTRAIT[0]
    _run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(portrait), "-vf", f"crop={w}:{w}:0:0", "-frames:v", "1", str(out_png)])
    return Path(out_png)


def flux2(prompt, ref, out_png, models=SCENE_MODELS):
    """FLUX.2 klein with `ref` as image 0, 9:16 out; each model in turn, keys rotating per model. Returns the model."""
    w, h = PORTRAIT
    err = None
    for model in models:
        def post(acct, token, model=model):
            r = httpx.post(f"https://api.cloudflare.com/client/v4/accounts/{acct}/ai/run/@cf/black-forest-labs/{model}",
                           timeout=120, headers={"Authorization": f"Bearer {token}"},
                           data={"prompt": prompt, "width": str(w), "height": str(h)},
                           files={"input_image_0": ("ref.png", Path(ref).read_bytes(), "image/png")})
            r.raise_for_status()
            return base64.b64decode(r.json()["result"]["image"])
        try:
            Path(out_png).write_bytes(with_keys(post, "CF_ACCOUNT_ID", "CF_API_TOKEN"))
            return model
        except Exception as e:
            err = e
            print(f"flux2[{model}]: {type(e).__name__}: {' '.join(str(e).split())[:140]}", file=sys.stderr)
    raise err


def restyle(portrait, outfit, out_png):
    """The user's photo with better clothes, posture, light and background; same face. Raises when FLUX.2 is down."""
    _, wear, place = OUTFITS[outfit]
    flux2(f"Photo of the same person from image 0: keep the face, hair, skin tone and age exactly the same. They wear {wear}, "
          f"stand upright with a relaxed confident posture and look at the camera. Waist-up vertical portrait, soft studio light, "
          f"{place} behind them with shallow depth of field, realistic photograph",
          ref_png(portrait, Path(out_png).with_name("restyle_ref.png")), out_png, RESTYLE_MODELS)
    return Path(out_png)


def _space_call(space, api_name, args):
    """Call a Gradio Space with each token in turn; a quota error moves to the next token, anything else raises.
    Returns the output video path."""
    from gradio_client import Client
    for token in _hf_tokens():
        try:
            out = Client(space, token=token, verbose=False).submit(*args, api_name=api_name).result(timeout=240)
        except Exception as e:
            if "quota" in str(e).lower():
                print(f"face[{space}] token {'anon' if token is None else token[:6]}: out of quota", file=sys.stderr)
                continue
            raise
        out = out[0] if isinstance(out, (list, tuple)) else out
        return out["video"] if isinstance(out, dict) else out
    raise RuntimeError(f"{space}: every token is out of ZeroGPU quota")


def _hf_tokens():
    return [t for t in (os.environ.get(n, "").strip() for n in ("HF_TOKEN", "HF_TOKEN_2", "HF_TOKEN_3")) if t] + [None]


def _leaptalk(head, wav, sec):
    if sec > 20:
        raise ValueError("LeapTalk takes at most 20 s of audio")
    from gradio_client import handle_file
    # auto_crop_face off: the clip must line up with the head square so it can be laid back onto the portrait
    return _space_call("hugging-apps/leaptalk-talking-head", "/generate",
                       [handle_file(str(head)), handle_file(str(wav)), min(20, int(sec) + 1), 1, 1.0, 42, False])


def _moda(head, wav, sec):
    from gradio_client import handle_file
    return _space_call("multimodalart/MoDA-fast-talking-head", "/generate_motion",
                       [handle_file(str(head)), handle_file(str(wav)), "Happiness", 1.2])


FACE_CHAIN = [("leaptalk", "LeapTalk", _leaptalk), ("moda", "MoDA", _moda)]


def talking(head, wav, sec):
    """(clip of the head square speaking wav, Space name), or (None, None) when every Space failed."""
    for name, _, fn in FACE_CHAIN:
        if time.time() - _face_down.get(name, 0) < DOWN_FOR:
            continue
        try:
            return fn(head, wav, sec), name
        except Exception as e:
            msg = " ".join(str(e).split())
            if any(w in msg.lower() for w in ("quota", "runtime_error", "paused")):
                _face_down[name] = time.time()
            print(f"face[{name}] {Path(wav).name}: {type(e).__name__}: {msg[:160]}", file=sys.stderr)
    return None, None


def _mask(path, w, h, lum):
    """A grey alpha mask drawn once with geq (white = opaque) and reused by every clip of the job."""
    if not Path(path).exists():
        _run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", f"color=c=black:s={w}x{h}", "-frames:v", "1",
              "-vf", f"format=gray,geq=lum='{lum}'", str(path)])
    return Path(path)


def presenter_clip(portrait, head, wav, out_mp4, sec):
    """Full-screen scene of the user talking: the head square speaks and is laid back onto the 9:16 portrait with
    feathered edges, so the outfit and background stay put. No Space available: a Ken Burns zoom on the portrait.
    Returns the Space name or None."""
    out_mp4, need = Path(out_mp4), sec + XFADE_SEC
    face, name = talking(head, wav, sec)
    if face is None:
        _still_to_clip(portrait, need, out_mp4)
        return None
    sq = round(PORTRAIT[0] * H / PORTRAIT[1])  # the head square once the portrait is stretched 1.6 % to fill W x H
    mask = _mask(out_mp4.parent / "feather.png", W, sq, f"255*clip(min(min(X,W-1-X),H-1-Y)/{FEATHER},0,1)")
    _run(["ffmpeg", "-y", "-loglevel", "error", "-loop", "1", "-i", str(portrait), "-i", str(face), "-loop", "1", "-i", str(mask),
          "-filter_complex",
          f"[0]scale={W}:{H},fps=30[bg];"
          f"[1:v]scale={W}:{sq},fps=30,tpad=stop_mode=clone:stop_duration={need:.3f}[f];"  # last frame holds through the crossfade tail
          f"[2]format=gray,scale={W}:{sq}[m];[f][m]alphamerge[fa];[bg][fa]overlay=0:0",
          "-t", f"{need:.3f}", "-an", *INTERMEDIATE, str(out_mp4)])
    return name


def bubble_clip(scene_mp4, head, wav, sec):
    """A round talking bubble of the user's face over a finished scene clip, rewritten in place. Every Space down:
    the bubble still shows the face, just not talking. Returns the Space name or None."""
    scene_mp4 = Path(scene_mp4)
    face, name = talking(head, wav, sec)
    inner = BUBBLE - 2 * RING
    mask = _mask(scene_mp4.parent / "circle.png", inner, inner, f"255*clip(({inner / 2}-hypot(X-{inner / 2},Y-{inner / 2}))*1.5,0,1)")
    ring = _mask(scene_mp4.parent / "ring.png", BUBBLE, BUBBLE, f"255*clip(({BUBBLE / 2}-hypot(X-{BUBBLE / 2},Y-{BUBBLE / 2}))*1.5,0,1)")
    src = ["-i", str(face)] if face else ["-loop", "1", "-i", str(head)]
    tmp = scene_mp4.with_name(scene_mp4.stem + "_bubble.mp4")
    _run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(scene_mp4), *src, "-loop", "1", "-i", str(mask), "-loop", "1", "-i", str(ring),
          "-filter_complex",
          # the face sits in the upper middle of the head square: a tighter crop fills the circle with it
          f"[1:v]crop=iw*0.62:iw*0.62:iw*0.19:ih*0.04,scale={inner}:{inner},fps=30,tpad=stop_mode=clone:stop_duration={sec + XFADE_SEC:.3f}[f];"
          f"[2]format=gray[m];[f][m]alphamerge[fc];"
          f"color=c=white:s={BUBBLE}x{BUBBLE}:r=30[w];[3]format=gray[rm];[w][rm]alphamerge[ring];"
          f"[0:v][ring]overlay={BUBBLE_X}:{BUBBLE_Y}:shortest=1[v1];[v1][fc]overlay={BUBBLE_X + RING}:{BUBBLE_Y + RING}:shortest=1",
          "-an", *INTERMEDIATE, str(tmp)])
    tmp.replace(scene_mp4)
    return name


# ---------- captions ----------

def words(wav, language="en", prompt=""):
    """Word timings via Groq Whisper: [{'word','start','end'}, ...] in seconds. Telling Whisper the language
    stops it guessing wrong on short Hindi and Hinglish clips; giving it the spoken script as `prompt` keeps the
    script's spelling and names, so timings land on the right words."""
    data = {"model": "whisper-large-v3-turbo", "response_format": "verbose_json",
            "language": LANGUAGES[language]["whisper"], "timestamp_granularities[]": "word"}
    if prompt:
        data["prompt"] = prompt
    def post(key):
        with open(wav, "rb") as f:  # reopened per key: a retried upload needs the file back at the start
            r = httpx.post("https://api.groq.com/openai/v1/audio/transcriptions", timeout=120,
                           headers={"Authorization": f"Bearer {key}"}, data=data,
                           files={"file": ("voice.wav", f, "audio/wav")})
        r.raise_for_status()
        return r.json()

    return [{"word": w["word"].strip(), "start": float(w["start"]), "end": float(w["end"])}
            for w in with_keys(post, "GROQ_API_KEY").get("words", []) if w["word"].strip()]


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
