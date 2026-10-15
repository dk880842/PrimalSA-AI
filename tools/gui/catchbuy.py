#!/usr/bin/env python3
"""外掛「捉寵設置」的「+」買可抓捕數（petquest 與 rebirth_pets 共用；只用標準函式庫）。

每按一次 +1 可抓捕數、扣 50,000 石幣（2026-10-12 實測）。**紅區按鈕**：petquest（寵物任務，2026-10-15 起不需旗標，使用者）/
rebirth_pets（--confirm-buy-catch）才會進來。2026-10-15 起不讀石幣、不因石幣擋（使用者）；保險 = 只按缺額、每次按後可抓捕數必須 +1（沒增加就停）、按前外掛數 < 背包誘餌不按、
**鑽石按前讀不到 → 不按、停手；按後讀不到或有變 → 停手**（鐵則 3）。

鑽石怎麼讀（2026-10-15 修）：舊版用 OCR 讀寵物面板頂部資源列，p1 實跑一路「鑽石 None → None」= 鑽石檢查形同虛設。
根因：帳號鑽石 = 0，資源列只有一個單獨的「0」（x≈552～558、y≈17～29，截圖 ui-log/005319-pet-slot-1.png），Windows OCR 對單獨一個「0」幾乎都漏讀
（parse_money 只能回 None）。改成像素點陣：DIA_BOX 白字二值化 → 剛好是「0」的字形 → '0'；其他內容 → 'px:<點陣指紋>'（不解讀數字，只比前後是否相同）；
沒有白字（面板沒開 / 位置不對）→ None。點陣是同一畫面的固定 UI 字，前後一致才算讀到（read_dia_stable 兩次相同）。

  parse_money(lines)                              OCR 行 → (石幣, 鑽石)：石幣 x<450、鑽石 450～700（x 分區 + 去重；讀不到 None，2026-10-13 三轉）
  parse_count_zero(txt, zero_ok)                  可抓捕數；zero_ok = 有「可抓捕數」字樣但沒數字 → 0（0 時 OCR 常漏「0」，2026-10-13 三轉 163）
  read_money_stable(read_fn, sleep_fn)            （舊，不再用於買）連續兩次讀到同一個非 0 石幣才採用
  dia_from_rows(rows)                             鑽石點陣 → '0' / 'px:指紋' / None（純函式）
  read_dia_stable / money()                       開寵物面板讀鑽石點陣（兩次一致才採用）→ (None, 鑽石讀值)；石幣不讀
  press_plus(role, limit=None)                    外掛 → 角色 → 捉寵設置 → 讀可抓捕數 → 點「+」一次 → 讀回 → 關面板 → (rc, 按前, 按後)
                                                  limit：按前可抓捕數已 ≥ limit 就不點（回 (0, 前, 前)）
  buy(role, n, money_fn, press_fn, log)           固定按 n 次 → (kind, msg, rc, bought)
  buy_to(role, target, money_fn, press_fn, log, min_before=None)
                                                  按到可抓捕數 = target 為止（續跑安全）→ 同上；min_before = 背包現有誘餌數：誘餌不夠只買缺額
                                                  （外掛可抓捕數 = 背包誘餌 + 買的次數，**推測**，按前讀到的數字 < min_before 就不按、停手，
                                                  每次按後仍驗 +1 / 鑽石不變）
    kind = 'ok' / 'fail'（呼叫端 fail(EXIT, msg)）/ 'pass'（rc 是 ass / uikit 退出碼，呼叫端 pass_or）
"""
import hashlib
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import uikit  # noqa: E402

PLUS_XY = (1295, 315)              # 外掛捉寵設置「可抓捕數 +」
PLUS_COST = 50000
MONEY_BOX = (250, 5, 700, 40)      # 寵物面板頂部資源列（石幣 x≈335,y≈23，右邊依序鑽石 / 活力 / 聲望；ui/pet.md）—— OCR 框待實機量；讀不到就不買
DIA_BOX = (545, 12, 175, 22)       # 鑽石數字（x, y, w, h；截圖座標）：鑽石圖示 x≈505～535 之後、活力圖示 x≈755 之前；白字（2026-10-15 量 ui-log 截圖，位數多時往右長）
DIA_WHITE = 200                    # 白字門檻：r, g, b 都 > 這個（資源列底是深色，量過無雜點）
DIA_ZERO = ('..###..', '.#####.', '.##..##', '##...##', '##...##', '##...##', '##...##', '##...##',
            '##...##', '##...##', '##...##', '.##.##.', '.#####.')      # 單獨「0」的字形（裁邊後 7×13；ui-log/005319、111110 兩張一致）
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


def dia_from_rows(rows):
    """鑽石框白字點陣（'0'/'1' 字串列）→ 讀值（純函式）：沒有白字 → None；裁邊後剛好是 DIA_ZERO（「0」）→ '0'；
    其他 → 'px:<裁邊點陣指紋>'（不解讀數字；呼叫端只比前後是否相同）"""
    rows = [r for r in rows or []]
    ys = [i for i, r in enumerate(rows) if '1' in r]
    if not ys:
        return None
    xs = [j for r in rows for j, c in enumerate(r) if c == '1']
    x0, x1 = min(xs), max(xs)
    crop = tuple(r[x0:x1 + 1].replace('0', '.').replace('1', '#') for r in rows[ys[0]:ys[-1] + 1])
    if crop == DIA_ZERO:
        return '0'
    return 'px:' + hashlib.sha1('\n'.join(crop).encode()).hexdigest()[:12]


def read_dia_px():
    """現場讀鑽石框（一次 gui pixel，同一張截圖）→ dia_from_rows 讀值；像素讀不到 → None"""
    x, y, w, h = DIA_BOX
    cols = uikit.px([(x + i, y + j) for j in range(h) for i in range(w)])
    if not cols or len(cols) != w * h:
        return None
    rows = [''.join('1' if min(cols[j * w + i]) > DIA_WHITE else '0' for i in range(w)) for j in range(h)]
    return dia_from_rows(rows)


def read_dia_stable(read_fn, sleep_fn=None, tries: int = 3, settle: float = 0.6):
    """只讀鑽石（2026-10-15 使用者：買可抓捕數不再讀石幣；鑽石檢查保留）：連續兩次讀到同一個值才採用，
    讀不到 / 不一致 → None（呼叫端不按 / 停手，不當 0）。read_fn() → (石幣, 鑽石)，石幣不看"""
    if sleep_fn:
        sleep_fn(settle)
    prev = None
    for _ in range(tries):
        _s, dia = read_fn()
        if dia is not None and prev is not None and dia == prev:
            return dia
        prev = dia
        if sleep_fn:
            sleep_fn(0.4)
    return None


def money() -> tuple:
    """寵物面板頂部資源列 → (None, 鑽石讀值)；石幣不讀、不擋（使用者 2026-10-15）。鑽石用像素點陣（read_dia_px，不靠 OCR：鑽石 0 時 OCR 漏讀單獨的「0」）；
    讀不穩 / 面板打不開 → None（呼叫端不按、停手）。名字沿用 money（呼叫端的 money_fn）"""
    import pet
    with pet.Session(False, True) as s:
        if s.rc:
            return None, None
        return None, read_dia_stable(lambda: (None, read_dia_px()), uikit.sleep)


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
        uikit.gui('seq', f'click {PLUS_XY[0]} {PLUS_XY[1]}; wait 800', note=f'{role} 捉寵設置「+」買 1 個可抓捕數（petquest / rebirth_pets --confirm-buy-catch）')
        after = read()
        return 0, before, after
    finally:
        try:
            ass.close_panel()
        except Exception:                                          # noqa: BLE001
            pass


def _one(role, money_fn, press_fn, log, limit=None, min_before=None):
    """按一次 → (kind, msg, rc, rec | None, pressed)。保險：按前讀不到鑽石 → 不按、停手；按後讀不到 / 有變 → 停手（鐵則 3）；
    可抓捕數 +1（沒增加停）、min_before（外掛數 < 背包誘餌 → 不按）。不讀石幣、不因石幣擋（使用者 2026-10-15）"""
    _s0, d0 = money_fn()
    if d0 is None:
        return 'fail', f'{role} 按「+」前讀不到鑽石 → 不按、停手（鐵則 3：鑽石檢查要能生效）', 0, None, False
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
    _s1, d1 = money_fn()
    rec = {'role': role, 'diamond': [d0, d1]}
    if d1 is None:
        return 'fail', f'{role}「+」後讀不到鑽石（按前 {d0}）→ 無法確認鑽石沒變、停手（鐵則 3）', 0, rec, True
    if d1 != d0:
        return 'fail', f'{role}「+」後鑽石 {d0} → {d1} 有變 → 停手（鐵則 3）', 0, rec, True
    log(f'{role} 買可抓捕數 1 個：可抓捕數 {before} → {after}、鑽石 {d0} → {d1}')
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
