#!/usr/bin/env python3
"""Fallback narrator when no koe.live voice is configured: macOS `say` (Kyoko) per sentence → mp3, same timeline.json shape
as narrate.py so cards/compose work unchanged. Marked as a stand-in in the timeline (voice: "say")."""
import json, pathlib, subprocess, re
ROOT = pathlib.Path(__file__).resolve().parent.parent
cfg = json.load(open(ROOT / "narration.json"))
def dur(p):
    return float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(p)], capture_output=True, text=True).stdout.strip() or 0)
for ver in [v for v in cfg if re.fullmatch(r"v\d+", v)]:
    wd = ROOT / "work" / ver; wd.mkdir(parents=True, exist_ok=True); t = 0.0; tl = []
    for seg in cfg[ver]:
        aiff = wd / f"{seg['id']}.aiff"; mp3 = wd / f"{seg['id']}.mp3"
        subprocess.run(["say", "-v", "Kyoko", "-o", str(aiff), seg["tts"]], check=True)
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(aiff), "-codec:a", "libmp3lame", "-q:a", "2", str(mp3)], check=True); aiff.unlink()
        d = dur(mp3); tl.append({**seg, "start": round(t, 2), "voice_dur": round(d, 2), "end": round(t + d + seg["hold"], 2), "heard": "(say stand-in, not verified)"}); t += d + seg["hold"]
    json.dump({"total": round(t, 2), "voice": "say", "segments": tl}, open(wd / "timeline.json", "w"), ensure_ascii=False, indent=1)
    print(ver, "total %.1fs (macOS say stand-in)" % t)
