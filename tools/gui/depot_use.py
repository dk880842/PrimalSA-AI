#!/usr/bin/env python3
"""從公共倉庫取出道具、使用一個、剩下的存回公共倉庫（例：2倍智慧果）。只用標準函式庫；背包 / 倉庫動作全用 bag.py。

用法（專案根目錄；WSL / Windows 原生相同）：
  uv run --no-project python tools/gui/depot_use.py DKBO 2倍智慧果 [--depot public] [--no-restore] [--have]
流程：暫停遇敵 + 等戰鬥結束（heal.set_encounter(False)）→ buff 列已有該道具的圖示（bag.BUFF_KIND：龍王的守護 = 人形 dragon、2倍智慧果 = EXP exp）就跳過
→ bag.depot_take（整疊取出）→ bag.use_item → bag.depot_store（剩餘存回）→ 關背包後等 buff 列出現圖示（4 秒）→ 開回遇敵（不管成敗都會開回）。
成敗判準：BUFF_KIND 的道具一定要看到圖示才回 0，沒看到 = 95（剩的已存回倉庫）；use_item 回 0 只代表「按了使用、彈窗關了」
（2026-10-12 2倍智慧果按了使用、彈窗關了卻沒扣道具，舊版沒驗就回 0）。不在 BUFF_KIND 的道具沒辦法驗，維持 use_item 結果。
每步失敗就停、回該步的退出碼（bag 90～96），不重點；取出後失敗會提醒「道具還在背包」。
最後一行 JSON {"ok","rc","step","buff",...}。
"""
import argparse
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import bag  # noqa: E402
import heal  # noqa: E402
import uikit  # noqa: E402


# 彈窗特徵 / 標題雙框 / 並排版型判斷 / 倉庫頁存入都已併入 bag.py（舊版在這裡 monkeypatch，bag 自己的 CLI 與其他腳本吃不到）；保留別名給舊測試
POPUP_SIG2, POPUP_SIG3 = bag.POPUP_SIG2, bag.POPUP_SIG3
is_pair_layout = bag.is_pair_layout


def _in_bag(item: str) -> bool:
    """背包頁有 item 嗎（找不到或切頁失敗 = False）"""
    try:
        return not bag.goto_page('bag') and bag.find_item(item) is not None
    except Exception:
        return False


def store_back(role: str, want: str, depot: str = 'public') -> int:
    return bag.depot_store(role, want, depot)


def use_one(role: str, want: str) -> int:
    """背包使用一個：找格（OCR 讀歪就逐格開彈窗核對名稱）→ 名稱核對 → 按鈕列 OCR 有「使用」才點（並排版型 619，否則 732）→ 彈窗關了"""
    return bag.use_item(role, want)


def run(role: str, item: str, depot: str = 'public', restore: bool = True, have: bool = False, reopen: bool = True) -> tuple:
    """→ (rc, info)。buff 圖示已在就跳過；encounter 先關、結束後一定開回（原本就關著也開回：本工具只在掛機時用）"""
    info = {'role': role, 'item': item, 'depot': depot}
    kind = bag.buff_kind(item)
    enc_off = False
    try:
        heal.set_encounter(False)
        enc_off = True
        heal.gui('seq', f'waitpix 20000 {heal.SIG_NO_BATTLE} 40')       # 關遇敵不會中止正在打的那場：等 VS 牌消失
        if kind and bag.has_buff(kind):                              # 圖示已在 = 還有效，整個跳過（不開背包）；吃了也驗不出有沒有吃到
            info.update(buff_before=True, buff=True, step='skip', note=f'buff 列已有 {kind} 圖示，不吃')
            return 0, info
        info['buff_before'] = False
        with bag.Session() as sess:                                      # 一次開背包做完 取出 → 使用 → 存回，最後才關（內部各步看到已開著不會關）
            if sess.rc:
                info['step'] = 'open'
                return sess.rc, info
            if not have:
                rc = bag.depot_take(role, item, depot)
                info['step'] = 'take'
                if rc == bag.EXIT_ITEM and _in_bag(item):               # 倉庫空但背包有（上次取出後失敗沒存回）→ 用背包那份
                    info['note'] = '倉庫沒有但背包有，直接用背包那份'
                    rc = 0
                if rc:
                    if restore and rc != bag.EXIT_ITEM:                  # 取出動作可能已生效只是驗證不到（格子更新延遲）→ 一定試著存回；背包沒有會回 92，無害
                        st = bag.depot_store(role, item, depot)
                        if not st:
                            info['store_note'] = '取出驗證失敗但背包其實有，已存回'
                    return rc, info
            # 取出後不管吃成不成功，剩下的都要存回倉庫（借出的道具要還）
            use_rc = bag.use_item(role, item)                             # buff 列被背包面板蓋住，成敗等關背包後再看（見下）
            info['step'] = 'use'
            if restore:
                st = bag.depot_store(role, item, depot)
                if st == bag.EXIT_ITEM and not use_rc:
                    info['store_note'] = '背包已沒有剩餘（只有一顆）'
                elif st and st != bag.EXIT_ITEM:
                    info['warn'] = f'{item} 還在 {role} 背包，沒存回倉庫（rc {st}）'
                    return (use_rc or st), info
        if kind and not use_rc:                                          # 成功判定看 buff 列圖示（龍王 = 人形、2倍智慧果 = EXP）；背包已關才看得到
            info['buff'] = bag._wait(lambda: bag.has_buff(kind), 4.0)
            if not info['buff']:
                use_rc = bag.EXIT_VERIFY
                info['warn_buff'] = f'使用後 buff 列沒看到 {kind} 圖示（沒吃到；剩的已存回倉庫）'
                info['step'] = 'verify'
                uikit.snap('depot-use-nobuff')
        if use_rc:
            return use_rc, info
        info['step'] = 'done'
        return 0, info
    finally:
        if reopen:
            try:
                heal.set_encounter(True)
            except RuntimeError as e:
                info['enc_warn'] = str(e)


def main() -> int:
    import winenv
    winenv.enable_server()
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('role')
    ap.add_argument('item')
    ap.add_argument('--depot', choices=['public', 'personal'], default='public')
    ap.add_argument('--have', action='store_true', help='道具已經在背包（上次取出後失敗）：跳過取出')
    ap.add_argument('--no-reopen', action='store_true', help='吃完不開回原地遇敵（跑任務用）')
    ap.add_argument('--no-restore', action='store_true', help='用完不把剩下的存回倉庫')
    a = ap.parse_args()
    roles = bag._roles(a.role)
    if not roles:
        print('角色名不在白名單', file=sys.stderr)
        return uikit.EXIT_USAGE
    rc, info = run(roles[0], a.item, a.depot, not a.no_restore, a.have, not a.no_reopen)
    info.update(ok=rc == 0, rc=rc)
    print(json.dumps(info, ensure_ascii=False))
    return rc


if __name__ == '__main__':
    sys.exit(main())
