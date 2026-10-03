import json
import subprocess

import pytest
from fastapi.testclient import TestClient

from app import llm, pipeline, render
from app import main as appmod
from app.presets import LANGUAGES

client = TestClient(appmod.app)


def post():
    return {"headline": "Your phone is slow for one reason", "image_prompt": "Close-up: a phone on a cafe table, soft window light",
            "query": "phone cafe table", "caption": "Background apps eat your RAM. Close them once a day.\nWhat slows yours?",
            "hashtags": ["#tech", "#phone", "#tips"], "alt": "A phone lying on a wooden cafe table."}


def test_validate_image_plan_accepts_a_good_post():
    llm.validate_image_plan(post())


@pytest.mark.parametrize("change, msg", [
    ({"headline": ""}, "headline missing"),
    ({"alt": None}, "alt missing"),
    ({"headline": "one"}, "3-8 words"),
    ({"headline": "Did you know phones get slow"}, "must not open"),
    ({"hashtags": ["#a", "b", "#c"]}, "hashtags"),
    ({"hashtags": ["#a"]}, "hashtags"),
])
def test_validate_image_plan_names_the_broken_rule(change, msg):
    with pytest.raises(ValueError, match=msg):
        llm.validate_image_plan({**post(), **change})


def test_validate_image_plan_wants_the_language_script():
    with pytest.raises(ValueError, match="script"):
        llm.validate_image_plan(post(), LANGUAGES["hi"]["script"])
    llm.validate_image_plan({**post(), "headline": "आपका फ़ोन धीमा क्यों है", "caption": "बैकग्राउंड ऐप्स बंद करें।"}, LANGUAGES["hi"]["script"])


def test_review_post_keeps_the_headline_and_takes_the_softened_caption(monkeypatch):
    seen = {}

    def fake_review(p, language):  # softens the first caption line only
        seen.update(hook=p["hook"], scenes=[sc["narration"] for sc in p["scenes"]])
        p["scenes"][1]["narration"] = "Closing apps may help a little."
        p["review"] = {"verdict": "fixed", "notes": ["softened"], "changed": 1}
        return p
    monkeypatch.setattr(llm, "review", fake_review)
    got = llm.review_post(post(), "en")
    assert seen == {"hook": post()["headline"], "scenes": [post()["headline"], *post()["caption"].split("\n")]}
    assert (got["headline"], got["caption"], got["review"]["verdict"]) == (
        post()["headline"], "Closing apps may help a little.\nWhat slows yours?", "fixed")  # the untouched line and the break stay


def test_poster_is_4_by_5_with_a_thumbnail(tmp_path):
    render.poster(None, "आपका फ़ोन धीमा क्यों है?", tmp_path / "a.png", tmp_path / "a.jpg")
    size = lambda f: subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=width,height", "-of", "csv=p=0", f],
                                    capture_output=True, text=True, check=True).stdout.strip()
    assert size(tmp_path / "a.png") == f"{render.PW},{render.PH}"
    assert size(tmp_path / "a.jpg") == "432,540"


def test_make_image_writes_the_post(monkeypatch, tmp_path):
    monkeypatch.setattr(pipeline, "OUT", tmp_path)
    monkeypatch.setattr(llm, "image_plan", lambda *a: dict(post(), model="test"))
    monkeypatch.setattr(llm, "review_post", lambda p, lang: dict(p, review={"verdict": "ok"}))
    monkeypatch.setattr(pipeline.media, "gen_image", lambda *a: None)  # every provider down
    monkeypatch.setattr(pipeline.media, "_wikimedia", lambda *a: (_ for _ in ()).throw(LookupError("none")))
    stages = []
    m = pipeline.make_image("slow phones", "tech", stages.append, job_id="ab12cd34")
    assert stages == pipeline.IMAGE_STAGES
    assert (m["kind"], m["visual"], m["hook"], m["image"]) == ("image", "card", post()["headline"], "/out/ab12cd34/ab12cd34.png")
    assert (tmp_path / "ab12cd34" / "ab12cd34.png").exists() and json.loads((tmp_path / "ab12cd34" / "ab12cd34.json").read_text())["alt"]


def test_generate_image_goes_on_the_image_queue(monkeypatch):
    videos, images = [], []
    monkeypatch.setattr(appmod.Q, "put", videos.append)
    monkeypatch.setattr(appmod.IQ, "put", images.append)
    assert client.post("/generate", json={"topics": ["a"], "kind": "gif"}).status_code == 400
    r = client.post("/generate", json={"topics": ["a", "b"], "kind": "image", "headline": False, "style": "anime"})
    ids = r.json()["job_ids"]
    assert [i for i, _ in images] == ids and not videos
    j = client.get(f"/jobs/{ids[0]}").json()
    assert (j["kind"], j["headline"], j["style"], j["status"]) == ("image", False, "anime", "queued")
    appmod.JOBS[ids[0]].update(status="done", result={"kind": "image"})
    assert client.post(f"/jobs/{ids[0]}/redo/1").status_code == 400  # an image post has one picture
    assert client.post(f"/jobs/{ids[0]}/redo/0").status_code == 200 and images[-1] == (ids[0], 0)


def test_load_done_jobs_picks_up_image_posts(monkeypatch, tmp_path):
    d = tmp_path / "ab12cd34"
    d.mkdir()
    (d / "ab12cd34.json").write_text(json.dumps({"id": "ab12cd34", "kind": "image", "topic": "t", "headline_on": False}))
    (d / "ab12cd34.png").write_bytes(b"")
    monkeypatch.setattr(pipeline, "OUT", tmp_path)
    monkeypatch.setattr(appmod, "JOBS", {})
    appmod.load_done_jobs()
    assert (appmod.JOBS["ab12cd34"]["kind"], appmod.JOBS["ab12cd34"]["headline"]) == ("image", False)
