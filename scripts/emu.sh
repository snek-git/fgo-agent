#!/usr/bin/env bash
# Start or stop the emulator together with FGO, so neither runs when nothing is playing.
# usage: scripts/emu.sh up     start the container if needed, wait for boot, open FGO
#        scripts/emu.sh down   close FGO and stop the container
set -uo pipefail
cd "$(dirname "$(readlink -f "$0")")/.."

SERIAL=127.0.0.1:5555
PKG=com.aniplex.fategrandorder

booted() { [ "$(docker exec fgo-redroid getprop sys.boot_completed 2>/dev/null | tr -d '\r')" = "1" ]; }

case "${1:-}" in
  up)
    if [ "$(docker inspect -f '{{.State.Running}}' fgo-redroid 2>/dev/null)" != "true" ]; then
      docker compose -f emu/compose.yaml up -d >&2 || { echo "could not start the emulator container" >&2; exit 1; }
    fi
    for _ in $(seq 1 60); do booted && break; sleep 2; done
    booted || { echo "the emulator did not finish booting" >&2; exit 1; }
    adb connect "$SERIAL" >&2 || { echo "adb could not connect to $SERIAL" >&2; exit 1; }
    if [ -z "$(adb -s "$SERIAL" shell pidof "$PKG" | tr -d '\r')" ]; then
      adb -s "$SERIAL" shell am start -n "$PKG/jp.delightworks.Fgo.player.AndroidPlugin" >&2 \
        || { echo "could not start FGO" >&2; exit 1; }
    fi
    ;;
  down)
    adb -s "$SERIAL" shell am force-stop "$PKG" >&2 || true
    docker stop fgo-redroid >&2 || { echo "could not stop the emulator" >&2; exit 1; }
    ;;
  *)
    echo "usage: scripts/emu.sh up|down" >&2
    exit 2
    ;;
esac
