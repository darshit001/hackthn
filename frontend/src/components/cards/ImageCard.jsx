import { useState } from "react";
import { ago, fileName } from "../../lib/format";
import { Icon } from "../Icon";
import { Caption } from "./Caption";
import { Confirm } from "./Confirm";
import { Facts } from "./Facts";
import { SaveButton } from "./SaveButton";

// The post text the Copy button puts on the clipboard; the headline is already on the picture
const postText = m => `${m.caption}\n\n${m.hashtags.join(" ")}`;
// the headline ends a sentence before the caption starts, unless it already does
const sentence = h => (/[.?!।]$/.test(h) ? h : `${h}.`);

// A finished image post: the 4:5 picture (or a carousel's slides) opens full size, the text is copied and pasted next to it on Qoneqt
export function ImageCard({ job, label, accent, onPlay, onCopy, onRedo, onDelete, onSave }) {
  const m = job.result, v = m.updated || 0;
  const thumb = `${m.thumb}?v=${v}`;
  const slides = (m.slides || [{ image: m.image, text: m.headline }]).map(x => ({ ...x, src: `${x.image}?v=${v}` }));  // older posts have no slides
  const many = slides.length > 1;  // a carousel downloads as one zip of its slides
  const [download, file] = many ? [m.zip, fileName(job.topic).replace(/\.mp4$/, ".zip")] : [m.image, fileName(job.topic).replace(/\.mp4$/, ".png")];
  const [ask, setAsk] = useState(null);  // the ⋮ button to focus again when the question closes
  const close = e => e.currentTarget.closest("details")?.removeAttribute("open");

  return (
    <article className="card post">
      <button type="button" className="thumb post" aria-label={`Open ${job.topic}`} onClick={() => onPlay({ id: job.id, slides: slides.map(x => x.src), download, file, thumb, topic: job.topic, alt: m.alt })}>
        <img src={thumb} alt={m.alt || ""} />
        {many && <span className="dur">{slides.length} slides</span>}
      </button>
      <div className="body">
        <div className="meta">
          <Facts job={job} label={label} accent={accent} length={false}>
            {m.style && m.style !== "photo" && <li>{label(m.style)} look</li>}
          </Facts>
          <time>{ago(job.created)}</time>
        </div>
        <h3>{job.topic}</h3>
        <Caption text={`${sentence(m.headline)} ${m.caption}`} tags={m.hashtags} />
        <div className="actions">
          <button type="button" className="btn icon" aria-label="Copy post text" title="Copy post text" onClick={() => onCopy(postText(m), "Post text copied")}><Icon name="copy" /></button>
          <a className="btn icon" href={download} download={file} aria-label={many ? "Download all slides (ZIP)" : "Download PNG"} title={many ? "Download all slides (ZIP)" : "Download PNG"}><Icon name="download" /></a>
          <details className="menu">
            <summary className="btn icon" aria-label="More actions"><Icon name="more" className="i fill" /></summary>
            <div className="pop">
              {many ? slides.map((x, i) => (
                <button type="button" key={i} onClick={e => { close(e); onRedo(job.id, i, true); }}>New picture for slide {i + 1}: {x.text}</button>
              )) : <button type="button" onClick={e => { close(e); onRedo(job.id, 0, true); }}>New picture, same text</button>}
              <hr />
              <button type="button" className="del" onClick={e => { setAsk(e.currentTarget.closest("details").querySelector("summary")); close(e); }}>{many ? "Delete carousel" : "Delete image"}</button>
            </div>
          </details>
          <SaveButton saved={!!job.saved} onClick={() => onSave(job.id, !job.saved)} />
        </div>
      </div>
      {ask && <Confirm title={`Delete "${job.topic}"?`} text={`The ${many ? "slides" : "image"} and the post text are removed from the server. This can't be undone.`}
        yes={many ? "Delete carousel" : "Delete image"} busy="Deleting…" thumb={thumb} from={ask} onYes={() => onDelete(job.id)} onNo={() => setAsk(null)} />}
    </article>
  );
}
