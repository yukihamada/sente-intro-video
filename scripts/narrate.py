#!/usr/bin/env python3
"""Synthesize narration sentence by sentence with Koe (the owner's own voice), measure durations, verify with Whisper.
Writes work/<ver>/<id>.mp3 + work/<ver>/timeline.json. Never truncates: every sentence is synthesized and checked."""
import json, os, sys, subprocess, urllib.request, time, pathlib, re
ROOT = pathlib.Path(__file__).resolve().parent.parent
cfg = json.load(open(ROOT / "narration.json"))
uid = os.environ.get(cfg["voice"]["user_id_env"], "")
if not uid: sys.exit("set %s (koe.live user id whose voice narrates)" % cfg["voice"]["user_id_env"])
def dur(p):
    o = subprocess.run(["ffprobe","-v","error","-show_entries","format=duration","-of","csv=p=0",str(p)],capture_output=True,text=True).stdout.strip()
    return float(o or 0)
def speak(text, out):
    body = json.dumps({"text": text, "user_id": uid, "lang": cfg["voice"]["lang"]}).encode()
    for attempt in range(4):
        try:
            req = urllib.request.Request(cfg["voice"]["api"], data=body, headers={"content-type": "application/json", "User-Agent": "sente-intro-video/1"})
            with urllib.request.urlopen(req, timeout=120) as r:
                data = r.read()
            if len(data) > 2000: out.write_bytes(data); return
        except Exception as e: err = e
        time.sleep(3 * (attempt + 1))
    sys.exit("koe speak failed for: %s (%s)" % (text, err))
def whisper(p):
    py = os.environ.get("WHISPER_PY", "/Library/Frameworks/Python.framework/Versions/3.11/bin/python3")
    code = "import mlx_whisper,sys;print(mlx_whisper.transcribe(sys.argv[1],path_or_hf_repo='mlx-community/whisper-large-v3-turbo',language='ja')['text'])"
    r = subprocess.run([py, "-c", code, str(p)], capture_output=True, text=True)
    return r.stdout.strip().splitlines()[-1] if r.stdout.strip() else "(whisper failed: %s)" % r.stderr[-200:]
for ver in [v for v in cfg if re.fullmatch(r"v\d+", v)]:
    wd = ROOT / "work" / ver; wd.mkdir(parents=True, exist_ok=True)
    t = 0.0; timeline = []
    for seg in cfg[ver]:
        mp3 = wd / f"{seg['id']}.mp3"
        if not mp3.exists() or os.environ.get("REDO"): speak(seg["tts"], mp3)
        d = dur(mp3); heard = whisper(mp3) if os.environ.get("VERIFY", "1") == "1" else ""
        timeline.append({**seg, "start": round(t, 2), "voice_dur": round(d, 2), "end": round(t + d + seg["hold"], 2), "heard": heard})
        t += d + seg["hold"]
    json.dump({"total": round(t, 2), "segments": timeline}, open(wd / "timeline.json", "w"), ensure_ascii=False, indent=1)
    print(ver, "total %.1fs" % t)
    for s in timeline: print("  %-6s %5.1f-%5.1f voice %.1fs | %s\n         heard: %s" % (s["id"], s["start"], s["end"], s["voice_dur"], s["tts"], s["heard"]))
