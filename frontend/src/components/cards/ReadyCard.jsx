import { useState } from "react";
import { ago, canHover, fileName, mmss, reducedMotion } from "../../lib/format";
import { Icon } from "../Icon";
import { Facts } from "./Facts";

// The post text the Copy buttons put on the clipboard
function postText(m, kind) {
  if (kind === "yt") return `${m.posts.youtube_title}\n\n${m.posts.youtube_description}`;
  if (kind === "ig") return `${m.posts.instagram}\n\n${m.hashtags.join(" ")}`;
  return `${m.hook}\n\n${m.caption}\n\n${m.hashtags.join(" ")}`;
}
const COPIED = { yt: "YouTube text copied", ig: "Instagram text copied", post: "Post text copied" };
const PREVIEW = canHover() && !reducedMotion();  // hovering a thumbnail plays it silently, the way a feed does

// a scene whose free GPU ran out shows the still photo; the count tells the user which videos a Redo scene would improve
const talked = m => {
  const faces = m.scenes.filter(sc => sc.face), n = faces.filter(sc => sc.face !== "photo").length;
  return n === faces.length ? "You, talking" : `You, talking in ${n} of ${faces.length} scenes`;
};

export function ReadyCard({ job, label, onPlay, onCopy, onRedo, onDelete }) {
  const m = job.result, v = m.updated || 0;
  const video = `${m.video}?v=${v}`, thumb = `${m.thumb}?v=${v}`;
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
          {m.presenter ? <li><Icon name="smile" />{talked(m)}</li>
            : m.style && m.style !== "photo" && <li><Icon name="image" />{label(m.style)} look</li>}
        </Facts>
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
