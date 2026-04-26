#!/usr/bin/env bash
# Build a static zip for Butterbase frontend hosting (slides only).
# Output: build/butterbase-slides.zip
#
# Deploy (after zip exists):
#   1. MCP: create_frontend_deployment { app_id, framework: "static" }
#   2. curl -X PUT "$uploadUrl" -H "Content-Type: application/zip" --data-binary @build/butterbase-slides.zip
#   3. MCP: start_frontend_deployment { app_id, deployment_id }
#
# Site: https://<subdomain>.butterbase.dev/slides/

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT="${ROOT}/build/butterbase-slides-root"
ZIP="${ROOT}/build/butterbase-slides.zip"
SRC="${ROOT}/pixel-love-studio/public/slides"

if [[ ! -f "${SRC}/index.html" ]]; then
  echo "error: missing ${SRC}/index.html" >&2
  exit 1
fi

rm -rf "$OUT"
mkdir -p "$OUT/slides"
cp -R "${SRC}/." "$OUT/slides/"

cat > "${OUT}/index.html" <<'EOF'
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <meta http-equiv="refresh" content="0; url=slides/" />
  <title>DailyReel Slides</title>
</head>
<body style="font-family: system-ui, sans-serif; padding: 2rem;">
  <p><a href="slides/">Open DailyReel slides</a></p>
</body>
</html>
EOF

mkdir -p "${ROOT}/build"
rm -f "$ZIP"
( cd "$OUT" && zip -r "$ZIP" . )

echo "[package-butterbase-slides] wrote $ZIP ($(du -h "$ZIP" | cut -f1))"
