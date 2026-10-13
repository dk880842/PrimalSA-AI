#!/usr/bin/env python3
"""外掛「捉寵設置」的「+」買可抓捕數（petquest 與 rebirth_pets 共用；只用標準函式庫）。

每按一次 +1 可抓捕數、扣 50,000 石幣（2026-10-12 實測）。**紅區按鈕**：只有呼叫端明確帶 --confirm-buy-bait（petquest）/
--confirm-buy-catch（rebirth_pets）才會進來。每次按前後都讀石幣（寵物面板頂部）：要剛好少 PLUS_COST、鑽石不變，否則停手（鐵則 3）。

  parse_money(lines)                              OCR 行 → (石幣, 鑽石)
  money()                                         開寵物面板讀 (石幣, 鑽石)；讀不到 (None, None)
  press_plus(role, limit=None)                    外掛 → 角色 → 捉寵設置 → 讀可抓捕數 → 點「+」一次 → 讀回 → 關面板 → (rc, 按前, 按後)
                                                  limit：按前可抓捕數已 ≥ limit 就不點（回 (0, 前, 前)）
  buy(role, n, money_fn, press_fn, log)           固定按 n 次 → (kind, msg, rc, bought)
  buy_to(role, target, money_fn, press_fn, log)   按到可抓捕數 = target 為止（續跑安全）→ 同上
    kind = 'ok' / 'fail'（呼叫端 fail(EXIT, msg)）/ 'pass'（rc 是 ass / uikit 退出碼，呼叫端 pass_or）
"""
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import uikit  # noqa: E402

PLUS_XY = (1295, 315)              # 外掛捉寵設置「可抓捕數 +」
PLUS_COST = 50000
MONEY_BOX = (250, 5, 700, 40)      # 寵物面板頂部資源列（石幣 x≈335,y≈23，右邊依序鑽石 / 活力 / 聲望；ui/pet.md）—— OCR 框待實機量；讀不到就不買
EXIT_BAIT = 163                    # = petquest.EXIT_BAIT（誘餌 / 買可抓捕數失敗）；rebirth_pets 自己把 pass 的碼對應成 EXIT_CATCH


def parse_money(lines) -> tuple:
    """寵物面板頂部資源列 OCR 行 [(文字, x, y)] → (石幣, 鑽石)：數字（去逗號）依 x 排序，第一個 = 石幣、第二個 = 鑽石；讀不到 None"""
    nums = []
    for t, x, _y in lines or []:
        for m in re.finditer(r'\d[\d,]*', str(t)):
            v = m.group().replace(',', '')
            if v.isdigit():
                nums.append((x, int(v)))
    nums.sort(key=lambda a: a[0])
    ded = []
    for x, v in nums:                                              # 多組 OCR 設定會把同一個數字讀多次（x 差 < 80）→ 合併，否則鑽石欄會變成石幣的重複（2026-10-13 實機誤停）
        if ded and abs(x - ded[-1][0]) < 80:
            continue
        ded.append((x, v))
    nums = ded
    stone = next((v for x, v in nums if x < 450), None)
    dia = next((v for x, v in nums if 450 <= x < 700), None)       # 鑽石欄在 x≈520～600；讀不到（OCR 常漏「0」）= None，不要拿 x≈808 的活力當鑽石（2026-10-13 實機誤停）
    return stone, dia


def money() -> tuple:
    """寵物面板頂部資源列 → (石幣, 鑽石)；面板打不開 / 讀不到 → (None, None)"""
    import pet
    import rebirth_pets as rp
    with pet.Session(False, True) as s:
        if s.rc:
            return None, None
        return parse_money(rp.ocr_lines(MONEY_BOX, '-Zooms', '2,3'))


def press_plus(role, limit=None) -> tuple:
    """外掛 → 選角色 → 捉寵設置 → 讀可抓捕數 → 點「+」一次 → 讀回 → 關面板 → (rc, 按前, 按後)。按前讀不到可抓捕數 → 不點"""
    import ass
    import rebirth_pets as rp
    rt = rp.Tools()
    rc = rt._ass_open(role, 'catch')
    try:
        if rc:
            return rc, None, None
        def read(zero_ok=False):
            txt = ''.join(t for t, _, _ in rp.ocr_lines(rp.OCR_TAB_CATCH, '-Zooms', '2,3,4'))
            n = rp.parse_count(txt)
            if n is None and zero_ok and '可抓捕數' in txt and not re.search(r'\d', re.sub(r'.*可抓捕數', '', txt)):
                return 0                                           # 2026-10-13 實機：可抓捕數 = 0 時 OCR 常整個漏掉「0」只剩「可抓捕數:」「+」；按後必須讀到 1 才算數（_one 仍驗 +1 / 石幣剛好 -50000）
            return n
        before = read(zero_ok=True)
        if before is None or not ass.panel_open():
            return EXIT_BAIT, before, None
        if limit is not None and before >= limit:
            return 0, before, before
        uikit.gui('seq', f'click {PLUS_XY[0]} {PLUS_XY[1]}; wait 800', note=f'{role} 捉寵設置「+」買 1 個可抓捕數（--confirm-buy-*）')
        after = read()
        return 0, before, after
    finally:
        try:
            ass.close_panel()
        except Exception:                                          # noqa: BLE001
            pass


def _one(role, money_fn, press_fn, log, limit=None):
    """按一次（含前後石幣檢查）→ (kind, msg, rc, rec | None, pressed)"""
    s0, d0 = money_fn()
    if s0 is None:
        return 'fail', f'{role} 買可抓捕數前讀不到石幣（寵物面板頂部，MONEY_BOX 待實機量）→ 不按「+」', 0, None, False
    if s0 < PLUS_COST:
        return 'fail', f'石幣 {s0} 不夠 {PLUS_COST} → 不買', 0, None, False
    rc, before, after = press_fn(role) if limit is None else press_fn(role, limit)
    if rc:
        return 'pass', f'{role} 外掛「+」失敗 rc={rc}（按前可抓捕數 {before}）', rc, None, False
    if limit is not None and after == before and before is not None and before >= limit:
        return 'ok', '', 0, None, False                            # 已夠，沒按
    if after != (before or 0) + 1:
        return 'fail', f'{role}「+」按了可抓捕數 {before} → {after}（不是 +1）→ 停手', 0, None, True
    s1, d1 = money_fn()
    rec = {'role': role, 'stone': [s0, s1], 'diamond': [d0, d1]}
    if s1 != s0 - PLUS_COST:
        return 'fail', f'{role}「+」後石幣 {s0} → {s1}（不是剛好扣 {PLUS_COST}）→ 停手（可能扣了別的貨幣）', 0, rec, True
    if d0 is not None and d1 is not None and d1 != d0:
        return 'fail', f'{role}「+」後鑽石 {d0} → {d1} 有變 → 停手（鐵則 3）', 0, rec, True
    log(f'{role} 買可抓捕數 1 個：石幣 {s0} → {s1}、可抓捕數 {before} → {after}')
    return 'ok', '', 0, rec, True


def buy(role, n, money_fn=money, press_fn=press_plus, log=print) -> tuple:
    """固定按 n 次。回 (kind, msg, rc, bought[紀錄])；中途失敗 bought 含已按的"""
    bought = []
    for i in range(n):
        kind, msg, rc, rec, _ = _one(role, money_fn, press_fn, log)
        if rec:
            bought.append(rec)
        if kind != 'ok':
            return kind, msg, rc, bought
        log(f'{role} 第 {i + 1}/{n} 次完成')
    return 'ok', '', 0, bought


def buy_to(role, target, money_fn=money, press_fn=press_plus, log=print) -> tuple:
    """按到可抓捕數 = target 為止（先讀、已夠就不按；續跑安全）。最多按 target 次"""
    bought = []
    for _ in range(target + 1):
        kind, msg, rc, rec, pressed = _one(role, money_fn, press_fn, log, limit=target)
        if rec:
            bought.append(rec)
        if kind != 'ok':
            return kind, msg, rc, bought
        if not pressed:
            return 'ok', '', 0, bought
    return 'fail', f'{role} 按了 {target + 1} 次仍沒到 {target}', 0, bought


def main(argv=None) -> int:
    """CLI：買可抓捕數（紅區，花石幣）：catchbuy.py DKBO2 5 --confirm-buy → 按到可抓捕數 = 5"""
    import argparse
    import winenv
    winenv.enable_server()
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('role')
    ap.add_argument('target', type=int)
    ap.add_argument('--confirm-buy', action='store_true', help='確認花石幣（每個 50,000）；沒給只印計畫')
    a = ap.parse_args(argv)
    if not a.confirm_buy:
        print(f'catchbuy：會在 {a.role} 的外掛捉寵設置按「+」到可抓捕數 = {a.target}（每次 {PLUS_COST} 石幣）；加 --confirm-buy 才執行')
        return 0
    rc = uikit.preflight('catchbuy')
    if rc:
        return rc
    kind, msg, code, bought = buy_to(a.role, a.target)
    print(kind, msg, bought)
    return 0 if kind == 'ok' else (code or EXIT_BAIT)


if __name__ == '__main__':
    sys.exit(main())
