import httpx
import pytest

from app.presets import with_keys


def _fail(code, body=""):
    req = httpx.Request("POST", "https://example.test")
    resp = httpx.Response(code, text=body, request=req)
    raise httpx.HTTPStatusError(f"HTTP {code}", request=req, response=resp)


def test_rotates_to_fallback_when_first_key_is_rejected(monkeypatch):
    monkeypatch.setenv("K", "dead")
    monkeypatch.setenv("K_2", "good")
    seen = []

    def call(key):
        seen.append(key)
        if key == "dead":
            _fail(401)
        return "ok"

    assert with_keys(call, "K") == "ok"
    assert seen == ["dead", "good"]


def test_rotates_on_a_400_that_blames_the_key(monkeypatch):
    """ElevenLabs answers a wrong-length key with 400 + authentication_error, not 401."""
    monkeypatch.setenv("K", "dead")
    monkeypatch.setenv("K_2", "good")

    def call(key):
        if key == "dead":
            _fail(400, '{"detail":{"type":"authentication_error","code":"invalid_api_key"}}')
        return "ok"

    assert with_keys(call, "K") == "ok"


def test_a_bad_request_raises_without_burning_the_fallback(monkeypatch):
    monkeypatch.setenv("K", "a")
    monkeypatch.setenv("K_2", "b")
    seen = []

    def call(key):
        seen.append(key)
        _fail(400, "'messages' must contain the word 'json'")

    with pytest.raises(httpx.HTTPStatusError):
        with_keys(call, "K")
    assert seen == ["a"]  # the second key is not spent on a request that is simply wrong


def test_paired_names_rotate_together_and_skip_half_set_tiers(monkeypatch):
    """Cloudflare's account id and token are one credential; a tier missing either half is not a candidate."""
    monkeypatch.setenv("ACC", "acc1")
    monkeypatch.setenv("TOK", "tok1")
    monkeypatch.setenv("ACC_2", "acc2")  # no TOK_2: incomplete, must be skipped
    monkeypatch.setenv("ACC_3", "acc3")
    monkeypatch.setenv("TOK_3", "tok3")
    seen = []

    def call(acc, tok):
        seen.append((acc, tok))
        if acc != "acc3":
            _fail(403)
        return "ok"

    assert with_keys(call, "ACC", "TOK") == "ok"
    assert seen == [("acc1", "tok1"), ("acc3", "tok3")]


def test_no_key_configured_names_the_variable(monkeypatch):
    monkeypatch.delenv("K", raising=False)
    monkeypatch.delenv("K_2", raising=False)
    with pytest.raises(RuntimeError, match="no K"):
        with_keys(lambda k: None, "K")


def test_a_hung_account_moves_on_only_when_asked(monkeypatch):
    """FLUX.2 hangs on one Cloudflare account while another answers (3 Oct 2026); elsewhere a timeout means the
    provider is slow, and the next engine is a better bet than the next key."""
    monkeypatch.setenv("K", "hung")
    monkeypatch.setenv("K_2", "good")

    def call(key):
        if key == "hung":
            raise httpx.ReadTimeout("The read operation timed out")
        return "ok"

    assert with_keys(call, "K", rotate_on_timeout=True) == "ok"
    with pytest.raises(httpx.ReadTimeout):
        with_keys(call, "K")
