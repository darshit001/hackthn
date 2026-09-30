"""Stages 4-5: word-pop ASS captions and ffmpeg composition.
W, H is the single aspect-ratio knob for the whole project."""
import os
import subprocess
from pathlib import Path

from presets import COMMUNITIES

W, H = 1080, 1920  # ponytail: one knob; set 1080, 1080 for a square feed variant
FONT = "Noto Sans"  # fontconfig substitutes (DejaVu Sans) when absent; Docker installs fonts-noto-core
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


def subtitles(words, community, out_ass):
    """Write an ASS file: one Dialogue per chunk, karaoke \\k per word so the active word lights up in the accent colour."""
    accent = ass_color(COMMUNITIES[community]["accent"])
    lines = [
        "[Script Info]", "ScriptType: v4.00+", f"PlayResX: {W}", f"PlayResY: {H}", "WrapStyle: 0", "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, "
        "Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
        f"Style: Cap,{FONT},88,{accent},&H00FFFFFF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,5,2,2,60,60,{int(H * 0.32)},1",
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
    _run(["ffmpeg", "-y", "-loglevel", "error", "-stream_loop", "-1", "-i", str(Path(src).resolve()), "-t", f"{sec:.3f}", "-an",
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
    _run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", "concat.txt", "-i", str(Path(voice_wav).resolve()),
          "-vf", f"subtitles={Path(ass).name}", "-c:v", "libx264", "-preset", "veryfast", "-crf", "23", "-pix_fmt", "yuv420p",
          # -shortest makes ffmpeg 7 queue raw frames to line streams up, default 10 s (~930 MB at 1080x1920,
          # the Railway OOM kill); voice and scenes are cut to the same length, so 1 s gives identical output
          "-c:a", "aac", "-b:a", "128k", "-shortest", "-shortest_buf_duration", "1", "-movflags", "+faststart",
          mp4.name], cwd=job_dir)
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
