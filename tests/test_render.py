from render import ass_time, ass_color, chunk, align, ass_text, subtitles, OUTRO, OUTRO_SEC


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


def test_ass_text_neutralises_markup():
    assert ass_text("a {b} c\\d\ne") == "a (b) c/d\\Ne"


def test_subtitles_writes_overlays(tmp_path):
    words = [w("hello", 0.0, 0.5), w("world", 0.5, 1.0)]
    overlays = [(0.0, 2.5, "Big hook", "Hook"), (3.0, 7.0, "Scene title", "Title"), (10.0, 12.0, OUTRO, "Outro")]
    text = subtitles(words, "general", tmp_path / "c.ass", overlays).read_text()
    assert "Style: Hook," in text and "Style: Title," in text and "Style: Outro," in text
    assert "Dialogue: 1,0:00:00.00,0:00:02.50,Hook,,0,0,0,,{\\fad(200,200)}Big hook" in text
    assert "Dialogue: 1,0:00:03.00,0:00:07.00,Title,,0,0,0,,{\\fad(150,150)}Scene title" in text
    assert "Dialogue: 1,0:00:10.00,0:00:12.00,Outro,,0,0,0,,{\\fad(300,0)}" in text and "Qoneqt" in text
    assert "HELLO" in text  # captions still there


def test_compose_crossfades_scenes_into_the_end_card(monkeypatch, tmp_path):
    import render
    cmds = []
    monkeypatch.setattr(render, "_run", lambda cmd, cwd=None: cmds.append(cmd))
    render.compose([(None, 1.0), (None, 2.5)], tmp_path / "voice.wav", tmp_path / "captions.ass", tmp_path, "x")
    scene0 = next(c for c in cmds if c[-1] == str(tmp_path / "scene0.mp4"))
    assert f"d={1.0 + render.XFADE_SEC:.3f}" in " ".join(scene0)  # every scene runs on for the overlap
    outro = next(c for c in cmds if c[-1] == str(tmp_path / "outro.mp4"))
    assert f"d={OUTRO_SEC:.3f}" in " ".join(outro)  # the card itself is not extended
    assert "bframes=0:ref=1" in scene0 and "bframes=0:ref=1" in outro  # small decoder buffers: xfade opens every clip at once
    final = cmds[-2]  # the last call is the thumbnail
    assert "bframes=0:ref=1" not in final  # the delivered video keeps x264's normal quality settings
    ins = [final[i + 1] for i, a in enumerate(final) if a == "-i"]
    assert ins[:3] == ["scene0.mp4", "scene1.mp4", "outro.mp4"] and ins[3].endswith("voice.wav")
    fc = final[final.index("-filter_complex") + 1]
    assert "[0:v]settb=AVTB,fps=30[s0]" in fc
    assert f"[s0][s1]xfade=transition={render.XFADE}:duration={render.XFADE_SEC}:offset=1.000[x1]" in fc
    assert "[x1][s2]xfade=" in fc and "offset=3.500[x2]" in fc  # the end card fades in when the last word ends
    assert fc.endswith("[x2]subtitles=captions.ass[v]")
    assert final[final.index("-map") + 1] == "[v]" and "3:a" in final  # voice is input 3, mapped straight through
    assert final[final.index("-shortest_buf_duration") + 1] == "1"  # ffmpeg 7 would otherwise buffer 10 s of raw frames (the Railway OOM)


def test_compose_mixes_music_under_the_voice(monkeypatch, tmp_path):
    import render
    cmds = []
    monkeypatch.setattr(render, "_run", lambda cmd, cwd=None: cmds.append(cmd))
    monkeypatch.setattr(render, "duration", lambda p: 20.0)
    render.compose([(None, 1.0)], tmp_path / "voice.wav", tmp_path / "captions.ass", tmp_path, "x", music=tmp_path / "bed.mp3")
    final = next(c for c in cmds if "-shortest" in c)
    fc = final[final.index("-filter_complex") + 1]
    assert "[3:a]volume=" in fc and "[2:a]asplit=2[a1][a2]" in fc  # inputs: scene0, outro, voice, music
    assert "sidechaincompress" in fc and "amix=inputs=2:duration=first:normalize=0[a]" in fc and "afade=t=out:st=18.50" in fc
    assert final[final.index("-map") + 1] == "[v]" and "[a]" in final
    assert "-stream_loop" in final
