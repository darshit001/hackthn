"""Stand-in for DeerFlow's image-generation script (the ppt-generation skill calls it once per slide, in order).
Usage: python gen_image.py --prompt-file p.json --output-file out.jpg [--aspect-ratio 16:9] [--reference-images prev.jpg] [--seed 7] [--backend procedural|pollinations]

Backends
  procedural  (default) paints the glassmorphism style locally with Pillow: violet→magenta→cyan mesh gradient on a
              near-black base, frosted glass orbs, grain, and a dark vignette on the side reserved for text. Deterministic
              per seed, so every slide shares one visual language. Prompt JSON may carry: vibrancy (0-1.4), dark_side
              (left|right|top|bottom|none), orbs [[cx, cy, r], ...] as fractions of width/height.
  pollinations free image API (returned 402/500 on 29 Sep 2026; kept for when it works again). Text fields are joined.
ponytail: no keyed image model on this account (Gemini image models 429 on free tier); swap in Gemini/Seedream here later."""
import argparse
import json
import random
import time
import urllib.parse
import urllib.request

from PIL import Image, ImageDraw, ImageFilter

SIZES = {"16:9": (1920, 1080), "4:3": (1600, 1200)}
VIOLET, MAGENTA, CYAN, BASE = (0x66, 0x7E, 0xEA), (0xF0, 0x93, 0xFB), (0x00, 0xD4, 0xFF), (11, 4, 22)


def procedural(spec, w, h, seed, out):
    rnd = random.Random(seed)
    vib = float(spec.get("vibrancy", 1.0))
    q = 4  # paint gradients at quarter resolution, blur, upscale: cheap mesh gradient
    lay = Image.new("RGB", (w // q, h // q), BASE)
    d = ImageDraw.Draw(lay)
    blobs = [((0.18, 0.2), VIOLET, 0.42), ((0.62, 0.55), MAGENTA, 0.36), ((0.95, 0.9), CYAN, 0.40), ((0.45, 1.05), VIOLET, 0.35)]
    for (cx, cy), col, r in blobs:
        col = tuple(int(BASE[i] + (col[i] - BASE[i]) * min(vib, 1.4) * 0.75) for i in range(3))
        rx, ry = int(r * w / q), int(r * w / q * 0.75)
        x, y = int(cx * w / q), int(cy * h / q)
        d.ellipse([x - rx, y - ry, x + rx, y + ry], fill=col)
    img = lay.filter(ImageFilter.GaussianBlur(radius=90 // q * 3)).resize((w, h), Image.LANCZOS)

    # frosted glass orbs with a rim highlight
    over = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    od = ImageDraw.Draw(over)
    for cx, cy, r in spec.get("orbs", [[0.72, 0.45, 0.2], [0.9, 0.18, 0.07]]):
        x, y, R = int(cx * w), int(cy * h), int(r * w)
        od.ellipse([x - R, y - R, x + R, y + R], fill=(255, 255, 255, 34), outline=(255, 255, 255, 110), width=max(2, R // 40))
        hx, hy = x - R // 3, y - R // 3
        od.ellipse([hx - R // 3, hy - R // 5, hx + R // 3, hy + R // 5], fill=(255, 255, 255, 60))
    over = over.filter(ImageFilter.GaussianBlur(radius=1.5))
    img = Image.alpha_composite(img.convert("RGBA"), over)

    # light particles
    pd = ImageDraw.Draw(img)
    for _ in range(int(spec.get("particles", 40))):
        x, y, r = rnd.randint(0, w), rnd.randint(0, h), rnd.choice([1, 1, 2, 3])
        pd.ellipse([x - r, y - r, x + r, y + r], fill=(255, 255, 255, rnd.randint(60, 160)))

    # vignette on the text side
    side = spec.get("dark_side", "left")
    if side != "none":
        mask = Image.new("L", (w, h), 0)
        md = ImageDraw.Draw(mask)
        steps = 64
        for i in range(steps):
            a = int(238 * (1 - i / steps) ** 1.1)
            if side in ("left", "right"):
                x0 = int(i * (w * 0.62) / steps)
                box = [x0, 0, x0 + w // steps + 2, h] if side == "left" else [w - x0 - w // steps - 2, 0, w - x0, h]
            else:
                y0 = int(i * (h * 0.62) / steps)
                box = [0, y0, w, y0 + h // steps + 2] if side == "top" else [0, h - y0 - h // steps - 2, w, h - y0]
            md.rectangle(box, fill=a)
        dark = Image.new("RGBA", (w, h), (7, 2, 16, 255))
        img = Image.composite(dark, img, mask.filter(ImageFilter.GaussianBlur(radius=40)))

    # grain
    noise = Image.effect_noise((w, h), 18).convert("RGBA")
    img = Image.blend(img, noise, 0.035)
    img.convert("RGB").save(out, "JPEG", quality=90)


def pollinations(spec, w, h, seed, out, model="flux"):
    text = " ".join(str(v) for v in spec.values() if isinstance(v, str))
    url = f"https://image.pollinations.ai/prompt/{urllib.parse.quote(text)}?width={w}&height={h}&seed={seed}&nologo=true&enhance=false&model={model}"
    for attempt in range(3):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "qoneqt-video-factory/1.0"})
            with urllib.request.urlopen(req, timeout=180) as r:
                data = r.read()
            if data[:3] == b"\xff\xd8\xff" or data[:8] == b"\x89PNG\r\n\x1a\n":
                open(out, "wb").write(data)
                return
            raise RuntimeError(f"not an image: {data[:80]!r}")
        except Exception as e:
            print(f"attempt {attempt + 1} failed: {e}")
            time.sleep(5)
    raise SystemExit("image generation failed")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--prompt-file", required=True)
    ap.add_argument("--output-file", required=True)
    ap.add_argument("--aspect-ratio", default="16:9")
    ap.add_argument("--reference-images", nargs="*", default=[])
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--backend", default="procedural", choices=["procedural", "pollinations"])
    a = ap.parse_args()
    spec = json.load(open(a.prompt_file, encoding="utf-8"))
    w, h = SIZES.get(a.aspect_ratio, SIZES["16:9"])
    (procedural if a.backend == "procedural" else pollinations)(spec, w, h, a.seed, a.output_file)
    print(f"wrote {a.output_file} [{a.backend}, seed {a.seed}, ref={a.reference_images or 'none'}]")
