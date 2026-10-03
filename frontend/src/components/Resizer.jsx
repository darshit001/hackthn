import { useLayoutEffect, useRef } from "react";

// The handle between the form and the videos. Drag it, or focus it and press the arrow keys, to set the form's
// width; a double-click goes back to the default. It writes --form-w on the layout directly, so dragging does not
// re-render the video list, and the width is remembered per browser.
// below 392px the community chips no longer fit in three columns
const MIN = 392, MAX = 720, BASE = 424, KEY = "formWidth";
const VIDEOS_MIN = 480;  // the list keeps room for one full card

export function Resizer() {
  const bar = useRef(null);
  const width = useRef(BASE);
  const asked = useRef(BASE);  // the last width picked; a window resize clamps to it, not to the clamped value
  const drag = useRef(null);

  const set = w => {
    const layout = bar.current.parentElement;
    const cs = getComputedStyle(layout);
    const room = layout.clientWidth - parseFloat(cs.paddingLeft) - parseFloat(cs.paddingRight) - bar.current.offsetWidth - VIDEOS_MIN;
    const max = Math.max(MIN, Math.min(MAX, room));
    width.current = Math.round(Math.min(Math.max(w, MIN), max));
    layout.style.setProperty("--form-w", `${width.current}px`);
    bar.current.setAttribute("aria-valuenow", width.current);
    bar.current.setAttribute("aria-valuemax", max);
  };
  const commit = () => {
    asked.current = width.current;
    try { localStorage.setItem(KEY, width.current); } catch {}
  };

  useLayoutEffect(() => {
    try { asked.current = Number(localStorage.getItem(KEY)) || BASE; } catch {}
    const fit = () => set(asked.current);
    fit();
    window.addEventListener("resize", fit);
    return () => window.removeEventListener("resize", fit);
  }, []);

  const end = () => {
    if (!drag.current) return;
    drag.current = null;
    document.documentElement.classList.remove("resizing");
    commit();
  };

  const onKeyDown = e => {
    const step = e.shiftKey ? 64 : 16;
    const to = { ArrowLeft: width.current - step, ArrowRight: width.current + step, Home: MIN, End: MAX }[e.key];
    if (to === undefined) return;
    e.preventDefault();
    set(to);
    commit();
  };

  return (
    <div ref={bar} className="resizer" role="separator" aria-orientation="vertical" aria-label="Form width"
      aria-valuemin={MIN} tabIndex={0} title="Drag to resize, double-click to reset"
      onPointerDown={e => {
        if (e.button !== 0) return;
        e.currentTarget.setPointerCapture(e.pointerId);
        drag.current = { x: e.clientX, w: width.current };
        document.documentElement.classList.add("resizing");
      }}
      onPointerMove={e => drag.current && set(drag.current.w + e.clientX - drag.current.x)}
      onPointerUp={end} onPointerCancel={end} onLostPointerCapture={end}
      onKeyDown={onKeyDown}
      onDoubleClick={() => { set(BASE); commit(); }} />
  );
}
