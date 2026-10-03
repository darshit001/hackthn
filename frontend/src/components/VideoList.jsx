import { useEffect, useMemo, useRef, useState } from "react";
import { PER_PAGE } from "../lib/constants";
import { reducedMotion } from "../lib/format";
import { Icon } from "./Icon";
import { Pager } from "./Pager";
import { LiveCard } from "./cards/LiveCard";
import { ReadyCard } from "./cards/ReadyCard";
import { FailedCard, QueuedCard } from "./cards/WaitCard";

const TABS = [["all", "All videos"], ["ready", "Ready"], ["making", "In progress"], ["failed", "Failed"]];

// Splits the jobs into the four tabs; the line of videos being made runs oldest first, everything else newest first.
export function groupJobs(jobs) {
  const newest = (a, b) => b.created - a.created;
  const making = jobs.filter(j => j.status === "queued" || j.status === "running").sort((a, b) => a.created - b.created);
  const failed = jobs.filter(j => j.status === "failed").sort(newest);
  const ready = jobs.filter(j => j.status === "done").sort(newest);
  return { all: [...making, ...failed, ...ready], making, failed, ready };
}

export function VideoList({ jobs, presets, actions }) {
  const [tab, setTab] = useState("all");
  const [q, setQ] = useState("");
  const [page, setPage] = useState(1);
  const top = useRef();
  const groups = useMemo(() => groupJobs(jobs), [jobs]);
  const queuePos = useMemo(() => new Map(groups.making.filter(j => j.status === "queued").map((j, i) => [j.id, i])), [groups]);

  // a click anywhere else closes an open ⋮ menu
  useEffect(() => {
    const close = e => document.querySelectorAll("details.menu[open]").forEach(d => !d.contains(e.target) && d.removeAttribute("open"));
    document.addEventListener("click", close);
    return () => document.removeEventListener("click", close);
  }, []);

  const needle = q.trim().toLowerCase();
  const list = needle ? groups[tab].filter(j => j.topic.toLowerCase().includes(needle)) : groups[tab];
  const pages = Math.max(1, Math.ceil(list.length / PER_PAGE));
  const current = Math.min(page, pages);  // deletes can leave us past the last page
  const shown = list.slice((current - 1) * PER_PAGE, current * PER_PAGE);

  const goTo = n => {
    setPage(n);
    top.current.scrollIntoView({ block: "start", behavior: reducedMotion() ? "auto" : "smooth" });
  };

  const card = j => {
    const common = { job: j, label: presets.label };
    if (j.status === "done") return <ReadyCard key={j.id} {...common} {...actions} />;
    if (j.status === "failed") return <FailedCard key={j.id} {...common} onRetry={actions.onRetry} onDelete={actions.onDelete} />;
    if (j.status === "queued") return <QueuedCard key={j.id} {...common} position={queuePos.get(j.id) || 0} onDelete={actions.onDelete} />;
    return <LiveCard key={j.id} {...common} accent={presets.accents[j.community]} onStop={actions.onStop} />;
  };

  return (
    <section className="videos" ref={top}>
      <div className="head">
        <div><h2>Your videos</h2><p className="sub">Watch, copy the post text and download when a video is ready.</p></div>
        <label className="search">
          <Icon name="search" />
          <input type="search" placeholder="Search videos by topic" aria-label="Search videos" value={q}
            onChange={e => { setQ(e.target.value); setPage(1); }} />
        </label>
      </div>
      <div className="tabs" role="tablist">
        {TABS.map(([key, name]) => (
          <button type="button" role="tab" key={key} aria-selected={tab === key} onClick={() => { setTab(key); setPage(1); }}>
            {name} <span>{groups[key].length}</span>
          </button>
        ))}
      </div>
      <div aria-live="polite">{shown.map(card)}</div>
      <Pager page={current} pages={pages} total={list.length} onPage={goTo} />
      {!jobs.length && <div className="empty"><b>No videos yet</b>Add a topic on the left and generate one. It appears here while it is being made.</div>}
      {jobs.length > 0 && !list.length && <div className="empty"><b>Nothing here</b>No videos match this filter.</div>}
    </section>
  );
}
