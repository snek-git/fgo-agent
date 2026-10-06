#!/usr/bin/env bash
# Build the redroid image (Android 13 + libndk ARM translation, su removed) and start it.
set -euo pipefail
cd "$(dirname "$0")/.."

docker compose -f emu/compose.yaml up -d --build

for _ in $(seq 1 60); do
  if [ "$(docker exec fgo-redroid getprop sys.boot_completed 2>/dev/null | tr -d '\r')" = "1" ]; then
    adb connect 127.0.0.1:5555
    echo "redroid is up: scrcpy -s 127.0.0.1:5555"
    exit 0
  fi
  sleep 2
done
echo "redroid did not finish booting, see: docker logs fgo-redroid" >&2
exit 1
