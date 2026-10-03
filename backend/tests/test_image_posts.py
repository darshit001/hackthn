import json
import subprocess

import pytest
from fastapi.testclient import TestClient

from app import llm, pipeline, render
from app import main as appmod
from app.presets import LANGUAGES

client = TestClient(appmod.app)


CAPTION = ("Your phone is not old, it is just carrying too much in the background.\n"
           "📱 Apps you never open still refresh, sync and use memory all day.\n"
           "🧹 Clear the app cache once a week from Settings, Storage.\n"
           "🔋 Turn off background refresh for apps that do not need it.\n"
           "Which app do you think slows your phone the most?\n"
           "Follow for more phone tips like this")
HI_CAPTION = ("फ़ोन पुराना नहीं, बस पीछे बहुत कुछ चल रहा है।\n📱 जो ऐप्स आप नहीं खोलते, वे भी पूरे दिन मेमोरी लेते हैं।\n"
              "🧹 हफ़्ते में एक बार सेटिंग्स में जाकर कैश साफ़ करें।\n🔋 ज़रूरत न हो तो बैकग्राउंड रिफ़्रेश बंद करें।\n"
              "आपका फ़ोन कौन सा ऐप धीमा करता है?\nऐसी और टेक टिप्स के लिए फ़ॉलो करें")


def post():
    return {"headline": "Your phone is slow for one reason", "image_prompt": "Close-up: a phone on a cafe table, soft window light",
            "query": "phone cafe table", "caption": CAPTION,
            "hashtags": ["#tech", "#phone", "#tips"], "alt": "A phone lying on a wooden cafe table."}


def planned(n=1):
    """What llm.image_plan returns: a single picture, or an n-slide carousel."""
    if n == 1:
        return dict(post(), slides=[{"text": post()["headline"], "image_prompt": post()["image_prompt"]}], look="", model="test")
    texts = ["Your phone is slow for one reason"] + [f"Point {i} is about phones and it leads on to the next one" for i in range(2, n + 1)]
    return dict(post(), headline=texts[0], look="Same young woman, same cafe, warm window light",
                slides=[{"text": t, "image_prompt": f"Close-up {i}"} for i, t in enumerate(texts)], model="test")


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
    llm.validate_image_plan({**post(), "headline": "आपका फ़ोन धीमा क्यों है", "caption": HI_CAPTION}, LANGUAGES["hi"]["script"])


def test_review_post_keeps_the_headline_and_takes_the_softened_caption(monkeypatch):
    seen = {}

    def fake_review(p, language):  # softens the second slide and the first caption line
        seen.update(hook=p["hook"], scenes=[sc["narration"] for sc in p["scenes"]])
        p["scenes"][1]["narration"] = "Point 2 may matter a little."
        p["scenes"][3]["narration"] = "Closing apps may help a little."
        p["review"] = {"verdict": "fixed", "notes": ["softened"], "changed": 2}
        return p
    monkeypatch.setattr(llm, "review", fake_review)
    p = planned(3)
    texts = [x["text"] for x in p["slides"]]
    got = llm.review_post(p, "en")
    assert seen == {"hook": texts[0], "scenes": [*texts, *post()["caption"].split("\n")]}
    assert [x["text"] for x in got["slides"]] == [texts[0], "Point 2 may matter a little.", texts[2]]
    assert (got["caption"], got["review"]["verdict"]) == (  # the untouched lines and the breaks stay
        "\n".join(["Closing apps may help a little.", *CAPTION.split("\n")[1:]]), "fixed")


def test_poster_is_4_by_5_with_a_thumbnail(tmp_path):
    render.poster(None, "आपका फ़ोन धीमा क्यों है?", tmp_path / "a.png", tmp_path / "a.jpg")
    size = lambda f: subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=width,height", "-of", "csv=p=0", f],
                                    capture_output=True, text=True, check=True).stdout.strip()
    assert size(tmp_path / "a.png") == f"{render.PW},{render.PH}"
    assert size(tmp_path / "a.jpg") == "432,540"


def test_make_image_writes_the_post(monkeypatch, tmp_path):
    monkeypatch.setattr(pipeline, "OUT", tmp_path)
    monkeypatch.setattr(llm, "image_plan", lambda *a: planned())
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


def carousel(**change):
    return {"look": "Same young woman, same cafe, warm window light", "query": "phone cafe", "caption": CAPTION,
            "alt": "A woman with a phone.", "hashtags": ["#a", "#b", "#c"],
            "slides": [{"text": "Your phone is slow for one reason", "image_prompt": "Close-up of a phone"},
                       {"text": "Background apps keep running and eat memory, and that is only half of it", "image_prompt": "Wide shot"}],
            **change}


def test_validate_carousel_plan():
    llm.validate_carousel_plan(carousel(), 2)
    with pytest.raises(ValueError, match="exactly 3"):
        llm.validate_carousel_plan(carousel(), 3)
    with pytest.raises(ValueError, match="look missing"):
        llm.validate_carousel_plan(carousel(look=""), 2)
    with pytest.raises(ValueError, match="slide 2: text and image_prompt"):
        llm.validate_carousel_plan(carousel(slides=[carousel()["slides"][0], {"text": "x"}]), 2)
    with pytest.raises(ValueError, match="slide 1: text must be 3-8"):
        llm.validate_carousel_plan(carousel(slides=[{"text": " ".join(["word"] * 12), "image_prompt": "p"}, carousel()["slides"][1]]), 2)
    with pytest.raises(ValueError, match="script"):
        llm.validate_carousel_plan(carousel(), 2, LANGUAGES["hi"]["script"])


def test_make_image_carousel_and_redo_one_slide(monkeypatch, tmp_path):
    import zipfile
    monkeypatch.setattr(pipeline, "OUT", tmp_path)
    monkeypatch.setattr(llm, "image_plan", lambda *a: planned(3))
    monkeypatch.setattr(llm, "review_post", lambda p, lang: dict(p, review={"verdict": "ok"}))
    prompts = []
    monkeypatch.setattr(pipeline.media, "gen_image", lambda prompt, *a: prompts.append(prompt))  # no AI picture: plain cards
    monkeypatch.setattr(pipeline.media, "_wikimedia", lambda *a: (_ for _ in ()).throw(LookupError("none")))
    m = pipeline.make_image("slow phones", "tech", job_id="ab12cd34", slides=3)
    d = tmp_path / "ab12cd34"
    assert sorted(prompts) == [f"Same young woman, same cafe, warm window light. Close-up {i}" for i in range(3)]  # every slide leads with the look
    assert [x["image"] for x in m["slides"]] == [f"/out/ab12cd34/ab12cd34-{i}.png" for i in (1, 2, 3)]
    assert (m["image"], m["zip"], m["thumb"]) == ("/out/ab12cd34/ab12cd34-1.png", "/out/ab12cd34/ab12cd34.zip", "/out/ab12cd34/ab12cd34.jpg")
    assert zipfile.ZipFile(d / "ab12cd34.zip").namelist() == [f"ab12cd34-{i}.png" for i in (1, 2, 3)]
    assert "2/3 →" in (d / "ab12cd34-2.ass").read_text() and "→" not in (d / "ab12cd34-3.ass").read_text().split("Mark,,0,0,0,,")[-1]
    before = (d / "ab12cd34-1.png").stat().st_mtime_ns
    prompts.clear()
    m2 = pipeline.redo_image("ab12cd34", slide=1)
    assert len(prompts) == 1 and prompts[0].startswith("Same young woman, same cafe, warm window light. Close-up 1 (take ")
    assert (d / "ab12cd34-1.png").stat().st_mtime_ns == before and m2["updated"]  # the other slides are left alone


def test_generate_carousel_options(monkeypatch):
    images = []
    monkeypatch.setattr(appmod.IQ, "put", images.append)
    assert client.post("/generate", json={"topics": ["a"], "kind": "image", "slides": 5}).status_code == 422
    jid = client.post("/generate", json={"topics": ["a"], "kind": "image", "slides": 3}).json()["job_ids"][0]
    assert appmod.JOBS[jid]["slides"] == 3
    appmod.JOBS[jid].update(status="done", result={"kind": "image", "slides": [{}, {}, {}]})
    assert client.post(f"/jobs/{jid}/redo/3").status_code == 400
    assert client.post(f"/jobs/{jid}/redo/2").status_code == 200 and images[-1] == (jid, 2)


def test_load_done_jobs_picks_up_a_carousel(monkeypatch, tmp_path):
    d = tmp_path / "ab12cd34"
    d.mkdir()
    (d / "ab12cd34.json").write_text(json.dumps({"id": "ab12cd34", "kind": "image", "topic": "t", "slides": [{}, {}]}))
    (d / "ab12cd34.zip").write_bytes(b"")
    monkeypatch.setattr(pipeline, "OUT", tmp_path)
    monkeypatch.setattr(appmod, "JOBS", {})
    appmod.load_done_jobs()
    assert appmod.JOBS["ab12cd34"]["slides"] == 2


def test_a_thin_caption_is_sent_back():
    with pytest.raises(ValueError, match="5-8 lines"):
        llm.validate_image_plan({**post(), "caption": "Close apps.\nWhat slows yours?"})
    with pytest.raises(ValueError, match="at least 40 words"):
        llm.validate_image_plan({**post(), "caption": "Close.\nApps.\nNow.\nWhy?\nFollow."})
    with pytest.raises(ValueError, match="5-8 lines"):
        llm.validate_carousel_plan(carousel(caption="Line one.\nAsk?"), 2)
    hi = {**post(), "headline": "आपका फ़ोन धीमा क्यों है", "caption": HI_CAPTION.rsplit("\n", 1)[0] + "\nFollow for more tech tips"}
    with pytest.raises(ValueError, match="follow line"):
        llm.validate_image_plan(hi, LANGUAGES["hi"]["script"])


def test_the_caption_line_goes_on_a_single_picture_and_the_last_slide_only(monkeypatch, tmp_path):
    monkeypatch.setattr(pipeline, "OUT", tmp_path)
    monkeypatch.setattr(llm, "review_post", lambda p, lang: dict(p, review={"verdict": "ok"}))
    monkeypatch.setattr(pipeline.media, "gen_image", lambda *a: None)
    monkeypatch.setattr(pipeline.media, "_wikimedia", lambda *a: (_ for _ in ()).throw(LookupError("none")))
    one, last, follow = LANGUAGES["hi"]["cta"]
    monkeypatch.setattr(llm, "image_plan", lambda *a: planned())
    pipeline.make_image("t", "tech", job_id="one", language="hi")
    assert one in (tmp_path / "one" / "one.ass").read_text()
    monkeypatch.setattr(llm, "image_plan", lambda *a: planned(3))
    pipeline.make_image("t", "tech", job_id="car", language="hi", slides=3)
    ass = [(tmp_path / "car" / f"car-{i}.ass").read_text() for i in (1, 2, 3)]
    assert not any(last in a or follow in a for a in ass[:2]) and last in ass[2] and follow in ass[2]
