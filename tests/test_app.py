from fastapi.testclient import TestClient

import app as appmod

client = TestClient(appmod.app)  # no `with`: lifespan (worker thread) is not started, which these tests do not need


def test_presets_has_three_lists():
    p = client.get("/presets").json()
    assert p["durations"] == [15, 30, 45, 60]
    assert {x["slug"] for x in p["languages"]} == {"en", "hi", "hinglish"}
    assert next(c for c in p["communities"] if c["slug"] == "hinglish_fun")["language"] == "hinglish"


def test_generate_rejects_bad_options():
    assert client.post("/generate", json={"topics": ["a"], "language": "fr"}).status_code == 400
    assert client.post("/generate", json={"topics": ["a"], "duration": 20}).status_code == 400
    assert client.post("/generate", json={"topics": ["a"], "community": "nope"}).status_code == 400


def test_generate_queues_job_with_options(monkeypatch):
    monkeypatch.setattr(appmod.Q, "put", lambda jid: None)  # keep the job out of the (unstarted) worker queue
    r = client.post("/generate", json={"topics": ["chai vs coffee"], "community": "hinglish_fun", "language": "hinglish", "duration": 15})
    assert r.status_code == 200
    j = client.get(f"/jobs/{r.json()['job_ids'][0]}").json()
    assert (j["language"], j["duration"], j["status"]) == ("hinglish", 15, "queued")


def test_suggest_validates_and_proxies(monkeypatch):
    assert client.get("/suggest", params={"community": "x"}).status_code == 400
    monkeypatch.setattr(appmod.llm, "suggest", lambda c, l: {"topics": ["a", "b", "c"], "trends": []})
    assert client.get("/suggest", params={"community": "tech", "language": "hi"}).json()["topics"] == ["a", "b", "c"]

    def boom(c, l):
        raise RuntimeError("every model failed")
    monkeypatch.setattr(appmod.llm, "suggest", boom)
    assert client.get("/suggest").status_code == 503
