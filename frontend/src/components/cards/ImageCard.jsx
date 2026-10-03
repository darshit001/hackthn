import { Icon } from "../Icon";
import { Facts } from "./Facts";
import { MoreMenu } from "./MoreMenu";
import { SaveButton } from "./SaveButton";

// A finished image post as a tile: the 4:5 picture (or a carousel's first slide) opens the watch view, the text is copied and pasted next to it on Qoneqt
export function ImageCard({ job, label, onPlay, onCopy, onRedo, onDelete, onSave }) {
  const m = job.result, v = m.updated || 0;
  const thumb = `${m.thumb}?v=${v}`;
  const many = m.slides?.length > 1;  // a carousel downloads as one zip of its slides; older posts have no slides

  return (
    <article className="card tile">
      <button type="button" className="thumb" aria-label={`Open ${job.topic}`} onClick={() => onPlay(job.id)}>
        <img src={thumb} alt={m.alt || ""} />
        {m.style && m.style !== "photo" && <span className="badge">{label(m.style)}</span>}
        {many && <span className="dur">{m.slides.length} slides</span>}
      </button>
      <SaveButton saved={!!job.saved} onClick={() => onSave(job.id, !job.saved)} />
      <div className="body">
        <h3 title={`${m.headline} ${m.caption}`}>{job.topic}</h3>
        <div className="foot">
          <Facts job={job} label={label} length={false} />
          <div className="actions">
            <a className="btn icon" href={many ? m.zip : m.image} download aria-label={many ? "Download all slides (ZIP)" : "Download PNG"} title={many ? "Download all slides (ZIP)" : "Download PNG"}><Icon name="download" /></a>
            <MoreMenu job={job} thumb={thumb} onCopy={onCopy} onRedo={onRedo} onDelete={onDelete} />
          </div>
        </div>
      </div>
    </article>
  );
}
