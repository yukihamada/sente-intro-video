#!/usr/bin/env python3
"""Synthesize the narration sentence by sentence with Koe (the owner's own voice), measure where the speech really ends,
verify the reading with Whisper, and lay out the timeline so each cut hits its target length exactly.

  narration.json  → work/<ver>/<id>.mp3 + work/<ver>/timeline.json
  env: KOE_USER_ID (required), VERIFY=0 (skip Whisper), REDO=1 (re-synthesize even if cached), WHISPER_PY (python with mlx_whisper)

Timeline rule: a segment shows for its spoken length + a hold. Holds are distributed by `weight` so the total equals
`targets[ver]` (30.0 / 15.0). A segment with `min_end` (the hook) is never shorter than that, so its caption is readable."""
import json, os, sys, subprocess, urllib.request, time, pathlib, re
ROOT = pathlib.Path(__file__).resolve().parent.parent
cfg = json.load(open(ROOT / "narration.json"))
uid = os.environ.get(cfg["voice"]["user_id_env"], "")
if not uid: sys.exit("set %s (koe.live user id whose voice narrates)" % cfg["voice"]["user_id_env"])

def dur(p):
    o = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(p)], capture_output=True, text=True).stdout.strip()
    return float(o or 0)

def speech_end(p):
    """Where the voice actually stops: the start of a trailing silence (Koe pads ~1-2 s of room at the end)."""
    total = dur(p)
    r = subprocess.run(["ffmpeg", "-i", str(p), "-af", "silencedetect=noise=-38dB:d=0.25", "-f", "null", "-"], capture_output=True, text=True).stderr
    starts = [float(m) for m in re.findall(r"silence_start: ([0-9.]+)", r)]
    ends = [float(m) for m in re.findall(r"silence_end: ([0-9.]+)", r)]
    if starts and (len(ends) < len(starts) or total - starts[-1] < 0.6 + (total - ends[-1] if ends and ends[-1] > starts[-1] else 0)):
        return min(total, starts[-1] + 0.12)
    return total

def speak(text, out):
    body = json.dumps({"text": text, "user_id": uid, "lang": cfg["voice"]["lang"]}).encode(); err = None
    for attempt in range(4):
        try:
            req = urllib.request.Request(cfg["voice"]["api"], data=body, headers={"content-type": "application/json", "User-Agent": "sente-intro-video/1"})
            with urllib.request.urlopen(req, timeout=120) as r: data = r.read()
            if len(data) > 2000: out.write_bytes(data); return
        except Exception as e: err = e
        time.sleep(3 * (attempt + 1))
    sys.exit("koe speak failed for: %s (%s)" % (text, err))

def whisper(p):
    py = os.environ.get("WHISPER_PY", sys.executable)
    code = "import mlx_whisper,sys;print(mlx_whisper.transcribe(sys.argv[1],path_or_hf_repo='mlx-community/whisper-large-v3-turbo',language='ja')['text'])"
    r = subprocess.run([py, "-c", code, str(p)], capture_output=True, text=True)
    return r.stdout.strip().splitlines()[-1] if r.stdout.strip() else "(whisper failed: %s)" % r.stderr[-200:]

def layout(segs, target):
    """speech lengths are fixed; holds = leftover time split by weight; min_end segments take what they need first."""
    speech = sum(s["speech"] for s in segs); left = max(0.0, target - speech)
    holds = [0.0] * len(segs)
    # 1) reserve for min_end segments (they come first in the cut, so their end is their own start + speech + hold)
    t = 0.0
    for i, s in enumerate(segs):
        if s.get("min_end"):
            need = max(0.0, s["min_end"] - (t + s["speech"])); holds[i] = min(need, left); left -= holds[i]
        t += s["speech"] + holds[i]
    # 2) the rest by weight (min_end segments do not take a second share)
    ws = [s["weight"] if not s.get("min_end") else 0.0 for s in segs]; wsum = sum(ws) or 1.0
    for i, w in enumerate(ws): holds[i] += left * w / wsum
    return holds

for ver in [v for v in cfg if re.fullmatch(r"v\d+", v)]:
    wd = ROOT / "work" / ver; wd.mkdir(parents=True, exist_ok=True); target = cfg["targets"][ver]; segs = []
    for seg in cfg[ver]:
        mp3 = wd / f"{seg['id']}.mp3"; txt = wd / f"{seg['id']}.txt"
        if not mp3.exists() or os.environ.get("REDO") or (txt.exists() and txt.read_text() != seg["tts"]):
            speak(seg["tts"], mp3); txt.write_text(seg["tts"])
        elif not txt.exists(): txt.write_text(seg["tts"])
        heard = whisper(mp3) if os.environ.get("VERIFY", "1") == "1" else ""
        segs.append({**seg, "speech": round(speech_end(mp3), 2), "file_dur": round(dur(mp3), 2), "heard": heard})
    holds = layout(segs, target); t = 0.0; out = []
    for s, h in zip(segs, holds):
        out.append({**s, "hold": round(h, 2), "start": round(t, 2), "end": round(t + s["speech"] + h, 2)}); t += s["speech"] + h
    json.dump({"total": round(t, 2), "target": target, "voice": "koe:" + uid, "segments": out}, open(wd / "timeline.json", "w"), ensure_ascii=False, indent=1)
    print(ver, "total %.1fs (target %.1f)" % (t, target))
    for s in out: print("  %-6s %5.1f-%5.1f speech %.1fs hold %.1fs | %s\n         heard: %s" % (s["id"], s["start"], s["end"], s["speech"], s["hold"], s["tts"], s["heard"]))
