import { useEffect, useRef } from "react";
import { Icon } from "./Icon";
import { SaveButton } from "./cards/SaveButton";

// One native <dialog> for every card. `video` is {video, thumb, topic}, an image post's {image, thumb, topic, alt}, or null.
export function PlayerDialog({ video, onClose, saved, onSave }) {
  const dialog = useRef(), player = useRef();

  useEffect(() => {
    const d = dialog.current;
    if (video && !d.open) {
      d.showModal();
      player.current?.play().catch(() => {});
    } else if (!video && d.open) d.close();
  }, [video]);

  return (
    <dialog ref={dialog} aria-label={video?.image ? "Image" : "Video player"} onClose={onClose}
      onClick={e => e.target === dialog.current && onClose() /* the backdrop is the dialog's own box */}>
      {video?.image && <img className="post" src={video.image} alt={video.alt || ""} />}
      {video && !video.image && <video ref={player} controls playsInline poster={video.thumb} src={video.video} />}
      <button type="button" className="x" aria-label="Close" onClick={onClose}><Icon name="x" /></button>
      {onSave && <SaveButton saved={saved} onClick={onSave} />}
      <p className="cap">{video?.topic}</p>
    </dialog>
  );
}
