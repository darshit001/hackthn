import { Icon } from "../Icon";

// Instagram-style save: an outline bookmark that fills with ink once the video is saved
export function SaveButton({ saved, onClick }) {
  const name = saved ? "Remove from Saved" : "Save";
  return (
    <button type="button" className="btn icon save" aria-pressed={saved} aria-label={name} title={name} onClick={onClick}>
      <Icon name="bookmark" />
    </button>
  );
}
