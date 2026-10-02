from fastapi.testclient import TestClient

import json

import app as appmod
import pipeline

client = TestClient(appmod.app)  # no `with`: lifespan (worker thread) is not started, which these tests do not need


def test_presets_has_three_lists():
    p = client.get("/presets").json()
    assert p["durations"] == [15, 30, 45, 60]
    assert {x["slug"] for x in p["languages"]} == {"en", "hi", "hinglish", "gu"}
    assert next(c for c in p["communities"] if c["slug"] == "hinglish_fun")["language"] == "hinglish"


def test_generate_rejects_bad_options():
    assert client.post("/generate", json={"topics": ["a"], "language": "fr"}).status_code == 400
    assert client.post("/generate", json={"topics": ["a"], "duration": 20}).status_code == 400
    assert client.post("/generate", json={"topics": ["a"], "community": "nope"}).status_code == 400


def test_generate_queues_job_with_options(monkeypatch):
    monkeypatch.setattr(appmod.Q, "put", lambda item: None)  # keep the job out of the (unstarted) worker queue
    r = client.post("/generate", json={"topics": ["chai vs coffee"], "community": "hinglish_fun", "language": "hinglish", "duration": 15})
    assert r.status_code == 200
    j = client.get(f"/jobs/{r.json()['job_ids'][0]}").json()
    assert (j["language"], j["duration"], j["status"]) == ("hinglish", 15, "queued")


def test_suggest_validates_and_proxies(monkeypatch):
    assert client.get("/suggest", params={"community": "x"}).status_code == 400
    monkeypatch.setattr(appmod.llm, "suggest", lambda c, l, t=False: {"topics": ["a", "b", "c"], "trends": []})
    assert client.get("/suggest", params={"community": "tech", "language": "hi"}).json()["topics"] == ["a", "b", "c"]

    def boom(c, l, t=False):
        raise RuntimeError("every model failed")
    monkeypatch.setattr(appmod.llm, "suggest", boom)
    assert client.get("/suggest").status_code == 503


def test_load_done_jobs_rebuilds_gallery(monkeypatch, tmp_path):
    d = tmp_path / "ab12cd34"
    d.mkdir()
    meta = {"id": "ab12cd34", "topic": "chai vs coffee", "community": "hinglish_fun", "language": "hinglish", "target": 15}
    (d / "ab12cd34.json").write_text(json.dumps(meta))
    (d / "ab12cd34.mp4").write_bytes(b"")
    (tmp_path / "_selfcheck").mkdir()
    (tmp_path / "_selfcheck" / "_selfcheck.json").write_text("{}")
    old = tmp_path / "99999999"  # a video from before language/duration existed, and one whose mp4 is gone
    old.mkdir()
    (old / "99999999.json").write_text(json.dumps({"id": "99999999", "topic": "old"}))
    monkeypatch.setattr(pipeline, "OUT", tmp_path)
    monkeypatch.setattr(appmod, "JOBS", {})
    appmod.load_done_jobs()
    assert set(appmod.JOBS) == {"ab12cd34"}
    j = appmod.JOBS["ab12cd34"]
    assert (j["status"], j["language"], j["duration"], j["result"]["topic"]) == ("done", "hinglish", 15, "chai vs coffee")


def good_plan():
    from tests.test_llm import good  # one schema fixture for the whole suite
    return dict(good(), model="test")


def test_plan_endpoint_and_plan_passthrough(monkeypatch):
    monkeypatch.setattr(appmod.llm, "plan", lambda t, c, l, d: dict(good_plan(), topic=t))
    assert client.post("/plan", json={"topic": "chai", "community": "tech", "language": "hi", "duration": 15}).json()["topic"] == "chai"
    assert client.post("/plan", json={"topic": "chai", "duration": 20}).status_code == 400
    queued = []
    monkeypatch.setattr(appmod.Q, "put", lambda item: queued.append(item))
    bad = good_plan(); bad.pop("posts")
    r = client.post("/generate", json={"topics": ["chai"], "plan": bad})
    assert r.status_code == 400 and "posts" in r.text
    r = client.post("/generate", json={"topics": ["chai"], "plan": good_plan()})
    jid = r.json()["job_ids"][0]
    assert appmod.JOBS[jid]["plan"]["hook"] == good_plan()["hook"] and queued[-1] == (jid, None)
    assert "plan" not in client.get("/jobs").json()[0]  # polling does not ship the plan blob
    r = client.post("/generate", json={"topics": ["a", "b"], "plan": good_plan()})  # batches ignore a plan
    assert all(appmod.JOBS[j]["plan"] is None for j in r.json()["job_ids"])


def test_redo_scene_queues_on_finished_job(monkeypatch):
    queued = []
    monkeypatch.setattr(appmod.Q, "put", lambda item: queued.append(item))
    assert client.post("/jobs/nope/redo/0").status_code == 404
    jid = client.post("/generate", json={"topics": ["x"]}).json()["job_ids"][0]
    assert client.post(f"/jobs/{jid}/redo/0").status_code == 409  # still queued
    appmod.JOBS[jid].update(status="done", result={"scenes": [{}, {}]})
    assert client.post(f"/jobs/{jid}/redo/2").status_code == 400
    assert client.post(f"/jobs/{jid}/redo/1").json() == {"job_id": jid, "scene": 1}
    assert appmod.JOBS[jid]["status"] == "queued" and queued[-1] == (jid, 1)
