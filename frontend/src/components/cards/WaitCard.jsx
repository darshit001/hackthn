import { useState } from "react";
import { STEP } from "../../lib/constants";
import { nth } from "../../lib/format";
import { Confirm } from "./Confirm";
import { Facts } from "./Facts";

// Queued and failed videos are quiet, compact cards with no clock; only the one being made is dark.
export function QueuedCard({ job, label, position, onDelete }) {
  const pos = nth(position);
  return (
    <article className="card wait tile">
      <div className="thumb screen dim"><span className="stage">{pos}</span></div>
      <div className="body">
        <div className="meta">
          <span className="status queued">Queued</span>
          <Facts job={job} label={label} />
        </div>
        <h3>{job.topic}</h3>
        <div className="actions">
          <p className="step">{pos}, waiting for the video before it</p>
          <button type="button" className="btn" onClick={e => { e.currentTarget.disabled = true; onDelete(job.id); }}>Remove</button>
        </div>
      </div>
    </article>
  );
}

export function FailedCard({ job, label, onRetry, onDelete }) {
  const [at, ...rest] = (job.error || "").split(":");
  const why = rest.join(":").trim() || "Something went wrong.";
  const [ask, setAsk] = useState(null);
  return (
    <article className={`card wait tile${job.stopped ? "" : " failed"}`}>
      <div className="thumb screen dim"><span className="stage"><small>Stopped at</small>{STEP[at] ? STEP[at][0] : at === "queue" ? "the queue" : at || "an unknown step"}</span></div>
      <div className="body">
        <div className="meta">
          {job.stopped ? <span className="status queued">Stopped</span> : <span className="status failed">Failed</span>}
          <Facts job={job} label={label} />
        </div>
        <h3>{job.topic}</h3>
        <p className={job.stopped ? "step" : "err"}>{why}</p>
        <div className="actions">
          <button type="button" className="btn" onClick={e => { e.currentTarget.disabled = true; onRetry(job); }}>Try again</button>
          <button type="button" className="btn del" onClick={async e => {
            if (!job.stopped) return setAsk(e.currentTarget);  // a video the user stopped goes without asking again
            const b = e.currentTarget;
            b.disabled = true;
            if (!(await onDelete(job.id))) b.disabled = false;
          }}>Delete</button>
        </div>
      </div>
      {ask && <Confirm title={`Delete "${job.topic}"?`} text="It is removed from your list." yes="Delete" busy="Deleting…"
        from={ask} onYes={() => onDelete(job.id)} onNo={() => setAsk(null)} />}
    </article>
  );
}
