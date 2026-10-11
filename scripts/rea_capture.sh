#!/usr/bin/env bash
# Reproduce the driveindex.com capture with REA (https://github.com/morluto/rea).
# Requires Node 22.19+ and a Chromium/Chrome binary. Output goes to ./capture (git-ignored).
set -euo pipefail

URL="${1:-https://driveindex.com/cars/ford/mustang-shelby-gt350r/2020}"
CHROME="${CHROME:-chromium}"
OUT="${OUT:-capture}"
PORT=9222
REA="npx -y rea-agents@6.4.0"

mkdir -p "$OUT"
"$CHROME" --headless=new --no-sandbox --remote-debugging-port=$PORT \
  --remote-debugging-address=127.0.0.1 --user-data-dir="$OUT/profile" \
  --password-store=basic ${HTTPS_PROXY:+--proxy-server="$HTTPS_PROXY"} "$URL" &
CHROME_PID=$!
trap 'kill $CHROME_PID 2>/dev/null || true' EXIT
until curl -s "http://127.0.0.1:$PORT/json/version" >/dev/null; do sleep 1; done

TARGET=$($REA list-browser-targets "http://127.0.0.1:$PORT" --json \
  | node -e 'let s="";process.stdin.on("data",d=>s+=d).on("end",()=>console.log(JSON.parse(s).normalized_result.targets[0].target_id))')

# Page structure, network, JSON response shapes and full script sources
$REA inspect-web-page "http://127.0.0.1:$PORT" "$TARGET" --observation-ms 4000 \
  --include-json-body-shapes --include-script-sources --json > "$OUT/inspect.json"
# Static bundle analysis: chunks, endpoint candidates, vendor fingerprints, source maps
$REA analyze-web-bundle "http://127.0.0.1:$PORT" "$TARGET" --json > "$OUT/bundle.json"
# Export captured scripts for static JavaScript analysis
$REA export-web-scripts "$PWD/$OUT/inspect.json" "$PWD/$OUT/scripts" --json > "$OUT/export.json"
$REA analyze-javascript-application "$PWD/$OUT/scripts/files" --json > "$OUT/app.json"

echo "Done. The valuation math lives in the app/(app)/dashboard/page-*.js chunk:"
grep -l "blendedRate" "$OUT"/scripts/files/isolated/*.js || true
