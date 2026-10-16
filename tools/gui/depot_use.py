#!/usr/bin/env python3
"""從公共倉庫取出道具、使用一個、剩下的存回公共倉庫（例：2倍智慧果）。只用標準函式庫；背包 / 倉庫動作全用 bag.py。

用法（專案根目錄；WSL / Windows 原生相同）：
  uv run --no-project python tools/gui/depot_use.py DKBO 2倍智慧果 [--depot public] [--no-restore] [--have]
流程：暫停遇敵 + 等戰鬥結束（heal.set_encounter(False)）→ buff 列已有該道具的圖示（bag.BUFF_KIND：龍王的守護 = 人形 dragon、2倍智慧果 = EXP exp）就跳過
→ bag.depot_take（整疊取出）→ bag.use_item → bag.depot_store（剩餘存回）→ 關背包後等 buff 列出現圖示（4 秒）→ 開回遇敵（不管成敗都會開回）。
成敗判準（2026-10-16 起共用 eatbuff.verify）：BUFF_KIND 的道具吃後要看到圖示、且 buff 剩餘時間增加（吃前沒圖示 = 0；讀不出時間以圖示為準），沒吃到 = 95（剩的已存回倉庫；不比道具數量）；use 後背包還開著 → eatbuff.close_bag_leftover 再關；
舊版判準：BUFF_KIND 的道具一定要看到圖示才回 0，沒看到 = 95；use_item 回 0 只代表「按了使用、彈窗關了」
（2026-10-12 2倍智慧果按了使用、彈窗關了卻沒扣道具，舊版沒驗就回 0）。不在 BUFF_KIND 的道具沒辦法驗，維持 use_item 結果。
每步失敗就停、回該步的退出碼（bag 90～96），不重點；取出後失敗會提醒「道具還在背包」。
任何出口（成功 / 失敗 / 例外）都由 bag.Session 結束時 close_leftover 收尾；另外**非 0 結束一律再 tidy()**（等 1 秒再 close_leftover 一次：
2026-10-14 08:21 / 08:49 / 09:01 rc 90 step=open，Session 判背包沒開所以沒關，面板晚一步才出現 → 下一片 quest.py 誤報 9）：道具彈窗 ESC、NPC 對話框蓋住背包 → ESC（不回答）、背包外框在 → 點 ✕ 1280,113
（2026-10-13 08:04 rc 90：吃龍王途中自動巡路抵達看門者，對話框把背包藏起來，舊版沒關 → quest.py 誤報 rc 9）。questrun 在遊戲自動巡路中不呼叫本工具。
questrun --dragon（2026-10-13 起）用 restore=False（剩的留在 DKBO 背包）、之後 have=True 直接從背包吃，run 結束才 bag.depot_store 存回；buff 判斷與 questrun 共用 bag.buff_state。
吃下並驗到圖示後，以「吃的時刻 + 持續時間」寫本視窗 bufftime.json（bufftime.record_eaten：exp 6 小時、dragon 10 分鐘，src = eat；psa-hud Buff 列倒數，不用再跑 bufftime.py read；跳過不吃 = 不改檔；寫失敗只警告）。
最後一行 JSON {"ok","rc","step","buff",...}。
"""
import argparse
import json
import re
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import bag  # noqa: E402
import bufftime  # noqa: E402,F401
import eatbuff  # noqa: E402
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


TIDY_WAIT_S = 1.0               # 失敗收尾前先等一下：背包面板可能晚一步才開（open_panel_ex 判沒開、其實正在開）


def tidy() -> str:
    """任何失敗出口的收尾（2026-10-14 08:21 / 08:49 / 09:01 rc 90 step=open：Session 判背包沒開 → 沒關；面板晚一步出現 / 對話框蓋住，
    下一片 quest.py 連 3 次不認得 → 9）：等 TIDY_WAIT_S → bag.close_leftover（道具彈窗 ESC、NPC 對話框 ESC 不回答、背包外框在 → ✕）。
    不認得的畫面不碰。→ close_leftover 做了什麼（'' = 沒東西要關）"""
    uikit.sleep(TIDY_WAIT_S)
    try:
        return bag.close_leftover(dialog_esc=True)
    except Exception as e:                                               # noqa: BLE001
        return f'error:{e}'


def run(role: str, item: str, depot: str = 'public', restore: bool = True, have: bool = False, reopen: bool = True) -> tuple:
    """→ (rc, info)。buff 圖示已在就跳過；encounter 先關、結束後一定開回（原本就關著也開回：本工具只在掛機時用）。
    非 0 結束（9 / 10 除外，畫面要留給人看）一律先 tidy() 關殘留面板，再開回遇敵"""
    info = {'role': role, 'item': item, 'depot': depot}
    rc = 1
    try:
        rc, info = _run(role, item, depot, restore, have, info)
        return rc, info
    finally:
        if rc and rc not in (uikit.EXIT_UNKNOWN_SCREEN, uikit.EXIT_HALT):
            t = tidy()
            if t:
                info['tidy'] = t
        if reopen:
            try:
                heal.set_encounter(True)
            except RuntimeError as e:
                info['enc_warn'] = str(e)


def _run(role: str, item: str, depot: str, restore: bool, have: bool, info: dict) -> tuple:
    kind = bag.buff_kind(item)
    heal.encounter_off_wait()                                    # 關遇敵 + 等 VS 牌消失（戰鬥中點「使用」無效，2026-10-16）
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
        eat_ts = time.time()                                          # 吃的時刻（到期 = 這個時刻 + 持續時間）
        if restore:
            st = bag.depot_store(role, item, depot)
            if st == bag.EXIT_ITEM and not use_rc:
                info['store_note'] = '背包已沒有剩餘（只有一顆）'
            elif st and st != bag.EXIT_ITEM:
                info['warn'] = f'{item} 還在 {role} 背包，沒存回倉庫（rc {st}）'
                return (use_rc or st), info
    eatbuff.close_bag_leftover(info)                                 # use 後背包沒關（戰鬥蓋住等）→ 再關一次
    if kind and not use_rc:                                          # 成功判定看 buff 剩餘時間增加（吃前沒圖示 = 0）；背包已關才讀得到
        if eatbuff.verify(kind, 0, eat_ts, info):
            use_rc = bag.EXIT_VERIFY
            info['step'] = 'verify'
            info['warn_buff'] = info.get('warn_buff', '') + '（剩的已存回倉庫）'
    if use_rc:
        return use_rc, info
    info['step'] = 'done'
    return 0, info


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
