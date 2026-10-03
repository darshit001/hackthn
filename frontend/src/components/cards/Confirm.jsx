import { useEffect, useId, useRef, useState } from "react";

// Asks before a card deletes or stops: a popup with the video's thumbnail beside the question, instead of the browser's
// confirm(). Cancel starts focused; Escape or a click outside cancels; focus goes back to `from`, the control that asked.
// onYes returns false when it failed, so the user can try again.
export function Confirm({ title, text, yes, busy, thumb, from, onYes, onNo }) {
  const [working, setWorking] = useState(false);
  const box = useRef(null), no = useRef(null), id = useId();
  useEffect(() => {
    if (!box.current.open) box.current.showModal();
    no.current.focus();
    return () => from?.focus();
  }, [from]);
  const cancel = () => !working && onNo();

  return (
    <dialog ref={box} className="ask" role="alertdialog" aria-labelledby={`${id}t`} aria-describedby={`${id}d`}
      onCancel={e => { e.preventDefault(); cancel(); }} onClick={e => e.target === box.current && cancel()}>
      <div className="box">
        {thumb && <img src={thumb} alt="" />}
        <div>
          <h3 id={`${id}t`}>{title}</h3>
          <p id={`${id}d`}>{text}</p>
          <div className="actions">
            <button type="button" className="btn" ref={no} disabled={working} onClick={onNo}>Cancel</button>
            <button type="button" className="btn danger" disabled={working} onClick={async () => {
              setWorking(true);
              if (!(await onYes())) setWorking(false);
            }}>{working ? busy : yes}</button>
          </div>
        </div>
      </div>
    </dialog>
  );
}
