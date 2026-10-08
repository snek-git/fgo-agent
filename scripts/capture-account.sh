#!/usr/bin/env bash
# Sync the roster and CE list from the game itself: restart FGO through mitmproxy on the PC,
# save the login response (the whole account), then import it.
# The emulator reaches the proxy through `adb reverse`, so nothing listens beyond localhost, and
# only fate-go hosts are intercepted. The proxy is switched off again however this exits.
set -euo pipefail
cd "$(dirname "$0")/.."

dev=(adb -s 127.0.0.1:5555)
port=8080
ca=~/.mitmproxy/mitmproxy-ca-cert.pem
log=data/capture/mitmdump.log
mkdir -p data/capture

if [ ! -f "$ca" ]; then
  # mitmproxy writes its CA on first start
  timeout 5 mitmdump --listen-host 127.0.0.1 --listen-port "$port" > /dev/null 2>&1 || true
fi
# Android 13 trusts certificates in /system/etc/security/cacerts, named by the old subject hash
hash=$(openssl x509 -inform PEM -subject_hash_old -noout -in "$ca")
docker cp "$ca" "fgo-redroid:/system/etc/security/cacerts/$hash.0"
docker exec fgo-redroid chmod 644 "/system/etc/security/cacerts/$hash.0"

before=$(ls data/capture/login-top-*.json 2>/dev/null | wc -l)
mitmdump --listen-host 127.0.0.1 --listen-port "$port" --allow-hosts 'fate-go' \
  -s scripts/capture_login.py > "$log" 2>&1 &
proxy=$!
cleanup() {
  "${dev[@]}" shell settings put global http_proxy :0 || true
  "${dev[@]}" reverse --remove "tcp:$port" || true
  kill "$proxy" 2>/dev/null || true
}
trap cleanup EXIT
sleep 4

"${dev[@]}" reverse "tcp:$port" "tcp:$port" > /dev/null
"${dev[@]}" shell settings put global http_proxy "127.0.0.1:$port"
"${dev[@]}" shell am force-stop com.aniplex.fategrandorder
"${dev[@]}" shell am start -n com.aniplex.fategrandorder/jp.delightworks.Fgo.player.AndroidPlugin > /dev/null

# Tap through the title screen until the login call has been saved. (440, 563) is the いいえ (No)
# button of the "app did not start normally, clear the cache?" dialog FGO shows after a launch
# that got cut off; anywhere else on the title screens a tap there just continues.
for _ in $(seq 1 40); do
  sleep 4
  if [ "$(ls data/capture/login-top-*.json 2>/dev/null | wc -l)" -gt "$before" ]; then
    echo "captured: $(ls data/capture/login-top-*.json | tail -1)"
    cleanup
    trap - EXIT
    uv run fgo-agent import-account
    exit 0
  fi
  "${dev[@]}" shell input tap 440 563
done
echo "no login response after 160s, see $log" >&2
exit 1
