import { useEffect, useRef } from "react";
import { Icon } from "./Icon";

// One native <dialog> for every card. `video` is {video, thumb, topic} or null.
export function PlayerDialog({ video, onClose }) {
  const dialog = useRef(), player = useRef();

  useEffect(() => {
    const d = dialog.current;
    if (video && !d.open) {
      d.showModal();
      player.current.play().catch(() => {});
    } else if (!video && d.open) d.close();
  }, [video]);

  return (
    <dialog ref={dialog} aria-label="Video player" onClose={onClose}
      onClick={e => e.target === dialog.current && onClose() /* the backdrop is the dialog's own box */}>
      {video && <video ref={player} controls playsInline poster={video.thumb} src={video.video} />}
      <button type="button" className="x" aria-label="Close" onClick={onClose}><Icon name="x" /></button>
      <p className="cap">{video?.topic}</p>
    </dialog>
  );
}
