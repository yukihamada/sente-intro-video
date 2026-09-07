#!/usr/bin/env bash
# Records the Sente iPhone app in the simulator, driven by the scripted transport (deterministic, no real keys).
#   scripts/record.sh <sente-ios repo> [udid]   → work/footage/phone_a.mp4 (Mac job) + phone_b.mp4 (Mac asleep → cloud)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"; REPO="${1:?path to sente-ios checkout}"; OUT="$ROOT/work/footage"; mkdir -p "$OUT"
APP="$REPO/build-sim/Build/Products/Debug-iphonesimulator/Sente.app"; BUNDLE=tokyo.hamada.sente
[ -d "$APP" ] || { echo "build first: cd $REPO && xcodebuild -project Sente.xcodeproj -scheme Sente -destination 'generic/platform=iOS Simulator' -derivedDataPath build-sim CODE_SIGNING_ALLOWED=NO build"; exit 2; }
UD="${2:-}"
if [ -z "$UD" ]; then
  RT=$(xcrun simctl list runtimes | grep -oE 'com.apple.CoreSimulator.SimRuntime.iOS-[0-9-]+' | tail -1)
  UD=$(xcrun simctl list devices | grep "Sente-Intro" | grep -oE "[0-9A-F-]{36}" | head -1 || true)
  [ -n "$UD" ] || UD=$(xcrun simctl create "Sente-Intro" com.apple.CoreSimulator.SimDeviceType.iPhone-16-Pro "$RT")
fi
xcrun simctl boot "$UD" 2>/dev/null || true; xcrun simctl bootstatus "$UD" -b >/dev/null
xcrun simctl status_bar "$UD" override --time "9:41" --batteryState charged --batteryLevel 100 --cellularBars 4 --wifiBars 3 >/dev/null 2>&1 || true
xcrun simctl ui "$UD" appearance light >/dev/null 2>&1 || true
xcrun simctl install "$UD" "$APP"
rec() { # name seconds autosend [extra env KEY=VAL ...]
  local name="$1" secs="$2" text="$3"; shift 3
  xcrun simctl terminate "$UD" $BUNDLE 2>/dev/null || true
  rm -f "$OUT/$name.mp4"
  xcrun simctl io "$UD" recordVideo --codec h264 --force "$OUT/$name.mp4" & local rp=$!
  sleep 1.5
  env SIMCTL_CHILD_SENTE_SCRIPT=1 SIMCTL_CHILD_SENTE_E2E=1 SIMCTL_CHILD_SENTE_E2E_TEAI_KEY=scripted SIMCTL_CHILD_SENTE_E2E_SENTE_TOKEN=scripted \
      SIMCTL_CHILD_SENTE_AUTOSEND="$text" "${@/#/SIMCTL_CHILD_}" xcrun simctl launch "$UD" $BUNDLE -AppleLanguages "(ja)" -AppleLocale ja_JP >/dev/null
  sleep "$secs"
  kill -INT $rp; for _ in $(seq 1 40); do kill -0 $rp 2>/dev/null || break; sleep 0.5; done; kill -9 $rp 2>/dev/null || true   # recordVideo finalizes on SIGINT; never block on wait
  echo "  $OUT/$name.mp4 $(ffprobe -v error -show_entries format=duration -of csv=p=0 "$OUT/$name.mp4")s"
}
ONLY="${ONLY:-}"
[ -n "$ONLY" ] && [ "$ONLY" != phone_a ] || rec phone_a 22 "Claude Code でテストして"
[ -n "$ONLY" ] && [ "$ONLY" != phone_b ] || rec phone_b 22 "やることを3つに絞って" SENTE_SCRIPT_MAC_ASLEEP=1
