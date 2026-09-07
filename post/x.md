スマホから一言で、自分のMacの Claude Code / Codex が動き、結果だけ返ってくる。Macが寝ていてもクラウドが引き取る。
GLM-5.3 なら Claude Sonnet 5 の約1/3の単価で約1.8倍速(1問の実測)。

先手 → curl -fsSL https://teai.io/te | sh
この動画も先手が作りました。プロンプトは返信に。
---
先手に頼んだプロンプト:
「sente-intro-video を clone して ./make.sh を実行し、30秒と15秒の紹介動画を作って。ナレーションは本人の声。数字は facts.json の実測値だけ。終わったら out/ の2本と Whisper の読み確認を報告して」

出典: teai.io 料金表(2026-09-05)・同じ1問を api.teai.io に投げた実測(2026-09-07・1回)
