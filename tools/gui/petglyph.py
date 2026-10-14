#!/usr/bin/env python3
"""寵物面板 / 倉庫卡的「字形樣板」讀字（只用標準函式庫；唯讀：只經 uikit.px 讀像素，capture 只點頭像 / 分頁 / 選格）。2026-10-14。

為什麼（2026-10-14 恐龍博士 / 卡坦實跑）：
  - 名字框的成長字串 OCR 會讀錯：40/9/6/5 在 2 / 4 倍讀成「姍/9/6/5」、殘行「65」、「49/>」「49/14」（DKBO5 49/10/8/1 實機讀不出）；
    每格 OCR 2～3 組設定 + 讀不出時等 EXP 橫幅重讀 2 次 ≈ 2.5～4.5 秒 → 5 隻的人 list 約 11 秒。
  - 倉庫卡綠字等級 OCR 掉百位（123 → 23）、讀不出。
  - 倉庫分頁「選卡讀名字框」在快戰掛機中不可靠：**戰鬥結束時面板刷新，選取會跳回寵物欄第 1 格**（2026-10-14 實機：選卡 1.4～2 秒後
    sel 全空、名字框變回 46/9/7/1、按鈕變回「存入寵物」），所以逐張選卡讀名字框會讀到別隻。卡片自己上面就有白字名字 / 成長字串、下面綠字等級。
作法：遊戲的字是固定字型、固定位置渲染 → 依字色二值化（半解析度 = gui pixel 截圖座標）→ digitmatch.segment 切字 → 單字樣板（digitmatch.Matcher，
  IoU ±1 px）。成長字串只有 0～9 與「/」11 種字；綠字等級只收數字（「轉」「級」用高度分辨，不需樣板）；倉庫卡名字用整塊圖樣板（petmatch.pack / iou）。
  任何一個字認不出 / 兩候選太近 / 字串置中位置不對（被橫幅蓋掉一個字會偏 6 px 以上）/ 格式不是 a/b/c/d → None，呼叫端退回 OCR（不猜）。

三種字色（kind）：
  cream  名字框（430,160 200×45；寵物分頁 = 選中寵物、倉庫分頁 = 選中的寵物或卡）奶油色字，同 petmatch.PREDS['name']
  white  倉庫卡上緣白字（名字 / 成長字串；相對卡心 CARD_TEXT）
  green  倉庫卡下緣綠字「0轉N級」（相對卡心 CARD_LVL）
樣板：種子 tools/gui/fixtures/pet_glyph_tpl.json（2026-10-14 實機擷取 + 人工核對標籤，`build` 產生，進 git）+
  執行中學到的 tools/.cache/pet-tpl/glyph-<版面>.json（OCR ≥ 2 行同意的成長字串 / 等級，且已認得的字都不矛盾才學；種子缺的字：cream / white 的 3、green 的 4 5 6）。

用法（專案根目錄）：
  uv run --no-project python tools/gui/petglyph.py read [--depot]           # 唯讀：讀現在的名字框（+ 倉庫分頁時全部卡片），不點擊
  uv run --no-project python tools/gui/petglyph.py capture [--role all] [--depot public,personal] [--ocr]   # 唯讀擷取樣本（開寵物面板、點頭像 / 格 / 分頁，不存取）
  uv run --no-project python tools/gui/petglyph.py build <labels.json> <capture.json>...   # 由人工標籤建種子樣板（寫 fixtures/pet_glyph_tpl.json）
  uv run --no-project python tools/gui/petglyph.py eval <labels.json> <capture.json>...    # 樣本正確率 / 耗時（字形 vs 擷取時的 OCR）
  uv run --no-project python tools/gui/petglyph.py fixture <labels.json> <capture.json>... # 重產測試樣本 fixtures/petglyph_samples.json（二值點陣）
  labels.json：{"slot": {"DKBO:1": "46/9/7/1", ...}, "card": {"DKBO:personal:5": "#46/9/8/2@127", "DKBO:public:1": "巴朵蘭恩@1", ...}}
程式用：read_growth(rows, kind) / read_card_level(rows) / read_cards(empty) / card_ident_text(card) / learn_growth / learn_card_level
"""
import argparse
import json
import re
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import digitmatch  # noqa: E402
import petmatch  # noqa: E402
import uikit  # noqa: E402

SEED_FILE = HERE / 'fixtures' / 'pet_glyph_tpl.json'
CAP_DIR = uikit.CACHE / 'petident' / 'samples'

PREDS = {
    'cream': petmatch.PREDS['name'],                                   # 奶油色字 ≈ (240,224,128)
    'white': lambda c: min(c) > 200,                                   # 卡片白字（深色描邊）
    'green': lambda c: c[1] > 170 and c[0] < 170 and c[2] < 140,       # 卡片綠字（同 petimg_match._text_px）
}
CARD_X = [818, 924, 1030, 1136, 1242]          # 同 pet.CARD_X / CARD_Y（不 import pet：pet 會 import 本模組）
CARD_Y = [275, 381, 488, 594]
CARD_TEXT = (-52, -41, 104, 25)                # 卡片上緣白字框（相對卡心；2026-10-14 實機：字在 cy-38～cy-19）
CARD_LVL = (-52, 16, 104, 28)                  # 卡片下緣綠字框（字在 cy+21～cy+40）
CENTER = {'cream': 102.0, 'white': 52.0, 'green': 52.0}    # 字串置中的 x（框內座標；實測 cream 102～102.5、white / green 52～53）
CENTER_TOL = 3.0                               # 被蓋掉一個字（寬 8～12 px）置中會偏 ≥ 4 px
GROWTH_CHARS = set('0123456789/')
MAX_VARIANTS = 6
KNOWN_IOU = 0.93                               # 學字時：已被同字以此分數認出就不再存
NAME_HIT, NAME_MARGIN = 0.90, 0.06             # 卡片名字整塊圖：門檻 / 與次佳別名差距（同名實測 ≥ 0.97）
MIN_NAME_INK = 120
LVL_TALL = 18                                  # 綠字：高度 ≥ 這個的是「轉」「級」（數字高 15）
_TPL: dict | None = None


def log(msg: str) -> None:
    print(f'petglyph：{msg}', file=sys.stderr)


# ---- 樣板 ----
def _load(p: Path) -> dict:
    try:
        d = json.loads(p.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return {}
    return d if isinstance(d, dict) else {}


def load_tpl(reload: bool = False) -> dict:
    """種子 + 學到的 → {'cream': {字: [點陣]}, 'white': {...}, 'green': {...}, 'card_name': {名字: [hex]}}（模組快取）"""
    global _TPL
    if _TPL is not None and not reload:
        return _TPL
    seed, learned = _load(SEED_FILE), _load(learn_file())
    out = {}
    for k in ('cream', 'white', 'green', 'card_name'):
        book = {}
        for src in (seed, learned):
            for ch, vs in (src.get(k) or {}).items():
                book.setdefault(ch, [])
                book[ch] += [v for v in vs if v not in book[ch]]
        out[k] = book
    _TPL = out
    return out


def learn_file() -> Path:
    """學到的字形檔（跟著 petmatch.TPL_DIR：測試換成暫存資料夾就不碰 tools/.cache）"""
    return petmatch.TPL_DIR / f'glyph-{petmatch.LAYOUT}.json'


def save_learned(tpl_add: dict) -> None:
    """tpl_add 的條目併進學習檔（種子不動）"""
    LEARN_FILE = learn_file()
    d = _load(LEARN_FILE)
    for k, book in tpl_add.items():
        for ch, vs in book.items():
            cur = d.setdefault(k, {}).setdefault(ch, [])
            cur += [v for v in vs if v not in cur]
    LEARN_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = LEARN_FILE.with_suffix('.tmp')
    tmp.write_text(json.dumps(d, ensure_ascii=False), encoding='utf-8')
    tmp.replace(LEARN_FILE)
    load_tpl(reload=True)


_MATCHERS: dict = {}


def matcher(kind: str, tpl: dict | None = None) -> digitmatch.Matcher:
    tpl = tpl if tpl is not None else load_tpl()
    key = (kind, id(tpl), sum(len(v) for v in (tpl.get(kind) or {}).values()))
    if key not in _MATCHERS:
        _MATCHERS[key] = digitmatch.Matcher(tpl.get(kind) or {})
    return _MATCHERS[key]


# ---- 二值化 / 切字 ----
def binarize(cols, w: int, h: int, kind: str) -> list:
    pred = PREDS[kind]
    return [''.join('1' if pred(cols[j * w + i]) else '0' for i in range(w)) for j in range(h)]


def segs_of(rows) -> list:
    return digitmatch.segment(rows) if rows and any('1' in r for r in rows) else []


GAP_MAX = 5                                    # 相鄰字距上限（2026-10-14 實機 cream 2～3、white 1～3、green -2～3 px）：中間被蓋掉一個字會空出 ≥ 10 px


def tight(segs) -> bool:
    """字與字之間沒有空洞（中間的字被橫幅 / 浮字蓋掉時置中不變、格式可能仍合法：49/10/8/1 → 49/1/8/1）"""
    return all(b[0] - (a[0] + len(a[2][0])) <= GAP_MAX for a, b in zip(segs, segs[1:]))


def centered(segs, kind: str) -> bool:
    """字串置中位置對不對（被 EXP 橫幅 / 浮字蓋掉頭或尾一個字 → 偏 ≥ 4 px）"""
    if not segs:
        return False
    x0, x1 = segs[0][0], segs[-1][0] + len(segs[-1][2][0]) - 1
    return abs((x0 + x1) / 2 - CENTER[kind]) <= CENTER_TOL


def classify_all(segs, kind: str, tpl: dict | None = None) -> list:
    m = matcher(kind, tpl)
    return [m.classify(g) for _, _, g in segs]


GROWTH_RE = petmatch.GROWTH_RE


def read_growth(rows, kind: str = 'cream', tpl: dict | None = None, info: dict | None = None) -> str | None:
    """名字框 / 卡片白字的成長字串 → 'a/b/c/d'（正規化）或 None（有字認不出 / 不置中 / 格式不符 / 數字高度不一致）"""
    segs = segs_of(rows)
    if not 7 <= len(segs) <= 15 or not centered(segs, kind) or not tight(segs):
        return None
    res = classify_all(segs, kind, tpl)
    if info is not None:
        info['glyphs'] = [(c, round(s, 3)) for c, s, _ in res]
    if any(c is None or c not in GROWTH_CHARS for c, _, _ in res):
        return None
    hs = [len(g) for (_, _, g), (c, _, _) in zip(segs, res) if c != '/']
    if max(hs) - min(hs) > 2:
        return None
    m = GROWTH_RE.match(''.join(c for c, _, _ in res))
    return '/'.join(str(int(x)) for x in m.groups()) if m else None


def level_parts(segs) -> tuple | None:
    """綠字「R轉N級」切字 → (轉前數字 segs, 等級數字 segs) 或 None（結構不對）。高 ≥ LVL_TALL 的是「轉」「級」（級 可能切成 2 塊）"""
    tall = [len(g) >= LVL_TALL for _, _, g in segs]
    if True not in tall:
        return None
    i = tall.index(True)                                   # 「轉」
    j = next((k for k in range(i + 1, len(segs)) if tall[k]), None)   # 「級」第一塊
    if i == 0 or j is None or not 1 <= j - i - 1 <= 3:
        return None
    return segs[:i], segs[i + 1:j]


def read_card_level(rows, tpl: dict | None = None, info: dict | None = None) -> int | None:
    """卡片綠字 → 等級 int 或 None。轉數與等級的數字都要認得（只收 0～9）、置中、1～140"""
    segs = segs_of(rows)
    if len(segs) < 4 or not centered(segs, 'green') or not tight(segs):
        return None
    parts = level_parts(segs)
    if not parts:
        return None
    pre, lv = parts
    res = classify_all(pre + lv, 'green', tpl)
    if info is not None:
        info['glyphs'] = [(c, round(s, 3)) for c, s, _ in res]
    if any(c is None or not c.isdigit() for c, _, _ in res):
        return None
    v = int(''.join(c for c, _, _ in res[len(pre):]))
    return v if 1 <= v <= 140 else None


def read_card_name(rows, tpl: dict | None = None) -> tuple:
    """卡片白字整塊圖 → (名字或 None, 最佳分, 次佳別名分)；名字樣板以整條白字框（104×25）為單位"""
    tpl = tpl if tpl is not None else load_tpl()
    book = tpl.get('card_name') or {}
    if not rows or petmatch.ink(rows) < MIN_NAME_INK or not book:
        return None, 0.0, 0.0
    stride = len(rows[0]) + 2 * petmatch.PAD
    img = petmatch.pack(rows)
    best = {}
    for label, vs in book.items():
        for h in vs:
            s = petmatch.iou(img, int(h, 16), stride)
            best[label] = max(best.get(label, 0.0), s)
    rk = sorted(best.items(), key=lambda kv: -kv[1])
    sc, second = rk[0][1], (rk[1][1] if len(rk) > 1 else 0.0)
    if sc < NAME_HIT or sc - second < NAME_MARGIN:
        return None, sc, second
    return rk[0][0], sc, second


# ---- 學字（執行中；呼叫端給可信標籤：OCR ≥ 2 行同意）----
def _learn_glyphs(segs, labels: str, kind: str, tpl: dict) -> dict:
    """segs 與 labels 一一對應；已認得的字有任何一個跟標籤不同 → 整次不學（標籤可疑）。回傳要新增的 {kind: {字: [點陣]}}"""
    if len(segs) != len(labels):
        return {}
    res = classify_all(segs, kind, tpl)
    if any(c is not None and c != want for (c, _, _), want in zip(res, labels)):
        return {}
    add: dict = {}
    m = matcher(kind, tpl)
    for (_, _, g), want, (c, s, _) in zip(segs, labels, res):
        if c == want and s >= KNOWN_IOU:
            continue
        cur = (tpl.get(kind) or {}).get(want, []) + add.get(kind, {}).get(want, [])
        if len(cur) >= MAX_VARIANTS:
            continue
        v, w, h, n = digitmatch.glyph_int(g)
        clash = [ch for ch, tv, tw, th, tn in m.items if ch != want and abs(tw - w) <= 3 and abs(th - h) <= 3
                 and digitmatch.iou(v, n, tv, tn) >= digitmatch.HIT_MIN]
        if clash:                                       # 這個字形跟別的字的樣板太像 → 學了會打架，不學
            return {}
        add.setdefault(kind, {}).setdefault(want, []).append(g)
    return add


def learn_growth(rows, growth: str, kind: str = 'cream', save: bool = True) -> int:
    """成長字串 growth（可信：OCR ≥ 2 行同意）對名字框 / 卡片白字點陣學單字樣板 → 新增幾個（0 = 不學 / 已認得）"""
    segs = segs_of(rows)
    if not GROWTH_RE.match(growth or '') or not centered(segs, kind) or not tight(segs):
        return 0
    add = _learn_glyphs(segs, growth, kind, load_tpl())
    if add and save:
        save_learned(add)
    return sum(len(v) for b in add.values() for v in b.values())


def learn_card_level(rows, level: int, save: bool = True) -> int:
    """卡片綠字等級（可信：OCR ≥ 2 行同意）→ 學「等級」那幾個數字（轉數不學：沒有標籤）"""
    segs = segs_of(rows)
    parts = level_parts(segs) if centered(segs, 'green') and tight(segs) else None
    if not parts:
        return 0
    add = _learn_glyphs(parts[1], str(int(level)), 'green', load_tpl())
    if add and save:
        save_learned(add)
    return sum(len(v) for b in add.values() for v in b.values())


def learn_card_name(rows, name: str, save: bool = True) -> bool:
    """卡片白字整塊圖學成名字樣板（名字要可信：選卡後名字框樣板 / OCR 精確命中）。別的名字也像 → 不學"""
    if not name or uikit.is_name_fragment(name) or not rows or petmatch.ink(rows) < MIN_NAME_INK:
        return False
    tpl = load_tpl()
    stride = len(rows[0]) + 2 * petmatch.PAD
    img = petmatch.pack(rows)
    book = tpl.get('card_name') or {}
    for other, vs in book.items():
        if other != name and any(petmatch.iou(img, int(h, 16), stride) >= NAME_HIT for h in vs):
            return False
    vs = book.get(name, [])
    if len(vs) >= MAX_VARIANTS or any(petmatch.iou(img, int(h, 16), stride) >= petmatch.DUP_IOU for h in vs):
        return False
    if save:
        save_learned({'card_name': {name: [format(img, 'x')]}})
    return True


# ---- 倉庫卡（不選卡，一次 pixel 讀全部）----
def card_box(idx: int, rel) -> tuple:
    dx, dy, w, h = rel
    return CARD_X[idx % 5] + dx, CARD_Y[idx // 5] + dy, w, h


def card_points(idxs) -> list:
    pts = []
    for k in idxs:
        for rel in (CARD_TEXT, CARD_LVL):
            x, y, w, h = card_box(k, rel)
            pts.extend((x + i, y + j) for j in range(h) for i in range(w))
    return pts


def parse_cards(idxs, cols, tpl: dict | None = None) -> list:
    """card_points(idxs) 讀到的顏色 → [{'index'(1 起), 'name', 'growth', 'level', 'text_rows', 'lvl_rows', 'name_score'}]"""
    out, k = [], 0
    tw, th = CARD_TEXT[2], CARD_TEXT[3]
    lw, lh = CARD_LVL[2], CARD_LVL[3]
    for i in idxs:
        trow = binarize(cols[k:k + tw * th], tw, th, 'white')
        k += tw * th
        lrow = binarize(cols[k:k + lw * lh], lw, lh, 'green')
        k += lw * lh
        g = read_growth(trow, 'white', tpl)
        nm, sc, _ = (None, 0.0, 0.0) if g else read_card_name(trow, tpl)
        out.append({'index': i + 1, 'name': nm, 'growth': g, 'level': read_card_level(lrow, tpl),
                    'text_rows': trow, 'lvl_rows': lrow, 'name_score': round(sc, 3)})
    return out


def read_cards(empty=None, tpl: dict | None = None) -> list | None:
    """倉庫分頁開著時：非空卡（empty = pet.scan_depot()['empty']；None = 全部 20 張）一次讀字 → parse_cards；讀不到像素 None。
    12 張約 0.9 s（常駐 server）。只讀不點，不受「戰鬥結束選取跳回」影響"""
    idxs = [i for i in range(20) if empty is None or not empty[i]]
    if not idxs:
        return []
    cols = uikit.px(card_points(idxs))
    return parse_cards(idxs, cols, tpl) if cols else None


def card_ident_text(c: dict) -> dict:
    """read_cards 的一張 → pet.resolve_ident 同格式的身分 dict（via 'card-glyph'）；都讀不出 → name / growth 皆 None"""
    return {'name': c.get('name'), 'via': 'card-glyph' if (c.get('name') or c.get('growth')) else None,
            'raw': None, 'growth': c.get('growth')}


# ---- 擷取樣本（唯讀；只開面板、點頭像 / 寵物格 / 倉庫分頁）----
def _raw(box) -> dict | None:
    x, y, w, h = box
    t = time.time()
    cols = uikit.px([(x + i, y + j) for j in range(h) for i in range(w)])
    if cols is None:
        return None
    return {'box': list(box), 'rows': [''.join('%02x%02x%02x' % c for c in cols[j * w:(j + 1) * w]) for j in range(h)],
            'ms': int((time.time() - t) * 1000)}


OCR_SET = [('-Dark', 0, '-Zooms', '2'), ('-Dark', 0, '-Zooms', '3'), ('-Dark', 0, '-Zooms', '4'), ('-Dark', 0, '-Zooms', '5,6'),
           ('-Dark', 120, '-Zooms', '2,3'), ('-Light', 150, '-Zooms', '2,3')]
CARD_OCR_SET = [('-Light', 200, '-Zooms', '2,3'), ('-Light', 150, '-Zooms', '2,3,4'), ('-Dark', 0, '-Zooms', '2,3,4')]


def _ocr_all(box, opts_list) -> dict:
    import petwatch
    out = {}
    for o in opts_list:
        t = time.time()
        out[' '.join(map(str, o))] = [petwatch.ocr(box, *o), int((time.time() - t) * 1000)]
    return out


def capture(roles, depots, with_ocr: bool = False) -> int:
    """唯讀擷取：每人寵物欄每格（名字框 / 等級 / 縮圖原始像素 + 現行 pet.read_slot 結果與耗時）、倉庫頁（不選卡，整頁 3 次）。
    存 tools/.cache/petident/samples/cap-<時間>.json"""
    import pet
    import winenv
    winenv.enable_server()
    ctx = pet.load_ctx(False)
    samples = []
    with pet.Session(False) as s:
        if s.rc:
            return s.rc
        first_public = True
        for r in roles:
            rc = pet.select_role(r, ctx)
            if rc:
                return rc
            f = pet.scan_frames()
            for i in range(5):
                if f['empty'][i]:
                    continue
                rc = pet.select_slot(i, f)
                if rc:
                    return rc
                uikit.sleep(0.4)
                d = {'kind': 'slot', 'role': r, 'idx': i + 1, 'name': _raw(petmatch.BOX_NAME), 'lvl': _raw(petmatch.BOX_LVL),
                     'cell': _raw((pet.SLOT_X - 50, pet.SLOT_Y[i] - 50, 100, 100))}
                t = time.time()
                d['pipe'] = pet.read_slot(i, dict(ctx, use_icache=False))
                d['pipe_ms'] = int((time.time() - t) * 1000)
                if with_ocr:
                    d['ocr'] = _ocr_all(petmatch.BOX_NAME, OCR_SET)
                samples.append(d)
                log(f'{r} 格 {i + 1}：{d["pipe"].get("name") or d["pipe"].get("raw_name")} {d["pipe_ms"]} ms')
                f = pet.scan_frames() or f
            for dep in depots:
                if dep == 'public' and not first_public:
                    continue
                rc, dd = pet.open_depot(dep)
                if rc:
                    return rc
                for rep in range(3):
                    samples.append({'kind': 'depot_page', 'role': r, 'depot': dep, 'rep': rep, 'page': _raw((760, 220, 540, 420)),
                                    'empty': dd['empty']})
                    uikit.sleep(1.0)
                if with_ocr:
                    for k in range(20):
                        if not dd['empty'][k]:
                            samples.append({'kind': 'card_ocr', 'role': r, 'depot': dep, 'idx': k + 1,
                                            'ocr': _ocr_all(card_box(k, CARD_TEXT), CARD_OCR_SET)})
                if dep == 'public':
                    first_public = False
            if depots and not pet.goto_pet_tab():
                return pet.EXIT_PANEL
    CAP_DIR.mkdir(parents=True, exist_ok=True)
    p = CAP_DIR / f'cap-{time.strftime("%m%d-%H%M%S")}.json'
    p.write_text(json.dumps(samples, ensure_ascii=False, default=str), encoding='utf-8')
    print(json.dumps({'ok': True, 'rc': 0, 'file': str(p), 'n': len(samples)}, ensure_ascii=False))
    return 0


# ---- 離線：樣本 → 點陣 ----
def _hex_cols(rows_hex) -> list:
    return [tuple(int(r[k * 6 + c * 2:k * 6 + c * 2 + 2], 16) for c in range(3)) for r in rows_hex for k in range(len(r) // 6)]


def sample_name_rows(s: dict) -> list:
    b = s['name']
    return binarize(_hex_cols(b['rows']), b['box'][2], b['box'][3], 'cream')


def page_card_rows(page: dict, idx: int) -> tuple:
    """整頁原始像素（760,220 540×420）→ 第 idx 張卡的 (白字點陣, 綠字點陣)"""
    ox, oy = page['box'][0], page['box'][1]
    out = []
    for rel, kind in ((CARD_TEXT, 'white'), (CARD_LVL, 'green')):
        x, y, w, h = card_box(idx, rel)
        cols = [tuple(int(page['rows'][y + j - oy][(x + i - ox) * 6 + c * 2:(x + i - ox) * 6 + c * 2 + 2], 16) for c in range(3))
                for j in range(h) for i in range(w)]
        out.append(binarize(cols, w, h, kind))
    return tuple(out)


def parse_label(t: str) -> dict:
    """'#46/9/8/2@127' / '摩娜西普@1' / '46/9/7/1' → {'name', 'growth', 'level'}"""
    m = re.match(r'^(?:#?(?P<g>\d+/\d+/\d+/\d+)|(?P<n>[^@#]+))?(?:@(?P<l>\d+))?$', t)
    return {'name': m['n'], 'growth': m['g'], 'level': int(m['l']) if m['l'] else None} if m else {}


def labeled(labels: dict, caps) -> list:
    """→ [(種類 'slot'/'card', 鍵, 標籤 dict, 白字或名字框點陣, 綠字點陣或 None, 樣本)]"""
    out = []
    for s in caps:
        if s['kind'] == 'slot' and s.get('name'):
            lab = (labels.get('slot') or {}).get(f'{s["role"]}:{s["idx"]}')
            if lab:
                out.append(('slot', f'{s["role"]}:{s["idx"]}', parse_label(lab), sample_name_rows(s), None, s))
        elif s['kind'] == 'depot_page' and s.get('page'):
            for k in range(20):
                if s['empty'][k]:
                    continue
                key = f'{s["role"]}:{s["depot"]}:{k + 1}'
                lab = (labels.get('card') or {}).get(key)
                if lab:
                    tr, lr = page_card_rows(s['page'], k)
                    out.append(('card', key, parse_label(lab), tr, lr, s))
    return out


def build(labels: dict, caps) -> dict:
    """人工標籤 → 種子樣板（每字最多 MAX_VARIANTS 個不重複變體；名字整塊圖）。只用置中、字數對得上的樣本"""
    tpl = {'cream': {}, 'white': {}, 'green': {}, 'card_name': {}}

    def add(kind, segs, text):
        if len(segs) != len(text):
            return
        for (_, _, g), ch in zip(segs, text):
            vs = tpl[kind].setdefault(ch, [])
            v, _, _, n = digitmatch.glyph_int(g)
            dup = False
            for o in vs:
                ov, _, _, on = digitmatch.glyph_int(o)
                dup = dup or digitmatch.iou(v, n, ov, on) >= digitmatch.SAME_IOU
            if len(vs) < MAX_VARIANTS and not dup:
                vs.append(g)
    for kind_, key, lab, rows, lrows, s in labeled(labels, caps):
        if kind_ == 'slot':
            segs = segs_of(rows)
            if lab.get('growth') and centered(segs, 'cream'):
                add('cream', segs, lab['growth'])
            continue
        segs = segs_of(rows)
        if lab.get('growth') and centered(segs, 'white'):
            add('white', segs, lab['growth'])
        elif lab.get('name') and petmatch.ink(rows) >= MIN_NAME_INK:
            img = petmatch.pack(rows)
            stride = len(rows[0]) + 2 * petmatch.PAD
            vs = tpl['card_name'].setdefault(lab['name'], [])
            if len(vs) < MAX_VARIANTS and not any(petmatch.iou(img, int(h, 16), stride) >= petmatch.DUP_IOU for h in vs):
                vs.append(format(img, 'x'))
        if lab.get('level') and lrows:
            ls = segs_of(lrows)
            parts = level_parts(ls) if centered(ls, 'green') else None
            if parts:
                add('green', parts[1], str(lab['level']))
    return tpl


def evaluate(labels: dict, caps, tpl: dict | None = None) -> dict:
    """樣本正確率：每類 {'n', 'ok', 'none', 'wrong', 'ms'}（字形）；slot 另列擷取時的現行 pipeline 與 OCR 各設定"""
    tpl = tpl if tpl is not None else load_tpl()
    st: dict = {}

    def bump(cat, got, want, ms=0.0, extra=None):
        d = st.setdefault(cat, {'n': 0, 'ok': 0, 'none': 0, 'wrong': 0, 'ms': 0.0, 'bad': []})
        d['n'] += 1
        d['ms'] += ms
        if got == want:
            d['ok'] += 1
        elif got is None:
            d['none'] += 1
        else:
            d['wrong'] += 1
        if got != want:
            d['bad'].append([extra, got, want])
    for kind_, key, lab, rows, lrows, s in labeled(labels, caps):
        t = time.perf_counter()
        if kind_ == 'slot':
            bump('slot_glyph', read_growth(rows, 'cream', tpl), lab.get('growth'), (time.perf_counter() - t) * 1000, key)
            p = s.get('pipe') or {}
            bump('slot_pipeline', p.get('unnamed'), lab.get('growth'), s.get('pipe_ms', 0), key)
            for o, (lines, ms) in (s.get('ocr') or {}).items():
                bump(f'slot_ocr[{o}]', petmatch.parse_growth(lines + lines), lab.get('growth'), ms, key)
            continue
        if lab.get('growth'):
            bump('card_growth_glyph', read_growth(rows, 'white', tpl), lab['growth'], (time.perf_counter() - t) * 1000, key)
        else:
            nm, _, _ = read_card_name(rows, tpl)
            bump('card_name_glyph', nm, lab.get('name'), (time.perf_counter() - t) * 1000, key)
        t = time.perf_counter()
        if lab.get('level') is not None:
            bump('card_level_glyph', read_card_level(lrows, tpl), lab['level'], (time.perf_counter() - t) * 1000, key)
    for d in st.values():
        d['ms'] = round(d['ms'] / max(1, d['n']), 2)
        d['bad'] = d['bad'][:12]
    return st


def card_ocr_eval(labels: dict, caps) -> dict:
    """擷取時對卡片白字框跑的 OCR（card_ocr 樣本）vs 標籤：成長字串用 parse_growth、名字要精確命中"""
    st: dict = {}
    for s in caps:
        if s['kind'] != 'card_ocr':
            continue
        lab = (labels.get('card') or {}).get(f'{s["role"]}:{s["depot"]}:{s["idx"]}')
        if not lab:
            continue
        lab = parse_label(lab)
        for o, (lines, ms) in s['ocr'].items():
            d = st.setdefault(o, {'n': 0, 'ok': 0, 'ms': 0})
            d['n'] += 1
            d['ms'] += ms
            if lab.get('growth'):
                d['ok'] += petmatch.parse_growth(lines + lines) == lab['growth']
            else:
                d['ok'] += any(re.sub(r'[^一-鿿]', '', t) == lab['name'] for t in lines)
    for d in st.values():
        d['ms'] = round(d['ms'] / max(1, d['n']))
    return st


SAMPLES_FILE = HERE / 'fixtures' / 'petglyph_samples.json'


def make_fixture(labels: dict, caps) -> dict:
    """測試用精簡樣本（二值點陣 + 標籤）：每個不同的成長字串 / 名字 / 等級各留 1～2 份，另留被橫幅蓋住的名字框（應讀 None）"""
    out = {'cream': [], 'white': [], 'name': [], 'green': [], 'cream_none': []}
    seen = set()
    for kind_, key, lab, rows, lrows, s in labeled(labels, caps):
        if kind_ == 'slot':
            if lab.get('growth') and read_growth(rows, 'cream') is None and len(out['cream_none']) < 3:
                out['cream_none'].append({'key': key, 'want': lab['growth'], 'rows': rows})
            elif lab.get('growth') and ('c', lab['growth']) not in seen and read_growth(rows, 'cream') == lab['growth']:
                seen.add(('c', lab['growth']))
                out['cream'].append({'key': key, 'want': lab['growth'], 'rows': rows})
            continue
        if lab.get('growth') and ('w', lab['growth']) not in seen and read_growth(rows, 'white') == lab['growth']:
            seen.add(('w', lab['growth']))
            out['white'].append({'key': key, 'want': lab['growth'], 'rows': rows})
        elif lab.get('name') and ('n', lab['name']) not in seen and read_card_name(rows)[0] == lab['name']:
            seen.add(('n', lab['name']))
            out['name'].append({'key': key, 'want': lab['name'], 'rows': rows})
        if lab.get('level') and ('g', lab['level']) not in seen and read_card_level(lrows) == lab['level']:
            seen.add(('g', lab['level']))
            out['green'].append({'key': key, 'want': lab['level'], 'rows': lrows})
    return out


def _load_caps(paths) -> list:
    caps = []
    for p in paths:
        caps += json.loads(Path(p).read_text(encoding='utf-8'))
    return caps


def read_live(depot: bool) -> int:
    """唯讀：現在的名字框（+ 倉庫分頁時全部卡片）"""
    import winenv
    winenv.enable_server()
    t = time.time()
    rows, _ = petmatch.grab([petmatch.BOX_NAME + ('name',)])
    out = {'name_box': read_growth(rows[0], 'cream') if rows else None, 'ms_name': int((time.time() - t) * 1000)}
    if depot:
        import pet
        d = pet.scan_depot()
        if d and d['sig']:
            t = time.time()
            cards = read_cards(d['empty']) or []
            out['cards'] = [{k: v for k, v in c.items() if not k.endswith('_rows')} for c in cards]
            out['ms_cards'] = int((time.time() - t) * 1000)
    print(json.dumps(dict(out, ok=True, rc=0), ensure_ascii=False))
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description='寵物面板 / 倉庫卡字形樣板讀字')
    sub = ap.add_subparsers(dest='cmd', required=True)
    a = sub.add_parser('read')
    a.add_argument('--depot', action='store_true')
    c = sub.add_parser('capture')
    c.add_argument('--role', default='all')
    c.add_argument('--depot', default='')
    c.add_argument('--ocr', action='store_true')
    for n in ('build', 'eval', 'fixture'):
        b = sub.add_parser(n)
        b.add_argument('labels')
        b.add_argument('caps', nargs='+')
    args = ap.parse_args(argv)
    if args.cmd == 'read':
        return read_live(args.depot)
    if args.cmd == 'capture':
        import pet
        roles = pet.role_list(args.role)
        if not roles:
            return uikit.EXIT_USAGE
        return capture(roles, [d for d in args.depot.split(',') if d], args.ocr)
    labels = json.loads(Path(args.labels).read_text(encoding='utf-8'))
    caps = _load_caps(args.caps)
    if args.cmd == 'build':
        tpl = build(labels, caps)
        SEED_FILE.write_text(json.dumps(tpl, ensure_ascii=False, separators=(',', ':')), encoding='utf-8')
        print(json.dumps({'ok': True, 'rc': 0, 'file': str(SEED_FILE),
                          'chars': {k: {ch: len(v) for ch, v in b.items()} for k, b in tpl.items()}}, ensure_ascii=False))
        return 0
    if args.cmd == 'fixture':
        fx = make_fixture(labels, caps)
        SAMPLES_FILE.write_text(json.dumps(fx, ensure_ascii=False, separators=(',', ':')), encoding='utf-8')
        print(json.dumps({'ok': True, 'rc': 0, 'file': str(SAMPLES_FILE), 'n': {k: len(v) for k, v in fx.items()}}, ensure_ascii=False))
        return 0
    res = evaluate(labels, caps)
    res['card_ocr'] = card_ocr_eval(labels, caps)
    print(json.dumps(res, ensure_ascii=False, indent=1))
    return 0


if __name__ == '__main__':
    sys.exit(main())
