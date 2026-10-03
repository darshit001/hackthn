import { useState } from "react";
import { FORMULA, VOICE } from "../../lib/constants";
import { ago, canHover, fileName, mmss, reducedMotion } from "../../lib/format";
import { Icon } from "../Icon";
import { Facts } from "./Facts";

// The post text the Copy buttons put on the clipboard
function postText(m, kind) {
  if (kind === "yt") return `${m.posts.youtube_title}\n\n${m.posts.youtube_description}`;
  if (kind === "ig") return `${m.posts.instagram}\n\n${m.hashtags.join(" ")}`;
  return `${m.hook}\n\n${m.caption}\n\n${m.hashtags.join(" ")}`;
}
// the brand-safety pass: nothing when it did not run (older videos, or the reviewer was unavailable)
function reviewText(r) {
  if (!r || r.verdict === "skipped") return "";
  if (r.verdict === "ok") return "Brand-safe";
  const n = r.changed ?? r.notes.length;
  return n > 0 ? `Reviewed, ${n} line${n === 1 ? "" : "s"} softened` : "Reviewed";
}
const COPIED = { yt: "YouTube text copied", ig: "Instagram text copied", post: "Post text copied" };
const PREVIEW = canHover() && !reducedMotion();  // hovering a thumbnail plays it silently, the way a feed does

export function ReadyCard({ job, label, sourceJob, onPlay, onCopy, onRedo, onDelete }) {
  const m = job.result, v = m.updated || 0;
  const video = `${m.video}?v=${v}`, thumb = `${m.thumb}?v=${v}`;
  const review = reviewText(m.review);
  const voice = VOICE[m.scenes[0].voice] || m.scenes[0].voice;
  const [hover, setHover] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const close = e => e.currentTarget.closest("details")?.removeAttribute("open");

  return (
    <article className="card">
      <button type="button" className="thumb" aria-label={`Play ${job.topic}`} onClick={() => onPlay({ video, thumb, topic: job.topic })}
        onMouseEnter={() => PREVIEW && setHover(true)} onMouseLeave={() => setHover(false)}>
        <img src={thumb} alt="" />
        {hover && <video className="peek" src={video} muted loop playsInline autoPlay />}
        <Icon name="play" className="i fill play" />
        <span className="dur">{mmss(m.duration)}</span>
      </button>
      <div className="body">
        <span className="status ready">Ready</span>
        <h3>{job.topic}</h3>
        <p className="desc">{m.hook} {m.caption}</p>
        <Facts job={job} label={label}>
          <li><Icon name="mic" />{voice} voice</li>
          {m.hook_formula && <li><Icon name="bolt" />{FORMULA[m.hook_formula] || m.hook_formula} hook, {m.hook_score}/10</li>}
          {m.seconds_to_make && <li><Icon name="timer" />Made in {mmss(m.seconds_to_make)}</li>}
          {m.style && m.style !== "photo" && <li><Icon name="image" />{label(m.style)} look</li>}
          {review && <li title={m.review.notes.join("\n")}><Icon name="shield" />{review}</li>}
          {m.source && <li><Icon name="copy" />Visuals shared with {(sourceJob && label(sourceJob.language)) || "the first version"}</li>}
        </Facts>
        <div className="tags">{m.hashtags.map(t => <span className="tag" key={t}>{t}</span>)}</div>
      </div>
      <div className="side">
        <time>Created {ago(job.created)}</time>
        <div className="actions">
          <button type="button" className="btn" onClick={() => onCopy(postText(m, "post"), COPIED.post)}><Icon name="copy" />Copy text</button>
          <a className="btn" href={m.video} download={fileName(job.topic)}><Icon name="download" />Download MP4</a>
          <details className="menu">
            <summary className="btn icon" aria-label="More actions"><Icon name="more" className="i fill" /></summary>
            <div className="pop">
              {m.posts && <>
                <button type="button" onClick={e => { close(e); onCopy(postText(m, "yt"), COPIED.yt); }}>Copy for YouTube</button>
                <button type="button" onClick={e => { close(e); onCopy(postText(m, "ig"), COPIED.ig); }}>Copy for Instagram</button>
                <hr />
              </>}
              {m.scenes.map((sc, i) => (
                <button type="button" key={i} onClick={e => { close(e); onRedo(job.id, i); }}>Redo scene {i + 1}: {sc.title || sc.query}</button>
              ))}
              <hr />
              <button type="button" className="del" disabled={deleting} onClick={async () => {
                if (!confirm(`Delete "${job.topic}"? The video and its post text are removed from the server.`)) return;
                setDeleting(true);
                if (!(await onDelete(job.id))) setDeleting(false);
              }}>{deleting ? "Deleting…" : "Delete video"}</button>
            </div>
          </details>
        </div>
      </div>
    </article>
  );
}
