import { useState } from "react";
import { ago, postText } from "../../lib/format";
import { Icon } from "../Icon";
import { Confirm } from "./Confirm";

// The ⋮ menu of a finished video, on its card and in the watch view: when it was made, copy, redo a scene, delete.
export function MoreMenu({ job, thumb, onCopy, onRedo, onDelete }) {
  const m = job.result;
  const [ask, setAsk] = useState(null);  // the ⋮ button to focus again when the question closes
  const close = e => e.currentTarget.closest("details")?.removeAttribute("open");

  return (
    <>
      <details className="menu">
        <summary className="btn icon" aria-label="More actions" title="More actions"><Icon name="more" className="i fill" /></summary>
        <div className="pop">
          <div className="pophead">Made {ago(job.created)}</div>
          <button type="button" onClick={e => { close(e); onCopy(postText(m), "Post text copied"); }}>Copy post text</button>
          <hr />
          {m.scenes.map((sc, i) => (
            <button type="button" key={i} onClick={e => { close(e); onRedo(job.id, i); }}>Redo scene {i + 1}: {sc.title || sc.query}</button>
          ))}
          <hr />
          <button type="button" className="del" onClick={e => { setAsk(e.currentTarget.closest("details").querySelector("summary")); close(e); }}>Delete video</button>
        </div>
      </details>
      {ask && <Confirm title={`Delete "${job.topic}"?`} text="The video and its post text are removed from the server. This can't be undone."
        yes="Delete video" busy="Deleting…" thumb={thumb} from={ask} onYes={() => onDelete(job.id)} onNo={() => setAsk(null)} />}
    </>
  );
}
