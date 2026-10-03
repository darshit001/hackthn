import { useRef, useState } from "react";
import { api } from "../../lib/api";
import { GLYPH, ICON, MAX_TOPICS } from "../../lib/constants";
import { reducedMotion } from "../../lib/format";
import { Icon } from "../Icon";
import { PresenterPhoto } from "./PresenterPhoto";
import { ScriptPreview } from "./ScriptPreview";

const HINT = "One topic per line, up to 10.";
// the two dropdowns are <details className="menu">: a click elsewhere closes them (VideoList), Escape closes them here
const shut = d => { d.removeAttribute("open"); d.querySelector("summary").focus(); };
const escToClose = e => { if (e.key === "Escape" && e.currentTarget.open) { e.preventDefault(); shut(e.currentTarget); } };
// the form scrolls on its own, so an opened list is brought into view
const reveal = d => d.open && d.querySelector(".pop").scrollIntoView({ block: "nearest", behavior: reducedMotion() ? "auto" : "smooth" });
const Glyph = ({ slug }) => <span className="glyph" aria-hidden="true">{GLYPH[slug] || slug.slice(0, 2)}</span>;
const toLines = text => text.split("\n").map(s => s.trim()).filter(Boolean).slice(0, MAX_TOPICS);

export function CreateForm({ presets, onStarted }) {
  const [text, setText] = useState("");
  const [community, setCommunity] = useState("general");
  const [language, setLanguage] = useState("en");
  const [duration, setDuration] = useState(30);
  const [style, setStyle] = useState("photo");
  const [every, setEvery] = useState(false);  // also make it in every other language
  const [talking, setTalking] = useState(false);  // the user's photo speaks the script instead of AI pictures
  const [photo, setPhoto] = useState("");  // data URL, already shrunk
  const [consent, setConsent] = useState(false);
  const [consentError, setConsentError] = useState("");
  const [layout, setLayout] = useState("both");  // presets.layouts: how the middle scenes mix the user in
  const consentRef = useRef();
  const [status, setStatus] = useState(HINT);
  const [ideas, setIdeas] = useState([]);
  const [ideasNote, setIdeasNote] = useState("");  // where the ideas came from, or why there are none
  const [busy, setBusy] = useState("");  // the button that is working: suggest | preview | start
  const [preview, setPreview] = useState(null);  // {topic, plan}
  const form = useRef();
  const topics = toLines(text);
  const options = { community, language, duration, style };
  const langs = presets.languages.length;
  const count = topics.length * (every ? langs : 1);
  const face = talking && photo ? { photo, photo_consent: consent, layout } : {};  // kept out of /plan: the script does not need the photo

  const changeText = value => { setText(value); setPreview(null); };
  const dropIdeas = () => { setIdeas([]); setIdeasNote(""); setPreview(null); };

  // a community with a non-English default (Hinglish Fun) switches the language; any change drops stale ideas
  const pickCommunity = c => {
    setCommunity(c.slug);
    if (c.language && c.language !== "en") setLanguage(c.language);
    dropIdeas();
  };

  // a talking video needs a photo and the consent tick; the problem is named next to the field that has it
  const faceReady = () => {
    if (!talking) return true;
    if (!photo) { setConsentError("Add a photo first, or switch back to AI pictures."); return false; }
    if (!consent) { setConsentError("Tick this to use the photo."); consentRef.current.focus(); return false; }
    return true;
  };

  const start = async (body, message) => {
    if (!faceReady()) return false;
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
    setBusy("suggest");
    try {
      const s = await api.suggest(community, language);
      setIdeas(s.topics.map(t => ({ text: t, added: topics.includes(t) })));
      setIdeasNote(s.trends.length ? "With today's trends in India" : `Ideas for ${presets.label(community)}`);
    } catch { setIdeas([]); setIdeasNote("Suggestions are unavailable right now. Type a topic instead."); }
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
    await start({ topics, ...options, all_languages: every, ...face }, message);
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
        <details className="menu drop" onKeyDown={escToClose} onToggle={e => { reveal(e.currentTarget); if (e.currentTarget.open && !ideas.length && busy !== "suggest") suggest(); }}>
          <summary className="btn"><Icon name="sparkles" />Suggest topics<Icon name="chevron" className="i chev" /></summary>
          <div className="pop ideas" aria-busy={busy === "suggest"}>
            <div className="pophead">
              <span>{busy === "suggest" ? "Finding ideas…" : <>{ideasNote.startsWith("With") && <Icon name="trending" />}{ideasNote}</>}</span>
              <button type="button" className="link" disabled={busy === "suggest"} onClick={suggest}><Icon name="refresh" />New ideas</button>
            </div>
            {busy !== "suggest" && ideas.map(i => (
              <button type="button" key={i.text} className={i.added ? "added" : ""} disabled={i.added} onClick={() => addIdea(i.text)}
                aria-label={i.added ? `${i.text}, added` : `Add ${i.text}`}>
                <span>{i.text}</span><Icon name={i.added ? "check" : "plus"} />
              </button>
            ))}
          </div>
        </details>
        <p className="hint">{status}</p>
        {preview && (
          <ScriptPreview key={preview.topic} {...preview} onClose={() => setPreview(null)}
            onMake={plan => start({ topics: [preview.topic], ...options, all_languages: every, plan, ...face },
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
      <div className="field"><span id="lang-label">3. Language</span>
        <details className="menu drop" onKeyDown={escToClose} onToggle={e => reveal(e.currentTarget)}>
          <summary className="sel pick" aria-labelledby="lang-label lang-now"><Glyph slug={language} /><span id="lang-now">{presets.label(language)}</span></summary>
          <div className="pop langs" role="group" aria-label="Language">
            {presets.languages.map(l => (
              <button type="button" key={l.slug} aria-pressed={language === l.slug} onClick={e => {
                setLanguage(l.slug); dropIdeas(); shut(e.currentTarget.closest("details"));
              }}><Glyph slug={l.slug} /><span>{l.label}</span>{language === l.slug && <Icon name="check" />}</button>
            ))}
          </div>
        </details>
      </div>
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
      <div className="field"><span>5. On screen</span>
        <div className="seg two" role="radiogroup" aria-label="On screen">
          <label>
            <input type="radio" name="screen" checked={!talking} onChange={() => { setTalking(false); setPhoto(""); }} /><span><Icon name="image" />AI pictures</span>
          </label>
          <label>
            <input type="radio" name="screen" checked={talking} onChange={() => setTalking(true)} /><span><Icon name="smile" />Me, talking</span>
          </label>
        </div>
      </div>
      {talking ? (
        <PresenterPhoto presets={presets} community={community} setPhoto={p => { setPhoto(p); setConsentError(""); }}
          layout={layout} setLayout={setLayout} consent={consent}
          setConsent={c => { setConsent(c); setConsentError(""); }} error={consentError} consentRef={consentRef} />
      ) : (
        <div className="field"><span>6. Look</span>
          <div className="seg" role="radiogroup" aria-label="Look">
            {presets.styles.map(s => (
              <label key={s.slug}>
                <input type="radio" name="style" value={s.slug} checked={style === s.slug} onChange={() => setStyle(s.slug)} /><span>{s.label}</span>
              </label>
            ))}
          </div>
        </div>
      )}

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
        <span><Icon name="clock" />{talking ? "About 3 minutes per video" : "About a minute per video"}</span>
        <span><kbd>Ctrl</kbd> <kbd>Enter</kbd> starts it</span>
      </p>
    </form>
  );
}
