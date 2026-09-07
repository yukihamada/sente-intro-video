#!/usr/bin/env python3
"""Assembles out/sente-intro-<ver>.mp4 (1080x1920, 30 fps, h264+aac) from work/<ver>/timeline.json, work/footage/*.mp4,
work/cards/*.png and work/<ver>/*.mp3. One ffmpeg call per version; the timeline is the single source of truth.
  scripts/compose.py [v30 v15 ...]"""
import json, pathlib, subprocess, sys, re
ROOT = pathlib.Path(__file__).resolve().parent.parent
W, H, FPS = 1080, 1920, 30
BG = "0x0D131F"
FOOT = ROOT / "work" / "footage"; CARDS = ROOT / "work" / "cards"; OUT = ROOT / "out"; OUT.mkdir(exist_ok=True)

def dur(p):
    return float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(p)], capture_output=True, text=True).stdout.strip() or 0)

def build(ver):
    tl = json.load(open(ROOT / "work" / ver / "timeline.json")); total = tl["total"]; segs = tl["segments"]
    # Footage windows: each phone scene gets one continuous slice of its clip; the slice starts at `skip` so the
    # typed prompt appears right as the voice starts (autosend types at ~2 s after launch).
    # simctl recordings end at the last screen change (= the result on screen), and app launch latency varies per run,
    # so anchor on the end: show the last ACTION_S seconds of the clip (prompt → send → result), then hold the result.
    ACTION_S = 4.2
    clips = {k: {"file": FOOT / f"{k}.mp4", "dur": dur(FOOT / f"{k}.mp4")} for k in ("phone_a", "phone_b")}
    inputs = ["-f", "lavfi", "-i", f"color=c={BG}:s={W}x{H}:r={FPS}:d={total:.2f}"]
    fc = []; idx = 1; last = "[0:v]"
    # phone scenes: contiguous runs of segments sharing a scene share one footage window
    runs = []
    for s in segs:
        if runs and runs[-1]["scene"] == s["scene"]: runs[-1]["end"] = s["end"]
        else: runs.append({"scene": s["scene"], "start": s["start"], "end": s["end"]})
    ph = int(H * 0.86)
    for r in runs:
        if r["scene"] not in clips: continue
        c = clips[r["scene"]]; need = r["end"] - r["start"]
        action = min(ACTION_S, need - 1.2)            # the result must be on screen for >= 1.2 s before the scene ends
        skip = max(0.0, c["dur"] - action)
        inputs += ["-ss", f"{skip:.2f}", "-i", str(c["file"])]
        # scale to 86% height, round the corners (alpha mask), place centered, a little above the lower third
        fc.append(f"[{idx}:v]tpad=stop_mode=clone:stop_duration=40,fps={FPS},scale=-2:{ph},format=rgba,"   # simctl recordings only emit frames on change: hold the last frame
                  f"geq=lum='p(X,Y)':cb='p(X,Y)':cr='p(X,Y)':a='if(lt(X,60)*lt(Y,60)*gt(hypot(60-X,60-Y),60)+gt(X,W-60)*lt(Y,60)*gt(hypot(X-(W-60),60-Y),60)+lt(X,60)*gt(Y,H-60)*gt(hypot(60-X,Y-(H-60)),60)+gt(X,W-60)*gt(Y,H-60)*gt(hypot(X-(W-60),Y-(H-60)),60),0,255)',"
                  f"setpts=PTS-STARTPTS+{r['start']:.2f}/TB[p{idx}]")
        fc.append(f"{last}[p{idx}]overlay=x=(W-w)/2:y=96:eof_action=pass:enable='between(t,{r['start']:.2f},{r['end']:.2f})'[v{idx}]")
        last = f"[v{idx}]"; idx += 1
    # cards: lower thirds per phone segment; full cards for cost / cta (compact cost card on the short cut)
    for s in segs:
        if s["scene"].startswith("phone"): png = CARDS / f"{ver}_{s['id']}.png"
        elif s["scene"] == "card_cost": png = CARDS / ("cost_compact.png" if ver == "v15" else "cost.png")
        elif s["scene"] == "card_cta": png = CARDS / "cta.png"
        else: continue
        inputs += ["-loop", "1", "-t", f"{total:.2f}", "-i", str(png)]
        fade_in = 0.25
        fc.append(f"[{idx}:v]format=rgba,fade=t=in:st={s['start']:.2f}:d={fade_in}:alpha=1[c{idx}]")
        fc.append(f"{last}[c{idx}]overlay=0:0:eof_action=pass:enable='between(t,{s['start']:.2f},{s['end']:.2f})'[v{idx}]")
        last = f"[v{idx}]"; idx += 1
    # narration: each sentence at its start, then loudness normalized
    a_in = []
    for s in segs:
        mp3 = ROOT / "work" / ver / f"{s['id']}.mp3"
        inputs += ["-i", str(mp3)]
        fc.append(f"[{idx}:a]adelay={int(s['start'] * 1000)}|{int(s['start'] * 1000)}[a{idx}]"); a_in.append(f"[a{idx}]"); idx += 1
    fc.append("".join(a_in) + f"amix=inputs={len(a_in)}:normalize=0,loudnorm=I=-16:TP=-1.5:LRA=11,apad=whole_dur={total:.2f}[aout]")
    fc.append(f"{last}fade=t=out:st={total - 0.6:.2f}:d=0.6,format=yuv420p[vout]")
    out = OUT / f"sente-intro-{ver[1:]}s.mp4"
    cmd = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", *inputs, "-filter_complex", ";".join(fc),
           "-map", "[vout]", "-map", "[aout]", "-t", f"{total:.2f}", "-r", str(FPS), "-c:v", "libx264", "-preset", "medium", "-crf", "20",
           "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", str(out)]
    subprocess.run(cmd, check=True)
    print(f"  {out}  {dur(out):.1f}s")

if __name__ == "__main__":
    vers = sys.argv[1:] or sorted(v.name for v in (ROOT / "work").iterdir() if re.fullmatch(r"v\d+", v.name))
    for v in vers: build(v)
