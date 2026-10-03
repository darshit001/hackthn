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
    assert out["review"] == {"verdict": "fixed", "notes": ["scene 2: dropped an invented number"]}
    assert apply_review(good(), {"verdict": "ok", "notes": [], "changes": []})["review"] == {"verdict": "ok", "notes": []}
    assert apply_review(good(), {"verdict": "ok", "notes": [], "changes": [{"scene": 3, "narration": "Softer."}]})["review"]["verdict"] == "fixed"  # ok with edits is an edit


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
    assert p["review"] == {"verdict": "ok", "notes": []} and "publishing editor" in seen["base"][0]["content"]


def test_review_is_skipped_when_every_model_is_down(monkeypatch):
    def down(base, validate, temperature=0.8):
        raise RuntimeError("every model failed: boom")
    monkeypatch.setattr(llm, "_ask", down)
    p = llm.review(good(), "en")
    assert p["review"]["verdict"] == "skipped" and "boom" in p["review"]["notes"][0]
    assert p["scenes"][1]["narration"] == "Sentence number 1 goes here."
