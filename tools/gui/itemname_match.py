#!/usr/bin/env python3
"""背包 / 倉庫道具格「名字圖」整名樣板比對（只用標準函式庫；唯讀：只讀截圖，不點擊）。2026-10-14。

為什麼：itemimg_match（縮圖）只認得到 imageId，大多數道具同圖多名（巴巴洛的許可證那張圖有 109 個名字、風的鎖 8 個），
名稱 OCR 又會讀錯 / 漏字。遊戲開「顯示道具名」時每格上半有白字名字（深色描邊，可能兩行：「巴巴洛的許 / 可證」「火的羽毛飾 / 品[火]」），
字型、位置、換行都是固定渲染 → 同一個道具在**同一欄**的格子每次的白字點陣都一樣（離線 tools/.cache 138 張截圖 1,231 格：同欄同名 IoU = 1.000）。
注意：截圖是客戶區縮半，各欄格心的半像素相位不同 → 同名換一欄只剩 IoU 0.65～0.9（不同名最高 0.731），所以樣板要「每欄各學一個變體」，
跨欄不會硬認（低於 HIT_MIN → None）。
作法（同 namematch / petmatch 的整塊圖樣板）：格子名字區（背包 BOXES['bag']、倉庫 BOXES['depot']，相對格心）白字（三通道最小 > WHITE_MIN）
二值化 → petmatch.pack 成大整數 → 與樣板 IoU（namematch.iou，±2 px 平移）→ namematch.decide：最佳 ≥ HIT_MIN 且贏次佳「別的名字」≥ MARGIN 才認，
否則 None（不猜，呼叫端退回縮圖 / OCR）。名字區的第二行會疊到圖示上半，圖示上的白點也一起進樣板（同一道具一樣固定，反而更好分）；
右下的數量字在框外，不影響。背包格與倉庫格寬度不同（換行位置不同），樣板分 'bag' / 'depot' 兩本。

被蓋住的格不判：沿用 itemimg_match.cell_state（背包格內緣變暗 / 倉庫格間米色縫壓暗）→ None = 被浮動 EXP 橫幅蓋住，state 'occluded'。
「顯示道具名」關著：有道具的格白點 < NAME_INK_MIN（實測名字關著最多 163 點 = 圖示本身的白點；開著最少約 340 點）→ state 'noname'。

樣板是學出來的（沒有預建檔）：tools/.cache/item-name-tpl/<版面>.json = {'bag': {名稱: [hex…]}, 'depot': {…}}。
學法保守（learn）：呼叫端只在「彈窗 / 提示窗核對過名稱」或「格名稱 OCR 精確命中 Item 表」時給標籤；
那格要有道具、沒被蓋住、名字白點夠；與既有「別的名稱」樣板 IoU ≥ HIT_MIN → 標籤可疑，不學；同名最多 MAX_VARIANTS 個變體（新道具紅標 / 選取框）。
離線測試（testenv：PSA_LOG_DIR 含 psatest-）一律改用暫存資料夾的樣板，不讀寫真正的 tools/.cache。

用法（專案根目錄；唯讀、不碰遊戲）：
  uv run --no-project python tools/gui/itemname_match.py read <截圖.png> [--kind bag|depot|both] [--json]   # 每個有道具的格：名字 / 分數 / 狀態
  uv run --no-project python tools/gui/itemname_match.py learn-shot <截圖.png> --kind bag --labels 0=巴巴洛的許可證,3=風的鎖   # 人工核對過的標籤學樣板
  uv run --no-project python tools/gui/itemname_match.py list                                                  # 現有樣板（名稱 → 變體數）
  uv run --no-project python tools/gui/itemname_match.py seed                                                  # 用人工標好的 fixtures/itemname_samples.json 學進樣板（冷啟動用）
程式用：read_page(img, kind) / read_cell(img, kind, slot) / learn(img, kind, slot, name) / names_hidden(page) / same_name(a, b) / seed()
img 可以是 get(x, y)、{(x, y): rgb}、pngread.decode 結果或 PNG 路徑（imgmatch.as_getter）；格號與 bag.py 相同（0 起）。
"""
import argparse
import base64
import json
import os
import sys
import time
import zlib
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import imgmatch  # noqa: E402
import namematch  # noqa: E402  （decide：門檻 + 與次佳差距）
import petmatch  # noqa: E402  （pack / iou / ink：整塊圖 ↔ 大整數）

LAYOUT = '2880x1659'
ROOT = HERE.parents[1]
_TEST = 'psatest-' in os.environ.get('PSA_LOG_DIR', '')
TPL_DIR = (Path(os.environ['PSA_LOG_DIR']) if _TEST else ROOT / 'tools' / '.cache') / 'item-name-tpl'
SAMPLES_FILE = HERE / 'fixtures' / 'itemname_samples.json'      # 人工標籤的名字圖樣本（test_itemname_match 的回歸樣本 + seed 冷啟動）

# 名字區（相對格心 dx, dy, w, h；截圖座標）。背包格心 bag.SLOT_X / SLOT_Y，倉庫格心 bag.DEPOT_X / DEPOT_Y
# 背包：同 bag.SLOT_NAME_R（第一行字約 cy-36～cy-21、第二行 cy-11～cy+5；數量字在 cy+20 以下）
# 倉庫：格寬 94（第一行 cy-36～cy-22、第二行 cy-12～cy+3；數量字 cy+15 以下）
BOXES = {'bag': (-52, -44, 104, 52), 'depot': (-47, -42, 94, 48)}
WHITE_MIN = 200          # 白字：三通道最小值 > 這個（同 itemimg_match.text_px / band_region）
NAME_INK_MIN = 250       # 名字開著時白點下限（離線：名字關著最多 163 點〔圖示本身白點〕、開著最少約 340 點）
SHIFT = 2                # 平移 ±2 px（第 3 列格心比實際字位置高 2 px；不同欄字的半像素相位不同，±1 不夠）
HIT_MIN = 0.85           # 命中門檻（離線：同欄同名 ≈ 1.0、不同名最高 0.731）
MARGIN = 0.15            # 與次佳「別的名稱」至少差這麼多
MAX_VARIANTS = 8         # 同名變體上限：5 欄各自的半像素相位 + 選取框 / 新道具紅標
DUP_IOU = 0.98           # 與既有變體這麼像就不重複存
PRUNE = 0.5              # 白點數比例 < 這個（IoU 上限）就不比


def _pred(c) -> bool:
    return c is not None and min(c[:3]) > WHITE_MIN


def cells_of(kind: str) -> list:
    """[(格號 0 起, cx, cy)]（同 itemimg_match.cells_of；這裡不 import itemimg_match 以免沒抽圖時連帶失敗）"""
    import bag
    xs, ys = (bag.SLOT_X, bag.SLOT_Y) if kind == 'bag' else (bag.DEPOT_X, bag.DEPOT_Y)
    return [(i, xs[i % 5], ys[i // 5]) for i in range(len(xs) * len(ys))]


def rows_at(img, kind: str, slot: int) -> list:
    """格子名字區二值化 → ['0'/'1' 字串列]"""
    get = imgmatch.as_getter(img)
    _, cx, cy = cells_of(kind)[slot]
    dx, dy, w, h = BOXES[kind]
    return [''.join('1' if _pred(get(cx + dx + i, cy + dy + j)) else '0' for i in range(w)) for j in range(h)]


def _stride(kind: str) -> int:
    return BOXES[kind][2] + 2 * petmatch.PAD


def same_name(a, b) -> bool:
    """名稱相同（去空白 / 括號內容後；「大地的羈絆」=「大地的羈絆[地]」、「2倍智慧果」=「2倍智慧果(綁定)」）"""
    import bag
    na, nb = bag.norm_name(a), bag.norm_name(b)
    return bool(na) and na == nb


# ---- 樣板檔 ----
def tpl_path(layout: str = LAYOUT) -> Path:
    return TPL_DIR / f'{layout}.json'


_CACHE: dict = {}


def load_tpl(layout: str = LAYOUT, reload: bool = False) -> dict:
    """{'bag': {名稱: [hex…]}, 'depot': {…}}；沒檔 / 壞檔 → 兩本空的。依檔案 mtime 快取"""
    p = tpl_path(layout)
    try:
        mt = p.stat().st_mtime_ns
    except OSError:
        mt = None
    hit = _CACHE.get(str(p))
    if not reload and hit and hit[0] == mt:
        return hit[1]
    d = {}
    if mt is not None:
        try:
            d = json.loads(p.read_text(encoding='utf-8'))
        except (OSError, ValueError):
            d = {}
    tpl = {k: (d.get(k) if isinstance(d.get(k), dict) else {}) for k in BOXES}
    _CACHE[str(p)] = (mt, tpl)
    return tpl


def save_tpl(tpl: dict, layout: str = LAYOUT) -> None:
    TPL_DIR.mkdir(parents=True, exist_ok=True)
    p = tpl_path(layout)
    tmp = p.with_suffix(f'.{os.getpid()}.tmp')
    tmp.write_text(json.dumps(tpl, ensure_ascii=False), encoding='utf-8')
    tmp.replace(p)
    _CACHE.pop(str(p), None)


def n_templates(tpl: dict | None = None) -> int:
    tpl = load_tpl() if tpl is None else tpl
    return sum(len(v) for b in tpl.values() for v in b.values())


# ---- 比對（純函式）----
def _ints(tpl: dict, kind: str) -> dict:
    """{名稱: [(大整數, 白點數)]}（hex 解碼快取；快取裡留著 book 本身的參考，同一個 dict 物件且變體數沒變才沿用）"""
    book = tpl.get(kind) or {}
    n = sum(len(v) for v in book.values())
    hit = _INTS.get((id(book), kind))
    if hit is None or hit[0] is not book or hit[1] != n:
        if len(_INTS) > 8:
            _INTS.clear()
        hit = (book, n, {nm: [(v, v.bit_count()) for v in (int(h, 16) for h in vs)] for nm, vs in book.items()})
        _INTS[(id(book), kind)] = hit
    return hit[2]


_INTS: dict = {}


def iou(a: int, b: int, kind: str) -> float:
    """a 平移 ±SHIFT 後與 b 的最大 IoU（namematch.iou；stride = 名字區寬 + 2×petmatch.PAD）"""
    return namematch.iou(a, b, _stride(kind), SHIFT)


def scores(img_int: int, kind: str, tpl: dict) -> dict:
    """名字圖（pack 後）→ {名稱: 最佳變體 IoU}。白點數差太多（IoU 上限 < PRUNE 或 < 該名目前最佳）的變體不比"""
    na = img_int.bit_count()
    out = {}
    for n, vs in _ints(tpl, kind).items():
        best = 0.0
        for v, nb in vs:
            ub = min(na, nb) / max(na, nb, 1)
            if ub < PRUNE or ub <= best:
                continue
            best = max(best, iou(img_int, v, kind))
        out[n] = best
    return out


# ---- 「新」道具紅標（2026-10-16 p2 卡坦：剛從倉庫取出的誘餌格左上有紅色三角標 + 左邊紅條，蓋住名字區左側）----
# 紅標位置固定（相對格心）：上緣橫條 cy-47～cy-38、左側直條 x cx-46～cx-36 / y 到 cy-10（背包；倉庫格小一圈，往內 3 px）。
# 偵測 = 左側直條中段紅點夠多；有紅標的格比對時「名字圖與樣板一起」清掉名字區左側 NEW_MASK 欄（不管樣板是不是帶紅標學的），
# 只比剩下的字 → 同一道具不論有沒有紅標、在哪一欄都認得（舊版只靠「帶紅標的變體」，換一欄就認不出）。
NEW_TAG_PROBE = {'bag': (-45, -26, 7, 14), 'depot': (-42, -23, 7, 14)}      # 左側紅條取樣框（相對格心 dx, dy, w, h）
NEW_TAG_MIN = 40                                                            # 98 點中紅點下限（實測紅標 ≥ 90、一般格 0）
NEW_MASK = {'bag': (20, 40), 'depot': (20, 40)}                              # 名字區左上清掉的 (寬, 高)（box 座標；紅條右緣 cx-36 = box x 16）


def _red(c) -> bool:
    return c is not None and c[0] > 150 and c[1] < 100 and c[2] < 100


def new_tag(img, kind: str, slot: int) -> bool:
    """這格左上有「新」紅標（純讀像素）"""
    get = imgmatch.as_getter(img)
    _, cx, cy = cells_of(kind)[slot]
    dx, dy, w, h = NEW_TAG_PROBE[kind]
    return sum(1 for j in range(h) for i in range(w) if _red(get(cx + dx + i, cy + dy + j))) >= NEW_TAG_MIN


def mask_rows(rows, kind: str) -> list:
    """名字區左上 NEW_MASK 範圍清成 0（紅標蓋住的地方）"""
    mw, mh = NEW_MASK[kind]
    return [('0' * mw + r[mw:]) if y < mh else r for y, r in enumerate(rows)]


def _masked_tpl(tpl: dict, kind: str) -> dict:
    """樣板同樣清掉 NEW_MASK 範圍（hex → rows → mask → hex；依 book 物件快取）"""
    book = tpl.get(kind) or {}
    n = sum(len(v) for v in book.values())
    hit = _MASKED.get(kind)
    if hit and hit[0] is book and hit[1] == n:
        return hit[2]
    w, h = BOXES[kind][2], BOXES[kind][3]
    stride = w + 2 * petmatch.PAD
    mw, mh = NEW_MASK[kind]
    m = 0
    for y in range(mh):
        for x in range(mw):
            m |= 1 << ((y + petmatch.PAD) * stride + x + petmatch.PAD)
    out = {kind: {nm: [format(int(hx, 16) & ~m, 'x') for hx in vs] for nm, vs in book.items()}}
    _MASKED[kind] = (book, n, out)
    return out


_MASKED: dict = {}


def match_rows(rows, kind: str, tpl: dict | None = None, new: bool = False) -> dict:
    """二值列 → {'name': 名稱或 None, 'score', 'second', 'ink'}（白點不足 NAME_INK_MIN → name None）。
    new = 這格有「新」紅標 → 名字圖與樣板都清掉紅標範圍再比（mask_rows / _masked_tpl）"""
    tpl = load_tpl() if tpl is None else tpl
    ink = petmatch.ink(rows)
    if ink < NAME_INK_MIN or not tpl.get(kind):
        return {'name': None, 'score': 0.0, 'second': 0.0, 'ink': ink}
    if new:
        rows, tpl = mask_rows(rows, kind), _masked_tpl(tpl, kind)
    name, best, second = namematch.decide(scores(petmatch.pack(rows), kind, tpl), HIT_MIN, MARGIN)
    return {'name': name, 'score': round(best, 3), 'second': round(second, 3), 'ink': ink, 'new': new}


def _cell_state(get, kind: str, slot: int):
    """True 有道具 / False 空格 / None 被橫幅蓋住（itemimg_match.cell_state：沿用縮圖那套遮擋偵測）"""
    import itemimg_match
    return itemimg_match.cell_state(get, kind, slot)


def read_cell(img, kind: str, slot: int, tpl: dict | None = None, state=...) -> dict:
    """一格 → {'slot', 'state': 'empty'|'occluded'|'noname'|'name'|'unknown', 'name', 'score', 'second', 'ink'}。
    noname = 有道具但白點不足（「顯示道具名」關著 / 名字被別的東西蓋掉）；unknown = 有名字但樣板認不出（沒學過 / 太近）"""
    get = imgmatch.as_getter(img)
    st = _cell_state(get, kind, slot) if state is ... else state
    if st is None:
        return {'slot': slot, 'state': 'occluded', 'name': None, 'score': 0.0, 'second': 0.0, 'ink': 0}
    if st is False:
        return {'slot': slot, 'state': 'empty', 'name': None, 'score': 0.0, 'second': 0.0, 'ink': 0}
    r = match_rows(rows_at(get, kind, slot), kind, tpl, new_tag(get, kind, slot))
    r['slot'] = slot
    r['state'] = 'noname' if r['ink'] < NAME_INK_MIN else ('name' if r['name'] else 'unknown')
    return r


def read_page(img, kind: str, tpl: dict | None = None, slots=None) -> dict:
    """整頁 → {'cells': {格: read_cell 結果（空格不列）}, 'occ': [True/False/None], 'names': {格: 名稱}, 'hidden': bool, 'ms'}。
    hidden = 有道具且沒被蓋住的格至少 1 格、而且全部白點不足 →「顯示道具名」關著"""
    t0 = time.time()
    get = imgmatch.as_getter(img)
    tpl = load_tpl() if tpl is None else tpl
    allc = cells_of(kind)
    want = set(range(len(allc)) if slots is None else slots)
    occ, cells = [], {}
    for i, _, _ in allc:
        st = _cell_state(get, kind, i)
        occ.append(st)
        if i in want and st is not False:
            cells[i] = read_cell(get, kind, i, tpl, state=st)
    vis = [c for c in cells.values() if c['state'] != 'occluded']
    return {'cells': cells, 'occ': occ, 'names': {i: c['name'] for i, c in cells.items() if c['name']},
            'hidden': bool(vis) and all(c['state'] == 'noname' for c in vis), 'ms': int((time.time() - t0) * 1000)}


def names_hidden(page: dict) -> bool:
    return bool(page and page.get('hidden'))


# ---- 學習 ----
def learn_rows(rows, kind: str, name: str, tpl: dict, log=None) -> bool:
    """純函式：名字圖加進 tpl（不存檔）。白點不足 / 與既有「別的名稱」IoU ≥ HIT_MIN（標籤可疑）/ 已有幾乎相同變體 / 變體已滿 → False"""
    if not name or petmatch.ink(rows) < NAME_INK_MIN:
        return False
    img = petmatch.pack(rows)
    book = tpl.setdefault(kind, {})
    key = next((k for k in book if same_name(k, name)), name)
    for other, vs in book.items():
        if other != key and any(iou(img, int(h, 16), kind) >= HIT_MIN for h in vs):
            if log:
                log(f'itemname：{kind} 標籤 {name!r} 但與既有 {other!r} 樣板 IoU ≥ {HIT_MIN}，標籤可疑，不學')
            return False
    vs = book.setdefault(key, [])
    if len(vs) >= MAX_VARIANTS or any(iou(img, int(h, 16), kind) >= DUP_IOU for h in vs):
        if not vs:
            book.pop(key, None)
        return False
    vs.append(format(img, 'x'))
    return True


def learn(img, kind: str, slot: int, name: str, save: bool = True, log=None) -> bool:
    """可信標籤（彈窗 / 提示窗核對過、或 OCR 精確命中 Item 表）→ 學這格的名字圖。那格要有道具、沒被蓋住。回是否新增"""
    get = imgmatch.as_getter(img)
    if _cell_state(get, kind, slot) is not True:
        return False
    tpl = load_tpl()
    tpl = {k: {n: list(v) for n, v in b.items()} for k, b in tpl.items()}      # 複本：不汙染快取
    if not learn_rows(rows_at(get, kind, slot), kind, name, tpl, log):
        return False
    if save:
        save_tpl(tpl)
    if log:
        log(f'itemname：學到 {kind} 格 {slot} 「{name}」（{kind} 本 {len(tpl[kind])} 種名稱）')
    return True


# ---- 樣本檔（fixtures/itemname_samples.json）----
def rows_encode(rows) -> str:
    """二值列 → base64(zlib(整數位元組))（列寬 / 列數由 kind 決定）"""
    v = int(''.join(rows), 2) if rows else 0
    return base64.b64encode(zlib.compress(v.to_bytes((v.bit_length() + 7) // 8 or 1, 'big'), 9)).decode('ascii')


def rows_decode(s: str, kind: str) -> list:
    _, _, w, h = BOXES[kind]
    v = int.from_bytes(zlib.decompress(base64.b64decode(s)), 'big')
    b = format(v, f'0{w * h}b')
    return [b[j * w:(j + 1) * w] for j in range(h)]


def load_samples(path=None) -> dict:
    """{'images': [{'kind', 'label', 'rows', 'n'（出現次數）}], 'samples': [{'rel', 'kind', 'slot', 'label', 'img'}]}；沒檔 → 空"""
    try:
        d = json.loads(Path(path or SAMPLES_FILE).read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return {'images': [], 'samples': []}
    for im in d.get('images', []):
        im['rows'] = rows_decode(im['b64'], im['kind'])
    return d


def seed(path=None, log=print) -> int:
    """人工標籤樣本學進樣板（照 learn_rows 的保守規則；出現次數多的變體先學）→ 新增變體數"""
    d = load_samples(path)
    tpl = {k: {n: list(v) for n, v in b.items()} for k, b in load_tpl().items()}
    n = sum(learn_rows(im['rows'], im['kind'], im['label'], tpl, log) for im in sorted(d['images'], key=lambda im: -im.get('n', 1)))
    if n:
        save_tpl(tpl)
    log(f'itemname seed：新增 {n} 個變體；樣板共 {n_templates(tpl)} 個（{tpl_path()}）')
    return n


# ---- CLI ----
def _parse_labels(s: str) -> dict:
    out = {}
    for part in (s or '').split(','):
        if '=' in part:
            k, v = part.split('=', 1)
            out[int(k)] = v.strip()
    return out


def main(argv=None) -> int:
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    sub = ap.add_subparsers(dest='cmd', required=True)
    p = sub.add_parser('read', help='讀截圖每格的名字（唯讀）')
    p.add_argument('png')
    p.add_argument('--kind', default='bag', choices=['bag', 'depot', 'both'])
    p.add_argument('--json', action='store_true')
    p = sub.add_parser('learn-shot', help='人工核對過的標籤從截圖學樣板')
    p.add_argument('png')
    p.add_argument('--kind', required=True, choices=['bag', 'depot'])
    p.add_argument('--labels', required=True, help='格號=名稱,格號=名稱（格號 0 起）')
    sub.add_parser('list', help='列出樣板')
    p = sub.add_parser('seed', help='用人工標籤樣本（fixtures/itemname_samples.json）學樣板')
    p.add_argument('--fixture', default=None)
    a = ap.parse_args(argv)
    if a.cmd == 'seed':
        seed(a.fixture)
        return 0
    if a.cmd == 'list':
        tpl = load_tpl()
        for k in BOXES:
            for n, vs in sorted(tpl[k].items()):
                print(f'{k}\t{n}\t{len(vs)} 個變體')
        print(f'共 {n_templates(tpl)} 個變體（{tpl_path()}）')
        return 0
    try:
        get = imgmatch.as_getter(a.png)
    except (OSError, ValueError) as e:
        print(f'截圖讀不到：{e}', file=sys.stderr)
        return 1
    if a.cmd == 'learn-shot':
        n = 0
        for slot, name in _parse_labels(a.labels).items():
            ok = learn(get, a.kind, slot, name, log=print)
            n += ok
            if not ok:
                print(f'格 {slot}「{name}」沒學（空格 / 被蓋住 / 白點不足 / 已有 / 標籤可疑）')
        print(f'新增 {n} 個變體')
        return 0
    out = {}
    for k in (['bag', 'depot'] if a.kind == 'both' else [a.kind]):
        out[k] = read_page(get, k)
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0
    for k, pg in out.items():
        print(f'[{k}] hidden={pg["hidden"]} {pg["ms"]} ms')
        for i, c in sorted(pg['cells'].items()):
            print(f'  格 {i:2d} {c["state"]:8s} {c["name"] or "-"}  score {c["score"]} second {c["second"]} ink {c["ink"]}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
