"""ElevenLabs API test: find the series narrator voice and voice a short line.

Env: ELEVENLABS_API_KEY. Output: tests/voice/test.mp3 + tests/voice/report.json
"""
import json, os, sys
import requests

KEY = os.environ.get("ELEVENLABS_API_KEY", "").strip()
API = "https://api.elevenlabs.io/v1"
H = {"xi-api-key": KEY}
VOICE_NAME = os.environ.get("VOICE_NAME", "Maxim")
TEXT = ("Капля срывается с мокрой косички Миры и падает ей на воротник. "
        "Папа замирает. Если на волосах осталась ржавая вода, у вас есть десять минут. "
        "А за окном снова начинается дождь.")

report = {}

def out():
    os.makedirs("tests/voice", exist_ok=True)
    json.dump(report, open("tests/voice/report.json", "w"), ensure_ascii=False, indent=1)
    print(json.dumps(report, ensure_ascii=False, indent=1))

def main():
    if not KEY:
        report["error"] = "ELEVENLABS_API_KEY secret is missing"
        out(); return

    sub = requests.get(f"{API}/user/subscription", headers=H, timeout=30)
    if sub.ok:
        j = sub.json()
        report["plan"] = {k: j.get(k) for k in ("tier", "character_count", "character_limit", "next_character_count_reset_unix")}
    else:
        report["subscription_http"] = [sub.status_code, sub.text[:300]]

    models = requests.get(f"{API}/models", headers=H, timeout=30)
    ids = [m["model_id"] for m in models.json()] if models.ok else []
    report["models"] = ids
    model = next((m for m in ids if "v4" in m), None) or ("eleven_v3" if "eleven_v3" in ids else "eleven_multilingual_v2")
    report["model_used"] = model

    voices = requests.get(f"{API}/voices", headers=H, timeout=30).json().get("voices", [])
    report["my_voices"] = [v["name"] for v in voices]
    voice = next((v for v in voices if VOICE_NAME.lower() in v["name"].lower()), None)

    if not voice:
        sh = requests.get(f"{API}/shared-voices", headers=H, timeout=30,
                          params={"search": VOICE_NAME, "language": "ru", "page_size": 10}).json()
        cands = sh.get("voices", [])
        report["library_matches"] = [c.get("name") for c in cands]
        if not cands:
            report["error"] = "voice not found"; out(); sys.exit(1)
        c = cands[0]
        add = requests.post(f"{API}/voices/add/{c['public_owner_id']}/{c['voice_id']}", headers=H,
                            json={"new_name": c["name"]}, timeout=30)
        report["library_add_http"] = [add.status_code, add.text[:300]]
        voice = {"voice_id": add.json().get("voice_id", c["voice_id"]) if add.ok else c["voice_id"], "name": c["name"]}

    report["voice_used"] = voice["name"]
    r = requests.post(f"{API}/text-to-speech/{voice['voice_id']}", headers=H, timeout=120,
                      params={"output_format": "mp3_44100_128"},
                      json={"text": TEXT, "model_id": model})
    report["tts_http"] = r.status_code
    if r.ok and r.headers.get("content-type", "").startswith("audio"):
        os.makedirs("tests/voice", exist_ok=True)
        open("tests/voice/test.mp3", "wb").write(r.content)
        report["mp3_bytes"] = len(r.content)
        report["characters"] = len(TEXT)
        out()
    else:
        report["tts_error"] = r.text[:500]
        out(); sys.exit(1)

if __name__ == "__main__":
    main()
