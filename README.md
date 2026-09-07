# sente-intro-video — 先手の紹介動画(30秒 / 15秒)を、先手に作らせる

スマホから自分の Mac の Claude Code / Codex を動かし、Mac が寝ていればクラウドの作業箱が引き取る。
モデルは選べて、GLM なら Claude の約 1/3 の単価でほぼ倍速い。その 30 秒と 15 秒の紹介動画を、
**インストールから合成まで 1 コマンド**で作る。ナレーションは本人の声(koe.live)。数字は `facts.json` の実測・出典だけ。

## できるもの

- `out/sente-intro-30s.mp4` — 1080x1920 / 30fps / 30.0s。構成: 一言 → Mac の Claude Code が動く(実画面) → Mac が寝ていてもクラウド(実画面) → 料金・速度カード → インストール CTA
- `out/sente-intro-15s.mp4` — 同 15.0s(一言 → Mac の Claude Code → 料金・速度 → CTA)

実画面は Sente iOS の**台本トランスポート**(`SENTE_SCRIPT=1`)で決定的に再生した本物の UI(鍵不要・外部通信なし)。

## 1 コマンド

```sh
# 先手を入れる(まだなら)
curl -fsSL https://teai.io/te | sh

# 動画を作る(依存 → Sente iOS をシミュレータでビルド → 台本で実走を録画 → 本人の声で読み上げ → カード → 合成 → 検証)
git clone https://github.com/yukihamada/sente-intro-video && cd sente-intro-video
KOE_USER_ID=<koe.live のあなたのID> ./make.sh
```

`KOE_USER_ID` を省くと macOS の `say` が代読します(本人の声ではない旨が timeline.json に残ります)。
実画面の録画(`work/footage/*.mp4`)はリポジトリに同梱しているので、**Xcode や sente-ios(非公開)が無くても上のコマンドだけで完成**します。
撮り直す場合だけ `SKIP_RECORD=0 SENTE_IOS=<sente-ios の checkout> ./make.sh`(Xcode が必要)。

## 先手に頼むなら(この動画はこのプロンプトで作りました)

```sh
te run "sente-intro-video を clone して ./make.sh を実行し、30秒と15秒の紹介動画を作って。
ナレーションは KOE_USER_ID=yukihamada(本人の声)。数字は facts.json の実測値だけを使い、盛らない。
終わったら out/ の2本と、Whisper の読み確認結果を報告して。"
```

または常駐エージェントとして: `te agent run intro-video`(定義 = `~/.config/sente/agent/intro-video.md`)。

## 数字の出典(facts.json)

| モデル(teai.io) | 入力 /1M | 出力 /1M | 同じ 1 問の所要 |
|---|---:|---:|---:|
| z-ai/glm-5.3 | $1.40 | $4.40 | 5.8s |
| anthropic/claude-sonnet-5 | $3.00 | $15.00 | 10.6s |
| anthropic/claude-opus-5 | $5.00 | $25.00 | 11.7s |

- 単価 = teai.io 料金表(2026-09-05 時点)。「約 1/3」は出力単価 4.40 vs 15.00(=1/3.4)。入力は 1/2.1。
- 速度 = 同じ質問 1 回を api.teai.io に stream で投げた実測(2026-09-07・max_tokens 400)。1 回の実測で、常にこの差ではない。
- 「同じ予算で 3 倍の仕事」は出力単価比からの帰結(トークン数が同じ前提)。

## 仕組み

| 段 | ファイル | 何をするか |
|---|---|---|
| 録画 | `scripts/record.sh` | シミュレータに Sente を入れ、`SENTE_SCRIPT=1 SENTE_AUTOSEND=…` で 2 場面を `simctl io recordVideo` |
| 声 | `scripts/narrate.py` | `narration.json` の 1 文ずつ koe.live `/api/speak` → mp3、`mlx_whisper` で読みを確認、`work/<ver>/timeline.json` |
| カード | `scripts/cards.py` | Playwright で 1080x1920 の透過 PNG(下三分の一の字幕・料金表・CTA)。数字は facts.json から |
| 合成 | `scripts/compose.py` | timeline を正として ffmpeg 1 回で合成。録画は最後の変化(結果表示)に合わせて位置決め、最後のフレームを保持 |

台本を変える = `narration.json`(`tts` は読み上げ用の仮名、`cap`/`sub` は画面の字幕)。数字を変える = `facts.json`。

## 落とし穴

- `simctl io recordVideo` は画面が変わった時だけフレームを出す → 動画長は「最後の変化」まで。合成側で `tpad` して保持している。
- `recordVideo` は SIGINT で終了するが `wait` すると戻らないことがある → ポーリングで待つ。
- シミュレータが固まったら `xcrun simctl shutdown all` → 新しいデバイスを作る。
- Koe の固有名詞は仮名で渡す(クロードコード・コーデックス・ジーエルエム・せんて)。Whisper が「Claude Code / GLM / 先手」と聞き取れたことを `timeline.json` の `heard` で確認する。
