import pytest
from llm import validate_plan, _parse, budget, validate_topics


def good():
    return {
        "hooks": [{"text": "a", "score": 5}, {"text": "b", "score": 6}, {"text": "c", "score": 7}],
        "hook": "Ever wonder why you feel tired?",
        "scenes": [{"narration": f"Sentence number {i} goes here.", "title": f"Point {i}", "query": "city night"} for i in range(5)],
        "caption": "Sleep more.",
        "hashtags": ["#sleep", "#health", "#Qoneqt"],
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
