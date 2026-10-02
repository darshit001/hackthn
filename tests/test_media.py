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
