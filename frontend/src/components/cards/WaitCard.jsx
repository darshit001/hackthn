import { STEP } from "../../lib/constants";
import { ago, nth } from "../../lib/format";
import { Facts } from "./Facts";

// Queued and failed videos are quiet, compact rows; only the one being made is dark.
export function QueuedCard({ job, label, position, onDelete }) {
  const pos = nth(position);
  return (
    <article className="card wait">
      <div className="thumb screen dim"><span className="stage">{pos}</span></div>
      <div className="body">
        <span className="status queued">Queued</span>
        <h3>{job.topic}</h3>
        <p className="step">{pos}, waiting for the video before it</p>
        <Facts job={job} label={label} />
      </div>
      <div className="side">
        <time>Added {ago(job.created)}</time>
        <div className="actions"><button type="button" className="btn" onClick={e => { e.currentTarget.disabled = true; onDelete(job.id); }}>Remove</button></div>
      </div>
    </article>
  );
}

export function FailedCard({ job, label, onRetry, onDelete }) {
  const [at, ...rest] = (job.error || "").split(":");
  const why = rest.join(":").trim() || "Something went wrong.";
  return (
    <article className={`card wait${job.stopped ? "" : " failed"}`}>
      <div className="thumb screen dim"><span className="stage"><small>Stopped at</small>{STEP[at] ? STEP[at][0] : at === "queue" ? "the queue" : at || "an unknown step"}</span></div>
      <div className="body">
        {job.stopped ? <span className="status queued">Stopped</span> : <span className="status failed">Failed</span>}
        <h3>{job.topic}</h3>
        <p className={job.stopped ? "step" : "err"}>{why}</p>
        <Facts job={job} label={label} />
      </div>
      <div className="side">
        <time>Started {ago(job.created)}</time>
        <div className="actions">
          <button type="button" className="btn" onClick={e => { e.currentTarget.disabled = true; onRetry(job); }}>Try again</button>
          <button type="button" className="btn del" onClick={async e => {
            if (!job.stopped && !confirm(`Delete "${job.topic}"?`)) return;
            const b = e.currentTarget;
            b.disabled = true;
            if (!(await onDelete(job.id))) b.disabled = false;
          }}>Delete</button>
        </div>
      </div>
    </article>
  );
}
