import { useState } from "react";
import { ago, canHover, mmss, reducedMotion } from "../../lib/format";
import { Icon } from "../Icon";
import { Confirm } from "./Confirm";
import { Facts } from "./Facts";
import { SaveButton } from "./SaveButton";

// The post text the Copy button puts on the clipboard
const postText = m => `${m.hook}\n\n${m.caption}\n\n${m.hashtags.join(" ")}`;
const PREVIEW = canHover() && !reducedMotion();  // hovering a thumbnail plays it silently, the way a feed does

// a scene whose free GPU ran out shows the still photo; the count tells the user which videos a Redo scene would improve
const talked = m => {
  const faces = m.scenes.filter(sc => sc.face), n = faces.filter(sc => sc.face !== "photo").length;
  return n === faces.length ? "You, talking" : `You, talking in ${n} of ${faces.length} scenes`;
};

export function ReadyCard({ job, label, onPlay, onCopy, onRedo, onDelete, onSave }) {
  const m = job.result, v = m.updated || 0;
  const video = `${m.video}?v=${v}`, thumb = `${m.thumb}?v=${v}`;
  const [hover, setHover] = useState(false);
  const [ask, setAsk] = useState(null);  // the ⋮ button to focus again when the question closes
  const close = e => e.currentTarget.closest("details")?.removeAttribute("open");

  return (
    <article className="card tile">
      <button type="button" className="thumb" aria-label={`Play ${job.topic}`} onClick={() => onPlay({ id: job.id, video, thumb, topic: job.topic })}
        onMouseEnter={() => PREVIEW && setHover(true)} onMouseLeave={() => setHover(false)}>
        <img src={thumb} alt="" />
        {hover && <video className="peek" src={video} muted loop playsInline autoPlay />}
        <Icon name="play" className="i fill play" />
        {m.presenter ? <span className="badge">{talked(m)}</span>
          : m.style && m.style !== "photo" && <span className="badge">{label(m.style)}</span>}
        <span className="dur">{mmss(m.duration)}</span>
      </button>
      <SaveButton saved={!!job.saved} onClick={() => onSave(job.id, !job.saved)} />
      <div className="body">
        <h3 title={`${m.hook} ${m.caption}`}>{job.topic}</h3>
        <div className="foot">
          <Facts job={job} label={label} length={false} />
          <div className="actions">
            <a className="btn icon" href={`/jobs/${job.id}/download`} download aria-label="Download video, cover and caption as a ZIP" title="Download video, cover and caption (ZIP)"><Icon name="download" /></a>
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
          </div>
        </div>
      </div>
      {ask && <Confirm title={`Delete "${job.topic}"?`} text="The video and its post text are removed from the server. This can't be undone."
        yes="Delete video" busy="Deleting…" thumb={thumb} from={ask} onYes={() => onDelete(job.id)} onNo={() => setAsk(null)} />}
    </article>
  );
}
