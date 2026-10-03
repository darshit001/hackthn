import pytest
import llm
from llm import validate_plan, _parse, budget, validate_topics, _suggest_prompt, validate_review, apply_review
from presets import COMMUNITIES, LANGUAGES


def good():
    return {
        "hooks": [{"text": "Ever wonder why you feel tired?", "formula": "question", "score": 8, "why": "Everyone is tired and wants the reason."},
                  {"text": "Sleep debt is a real bill.", "formula": "bold_claim", "score": 6, "why": "Money framing makes sleep feel urgent."},
                  {"text": "Eight hours is a myth.", "formula": "myth", "score": 7, "why": "Contradicts what every viewer was told."}],
        "hook": "Ever wonder why you feel tired?",
        "scenes": [{"beat": b, "narration": f"Sentence number {i} goes here.", "title": f"Point {i}", "query": "city night"}
                   for i, b in enumerate(["hook", "context", "rehook", "twist", "payoff"])],
        "caption": "Sleep more.",
        "hashtags": ["#sleep", "#health", "#Qoneqt"],
        "posts": {"youtube_title": "Why you feel tired all day", "youtube_description": "Sleep debt, explained in thirty seconds.\n#sleep #health #shorts",
                  "instagram": "Tired all the time? Here is the real reason."},
    }


def test_good_plan_passes():
    validate_plan(good())


@pytest.mark.parametrize("mutate,msg", [
    (lambda p: p.update(scenes=p["scenes"][:4]), "5-7 scenes"),
    (lambda p: p.update(scenes=p["scenes"] * 2), "5-7 scenes"),
    (lambda p: p["scenes"][1].update(narration=" ".join(["word"] * 26)), "over 25 words"),
    (lambda p: p["scenes"][0].update(narration=" ".join(["word"] * 41)), "over 40 words"),
    (lambda p: p["scenes"][0].update(narration="   "), "narration missing"),
    (lambda p: p["scenes"][0].update(title=""), "title"),
    (lambda p: p["scenes"][0].pop("title"), "title"),
    (lambda p: p["scenes"][0].update(title=" ".join(["w"] * 9)), "title"),
    (lambda p: p["scenes"][0].update(query="one two three four five"), "1-4 words"),
    (lambda p: p["scenes"][0].update(query="शहर रात"), "ASCII"),
    (lambda p: p.update(hashtags=["sleep", "#a", "#b"]), "start with #"),
    (lambda p: p.update(hashtags=["#a", "#b"]), "3-10 hashtags"),
    (lambda p: p.update(hook=""), "hook missing"),
    (lambda p: p.update(caption=""), "caption missing"),
    (lambda p: p["scenes"][0].update(image_prompt=42), "image_prompt"),
    (lambda p: p["scenes"][0].update(image_prompt=" ".join(["w"] * 61)), "image_prompt"),
    (lambda p: p.update(hook="Did you know sleep matters?", hooks=[dict(p["hooks"][0], text="Did you know sleep matters?")] + p["hooks"][1:]), "banned opener"),
    (lambda p: p.update(hook="Kya aap jaante hain neend kyun zaroori hai?", hooks=[dict(p["hooks"][0], text="Kya aap jaante hain neend kyun zaroori hai?")] + p["hooks"][1:]), "banned opener"),
    (lambda p: p.update(hooks=p["hooks"] + [p["hooks"][0]]), "exactly 3 hooks"),
    (lambda p: p["hooks"][0].update(formula="riddle"), "formula"),
    (lambda p: p["hooks"][0].update(score=11), "score"),
    (lambda p: p["hooks"][0].update(score=True), "score"),
    (lambda p: p["hooks"][0].update(why=""), "why"),
    (lambda p: p["hooks"][0].update(why=" ".join(["w"] * 31)), "why"),
    (lambda p: p.update(hook="Something else entirely"), "one of the three hooks"),
    (lambda p: p["scenes"][0].update(beat="context"), "scene 1 beat"),
    (lambda p: p["scenes"][-1].update(beat="twist"), "last scene beat"),
    (lambda p: p["scenes"][1].update(beat="intro"), "beat must be"),
    (lambda p: p["scenes"][1].pop("beat"), "beat must be"),
    (lambda p: p.pop("posts"), "posts"),
    (lambda p: p["posts"].update(instagram=""), "posts"),
    (lambda p: p["posts"].update(youtube_title="x" * 101), "youtube_title"),
    (lambda p: p["scenes"][0].update(image_prompt_b=" ".join(["w"] * 61)), "image_prompt_b"),
    (lambda p: p["scenes"][0].update(image_prompt_b=42), "image_prompt_b"),
])
def test_bad_plan_rejected(mutate, msg):
    p = good()
    mutate(p)
    with pytest.raises(ValueError, match=msg):
        validate_plan(p)


def test_scene_one_may_carry_a_long_hook():
    p = good()
    p["scenes"][0]["narration"] = " ".join(["word"] * 30)  # UI swaps a story/warning hook into scene 1
    validate_plan(p)


def test_opener_check_stops_at_word_boundaries():
    p = good()
    p["hooks"][0]["text"] = p["hook"] = "Today weekend plans are sorted."  # "today we" is banned, "Today weekend" is not
    validate_plan(p)


def test_image_prompt_is_optional():
    p = good()
    p["scenes"][0]["image_prompt"] = "A woman journaling over coffee at a sunlit cafe table, soft morning light"
    validate_plan(p)


def test_parse_strips_fences_and_prose():
    assert _parse('Sure! ```json\n{"a": 1}\n``` done') == {"a": 1}


@pytest.mark.parametrize("duration,expected", [
    (15, (3, 4, 31, 41)),
    (30, (4, 6, 61, 83)),
    (45, (6, 8, 92, 124)),
    (60, (8, 9, 122, 166)),
])
def test_budget_windows(duration, expected):
    assert budget(duration) == expected


def test_validate_plan_honours_scene_range():
    p = good()  # 5 scenes
    validate_plan(p, scenes=(3, 5))
    with pytest.raises(ValueError, match="3-4 scenes"):
        validate_plan(p, scenes=(3, 4))


def test_validate_topics():
    validate_topics({"topics": ["a", "b", "c"]})
    for bad in ({"topics": []}, {"topics": ["a", " ", "c"]}, {"topics": "a"}, [], {"topics": ["x"] * 9}):
        with pytest.raises(ValueError, match="topics"):
            validate_topics(bad)


def test_suggest_prompt_trends_only_rule():
    args = (COMMUNITIES["tech"], LANGUAGES["en"], ["india vs brazil", "forex factory"])
    assert "Every topic must be inspired" in _suggest_prompt(*args, trends_only=True)
    assert "Every topic must be inspired" not in _suggest_prompt(*args)
    assert "Every topic must be inspired" not in _suggest_prompt(COMMUNITIES["tech"], LANGUAGES["en"], [], trends_only=True)  # feed down


def test_image_prompt_b_is_optional():
    p = good()
    p["scenes"][0]["image_prompt_b"] = "Close-up: the same woman's hands around the warm cup, steam rising, soft window light"
    validate_plan(p)


def test_system_prompt_carries_the_retention_rules():
    from llm import SYSTEM, FORMULAS, BEATS
    text = SYSTEM.format(duration=30, scenes_lo=4, scenes_hi=6, words_lo=61, words_hi=83)
    assert all(f in text for f in FORMULAS) and all(b in text for b in BEATS)
    assert "Wide shot:" in text and "image_prompt_b" in text and "youtube_title" in text and "Did you know" in text


def test_validate_review_accepts_the_three_verdicts():
    validate_review({"verdict": "ok", "notes": [], "changes": []}, 5)
    validate_review({"verdict": "fixed", "notes": ["scene 2: softened"], "changes": [{"scene": 2, "narration": "Studies suggest it helps."}]}, 5)
    validate_review({"verdict": "blocked", "notes": ["incites hatred"], "changes": []}, 5)


@pytest.mark.parametrize("r, msg", [
    ({"verdict": "maybe", "notes": [], "changes": []}, "verdict"),
    ({"verdict": "ok", "notes": "fine", "changes": []}, "notes"),
    ({"verdict": "ok", "notes": [], "changes": "none"}, "changes"),
    ({"verdict": "fixed", "notes": [], "changes": []}, "at least one change"),
    ({"verdict": "fixed", "notes": [], "changes": [{"scene": 6, "narration": "x"}]}, "1 to 5"),
    ({"verdict": "fixed", "notes": [], "changes": [{"scene": True, "narration": "x"}]}, "1 to 5"),
    ({"verdict": "fixed", "notes": [], "changes": [{"scene": 2, "narration": " "}]}, "narration missing"),
    ({"verdict": "fixed", "notes": [], "changes": [{"scene": 2, "narration": " ".join(["w"] * 26)}]}, "over 25 words"),
    ({"verdict": "fixed", "notes": [], "changes": [{"scene": 1, "narration": " ".join(["w"] * 41)}]}, "over 40 words"),
])
def test_validate_review_rejects(r, msg):
    with pytest.raises(ValueError, match=msg):
        validate_review(r, 5)


def test_apply_review_softens_the_listed_lines_and_stamps_the_plan():
    out = apply_review(good(), {"verdict": "fixed", "notes": [" scene 2: dropped an invented number "], "changes": [{"scene": 2, "narration": " Studies suggest it helps. "}]})
    assert out["scenes"][1]["narration"] == "Studies suggest it helps." and out["scenes"][0]["narration"] == "Sentence number 0 goes here."
    assert out["review"] == {"verdict": "fixed", "notes": ["scene 2: dropped an invented number"], "changed": 1}
    assert apply_review(good(), {"verdict": "ok", "notes": [], "changes": []})["review"] == {"verdict": "ok", "notes": [], "changed": 0}
    assert apply_review(good(), {"verdict": "ok", "notes": [], "changes": [{"scene": 3, "narration": "Softer."}]})["review"]["verdict"] == "fixed"  # ok with edits is an edit


def test_apply_review_never_drops_the_hook_from_scene_one():
    p = apply_review(good(), {"verdict": "fixed", "notes": ["softened"], "changes": [{"scene": 1, "narration": "Tired? Here is why."}]})
    assert p["scenes"][0]["narration"] == "Sentence number 0 goes here."
    assert p["review"] == {"verdict": "fixed", "notes": ["softened", "scene 1 left as written to keep the hook"], "changed": 0}
    p = good(); p["scenes"][0]["narration"] = p["hook"] + " Stakes."
    p = apply_review(p, {"verdict": "fixed", "notes": [], "changes": [{"scene": 1, "narration": p["hook"] + " Softer stakes."}]})
    assert p["scenes"][0]["narration"] == "Ever wonder why you feel tired? Softer stakes." and p["review"]["changed"] == 1


def test_apply_review_blocks_before_any_spend():
    with pytest.raises(RuntimeError, match="blocked by the safety review: incites hatred"):
        apply_review(good(), {"verdict": "blocked", "notes": ["incites hatred"], "changes": []})
    with pytest.raises(RuntimeError, match="unsafe content"):
        apply_review(good(), {"verdict": "blocked", "notes": [], "changes": []})


def test_review_prompt_carries_the_script_and_runs_cold(monkeypatch):
    seen = {}

    def fake(base, validate, temperature=0.8):
        seen.update(base=base, temperature=temperature)
        r = {"verdict": "ok", "notes": [], "changes": []}
        validate(r)
        return r
    monkeypatch.setattr(llm, "_ask", fake)
    p = llm.review(good(), "hi")
    user = seen["base"][1]["content"]
    assert seen["temperature"] == 0.2 and "1. Sentence number 0 goes here." in user and "5. Sentence number 4" in user
    assert "Devanagari" in user and "Hook: Ever wonder why you feel tired?" in user
    assert p["review"] == {"verdict": "ok", "notes": [], "changed": 0} and "publishing editor" in seen["base"][0]["content"]


def test_review_is_skipped_when_every_model_is_down(monkeypatch):
    def down(base, validate, temperature=0.8):
        raise RuntimeError("every model failed: boom")
    monkeypatch.setattr(llm, "_ask", down)
    p = llm.review(good(), "en")
    assert p["review"]["verdict"] == "skipped" and "boom" in p["review"]["notes"][0]
    assert p["scenes"][1]["narration"] == "Sentence number 1 goes here."


def hindi():
    """good() as a Hindi translation: the hook, every narration and every title carry Devanagari."""
    q = good()
    q["hook"] = q["hooks"][0]["text"] = "थकान क्यों?"
    for s in q["scenes"]:
        s.update(narration="नमस्ते " + s["narration"], title="शीर्षक")
    q["scenes"][0]["narration"] = "थकान क्यों? " + q["scenes"][0]["narration"]
    return q


def test_translate_keeps_the_visuals_and_the_review_and_pins_the_scene_count(monkeypatch):
    import json
    src = dict(good(), model="test", review={"verdict": "ok", "notes": []})
    seen = {}

    def fake(base, validate, temperature=0.8):
        seen.update(system=base[0]["content"], user=base[1]["content"], temperature=temperature)
        q = hindi()
        for s in q["scenes"]:  # a model that "helpfully" rewrites the visuals is corrected, not retried
            s.update(query="changed", image_prompt="changed", beat="twist")
        q["hooks"][0]["score"] = 1
        q["hashtags"] = ["#changed"]
        validate(q)
        return q
    monkeypatch.setattr(llm, "_ask", fake)
    out = llm.translate(src, "hi", 30)
    assert [s["query"] for s in out["scenes"]] == ["city night"] * 5 and [s["beat"] for s in out["scenes"]] == [s["beat"] for s in src["scenes"]]
    assert all(s.get("image_prompt") is None for s in out["scenes"])  # the source had none, so none is invented
    assert out["hooks"][0]["score"] == 8 and out["hashtags"] == src["hashtags"] and out["review"] == src["review"]
    assert out["scenes"][0]["narration"].startswith("थकान क्यों? नमस्ते") and out["scenes"][0]["title"] == "शीर्षक"
    assert seen["temperature"] == 0.5 and "Devanagari" in seen["system"] and "30 second" in seen["system"]
    user = seen["user"]
    assert '"model"' not in user and '"review"' not in user and "Sentence number 0" in user and "Point 4" in user
    assert "image_prompt" not in user and "query" not in user and '"hashtags"' not in user and "#Qoneqt" not in user  # only the words travel (#sleep rides in youtube_description)


def test_translate_keeps_the_hook_the_user_chose(monkeypatch):
    src = good(); src["hook"] = src["hooks"][2]["text"]  # swapped in the lower-scoring myth hook
    ret = {}
    monkeypatch.setattr(llm, "_ask", lambda base, validate, temperature=0.8: validate(ret["q"]) or ret["q"])
    q = hindi(); q["hooks"][2]["text"] = "आठ घंटे एक मिथक है।"
    ret["q"] = q  # hindi() opens on its hooks[0], the top-scored one
    with pytest.raises(ValueError, match="hook 3"):
        llm.translate(src, "hi", 30)
    q = hindi(); q["hooks"][2]["text"] = q["hook"] = "आठ घंटे एक मिथक है।"
    q["scenes"][0]["narration"] = q["hook"] + " नमस्ते।"
    ret["q"] = q
    assert llm.translate(src, "hi", 30)["hook"] == "आठ घंटे एक मिथक है।"


def test_translate_rejects_a_different_scene_count(monkeypatch):
    def fake(base, validate, temperature=0.8):
        q = good(); q["scenes"] = q["scenes"][:4]
        validate(q)
        return q
    monkeypatch.setattr(llm, "_ask", fake)
    with pytest.raises(ValueError, match="need 5-5 scenes"):
        llm.translate(good(), "gu", 30)


def test_translate_rejects_text_outside_the_target_script(monkeypatch):
    ret = {}
    monkeypatch.setattr(llm, "_ask", lambda base, validate, temperature=0.8: validate(ret["q"]) or ret["q"])
    ret["q"] = q = hindi(); q["hook"] = q["hooks"][0]["text"] = "Tired?"  # the model left the hook in English
    with pytest.raises(ValueError, match="hook is not in हिन्दी"):
        llm.translate(good(), "hi", 30)
    ret["q"] = q = hindi(); q["scenes"][1]["title"] = "Point 1"
    with pytest.raises(ValueError, match="scene 2 title is not in हिन्दी"):
        llm.translate(good(), "hi", 30)
    ret["q"] = q = good(); q["scenes"][2]["narration"] = "नमस्ते दुनिया"
    with pytest.raises(ValueError, match="scene 3 narration is not in English"):
        llm.translate(good(), "en", 30)


def test_groq_asks_qwen_for_what_the_free_tier_allows(monkeypatch):
    sent = []

    class R:
        def raise_for_status(self): pass
        def json(self): return {"choices": [{"message": {"content": "{}"}}]}
    monkeypatch.setenv("GROQ_API_KEY", "x")
    monkeypatch.setattr(llm.httpx, "post", lambda url, json=None, **kw: sent.append(json["max_tokens"]) or R())
    llm._call_groq("qwen/qwen3.8-27b", [], 0.5)
    llm._call_groq("openai/gpt-oss-120b", [], 0.5)
    assert sent == [1000, 4000]
