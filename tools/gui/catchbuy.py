#!/usr/bin/env python3
"""外掛「捉寵設置」的「+」買可抓捕數（petquest 與 rebirth_pets 共用；只用標準函式庫）。

每按一次 +1 可抓捕數、扣 50,000 石幣（2026-10-12 實測）。**紅區按鈕**：只有呼叫端明確帶 --confirm-buy-bait（petquest）/
--confirm-buy-catch（rebirth_pets）才會進來。每次按前後都讀石幣（寵物面板頂部）：要剛好少 PLUS_COST、鑽石不變，否則停手（鐵則 3）。

  parse_money(lines)                              OCR 行 → (石幣, 鑽石)：石幣 x<450、鑽石 450～700（x 分區 + 去重；讀不到 None，2026-10-13 三轉）
  parse_count_zero(txt, zero_ok)                  可抓捕數；zero_ok = 有「可抓捕數」字樣但沒數字 → 0（0 時 OCR 常漏「0」，2026-10-13 三轉 163）
  read_money_stable(read_fn, sleep_fn)            連續兩次讀到同一個非 0 石幣才採用（2026-10-15 單次讀成 0 → 163 的修法；讀 0 / None = 讀錯重讀）
  money()                                         開寵物面板（等 0.6 秒）讀 (石幣, 鑽石)；讀不穩 (None, None) + 存圖 catchbuy-money-unreadable
  press_plus(role, limit=None)                    外掛 → 角色 → 捉寵設置 → 讀可抓捕數 → 點「+」一次 → 讀回 → 關面板 → (rc, 按前, 按後)
                                                  limit：按前可抓捕數已 ≥ limit 就不點（回 (0, 前, 前)）
  buy(role, n, money_fn, press_fn, log)           固定按 n 次 → (kind, msg, rc, bought)
  buy_to(role, target, money_fn, press_fn, log, min_before=None)
                                                  按到可抓捕數 = target 為止（續跑安全）→ 同上；min_before = 背包現有誘餌數：誘餌不夠只買缺額
                                                  （外掛可抓捕數 = 背包誘餌 + 買的次數，**推測**，按前讀到的數字 < min_before 就不按、停手，
                                                  每次按後仍驗 +1 / 石幣剛好 −50,000）
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


def parse_count_zero(txt, zero_ok: bool = False):
    """捉寵設置那一列 OCR 文字 → 可抓捕數（純函式；rebirth_pets.parse_count 為主）。zero_ok：讀到「可抓捕數」但後面完全沒有數字 → 0
    （2026-10-13 三轉實機：可抓捕數 = 0 時 OCR 常整個漏掉「0」只剩「可抓捕數:」「+」→ 舊版回 163；按後必須讀到 1 才算數，_one 仍驗 +1 / 石幣剛好 -50000）。
    沒讀到「可抓捕數」字樣 → None（不猜）"""
    import rebirth_pets as rp
    n = rp.parse_count(txt)
    t = str(txt or '')
    if n is None and zero_ok and '可抓捕數' in t and not re.search(r'\d', t.split('可抓捕數')[-1]):
        return 0
    return n


def read_money_stable(read_fn, sleep_fn=None, tries: int = 5, settle: float = 0.6) -> tuple:
    """讀石幣 / 鑽石要「連續兩次讀到同一個非 0 石幣」才算數（純函式，read_fn() → (石幣, 鑽石)）。
    2026-10-15 p1 卡坦 163「石幣 0 不夠 50000」（實際約 6,720,000）：面板剛開 1 秒內就讀一次、單次 OCR 讀成 0 → 不買；
    現在面板開好先等 settle 秒，石幣讀到 None / 0（帳號有 50,000 以上才會走到這裡，0 一律當讀錯）/ 兩次不一致 → 重讀，最多 tries 次，
    仍不穩 → (None, None)（呼叫端「不買、回錯誤」）。鑽石以兩次一致的那組為準（一致才採用，不一致 → None 不驗鑽石增減由呼叫端略過）"""
    if sleep_fn:
        sleep_fn(settle)
    prev = None
    for _ in range(tries):
        stone, dia = read_fn()
        if stone:                                                  # None / 0 = 讀錯
            if prev is not None and prev[0] == stone:
                return stone, (dia if dia == prev[1] else None)
            prev = (stone, dia)
        elif sleep_fn:
            sleep_fn(0.4)
    return None, None


def money() -> tuple:
    """寵物面板頂部資源列 → (石幣, 鑽石)；面板打不開 / 讀不穩 → (None, None)（讀失敗存圖到 ui-log）"""
    import pet
    import rebirth_pets as rp
    with pet.Session(False, True) as s:
        if s.rc:
            return None, None
        r = read_money_stable(lambda: parse_money(rp.ocr_lines(MONEY_BOX, '-Zooms', '2,3,4')), uikit.sleep)
        if r[0] is None:
            try:
                uikit.snap('catchbuy-money-unreadable')
            except Exception:                                      # noqa: BLE001
                pass
        return r


def press_plus(role, limit=None, min_before=None) -> tuple:
    """外掛 → 選角色 → 捉寵設置 → 讀可抓捕數 → 點「+」一次 → 讀回 → 關面板 → (rc, 按前, 按後)。按前讀不到可抓捕數 → 不點。
    min_before：按前可抓捕數低於這個值（例：背包誘餌數 → 外掛數字沒把背包誘餌算進去）→ 不點、回 (EXIT_BAIT, 前, None)"""
    import ass
    import rebirth_pets as rp
    rt = rp.Tools()
    rc = rt._ass_open(role, 'catch')
    try:
        if rc:
            return rc, None, None
        def read(zero_ok=False):
            return parse_count_zero(''.join(t for t, _, _ in rp.ocr_lines(rp.OCR_TAB_CATCH, '-Zooms', '2,3,4')), zero_ok)
        before = read(zero_ok=True)
        if before is None or not ass.panel_open():
            return EXIT_BAIT, before, None
        if limit is not None and before >= limit:
            return 0, before, before
        if min_before is not None and before < min_before:
            return EXIT_BAIT, before, None
        uikit.gui('seq', f'click {PLUS_XY[0]} {PLUS_XY[1]}; wait 800', note=f'{role} 捉寵設置「+」買 1 個可抓捕數（--confirm-buy-*）')
        after = read()
        return 0, before, after
    finally:
        try:
            ass.close_panel()
        except Exception:                                          # noqa: BLE001
            pass


def _one(role, money_fn, press_fn, log, limit=None, min_before=None):
    """按一次（含前後石幣檢查）→ (kind, msg, rc, rec | None, pressed)"""
    s0, d0 = money_fn()
    if s0 is None:
        return 'fail', f'{role} 買可抓捕數前讀不到石幣（寵物面板頂部，MONEY_BOX 待實機量）→ 不按「+」', 0, None, False
    if s0 < PLUS_COST:
        return 'fail', f'石幣 {s0} 不夠 {PLUS_COST} → 不買', 0, None, False
    if limit is None:
        rc, before, after = press_fn(role)
    elif min_before is None:
        rc, before, after = press_fn(role, limit)
    else:
        rc, before, after = press_fn(role, limit, min_before)
    if rc == EXIT_BAIT and min_before is not None and before is not None and before < min_before:
        return 'fail', f'{role} 外掛可抓捕數 {before} < 背包誘餌 {min_before}：外掛數字沒把背包誘餌算進去（不能相加）→ 不按「+」、停手', 0, None, False
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


def buy_to(role, target, money_fn=money, press_fn=press_plus, log=print, min_before=None) -> tuple:
    """按到可抓捕數 = target 為止（先讀、已夠就不按；續跑安全）。最多按 target 次。
    min_before：背包現有誘餌數（誘餌不夠只買缺額：外掛可抓捕數 = 背包誘餌 + 買的次數，每次按前後讀回 +1 驗證；
    按前讀到的數字 < min_before = 外掛沒把背包誘餌算進去 → 不按、fail，避免白花 50,000）"""
    bought = []
    for _ in range(target + 1):
        kind, msg, rc, rec, pressed = _one(role, money_fn, press_fn, log, limit=target, min_before=min_before)
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
