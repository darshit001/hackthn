// Search, filter and sort for the video list. Plain functions so library.test.js can run them under `node --test`.

export const FILTERS = [["kind", "Type"], ["community", "Community"], ["language", "Language"], ["style", "Look"], ["duration", "Length"]];

export const SORTS = [["latest", "Latest first"], ["oldest", "Oldest first"], ["shortest", "Shortest"], ["longest", "Longest"], ["az", "A to Z"]];

// the value a job has for a filter group; older jobs have no style and were all photographs, and no kind and were all videos
export const facet = (j, key) => key === "style" ? (j.style || "photo") : key === "kind" ? (j.kind || "video") : j[key];

const making = j => j.status === "queued" || j.status === "running";
const seconds = j => j.result?.duration ?? j.duration ?? 0;  // an image post has no length and sorts as the shortest

// the topic, the community's name and, once a video is ready, its hook, caption and hashtags
export function haystack(j, label) {
  const m = j.result || {};
  return [j.topic, label(j.community), m.hook, m.caption, ...(m.hashtags || [])].filter(Boolean).join(" ").toLowerCase();
}

// picks = { community: Set, ... }; any pick within a group, every group with a pick
export function matches(j, needle, picks, label) {
  if (needle && !haystack(j, label).includes(needle)) return false;
  return FILTERS.every(([key]) => !picks[key]?.size || picks[key].has(facet(j, key)));
}

// videos being made stay first and in queue order whatever the sort, so nothing looks like it jumped the line
export function sortJobs(list, by) {
  const cmp = {
    latest: (a, b) => b.created - a.created,
    oldest: (a, b) => a.created - b.created,
    shortest: (a, b) => seconds(a) - seconds(b),
    longest: (a, b) => seconds(b) - seconds(a),
    az: (a, b) => a.topic.localeCompare(b.topic),
  }[by];
  return [...list.filter(making), ...list.filter(j => !making(j)).sort(cmp)];
}

// "More videos" beside the player: other finished videos, same community and language first, then same community,
// then same language, newest first within each
export function related(jobs, job, n = 6) {
  const score = j => (j.community === job.community) * 2 + (j.language === job.language);
  return jobs.filter(j => j.result && j.status === "done" && j.id !== job.id)
    .sort((a, b) => score(b) - score(a) || b.created - a.created).slice(0, n);
}
