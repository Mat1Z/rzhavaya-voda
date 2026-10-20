"""Voice the episode script -> voice.mp3.

ElevenLabs (voice "Maxim") when the API key can find the voice; otherwise free Microsoft Edge TTS as a fallback.
Usage: python pipeline/make_voice.py episodes/03
Env: ELEVENLABS_API_KEY (optional), ELEVEN_VOICE_ID (optional), VOICE_NAME (default Maxim)
"""
import asyncio, os, sys
import requests

API = "https://api.elevenlabs.io/v1"


def eleven(text, out):
    key = os.environ.get("ELEVENLABS_API_KEY", "").strip()
    if not key:
        return "нет ключа"
    H = {"xi-api-key": key}
    vid = os.environ.get("ELEVEN_VOICE_ID", "").strip()
    name = os.environ.get("VOICE_NAME", "Maxim").lower()
    if not vid:
        r = requests.get(f"{API}/voices", headers=H, timeout=30)
        if not r.ok:
            return f"voices: {r.status_code} {r.text[:150]}"
        vid = next((v["voice_id"] for v in r.json().get("voices", []) if name in v["name"].lower()), None)
        if not vid:
            return "голос не найден в «Мои голоса»"
    model = os.environ.get("ELEVEN_MODEL", "eleven_v3")
    for m in (model, "eleven_multilingual_v2"):
        r = requests.post(f"{API}/text-to-speech/{vid}", headers=H, timeout=180,
                          params={"output_format": "mp3_44100_128"}, json={"text": text, "model_id": m})
        if r.ok and r.headers.get("content-type", "").startswith("audio"):
            open(out, "wb").write(r.content)
            print(f"voice: ElevenLabs ({m})")
            return None
    return f"tts: {r.status_code} {r.text[:150]}"


async def edge(text, out):
    import edge_tts
    await edge_tts.Communicate(text, "ru-RU-DmitryNeural", rate="-8%", pitch="-6Hz").save(out)
    print("voice: Edge TTS ru-RU-DmitryNeural (запасной голос)")


def main(ep):
    out = f"{ep}/voice.mp3"
    if os.path.exists(out):
        print("voice: already exists"); return
    text = open(f"{ep}/script.txt", encoding="utf-8").read().strip()
    err = eleven(text, out)
    if err:
        print(f"ElevenLabs не использован: {err}")
        asyncio.run(edge(text, out))


if __name__ == "__main__":
    main(sys.argv[1].rstrip("/"))
