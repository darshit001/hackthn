import { useRef, useState } from "react";
import { Icon } from "../Icon";

const SIDE = 1024;  // the server crops a 1024 square anyway; a phone photo is shrunk here so the upload stays ~200 KB

async function shrink(file) {
  const bmp = await createImageBitmap(file);  // throws on what the browser can't decode (HEIC on most desktops)
  const k = Math.min(1, SIDE / Math.max(bmp.width, bmp.height));
  const c = document.createElement("canvas");
  c.width = Math.round(bmp.width * k);
  c.height = Math.round(bmp.height * k);
  c.getContext("2d").drawImage(bmp, 0, 0, c.width, c.height);
  return c.toDataURL("image/jpeg", 0.9);
}

// The talking-presenter photo: pick, see where the face lands in the 9:16 frame, confirm it may be used.
export function PresenterPhoto({ photo, setPhoto, consent, setConsent, error, consentRef }) {
  const input = useRef();
  const [note, setNote] = useState("");

  const pick = async file => {
    if (!file) return;
    if (!file.type.startsWith("image/")) { setNote("That file is not a photo. Use a JPG or PNG."); return; }
    try { setPhoto(await shrink(file)); setNote(""); }
    catch { setNote("This photo could not be opened. Use a JPG or PNG."); }
  };

  return (
    <div className="field presenter"><span>6. Your photo</span>
      <input ref={input} id="photo" type="file" accept="image/*" className="vh" tabIndex={photo ? -1 : 0} onChange={e => { pick(e.target.files[0]); e.target.value = ""; }} />
      {photo ? (
        <div className="face">
          {/* a small copy of the real frame: the photo blurred behind, the face square in the middle */}
          <div className="mini" aria-hidden="true">
            <img className="bg" src={photo} alt="" />
            <img className="sq" src={photo} alt="" />
          </div>
          <div className="about">
            <p>Your face speaks the script: lips, head and eyes move. Hands and body stay still.</p>
            <button type="button" className="btn" onClick={() => input.current.click()}><Icon name="refresh" />Change photo</button>
          </div>
        </div>
      ) : (
        <label htmlFor="photo" className="dropzone"
          onDragOver={e => e.preventDefault()} onDrop={e => { e.preventDefault(); pick(e.dataTransfer.files[0]); }}>
          <Icon name="image" />
          <strong>Add a photo of your face</strong>
          <small>Looking at the camera, shoulders up, good light</small>
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
  );
}
