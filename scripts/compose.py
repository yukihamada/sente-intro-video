#!/usr/bin/env python3
"""Assembles out/sente-intro-<N>s.mp4 (1080x1920, 30 fps, h264+aac) from work/<ver>/timeline.json, work/footage/*.mp4,
work/cards/*.png and work/<ver>/*.mp3. One ffmpeg call per version; the timeline is the single source of truth.
Writes to a temp file and renames on success, so an interrupted run never leaves a half-written mp4 in out/.
  scripts/compose.py [v30 v15 ...]"""
import json, pathlib, subprocess, sys, re, os
ROOT = pathlib.Path(__file__).resolve().parent.parent
W, H, FPS = 1080, 1920, 30
BG = "0x0D131F"
FOOT = ROOT / "work" / "footage"; CARDS = ROOT / "work" / "cards"; OUT = ROOT / "out"; OUT.mkdir(exist_ok=True)
ACTION_S = 4.2          # seconds of real action (prompt → send → result) to show from the end of a clip
PHONE_H = int(H * 0.86)  # footage height on the canvas
PHONE_Y = 96

def probe(p):
    o = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height:format=duration", "-of", "json", str(p)], capture_output=True, text=True).stdout
    j = json.loads(o); st = j["streams"][0]
    return int(st["width"]), int(st["height"]), float(j["format"]["duration"])

def build(ver):
    tl = json.load(open(ROOT / "work" / ver / "timeline.json")); total = tl["total"]; segs = tl["segments"]
    inputs = ["-f", "lavfi", "-i", f"color=c={BG}:s={W}x{H}:r={FPS}:d={total:.2f}"]
    fc = []; idx = 1; last = "[0:v]"
    # one footage window per run of consecutive segments that share a phone scene
    runs = []
    for s in segs:
        if runs and runs[-1]["scene"] == s["scene"]: runs[-1]["end"] = s["end"]
        else: runs.append({"scene": s["scene"], "start": s["start"], "end": s["end"]})
    mask = CARDS / "phone_mask.png"
    for r in runs:
        if not r["scene"].startswith("phone"): continue
        clip = FOOT / f"{r['scene']}.mp4"; w, h, d = probe(clip); need = r["end"] - r["start"]
        pw = int(round(PHONE_H * w / h / 2) * 2)
        # simctl recordings end at the last screen change (= the result on screen) and launch latency varies per run,
        # so anchor on the end: the result must be visible >= 1.2 s before the scene ends, then hold the last frame.
        action = max(1.0, min(ACTION_S, need - 1.2)); skip = max(0.0, d - action)
        inputs += ["-ss", f"{skip:.2f}", "-i", str(clip)]; vi = idx; idx += 1
        inputs += ["-loop", "1", "-i", str(mask)]; mi = idx; idx += 1
        fc.append(f"[{vi}:v]tpad=stop_mode=clone:stop_duration=60,fps={FPS},scale={pw}:{PHONE_H},format=rgba[pv{vi}]")
        fc.append(f"[{mi}:v]scale={pw}:{PHONE_H},format=gray[pm{vi}]")
        fc.append(f"[pv{vi}][pm{vi}]alphamerge,setpts=PTS-STARTPTS+{r['start']:.2f}/TB[p{vi}]")
        fc.append(f"{last}[p{vi}]overlay=x=(W-w)/2:y={PHONE_Y}:eof_action=pass:enable='between(t,{r['start']:.2f},{r['end']:.2f})'[v{vi}]")
        last = f"[v{vi}]"
    # cards: lower third per phone segment; full cards for cost / cta (compact cost card on the 15 s cut)
    for s in segs:
        if s["scene"].startswith("phone"): png = CARDS / f"{ver}_{s['id']}.png"
        elif s["scene"] == "card_cost": png = CARDS / ("cost_compact.png" if ver == "v15" else "cost.png")
        elif s["scene"] == "card_cta": png = CARDS / "cta.png"
        else: continue
        inputs += ["-loop", "1", "-t", f"{total:.2f}", "-i", str(png)]
        fc.append(f"[{idx}:v]format=rgba,fade=t=in:st={s['start']:.2f}:d=0.25:alpha=1[c{idx}]")
        fc.append(f"{last}[c{idx}]overlay=0:0:eof_action=pass:enable='between(t,{s['start']:.2f},{s['end']:.2f})'[v{idx}]")
        last = f"[v{idx}]"; idx += 1
    # narration: each sentence at its start, trimmed to the spoken part; loudness normalized.
    # The CTA card stays crisp to the last frame (no video fade-out).
    a_in = []
    for s in segs:
        inputs += ["-i", str(ROOT / "work" / ver / f"{s['id']}.mp3")]
        fc.append(f"[{idx}:a]atrim=0:{s['speech'] + 0.3:.2f},adelay={int(s['start'] * 1000)}|{int(s['start'] * 1000)}[a{idx}]"); a_in.append(f"[a{idx}]"); idx += 1
    fc.append("".join(a_in) + f"amix=inputs={len(a_in)}:normalize=0,loudnorm=I=-16:TP=-1.5:LRA=11,apad=whole_dur={total:.2f}[aout]")
    fc.append(f"{last}fade=t=in:st=0:d=0.3,format=yuv420p[vout]")
    out = OUT / f"sente-intro-{ver[1:]}s.mp4"; tmp = OUT / f".{out.name}.part.mp4"
    cmd = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", *inputs, "-filter_complex", ";".join(fc),
           "-map", "[vout]", "-map", "[aout]", "-t", f"{total:.2f}", "-r", str(FPS), "-c:v", "libx264", "-preset", "medium", "-crf", "20",
           "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", str(tmp)]
    subprocess.run(cmd, check=True)
    w, h, d = probe(tmp); assert (w, h) == (W, H) and abs(d - total) < 0.2, (w, h, d, total)
    os.replace(tmp, out)
    print(f"  {out}  {d:.1f}s")

if __name__ == "__main__":
    vers = sys.argv[1:] or sorted(v.name for v in (ROOT / "work").iterdir() if re.fullmatch(r"v\d+", v.name))
    for v in vers: build(v)
