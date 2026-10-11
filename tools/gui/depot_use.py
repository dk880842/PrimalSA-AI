#!/usr/bin/env python3
"""從公共倉庫取出道具、使用一個、剩下的存回公共倉庫（例：2倍智慧果）。只用標準函式庫；背包 / 倉庫動作全用 bag.py。

用法（專案根目錄；WSL / Windows 原生相同）：
  uv run --no-project python tools/gui/depot_use.py DKBO 2倍智慧果 [--depot public] [--no-restore] [--have]
流程：暫停遇敵 + 等戰鬥結束（heal.set_encounter(False)）→ bag.depot_take（整疊取出）→ bag.use_item（verify_buff）→ bag.depot_store（剩餘存回）
→ 開回遇敵（不管成敗都會開回）。每步失敗就停、回該步的退出碼（bag 90～96），不重點；取出後失敗會提醒「道具還在背包」。
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


# bag.POPUP_SIG 只有單張樣本，量到的 2 倍智慧果倉庫彈窗（多行說明、藍色「取出」鈕）不吻合（2026-10-11 實測 rc 90）。
# 這裡補一組右下框線 + 彈窗內暗底兩點（倉庫取出彈窗與背包使用彈窗的按鈕列不同，不用按鈕當特徵；沒彈窗時這三點分別是亮棕 / 米色 / 棕）（截圖座標，樣本 tools/.cache/ui-log/110407-bag-depot-nopopup.png），與舊特徵「任一組吻合」就算彈窗開著。
POPUP_SIG2 = [(968, 500, 183, 127, 64, 25), (730, 230, 38, 28, 22, 22), (600, 600, 35, 26, 22, 22)]


def _popup_open() -> bool:
    return uikit.sig_match(bag.POPUP_SIG) or uikit.sig_match(POPUP_SIG2)


bag.POPUP = uikit.Panel('BAGPOPUP', None, bag.POPUP_SIG, None, forbidden=bag.POPUP.forbidden, is_open_fn=_popup_open)


# 彈窗垂直置中，說明文字越長標題越高：bag.POPUP_NAME_BOX（y 133）是短說明的位置；2倍智慧果（說明 4 行）標題在 y≈270。
# 預設框讀不到字才改讀這個框（備援框只含標題列，不含說明文字）
POPUP_NAME_ALT = (600, 250, 330, 45)
_orig_popup_name = bag.popup_name


def _popup_name() -> str:
    return _orig_popup_name() or bag._ocr_join(POPUP_NAME_ALT, bag.NAME_OPTS)


bag.popup_name = _popup_name


def store_back(role: str, want: str, depot: str = 'public') -> int:
    """背包 want（整疊）存入倉庫。bag.depot_store 在倉庫頁用背包面板特徵點背包格會被擋（rc 90），所以這裡改用倉庫面板：
    背包找格 → 開倉庫頁 → 單擊右半背包格 → 彈窗名稱核對 → 按鈕列 OCR 有「存入」才點 732,648 → 彈窗關了且該格不再吻合"""
    if bag.protected(want):
        return bag._fail(bag.EXIT_GUARD, f'「{want}」在保護名單，不存倉')
    with bag.Session() as s:
        if s.rc:
            return s.rc
        rc = bag.select_role(role)
        if rc:
            return rc
        i = bag.find_item(want, popup_fallback=False)
        if i is None:
            return bag._fail(bag.EXIT_ITEM, f'{role} 背包找不到「{want}」', 'bag-noitem')
        rc = bag.open_depot(depot)
        if rc:
            return rc
        x, y = bag.slot_xy(i)
        if not bag._click(x, y, bag.DEPOT, f'bag 倉庫頁點背包第 {i + 1} 格') or not bag._wait(bag.popup_open, 1.5):
            return bag._fail(bag.EXIT_PANEL, f'倉庫頁點背包第 {i + 1} 格沒開彈窗', 'bag-store-nopopup')
        nm = bag.popup_name()
        if not bag.name_match(nm, want):
            bag.close_popup()
            return bag._fail(bag.EXIT_NAME, f'彈窗名稱 OCR 是 {nm!r}，不是「{want}」（不存）', 'bag-store-name')
        txt = bag._ocr_join(bag.POPUP_BTN_BOX, bag.BTN_OPTS)
        if '存入' not in re.sub(r'\s+', '', txt):
            bag.close_popup()
            return bag._fail(bag.EXIT_NAME, f'彈窗按鈕列 OCR 是 {txt!r}，沒有「存入」', 'bag-store-btn')
        if not bag._click(732, 648, bag.POPUP, f'bag 存入「{want}」', wait_ms=700):
            return bag._fail(bag.EXIT_PANEL, '彈窗特徵消失，沒點存入', 'bag-store-gone')
        if not bag._wait(lambda: not bag.popup_open(), 2.5):
            return bag._fail(bag.EXIT_VERIFY, '按了存入但彈窗沒關（不重點）', 'bag-store-verify')
        t = bag.read_slot_name(i)
        if t and bag.name_match(t, want):
            return bag._fail(bag.EXIT_VERIFY, f'存入後第 {i + 1} 格仍讀到「{want}」', 'bag-store-verify')
    return 0


def use_one(role: str, want: str) -> int:
    """背包使用一個。bag.use_item 的按鈕座標靠 OCR 判斷版型，「使用 / 更多」並排的彈窗曾被誤判成單鈕（732,648 點空）。
    這裡固定：OCR 按鈕列必須有「使用」；有「更多」= 並排版型 → 使用在 619,648，否則 732,648。點一次、驗證彈窗關了或數量少 1"""
    with bag.Session() as s:
        if s.rc:
            return s.rc
        rc = bag.select_role(role)
        if rc:
            return rc
        i = bag.find_item(want, popup_fallback=False)
        if i is None:
            return bag._fail(bag.EXIT_ITEM, f'{role} 背包找不到「{want}」', 'bag-noitem')
        if not bag.open_slot_popup(i):
            return bag._fail(bag.EXIT_PANEL, f'點第 {i + 1} 格沒開彈窗', 'bag-nopopup')
        nm = bag.popup_name()
        if not bag.name_match(nm, want):
            bag.close_popup()
            return bag._fail(bag.EXIT_NAME, f'彈窗名稱 OCR 是 {nm!r}，不是「{want}」（不使用）', 'bag-popup-name')
        txt = re.sub(r'\s+', '', bag._ocr_join(bag.POPUP_BTN_BOX, bag.BTN_OPTS))
        if '使用' not in txt:
            bag.close_popup()
            return bag._fail(bag.EXIT_NAME, f'彈窗按鈕列 OCR 是 {txt!r}，沒有「使用」', 'bag-use-btn')
        x = 619 if is_pair_layout() else 732
        if not bag._click(x, 648, bag.POPUP, f'bag 使用「{want}」', wait_ms=600):
            return bag._fail(bag.EXIT_PANEL, '彈窗特徵消失，沒點使用', 'bag-use-gone')
        bag._wait(lambda: not bag.popup_open(), 2.0)
        if bag.popup_open():                       # 疊加道具使用後彈窗可能還開著：ESC 關掉，不重點
            bag.close_popup()
    return 0


def is_pair_layout() -> bool:
    """彈窗按鈕列是「使用（藍）+ 更多（橘）」並排：看 825,648 一帶是橘黃（更多鈕），而 732,648 附近不是藍（單鈕版）"""
    cols = uikit.px([(825, 648), (619, 648)]) or []
    if len(cols) != 2:
        return False
    (r, g, b), (r2, g2, b2) = cols
    return r > 200 and g > 130 and b < 100 and b2 > r2          # 橘黃 + 藍


def run(role: str, item: str, depot: str = 'public', restore: bool = True, have: bool = False) -> tuple:
    """→ (rc, info)。encounter 先關、結束後一定開回（原本就關著也開回：本工具只在掛機時用）"""
    info = {'role': role, 'item': item, 'depot': depot}
    enc_off = False
    try:
        heal.set_encounter(False)
        enc_off = True
        heal.gui('seq', f'waitpix 20000 {heal.SIG_NO_BATTLE} 40')       # 關遇敵不會中止正在打的那場：等 VS 牌消失
        for step, fn in (('take', lambda: 0 if have else bag.depot_take(role, item, depot)),
                         ('use', lambda: use_one(role, item)),
                         ('store', lambda: store_back(role, item, depot) if restore else 0)):
            rc = fn()
            info['step'] = step
            if rc:
                if rc == bag.EXIT_ITEM and step == 'store':
                    info['store_note'] = '背包已沒有剩餘（只有一顆）'
                    rc = 0
                else:
                    if step != 'take':
                        info['warn'] = f'{item} 已取出在 {role} 背包，沒存回倉庫'
                    return rc, info
        info['step'] = 'done'
        return 0, info
    finally:
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
    ap.add_argument('--no-restore', action='store_true', help='用完不把剩下的存回倉庫')
    a = ap.parse_args()
    roles = bag._roles(a.role)
    if not roles:
        print('角色名不在白名單', file=sys.stderr)
        return uikit.EXIT_USAGE
    rc, info = run(roles[0], a.item, a.depot, not a.no_restore, a.have)
    info.update(ok=rc == 0, rc=rc)
    print(json.dumps(info, ensure_ascii=False))
    return rc


if __name__ == '__main__':
    sys.exit(main())
