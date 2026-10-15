#!/usr/bin/env bash
# WSL / Git Bash 手打用包裝：開精靈王石器畫面鏡像視窗（背景執行，立即返回）。bash tools/gui/mirror.sh
DIR="$(cd "$(dirname "$0")" && pwd)"
winpath() { if command -v wslpath >/dev/null 2>&1; then wslpath -w "$1"; elif command -v cygpath >/dev/null 2>&1; then cygpath -w "$1"; else printf '%s' "$1"; fi; }
PS="$(winpath "$DIR/mirror.ps1")"
# 多視窗：PSA_CLIENT=PrimalSA2 bash tools/gui/mirror.sh 開另一個視窗的鏡像（WSL 經 WSLENV 傳給 powershell.exe，Start-Process 的子程序再繼承）
if [ -n "$PSA_CLIENT" ]; then case ":$WSLENV:" in *:PSA_CLIENT:*) ;; *) export WSLENV="${WSLENV:+$WSLENV:}PSA_CLIENT" ;; esac; fi
powershell.exe -NoProfile -c "Start-Process powershell.exe -WindowStyle Hidden -ArgumentList '-NoProfile','-ExecutionPolicy','Bypass','-STA','-File','\"$PS\"'"
