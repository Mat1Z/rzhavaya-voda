"""Generate episode frames with Cloudflare Workers AI (FLUX.2 klein) and write shots.json for build.py.

Usage: python pipeline/make_images.py episodes/03
Env: CF_ACCOUNT_ID, CF_API_TOKEN
"""
import base64, io, json, os, sys, time
import requests
from PIL import Image

STYLE = ("Stylized low-poly 3D render, blocky characters with pixel-art textures, muted desaturated colors, "
         "rust-orange accents, moody cinematic lighting, vertical 9:16. Grim post-apocalyptic mood: grimy worn "
         "surfaces, rust stains and streaks, peeling paint, damp stained concrete, clutter, dim single light source, "
         "deep heavy shadows, desaturated teal-grey and rust palette, subtle film grain. ")
MIRA = ("Mira, a small 10-year-old child with a round childlike face and two dark braids, yellow raincoat with "
        "orange trim, grey backpack, dark jeans")
NURLAN = ("her father Nurlan, a 40-year-old plumber with short black hair, round glasses, stubble, grey work "
          "jacket with orange stitching")
MODELS = ["flux-2-klein-9b", "flux-2-klein-4b"]


def dry(ep, spec):
    """Placeholder frames (no Cloudflare) to test voice + montage without spending the daily limit."""
    from PIL import ImageDraw
    os.makedirs(f"{ep}/img", exist_ok=True)
    shots = []
    for k, (anchor, name, motion, prompt) in enumerate(spec["shots"]):
        im = Image.new("RGB", (768, 1360), (30 + 9 * k, 34, 38))
        d = ImageDraw.Draw(im)
        d.rectangle([40, 40, 728, 1320], outline=(200, 90, 40), width=6)
        d.text((80, 600), f"KADR {name}", fill=(230, 230, 230))
        im.save(f"{ep}/img/{name}.jpg")
        shots.append([anchor, f"img/{name}.jpg", motion])
    json.dump(shots, open(f"{ep}/shots.json", "w", encoding="utf-8"), ensure_ascii=False)
    print("dry run: placeholder frames")


def main(ep):
    if os.environ.get("DRY_IMAGES") == "1":
        return dry(ep, json.load(open(f"{ep}/episode.json", encoding="utf-8")))
    acc, tok = os.environ["CF_ACCOUNT_ID"].strip(), os.environ["CF_API_TOKEN"].strip()
    base = f"https://api.cloudflare.com/client/v4/accounts/{acc}/ai/run/@cf/black-forest-labs/"
    H = {"Authorization": f"Bearer {tok}"}
    spec = json.load(open(f"{ep}/episode.json", encoding="utf-8"))
    os.makedirs(f"{ep}/img", exist_ok=True)
    shots, failed = [], []
    for anchor, name, motion, prompt in spec["shots"]:
        path = f"img/{name}.jpg"
        shots.append([anchor, path, motion])
        if os.path.exists(f"{ep}/{path}"):
            continue  # already generated on an earlier run
        refs = []
        if "{MIRA}" in prompt: refs.append(("refs/mira.png", "the girl"))
        if "{NURLAN}" in prompt: refs.append(("refs/nurlan.png", "the man"))
        text = prompt.replace("{MIRA}", MIRA).replace("{NURLAN}", NURLAN)
        if refs:
            text = "Use " + ", ".join(f"{who} in image {i}" for i, (_, who) in enumerate(refs)) + " (same face and clothes). " + text
        data = {"prompt": STYLE + text, "width": "768", "height": "1360", "seed": "3"}
        ok = False
        for model in MODELS:
            for attempt in range(4):
                files = {f"input_image_{i}": (os.path.basename(p), open(p, "rb"), "image/png") for i, (p, _) in enumerate(refs)}
                r = requests.post(base + model, headers=H, data=data, files=files or None, timeout=180)
                if r.status_code < 500 and "Capacity" not in r.text:
                    break
                time.sleep(5 * (attempt + 1))
            img = (r.json().get("result") or {}).get("image") if r.headers.get("content-type", "").startswith("application/json") else None
            if img:
                Image.open(io.BytesIO(base64.b64decode(img))).convert("RGB").save(f"{ep}/{path}", quality=92)
                print(f"{name}: ok ({model})", flush=True)
                ok = True
                break
            print(f"{name}: {model} failed: {r.text[:200]}", flush=True)
            if "daily free allocation" in r.text:
                break  # same account limit for every model
        if not ok:
            failed.append(name)
    json.dump(shots, open(f"{ep}/shots.json", "w", encoding="utf-8"), ensure_ascii=False)
    if failed:
        sys.exit(f"Не получились кадры: {', '.join(failed)}")


if __name__ == "__main__":
    main(sys.argv[1].rstrip("/"))
