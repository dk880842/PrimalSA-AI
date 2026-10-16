#!/usr/bin/env bash
# herdr 派工收尾：等 spawn.sh 派出的 session 做完 → 印報告 → 關 tab（使用者 2026-10-16：回報之後自動讀、自動關）
#
# 用法（主 session 派工後立刻用背景執行，完成通知裡就是報告）：
#   bash tools/herdr/collect.sh <名稱> [逾時毫秒，預設 7200000]
# 流程：herdr agent wait（idle / done / blocked）→ blocked = 子 session 在等權限 / 問題，不關 tab、印最後畫面
#       → 報告檔 notes/handoff/<名稱>.md 不存在或比派工時間舊 = 沒寫報告，不關 tab
#       → 印報告、herdr tab close。
# 退出碼：0 已讀報告並關 tab、2 參數錯、3 不在 herdr 內、4 等待逾時 / 失敗（tab 留著）、
#         5 子 session 卡在權限 / 問題（blocked，tab 留著）、6 做完但沒有報告檔（tab 留著）
set -uo pipefail

name="${1:-}"; tmo="${2:-7200000}"
[[ -n "$name" ]] || { sed -n 2,10p "$0"; exit 2; }
[[ "${HERDR_ENV:-}" == 1 ]] || { echo "不在 herdr pane 內" >&2; exit 3; }
root="$(cd "$(dirname "$0")/../.." && pwd)"
report="$root/notes/handoff/$name.md"
start="$(date +%s)"

info() { herdr agent get "$name" 2>/dev/null | python3 -c 'import json,sys
a=json.load(sys.stdin)["result"]["agent"]; print(a.get("tab_id",""), a.get("agent_status",""))'; }

read -r tab _ <<<"$(info)"
[[ -n "${tab:-}" ]] || { echo "找不到 agent：$name" >&2; exit 4; }

herdr agent wait "$name" --timeout "$tmo" >/dev/null 2>&1 || { echo "等待 $name 逾時 / 失敗（tab $tab 留著）" >&2; exit 4; }
read -r _ st <<<"$(info)"
if [[ "$st" == blocked ]]; then
  echo "== $name 卡在權限 / 問題（tab $tab 留著），最後畫面："
  herdr agent read "$name" --source recent-unwrapped --lines 25
  exit 5
fi
# 報告檔要是本次（等待開始之後或派工後）寫的；spawn 後才建立的檔 mtime 一定 ≥ 派工時間，這裡只防完全沒寫
if [[ ! -f "$report" ]]; then
  echo "== $name 已閒置但沒有報告檔 $report（tab $tab 留著），最後畫面："
  herdr agent read "$name" --source recent-unwrapped --lines 25
  exit 6
fi
echo "== $name 報告（$(date -d @"$(stat -c %Y "$report")" '+%H:%M:%S') 寫入，等待 $(( $(date +%s) - start )) 秒）"
cat "$report"
herdr tab close "$tab" >/dev/null 2>&1 && echo "== 已關 tab $tab" || echo "== 關 tab $tab 失敗"
exit 0
