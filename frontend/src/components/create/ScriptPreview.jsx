import { useState } from "react";
import { FORMULA } from "../../lib/constants";

// The exact plan the pipeline would use, with the scored hooks to pick from.
export function ScriptPreview({ topic, plan, onMake, onClose }) {
  const hooks = (plan.hooks || []).filter(h => h && h.text);
  if (!hooks.some(h => h.text === plan.hook)) hooks.unshift({ text: plan.hook });
  const [hook, setHook] = useState(plan.hook);
  const [starting, setStarting] = useState(false);

  // the chosen hook replaces the old one at the start of the first scene's narration
  const make = async () => {
    const p = structuredClone(plan), s0 = p.scenes[0];
    s0.narration = s0.narration.startsWith(p.hook) ? hook + s0.narration.slice(p.hook.length) : `${hook} ${s0.narration}`;
    p.hook = hook;
    setStarting(true);
    if (!(await onMake(p))) setStarting(false);
  };

  return (
    <div className="preview">
      <h2>Script for “{topic}”</h2>
      <p className="hint">Pick the opening line. The scenes below stay as written.</p>
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
        {plan.scenes.map((sc, i) => (
          <li key={i}>{sc.beat && <><span className="beat">{sc.beat}</span> </>}<b>{sc.title || ""}</b> {sc.narration}</li>
        ))}
      </ol>
      <div className="actions" style={{ justifyContent: "flex-start" }}>
        <button type="button" className="primary small" disabled={starting} onClick={make}>Generate with this hook</button>
        <button type="button" className="btn" onClick={onClose}>Close</button>
      </div>
    </div>
  );
}
