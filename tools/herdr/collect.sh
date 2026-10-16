#!/usr/bin/env bash
# herdr 派工收尾：等 spawn.sh 派出的 session 做完 → 印報告 → 關 tab（使用者 2026-10-16：回報之後自動讀、自動關）
#
# 用法（主 session 派工後立刻用背景執行，完成通知裡就是報告）：
#   bash tools/herdr/collect.sh <名稱> [逾時毫秒，預設 7200000]
# 流程：herdr agent wait（idle / done / blocked）→ blocked = 子 session 在等權限 / 問題，不關 tab、印最後畫面
#       → 報告檔 notes/handoff/<名稱>.md 不存在：看最後畫面還有背景工作（底列「N shell still running」「N monitor still running」、
#         「· N shell」「· N monitor」）= 還沒做完，每 COLLECT_POLL_S 秒（預設 30）再看，直到報告出現 / 背景工作結束 / 逾時
#         （2026-10-17：舊版 done 但背景 shell / monitor 還在跑就判「沒報告」exit 6）；沒有背景工作仍沒報告 = 沒寫報告，不關 tab
#       → 印報告、herdr tab close。
# 退出碼：0 已讀報告並關 tab、2 參數錯、3 不在 herdr 內、4 等待逾時 / 失敗（tab 留著）、
#         5 子 session 卡在權限 / 問題（blocked，tab 留著）、6 做完（沒有背景工作）但沒有報告檔（tab 留著）
# 離線測試：bash tools/herdr/test_collect.sh（假 herdr 指令，不碰真的 tab）
set -uo pipefail

# 純函式：stdin 是子 session 最後畫面 → 有背景 shell / monitor 在跑回 0
bg_running() {
  grep -Eqi '[0-9]+ (shells?|monitors?) (still )?running|·[[:space:]]*[0-9]+[[:space:]]+(shells?|monitors?)\b'
}

collect_main() {
  local name="${1:-}" tmo="${2:-7200000}"
  [[ -n "$name" ]] || { sed -n 2,14p "$0"; return 2; }
  [[ "${HERDR_ENV:-}" == 1 ]] || { echo "不在 herdr pane 內" >&2; return 3; }
  local root report start deadline poll tab st left screen
  root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
  report="${COLLECT_REPORT_DIR:-$root/notes/handoff}/$name.md"
  start="$(date +%s)"
  deadline=$(( start + tmo / 1000 ))
  poll="${COLLECT_POLL_S:-30}"

  info() { herdr agent get "$name" 2>/dev/null | python3 -c 'import json,sys
a=json.load(sys.stdin)["result"]["agent"]; print(a.get("tab_id",""), a.get("agent_status",""))'; }

  read -r tab _ <<<"$(info)"
  [[ -n "${tab:-}" ]] || { echo "找不到 agent：$name" >&2; return 4; }

  while :; do
    left=$(( (deadline - $(date +%s)) * 1000 ))
    (( left > 0 )) || { echo "等待 $name 逾時（tab $tab 留著）" >&2; return 4; }
    herdr agent wait "$name" --timeout "$left" >/dev/null 2>&1 || { echo "等待 $name 逾時 / 失敗（tab $tab 留著）" >&2; return 4; }
    read -r _ st <<<"$(info)"
    if [[ "$st" == blocked ]]; then
      echo "== $name 卡在權限 / 問題（tab $tab 留著），最後畫面："
      herdr agent read "$name" --source recent-unwrapped --lines 25
      return 5
    fi
    # 報告檔要是本次（等待開始之後或派工後）寫的；spawn 後才建立的檔 mtime 一定 ≥ 派工時間，這裡只防完全沒寫
    [[ -f "$report" ]] && break
    screen="$(herdr agent read "$name" --source recent-unwrapped --lines 25 2>/dev/null)"
    if bg_running <<<"$screen"; then
      (( $(date +%s) + poll < deadline )) || { echo "等待 $name 逾時：背景工作還在跑、沒有報告檔（tab $tab 留著）" >&2; return 4; }
      sleep "$poll"
      continue
    fi
    echo "== $name 已閒置但沒有報告檔 $report（tab $tab 留著），最後畫面："
    printf '%s\n' "$screen"
    return 6
  done
  echo "== $name 報告（$(date -d @"$(stat -c %Y "$report")" '+%H:%M:%S') 寫入，等待 $(( $(date +%s) - start )) 秒）"
  cat "$report"
  herdr tab close "$tab" >/dev/null 2>&1 && echo "== 已關 tab $tab" || echo "== 關 tab $tab 失敗"
  return 0
}

[[ "${BASH_SOURCE[0]}" == "$0" ]] && { collect_main "$@"; exit $?; }
true
