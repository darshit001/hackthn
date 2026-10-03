import { useId, useLayoutEffect, useRef, useState } from "react";
import { FORMULA } from "../../lib/constants";

const cap = i => (i ? 25 : 40);  // the backend's narration limits: the first scene carries the hook
const words = s => (s.trim() ? s.trim().split(/\s+/).length : 0);

// a narration box is exactly as tall as its text, on first render and on every edit
function Narration(props) {
  const ref = useRef();
  useLayoutEffect(() => {
    const t = ref.current;
    t.style.height = "auto";
    t.style.height = `${t.scrollHeight}px`;
  }, [props.value]);
  return <textarea ref={ref} rows={1} className="nar" {...props} />;
}

// The exact plan the pipeline would use: pick a scored hook, edit any scene's title or narration.
export function ScriptPreview({ topic, plan, onMake, onClose }) {
  const hooks = (plan.hooks || []).filter(h => h && h.text);
  if (!hooks.some(h => h.text === plan.hook)) hooks.unshift({ text: plan.hook });
  const [hook, setHook] = useState(plan.hook);
  const [edits, setEdits] = useState(() => plan.scenes.map(s => ({ title: s.title || "", narration: s.narration })));
  const [starting, setStarting] = useState(false);
  const uid = useId();
  const edit = (i, key, value) => setEdits(list => list.map((e, j) => (j === i ? { ...e, [key]: value } : e)));

  const make = async () => {
    const p = structuredClone(plan), s0 = p.scenes[0];
    p.scenes.forEach((sc, i) => {
      const title = edits[i].title.trim(), narration = edits[i].narration.trim().replace(/\s+/g, " ");
      if (title) sc.title = title;  // an emptied field keeps the original
      if (narration) sc.narration = narration;
    });
    // the chosen hook replaces the old one at the start of the first scene; only on a real swap, or an edit inside the hook gets it twice
    if (hook !== p.hook) s0.narration = s0.narration.startsWith(p.hook) ? hook + s0.narration.slice(p.hook.length) : `${hook} ${s0.narration}`;
    p.hook = hook;
    setStarting(true);
    if (!(await onMake(p))) setStarting(false);
  };

  // the preview sits inside the create form: Enter in a field must not submit it
  const noSubmit = e => { if (e.key === "Enter" && e.target.tagName === "INPUT") e.preventDefault(); };

  return (
    <div className="preview" onKeyDown={noSubmit}>
      <h2>Script for “{topic}”</h2>
      <p className="hint">Pick the opening line and edit any line. Nothing is spent until you generate.</p>
      <div className="hooks">
        {hooks.map(h => (
          <label key={h.text}>
            <input type="radio" name="hook" checked={hook === h.text} onChange={() => setHook(h.text)} />
            <span className="text">{h.text}{h.why && <em className="why">{h.why}</em>}</span>
            {h.formula && <span className="tag">{FORMULA[h.formula] || h.formula}</span>}
            {h.score && <small>{h.score}/10</small>}
          </label>
        ))}
      </div>
      <ol className="scenes">
        {edits.map((e, i) => {
          const n = words(e.narration), wc = `${uid}-wc${i}`;
          return (
            <li key={i}>
              {plan.scenes[i].beat && <span className="beat">{plan.scenes[i].beat}</span>}
              <input className="title" aria-label={`Scene ${i + 1} title`} value={e.title} onChange={ev => edit(i, "title", ev.target.value)} />
              <Narration aria-label={`Scene ${i + 1} narration`} aria-describedby={wc} value={e.narration} onChange={ev => edit(i, "narration", ev.target.value)} />
              <small id={wc} className={n > cap(i) ? "wc over" : "wc"}>{n}/{cap(i)}</small>
            </li>
          );
        })}
      </ol>
      <div className="actions" style={{ justifyContent: "flex-start" }}>
        <button type="button" className="primary small" disabled={starting} onClick={make}>Generate this script</button>
        <button type="button" className="btn" onClick={onClose}>Close</button>
      </div>
    </div>
  );
}
