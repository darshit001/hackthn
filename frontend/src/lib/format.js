const RTF = new Intl.RelativeTimeFormat("en", { numeric: "auto" });

export function ago(ts) {
  const s = Date.now() / 1000 - ts;
  for (const [unit, sec] of [["day", 86400], ["hour", 3600], ["minute", 60]]) if (s >= sec) return RTF.format(-Math.floor(s / sec), unit);
  return "just now";
}

export function mmss(sec) {
  sec = Math.max(0, Math.round(sec));
  return `${Math.floor(sec / 60)}:${String(sec % 60).padStart(2, "0")}`;
}

export const cap = s => s.charAt(0).toUpperCase() + s.slice(1);
export const nth = i => ["Next up", "2nd in line", "3rd in line"][i] || `${i + 1}th in line`;

export const reducedMotion = () => matchMedia("(prefers-reduced-motion: reduce)").matches;
export const canHover = () => matchMedia("(hover: hover)").matches;

// The post text the Copy buttons put on the clipboard
export const postText = m => `${m.hook}\n\n${m.caption}\n\n${m.hashtags.join(" ")}`;

// a scene whose free GPU ran out shows the still photo; the count tells the user which videos a Redo scene would improve
export const talked = m => {
  const faces = m.scenes.filter(sc => sc.face), n = faces.filter(sc => sc.face !== "photo").length;
  return n === faces.length ? "You, talking" : `You, talking in ${n} of ${faces.length} scenes`;
};
