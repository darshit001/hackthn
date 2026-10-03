import { useEffect, useState } from "react";
import { api } from "../lib/api";
import { LABEL } from "../lib/constants";

// Communities, languages and lengths come from the backend; `label` and `accent` look a slug up in them.
export function usePresets() {
  const [presets, setPresets] = useState({ communities: [], languages: [], durations: [], labels: {}, accents: {} });
  useEffect(() => {
    api.presets().then(p => {
      const labels = {}, accents = {};
      p.communities.forEach(c => { labels[c.slug] = LABEL[c.slug] || c.label; accents[c.slug] = c.accent; });
      p.languages.forEach(l => { labels[l.slug] = l.label; });
      setPresets({ ...p, labels, accents });
    });
  }, []);
  return { ...presets, label: slug => presets.labels[slug] || LABEL[slug] || slug };
}
