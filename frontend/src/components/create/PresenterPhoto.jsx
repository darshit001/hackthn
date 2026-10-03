import { useRef, useState } from "react";
import { api } from "../../lib/api";
import { Icon } from "../Icon";

const SIDE = 1024;  // the server crops a 9:16 portrait anyway; a phone photo is shrunk here so the upload stays ~200 KB

export async function shrink(file) {
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
      <input type="radio" name="version" checked={checked} disabled={!src || busy} onChange={onPick} />
      <span className="pic">{src && <img src={src} alt="" />}{(busy || !src) && <Icon name="sparkles" />}</span>
      <span className="cap">{checked && <Icon name="check" />}{label}</span>
    </label>
  );
}

// The user's photo, and on request an AI-restyled copy beside it (same face, the chosen outfit, better light): a restyle
// spends free daily quota, so it runs only when the button is pressed.
export function PresenterPhoto({ presets, community, setPhoto, consent, setConsent, error, consentRef }) {
  const input = useRef();
  const [original, setOriginal] = useState("");
  const [restyled, setRestyled] = useState("");
  const [useOriginal, setUseOriginal] = useState(true);
  const [outfit, setOutfit] = useState(presets.outfit_for[community] || "smart");
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState("");

  // the user asked for it, so a restyle that lands is the photo used; a failed one changes nothing and says why
  const restyle = async () => {
    setBusy(true);
    setNote("");
    try {
      const { photo: out } = await api.restyle(original, outfit);
      setRestyled(out);
      setUseOriginal(false);
      setPhoto(out);
    } catch (e) {
      setNote(e.message || "Restyle failed. Try again, or use your original photo.");
    }
    setBusy(false);
  };

  const pick = async file => {
    if (!file) return;
    if (!file.type.startsWith("image/")) { setNote("That file is not a photo. Use a JPG or PNG."); return; }
    let photo;
    try { photo = await shrink(file); } catch { setNote("This photo could not be opened. Use a JPG or PNG."); return; }
    setOriginal(photo);
    setRestyled("");  // an older restyle is of another picture
    setUseOriginal(true);
    setPhoto(photo);
    setNote("");
  };

  const choose = orig => { setUseOriginal(orig); setPhoto(orig ? original : restyled); };

  return (
    <div className="field presenter"><span className="lbl"><b>5</b>Your photo</span>
      <input ref={input} id="photo" type="file" accept="image/*" className="vh" tabIndex={original ? -1 : 0}
        onChange={e => { pick(e.target.files[0]); e.target.value = ""; }} />
      {original ? (
        <>
          <div className="versions" role="radiogroup" aria-label="Photo to use" aria-busy={busy}>
            <Version src={original} label="Original" checked={useOriginal} onPick={() => choose(true)} />
            {(restyled || busy) && (
              <Version src={restyled || original} label={busy ? "Restyling…" : "Restyled"} checked={!useOriginal} busy={busy} onPick={() => choose(false)} />
            )}
            <div className="ver-actions">
              <button type="button" className="btn" disabled={busy} onClick={restyle}>
                <Icon name="sparkles" />{restyled ? "Restyle again" : "Restyle with AI"}
              </button>
              <button type="button" className="btn" onClick={() => input.current.click()}><Icon name="image" />Change photo</button>
            </div>
          </div>
          <div className="chips outfits" role="radiogroup" aria-label="Outfit">
            {presets.outfits.map(o => (
              <label className="chip" key={o.slug}>
                <input type="radio" name="outfit" checked={outfit === o.slug} onChange={() => setOutfit(o.slug)} /><span>{o.label}</span>
              </label>
            ))}
          </div>
        </>
      ) : (
        <label htmlFor="photo" className="dropzone"
          onDragOver={e => e.preventDefault()} onDrop={e => { e.preventDefault(); pick(e.dataTransfer.files[0]); }}>
          <Icon name="image" />
          <strong>Add a photo of your face</strong>
          <small>Then restyle it with AI in an outfit you pick, or use it as it is.</small>
        </label>
      )}
      <p className="hint below">You talk to camera in the first and last scene; the scenes in between are AI pictures with you in them.</p>
      {note && <p className="hint err" role="alert">{note}</p>}
      <label className="check consent">
        <input ref={consentRef} type="checkbox" checked={consent} onChange={e => setConsent(e.target.checked)}
          aria-describedby={error ? "consent-error" : undefined} aria-invalid={!!error} />
        <span>This is me, or I have permission to use this face <abbr title="required">*</abbr></span>
      </label>
      {error && <p id="consent-error" className="hint err">{error}</p>}
    </div>
  );
}
