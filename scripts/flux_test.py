"""Image quality test: Cloudflare Workers AI FLUX models for «Ржавая вода» part 3.

Env: CF_ACCOUNT_ID, CF_API_TOKEN. Output: tests/flux/<model>/<shot>.jpg + tests/flux/report.json
"""
import base64, io, json, os, sys, time
import requests
from PIL import Image

ACC = os.environ["CF_ACCOUNT_ID"].strip()
TOK = os.environ["CF_API_TOKEN"].strip()
BASE = f"https://api.cloudflare.com/client/v4/accounts/{ACC}/ai/run/"
SUFFIX = os.environ.get("OUT_SUFFIX", "")
H = {"Authorization": f"Bearer {TOK}"}

STYLE = ("Stylized low-poly 3D render, blocky characters with pixel-art textures, "
         "muted desaturated colors, rust-orange accents, moody cinematic lighting, vertical 9:16. ")
if os.environ.get("GRIM") == "1":
    STYLE += ("Grim post-apocalyptic mood: grimy worn surfaces, rust stains and streaks, peeling paint, "
              "damp stained concrete, clutter, dim single light source, deep heavy shadows, "
              "desaturated teal-grey and rust palette, subtle film grain. ")
MIRA = ("Mira, a small 10-year-old child with a round childlike face and two dark braids, yellow raincoat with orange trim, "
        "grey backpack, dark jeans")
NURLAN = ("her father Nurlan, a 40-year-old plumber with short black hair, round glasses, "
          "stubble, grey work jacket with orange stitching")

SHOTS = {
    "01_window": f"{MIRA} stands at a dark apartment window looking out, rust-orange rain streaks run down the glass, {NURLAN} stands behind her with a hand on her shoulder, Soviet panel building interior, night.",
    "02_towel": f"Small tiled bathroom lit by one bulb, {NURLAN} gently dries {MIRA.split(',')[0]}'s wet braids with a towel, a blue plastic water canister on the floor.",
    "03_street": "Empty Soviet courtyard between grey panel buildings during heavy rust-orange rain, orange puddles, an abandoned car, a lone street lamp, no people.",
    "04_tape": f"{NURLAN} seals the gaps of a window frame with wide grey duct tape, {MIRA} holds the tape roll for him, heavy rust-orange rain falls only outside behind the glass, the room interior is completely dry, one candle on the windowsill.",
    "05_drop": "Extreme close-up of a single rust-orange raindrop sliding down a window pane, blurred dark city behind, high detail.",
    "06_hallway": f"Dark apartment hallway, {NURLAN} holds a flashlight, {MIRA} hides behind him, rusty water drips from a cracked ceiling into a bucket.",
}

def refs_for(prompt):
    files = []
    if "Mira" in prompt:
        files.append("refs/mira.png")
    if "Nurlan" in prompt:
        files.append("refs/nurlan.png")
    if os.environ.get("USE_STYLE_REF") == "1":
        files.append("refs/style.png")
    return files[:4]

def ref_text(paths):
    names = {"refs/mira.png": "the girl in image {i}", "refs/nurlan.png": "the man in image {i}",
             "refs/style.png": "the art style of image {i}"}
    if not paths:
        return ""
    parts = [names[p].format(i=i) for i, p in enumerate(paths)]
    return "Use " + ", ".join(parts) + ". "

def save_b64(b64, path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    im = Image.open(io.BytesIO(base64.b64decode(b64))).convert("RGB")
    im.save(path, quality=92)
    return im.size

def run_klein(model, name, prompt, report):
    paths = refs_for(prompt)
    data = {"prompt": ref_text(paths) + STYLE + prompt, "width": "768", "height": "1360", "seed": "7"}
    files = {f"input_image_{i}": (os.path.basename(p), open(p, "rb"), "image/png") for i, p in enumerate(paths)}
    t = time.time()
    for attempt in range(4):
        for f in files.values():
            f[1].seek(0)
        r = requests.post(BASE + "@cf/black-forest-labs/" + model, headers=H, data=data, files=files, timeout=180)
        if r.status_code < 500 and "Capacity" not in r.text:
            break
        time.sleep(5 * (attempt + 1))
    dt = round(time.time() - t, 1)
    return finish(r, model, name, dt, report)

def run_schnell(name, prompt, report):
    t = time.time()
    r = requests.post(BASE + "@cf/black-forest-labs/flux-1-schnell", headers=H,
                      json={"prompt": STYLE + prompt, "steps": 8}, timeout=180)
    dt = round(time.time() - t, 1)
    return finish(r, "flux-1-schnell", name, dt, report)

def finish(r, model, name, dt, report):
    entry = {"model": model, "shot": name, "seconds": dt, "http": r.status_code}
    try:
        j = r.json()
        img = (j.get("result") or {}).get("image")
        if img:
            entry["size"] = save_b64(img, f"tests/flux/{model}{SUFFIX}/{name}.jpg")
            entry["ok"] = True
        else:
            entry["ok"] = False
            entry["error"] = json.dumps(j.get("errors") or j)[:500]
    except Exception as e:  # non-JSON response
        entry["ok"] = False
        entry["error"] = f"{e}: {r.text[:300]}"
    print(entry, flush=True)
    report.append(entry)

def main():
    models = sys.argv[1:] or os.environ.get("MODELS", "flux-2-klein-4b,flux-2-klein-9b,flux-1-schnell").split(",")
    report = []
    for name, prompt in SHOTS.items():
        for m in models:
            if m == "flux-1-schnell":
                run_schnell(name, prompt, report)
            else:
                run_klein(m, name, prompt, report)
    os.makedirs("tests/flux", exist_ok=True)
    json.dump(report, open(f"tests/flux/report{SUFFIX}.json", "w"), ensure_ascii=False, indent=1)
    ok = sum(e["ok"] for e in report)
    print(f"done: {ok}/{len(report)} ok")
    if ok == 0:
        sys.exit(1)

if __name__ == "__main__":
    main()
