from render import ass_time, ass_color, chunk, align


def test_ass_time_formats_centiseconds():
    assert ass_time(0) == "0:00:00.00"
    assert ass_time(61.5) == "0:01:01.50"
    assert ass_time(3599.994) == "0:59:59.99"


def test_ass_color_is_bgr_with_zero_alpha():
    assert ass_color("FFE500") == "&H0000E5FF"
    assert ass_color("00E5FF") == "&H00FFE500"


def w(word, start, end):
    return {"word": word, "start": start, "end": end}


def test_chunk_splits_by_size_and_gap():
    words = [w("a", 0, .2), w("b", .2, .4), w("c", .4, .6), w("d", .6, .8), w("e", .8, 1.0),
             w("f", 2.0, 2.2), w("g", 2.2, 2.4)]
    got = chunk(words, size=4, max_gap=0.6)
    assert [[x["word"] for x in c] for c in got] == [["a", "b", "c", "d"], ["e"], ["f", "g"]]


def test_align_uses_script_spelling_when_counts_match():
    timed = [w("Hello", 0.2, 0.5), w("from", 0.5, 0.9), w("QNECT", 0.9, 1.5)]
    got = align(["Hello from Qoneqt"], [(0.0, 1.8)], timed)
    assert [x["word"] for x in got] == ["Hello", "from", "Qoneqt"]
    assert got[2]["start"] == 0.9


def test_align_spreads_evenly_when_whisper_is_empty():
    got = align(["one two three four"], [(2.0, 4.0)], [])
    assert [x["word"] for x in got] == ["one", "two", "three", "four"]
    assert got[0]["start"] == 2.0 and abs(got[-1]["end"] - 4.0) < 1e-9


def test_align_falls_back_to_whisper_words_on_big_mismatch():
    timed = [w(f"w{i}", i * 0.2, i * 0.2 + 0.2) for i in range(10)]
    got = align(["just two"], [(0.0, 2.0)], timed)
    assert len(got) == 10


def test_run_caps_every_ffmpeg_thread_pool(monkeypatch):
    import subprocess
    import render
    seen = {}
    monkeypatch.setattr(subprocess, "run", lambda cmd, **kw: seen.setdefault("cmd", cmd) and type("R", (), {"returncode": 0})())
    render._run(["ffmpeg", "-y", "-i", "a.mp4", "-i", "b.wav", "-c:v", "libx264", "out.mp4"])
    t = render.THREADS
    assert seen["cmd"] == ["ffmpeg", "-filter_threads", t, "-y", "-threads", t, "-i", "a.mp4",
                           "-threads", t, "-i", "b.wav", "-c:v", "libx264", "-threads", t, "out.mp4"]


def test_compose_bounds_shortest_buffer(monkeypatch, tmp_path):
    # ffmpeg 7 buffers up to 10 s of raw 1080x1920 frames for -shortest (~930 MB): the Railway OOM kill
    import render
    cmds = []
    monkeypatch.setattr(render, "_run", lambda cmd, cwd=None: cmds.append(cmd))
    render.compose([(None, 1.0)], tmp_path / "voice.wav", tmp_path / "captions.ass", tmp_path, "x")
    final = next(c for c in cmds if "-shortest" in c)
    assert final[final.index("-shortest_buf_duration") + 1] == "1"
