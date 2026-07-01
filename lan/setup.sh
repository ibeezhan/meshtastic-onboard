#!/usr/bin/env bash
# One-time setup for the LAN stack. Fetches the two third-party pieces we do NOT
# vendor (so their licenses/updates stay with upstream):
#   * ianmcorvidae/meshtastic-http-proxy  -> lan/http-proxy/
#   * meshtastic/web prebuilt release      -> lan/web-client/  (+ our autoconnect.js)
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"

echo "[setup] http-proxy"
if [ ! -d "$HERE/http-proxy/.git" ]; then
  git clone --depth 1 https://github.com/ianmcorvidae/meshtastic-http-proxy.git "$HERE/http-proxy"
else
  echo "  already present"
fi

echo "[setup] web client (latest meshtastic/web release build.tar)"
if [ ! -f "$HERE/web-client/index.html" ]; then
  mkdir -p "$HERE/web-client"
  URL="$(curl -s https://api.github.com/repos/meshtastic/web/releases/latest \
        | grep -o 'https://[^"]*build\.tar' | head -1)"
  [ -n "$URL" ] || { echo "  could not find build.tar asset"; exit 1; }
  echo "  downloading $URL"
  curl -sL "$URL" -o "$HERE/web-client/build.tar"
  ( cd "$HERE/web-client" && tar xf build.tar && rm build.tar )
  # release ships pre-gzipped for nginx gzip_static; decompress for a plain static server
  find "$HERE/web-client" -name '*.gz' -exec gunzip -f {} \;
  # inject one-click auto-connect
  cp "$HERE/autoconnect.js" "$HERE/web-client/autoconnect.js"
  if ! grep -q autoconnect.js "$HERE/web-client/index.html"; then
    perl -0pi -e 's#</body>#<script src="/autoconnect.js"></script></body>#' "$HERE/web-client/index.html"
  fi
else
  echo "  already present"
fi

echo "[setup] done. Now: ./start-lan-stack.sh"
