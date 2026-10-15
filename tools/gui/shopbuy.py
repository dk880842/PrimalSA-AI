#!/usr/bin/env python3
"""薩姆吉爾醫院藥劑師（1005:22,57）買耐久力回複藥 ×1 給每個缺的人（紅暴 2031 前置；只用標準函式庫）。

**隊員無法和 NPC 互動**（遊戲提示「網路協議錯誤隊員無法和NPC互動」，購買數量會變 0）→ 必須先解散隊伍、每人單人買、買完 team.form。
流程（2026-10-14 實機手動跑過 5 人一次，本腳本照那次寫成、**腳本本身未實機**）：
  bag.team_read 找缺藥的人 → 傳送回薩姆吉爾 + 進醫院（heal.py --no-return）→ team.py disband →
  逐人：char.py switch → walk 1005:24,63 → 點藥劑師 NPC（BUY_NPC 463,288；剛走到時第 1 下常被吃掉 → 最多點 3 次等對話框）→
  「道具商店」948,462 → 「購買」995,592（數量預設 1、500 石幣）→ 提示「確定」615,557 → ESC →
  char.py ensure DKBO → team.py form → bag.team_read 再驗每人都有。
用法：uv run --no-project python tools/gui/shopbuy.py medicine [--roles DKBO,DKBO2] [--confirm-spend] [--dry-run]
  --confirm-spend 才會真的花石幣（每人 500）；沒給只列誰缺。
可 import：shopbuy.run(roles, confirm_spend=True) → (rc, info)。紅暴已不呼叫（2026-10-15 起耐久力回複藥 NPC 會給，不檢查不買），模組保留備用。
（2026-10-14 修：舊版呼叫 heal.main(['--no-return']) / char.main(['switch', …])，兩者都不收參數 → 一跑就 TypeError；改呼叫 heal.heal_trip / char.switch / char.ensure）
退出碼：0 完成 / 1 參數 / 2 佈局 / 9 疑似驗證視窗 / 10 netwatch / 180 讀背包失敗 / 181 前置（傳送 / 解散）失敗 /
  182 某人買不到（對話框沒出現 / 商店沒開）/ 183 買完仍缺 / 184 重新組隊失敗（藥已買齊，改手動 team.py form）
"""
import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import charstate  # noqa: E402
import clients  # noqa: E402
import uikit  # noqa: E402

ROLES = clients.roster()      # 這個視窗（PSA_CLIENT）的名單：主視窗 DKBO、DKBO2～5；PrimalSA2 = DKBO6～10；第 1 個 = 隊長
LEADER = ROLES[0] if ROLES else ''
ITEM = '耐久力回複藥'
BUY_NPC = (463, 288)          # 藥劑師，站在 1005:24,63 時的截圖座標（2026-10-14 量；鏡頭最左）
STAND = (24, 63)
DIALOG_SIG = '948,462'        # 對話框「道具商店」鈕（點 NPC 後有棕底對話框；用 pixel 比顏色）
SHOP_BTN = (948, 462)
BUY_BTN = (995, 592)
CONFIRM_BTN = (615, 557)
EXIT_BAG, EXIT_PRE, EXIT_BUY, EXIT_STILL, EXIT_FORM = 180, 181, 182, 183, 184
SRC = 'shopbuy'


def _gui(*a, note=''):
    return uikit.gui(*a, note=note)


def missing_roles(roles) -> tuple:
    """背包讀一次 → (rc, [缺 ITEM 的角色])"""
    import bag
    rc, d = bag.team_read(roles, names=(ITEM,), level=False)
    if rc:
        return rc, []
    return 0, [r for r in roles if not (d.get(r, {}).get('have') or {}).get(ITEM)]


def _shop_open() -> bool:
    """便利店面板：右上 X 紅圓（1207,107）+ 標題「便利店」。用 pixel 比紅色"""
    px = uikit.px([(1207, 107)]) or []
    return bool(px) and px[0][0] > 180 and px[0][1] < 100


def buy_one(role: str, log) -> int:
    import char
    import walk
    rc = char.switch(role)
    if rc:
        return rc
    try:
        walk.walk_to(1005, STAND[0], STAND[1])
    except RuntimeError as e:
        log(f'{role} 走不到 {STAND}：{e}')
        return EXIT_BUY
    for _ in range(3):                                         # 剛到第 1 下點擊常被吃掉
        out = _gui('seq', f'click {BUY_NPC[0]} {BUY_NPC[1]}; wait 1300; click {SHOP_BTN[0]} {SHOP_BTN[1]}; wait 1000',
                   note=f'shopbuy {role} 點藥劑師 → 道具商店')
        if _shop_open():
            break
    else:
        log(f'{role} 商店沒開')
        return EXIT_BUY
    _gui('seq', f'click {BUY_BTN[0]} {BUY_BTN[1]}; wait 700; click {CONFIRM_BTN[0]} {CONFIRM_BTN[1]}; wait 900',
         note=f'shopbuy {role} 買 {ITEM} ×1（500 石幣）')
    _gui('key', '{ESC}')
    return 0


PASS = (uikit.EXIT_UNKNOWN_SCREEN, uikit.EXIT_HALT)


def log(m: str) -> None:
    print(f'{SRC}: {m}', flush=True)


def run(roles, confirm_spend: bool = False, dry_run: bool = False) -> tuple:
    """→ (rc, info)；info = {'missing', 'bought', 'still_missing'}。confirm_spend=False / dry_run → 只讀誰缺（rc 0）。
    傳送村子 + 進醫院（heal.heal_trip no_return，不開遇敵）→ 解散 → 逐人 char.switch → 買 → char.ensure 隊長 → team.form → 重讀驗證"""
    info = {'missing': [], 'bought': []}
    rc, miss = missing_roles(list(roles))
    if rc:
        return (rc if rc in PASS else EXIT_BAG), info
    info['missing'] = miss
    log(f'缺 {ITEM}：{miss or "無"}')
    if not miss or dry_run or not confirm_spend:
        return 0, info
    import char
    import heal
    import team
    try:
        heal.heal_trip('波拉島', no_return=True, reopen=False)        # 只是借它「傳送薩姆吉爾 + 走進醫院 1005」；補滿血順便
    except RuntimeError as e:
        log(f'回村進醫院失敗：{e}')
        return EXIT_PRE, info
    rc = team.disband()                                                 # 隊員無法和 NPC 互動 → 一定要單人買
    if rc:
        return (rc if rc in PASS else EXIT_PRE), info
    for r in miss:
        rc = buy_one(r, log)
        if rc:
            char.ensure(LEADER)
            return (rc if rc in PASS else EXIT_BUY), info
        info['bought'].append(r)
    rc = char.ensure(LEADER)
    if rc in PASS:
        return rc, info
    rc = team.form()
    if rc:
        return (rc if rc in PASS else EXIT_FORM), info
    rc, still = missing_roles(list(roles))
    info['still_missing'] = still
    if rc:
        return (rc if rc in PASS else EXIT_BAG), info
    return (EXIT_STILL if still else 0), info


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('what', choices=['medicine'])
    ap.add_argument('--roles', default='all')
    ap.add_argument('--confirm-spend', action='store_true')
    ap.add_argument('--dry-run', action='store_true')
    a = ap.parse_args(argv)
    roles = list(ROLES) if a.roles == 'all' else [charstate.norm_char(r, ROLES) for r in a.roles.split(',')]
    if not roles or not all(roles):
        print(f'shopbuy：角色名不在這個視窗的名單 {ROLES}（PSA_CLIENT={clients.name()}）', file=sys.stderr)
        return uikit.EXIT_USAGE
    rc, info = run(roles, a.confirm_spend, a.dry_run)
    print(json.dumps(info, ensure_ascii=False))
    return rc


if __name__ == '__main__':
    sys.exit(main())
