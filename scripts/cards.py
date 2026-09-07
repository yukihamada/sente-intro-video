#!/usr/bin/env python3
"""Renders the overlay cards (1080x1920, transparent PNG) from narration.json + work/<ver>/timeline.json with Playwright.
Lower-third caption per segment; full-frame cards for the cost table and the CTA. Facts on the cost card come from
facts.json (measured/quoted values with their source) — never typed into the template by hand."""
import json, pathlib, sys, html, re
from playwright.sync_api import sync_playwright
ROOT = pathlib.Path(__file__).resolve().parent.parent
facts = json.load(open(ROOT / "facts.json"))
cfg = json.load(open(ROOT / "narration.json"))

CSS = """
<style>
@font-face{font-family:JP;src:local("Hiragino Sans W6"),local("HiraginoSans-W6"),local("Hiragino Sans");}
@font-face{font-family:JPB;src:local("Hiragino Sans W8"),local("HiraginoSans-W8"),local("Hiragino Sans W7"),local("Hiragino Sans");}
:root{--ink:#F3F5F9;--dim:#A8B3C4;--accent:#5B8CFF;--bg:#0D131F;--panel:rgba(10,15,26,.78);--mono:"SF Mono",Menlo,monospace}
html,body{margin:0;width:1080px;height:1920px;background:transparent;font-family:JP,"Hiragino Sans",sans-serif;color:var(--ink)}
.full{position:absolute;inset:0;background:var(--bg)}
.third{position:absolute;left:0;right:0;bottom:0;padding:0 72px 128px;background:linear-gradient(180deg,rgba(13,19,31,0) 0%,rgba(13,19,31,.82) 38%,rgba(13,19,31,.96) 100%);height:560px;box-sizing:border-box;display:flex;flex-direction:column;justify-content:flex-end;gap:22px}
.cap{font-family:JPB;font-size:64px;line-height:1.22;letter-spacing:-.01em;text-wrap:balance;font-weight:800}
.sub{font-size:40px;line-height:1.35;color:var(--dim)}
.eyebrow{font-size:30px;letter-spacing:.18em;color:var(--accent);text-transform:uppercase;font-family:var(--mono)}
.brand{position:absolute;top:96px;left:72px;display:flex;align-items:center;gap:20px}
.brand .mark{width:26px;height:26px;border-radius:50%;background:var(--accent);box-shadow:0 0 0 10px rgba(91,140,255,.18)}
.brand .name{font-family:JPB;font-size:38px;letter-spacing:.06em}
.brand .en{font-family:var(--mono);font-size:26px;color:var(--dim);margin-left:6px}
/* cost card */
.cost{position:absolute;inset:0;padding:0 72px;display:flex;flex-direction:column;justify-content:center;gap:56px}
.h1{font-family:JPB;font-size:84px;line-height:1.15;letter-spacing:-.02em;text-wrap:balance}
.h1 b{color:var(--accent)}
table{width:100%;border-collapse:collapse;font-variant-numeric:tabular-nums}
th,td{padding:26px 8px;border-bottom:2px solid rgba(255,255,255,.10);text-align:right;font-size:40px}
th{color:var(--dim);font-weight:500;font-size:30px;letter-spacing:.06em}
td:first-child,th:first-child{text-align:left}
td.m{font-family:var(--mono);font-size:38px}
tr.hi td{color:var(--ink);font-family:JPB}
tr.hi td:first-child{color:var(--accent)}
.big{display:flex;gap:40px}
.big .kpi{flex:1;padding:36px 40px;border:2px solid rgba(91,140,255,.35);border-radius:28px;background:rgba(91,140,255,.08)}
.kpi .n{font-family:JPB;font-size:112px;line-height:1;letter-spacing:-.03em}
.kpi .n small{font-size:48px;color:var(--dim);margin-left:8px}
.kpi .l{margin-top:16px;font-size:32px;color:var(--dim);line-height:1.35}
.src{font-size:26px;color:var(--dim);line-height:1.5;font-family:var(--mono)}
/* cta card */
.cta{position:absolute;inset:0;padding:0 72px;display:flex;flex-direction:column;justify-content:center;gap:64px}
.cmd{font-family:var(--mono);font-size:44px;padding:40px 44px;border-radius:24px;background:#111A2B;border:2px solid rgba(255,255,255,.12);color:#E8EEFF;word-break:break-all;line-height:1.4}
.cmd .p{color:var(--accent)}
.line{font-size:44px;line-height:1.45;color:var(--dim)}
.line b{color:var(--ink);font-family:JPB}
</style>
"""

def brand():
    return '<div class="brand"><div class="mark"></div><div class="name">先手</div><div class="en">Sente</div></div>'

def third(seg):
    sub = f'<div class="sub">{html.escape(seg["sub"])}</div>' if seg.get("sub") else ""
    return f'{CSS}<div class="third"><div class="cap">{html.escape(seg["cap"])}</div>{sub}</div>{brand()}'

def cost_card(compact):
    p = facts["prices_usd_per_1m"]; s = facts["speed_same_prompt"]
    glm, son, opus = p["z-ai/glm-5.3"], p["anthropic/claude-sonnet-5"], p["anthropic/claude-opus-5"]
    ratio_out = son["out"] / glm["out"]; ratio_speed = s["anthropic/claude-sonnet-5"]["total_s"] / s["z-ai/glm-5.3"]["total_s"]
    rows = "".join(
        f'<tr class="{"hi" if m == "z-ai/glm-5.3" else ""}"><td>{html.escape(lbl)}</td><td class="m">${p[m]["in"]:.2f}</td><td class="m">${p[m]["out"]:.2f}</td><td class="m">{s[m]["total_s"]:.1f}s</td></tr>'
        for m, lbl in [("z-ai/glm-5.3", "GLM-5.3"), ("anthropic/claude-sonnet-5", "Claude Sonnet 5"), ("anthropic/claude-opus-5", "Claude Opus 5")])
    table = "" if compact else f'<table><tr><th>モデル(teai.io)</th><th>入力 /1M</th><th>出力 /1M</th><th>同じ1問</th></tr>{rows}</table>'
    return f'''{CSS}<div class="full"></div><div class="cost">
<div class="eyebrow">MODEL IS A CHOICE</div>
<div class="h1">同じ仕事なら、<b>安くて速い</b>方を選べる。</div>
<div class="big">
 <div class="kpi"><div class="n">1/{ratio_out:.1f}<small></small></div><div class="l">出力単価<br>GLM-5.3 ÷ Claude Sonnet 5</div></div>
 <div class="kpi"><div class="n">{ratio_speed:.1f}<small>倍速</small></div><div class="l">同じ質問1回の所要<br>{s["z-ai/glm-5.3"]["total_s"]:.1f}s vs {s["anthropic/claude-sonnet-5"]["total_s"]:.1f}s</div></div>
</div>
{table}
<div class="src">出典: {html.escape(facts["price_source"])} / 速度: {html.escape(facts["speed_source"])}</div>
</div>{brand()}'''

def cta_card():
    return f'''{CSS}<div class="full"></div><div class="cta">
<div class="eyebrow">INSTALL</div>
<div class="h1">先手は、ここから。</div>
<div class="cmd"><span class="p">$</span> {html.escape(facts["install"])}</div>
<div class="line"><b>この動画も、先手が作りました。</b><br>プロンプトとコマンドは説明欄に。</div>
</div>{brand()}'''

def main():
    out = ROOT / "work" / "cards"; out.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        b = p.chromium.launch(); pg = b.new_page(viewport={"width": 1080, "height": 1920}, device_scale_factor=1)
        def shot(name, html_):
            pg.set_content(html_); pg.wait_for_timeout(150)
            pg.screenshot(path=str(out / f"{name}.png"), omit_background=True); print("  ", out / f"{name}.png")
        for ver in [v for v in cfg if re.fullmatch(r"v\d+", v)]:
            for seg in cfg[ver]:
                if seg["scene"].startswith("phone"): shot(f"{ver}_{seg['id']}", third(seg))
        shot("cost", cost_card(compact=False)); shot("cost_compact", cost_card(compact=True)); shot("cta", cta_card())
        b.close()

if __name__ == "__main__": main()
