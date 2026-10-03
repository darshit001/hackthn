import { useEffect, useState } from "react";
import { api } from "../lib/api";
import { LABEL } from "../lib/constants";

// Communities, languages, lengths and looks come from the backend; `label` and `accent` look a slug up in them.
export function usePresets() {
  const [presets, setPresets] = useState({ communities: [], languages: [], durations: [], styles: [], outfits: [], layouts: [], outfit_for: {}, labels: {}, accents: {} });
  useEffect(() => {
    api.presets().then(p => {
      const labels = {}, accents = {};
      p.communities.forEach(c => { labels[c.slug] = LABEL[c.slug] || c.label; accents[c.slug] = c.accent; });
      p.languages.forEach(l => { labels[l.slug] = l.label; });
      p.styles.forEach(s => { labels[s.slug] = s.label; });
      setPresets({ ...p, labels, accents });
    });
  }, []);
  return { ...presets, label: slug => presets.labels[slug] || LABEL[slug] || slug };
}
