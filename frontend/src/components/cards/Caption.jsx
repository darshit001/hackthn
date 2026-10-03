import { useLayoutEffect, useRef, useState } from "react";

// The post text clamped to two lines, Instagram-style: "more" shows only when the text is cut off,
// and opens the whole caption with its hashtags in place
export function Caption({ text, tags = [] }) {
  const p = useRef(null);
  const [open, setOpen] = useState(false);
  const [cut, setCut] = useState(false);

  useLayoutEffect(() => {
    if (open) return;  // open text is never cut; keep "less" showing
    const el = p.current, check = () => setCut(el.scrollHeight > el.clientHeight + 1);
    check();
    const ro = new ResizeObserver(check);  // the card narrows or widens with the window
    ro.observe(el);
    return () => ro.disconnect();
  }, [text, open]);

  return (
    <div className={open ? "caption open" : "caption"}>
      <p ref={p} className="desc">
        {text}
        {open && tags.length > 0 && <span className="tags">{tags.join(" ")}</span>}
      </p>
      {(cut || open) && (
        <button type="button" className="more" aria-expanded={open} onClick={() => setOpen(!open)}>
          {open ? "less" : "more"}
        </button>
      )}
    </div>
  );
}
