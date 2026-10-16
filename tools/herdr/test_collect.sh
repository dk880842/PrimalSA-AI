#!/usr/bin/env bash
# collect.sh 離線測試：假 herdr 指令（PATH 前面放替身），不碰真的 herdr tab。
# 用法：bash tools/herdr/test_collect.sh
set -u
here="$(cd "$(dirname "$0")" && pwd)"
tmp="$(mktemp -d)"; trap 'rm -rf "$tmp"' EXIT
fails=0
check() { if eval "$2"; then echo "PASS $1"; else echo "FAIL $1"; fails=$((fails + 1)); fi; }

# shellcheck source=/dev/null
source "$here/collect.sh"
check 'bg_running：1 shell still running' 'bg_running <<<"✻ done  1 shell still running"'
check 'bg_running：1 monitor still running' 'bg_running <<<"x 1 monitor still running y"'
check 'bg_running：· 2 shells' 'bg_running <<<"esc to interrupt · 2 shells"'
check 'bg_running：沒有背景工作' '! bg_running <<<"完成，報告在 notes/handoff/x.md"'

# 假 herdr：agent read 回 $tmp/screen-N（第 N 次讀，用完沿用最後一個）；寫報告由 screen 檔內含 WRITE 觸發
mkdir -p "$tmp/bin" "$tmp/rep"
cat > "$tmp/bin/herdr" <<'SH'
#!/usr/bin/env bash
d="$FAKE_DIR"
case "$1 $2" in
  "agent get") echo '{"result":{"agent":{"tab_id":"t9","agent_status":"done"}}}' ;;
  "agent wait") exit 0 ;;
  "agent read")
    n=$(( $(cat "$d/n" 2>/dev/null || echo 0) + 1 )); echo "$n" > "$d/n"
    f="$d/screen-$n"; [[ -f "$f" ]] || f="$(ls "$d"/screen-* | sort -V | tail -1)"
    if grep -q WRITE "$f"; then echo "報告內容" > "$d/rep/job.md"; fi
    cat "$f" ;;
  "tab close") echo closed >> "$d/closed" ;;
esac
SH
chmod +x "$tmp/bin/herdr"
run() { (export PATH="$tmp/bin:$PATH" FAKE_DIR="$tmp" HERDR_ENV=1 COLLECT_POLL_S=0 COLLECT_REPORT_DIR="$tmp/rep"; bash "$here/collect.sh" job 600000 >"$tmp/out" 2>&1); echo $?; }
reset() { rm -f "$tmp"/screen-* "$tmp/n" "$tmp/closed" "$tmp/rep/job.md"; }

reset; printf '1 shell still running\n' > "$tmp/screen-1"; printf '· 1 monitor\n' > "$tmp/screen-2"; printf 'WRITE 1 shell still running\n' > "$tmp/screen-3"
rc=$(run)
check "done 但背景 shell / monitor 還在跑 → 繼續等，報告出現後讀報告關 tab（rc=$rc）" '[[ $rc == 0 && -f $tmp/closed ]] && grep -q 報告內容 "$tmp/out"'
reset; printf 'idle\n' > "$tmp/screen-1"
rc=$(run)
check "沒有背景工作也沒報告 → 6、不關 tab（rc=$rc）" '[[ $rc == 6 && ! -f $tmp/closed ]]'
reset; echo 舊報告 > "$tmp/rep/job.md"; printf 'x\n' > "$tmp/screen-1"
rc=$(run)
check "已有報告 → 0、關 tab（rc=$rc）" '[[ $rc == 0 && -f $tmp/closed ]]'

echo "FAIL 數: $fails"
exit $(( fails > 0 ))
