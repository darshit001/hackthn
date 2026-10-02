from pathlib import Path

import media


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


def test_words_sends_the_script_as_whisper_prompt(monkeypatch, tmp_path):
    seen = {}

    class R:
        def raise_for_status(self):
            pass

        def json(self):
            return {"words": [{"word": " Hello ", "start": 0.1, "end": 0.4}, {"word": " ", "start": 0.4, "end": 0.4}]}

    monkeypatch.setattr(media.httpx, "post", lambda url, **kw: seen.update(kw) or R())
    monkeypatch.setenv("GROQ_API_KEY", "k")
    wav = tmp_path / "v.wav"
    wav.write_bytes(b"RIFF")
    assert media.words(wav, "hi", "नमस्ते दुनिया") == [{"word": "Hello", "start": 0.1, "end": 0.4}]
    assert seen["data"]["prompt"] == "नमस्ते दुनिया" and seen["data"]["language"] == "hi"
    media.words(wav, "en")
    assert "prompt" not in seen["data"]  # no script, no prompt
