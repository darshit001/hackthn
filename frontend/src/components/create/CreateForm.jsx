import { useEffect, useRef, useState } from "react";
import { api } from "../../lib/api";
import { ICON, MAX_TOPICS } from "../../lib/constants";
import { reducedMotion } from "../../lib/format";
import { Icon } from "../Icon";
import { ScriptPreview } from "./ScriptPreview";

const HINT = "One topic per line, up to 10.";
// the suggestions dropdown is a <details className="menu">: a click elsewhere closes it (VideoList), Escape closes it here
const shut = d => { d.removeAttribute("open"); d.querySelector("summary").focus(); };
const escToClose = e => { if (e.key === "Escape" && e.currentTarget.open) { e.preventDefault(); shut(e.currentTarget); } };
// the form scrolls on its own, so an opened list is brought into view
const reveal = d => d.open && d.querySelector(".pop").scrollIntoView({ block: "nearest", behavior: reducedMotion() ? "auto" : "smooth" });
const toLines = text => text.split("\n").map(s => s.trim()).filter(Boolean).slice(0, MAX_TOPICS);

const SKELETON = ["78%", "62%", "85%", "55%", "70%", "66%"];

export function CreateForm({ presets, onStarted }) {
  const [text, setText] = useState("");
  const [community, setCommunity] = useState("general");
  const [language, setLanguage] = useState("en");
  const [duration, setDuration] = useState(30);
  const [style, setStyle] = useState("photo");
  const [status, setStatus] = useState(HINT);
  const [ideas, setIdeas] = useState([]);
  const [ideasNote, setIdeasNote] = useState("");  // where the ideas came from, or why there are none
  const [busy, setBusy] = useState("");  // the button that is working: suggest | preview | start
  const [preview, setPreview] = useState(null);  // {topic, plan}
  const form = useRef();
  const want = useRef("");  // the community|language the ideas are for; a late answer for an old pick is dropped
  const topics = toLines(text);
  const options = { community, language, duration, style };
  const count = topics.length;

  const changeText = value => { setText(value); setPreview(null); };
  const dropIdeas = () => { setIdeas([]); setIdeasNote(""); setPreview(null); };

  // a community with a non-English default (Hinglish Fun) switches the language; any change drops stale ideas
  const pickCommunity = c => {
    setCommunity(c.slug);
    if (c.language && c.language !== "en") setLanguage(c.language);
    dropIdeas();
  };

  const start = async (body, message) => {
    try {
      await api.generate(body);
      onStarted(message);
      changeText("");
      return true;
    } catch (e) {
      setStatus("Could not start: " + e.message);
      return false;
    }
  };

  const suggest = async () => {
    const key = `${community}|${language}`;
    setBusy("suggest");
    try {
      const s = await api.suggest(community, language);
      if (want.current !== key) return;
      setIdeas(s.topics.map(t => ({ text: t, added: topics.includes(t) })));
      setIdeasNote(s.trends.length ? "With today's trends in India" : `Ideas for ${presets.label(community)}`);
    } catch {
      if (want.current !== key) return;
      setIdeas([]); setIdeasNote("Suggestions are unavailable right now. Type a topic instead.");
    }
    setBusy("");
  };

  // today's ideas are fetched as soon as the pick settles: they become the topic box's placeholder and the dropdown opens on them
  // ponytail: no per-pick cache, so switching back refetches; cache by key if the free LLM quota gets tight
  useEffect(() => {
    want.current = `${community}|${language}`;
    const t = setTimeout(suggest, 700);
    return () => clearTimeout(t);
  }, [community, language]);  // eslint-disable-line react-hooks/exhaustive-deps

  const addIdea = idea => {
    if (!topics.includes(idea)) changeText([...topics, idea].join("\n"));
    setIdeas(list => list.map(i => (i.text === idea ? { ...i, added: true } : i)));
  };

  const showScript = async () => {
    setBusy("preview");
    setPreview(null);  // remount the preview so a fresh plan does not inherit the old edits
    try { setPreview({ topic: topics[0], plan: await api.plan({ topic: topics[0], ...options }) }); }
    catch { setStatus("Could not write the script right now. Try again or just generate the video."); }
    setBusy("");
  };

  const submit = async e => {
    e.preventDefault();
    if (!topics.length) return;
    setBusy("start");
    await start({ topics, ...options }, count === 1 ? "Generating 1 video" : `Generating ${count} videos`);
    setBusy("");
  };

  // the picked community's caption colour; no control may be named "style", or form.style stops being the CSS one
  const hue = presets.accents[community] || "#FFE500";

  return (
    <form ref={form} className="new" aria-labelledby="new-title" onSubmit={submit} style={{ "--hue": hue }}>
      <h1 id="new-title">Create a video</h1>

      {/* the order a person decides in: where it goes, which language, what about (suggestions use both), how it looks */}
      <div className="field"><span className="lbl"><b>1</b>Community</span>
        <div className="chips three" role="radiogroup" aria-label="Community">
          {presets.communities.map(c => (
            <label className="chip comm" key={c.slug}>
              <input type="radio" name="community" value={c.slug} checked={community === c.slug} onChange={() => pickCommunity(c)} />
              <Icon name={ICON[c.slug] || "folder"} /><span>{presets.label(c.slug)}</span>
            </label>
          ))}
        </div>
      </div>

      <div className="field"><span className="lbl"><b>2</b>Language</span>
        <div className="chips" role="radiogroup" aria-label="Language">
          {presets.languages.map(l => (
            <label className="chip" key={l.slug}>
              <input type="radio" name="language" value={l.slug} checked={language === l.slug} onChange={() => { setLanguage(l.slug); dropIdeas(); }} />
              <span>{l.label}</span>
            </label>
          ))}
        </div>
      </div>

      <div className="field topic">
        <div className="lblrow">
          <label className="lbl" htmlFor="topics"><b>3</b>Topic</label>
          <details className="menu drop" onKeyDown={escToClose} onToggle={e => { reveal(e.currentTarget); if (e.currentTarget.open && !ideas.length && busy !== "suggest") suggest(); }}>
            <summary className="link"><Icon name="sparkles" />Suggest topics<Icon name="chevron" className="i chev" /></summary>
            <div className="pop ideas" aria-busy={busy === "suggest"}>
              <div className="pophead">
                <span>{busy === "suggest" ? "Finding ideas…" : <>{ideasNote.startsWith("With") && <Icon name="trending" />}{ideasNote}</>}</span>
                <button type="button" className="link" disabled={busy === "suggest"} onClick={suggest}><Icon name="refresh" className={`i${busy === "suggest" ? " spin" : ""}`} />New ideas</button>
              </div>
              {/* six ideas come back, so six placeholder rows hold their place while they are written */}
              {busy === "suggest" && SKELETON.map((w, n) => <span key={n} className="skel" style={{ "--w": w, "--n": n }} aria-hidden="true" />)}
              {busy !== "suggest" && ideas.map(i => (
                <button type="button" key={i.text} className={i.added ? "added" : ""} disabled={i.added} onClick={e => { addIdea(i.text); e.currentTarget.closest("details").open = false; form.current.topics.focus(); }}
                  aria-label={i.added ? `${i.text}, added` : `Add ${i.text}`}>
                  <span>{i.text}</span><Icon name={i.added ? "check" : "plus"} />
                </button>
              ))}
            </div>
          </details>
        </div>
        <textarea id="topics" className="topics" rows={3} value={text} aria-describedby="topics-hint"
          placeholder={(ideas.length ? ideas.slice(0, 3).map(i => i.text) : presets.communities.find(c => c.slug === community)?.examples || []).join("\n")}
          onChange={e => changeText(e.target.value)}
          onKeyDown={e => { if ((e.ctrlKey || e.metaKey) && e.key === "Enter") form.current.requestSubmit(); }} />
        <p className="hint" id="topics-hint"><span>{status}</span><span className="count">{topics.length}/{MAX_TOPICS}</span></p>
      </div>

      <div className="field"><span className="lbl"><b>4</b>Look</span>
        <div className="chips look" role="radiogroup" aria-label="Look">
          {presets.styles.map(s => (
            <label className="chip" key={s.slug}>
              <input type="radio" name="look" value={s.slug} checked={style === s.slug} onChange={() => setStyle(s.slug)} /><span>{s.label}</span>
            </label>
          ))}
        </div>
      </div>
      <div className="field"><span className="lbl"><b>5</b>Length</span>
        <div className="chips" role="radiogroup" aria-label="Length">
          {presets.durations.map(d => (
            <label className="chip" key={d}>
              <input type="radio" name="duration" value={d} checked={duration === d} onChange={() => { setDuration(d); setPreview(null); }} /><span>{d} s</span>
            </label>
          ))}
        </div>
      </div>

      <div className="go">
        {/* a script preview is for one topic at a time */}
        <button type="button" className="btn" disabled={topics.length !== 1 || busy === "preview"} onClick={showScript}>
          {busy === "preview" ? "Writing…" : "Preview script"}
        </button>
        <button type="submit" className="primary" disabled={!topics.length || busy === "start"}>
          <Icon name="play" className="i fill" /><span>{count <= 1 ? "Generate video" : `Generate ${count} videos`}</span>
        </button>
      </div>
      <p className="after">
        <span><Icon name="clock" />About a minute per video</span>
        <span><kbd>Ctrl</kbd> <kbd>Enter</kbd> starts it</span>
      </p>
      {preview && (
        <ScriptPreview key={preview.topic} {...preview} onClose={() => setPreview(null)}
          onMake={plan => start({ topics: [preview.topic], ...options, plan }, "Generating 1 video with your script")} />
      )}
    </form>
  );
}
