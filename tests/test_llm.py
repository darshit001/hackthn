import pytest
from llm import validate_plan, _parse, budget, validate_topics, _suggest_prompt
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
    (lambda p: p["scenes"][0].update(narration=" ".join(["word"] * 26)), "over 25 words"),
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
    (lambda p: p["hooks"][0].update(why=""), "why"),
    (lambda p: p.update(hook="Something else entirely"), "one of the three hooks"),
    (lambda p: p["scenes"][0].update(beat="context"), "scene 1 beat"),
    (lambda p: p["scenes"][-1].update(beat="twist"), "last scene beat"),
    (lambda p: p["scenes"][1].update(beat="intro"), "beat must be"),
    (lambda p: p["scenes"][1].pop("beat"), "beat must be"),
    (lambda p: p.pop("posts"), "posts"),
    (lambda p: p["posts"].update(instagram=""), "posts"),
    (lambda p: p["posts"].update(youtube_title="x" * 101), "youtube_title"),
    (lambda p: p["scenes"][0].update(image_prompt_b=" ".join(["w"] * 61)), "image_prompt_b"),
])
def test_bad_plan_rejected(mutate, msg):
    p = good()
    mutate(p)
    with pytest.raises(ValueError, match=msg):
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
