import { FEED_URL } from "../lib/constants";
import { Icon } from "./Icon";

export function Header({ making, ready }) {
  return (
    <header className="top">
      <a className="brand" href="/">
        <span className="mark" aria-hidden="true"><Icon name="play" className="i fill" /></span>Qoneqt Video Factory
      </a>
      <nav>
        <span className="tally">
          <i className={`dot${making ? " on" : ""}`} aria-hidden="true" />
          <span>{making ? `${making} generating` : "Idle"}{ready ? `, ${ready} ready` : ""}</span>
        </span>
        <a className="btn" href={FEED_URL} target="_blank" rel="noopener">
          <Icon name="external" /><span><span className="w">Open </span>Global Feed</span>
        </a>
      </nav>
    </header>
  );
}
