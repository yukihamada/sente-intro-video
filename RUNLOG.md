# 先手による自走ログ(証拠)

実行: m5(YUKInoMacBook-Pro・128GB) 2026-09-07 20:2x JST

```
SKIP_RECORD=1 KOE_USER_ID=yukihamada te agent run intro-video "SKIP_RECORD=1 KOE_USER_ID=yukihamada ./make.sh deps narrate cards compose verify を実行して、30秒と15秒の紹介動画を作り直して(録画は同梱のものを使う)。失敗した段があれば原因を直してその段から再実行。終わったら out/ の2本のパスと秒数、work/v30/timeline.json の heard を1行ずつ報告して。"
```

先手の報告(原文):

- **deps**: OK（SKIP_RECORD=1 で同梱録画を使用）
- **narrate**: OK（全セグメント Whisper 確認済み）
- **cards**: OK（10枚生成）
- **compose**: OK（2本とも合成）
- **verify**: OK（mean_volume 確認済み）
---
**out/ の2本:**
| ファイル | 秒数 | mean_volume |
|---|---|---|
| `out/sente-intro-30s.mp4` | 30.0s | -17.2 dB |
| `out/sente-intro-15s.mp4` | 15.0s | -16.7 dB |
**work/v30/timeline.json heard 一覧:**
| セグメント | heard |
|---|---|
| hook | スマホから一言 |
| mac1 | 自分のMacのクロードコードや |
| mac2 | コーデックスが動いて結果だけ返ってくる |
| cloud | Macが寝ていてもクラウドの作業箱が引き取る |
| cost | モデルは選べる。GLMならクロードの3分の1の値段でほぼ倍速い。安くて早いは同じ予算で3倍の仕事。 |
| cta | 先手。この動画も先手が作りました。 |

成果物(m5): out/sente-intro-30s.mp4 1,286,254B / out/sente-intro-15s.mp4 613,363B(20:30)

## 最終版の再走(m5・2026-09-07 23:0x JST・引数なしの既定 = 同梱録画)

```
KOE_USER_ID=yukihamada te agent run intro-video
```

- record: SKIP（既定=同梱のもの）
- narrate: OK（KOE_USER_ID=yukihamada・本人の声、v30 計 30.0s / v15 計 15.0s、各文 Whisper で読み確認）
- cards: OK（facts.json の数字だけで 11 枚）
- compose: OK（1080x1920 / 30fps / h264+aac）
- verify: OK（2 本とも目標尺ぴったり、音量あり）
成果物：
- `/Users/yukihamada/workspace/sente-intro-video/out/sente-intro-30s.mp4` — 30.0s、mean_volume -16.9 dB
- `/Users/yukihamada/workspace/sente-intro-video/out/sente-intro-15s.mp4` — 15.0s、mean_volume -16.5 dB
work/v30/timeline.json の heard（Whisper 読み確認）:
- hook: スマホから一言
- mac1: 自分のMacのクロードコードや
- mac2: コーデックスが動いて結果だけ返ってくる
- cloud: Macが寝ていてもクラウドの作業箱が引き取る
- cost: モデルは選べる。GLMならクロードの3分の1の値段でほぼ倍速い。安くて早いは同じ予算で3倍の仕事。
- cta: 先手。この動画も先手が作りました。
固有名詞（クロードコード・コーデックス・GLM・先手）すべて正しく聞き取れています。公開はしていません。
✅完了（証拠：上記 out/ 2 本と heard 一覧）

成果物(m5): out/sente-intro-30s.mp4 1,356,478B / out/sente-intro-15s.mp4 743,858B(23:01)
