from pathlib import Path

from app import media


def test_gen_image_rests_provider_on_auth_but_retries_on_429(monkeypatch, tmp_path):
    calls = []

    def flaky(prompt, out):  # 429 once (parallel scenes bursting), then fine
        calls.append("flaky")
        if calls.count("flaky") == 1:
            raise RuntimeError("HTTP 429 Too Many Requests")
        return "AI image, test"

    def dead(prompt, out):
        calls.append("dead")
        raise RuntimeError("HTTP 402 Payment Required")

    monkeypatch.setattr(media, "IMAGE_CHAIN", [("dead", dead), ("flaky", flaky)])
    monkeypatch.setattr(media, "_image_down", {})
    monkeypatch.setattr(media.time, "sleep", lambda s: None)
    assert media.gen_image("a cat", tmp_path / "a.png") == "AI image, test"
    assert calls == ["dead", "flaky", "flaky"]  # dead rests after one 402; flaky gets its second pass
    assert media.gen_image("a dog", tmp_path / "b.png") == "AI image, test"
    assert calls[3:] == ["flaky"]  # the rested provider is skipped entirely within DOWN_FOR


def test_tts_retries_an_engine_once_before_falling_back(monkeypatch, tmp_path):
    calls = []

    def edge(text, preset, tmp):
        calls.append("edge")
        if calls.count("edge") == 1:
            raise RuntimeError("No audio was received")
        tmp.write_bytes(b"x")

    def quota(text, preset, tmp):
        calls.append("eleven")
        raise RuntimeError("HTTP 402 Payment Required")

    monkeypatch.setattr(media, "TTS_CHAIN", [("elevenlabs", quota), ("edge", edge)])
    monkeypatch.setattr(media, "_normalize", lambda src, dst: None)
    monkeypatch.setattr(media.time, "sleep", lambda s: None)
    assert media.tts("hello", "general", tmp_path / "v.wav", "en") == "edge"
    assert calls == ["eleven", "edge", "edge"]  # quota error is not retried; the edge hiccup is


def test_gujarati_skips_elevenlabs_and_speaks_as_dhwani(monkeypatch, tmp_path):
    calls = []

    def eleven(text, preset, tmp):
        calls.append("eleven")
        tmp.write_bytes(b"x")

    def edge(text, preset, tmp):
        calls.append(preset["voice_edge"])
        tmp.write_bytes(b"x")

    monkeypatch.setattr(media, "TTS_CHAIN", [("elevenlabs", eleven), ("edge", edge)])
    monkeypatch.setattr(media, "_normalize", lambda src, dst: None)
    assert media.tts("નમસ્તે", "finance", tmp_path / "v.wav", "gu") == "edge"  # finance is a male voice elsewhere
    assert calls == ["gu-IN-DhwaniNeural"]
    assert media.tts("hello", "finance", tmp_path / "e.wav", "en") == "elevenlabs"  # other languages keep ElevenLabs first


def test_words_sends_the_script_as_whisper_prompt(monkeypatch, tmp_path):
    seen = {}

    class R:
        def raise_for_status(self):
            pass

        def json(self):
            return {"words": [{"word": " Hello ", "start": 0.1, "end": 0.4}, {"word": " ", "start": 0.4, "end": 0.4}]}

    monkeypatch.setattr(media.httpx, "post", lambda url, **kw: seen.update(kw) or R())
    monkeypatch.setenv("GROQ_API_KEY", "k")
    monkeypatch.setattr(media, "_run", lambda cmd, cwd=None: Path(cmd[-1]).write_bytes(b"fLaC"))
    wav = tmp_path / "v.wav"
    wav.write_bytes(b"RIFF")
    assert media.words(wav, "hi", "नमस्ते दुनिया") == [{"word": "Hello", "start": 0.1, "end": 0.4}]
    assert seen["data"]["prompt"] == "नमस्ते दुनिया" and seen["data"]["language"] == "hi"
    media.words(wav, "en")
    assert "prompt" not in seen["data"]  # no script, no prompt


def test_stock_clip_cuts_between_two_stills_on_long_scenes(monkeypatch, tmp_path):
    made = []
    monkeypatch.setattr(media, "_still_to_clip", lambda img, sec, out, zoom_in=True: made.append((Path(img).name, round(sec, 3), Path(out).name, zoom_in)))
    monkeypatch.setattr(media, "_run", lambda cmd, cwd=None: made.append((cmd[-1], cwd)))
    zi = sum(map(ord, "city night")) % 2 == 0
    src = media.stock_clip("city night", 6.0, tmp_path / "clip2.mp4", image=tmp_path / "a.png", credit="AI image, test", image_b=tmp_path / "b.png")
    assert src == {"source": "ai", "credit": "AI image, test", "split": True}
    assert made[0] == ("a.png", 3.0, "clip2a.mp4", zi)  # A: first half, one zoom direction
    assert made[1] == ("b.png", round(3.0 + media.XFADE_SEC, 3), "clip2b.mp4", not zi)  # B: the rest plus the crossfade tail
    assert made[2] == ("clip2.mp4", tmp_path)  # the hard-cut join, run in the job dir so the list's relative names resolve
    assert (tmp_path / "clip2.txt").read_text() == "file 'clip2a.mp4'\nfile 'clip2b.mp4'\n"


def test_stock_clip_falls_back_to_one_still_when_the_split_fails(monkeypatch, tmp_path):
    made = []
    monkeypatch.setattr(media, "_split_clip", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("ffmpeg exit 1")))
    monkeypatch.setattr(media, "_still_to_clip", lambda img, sec, out, zoom_in=True: made.append((Path(img).name, round(sec, 3))))
    src = media.stock_clip("city night", 6.0, tmp_path / "clip1.mp4", image=tmp_path / "a.png", credit="AI image, test", image_b=tmp_path / "b.png")
    assert src["split"] is False and made == [("a.png", round(6.0 + media.XFADE_SEC, 3))]  # A alone, full length


def test_stock_clip_keeps_one_still_on_short_scenes(monkeypatch, tmp_path):
    made = []
    monkeypatch.setattr(media, "_still_to_clip", lambda img, sec, out, zoom_in=True: made.append((Path(img).name, round(sec, 3))))
    src = media.stock_clip("city night", 3.0, tmp_path / "clip0.mp4", image=tmp_path / "a.png", credit="AI image, test", image_b=tmp_path / "b.png")
    assert src["split"] is False and made == [("a.png", round(3.0 + media.XFADE_SEC, 3))]


def test_stock_clip_uses_b_alone_when_a_failed(monkeypatch, tmp_path):
    made = []
    monkeypatch.setattr(media, "_still_to_clip", lambda img, sec, out, zoom_in=True: made.append(Path(img).name))
    src = media.stock_clip("city night", 6.0, tmp_path / "clip0.mp4", image=None, credit="AI image, test", image_b=tmp_path / "b.png")
    assert src == {"source": "ai", "credit": "AI image, test", "split": False} and made == ["b.png"]


def test_gen_image_leads_with_the_look_and_keeps_the_common_suffix(monkeypatch, tmp_path):
    seen = []
    monkeypatch.setattr(media, "IMAGE_CHAIN", [("ok", lambda prompt, out: seen.append(prompt) or "AI image, test")])
    monkeypatch.setattr(media, "_image_down", {})
    media.gen_image("Wide shot: a cat on a roof", tmp_path / "a.png", style="anime")
    media.gen_image("Wide shot: a cat on a roof", tmp_path / "b.png")
    assert seen[0] == "Anime illustration, cel shading, vivid colours, clean line art. Wide shot: a cat on a roof" + media.IMAGE_SUFFIX
    assert seen[1].startswith("Photograph, cinematic soft light. Wide shot: a cat on a roof") and seen[1].endswith("no text, no watermark, no logo")


def _ff(*args):
    import subprocess
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", *map(str, args)], check=True)


def _probe(path):
    import subprocess
    return subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=width,height", "-of", "csv=p=0", path],
                          capture_output=True, text=True).stdout.strip()


def test_presenter_and_bubble_clips_fall_through_the_chain(monkeypatch, tmp_path):
    portrait, face, scene = tmp_path / "photo.png", tmp_path / "face.mp4", tmp_path / "clip1.mp4"
    _ff("-f", "lavfi", "-i", "color=c=orange:s=%dx%d" % media.PORTRAIT, "-frames:v", "1", portrait)
    head = media.head_png(portrait, tmp_path / "head.png")
    _ff("-f", "lavfi", "-i", "testsrc=s=512x512:r=25:d=1", "-pix_fmt", "yuv420p", face)
    calls = []

    def leap(p, w, sec):
        calls.append("leap")
        raise RuntimeError("You have exceeded your free ZeroGPU quota")

    def moda(p, w, sec):
        calls.append("moda")
        return str(face)

    monkeypatch.setattr(media, "FACE_CHAIN", [("leaptalk", "LeapTalk", leap), ("moda", "MoDA", moda)])
    monkeypatch.setattr(media, "_face_down", {})
    out = tmp_path / "clip0.mp4"
    assert media.presenter_clip(portrait, head, tmp_path / "v.wav", out, 1.0) == "moda"
    assert _probe(out) == f"{media.W},{media.H}"
    assert media.duration(out) >= 1.0 + media.XFADE_SEC - 0.05  # the last frame holds through the crossfade tail
    media._still_to_clip(portrait, 1.4, scene)
    assert media.bubble_clip(scene, head, tmp_path / "v.wav", 1.0) == "moda"
    assert _probe(scene) == f"{media.W},{media.H}"
    assert calls == ["leap", "moda", "moda"]  # the out-of-quota Space rests

    monkeypatch.setattr(media, "FACE_CHAIN", [("moda", "MoDA", leap)])
    monkeypatch.setattr(media, "_face_down", {})
    assert media.presenter_clip(portrait, head, tmp_path / "v.wav", out, 1.0) is None  # still portrait, zooming
    assert media.bubble_clip(scene, head, tmp_path / "v.wav", 1.0) is None  # still face in the bubble
    assert _probe(out) == _probe(scene) == f"{media.W},{media.H}"


def test_gen_image_puts_the_user_in_or_falls_back_to_plain_flux(monkeypatch, tmp_path):
    monkeypatch.setattr(media, "_image_down", {})
    monkeypatch.setattr(media, "IMAGE_CHAIN", [("plain", lambda p, o: "AI image, plain")])
    monkeypatch.setattr(media, "flux2", lambda p, ref, o: "flux-2-klein-9b")
    assert media.gen_image("a stadium", tmp_path / "a.png", ref=tmp_path / "ref.png") == "AI image with you, FLUX.2 klein-9b via Cloudflare Workers AI"
    assert media.gen_image("a stadium", tmp_path / "a.png") == "AI image, plain"  # no ref: no FLUX.2

    def quota(p, ref, o):
        raise RuntimeError("HTTP 429 neurons")
    monkeypatch.setattr(media, "flux2", quota)
    assert media.gen_image("a stadium", tmp_path / "a.png", ref=tmp_path / "ref.png") == "AI image, plain"
    assert "flux2" in media._image_down

    media._image_down.clear()  # a hung FLUX.2 rests too, or every scene after it waits out the timeout

    def hang(p, ref, o):
        raise TimeoutError("The read operation timed out")
    monkeypatch.setattr(media, "flux2", hang)
    assert media.gen_image("a stadium", tmp_path / "a.png", ref=tmp_path / "ref.png") == "AI image, plain"
    assert "flux2" in media._image_down


def test_space_call_rotates_tokens_on_quota_only(monkeypatch):
    import gradio_client
    seen = []

    class FakeJob:
        def __init__(self, token):
            self.token = token

        def result(self, timeout=None):
            if self.token != "t2":
                raise RuntimeError("You have exceeded your free ZeroGPU quota (180s requested vs. 87s left)")
            return {"video": "/tmp/v.mp4"}

    class FakeClient:
        def __init__(self, space, token=None, verbose=True):
            seen.append(token)
            self.token = token

        def submit(self, *args, api_name=None):
            return FakeJob(self.token)

    monkeypatch.setattr(gradio_client, "Client", FakeClient)
    monkeypatch.setenv("HF_TOKEN", "t1")
    monkeypatch.setenv("HF_TOKEN_2", "t2")
    monkeypatch.delenv("HF_TOKEN_3", raising=False)
    assert media._space_call("x/y", "/go", []) == "/tmp/v.mp4"
    assert seen == ["t1", "t2"]
