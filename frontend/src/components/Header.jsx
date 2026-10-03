import { useState } from "react";
import { Icon } from "./Icon";

// the page follows the OS until someone picks a side; the pick is saved and applied before paint (index.html)
const current = () =>
  document.documentElement.dataset.theme || (matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light");

function ThemeToggle() {
  const [theme, setTheme] = useState(current);
  const next = theme === "dark" ? "light" : "dark";
  const flip = () => {
    const t = current() === "dark" ? "light" : "dark";
    document.documentElement.dataset.theme = t;
    try { localStorage.setItem("theme", t); } catch {}
    setTheme(t);
  };
  return (
    <button type="button" className="btn icon" onClick={flip} aria-label={`Switch to ${next} mode`} title={`Switch to ${next} mode`}>
      <Icon name={next === "dark" ? "moon" : "sun"} />
    </button>
  );
}

export function Header({ making, ready }) {
  return (
    <header className="top">
      <a className="brand" href="/">
        {/* the Qoneqt Video Factory mark: a play panel with two frames trailing behind it */}
        <svg className="mark" viewBox="0 0 64 51" aria-hidden="true">
          <defs>
            <linearGradient id="qm-a" x1="0" y1="1" x2="1" y2="0"><stop offset="0" stopColor="#3326E6" /><stop offset="1" stopColor="#9A3CF7" /></linearGradient>
            <linearGradient id="qm-b" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stopColor="#B78DF7" /><stop offset="1" stopColor="#7B52F2" /></linearGradient>
            <linearGradient id="qm-c" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stopColor="#D6BEFA" /><stop offset="1" stopColor="#AD8DF5" /></linearGradient>
          </defs>
          <g strokeLinejoin="round">
            <polygon points="4,12 33,4 33,47 4,40" fill="url(#qm-a)" stroke="url(#qm-a)" strokeWidth="8" />
            <polygon points="41.7,6.5 48.5,8.5 48.5,40 41.7,45.5" fill="url(#qm-b)" stroke="url(#qm-b)" strokeWidth="3" />
            <polygon points="55,12.3 61.8,14.5 61.8,36 55,42.5" fill="url(#qm-c)" stroke="url(#qm-c)" strokeWidth="3" />
            <polygon points="12.3,20.5 22.6,26.5 12.3,31.5" fill="#fff" stroke="#fff" strokeWidth="3" />
          </g>
        </svg>
        <span className="name">Qoneqt<small>Video Factory</small></span>
      </a>
      <nav>
        <span className="tally">
          <i className={`dot${making ? " on" : ""}`} aria-hidden="true" />
          <span>{making ? `${making} generating` : "Idle"}{ready ? `, ${ready} ready` : ""}</span>
        </span>
        <ThemeToggle />
      </nav>
    </header>
  );
}
