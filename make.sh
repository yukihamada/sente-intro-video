#!/usr/bin/env bash
# 先手(Sente)の紹介動画 30秒 / 15秒を、インストールから一本で作る。
#   ./make.sh                 # 全部(依存→Sente iOS をシミュレータでビルド→台本で実走を録画→本人の声で読み上げ→字幕カード→合成→検証)
#   ./make.sh record compose  # 一部だけ
# 前提: macOS + Xcode(iOS シミュレータ)。KOE_USER_ID = koe.live で声を登録したユーザーID(未設定なら macOS `say` で代読)。
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"; cd "$ROOT"
STEPS=("$@"); [ ${#STEPS[@]} -gt 0 ] || STEPS=(deps app record narrate cards compose verify)
SENTE_IOS="${SENTE_IOS:-$HOME/workspace/sente-ios}"
step() { printf '\n\033[36m▸ %s\033[0m\n' "$*"; }
has() { [[ " ${STEPS[*]} " == *" $1 "* ]]; }

if has deps; then step "deps"
  command -v brew >/dev/null || { echo "Homebrew が必要: https://brew.sh"; exit 2; }
  for b in ffmpeg xcodegen; do command -v $b >/dev/null || brew install $b; done
  python3 -c "import playwright" 2>/dev/null || python3 -m pip install -q playwright
  python3 -m playwright install chromium >/dev/null 2>&1 || true
  command -v te >/dev/null || { echo "先手(te)を入れる: curl -fsSL https://teai.io/te | sh"; curl -fsSL https://teai.io/te | sh; }
  xcode-select -p >/dev/null || { echo "Xcode が必要"; exit 2; }
fi

if has app; then step "Sente iOS をシミュレータ向けにビルド ($SENTE_IOS)"
  [ -d "$SENTE_IOS" ] || git clone https://github.com/yukihamada/sente-ios "$SENTE_IOS"
  ( cd "$SENTE_IOS" && xcodegen generate -q && xcodebuild -project Sente.xcodeproj -scheme Sente -destination 'generic/platform=iOS Simulator' \
      -derivedDataPath build-sim CODE_SIGNING_ALLOWED=NO build -quiet )
fi

if has record; then step "台本トランスポートで実走を録画 (Mac に Claude Code / Mac が寝ている→クラウド)"
  ./scripts/record.sh "$SENTE_IOS"
fi

if has narrate; then step "ナレーション(本人の声・1文ずつ・Whisper で読み確認)"
  if [ -n "${KOE_USER_ID:-}" ]; then python3 scripts/narrate.py
  else echo "KOE_USER_ID 未設定 → macOS say で代読"; python3 scripts/narrate_say.py; fi
fi

if has cards; then step "字幕・料金・CTA カードを描く (facts.json の数字だけを使う)"
  python3 scripts/cards.py
fi

if has compose; then step "合成 (1080x1920 / 30fps / h264+aac)"
  python3 scripts/compose.py
fi

if has verify; then step "検証"
  for f in out/sente-intro-30s.mp4 out/sente-intro-15s.mp4; do
    d=$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$f"); v=$(ffmpeg -i "$f" -af volumedetect -f null - 2>&1 | grep -oE 'mean_volume: [-0-9.]+ dB')
    printf '  %s  %.1fs  %s\n' "$f" "$d" "$v"
  done
  echo "  done → $ROOT/out/"
fi
