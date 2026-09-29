import pytest
from llm import validate_plan, _parse


def good():
    return {
        "hooks": [{"text": "a", "score": 5}, {"text": "b", "score": 6}, {"text": "c", "score": 7}],
        "hook": "Ever wonder why you feel tired?",
        "scenes": [{"narration": f"Sentence number {i} goes here.", "query": "city night"} for i in range(5)],
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
