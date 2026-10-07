#!/usr/bin/env bash
# Build the redroid image (Android 13 + libndk ARM translation, su removed) and start it.
set -euo pipefail
cd "$(dirname "$0")/.."

docker compose -f emu/compose.yaml up -d --build

for _ in $(seq 1 60); do
  if [ "$(docker exec fgo-redroid getprop sys.boot_completed 2>/dev/null | tr -d '\r')" = "1" ]; then
    adb connect 127.0.0.1:5555
    # The "viewing full screen" hint steals focus from the game on first launch.
    adb -s 127.0.0.1:5555 shell settings put secure immersive_mode_confirmations confirmed
    # Media volume starts at 5/15, which makes scrcpy and the viewer's audio quiet.
    adb -s 127.0.0.1:5555 shell cmd media_session volume --stream 3 --set 15 > /dev/null
    echo "redroid is up: scrcpy -s 127.0.0.1:5555 --audio-codec=aac"
    exit 0
  fi
  sleep 2
done
echo "redroid did not finish booting, see: docker logs fgo-redroid" >&2
exit 1
