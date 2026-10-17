#!/usr/bin/env python3
"""小數字「像素字形」讀值（只用標準函式庫；唯讀：只經 uikit.px / uikit.spx 讀像素）。2026-10-16。

為什麼（2026-10-16 p2 卡坦 catch2 實跑）：
  - 拆分「數量輸入」框的整疊數量 20：rebirth_pets._split 用 OCR 預設參數讀成空 →「整疊數量讀不出」rc 164；
  - 外掛捉寵設置「可抓捕數」20：OCR 讀成「2」→ 按「+」後讀「前 2、後 21」→ 判非 +1 停手（已花 50,000 石幣）。
  兩個都是 Windows OCR 掉字 / 漏讀。字是遊戲固定字型、固定位置渲染，像素二值化後**字數（位數）一定讀得準**（白 / 深色字在單色底上，連通元件就是一個字）。
作法：框內依字色二值化 → digitmatch.segment 切字（只留高度在該字型範圍內的元件）→
  ① 每個字都被樣板認出（digitmatch.Matcher，IoU ±1 px）→ 直接用；
  ② 否則呼叫端給 OCR 讀值，**位數必須等於像素切出的字數**才採用（20 讀成 2 → 位數 1 ≠ 2 字 → 不採用、換參數 / 重讀），採用時順便學字（petglyph._learn_glyphs：
     已認得的字跟標籤矛盾 / 跟別的字太像就不學）；③ 都不行 → None（呼叫端不猜、停手）。
三種字型（kind）：
  qty   拆分「數量輸入」視窗的數量框白字（bag.SPLIT_QTY_BOX 670,430 170×45；字高約 19～20）
  slot  背包格右下角疊數白字（相對格心 SLOT_COUNT；字高 16～17）—— 拆分前讀一次，跟數量框交叉核對
  ass   外掛「捉寵設置」可抓捕數深色字（ASS_COUNT_BOX 1170,300 80×30；字高約 15）
  shop  便利店數量框白字（SHOP_QTY_BOX 968,450 56×32，米底；字高 19，筆畫比 qty 細 → 另一組樣板；2026-10-17 p1 每日任務 OCR 讀單一「1」全空 → 227）
現場取像素的來源（LIVE_SRC，2026-10-17 dev-shop-qty2 查 227 根因）：
  `gui pixel`（uikit.px）取的是客戶區**原生 (2x, 2y) 單點**，`gui shot` 存的是 **HighQualityBicubic 縮圖** —— 兩者點陣不同。
  種子樣板全部從截圖切 → 實機用 px 讀，字形對不上：shop 實機 4 次全 None（同一張存證圖離線讀得出 1，play-p1-dailyrun）；
  qty 的種子 03:11 就有 1、4，19:41 實機仍學了另一版 1、4（tools/.cache/num-tpl.json，字高 20 vs 種子 19）。
  shop → 'shot'：改用 uikit.spx（gui.ps1 spixel：跟 shot 同一段縮圖取色）→ 實機與截圖 / fixture 逐點相同。
  qty / slot / ass 仍 'px'（OCR 備援 + 實機學到的字在撐；要切 'shot' 得連 bag / catchbuy 實機驗證，見 dev-shop-qty2 報告）。
  label 子指令從截圖學字：只適合 LIVE_SRC = 'shot' 的 kind（px 的 kind 學了也只認得截圖字形）。
樣板：種子 tools/gui/fixtures/num_glyph_tpl.json（2026-10-16 從 tools/.cache 3056 張截圖切字、人工看點陣標籤；qty / ass 只有 0 1 2 4 5，slot 缺 3 7；
  shop 2026-10-17 從 8217 張掃出便利店畫面 165 張：只有 1〔143 張點陣完全相同〕與 3〔daily-probe/22-qty3.png〕，其他數字等實機截圖人工 label）
  + 執行中學到的 tools/.cache/num-tpl.json（OCR 位數與字數一致才學；測試環境改用暫存資料夾）。

用法（專案根目錄；唯讀）：
  uv run --no-project python tools/gui/numglyph.py read qty|ass|shop       # 現場讀一次數量框 / 可抓捕數 / 便利店數量框（只讀像素；shop 走 spixel 縮圖取色）
  uv run --no-project python tools/gui/numglyph.py read slot <格號 0 起>    # 背包格疊數
  uv run --no-project python tools/gui/numglyph.py shot <截圖.png> qty|ass|shop|slot [格號]   # 離線讀截圖
  uv run --no-project python tools/gui/numglyph.py label <截圖.png> shop 0  # 人工看過截圖的值 → 學進 tools/.cache/num-tpl.json（例：ui-log/*-shop-qty-unread.png）
程式用：read_rows(rows, kind) / read_box(kind, box) / read_number(kind, box, ocr_reads, sleep_fn) / slot_box(i) / digits_ok(n, v) / learn(rows, v, kind)
"""
import argparse
import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import digitmatch  # noqa: E402

SEED_FILE = HERE / 'fixtures' / 'num_glyph_tpl.json'
_TEST = 'psatest-' in os.environ.get('PSA_LOG_DIR', '')
LEARN_FILE = (Path(os.environ['PSA_LOG_DIR']) if _TEST else HERE.parent / '.cache') / 'num-tpl.json'

PREDS = {
    'qty': lambda c: min(c[:3]) > 200,            # 數量框白字（米色框底 223,187,147）
    'slot': lambda c: min(c[:3]) > 200,           # 背包格疊數白字（深色描邊）
    'ass': lambda c: max(c[:3]) < 110,            # 外掛面板淺灰底（221,221,219）上的深色字
    'shop': lambda c: min(c[:3]) > 200,           # 便利店數量框白字（米底；鍵盤開著時框內只剩 1 px 寬直線，字高篩掉）
}
HEIGHT = {'qty': (17, 22), 'slot': (14, 18), 'ass': (13, 17), 'shop': (16, 22)}     # 字高範圍（px）：其他高度的元件（圖示白點、框線）不算字
QTY_BOX = (670, 430, 170, 45)                     # = bag.SPLIT_QTY_BOX
ASS_COUNT_BOX = (1170, 300, 80, 30)               # 「可抓捕數:」冒號（x≈1158）之後、「+」鈕（x≥1256）之前
SHOP_QTY_BOX = (968, 450, 56, 32)                 # = shopkit.QTY_BOX（便利店數量框；「1」在 x 991～1001 × y 457～475）
BOXES = {'qty': QTY_BOX, 'ass': ASS_COUNT_BOX, 'shop': SHOP_QTY_BOX}
LIVE_SRC = {'qty': 'px', 'slot': 'px', 'ass': 'px', 'shop': 'shot'}   # 現場取像素：'px' = uikit.px 原生單點；'shot' = uikit.spx 截圖同一段縮圖（見檔頭）
SLOT_COUNT = (0, 18, 46, 28)                      # 背包格疊數框（相對格心 dx, dy, w, h；實測「21」在 cx+20～+43、cy+26～+42）
SLOT_X, SLOT_Y = [752, 860, 966, 1072, 1180], [245, 352, 460]     # = bag.SLOT_X / SLOT_Y（不 import bag：bag 會 import 本模組）


def slot_box(i: int) -> tuple:
    """背包第 i 格（0 起）疊數框 (x, y, w, h)"""
    cx, cy = SLOT_X[i % 5], SLOT_Y[i // 5]
    dx, dy, w, h = SLOT_COUNT
    return (cx + dx, cy + dy, w, h)


# ---- 樣板 ----
def _load(p: Path) -> dict:
    try:
        d = json.loads(p.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return {}
    return d if isinstance(d, dict) else {}


_TPL = None


def load_tpl(reload: bool = False) -> dict:
    """種子 + 學到的 → {kind: {字: [點陣列]}}（模組快取）"""
    global _TPL
    if _TPL is not None and not reload:
        return _TPL
    seed, learned = _load(SEED_FILE), _load(LEARN_FILE)
    out = {}
    for k in PREDS:
        book = {}
        for src in (seed, learned):
            for ch, vs in (src.get(k) or {}).items():
                book.setdefault(ch, [])
                book[ch] += [v for v in vs if v not in book[ch]]
        out[k] = book
    _TPL = out
    return out


def _save_learned(add: dict) -> None:
    d = _load(LEARN_FILE)
    for k, book in add.items():
        for ch, vs in book.items():
            cur = d.setdefault(k, {}).setdefault(ch, [])
            cur += [v for v in vs if v not in cur]
    LEARN_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = LEARN_FILE.with_suffix(f'.{os.getpid()}.tmp')
    tmp.write_text(json.dumps(d, ensure_ascii=False), encoding='utf-8')
    tmp.replace(LEARN_FILE)
    load_tpl(reload=True)


# ---- 讀（純函式）----
def binarize(cols, w: int, h: int, kind: str) -> list:
    pred = PREDS[kind]
    return [''.join('1' if pred(cols[j * w + i]) else '0' for i in range(w)) for j in range(h)]


def segs_of(rows, kind: str) -> list:
    """切字 → [(x0, y0, 點陣)]，只留字高在 HEIGHT[kind] 內的元件"""
    if not rows or not any('1' in r for r in rows):
        return []
    lo, hi = HEIGHT[kind]
    return [s for s in digitmatch.segment(rows) if lo <= len(s[2]) <= hi]


def read_rows(rows, kind: str, tpl: dict | None = None) -> dict:
    """二值列 → {'n': 字數, 'text': 每字都認出的數字串或 None, 'value': int 或 None}"""
    tpl = load_tpl() if tpl is None else tpl
    segs = segs_of(rows, kind)
    out = {'n': len(segs), 'text': None, 'value': None}
    if not segs:
        return out
    m = digitmatch.Matcher(tpl.get(kind) or {})
    s = ''
    for _, _, g in segs:
        ch, _, _ = m.classify(g)
        if ch is None or not ch.isdigit():
            return out
        s += ch
    out['text'], out['value'] = s, int(s)
    return out


def digits_ok(n: int, v) -> bool:
    """OCR 讀值 v 的位數 == 像素切出的字數 n（n 0 = 沒字 → 一律不採用）"""
    return n > 0 and v is not None and len(str(int(v))) == n


def learn(rows, value: int, kind: str, save: bool = True) -> int:
    """可信讀值（位數 == 字數）學字 → 新增幾個樣板。沿用 petglyph._learn_glyphs（已認得的字與標籤矛盾 / 與別的字太像 → 整次不學）"""
    import petglyph
    segs = segs_of(rows, kind)
    if not digits_ok(len(segs), value):
        return 0
    add = petglyph._learn_glyphs(segs, str(int(value)), kind, load_tpl())
    n = sum(len(v) for b in add.values() for v in b.values())
    if n and save:
        _save_learned(add)
    return n


# ---- 現場讀（唯讀像素）----
def live_rows(box, kind: str):
    """框內一次讀像素（LIVE_SRC：'shot' → uikit.spx 跟截圖同一段縮圖；'px' → uikit.px 原生單點）→ 二值列；讀不到 None"""
    import uikit
    x, y, w, h = box
    pts = [(x + i, y + j) for j in range(h) for i in range(w)]
    cols = uikit.spx(pts) if LIVE_SRC.get(kind) == 'shot' else uikit.px(pts)
    if not cols or len(cols) != w * h:
        return None
    return binarize(cols, w, h, kind)


def read_box(kind: str, box=None) -> dict:
    """現場讀一次 → read_rows 結果 + 'rows'（讀不到像素 → n = -1）"""
    box = box or BOXES[kind]
    rows = live_rows(box, kind)
    if rows is None:
        return {'n': -1, 'text': None, 'value': None, 'rows': None}
    r = read_rows(rows, kind)
    r['rows'] = rows
    return r


def read_number(kind: str, box=None, ocr_reads=(), sleep_fn=None, tries: int = 2, log=None) -> dict:
    """讀一個數字（最少動作：只讀像素 / OCR，不點擊）→ {'value', 'n', 'via': 'tpl' | 'ocr' | None, 'ocr': [讀過的 OCR 值]}。
    每輪：像素切字 → 樣板全認出就回；否則依序試 ocr_reads（零參數函式 → int | None），位數 == 字數才採用（順便學字）；
    都不行等 0.4 秒重讀，最多 tries 輪。仍不行 value = None（呼叫端不猜）"""
    seen = []
    last = {'value': None, 'n': -1, 'via': None, 'ocr': seen}
    for t in range(max(1, tries)):
        r = read_box(kind, box)
        last['n'] = r['n']
        if r['value'] is not None:
            return {'value': r['value'], 'n': r['n'], 'via': 'tpl', 'ocr': seen}
        if r['n'] > 0:
            for fn in ocr_reads:
                v = fn()
                seen.append(v)
                if digits_ok(r['n'], v):
                    try:
                        added = learn(r['rows'], v, kind)
                    except Exception:                               # noqa: BLE001  學字失敗不影響讀值
                        added = 0
                    if log and added:
                        log(f'numglyph：{kind} 學到 {added} 個字（讀值 {v}）')
                    return {'value': int(v), 'n': r['n'], 'via': 'ocr', 'ocr': seen}
        if t + 1 < tries and sleep_fn:
            sleep_fn(0.4)
    if log:
        log(f'numglyph：{kind} 讀不出（像素 {last["n"]} 字、OCR {seen} 位數不合）→ 不採用')
    return last


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description='小數字像素字形讀值（唯讀）')
    sub = ap.add_subparsers(dest='cmd', required=True)
    r = sub.add_parser('read')
    r.add_argument('kind', choices=sorted(PREDS))
    r.add_argument('slot', nargs='?', type=int, default=0)
    s = sub.add_parser('shot')
    s.add_argument('png')
    s.add_argument('kind', choices=sorted(PREDS))
    s.add_argument('slot', nargs='?', type=int, default=0)
    lb = sub.add_parser('label', help='人工確認截圖框內的數值 → 學字（位數須 = 像素字數；與已認得的字矛盾 / 太像別的字就不學）')
    lb.add_argument('png')
    lb.add_argument('kind', choices=sorted(PREDS))
    lb.add_argument('value', type=int)
    lb.add_argument('slot', nargs='?', type=int, default=0)
    a = ap.parse_args(argv)
    box = slot_box(a.slot) if a.kind == 'slot' else BOXES[a.kind]
    if a.cmd == 'read':
        import winenv
        winenv.enable_server()
        res = read_box(a.kind, box)
        res.pop('rows', None)
    else:
        import imgmatch
        get = imgmatch.as_getter(a.png)
        x, y, w, h = box
        rows = binarize([get(x + i, y + j) for j in range(h) for i in range(w)], w, h, a.kind)
        res = read_rows(rows, a.kind)
        if a.cmd == 'label':
            res['learned'] = learn(rows, a.value, a.kind)
    print(json.dumps(res, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    sys.exit(main())
