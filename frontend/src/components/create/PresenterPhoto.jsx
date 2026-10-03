import { useRef, useState } from "react";
import { api } from "../../lib/api";
import { Icon } from "../Icon";

const SIDE = 1024;  // the server crops a 9:16 portrait anyway; a phone photo is shrunk here so the upload stays ~200 KB

async function shrink(file) {
  const bmp = await createImageBitmap(file);  // throws on what the browser can't decode (HEIC on most desktops)
  const k = Math.min(1, SIDE / Math.max(bmp.width, bmp.height));
  const c = document.createElement("canvas");
  c.width = Math.round(bmp.width * k);
  c.height = Math.round(bmp.height * k);
  c.getContext("2d").drawImage(bmp, 0, 0, c.width, c.height);
  return c.toDataURL("image/jpeg", 0.9);
}

// One 9:16 card per version of the photo; picking a card is picking the face that goes in the video.
function Version({ src, label, checked, onPick, busy }) {
  return (
    <label className={"ver" + (busy ? " busy" : "")}>
      <input type="radio" name="version" checked={checked} disabled={!src} onChange={onPick} />
      <span className="pic">{src ? <img src={src} alt="" /> : <Icon name="sparkles" />}</span>
      <span className="cap">{checked && <Icon name="check" />}{label}</span>
    </label>
  );
}

// The user's photo: restyled by AI on upload (same face, better clothes and light), shown beside the original;
// the outfit and how the middle scenes mix the user in are picked here too.
export function PresenterPhoto({ presets, community, setPhoto, layout, setLayout, consent, setConsent, error, consentRef }) {
  const input = useRef();
  const [original, setOriginal] = useState("");
  const [restyled, setRestyled] = useState("");
  const [useOriginal, setUseOriginalState] = useState(false);
  const keepOriginal = useRef(false);  // read when a restyle lands, so a late answer never overrides the user's pick
  const setUseOriginal = v => { keepOriginal.current = v; setUseOriginalState(v); };
  const [outfit, setOutfit] = useState(presets.outfit_for[community] || "smart");
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState("");

  const restyle = async (photo, look, fresh = false) => {
    setBusy(true);
    setNote("");
    try {
      const { photo: out } = await api.restyle(photo, look);
      setRestyled(out);
      if (!keepOriginal.current) setPhoto(out);
    } catch {
      if (restyled && !fresh) setNote("Could not restyle again right now. Your last restyled photo stays.");
      else {
        setNote("Restyle is unavailable right now, so your original photo is used.");
        setUseOriginal(true);
        setPhoto(photo);
      }
    }
    setBusy(false);
  };

  const pick = async file => {
    if (!file) return;
    if (!file.type.startsWith("image/")) { setNote("That file is not a photo. Use a JPG or PNG."); return; }
    let photo;
    try { photo = await shrink(file); } catch { setNote("This photo could not be opened. Use a JPG or PNG."); return; }
    setOriginal(photo);
    setRestyled("");
    setUseOriginal(false);
    setPhoto(photo);  // usable at once; the restyled one replaces it when it lands
    restyle(photo, outfit, true);  // a new photo: an older restyle is of someone else's picture
  };

  const choose = orig => { setUseOriginal(orig); setPhoto(orig ? original : restyled); };

  return (
    <>
      <div className="field presenter"><span>6. Your photo</span>
        <input ref={input} id="photo" type="file" accept="image/*" className="vh" tabIndex={original ? -1 : 0}
          onChange={e => { pick(e.target.files[0]); e.target.value = ""; }} />
        {original ? (
          <>
            <div className="versions" role="radiogroup" aria-label="Photo to use" aria-busy={busy}>
              <Version src={original} label="Original" checked={useOriginal} onPick={() => choose(true)} />
              <Version src={restyled} label={busy ? "Restyling…" : "Restyled"} checked={!useOriginal && !!restyled} busy={busy}
                onPick={() => choose(false)} />
              <div className="ver-actions">
                <button type="button" className="btn" disabled={busy} onClick={() => restyle(original, outfit)}><Icon name="refresh" />Try again</button>
                <button type="button" className="btn" onClick={() => input.current.click()}><Icon name="image" />Change photo</button>
              </div>
            </div>
            <div className="seg outfits" role="radiogroup" aria-label="Outfit">
              {presets.outfits.map(o => (
                <label key={o.slug}>
                  <input type="radio" name="outfit" checked={outfit === o.slug} disabled={busy}
                    onChange={() => { setOutfit(o.slug); restyle(original, o.slug); }} /><span>{o.label}</span>
                </label>
              ))}
            </div>
          </>
        ) : (
          <label htmlFor="photo" className="dropzone"
            onDragOver={e => e.preventDefault()} onDrop={e => { e.preventDefault(); pick(e.dataTransfer.files[0]); }}>
            <Icon name="image" />
            <strong>Add a photo of your face</strong>
            <small>AI dresses you up and puts you in every scene. You choose which photo is used.</small>
          </label>
        )}
        {note && <p className="hint err" role="alert">{note}</p>}
        <label className="check consent">
          <input ref={consentRef} type="checkbox" checked={consent} onChange={e => setConsent(e.target.checked)}
            aria-describedby={error ? "consent-error" : undefined} aria-invalid={!!error} />
          <span>This is me, or I have permission to use this face <abbr title="required">*</abbr></span>
        </label>
        {error && <p id="consent-error" className="hint err">{error}</p>}
      </div>
      <div className="field"><span>7. Middle scenes</span>
        <div className="seg three" role="radiogroup" aria-label="Middle scenes">
          {presets.layouts.map(l => (
            <label key={l.slug}>
              <input type="radio" name="layout" checked={layout === l.slug} onChange={() => setLayout(l.slug)} /><span>{l.label}</span>
            </label>
          ))}
        </div>
        <p className="hint below">You talk full-screen in the first and last scene.</p>
      </div>
    </>
  );
}
