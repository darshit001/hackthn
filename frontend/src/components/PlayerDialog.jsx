import { useEffect, useRef, useState } from "react";
import { Icon } from "./Icon";
import { SaveButton } from "./cards/SaveButton";

// One native <dialog> for every card. `video` is {id, video, thumb, topic}, an image post's {slides, download, file, thumb, topic, alt}, or null.
// A carousel's slides step with the ‹ › buttons or the arrow keys.
export function PlayerDialog({ video, onClose, saved, onSave }) {
  const dialog = useRef(), player = useRef();
  const [at, setAt] = useState(0);
  const slides = video?.slides || [];
  const go = step => setAt(i => Math.min(slides.length - 1, Math.max(0, i + step)));

  useEffect(() => {
    const d = dialog.current;
    setAt(0);
    if (video && !d.open) {
      d.showModal();
      player.current?.play().catch(() => {});
    } else if (!video && d.open) d.close();
  }, [video]);

  return (
    <dialog ref={dialog} aria-label={slides.length ? "Image" : "Video player"} onClose={onClose}
      onKeyDown={e => { if (slides.length > 1 && (e.key === "ArrowLeft" || e.key === "ArrowRight")) { e.preventDefault(); go(e.key === "ArrowLeft" ? -1 : 1); } }}
      onClick={e => e.target === dialog.current && onClose() /* the backdrop is the dialog's own box */}>
      {slides.length > 0 && <img className="post" src={slides[at]} alt={video.alt || ""} />}
      {slides.length > 1 && <>
        <button type="button" className="nav prev" aria-label="Previous slide" disabled={at === 0} onClick={() => go(-1)}><Icon name="left" /></button>
        <button type="button" className="nav next" aria-label="Next slide" disabled={at === slides.length - 1} onClick={() => go(1)}><Icon name="right" /></button>
      </>}
      {video && !slides.length && <video ref={player} controls playsInline poster={video.thumb} src={video.video} />}
      <button type="button" className="x" aria-label="Close" onClick={onClose}><Icon name="x" /></button>
      {onSave && <SaveButton saved={saved} onClick={onSave} />}
      {video && !slides.length && <a className="dl" href={`/jobs/${video.id}/download`} download aria-label="Download video, cover and caption as a ZIP" title="Download video, cover and caption (ZIP)"><Icon name="download" /></a>}
      <p className="cap">{video?.topic}{slides.length > 1 && <span className="count" aria-live="polite">Slide {at + 1} of {slides.length}</span>}</p>
    </dialog>
  );
}
