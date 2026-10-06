#!/usr/bin/env bash
# Install an .apk or .xapk (zip of split apks + optional obb) into the redroid container.
# usage: scripts/install-apk.sh ~/Downloads/fgo.xapk
set -euo pipefail

SERIAL="${SERIAL:-127.0.0.1:5555}"
file="${1:?usage: install-apk.sh <file.apk|file.xapk>}"

adb connect "$SERIAL" >/dev/null

case "$file" in
  *.apk)
    adb -s "$SERIAL" install "$file"
    ;;
  *.xapk|*.apks|*.zip)
    work="$(mktemp -d)"
    trap 'rm -rf "$work"' EXIT
    unzip -q "$file" -d "$work"
    mapfile -t apks < <(find "$work" -maxdepth 1 -name '*.apk')
    if [ "${#apks[@]}" -eq 0 ]; then
      echo "no .apk files inside $file" >&2
      exit 1
    fi
    adb -s "$SERIAL" install-multiple "${apks[@]}"
    if [ -d "$work/Android/obb" ]; then
      adb -s "$SERIAL" push "$work/Android/obb/." /sdcard/Android/obb/
    fi
    ;;
  *)
    echo "unknown file type: $file" >&2
    exit 1
    ;;
esac

adb -s "$SERIAL" shell pm list packages | grep -i fategrandorder

# vold can't set quota project ids on a btrfs-backed /data, so Android never creates the app's
# external cache dir. Make it by hand, owned like the files dir next to it.
docker exec fgo-redroid sh -c '
  pkg=com.aniplex.fategrandorder
  owner=$(stat -c %U /data/data/$pkg)
  d=/data/media/0/Android/data/$pkg
  mkdir -p $d/files $d/cache
  chown $owner:ext_data_rw $d $d/files $d/cache
  chmod 2770 $d $d/files $d/cache'
