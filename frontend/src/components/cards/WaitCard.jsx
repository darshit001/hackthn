import { STEP } from "../../lib/constants";
import { ago, nth } from "../../lib/format";
import { Facts } from "./Facts";

// Queued and failed videos are quiet, compact rows; only the one being made is dark.
export function QueuedCard({ job, label, position }) {
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
      <div className="side"><time>Added {ago(job.created)}</time></div>
    </article>
  );
}

export function FailedCard({ job, label, onRetry }) {
  const [at, ...rest] = (job.error || "").split(":");
  const why = rest.join(":").trim() || "Something went wrong.";
  return (
    <article className="card failed wait">
      <div className="thumb screen dim"><span className="stage"><small>Stopped at</small>{STEP[at] ? STEP[at][0] : at || "an unknown step"}</span></div>
      <div className="body">
        <span className="status failed">Failed</span>
        <h3>{job.topic}</h3>
        <p className="err">{why}</p>
        <Facts job={job} label={label} />
      </div>
      <div className="side">
        <time>Started {ago(job.created)}</time>
        <div className="actions"><button type="button" className="btn" onClick={e => { e.currentTarget.disabled = true; onRetry(job); }}>Try again</button></div>
      </div>
    </article>
  );
}
