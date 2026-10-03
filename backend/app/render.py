"""Stages 4-5: word-pop ASS captions and ffmpeg composition.
W, H is the single aspect-ratio knob for the whole project."""
import os
import subprocess
from pathlib import Path

from .presets import COMMUNITIES

W, H = 1080, 1920  # ponytail: one knob; set 1080, 1080 for a square feed variant
FONT = "Noto Sans"  # fontconfig substitutes (DejaVu Sans) when absent; Docker installs fonts-noto-core
OUTRO_SEC = 2.0  # branded end card; pipeline pads the voice track by the same amount so -shortest keeps lengths equal
VIOLET = "6B3DF0"  # Qoneqt brand violet, used by the outro and the UI
XFADE = os.environ.get("XFADE", "fade")  # ffmpeg xfade transition between scenes and into the end card; try "smoothleft"
XFADE_SEC = 0.35  # every scene clip runs this much past its voice line and crossfades over that overlap, so speech never shifts
# ffmpeg sizes its decoder, filter and x264 thread pools from the host's cores, which on a shared cloud box can
# be dozens; each thread holds 1080x1920 frames, so uncapped it blows a 1 GB container. Raise on a big laptop.
THREADS = os.environ.get("FFMPEG_THREADS", "2")


def _run(cmd, cwd=None):
    """Caps every thread pool: -filter_threads is global, -threads before each -i caps that input's decoder,
    and -threads before the output path (every call ends with it) caps the encoder."""
    capped = [cmd[0], "-filter_threads", THREADS]
    for arg in cmd[1:-1]:
        if arg == "-i":
            capped += ["-threads", THREADS]
        capped.append(arg)
    cmd = [*capped, "-threads", THREADS, cmd[-1]]
    r = subprocess.run(cmd, capture_output=True, text=True, cwd=cwd)
    if r.returncode:
        # a negative code is a signal: -9 with empty stderr means the kernel OOM-killed ffmpeg
        raise RuntimeError(f"ffmpeg exit {r.returncode}: {r.stderr.strip()[-400:]}")


def duration(path):
    """Seconds of media at path, via ffprobe."""
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
                         check=True, capture_output=True, text=True).stdout
    return float(out.strip())


MUSIC_GAIN = 0.22  # bed level before ducking; sidechaincompress pulls it down a further ~18 dB under speech


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


def ass_text(s):
    """User text -> safe ASS dialogue text: braces would open override blocks and a backslash would start a tag,
    so they become parens and a slash; newlines become hard breaks. ponytail: libass escape sequences vary by version."""
    return str(s).replace("\\", "/").replace("{", "(").replace("}", ")").replace("\n", "\\N")


OUTRO = f"{{\\fs140\\b1\\c{ass_color(VIOLET)}}}Qoneqt{{\\r}}\\NFollow for more"
FX = {"Hook": "{\\fad(200,200)}", "Title": "{\\fad(150,150)}", "Outro": "{\\fad(300,0)}"}


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


def chunk(words, size=3, max_gap=0.6):
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


def subtitles(words, community, out_ass, overlays=(), low=False):
    """Write an ASS file: one Dialogue per caption chunk with karaoke \\k per word so the active word lights up in the
    accent colour, plus overlays [(start, end, ass_text, style)] on layer 1: Hook (top), Title (upper third), Outro (centre).
    Everything on screen goes through libass so Devanagari shapes correctly and no extra ffmpeg pass is needed.
    low: captions near the bottom, under a talking presenter's chin instead of over the mouth."""
    accent = ass_color(COMMUNITIES[community]["accent"])
    fmt = ("Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, "
           "Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding")
    white, black, shadow = "&H00FFFFFF", "&H00000000", "&H80000000"
    lines = [
        "[Script Info]", "ScriptType: v4.00+", f"PlayResX: {W}", f"PlayResY: {H}", "WrapStyle: 0", "",
        "[V4+ Styles]", fmt,
        f"Style: Cap,{FONT},88,{accent},{white},{black},{shadow},-1,0,0,0,100,100,0,0,1,5,2,2,60,60,{int(H * (0.12 if low else 0.32))},1",
        f"Style: Hook,{FONT},84,{white},{white},{black},{shadow},-1,0,0,0,100,100,0,0,1,4,2,8,80,80,{int(H * 0.18)},1",
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


# Scene clips are intermediates that the xfade compose decodes all at once (one decoder per scene plus the end card).
# No B-frames and one reference frame keep each decoder's picture buffer tiny: 9 scenes peak at ~610 MB instead of ~910 MB.
INTERMEDIATE = ["-c:v", "libx264", "-preset", "veryfast", "-crf", "23", "-x264-params", "bframes=0:ref=1", "-pix_fmt", "yuv420p"]


def card(sec, out_mp4):
    """Fallback visual: slowly moving purple gradient. Captions carry the words."""
    _run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi",
          "-i", f"gradients=s={W}x{H}:c0=0x2A0E5C:c1=0x0B0416:speed=0.02:d={sec:.3f}",
          "-r", "30", *INTERMEDIATE, "-t", f"{sec:.3f}", str(out_mp4)])


def _scene_video(src, sec, dst, cwd):
    """Loop/trim a clip to `sec`, cover-scale and centre-crop to W×H, drop its audio."""
    _run(["ffmpeg", "-y", "-loglevel", "error", "-stream_loop", "-1", "-i", str(Path(src).resolve()), "-t", f"{sec:.3f}", "-an",
          "-vf", f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},fps=30,setsar=1", *INTERMEDIATE, dst], cwd=cwd)


def compose(scene_clips, voice_wav, ass, job_dir, out_id, music=None):
    """scene_clips: [(clip path or None, seconds)] in order. Each scene is rendered XFADE_SEC longer than its seconds and
    crossfades into the next (the last into the end card) over exactly that overlap, so the voice timeline, the captions
    and the total length (sum of seconds + OUTRO_SEC) are untouched. music: optional track path, looped under the voice
    and ducked while it speaks. Writes <job_dir>/<out_id>.mp4 and .jpg. Returns (mp4, jpg)."""
    job_dir = Path(job_dir)
    parts, offsets, t = [], [], 0.0
    for i, (clip, sec) in enumerate(scene_clips):
        dst = f"scene{i}.mp4"
        if clip is None:
            card(sec + XFADE_SEC, job_dir / dst)
        else:
            _scene_video(clip, sec + XFADE_SEC, dst, job_dir)
        parts.append(dst)
        t += sec
        offsets.append(t)  # the fade out of this scene starts where the next one's first word does
    card(OUTRO_SEC, job_dir / "outro.mp4")
    parts.append("outro.mp4")
    n = len(parts)
    cmd = ["ffmpeg", "-y", "-loglevel", "error"]
    for p in parts:
        cmd += ["-i", p]
    cmd += ["-i", str(Path(voice_wav).resolve())]
    # all clips come from the same encoder settings, but xfade insists on identical timebases and rates: say so
    graph = [f"[{k}:v]settb=AVTB,fps=30[s{k}]" for k in range(n)]
    prev = "s0"
    for k in range(1, n):
        graph.append(f"[{prev}][s{k}]xfade=transition={XFADE}:duration={XFADE_SEC}:offset={offsets[k - 1]:.3f}[x{k}]")
        prev = f"x{k}"
    graph.append(f"[{prev}]subtitles={Path(ass).name}[v]")
    maps = ["-map", "[v]"]
    if music:
        # audio only, so no frame memory: music looped, faded out at the end, compressed with the voice as sidechain, mixed
        total = duration(voice_wav)
        cmd += ["-stream_loop", "-1", "-i", str(Path(music).resolve())]
        graph += [f"[{n + 1}:a]volume={MUSIC_GAIN},afade=t=out:st={max(0.0, total - 1.5):.2f}:d=1.5[m]",
                  f"[{n}:a]asplit=2[a1][a2]",
                  "[m][a2]sidechaincompress=threshold=0.02:ratio=8:attack=20:release=400[md]",
                  "[a1][md]amix=inputs=2:duration=first:normalize=0[a]"]
        maps += ["-map", "[a]"]
    else:
        maps += ["-map", f"{n}:a"]
    mp4, jpg = job_dir / f"{out_id}.mp4", job_dir / f"{out_id}.jpg"
    cmd += ["-filter_complex", ";".join(graph), *maps, "-c:v", "libx264", "-preset", "veryfast", "-crf", "23", "-pix_fmt", "yuv420p",
            # -shortest makes ffmpeg 7 queue raw frames to line streams up, default 10 s (~930 MB at 1080x1920,
            # the Railway OOM kill); voice and scenes are cut to the same length, so 1 s gives identical output
            "-c:a", "aac", "-b:a", "128k", "-shortest", "-shortest_buf_duration", "1", "-movflags", "+faststart", mp4.name]
    _run(cmd, cwd=job_dir)
    _run(["ffmpeg", "-y", "-loglevel", "error", "-ss", "1", "-i", mp4.name, "-frames:v", "1", "-q:v", "3", jpg.name], cwd=job_dir)
    return mp4, jpg


if __name__ == "__main__":
    # Offline self-check: two gradient scenes, synthetic silence, fake word timings -> out/_selfcheck/sample.mp4
    d = Path("out/_selfcheck")
    d.mkdir(parents=True, exist_ok=True)
    timed = [{"word": w, "start": i * 0.4, "end": i * 0.4 + 0.35} for i, w in enumerate("word pop captions light up one at a time".split())]
    words = align(["word pop captions light up", "one at a time"], [(0, 2), (2, 4)], timed)
    overlays = [(0.0, 2.0, ass_text("Word-pop captions, now with a hook"), "Hook"), (2.0, 4.0, ass_text("Scene title card"), "Title"),
                (4.0, 4.0 + OUTRO_SEC, OUTRO, "Outro")]
    ass = subtitles(words, "general", d / "captions.ass", overlays)
    _run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono", "-t", f"{4 + OUTRO_SEC}", "-c:a", "pcm_s16le", "voice.wav"], cwd=d)
    track = Path("assets/music/Wallpaper.mp3")
    mp4, jpg = compose([(None, 2.0), (None, 2.0)], d / "voice.wav", ass, d, "sample", music=track if track.exists() else None)
    probe = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=codec_type,width,height", "-of", "csv=p=0", mp4],
                           capture_output=True, text=True, check=True).stdout
    print(probe.strip())
    assert f"video,{W},{H}" in probe and "audio" in probe, probe
    total = duration(mp4)
    assert abs(total - (4 + OUTRO_SEC)) < 0.2, f"xfade changed the length: {total}s"  # overlaps must eat exactly the added tails
    print(f"RENDER OK -> {mp4} {jpg}")
