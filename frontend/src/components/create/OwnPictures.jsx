import { useState } from "react";
import { api } from "../../lib/api";
import { Icon } from "../Icon";
import { shrink } from "./PresenterPhoto";

// the picture a slot puts on its slide: the AI redraw once made and picked, else the user's own
export const chosen = p => (p?.useAi ? p.ai : p?.mine) || "";

// One 4:5 tile per slide, the post's own shape. A tile takes a click, a drop or several files at once (they fill the
// tiles from there on); Regenerate redraws that one picture with AI in the picked look, and the user's original stays one
// click away. A redraw spends free daily quota, so it runs only when pressed.
export function OwnPictures({ slides, pics, setPics, topic, style, error }) {
  const [note, setNote] = useState("");
  const patch = (i, change) => setPics(list => { const next = [...list]; next[i] = { ...next[i], ...change }; return next; });

  const add = async (i, files) => {
    const imgs = [...files].filter(f => f.type.startsWith("image/")).slice(0, slides - i);
    if (!imgs.length) { setNote("That file is not a picture. Use a JPG or PNG."); return; }
    setNote("");
    for (const [k, f] of imgs.entries()) {
      try { patch(i + k, { mine: await shrink(f), ai: "", useAi: false }); }  // an older redraw is of another picture
      catch { setNote("A picture could not be opened. Use a JPG or PNG."); }
    }
  };

  const regenerate = async i => {
    patch(i, { busy: true });
    setNote("");
    try {
      const { picture } = await api.reimagine(pics[i].mine, topic, style);
      patch(i, { ai: picture, useAi: true, busy: false });
    } catch (e) {
      patch(i, { busy: false });
      setNote(e.message || "Regenerate failed. Try again, or use your own picture.");
    }
  };

  return (
    <>
      <div className="slots">
        {Array.from({ length: slides }, (_, i) => {
          const p = pics[i] || {}, src = chosen(p), name = slides > 1 ? `Slide ${i + 1}` : "Your picture";
          return (
            <div className={"slot" + (p.busy ? " busy" : "")} key={i}>
              <label className={"frame" + (src ? "" : " blank")} aria-busy={!!p.busy}
                onDragOver={e => e.preventDefault()} onDrop={e => { e.preventDefault(); add(i, e.dataTransfer.files); }}>
                <input type="file" accept="image/*" multiple={!src} className="vh" disabled={p.busy}
                  aria-label={src ? `Replace ${name.toLowerCase()}` : `Add ${name.toLowerCase()}`}
                  onChange={e => { add(i, e.target.files); e.target.value = ""; }} />
                {src ? <img src={src} alt="" /> : <><Icon name="plus" /><span>{name}</span></>}
                {p.busy && <Icon name="sparkles" />}
                {src && !p.busy && <span className="tag">{p.useAi ? "AI" : "Yours"}</span>}
              </label>
              {p.mine && (
                <div className="slot-actions">
                  <button type="button" className="btn" disabled={p.busy} onClick={() => regenerate(i)}>
                    <Icon name="sparkles" />{p.busy ? "Drawing…" : "Regenerate"}
                  </button>
                  {p.ai && !p.busy && (
                    <button type="button" className="link" onClick={() => patch(i, { useAi: !p.useAi })}>
                      {p.useAi ? "Use mine" : "Use AI's"}
                    </button>
                  )}
                </div>
              )}
            </div>
          );
        })}
      </div>
      {(note || error) && <p className="hint err" role="alert">{note || error}</p>}
    </>
  );
}
