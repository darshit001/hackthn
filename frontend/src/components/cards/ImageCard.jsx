import { useState } from "react";
import { ago, fileName } from "../../lib/format";
import { Icon } from "../Icon";
import { Facts } from "./Facts";
import { SaveButton } from "./SaveButton";

// The post text the Copy button puts on the clipboard; the headline is already on the picture
const postText = m => `${m.caption}\n\n${m.hashtags.join(" ")}`;
// the headline ends a sentence before the caption starts, unless it already does
const sentence = h => (/[.?!।]$/.test(h) ? h : `${h}.`);

// A finished image post: the 4:5 picture opens full size, the text is copied and pasted next to it on Qoneqt
export function ImageCard({ job, label, accent, onPlay, onCopy, onRedo, onDelete, onSave }) {
  const m = job.result, v = m.updated || 0;
  const image = `${m.image}?v=${v}`, thumb = `${m.thumb}?v=${v}`;
  const [deleting, setDeleting] = useState(false);
  const close = e => e.currentTarget.closest("details")?.removeAttribute("open");

  return (
    <article className="card post">
      <button type="button" className="thumb post" aria-label={`Open ${job.topic}`} onClick={() => onPlay({ id: job.id, image, thumb, topic: job.topic, alt: m.alt })}>
        <img src={thumb} alt={m.alt || ""} />
      </button>
      <div className="body">
        <div className="meta">
          <Facts job={job} label={label} accent={accent} length={false}>
            {m.style && m.style !== "photo" && <li>{label(m.style)} look</li>}
          </Facts>
          <time>{ago(job.created)}</time>
        </div>
        <h3>{job.topic}</h3>
        <p className="desc">{sentence(m.headline)} {m.caption}</p>
        <div className="actions">
          <button type="button" className="btn icon" aria-label="Copy post text" title="Copy post text" onClick={() => onCopy(postText(m), "Post text copied")}><Icon name="copy" /></button>
          <a className="btn icon" href={m.image} download={fileName(job.topic).replace(/\.mp4$/, ".png")} aria-label="Download PNG" title="Download PNG"><Icon name="download" /></a>
          <details className="menu">
            <summary className="btn icon" aria-label="More actions"><Icon name="more" className="i fill" /></summary>
            <div className="pop">
              <button type="button" onClick={e => { close(e); onRedo(job.id, 0, true); }}>New picture, same text</button>
              <hr />
              <button type="button" className="del" disabled={deleting} onClick={async () => {
                if (!confirm(`Delete "${job.topic}"? The image and its post text are removed from the server.`)) return;
                setDeleting(true);
                if (!(await onDelete(job.id))) setDeleting(false);
              }}>{deleting ? "Deleting…" : "Delete image"}</button>
            </div>
          </details>
          <SaveButton saved={!!job.saved} onClick={() => onSave(job.id, !job.saved)} />
        </div>
      </div>
    </article>
  );
}
