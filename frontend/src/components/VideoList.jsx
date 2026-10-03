import { useEffect, useMemo, useRef, useState } from "react";
import { PER_PAGE } from "../lib/constants";
import { FILTERS, SORTS, facet, matches, sortJobs } from "../lib/library";
import { reducedMotion } from "../lib/format";
import { Icon } from "./Icon";
import { Pager } from "./Pager";
import { LiveCard } from "./cards/LiveCard";
import { ImageCard } from "./cards/ImageCard";
import { ReadyCard } from "./cards/ReadyCard";
import { FailedCard, QueuedCard } from "./cards/WaitCard";

const TABS = [["all", "All"], ["ready", "Ready"], ["saved", "Saved"], ["making", "In progress"], ["failed", "Failed"]];

// Splits the jobs into the four tabs; the line of videos being made runs oldest first, everything else newest first.
export function groupJobs(jobs) {
  const newest = (a, b) => b.created - a.created;
  const making = jobs.filter(j => j.status === "queued" || j.status === "running").sort((a, b) => a.created - b.created);
  const failed = jobs.filter(j => j.status === "failed").sort(newest);
  const ready = jobs.filter(j => j.status === "done").sort(newest);
  return { all: [...making, ...failed, ...ready], making, failed, ready, saved: ready.filter(j => j.saved) };
}

export function VideoList({ jobs, presets, actions }) {
  const [tab, setTab] = useState("all");
  const [q, setQ] = useState("");
  const [page, setPage] = useState(1);
  const [picks, setPicks] = useState({});
  const [sort, setSort] = useState("latest");
  const top = useRef();
  const groups = useMemo(() => groupJobs(jobs), [jobs]);
  // images and videos wait in separate lines, so each counts its place in its own
  const queuePos = useMemo(() => {
    const line = kind => groups.making.filter(j => j.status === "queued" && (j.kind === "image") === kind).map((j, i) => [j.id, i]);
    return new Map([...line(false), ...line(true)]);
  }, [groups]);

  // a click anywhere else closes an open ⋮ menu
  useEffect(() => {
    const close = e => document.querySelectorAll("details.menu[open]").forEach(d => !d.contains(e.target) && d.removeAttribute("open"));
    document.addEventListener("click", close);
    return () => document.removeEventListener("click", close);
  }, []);

  // a filter group offers only the values some video has, in the form's order, and only when there are two to choose between
  const options = useMemo(() => {
    const order = { kind: ["video", "image"], community: presets.communities.map(c => c.slug), language: presets.languages.map(l => l.slug), style: presets.styles.map(s => s.slug), duration: presets.durations };
    return FILTERS.map(([key, name]) => [key, name, order[key].filter(v => jobs.some(j => facet(j, key) === v))]).filter(([, , vals]) => vals.length > 1);
  }, [jobs, presets]);
  const picked = Object.values(picks).reduce((n, set) => n + set.size, 0);
  const toggle = (key, v) => {
    setPicks(p => { const set = new Set(p[key]); set.has(v) ? set.delete(v) : set.add(v); return { ...p, [key]: set }; });
    setPage(1);
  };

  const needle = q.trim().toLowerCase();
  const list = sortJobs(groups[tab].filter(j => matches(j, needle, picks, presets.label)), sort);
  const pages = Math.max(1, Math.ceil(list.length / PER_PAGE));
  const current = Math.min(page, pages);  // deletes can leave us past the last page
  const shown = list.slice((current - 1) * PER_PAGE, current * PER_PAGE);

  const goTo = n => {
    setPage(n);
    top.current.scrollIntoView({ block: "start", behavior: reducedMotion() ? "auto" : "smooth" });
  };

  const card = j => {
    const common = { job: j, label: presets.label, accent: presets.accents[j.community] };
    if (j.status === "done" && j.kind === "image") return <ImageCard key={j.id} {...common} {...actions} />;
    if (j.status === "done") return <ReadyCard key={j.id} {...common} {...actions} />;
    if (j.status === "failed") return <FailedCard key={j.id} {...common} onRetry={actions.onRetry} onDelete={actions.onDelete} />;
    if (j.status === "queued") return <QueuedCard key={j.id} {...common} position={queuePos.get(j.id) || 0} onDelete={actions.onDelete} />;
    return <LiveCard key={j.id} {...common} onStop={actions.onStop} />;
  };

  return (
    <section className="videos" ref={top}>
      <div className="head">
        <h2>Your posts</h2>
        <div className="find">
          <label className="search">
            <Icon name="search" />
            <input type="search" placeholder="Search by topic, hook or #hashtag" aria-label="Search posts" value={q}
              onChange={e => { setQ(e.target.value); setPage(1); }} />
          </label>
          <details className="menu filter">
            <summary className="btn"><Icon name="filter" />Filter{picked > 0 && <span className="count">{picked}</span>}</summary>
            <div className="pop">
              <div className="pophead">
                <span>Show posts that match</span>
                {picked > 0 && <button type="button" className="link" onClick={() => { setPicks({}); setPage(1); }}>Clear</button>}
              </div>
              {options.map(([key, name, vals]) => (
                <fieldset key={key}>
                  <legend>{name}</legend>
                  {vals.map(v => (
                    <label className="chip" key={v}>
                      <input type="checkbox" checked={!!picks[key]?.has(v)} onChange={() => toggle(key, v)} />
                      {key === "duration" ? `${v} s` : presets.label(v)}
                    </label>
                  ))}
                </fieldset>
              ))}
              {!options.length && <p className="none">Make videos in more than one community, language, look or length to filter them.</p>}
            </div>
          </details>
        </div>
      </div>
      <div className="tabrow">
        <div className="tabs" role="tablist">
          {TABS.map(([key, name]) => (
            <button type="button" role="tab" key={key} aria-selected={tab === key} onClick={() => { setTab(key); setPage(1); }}>
              {name} <span>{groups[key].length}</span>
            </button>
          ))}
        </div>
        <label className="sort">
          <Icon name="sort" />
          <select aria-label="Sort videos" value={sort} onChange={e => { setSort(e.target.value); setPage(1); }}>
            {SORTS.map(([key, name]) => <option key={key} value={key}>{name}</option>)}
          </select>
          <Icon name="chevron" />
        </label>
      </div>
      <div aria-live="polite">{shown.map(card)}</div>
      <Pager page={current} pages={pages} total={list.length} onPage={goTo} />
      {!jobs.length && <div className="empty"><b>Nothing here yet</b>Add a topic on the left and generate a video or an image. It appears here while it is being made.</div>}
      {jobs.length > 0 && !list.length && (tab === "saved" && !groups.saved.length
        ? <div className="empty"><b>No saved videos yet</b>Tap the bookmark on a video to keep it here.</div>
        : <div className="empty"><b>Nothing here</b>Nothing matches this filter.</div>)}
    </section>
  );
}
