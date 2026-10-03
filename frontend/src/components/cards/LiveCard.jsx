import { useEffect, useState } from "react";
import { STAGES, STEP } from "../../lib/constants";
import { ago, cap, mmss } from "../../lib/format";
import { Icon } from "../Icon";
import { Facts } from "./Facts";

function Elapsed({ since }) {
  const [now, setNow] = useState(Date.now());
  useEffect(() => { const t = setInterval(() => setNow(Date.now()), 1000); return () => clearInterval(t); }, []);
  return <span>{mmss(now / 1000 - since)}</span>;
}

// a still can be fetched while it is still being written; a broken one hides itself and the next poll asks again
function Still({ src, className, title }) {
  const [broken, setBroken] = useState(false);
  return broken ? null : <img className={className} src={src} alt="" title={title} onError={() => setBroken(true)} />;
}

// The video being made: the phone screen shows the newest still, six bars show the step, the strip collects every still.
export function LiveCard({ job, label, accent, onStop }) {
  const idx = STAGES.indexOf(job.stage);
  const pct = Math.round(((idx + 0.5) / STAGES.length) * 100);
  const stills = job.stills || [], last = stills[stills.length - 1];
  const talking = job.presenter && job.stage === "visuals";  // the slow step of a talking video: one scene at a time on a free GPU
  const [word, verb] = talking ? ["Face", "Making your photo talk"] : STEP[job.stage] || [cap(job.stage || ""), cap(job.stage || "")];
  const [count, noun] = talking && job.scenes ? [`${job.faces || 0} of ${job.scenes.length}`, "scenes"]
    : job.stage === "images" && job.shots && !job.presenter ? [`${stills.length} of ${job.shots}`, "stills"] : ["", ""];
  const src = f => `/out/${job.id}/${f}?${job.stage}${stills.length}`;
  const started = job.started || job.created;

  return (
    <article className="card live">
      <div className="thumb screen" style={{ "--accent": accent || "#FFE500" }}>
        {last ? <>
          <Still key={src(last)} className="still" src={src(last)} />
          <i className="bar" style={{ "--fill": `${pct}%` }} />
        </> : <i className="fill" style={{ "--fill": `${pct}%` }} />}
        <span className="stage swap" key={job.stage}>{word}{count && <small>{count} {noun}</small>}</span>
      </div>
      <div className="body">
        <span className="status making">Generating</span>
        <h3>{job.topic}</h3>
        {job.hook && <p className="desc">{job.hook}</p>}
        <ol className="steps" aria-label="Steps">
          {STAGES.map((st, i) => <li key={st} className={i < idx ? "done" : i === idx ? "now" : ""}><span>{STEP[st][0]}</span></li>)}
        </ol>
        <p className="step">
          <span className="swap" key={job.stage}>{verb}{count && `, ${count}`}</span>
          <span className="elapsed"><Icon name="timer" /><Elapsed since={started} /></span>
        </p>
        {stills.length > 0 && (
          <div className="strip">
            {stills.map(f => <Still key={src(f)} src={src(f)} title={(job.scenes || [])[parseInt(f.slice(3), 10)] || ""} />)}
          </div>
        )}
        <Facts job={job} label={label} />
      </div>
      <div className="side">
        <time>Started {ago(started)}</time>
        {!job.result && (  // a scene redo on a finished video can't be stopped halfway
          <div className="actions">
            <button type="button" className="btn del" onClick={e => {
              if (!confirm(`Stop "${job.topic}"? The work done so far is thrown away.`)) return;
              e.currentTarget.disabled = true;
              onStop(job.id);
            }}><Icon name="x" />Stop</button>
          </div>
        )}
      </div>
    </article>
  );
}
