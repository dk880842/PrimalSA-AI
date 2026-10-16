#!/usr/bin/env bash
# herdr 派工：另開 tab 跑一個獨立的 Claude Code session（取代 Agent 工具的 subagent，主 session 不吃子工作的上下文）
#
# 用法：
#   bash tools/herdr/spawn.sh <名稱> <角色> <prompt 檔 | -> [tab 標題]
#     名稱   herdr agent 名（[a-z][a-z0-9_-]{0,31}，同時存活的要唯一），例：play-p1、dev-restore
#     角色   .claude/agents/ 的具名 agent：psa-play-sonnet-medium、psa-dev-sonnet-medium、
#            psa-dev-opus-medium、psa-plan-opus-medium、psa-research-haiku-medium
#     prompt 派工內容（檔案路徑，或 - 讀 stdin）
#     標題   tab 名與 claude session 名（--name），預設 = 名稱
#   環境變數：PSA_SPAWN_PERM（預設 auto）= claude --permission-mode
#
# 子 session 結束時把完整報告寫到 notes/handoff/<名稱>.md，畫面只回一行；
# 主 session 只讀那個檔（或 herdr agent get / read --lines 20 看狀態），不要整頁 read。
#   查狀態：herdr agent get <名稱>        追加指示：herdr agent prompt <名稱> "..."
#   收尾：派工後立刻背景跑 bash tools/herdr/collect.sh <名稱>：做完自動印報告 + 關 tab（使用者 2026-10-16）
#
# 退出碼：0 成功（印 tab_id / pane_id / 名稱）、2 參數錯、3 不在 herdr 內、4 角色定義不存在、
#         5 開 tab 失敗、6 claude 啟動失敗、7 送 prompt 失敗
set -euo pipefail

name="${1:-}"; role="${2:-}"; src="${3:-}"; label="${4:-${1:-}}"
if [[ -z "$name" || -z "$role" || -z "$src" ]]; then sed -n 2,20p "$0"; exit 2; fi
[[ "$name" =~ ^[a-z][a-z0-9_-]{0,31}$ ]] || { echo "名稱不合法：$name" >&2; exit 2; }
[[ "${HERDR_ENV:-}" == 1 ]] || { echo "不在 herdr pane 內" >&2; exit 3; }

root="$(cd "$(dirname "$0")/../.." && pwd)"
def="$root/.claude/agents/$role.md"
[[ -f "$def" ]] || { echo "找不到角色定義：$def" >&2; exit 4; }
model="$(sed -n 's/^model:[[:space:]]*//p' "$def" | head -1)"
effort="$(sed -n 's/^effort:[[:space:]]*//p' "$def" | head -1)"

if [[ "$src" == - ]]; then task="$(cat)"; else task="$(cat "$src")"; fi
mkdir -p "$root/notes/handoff"
report="notes/handoff/$name.md"
task="$task

---
（派工規則）你是由主 session 用 herdr 另開 tab 派出的獨立 session（名稱 $name）。
結束時把完整報告（做了什麼、結果、改了哪些檔、commit / 分支、未實機或待確認事項）用繁體中文寫到 \`$report\`（覆寫），
畫面上最後只回一行：「完成，報告在 $report」或「停手：<原因>，報告在 $report」。"

j() { python3 -c 'import json,sys; d=json.load(sys.stdin); print(eval(sys.argv[1]))' "$1"; }

out="$(herdr tab create --workspace "$HERDR_WORKSPACE_ID" --cwd "$root" --label "$label" --no-focus)" \
  || { echo "開 tab 失敗：$out" >&2; exit 5; }
tab="$(j 'd["result"]["tab"]["tab_id"]' <<<"$out")"
pane="$(j 'd["result"]["root_pane"]["pane_id"]' <<<"$out")"

args=(--name "$label" --agent "$role" --permission-mode "${PSA_SPAWN_PERM:-auto}")
[[ -n "$model" ]] && args+=(--model "$model")
[[ -n "$effort" ]] && args+=(--effort "$effort")
herdr agent start "$name" --kind claude --pane "$pane" --timeout 60000 -- "${args[@]}" >/dev/null \
  || { echo "claude 啟動失敗（tab $tab 留著供檢查）" >&2; exit 6; }

herdr agent prompt "$name" "$task" --wait --until working --until blocked --timeout 30000 >/dev/null \
  || { echo "送 prompt 失敗或未開始（tab $tab）；用 herdr agent read $name --lines 20 檢查，勿盲目重送" >&2; exit 7; }

# agent start / prompt 可能把焦點切到新 tab，切回派工的 tab
herdr tab focus "$HERDR_TAB_ID" >/dev/null 2>&1 || true

echo "tab=$tab pane=$pane name=$name role=$role report=$report"
