#!/usr/bin/env python3
"""Synthesize the narration sentence by sentence with Koe (the owner's own voice), measure where the speech really ends,
verify the reading with Whisper, and lay out the timeline so each cut hits its target length exactly.

  narration.json  → work/<ver>/<id>.mp3 + work/<ver>/timeline.json
  env: KOE_USER_ID (required), VERIFY=0 (skip Whisper), REDO=1 (re-synthesize even if cached), WHISPER_PY (python with mlx_whisper)

Timeline rule: a segment shows for its spoken length + a hold. Holds are distributed by `weight` so the total equals
`targets[ver]` (30.0 / 15.0). No segment is shorter than `min_segment_s`, so every caption stays readable."""
import json, os, sys, subprocess, urllib.request, time, pathlib, re
ROOT = pathlib.Path(__file__).resolve().parent.parent
cfg = json.load(open(ROOT / "narration.json"))
uid = os.environ.get(cfg["voice"]["user_id_env"], "")
if not uid: sys.exit("set %s (koe.live user id whose voice narrates)" % cfg["voice"]["user_id_env"])

def dur(p):
    o = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(p)], capture_output=True, text=True).stdout.strip()
    return float(o or 0)

def speech_span(p):
    """(start, end) of the actual voice: Koe pads silence before and after the sentence; the cut uses only the voice."""
    total = dur(p)
    r = subprocess.run(["ffmpeg", "-i", str(p), "-af", "silencedetect=noise=-38dB:d=0.2", "-f", "null", "-"], capture_output=True, text=True).stderr
    starts = [float(m) for m in re.findall(r"silence_start: ([0-9.]+)", r)]
    ends = [float(m) for m in re.findall(r"silence_end: ([0-9.]+)", r)]
    a = 0.0
    if starts and starts[0] < 0.05 and ends: a = max(0.0, ends[0] - 0.08)          # leading silence
    b = total
    if starts and (len(ends) < len(starts) or ends[-1] < starts[-1]): b = min(total, starts[-1] + 0.12)   # trailing silence
    return round(a, 2), round(b, 2)

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

def layout(segs, target, min_len):
    """speech lengths are fixed; every segment lasts >= min_len (a caption must be readable); the leftover is split by weight."""
    holds = [max(0.0, min_len - s["speech"]) for s in segs]
    left = target - sum(s["speech"] for s in segs) - sum(holds)
    if left < -0.4: sys.exit("%s: speech %.1fs + minimum holds exceed the target %.1fs by %.1fs — shorten a sentence" % (segs[0].get("ver", "?"), sum(s["speech"] for s in segs), target, -left))
    if left < 0:   # up to 0.4 s over: shave it from the holds (no caption drops below min_len - 0.4)
        over = -left; hs = sum(holds) or 1.0
        holds = [h - over * h / hs for h in holds]; left = 0.0
        print("  note: %s ran %.1fs over; holds shaved proportionally" % (segs[0].get("ver", "?"), over))
    ws = [s["weight"] for s in segs]; wsum = sum(ws) or 1.0
    return [h + left * w / wsum for h, w in zip(holds, ws)]

for ver in [v for v in cfg if re.fullmatch(r"v\d+", v)]:
    wd = ROOT / "work" / ver; wd.mkdir(parents=True, exist_ok=True); target = cfg["targets"][ver]; segs = []
    for seg in cfg[ver]:
        mp3 = wd / f"{seg['id']}.mp3"; txt = wd / f"{seg['id']}.txt"
        if not mp3.exists() or os.environ.get("REDO") or (txt.exists() and txt.read_text() != seg["tts"]):
            speak(seg["tts"], mp3); txt.write_text(seg["tts"])
        elif not txt.exists(): txt.write_text(seg["tts"])
        heard = whisper(mp3) if os.environ.get("VERIFY", "1") == "1" else ""
        a, b = speech_span(mp3)
        segs.append({**seg, "ver": ver, "speech_start": a, "speech_end": b, "speech": round(b - a, 2), "file_dur": round(dur(mp3), 2), "heard": heard})
    holds = layout(segs, target, cfg.get("min_segment_s", 3.0)); t = 0.0; out = []
    for s, h in zip(segs, holds):
        out.append({**s, "hold": round(h, 2), "start": round(t, 2), "end": round(t + s["speech"] + h, 2)}); t += s["speech"] + h
    json.dump({"total": round(t, 2), "target": target, "voice": "koe:" + uid, "segments": out}, open(wd / "timeline.json", "w"), ensure_ascii=False, indent=1)
    print(ver, "total %.1fs (target %.1f)" % (t, target))
    for s in out: print("  %-6s %5.1f-%5.1f speech %.1fs hold %.1fs | %s\n         heard: %s" % (s["id"], s["start"], s["end"], s["speech"], s["hold"], s["tts"], s["heard"]))
