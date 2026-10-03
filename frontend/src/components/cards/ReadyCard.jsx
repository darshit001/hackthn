import { useState } from "react";
import { canHover, mmss, reducedMotion, talked } from "../../lib/format";
import { Icon } from "../Icon";
import { Facts } from "./Facts";
import { MoreMenu } from "./MoreMenu";
import { SaveButton } from "./SaveButton";

const PREVIEW = canHover() && !reducedMotion();  // hovering a thumbnail plays it silently, the way a feed does

export function ReadyCard({ job, label, onPlay, onCopy, onRedo, onDelete, onSave }) {
  const m = job.result, v = m.updated || 0;
  const video = `${m.video}?v=${v}`, thumb = `${m.thumb}?v=${v}`;
  const [hover, setHover] = useState(false);

  return (
    <article className="card tile">
      <button type="button" className="thumb" aria-label={`Play ${job.topic}`} onClick={() => onPlay(job.id)} style={{ "--cover": `url("${thumb}")` }}
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
            <MoreMenu job={job} thumb={thumb} onCopy={onCopy} onRedo={onRedo} onDelete={onDelete} />
          </div>
        </div>
      </div>
    </article>
  );
}
