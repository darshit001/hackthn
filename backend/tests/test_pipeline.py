import pytest
from app import llm, pipeline

BLOCKED = "blocked by the safety review: scene 2: dangerous advice"


def test_a_blocked_source_blocks_its_siblings(tmp_path, monkeypatch):
    monkeypatch.setattr(pipeline, "OUT", tmp_path)
    (tmp_path / "src1").mkdir()
    (tmp_path / "src1" / "blocked.txt").write_text(BLOCKED)
    with pytest.raises(RuntimeError, match="^blocked by the safety review in the first language: scene 2: dangerous advice$"):
        pipeline._source("src1")


def test_make_video_flags_a_blocked_plan_but_not_a_failed_one(tmp_path, monkeypatch):
    monkeypatch.setattr(pipeline, "OUT", tmp_path)
    monkeypatch.setattr(llm, "plan", lambda *a: {"scenes": []})

    def blocked(p, language):
        raise RuntimeError(BLOCKED)
    monkeypatch.setattr(llm, "review", blocked)
    with pytest.raises(RuntimeError, match="blocked"):
        pipeline.make_video("t", job_id="j1")
    assert (tmp_path / "j1" / "blocked.txt").read_text() == BLOCKED

    def down(*a):
        raise RuntimeError("every model failed: x")
    monkeypatch.setattr(llm, "plan", down)
    with pytest.raises(RuntimeError, match="every model failed"):
        pipeline.make_video("t", job_id="j2")
    assert not (tmp_path / "j2" / "blocked.txt").exists()
