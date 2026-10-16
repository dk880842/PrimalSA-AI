#!/usr/bin/env python3
"""截圖樣本「分類索引 + 像素快取」（純標準函式庫、純離線，不碰遊戲）。

背景：tools/.cache 下約 775 張 1440×830 截圖是 screen_sigs 挑點、make_fixtures 重產 fixture 的樣本；
每次用 pngread 純 Python 解碼全部 PNG 很慢（一張約 0.5～1 秒）。這裡把每張解碼一次，存成 zlib 壓縮的 RGB raw，
之後任意取點只要解壓（約 5 ms）；同時維護一份分類索引（每張圖是什麼畫面）。

檔案（都在 tools/.cache，已被 gitignore）：
  shots-index.json        索引：{version, sig, entries: {相對路徑: {sha1, size, mtime, w, h, label, label_src, auto?, not_panel?}}}
  shotcache/points.pkl    點快取：{sha1: {y*1440+x: rgb 整數}}；build 時對每張圖取好 classify / annotate 要的全部點（約 700 個）
實測（774 張）：這批截圖 pngread 解碼只要約 10～25 ms/張，整張解壓存起來（1.3 GB）反而比重新解碼慢，所以只存「取過的點」；
同一組點第二次起是查表，沒存過的點才解碼 PNG 補並寫回（程式結束自動 flush）。
掃描範圍 = tools/.cache 底下全部 .png，排除 pet-images / gh-pages / shotcache / tools（資料夾，不是截圖樣本）。
不搬移、不改名任何截圖；測試與 fixture 用相對路徑（例 watch-panels/role-0.png）引用。分類用索引檔表達。

標籤（label）：面板 pet/bag/quest/transfer/setting/team/qteam/switch/ass/role、battle、dialog、reward、select、
  idle、walking、login、charsel、notice（提示視窗）、loading、black、unknown；非 1440×830 的圖 label = 'offsize'（不進點快取）。
標籤來源（label_src）優先序：manual（relabel 指令）> fixture（make_fixtures.PANEL_POS 人工標籤）> rule（目錄 / 檔名規則）> auto（screen_sigs.classify）。
manual 在重建時保留（sha1 沒變）；其餘每次 build 都重算（screen_sigs 調整後標籤會跟著更新）。

CLI（uv run --no-project python tools/gui/shotcache.py ...）：
  build                 增量建置：新圖 / 改過的圖才解碼（多行程），刪掉的圖從索引與點快取移除；標籤依據（screen_sigs / make_fixtures 標籤表）變了才重算非 manual 標籤
  stats                 各類張數（人工 = manual+fixture、規則、自動分開）+ 可疑 auto 數
  list [--label L] [--src S] [--suspect]   列出路徑 / 標籤 / 來源（--suspect = 只列可疑）
  relabel <路徑> <標籤>  人工指定標籤（label_src=manual）
  bench                 量測：全部樣本取 100 個隨機點，點快取（冷 / 熱）vs 原本 pngread

Python API：
  import shotcache
  for rel, label, shot in shotcache.iter_shots(label=None, src=None):   # shot(x, y) → (r, g, b)；shot.pixels(pts) → {(x, y): (r, g, b)}
      ...
  shot = shotcache.get('watch-panels/role-0.png')    # 單張；索引沒有 / 過期時自動補建；像素走點快取
  shotcache.label_of('ui/pet.png') → ('pet', 'fixture')
"""
import ast
import atexit
import hashlib
import json
import os
import pickle
import struct
import sys
import time
import zlib
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import pngread  # noqa: E402
import screen_sigs  # noqa: E402

CACHE = HERE.parent / '.cache'
INDEX = CACHE / 'shots-index.json'
PTS = CACHE / 'shotcache' / 'points.pkl'
SIZE = (1440, 830)
SKIP_DIRS = {'pet-images', 'gh-pages', 'shotcache', 'tools'}
_PTS = None
VERSION = 1
PANELS = tuple(screen_sigs.PANEL_NAMES)                 # 面板標籤名（pet / bag …）
SRC_RANK = {'manual': 0, 'fixture': 1, 'rule': 2, 'auto': 3, 'size': 4}


# ---------------------------------------------------------------- 掃描 / 解碼
def scan() -> list:
    """tools/.cache 底下全部 .png 的相對路徑（posix 斜線、排序），排除 SKIP_DIRS"""
    out = []
    for root, dirs, files in os.walk(CACHE):
        rel_root = Path(root).relative_to(CACHE)
        if rel_root == Path('.'):
            dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for f in files:
            if f.lower().endswith('.png'):
                out.append((rel_root / f).as_posix())
    return sorted(out)


def png_size(data: bytes):
    """只讀 IHDR → (w, h)；不是 PNG 回 None"""
    if data[:8] != b'\x89PNG\r\n\x1a\n' or len(data) < 24:
        return None
    return struct.unpack('>II', data[16:24])


def label_points() -> list:
    """標籤判定要的取樣點（classify + annotate 全部）；build 時對每張圖先取好存進點快取"""
    global _PTS
    if _PTS is None:
        _PTS = list(dict.fromkeys(screen_sigs.points() + screen_sigs.annot_points()))
    return _PTS


def _decode_job(rel: str):
    """子行程：讀檔、算 sha1、解碼一次、取 label_points() → (rel, sha1, (w, h), {key: rgb 整數}, 錯誤)。
    非 1440×830 不解碼、點為空。"""
    try:
        data = (CACHE / rel).read_bytes()
        sha = hashlib.sha1(data).hexdigest()
        wh = png_size(data)
        if wh != SIZE:
            return rel, sha, wh, {}, None
        w, h, bpp, rows = pngread.decode(data)
        return rel, sha, wh, {_key(x, y): _rgb(rows[y][x * bpp:x * bpp + 3]) for x, y in label_points()}, None
    except Exception as e:                  # 檔案寫到一半 / 損毀：略過，下次 build 再試
        return rel, None, None, {}, '%s: %s' % (type(e).__name__, e)


def _key(x: int, y: int) -> int:
    return y * SIZE[0] + x


def _rgb(c) -> int:
    return (c[0] << 16) | (c[1] << 8) | c[2]


# ---------------------------------------------------------------- 點快取
# 實測（2026-10-11，774 張 1440×830）：這批截圖用 pngread 解碼只要約 10～25 ms/張（整批 18 秒 + 讀檔 8 秒），
# 把整張解壓存起來（zlib RGB raw，1.3 GB）讀回來反而更慢，所以不存整張像素；改存「每張圖已取過的點」。
# 同一組點（classify / 面板判定 / fixture 挑點）第二次起是 dict 查表（整批 774 張 < 1 秒）；沒存過的點才解碼 PNG 補，並寫回。
_TABLE = None           # {sha1: {key: rgb 整數}}
_DIRTY = False


def _table() -> dict:
    global _TABLE
    if _TABLE is None:
        try:
            with open(PTS, 'rb') as f:
                d = pickle.load(f)
            _TABLE = d if isinstance(d, dict) and d.get('version') == VERSION else {}
            _TABLE = _TABLE.get('t', {})
        except (OSError, ValueError, pickle.UnpicklingError, EOFError):
            _TABLE = {}
    return _TABLE


def flush() -> None:
    """點快取寫回磁碟（有新增才寫；程式結束時自動呼叫）"""
    global _DIRTY
    if _DIRTY and _TABLE is not None:
        CACHE.mkdir(exist_ok=True)
        tmp = PTS.with_suffix('.tmp%d' % os.getpid())
        with open(tmp, 'wb') as f:
            pickle.dump({'version': VERSION, 't': _TABLE}, f, protocol=4)
        os.replace(tmp, PTS)
        _DIRTY = False


atexit.register(flush)


class Shot:
    """一張截圖的像素存取：shot(x, y) → (r, g, b)、shot.pixels(pts) → {(x, y): (r, g, b)}。
    先查點快取，沒有才解碼 PNG（本物件內只解碼一次）並把新點寫進快取。"""

    def __init__(self, rel: str, sha1: str):
        self.rel, self.sha1, self.w, self.h, self._rows = rel, sha1, SIZE[0], SIZE[1], None

    def _fetch(self, x: int, y: int) -> int:
        global _DIRTY
        if not (0 <= x < self.w and 0 <= y < self.h):
            raise IndexError((x, y))
        t = _table().setdefault(self.sha1, {})
        k = _key(x, y)
        v = t.get(k)
        if v is None:
            if self._rows is None:
                w, h, bpp, rows = pngread.decode((CACHE / self.rel).read_bytes())
                self._rows, self._bpp = rows, bpp
            v = t[k] = _rgb(self._rows[y][x * self._bpp:x * self._bpp + 3])
            _DIRTY = True
        return v

    def __call__(self, x: int, y: int):
        v = self._fetch(x, y)
        return (v >> 16, (v >> 8) & 255, v & 255)

    def pixels(self, pts) -> dict:
        """pts = [(x, y), ...] → {(x, y): (r, g, b)}（同 pngread.pixels；越界丟 IndexError）"""
        out = {}
        for x, y in pts:
            v = self._fetch(x, y)
            out[(x, y)] = (v >> 16, (v >> 8) & 255, v & 255)
        return out


# ---------------------------------------------------------------- 標籤
def _fixture_tables() -> tuple:
    """用 ast 讀 make_fixtures.py 的 PANEL_POS / PANEL_NEG（不 import：避免循環與載入 grind）→ ({檔: 面板}, {負例檔})"""
    try:
        tree = ast.parse((HERE / 'make_fixtures.py').read_text(encoding='utf-8'))
    except OSError:
        return {}, set()
    vals = {}
    for n in tree.body:
        if isinstance(n, ast.Assign) and len(n.targets) == 1 and isinstance(n.targets[0], ast.Name) and n.targets[0].id in ('PANEL_POS', 'PANEL_NEG'):
            vals[n.targets[0].id] = ast.literal_eval(n.value)
    return dict(vals.get('PANEL_POS', {})), set(vals.get('PANEL_NEG', []))


def rule_label(rel: str):
    """目錄 / 檔名規則 → 標籤或 None。只放有把握的：quest-log 的檔名後綴、battle-samples 的戰鬥系列"""
    name = rel.rsplit('/', 1)[-1]
    if rel.startswith('quest-log/'):
        if name.endswith('-dialog.png'):            # -dialog / -npc-dialog
            return 'dialog'
        if name.endswith('-reward.png'):
            return 'reward'
    if rel.startswith('battle-samples/') and name.startswith(('vs_', 'seq_', 'full_playing', 'cmd_')):
        return 'battle'
    return None


def auto_label(shot: Shot) -> str:
    """screen_sigs.classify / annotate 自動判"""
    px = shot.pixels(label_points())
    c = screen_sigs.classify(px)
    ann = screen_sigs.annotate(px, c)
    for a, lab in (('login', 'login'), ('charsel', 'charsel'), ('notice_dialog', 'notice'), ('net_lost', 'notice'), ('loading', 'loading'), ('black', 'black')):
        if a in ann:
            return lab
    return c['panel'] if c['state'] == 'panel' and c['panel'] else c['state']


def decide(rel: str, shot, old: dict, fx_pos: dict) -> tuple:
    """標籤優先序 manual > fixture > rule > auto → (label, label_src)"""
    if old and old.get('label_src') == 'manual':
        return old['label'], 'manual'
    if rel in fx_pos:
        return fx_pos[rel], 'fixture'
    r = rule_label(rel)
    if r:
        return r, 'rule'
    return auto_label(shot), 'auto'


def suspects(entries: dict) -> list:
    """可疑 = 需要人工確認的 → [(rel, 原因)]：auto 判 unknown / 判成面板卻是 make_fixtures 的負例 / 規則或人工標籤與 auto 判不同"""
    out = []
    for rel, e in sorted(entries.items()):
        if e['label'] == 'offsize':
            continue
        if e['label_src'] == 'auto':
            if e['label'] == 'unknown':
                out.append((rel, 'auto=unknown'))
            elif e.get('not_panel') and e['label'] in PANELS:
                out.append((rel, 'auto 判面板 %s 但是 PANEL_NEG 負例' % e['label']))
        elif e.get('auto') and e['auto'] != e['label']:
            out.append((rel, '%s 標籤=%s，auto 判=%s' % (e['label_src'], e['label'], e['auto'])))
    return out


# ---------------------------------------------------------------- 索引
def load_index() -> dict:
    try:
        d = json.loads(INDEX.read_text(encoding='utf-8'))
        if d.get('version') == VERSION:
            return d['entries']
    except (OSError, ValueError):
        pass
    return {}


def load_sig() -> str:
    try:
        return json.loads(INDEX.read_text(encoding='utf-8')).get('sig', '')
    except (OSError, ValueError):
        return ''


def label_sig(fx_pos: dict, fx_neg: set) -> str:
    """標籤依據的指紋：screen_sigs / battleguard / 本檔原始碼 + make_fixtures 的人工標籤表；沒變就不必重算標籤"""
    h = hashlib.sha1()
    for f in (HERE / 'screen_sigs.py', HERE / 'battleguard.py', Path(__file__)):
        h.update(f.read_bytes())
    h.update(repr((sorted(fx_pos.items()), sorted(fx_neg))).encode('utf-8'))
    return h.hexdigest()


def save_index(entries: dict, sig: str = None) -> None:
    CACHE.mkdir(exist_ok=True)
    tmp = INDEX.with_suffix('.tmp%d' % os.getpid())
    tmp.write_text(json.dumps({'version': VERSION, 'sig': load_sig() if sig is None else sig, 'entries': entries}, ensure_ascii=False, indent=0, sort_keys=True), encoding='utf-8')
    os.replace(tmp, INDEX)


def build(verbose: bool = True, workers: int = 3) -> dict:
    """增量建置 → 統計 {'new', 'kept', 'removed', 'offsize', 'errors', 'secs'}。
    判斷沒變 = 路徑存在於索引且 size + mtime 相同（不重算 sha1）；新圖 / 變動的圖才解碼（多行程）並把標籤判定用的點存進點快取。"""
    global _DIRTY
    t0 = time.time()
    CACHE.mkdir(exist_ok=True)
    PTS.parent.mkdir(exist_ok=True)
    old = load_index()
    fx_pos, fx_neg = _fixture_tables()
    rels = scan()
    todo, entries = [], {}
    for rel in rels:
        st = (CACHE / rel).stat()
        o = old.get(rel)
        if o and o['size'] == st.st_size and o['mtime'] == st.st_mtime_ns:
            entries[rel] = dict(o)
        else:
            todo.append(rel)
    new = errors = 0
    if todo:
        if workers > 1 and len(todo) > 4:
            import multiprocessing
            with multiprocessing.Pool(workers, initializer=_lower_priority) as pool:
                results = pool.map(_decode_job, todo, chunksize=4)
        else:
            results = [_decode_job(r) for r in todo]
        tab = _table()
        for rel, sha, wh, pts, err in results:
            if err:
                errors += 1
                if verbose:
                    print('略過（讀取 / 解碼失敗）', rel, err)
                continue
            if pts:
                tab.setdefault(sha, {}).update(pts)
                _DIRTY = True
            st = (CACHE / rel).stat()
            e = {'sha1': sha, 'size': st.st_size, 'mtime': st.st_mtime_ns, 'w': wh[0] if wh else 0, 'h': wh[1] if wh else 0, 'label': 'unknown', 'label_src': 'auto'}
            if wh != SIZE:
                e['label'], e['label_src'] = 'offsize', 'size'
            entries[rel] = e
            new += 1
    # 重算非 manual 標籤（指紋沒變且不是新圖就沿用，避免每次 build 都解壓全部）
    sig = label_sig(fx_pos, fx_neg)
    same_sig = sig == load_sig()
    new_set = set(todo)
    offsize = 0
    for rel, e in entries.items():
        if e['label'] == 'offsize':
            offsize += 1
            continue
        if same_sig and rel not in new_set and e['label_src'] != 'size':
            continue
        shot = Shot(rel, e['sha1'])
        e['label'], e['label_src'] = decide(rel, shot, e, fx_pos)
        if e['label_src'] in ('fixture', 'rule'):
            e['auto'] = auto_label(shot)            # 供「人工標籤 vs auto」差異偵測
        else:
            e.pop('auto', None)
        if rel in fx_neg:
            e['not_panel'] = True
        else:
            e.pop('not_panel', None)
    removed = len(set(old) - set(entries))
    save_index(entries, sig)
    live = {e['sha1'] for e in entries.values()}
    tab = _table()
    for sha in [k for k in tab if k not in live]:   # 圖被刪 / 改掉：點快取一併移除
        del tab[sha]
        _DIRTY = True
    flush()
    res = {'new': new, 'kept': len(entries) - new, 'removed': removed, 'offsize': offsize, 'errors': errors, 'secs': round(time.time() - t0, 2)}
    if verbose:
        print('build：', res)
    return res


def _lower_priority():
    try:
        os.nice(10)
    except (AttributeError, OSError):
        pass


# ---------------------------------------------------------------- API
def _norm(path) -> str:
    p = Path(path)
    if p.is_absolute():
        p = p.relative_to(CACHE)
    return p.as_posix()


def get(path) -> Shot:
    """單張：path = 相對 tools/.cache 或絕對路徑。索引沒有 / size+mtime 變了就自動補建（會更新索引）。非 1440×830 丟 ValueError"""
    rel = _norm(path)
    entries = load_index()
    e = entries.get(rel)
    st = (CACHE / rel).stat()
    if not e or e['size'] != st.st_size or e['mtime'] != st.st_mtime_ns:
        build(verbose=False, workers=1)
        e = load_index().get(rel)
    if not e or e['label'] == 'offsize':
        raise ValueError('不是 1440×830 或無法解碼：' + rel)
    return Shot(rel, e['sha1'])


def label_of(path):
    """(label, label_src) 或 None（索引沒有）"""
    e = load_index().get(_norm(path))
    return (e['label'], e['label_src']) if e else None


def iter_shots(label=None, src=None):
    """產出 (相對路徑, 標籤, Shot)，依路徑排序；label / src 可濾（可傳字串或集合）；offsize 不產出。索引需先 build"""
    ls = {label} if isinstance(label, str) else (set(label) if label else None)
    ss = {src} if isinstance(src, str) else (set(src) if src else None)
    for rel, e in sorted(load_index().items()):
        if e['label'] == 'offsize' or (ls and e['label'] not in ls) or (ss and e['label_src'] not in ss):
            continue
        yield rel, e['label'], Shot(rel, e['sha1'])


def relabel(path, label: str) -> None:
    rel = _norm(path)
    entries = load_index()
    if rel not in entries:
        raise SystemExit('索引沒有這張圖（先 build）：' + rel)
    entries[rel]['label'], entries[rel]['label_src'] = label, 'manual'
    save_index(entries)


# ---------------------------------------------------------------- CLI
def stats(entries: dict = None) -> dict:
    entries = load_index() if entries is None else entries
    tab = {}
    for e in entries.values():
        t = tab.setdefault(e['label'], {'manual': 0, 'fixture': 0, 'rule': 0, 'auto': 0, 'size': 0})
        t[e['label_src']] += 1
    return tab


def _print_stats() -> None:
    entries = load_index()
    tab = stats(entries)
    print('%-10s %6s %6s %6s %6s %6s' % ('label', '合計', '人工', '規則', '自動', '其他'))
    tot = [0, 0, 0, 0, 0]
    for lab, t in sorted(tab.items(), key=lambda kv: -sum(kv[1].values())):
        row = [sum(t.values()), t['manual'] + t['fixture'], t['rule'], t['auto'], t['size']]
        tot = [a + b for a, b in zip(tot, row)]
        print('%-10s %6d %6d %6d %6d %6d' % ((lab,) + tuple(row)))
    print('%-10s %6d %6d %6d %6d %6d' % (('總計',) + tuple(tot)), '（人工 = manual + fixture；其他 = offsize）')
    sus = suspects(entries)
    print('可疑（需人工確認）：%d 張' % len(sus))


def _bench() -> None:
    """全部樣本取 100 個隨機點：pngread（原本做法）、點快取冷（點沒存過，要解碼）、點快取熱（第二次同一組點）"""
    import random
    random.seed(1)
    pts = [(random.randrange(1440), random.randrange(830)) for _ in range(100)]
    items = list(iter_shots())
    t = time.time()
    for rel, lab, shot in items:
        w, h, bpp, rows = pngread.decode((CACHE / rel).read_bytes())
        pngread.pixels(rows, bpp, pts)
    t_png = time.time() - t
    t = time.time()
    for rel, lab, shot in items:
        shot.pixels(pts)
    t_cold = time.time() - t
    t = time.time()
    for rel, lab, shot in items:
        shot.pixels(pts)
    t_hot = time.time() - t
    # 熱路徑 = 另一個 Shot 物件（不靠物件內的 rows）：同一組點再取
    t = time.time()
    for rel, lab, shot in iter_shots():
        shot.pixels(pts)
    t_hot2 = time.time() - t
    print('取 100 點 × %d 張：pngread %.2f 秒；點快取冷 %.2f 秒、熱 %.3f 秒（新 Shot 物件 %.3f 秒）' % (len(items), t_png, t_cold, t_hot, t_hot2))
    # 標籤判定的那組點（build 已預存）
    t = time.time()
    n = sum(1 for rel, lab, shot in iter_shots() if auto_label(shot))
    print('全部樣本 classify（label_points 約 %d 點）：%.2f 秒' % (len(label_points()), time.time() - t))


def main(argv) -> int:
    if not argv or argv[0] in ('-h', '--help'):
        print(__doc__)
        return 0
    cmd, rest = argv[0], argv[1:]
    if cmd == 'build':
        build()
    elif cmd == 'stats':
        _print_stats()
    elif cmd == 'list':
        label = src = None
        sus_only = '--suspect' in rest
        for i, a in enumerate(rest):
            if a == '--label':
                label = rest[i + 1]
            elif a == '--src':
                src = rest[i + 1]
        entries = load_index()
        sus = dict(suspects(entries))
        for rel, e in sorted(entries.items()):
            if (label and e['label'] != label) or (src and e['label_src'] != src) or (sus_only and rel not in sus):
                continue
            print(rel, e['label'], e['label_src'], sus.get(rel, ''))
    elif cmd == 'relabel' and len(rest) == 2:
        relabel(rest[0], rest[1])
        print('已標記', _norm(rest[0]), '→', rest[1], '(manual)')
    elif cmd == 'bench':
        _bench()
    else:
        print(__doc__)
        return 2
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
