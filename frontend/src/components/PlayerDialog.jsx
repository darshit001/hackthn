import { useEffect, useRef, useState } from "react";
import { FORMULA } from "../lib/constants";
import { ago, mmss, postText, talked } from "../lib/format";
import { related } from "../lib/library";
import { Icon } from "./Icon";
import { Facts } from "./cards/Facts";
import { MoreMenu } from "./cards/MoreMenu";
import { SaveButton } from "./cards/SaveButton";

const TABS = [["post", "Post"], ["details", "Details"], ["script", "Script"]];
const VOICE = { elevenlabs: "ElevenLabs", edge: "Edge TTS", gemini: "Gemini TTS" };
// a caption line that opens with an emoji or a bullet is a point; the lines before the first and after the last stay prose
const POINT = /^(\p{Extended_Pictographic}(\uFE0F|\u200D\p{Extended_Pictographic})*|[•●▪◆*-])\s*/u;
function Caption({ text }) {
  const lines = text.split("\n").map(s => s.trim()).filter(Boolean);
  const first = lines.findIndex(l => POINT.test(l)), last = lines.findLastIndex(l => POINT.test(l));
  const prose = part => part.map((l, i) => <p key={i}>{l}</p>);
  if (first < 0) return prose(lines);
  return (
    <>
      {prose(lines.slice(0, first))}
      <ul className="points">
        {lines.slice(first, last + 1).map((l, i) => {
          const mark = l.match(POINT)?.[0] || "";
          return <li key={i}><span aria-hidden="true">{mark.trim()}</span><span>{l.slice(mark.length)}</span></li>;
        })}
      </ul>
      {prose(lines.slice(last + 1))}
    </>
  );
}

const took = s => s >= 60 ? `${Math.floor(s / 60)} min ${Math.round(s % 60)} s` : `${Math.round(s)} s`;

// The watch view: one native <dialog> with the vertical video on the left and, beside it, what to post, how it was made,
// the script scene by scene and more videos to jump to. `job` is a finished job or null. An image post shows its picture instead,
// and a carousel's slides step with the ‹ › buttons or the arrow keys.
export function PlayerDialog({ job, jobs, label, actions, onOpen, onClose }) {
  const dialog = useRef(), sheet = useRef();
  const [tab, setTab] = useState("post");
  const [at, setAt] = useState(0);

  useEffect(() => {
    const d = dialog.current;
    if (job && !d.open) d.showModal();
    else if (!job && d.open) d.close();
  }, [job]);
  // another video opens at its top, on the Post tab
  useEffect(() => { setTab("post"); setAt(0); sheet.current?.scrollTo(0, 0); }, [job?.id]);

  const m = job?.result, v = m?.updated || 0;
  const thumb = m && `${m.thumb}?v=${v}`;
  const slides = job?.kind === "image" ? (m.slides || [{ image: m.image }]).map(x => `${x.image}?v=${v}`) : [];  // older posts have no slides
  const go = step => setAt(i => Math.min(slides.length - 1, Math.max(0, i + step)));
  const voice = m && [...new Set((m.scenes || []).map(sc => VOICE[sc.voice]).filter(Boolean))].join(", ");
  const details = m ? [
    ["Hook", m.hook_formula && `${FORMULA[m.hook_formula] || m.hook_formula}${m.hook_score ? `, scored ${m.hook_score}/10` : ""}`],
    ["Why this hook", m.hook_why],
    ["Look", m.presenter ? talked(m) : label(m.style || "photo")],
    ["Voice", voice],
    ["Music", m.music],
    ["Script by", m.llm],
    ["Pictures by", m.image_model],
    ["Made in", m.seconds_to_make && took(m.seconds_to_make)],
    ["Created", ago(job.created)],
  ].filter(([, val]) => val) : [];
  const more = job ? related(jobs, job) : [];

  return (
    <dialog ref={dialog} className="watch" aria-label={job ? `Watch ${job.topic}` : "Video player"} onClose={onClose}
      onKeyDown={e => { if (slides.length > 1 && (e.key === "ArrowLeft" || e.key === "ArrowRight")) { e.preventDefault(); go(e.key === "ArrowLeft" ? -1 : 1); } }}
      onClick={e => e.target === dialog.current && onClose() /* the backdrop is the dialog's own box */}>
      {job && <>
        <div className="stage">
          {slides.length ? <>
            <img className="post" src={slides[at]} alt={m.alt || ""} />
            {slides.length > 1 && <>
              <button type="button" className="nav prev" aria-label="Previous slide" disabled={at === 0} onClick={() => go(-1)}><Icon name="left" /></button>
              <button type="button" className="nav next" aria-label="Next slide" disabled={at === slides.length - 1} onClick={() => go(1)}><Icon name="right" /></button>
              <span className="count" aria-live="polite">Slide {at + 1} of {slides.length}</span>
            </>}
          </> : <video key={job.id} controls autoPlay playsInline poster={thumb} src={`${m.video}?v=${v}`} />}
        </div>
        <div className="sheet" ref={sheet}>
          <div className="titlebar">
            <h2>{job.topic}</h2>
            <button type="button" className="btn icon x" aria-label="Close" onClick={onClose}><Icon name="x" /></button>
          </div>
          <Facts job={job} label={label} length={false}>
            {m.duration != null && <li><Icon name="clock" />{mmss(m.duration)}</li>}
            {m.style && m.style !== "photo" && !m.presenter && <li><Icon name="image" />{label(m.style)} look</li>}
          </Facts>
          <div className="actions">
            {slides.length ? <a className="btn ink" href={slides.length > 1 ? m.zip : m.image} download title={slides.length > 1 ? "All slides in one ZIP" : "The picture as a PNG"}><Icon name="download" />Download</a>
              : <a className="btn ink" href={`/jobs/${job.id}/download`} download title="Video, cover and post text in one ZIP"><Icon name="download" />Download</a>}
            <SaveButton saved={!!job.saved} onClick={() => actions.onSave(job.id, !job.saved)} />
            <MoreMenu job={job} thumb={thumb} onCopy={actions.onCopy} onRedo={actions.onRedo} onDelete={actions.onDelete} />
          </div>

          <div className="tabs" role="tablist">
            {TABS.filter(([key]) => key !== "script" || m.scenes).map(([key, name]) => (
              <button type="button" role="tab" key={key} aria-selected={tab === key} onClick={() => setTab(key)}>{name}</button>
            ))}
          </div>
          {tab === "post" && (
            <div className="pane" role="tabpanel">
              <p className="hook">{m.hook || m.headline}</p>
              <Caption text={m.caption} />
              {m.hashtags.length > 0 && <p className="tags">{m.hashtags.map(h => <span className="tag" key={h}>{h}</span>)}</p>}
              <button type="button" className="btn" onClick={() => actions.onCopy(postText(m), "Post text copied")}><Icon name="copy" />Copy post text</button>
            </div>
          )}
          {tab === "details" && (
            <dl className="pane" role="tabpanel">
              {details.map(([k, val]) => <div key={k}><dt>{k}</dt><dd>{val}</dd></div>)}
            </dl>
          )}
          {tab === "script" && (
            <ol className="pane script" role="tabpanel">
              {m.scenes.map((sc, i) => (
                <li key={i}>
                  <div className="row">
                    <b>{sc.title || `Scene ${i + 1}`}</b>
                    <span>{sc.seconds ? `${Math.round(sc.seconds)} s` : ""}</span>
                    <button type="button" className="btn small" disabled={job.status !== "done"} onClick={() => actions.onRedo(job.id, i)}
                      title={`Make scene ${i + 1} again with a new picture`}><Icon name="refresh" />Redo</button>
                  </div>
                  <p>{sc.narration}</p>
                </li>
              ))}
            </ol>
          )}

          {more.length > 0 && <>
            <h3 className="more">More videos</h3>
            <div className="minis">
              {more.map(j => (
                <button type="button" key={j.id} className="mini" onClick={() => onOpen(j.id)}>
                  <span className="thumb"><img src={`${j.result.thumb}?v=${j.result.updated || 0}`} alt="" loading="lazy" />{j.result.duration != null && <span className="dur">{mmss(j.result.duration)}</span>}</span>
                  <span className="name">{j.topic}</span>
                </button>
              ))}
            </div>
          </>}
        </div>
      </>}
    </dialog>
  );
}
