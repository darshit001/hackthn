import { useRef, useState } from "react";
import { api } from "../../lib/api";
import { ICON, MAX_TOPICS } from "../../lib/constants";
import { Icon } from "../Icon";
import { ScriptPreview } from "./ScriptPreview";

const HINT = "One topic per line, up to 10. Suggestions use what India is searching today.";
const toLines = text => text.split("\n").map(s => s.trim()).filter(Boolean).slice(0, MAX_TOPICS);

export function CreateForm({ presets, onStarted }) {
  const [text, setText] = useState("");
  const [community, setCommunity] = useState("general");
  const [language, setLanguage] = useState("en");
  const [duration, setDuration] = useState(30);
  const [style, setStyle] = useState("photo");
  const [every, setEvery] = useState(false);  // also make it in every other language
  const [status, setStatus] = useState(HINT);
  const [ideas, setIdeas] = useState([]);
  const [busy, setBusy] = useState("");  // the button that is working: suggest | preview | start
  const [preview, setPreview] = useState(null);  // {topic, plan}
  const form = useRef();
  const topics = toLines(text);
  const options = { community, language, duration, style };
  const langs = presets.languages.length;
  const count = topics.length * (every ? langs : 1);

  const changeText = value => { setText(value); setPreview(null); };
  const dropIdeas = () => { setIdeas([]); setPreview(null); };

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
      setEvery(false);  // a forgotten tick would silently make the next batch one per language
      return true;
    } catch (e) {
      setStatus("Could not start: " + e.message);
      return false;
    }
  };

  const suggest = async () => {
    setBusy("suggest"); setStatus("");
    try {
      const s = await api.suggest(community, language);
      setIdeas(s.topics.map(t => ({ text: t, added: topics.includes(t) })));
      setStatus(s.trends.length ? `${s.topics.length} ideas, some from today's Google Trends India.` : `${s.topics.length} ideas.`);
    } catch { setStatus("Suggestions are unavailable right now. Type a topic instead."); }
    setBusy("");
  };

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
    const message = every ? `Generating ${count} videos in ${langs} languages` : count === 1 ? "Generating 1 video" : `Generating ${count} videos`;
    await start({ topics, ...options, all_languages: every }, message);
    setBusy("");
  };

  return (
    <form ref={form} className="new" aria-labelledby="new-title" onSubmit={submit}>
      <h1 id="new-title">Create a new video</h1>
      <p className="sub">Turn a topic into a ready-to-post Global Feed video.</p>

      <label className="field" htmlFor="topics"><span>1. Topics</span>
        <div className="ta">
          <textarea id="topics" className="topics" rows={4} value={text}
            placeholder={"why sleep matters\n5 AI tools every student should know\nchai vs coffee"}
            onChange={e => changeText(e.target.value)}
            onKeyDown={e => { if ((e.ctrlKey || e.metaKey) && e.key === "Enter") form.current.requestSubmit(); }} />
          <span className="count">{topics.length}/{MAX_TOPICS}</span>
        </div>
      </label>
      <div className="row" style={{ margin: "-6px 0 16px" }}>
        <button type="button" className="btn" disabled={busy === "suggest"} onClick={suggest}>{busy === "suggest" ? "Thinking…" : "Suggest topics"}</button>
        <p className="hint">{status}</p>
        {ideas.length > 0 && (
          <ul className="ideas">
            {ideas.map(i => (
              <li key={i.text}>
                <span>{i.text}</span>
                <button type="button" className="btn" disabled={i.added} onClick={() => addIdea(i.text)}>{i.added ? "Added" : "Add"}</button>
              </li>
            ))}
          </ul>
        )}
        {preview && (
          <ScriptPreview key={preview.topic} {...preview} onClose={() => setPreview(null)}
            onMake={plan => start({ topics: [preview.topic], ...options, all_languages: every, plan },
              every ? `Generating ${langs} videos in ${langs} languages with your script` : "Generating 1 video with your script")} />
        )}
      </div>

      <div className="field"><span>2. Community</span>
        <div className="tiles" role="radiogroup" aria-label="Community">
          {presets.communities.map(c => (
            <label className="tile" key={c.slug}>
              <input type="radio" name="community" value={c.slug} checked={community === c.slug} onChange={() => pickCommunity(c)} />
              <Icon name={ICON[c.slug] || "folder"} /><span>{presets.label(c.slug)}</span>
            </label>
          ))}
        </div>
      </div>
      <label className="field"><span>3. Language</span>
        <div className="iconsel"><Icon name="globe" />
          <select className="sel" name="language" value={language} onChange={e => { setLanguage(e.target.value); dropIdeas(); }}>
            {presets.languages.map(l => <option key={l.slug} value={l.slug}>{l.label}</option>)}
          </select>
        </div>
      </label>
      <label className="check">
        <input type="checkbox" checked={every} onChange={e => setEvery(e.target.checked)} />Also make it in the other languages (same visuals)
      </label>
      <div className="field"><span>4. Length</span>
        <div className="seg" role="radiogroup" aria-label="Length">
          {presets.durations.map(d => (
            <label key={d}>
              <input type="radio" name="duration" value={d} checked={duration === d} onChange={() => { setDuration(d); setPreview(null); }} /><span>{d} s</span>
            </label>
          ))}
        </div>
      </div>
      <div className="field"><span>5. Look</span>
        <div className="seg" role="radiogroup" aria-label="Look">
          {presets.styles.map(s => (
            <label key={s.slug}>
              <input type="radio" name="style" value={s.slug} checked={style === s.slug} onChange={() => setStyle(s.slug)} /><span>{s.label}</span>
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
    </form>
  );
}
