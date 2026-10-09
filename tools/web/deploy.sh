#!/usr/bin/env bash
# 建置靜態網站並發布到 GitHub Pages（gh-pages 分支；不需要 GitHub Actions / workflow 權限）
# 用法（專案根目錄）：bash tools/web/deploy.sh
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
OUT="$ROOT/tools/.cache/gh-pages"
REMOTE="$(git -C "$ROOT" remote get-url origin)"
REV="$(git -C "$ROOT" rev-parse --short HEAD)"

uv run --no-project python "$ROOT/tools/web/build.py" --out "$OUT"

# gh-pages 每次都是單一 commit（只放建置結果，不留歷史，repo 才不會越來越大）
cd "$OUT"
git init -q -b gh-pages
git add -A
git -c user.name="$(git -C "$ROOT" config user.name)" -c user.email="$(git -C "$ROOT" config user.email)" \
    commit -q -m "部署網站（main $REV）"
git -c credential.https://github.com.helper='!gh auth git-credential' push -q -f "$REMOTE" gh-pages
rm -rf "$OUT/.git"
echo "已發布到 gh-pages（main $REV），GitHub Pages 約 1 分鐘後更新"
