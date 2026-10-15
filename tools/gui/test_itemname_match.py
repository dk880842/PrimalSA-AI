#!/usr/bin/env python3
"""itemname_match（道具格名字樣板）+ bag.py 名字優先接線的離線測試（不碰遊戲）。用法：
  uv run --no-project python tools/gui/test_itemname_match.py                  # 跑測試
  uv run --no-project python tools/gui/test_itemname_match.py --make-fixtures  # 從 tools/.cache 截圖重做 fixtures/itemname_samples.json（維護用；標籤沿用檔內的）

回歸樣本 fixtures/itemname_samples.json（2026-10-14 人工標籤）：tools/.cache 裡 shotcache 標成 bag 的截圖中，背包頁 / 倉庫頁、名字開著、
有道具且沒被橫幅蓋住的格 → 138 張截圖、1,231 格（背包 815、倉庫 416）、68 種「名稱 × 格種」；相同點陣只存一份（170 張名字圖）。
標籤做法：先把名字圖依 IoU ≥ 0.9 分群，每群代表格彩色裁片拼成總表人工讀字（139 群），群內共用標籤。

測什麼：
  1. 準確率（樣板 = 其他截圖的名字圖，比對門檻 / 分差照 itemname_match）：留一張截圖（LOSO）、留一張名字圖（更嚴：同點陣也拿掉）、
     開集（整個名稱拿掉 → 必須 None）都要 0 誤認；印對 / 錯 / 判不出數字。
  2. learn_rows 保守規則：白點不足、與別的名稱樣板太像、重複、變體上限。
  3. read_page：合成畫面（樣本點陣貼回格子位置，其他當空格棕）→ 名字 / 空格 / 被蓋住（格內緣壓暗）/ 名字關著。
  4. bag.py 接線（假面板 / 假 OCR / 假彈窗，同 test_bag_icon.install）：name 模式零 OCR、名字樣板認出就不開彈窗、
     同圖多名靠名字分得開、彈窗核對後學會、OCR 精確命中後學會、換角色 / 太舊的截圖不學、縮圖與標籤矛盾不學、iconocr 模式不看名字樣板。
"""
import os
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import testenv  # noqa: E402,F401  紀錄檔 / 名字樣板轉向暫存
import itemname_match as N  # noqa: E402
import namematch  # noqa: E402
import petmatch  # noqa: E402

CACHE = HERE.parents[1] / 'tools' / '.cache'
fails = 0


def check(name, cond, extra=''):
    global fails
    print(('PASS' if cond else 'FAIL'), name, extra)
    if not cond:
        fails += 1


# ---- 樣本檔 ----
def build_fixture(labels, path=None) -> dict:
    """labels = [(截圖相對路徑, kind, 格號, 名稱)] → 從 tools/.cache 截圖重讀名字點陣 → 寫 fixtures/itemname_samples.json"""
    import json
    import imgmatch
    gets, images, idx, samples = {}, [], {}, []
    for rel, kind, slot, label in labels:
        if rel not in gets:
            gets[rel] = imgmatch.as_getter(str(CACHE / rel))
        rows = N.rows_at(gets[rel], kind, slot)
        b64 = N.rows_encode(rows)
        key = (kind, label, b64)
        if key not in idx:
            idx[key] = len(images)
            images.append({'kind': kind, 'label': label, 'b64': b64, 'n': 0})
        images[idx[key]]['n'] += 1
        samples.append({'rel': rel, 'kind': kind, 'slot': slot, 'label': label, 'img': idx[key]})
    d = {'note': 'itemname_match 回歸樣本（2026-10-14 人工標籤；test_itemname_match.py --make-fixtures 重做）',
         'box': N.BOXES, 'white_min': N.WHITE_MIN, 'images': images, 'samples': samples}
    p = Path(path or N.SAMPLES_FILE)
    p.write_text(json.dumps(d, ensure_ascii=False, separators=(',', ':')), encoding='utf-8')
    print(f'寫入 {p}：{len(images)} 張名字圖、{len(samples)} 格')
    return d


def make_fixtures() -> int:
    d = N.load_samples()
    if not d['samples']:
        print('fixtures/itemname_samples.json 沒有樣本（標籤來源），無法重做')
        return 1
    build_fixture([(s['rel'], s['kind'], s['slot'], s['label']) for s in d['samples']])
    return 0


# ---- 1. 準確率 ----
def _decide(scores: dict):
    """照 itemname_match.decide（含只差數字的同族規則）；樣板本 = 這次比對的名稱"""
    nm, b, sec, _ = N.decide(scores, {lb: [] for lb in scores})
    return nm, b, sec


def test_accuracy(d) -> dict:
    import bag
    imgs = d['images']
    for im in imgs:
        im['v'] = petmatch.pack(im['rows'])
    shots_of = {}
    for s in d['samples']:
        shots_of.setdefault(s['img'], set()).add(s['rel'])
    t0 = time.time()
    M = {}                                          # (i, j) → IoU（同 kind）
    for i, a in enumerate(imgs):
        for j in range(i + 1, len(imgs)):
            b = imgs[j]
            if a['kind'] != b['kind']:
                continue
            na, nb = a['v'].bit_count(), b['v'].bit_count()
            if min(na, nb) / max(na, nb) < N.PRUNE:
                continue
            M[(i, j)] = M[(j, i)] = N.iou(a['v'], b['v'], a['kind'])
    ms = int((time.time() - t0) * 1000)
    out = {}

    def run(name, pool_of):
        res = {'bag': [0, 0, 0], 'depot': [0, 0, 0], 'family': [0, 0, 0]}   # 對 / 錯 / 判不出（加權：格數）；family = 只差數字的同族名稱（另計）
        wrong = []
        for s in d['samples']:
            i = s['img']
            sc = {}
            for j in pool_of(s):
                v = M.get((i, j), 1.0 if i == j else 0.0)
                lb = imgs[j]['label']
                sc[lb] = max(sc.get(lb, 0.0), v)
            nm, b, sec = _decide(sc)
            r = res['family' if bag.digit_siblings(s['label']) else s['kind']]
            if nm is None:
                r[2] += 1
            elif nm == s['label']:
                r[0] += 1
            else:
                r[1] += 1
                wrong.append((s['rel'], s['slot'], s['label'], nm, round(b, 3)))
        out[name] = res
        print(f'  {name}：背包 對 {res["bag"][0]} / 錯 {res["bag"][1]} / 判不出 {res["bag"][2]}；'
              f'倉庫 對 {res["depot"][0]} / 錯 {res["depot"][1]} / 判不出 {res["depot"][2]}；'
              f'同族名稱（N轉新手禮盒，同族沒學齊一律判不出）對 {res["family"][0]} / 錯 {res["family"][1]} / 判不出 {res["family"][2]}', wrong[:3])
        return res
    same_kind = {k: [j for j, im in enumerate(imgs) if im['kind'] == k] for k in ('bag', 'depot')}
    print(f'  名字圖 {len(imgs)} 張、樣本 {len(d["samples"])} 格；兩兩 IoU {len(M) // 2} 組 {ms} ms')
    # LOSO：樣板 = 出現在其他截圖的名字圖（同點陣只要別張截圖也有就算）
    r = run('留一張截圖（LOSO）', lambda s: [j for j in same_kind[s['kind']] if shots_of[j] - {s['rel']}])
    check('LOSO：0 誤認（含同族名稱）、背包 / 倉庫（同族名稱另計）各至少 95% 認對', r['bag'][1] == 0 and r['depot'][1] == 0 and r['family'][1] == 0
          and r['bag'][0] >= 0.95 * sum(r['bag']) and r['depot'][0] >= 0.95 * sum(r['depot']), r)
    r = run('留一張名字圖（同點陣全拿掉）', lambda s: [j for j in same_kind[s['kind']] if j != s['img']])
    check('留一張名字圖：0 誤認', r['bag'][1] == 0 and r['depot'][1] == 0 and r['family'][1] == 0, r)
    r = run('開集（整個名稱拿掉）', lambda s: [j for j in same_kind[s['kind']] if imgs[j]['label'] != s['label']])
    check('開集：名稱不在樣板 → 全部判不出（0 誤認）', r['bag'][0] == 0 and r['bag'][1] == 0 and r['depot'][1] == 0 and r['depot'][0] == 0
          and r['family'][0] == 0 and r['family'][1] == 0, r)
    # 不同名最高分（安全距離）
    worst = max((v for (i, j), v in M.items() if imgs[i]['label'] != imgs[j]['label']), default=0)
    check(f'不同名最高 IoU {worst:.3f} < HIT_MIN {N.HIT_MIN} - 0.1', worst < N.HIT_MIN - 0.1, worst)
    return out


# ---- 2. learn_rows ----
def test_learn_rules(d):
    imgs = d['images']
    bag_imgs = [im for im in imgs if im['kind'] == 'bag']
    a = next(im for im in bag_imgs if im['label'] == '巴巴洛的許可證')
    b = next(im for im in bag_imgs if im['label'] == '風的鎖[風]')
    tpl = {'bag': {}, 'depot': {}}
    check('learn_rows：新名稱 → 學', N.learn_rows(a['rows'], 'bag', a['label'], tpl))
    check('learn_rows：同一張點陣再學 → 不重複', not N.learn_rows(a['rows'], 'bag', a['label'], tpl))
    check('learn_rows：同點陣標成別的名稱（標籤可疑）→ 不學', not N.learn_rows(a['rows'], 'bag', '風的鎖', tpl) and '風的鎖' not in tpl['bag'], tpl['bag'].keys())
    check('learn_rows：另一個名稱 → 學', N.learn_rows(b['rows'], 'bag', b['label'], tpl))
    check('learn_rows：名稱帶不帶 [風] 視為同名 → 併到同一本', not N.learn_rows(b['rows'], 'bag', '風的鎖', tpl) and len(tpl['bag']) == 2, list(tpl['bag']))
    blank = ['0' * 104] * 52
    check('learn_rows：白點不足（名字關著）→ 不學', not N.learn_rows(blank, 'bag', '龍王的守護', tpl))
    many = [im for im in bag_imgs if im['label'] == '龍王的守護']
    t2 = {'bag': {}, 'depot': {}}
    n = sum(N.learn_rows(im['rows'], 'bag', '龍王的守護', t2) for im in many)
    check(f'learn_rows：變體上限 MAX_VARIANTS（龍王的守護 {len(many)} 張不同點陣）', len(t2['bag']['龍王的守護']) == min(n, N.MAX_VARIANTS) <= N.MAX_VARIANTS, n)
    nm = N.match_rows(a['rows'], 'bag', tpl)
    check('match_rows：學過的點陣 → 認得、分數 1.0', nm['name'] == '巴巴洛的許可證' and nm['score'] == 1.0, nm)


# ---- 3. 合成畫面 ----
EMPTY = (104, 74, 49)


def synth(cells: dict, dark=()):
    """cells = {(kind, 格): 二值列} → get(x, y)：名字白點 = 白、其他 = 空格棕；dark 的背包格內緣壓暗（模擬橫幅蓋住）"""
    px = {}
    for (kind, slot), rows in cells.items():
        _, cx, cy = N.cells_of(kind)[slot]
        dx, dy, w, h = N.BOXES[kind]
        for j, r in enumerate(rows):
            for i, ch in enumerate(r):
                if ch == '1':
                    px[(cx + dx + i, cy + dy + j)] = (255, 255, 255)
    for slot in dark:
        _, cx, cy = N.cells_of('bag')[slot]
        for x in range(cx - 44, cx + 46):
            for y in range(cy - 40, cy + 40):
                px.setdefault((x, y), (60, 42, 28))

    def get(x, y):
        return px.get((x, y), EMPTY)
    return get


def pick(d, label, kind='bag', slot=None):
    """名稱 → (格號, 點陣)：取該名稱在樣本中出現的格（slot 指定就要同格），點陣用那格的"""
    for s in d['samples']:
        if s['label'] == label and s['kind'] == kind and (slot is None or s['slot'] == slot):
            return s['slot'], d['images'][s['img']]['rows']
    raise KeyError(label)


def seed_tpl(d, kinds=('bag', 'depot')):
    """暫存樣板 = fixtures 全部點陣（testenv 已把 TPL_DIR 轉到暫存）"""
    p = N.tpl_path()
    if p.exists():
        p.unlink()
    N._CACHE.clear()
    return N.seed(log=lambda m: None)


def clear_tpl():
    p = N.tpl_path()
    if p.exists():
        p.unlink()
    N._CACHE.clear()


def test_read_page(d):
    seed_tpl(d)
    sa, ra = pick(d, '巴巴洛的許可證')
    sb, rb = pick(d, '龍王的守護', slot=next(s['slot'] for s in d['samples'] if s['label'] == '龍王的守護' and s['kind'] == 'bag' and s['slot'] != sa))
    get = synth({('bag', sa): ra, ('bag', sb): rb})
    pg = N.read_page(get, 'bag')
    check('read_page：兩格名字都認得、其他格空', pg['names'] == {sa: '巴巴洛的許可證', sb: '龍王的守護'} and pg['occ'].count(True) == 2, pg['names'])
    get = synth({('bag', sa): ra, ('bag', sb): rb}, dark=(sb,))
    pg = N.read_page(get, 'bag')
    check('read_page：被蓋住的格 → occluded、不給名字（不判）', pg['cells'][sb]['state'] == 'occluded' and sb not in pg['names'] and pg['occ'][sb] is None,
          pg['cells'][sb])
    noname = [r.replace('1', '0') for r in ra]
    noname[44] = '0' * 40 + '1' * 20 + '0' * 44                         # 只剩一點點白（圖示本身的白點）
    get = synth({('bag', sa): noname, ('bag', sb): [r.replace('1', '0') for r in rb]})
    gx = get

    def get2(x, y):                                                       # 讓格子判成「有道具」：格心附近畫圖示色
        _, cx, cy = N.cells_of('bag')[sa]
        _, cx2, cy2 = N.cells_of('bag')[sb]
        for X, Y in ((cx, cy), (cx2, cy2)):
            if abs(x - X) <= 20 and abs(y - Y) <= 20:
                return (200, 40, 40)
        return gx(x, y)
    pg = N.read_page(get2, 'bag')
    check('read_page：有道具但白點不足 → noname、hidden（顯示道具名關著）', pg['hidden'] and all(c['state'] == 'noname' for c in pg['cells'].values()),
          {i: c['state'] for i, c in pg['cells'].items()})
    clear_tpl()


# ---- 3b. 只差數字的同族名稱（2026-10-15 PrimalSA2：1轉新手禮盒被共用樣板「2轉新手禮盒」認走）----
FAMILY_FILE = HERE / 'fixtures' / 'itemname_digit_family.json'


def test_digit_family(d):
    import json
    import bag
    fam = json.loads(FAMILY_FILE.read_text(encoding='utf-8'))
    one = N.rows_decode(fam['images'][0]['b64'], 'bag')
    two = next(im['rows'] for im in d['images'] if im['label'] == '2轉新手禮盒' and im['kind'] == 'bag')
    three = next(im['rows'] for im in d['images'] if im['label'] == '3轉新手禮盒' and im['kind'] == 'bag')
    hx = lambda rows: format(petmatch.pack(rows), 'x')   # noqa: E731

    # bag：同族判定 + name_match 數字嚴格
    sib = bag.digit_siblings('1轉新手禮盒')
    check('digit_siblings：1轉新手禮盒 → 2～5轉新手禮盒（Item 表）', {'2轉新手禮盒', '3轉新手禮盒', '4轉新手禮盒', '5轉新手禮盒'} <= set(sib) and '1轉新手禮盒' not in sib, sib)
    check('digit_siblings：迎新助力禮盒 / 龍王的守護（沒有數字）→ []', bag.digit_siblings('迎新助力禮盒') == [] and bag.digit_siblings('龍王的守護') == [])
    check('digit_siblings：石幣2萬 → 含石幣3萬', '石幣3萬' in bag.digit_siblings('石幣2萬'))
    check('name_match：彈窗「1轉新手禮盒」≠ 要的「2轉新手禮盒」（舊版相似度 0.83 → 誤判吻合）',
          not bag.name_match('1轉新手禮盒', '2轉新手禮盒') and not bag.name_match('2轉新手禮盒', '1轉新手禮盒'))
    check('name_match：同族名稱 OCR 漏掉數字（「轉新手禮盒」）→ 不算吻合', not bag.name_match('轉新手禮盒', '2轉新手禮盒'))
    check('name_match：同族名稱數字對、其他字錯一個 → 吻合', bag.name_match('2轉新手禮 盒', '2轉新手禮盒') and bag.name_match('2轉新乎禮盒', '2轉新手禮盒'))
    check('name_match：沒有同族的名稱照舊寬鬆（「倍智慧果」吻合 2倍智慧果、首 / 百混淆）',
          bag.name_match('倍智慧果', '2倍智慧果') and bag.name_match('薩姆百爾的百飾', '薩姆吉爾的首飾'))

    # 名字樣板：舊版判法會認成 2轉（重現）；新版 → 不確定
    iou12 = N.iou(petmatch.pack(one), petmatch.pack(two), 'bag')
    check(f'重現：1轉 vs 2轉樣板 IoU {iou12:.3f} > HIT_MIN（一個數字的差別整名 IoU 分不出）', iou12 > N.HIT_MIN, iou12)
    tpl = {'bag': {'2轉新手禮盒': [hx(two)], '3轉新手禮盒': [hx(three)]}, 'depot': {}}
    old = namematch.decide(N.scores(petmatch.pack(one), 'bag', tpl), N.HIT_MIN, N.MARGIN)[0]
    check('重現：舊判法（namematch.decide）把 1轉認成 2轉新手禮盒', old == '2轉新手禮盒', old)
    r = N.match_rows(one, 'bag', tpl)
    check('新判法：1轉、同族沒學齊 → name None、near 2轉新手禮盒（不確定，交給縮圖 / OCR / 彈窗）', r['name'] is None and r['near'] == '2轉新手禮盒', r)
    r = N.match_rows(two, 'bag', tpl)
    check('新判法：2轉自己（IoU 1.0）但 1 / 4 / 5轉沒學過 → 一樣不確定（取捨：寧可多開一次彈窗）', r['name'] is None and r['near'] == '2轉新手禮盒', r)
    full = {'bag': {f'{k}轉新手禮盒': [hx(v)] for k, v in ((1, one), (2, two), (3, three))}, 'depot': {}}
    for k in (4, 5):                                       # 4 / 5轉沒有實樣：用 3轉點陣去掉一半當代用（只要「學過」且不像）
        full['bag'][f'{k}轉新手禮盒'] = [hx([row[:52] + '0' * 52 if j % k else row for j, row in enumerate(three)])]
    for n in bag.digit_siblings('1轉新手禮盒'):
        full['bag'].setdefault(n, [hx(['0' * 104] * 52)])   # 其他同族（若 Item 表有）：空圖佔位 = 學過但完全不像
    r1, r2 = N.match_rows(one, 'bag', full), N.match_rows(two, 'bag', full)
    check('同族全學過：1轉 → 1轉新手禮盒、2轉 → 2轉新手禮盒（逐點相同 ≥ EXACT_MIN 且贏兄弟）',
          r1['name'] == '1轉新手禮盒' and r2['name'] == '2轉新手禮盒', (r1, r2))
    near = [('0' * 30 + r[30:]) if j % 2 == 0 else r for j, r in enumerate(one)]   # 左半（數字那段）掉一半的點 → 不是逐點相同
    v = N.iou(petmatch.pack(near), petmatch.pack(one), 'bag')
    r = N.match_rows(near, 'bag', full)
    check(f'同族全學過但不夠像（IoU {v:.3f} < EXACT_MIN）→ 不確定', v < N.EXACT_MIN and r['name'] is None, (v, r))
    r = N.match_rows(one, 'bag', {'bag': {'迎新助力禮盒': [hx(one)]}, 'depot': {}})
    check('沒有數字的名稱照舊（樣板名不屬同族）→ 認得', r['name'] == '迎新助力禮盒', r)

    # learn_rows：同族可以並存；逐點相同 = 標籤矛盾 → 刪兄弟變體、不學
    t = {'bag': {'2轉新手禮盒': [hx(two)]}, 'depot': {}}
    check('learn_rows：1轉（與 2轉樣板 IoU 0.89 ≥ HIT_MIN）是同族 → 可以學（舊版判「標籤可疑」永遠學不進來）',
          N.learn_rows(one, 'bag', '1轉新手禮盒', t) and set(t['bag']) == {'1轉新手禮盒', '2轉新手禮盒'}, list(t['bag']))
    t = {'bag': {'2轉新手禮盒': [hx(two)], '風的鎖': [hx(three)]}, 'depot': {}}
    msgs = []
    check('learn_rows：2轉的點陣標成「1轉」（與 2轉樣板逐點相同）→ 不學、刪掉 2轉那個變體（兩個標籤必有一個錯）',
          not N.learn_rows(two, 'bag', '1轉新手禮盒', t, log=msgs.append) and '2轉新手禮盒' not in t['bag'] and '1轉新手禮盒' not in t['bag']
          and '風的鎖' in t['bag'] and msgs, (list(t['bag']), msgs))

    # read_page：uncertain 狀態 + near
    clear_tpl()
    N.save_tpl({'bag': {'2轉新手禮盒': [hx(two)], '3轉新手禮盒': [hx(three)]}, 'depot': {}})
    get = synth({('bag', 5): one})
    pg = N.read_page(get, 'bag')
    check('read_page：1轉格 → state uncertain、names 不列、near 2轉新手禮盒', pg['cells'][5]['state'] == 'uncertain' and 5 not in pg['names']
          and pg['near'] == {5: '2轉新手禮盒'}, (pg['cells'].get(5), pg['near']))
    clear_tpl()

    # icon_label：同圖多名一定標「(同圖)」，工作集的名稱排前面
    c = {'name': None, 'names': ['不明禮盒A', '迎新助力禮盒', '1轉新手禮盒', '2轉新手禮盒'], 'ambiguous': True}
    lb = bag.icon_label(c, ['迎新助力禮盒', '1轉新手禮盒', '2轉新手禮盒'])
    check('icon_label：工作集多個同圖名 → 「迎新助力禮盒/1轉新手禮盒/2轉新手禮盒…(同圖)」', lb == '迎新助力禮盒/1轉新手禮盒/2轉新手禮盒…(同圖)', lb)
    check('item_pool：迎新助力禮盒、1轉 / 2轉新手禮盒都在（同圖 50055，工作集只有 2轉時迎新被標成 2轉）',
          {'迎新助力禮盒', '1轉新手禮盒', '2轉新手禮盒'} <= set(bag.item_pool()))


# ---- 4. bag.py 接線 ----
def test_bag(d):
    import bag
    import uikit
    import test_bag_icon as TB
    keep_mode = bag.ITEM_MATCH
    keep_ims = bag.icon_match_slots
    sa, ra = pick(d, '巴巴洛的許可證')
    sk, rk = pick(d, '風的鎖[風]', slot=next(s['slot'] for s in d['samples'] if s['label'] == '風的鎖[風]' and s['kind'] == 'bag' and s['slot'] != sa))
    get = synth({('bag', sa): ra, ('bag', sk): rk})

    # name 模式 + 樣板：零 OCR、零彈窗
    seed_tpl(d)
    bag.ITEM_MATCH = 'name'
    bag._CUR.clear(), bag._SHOT.clear()
    st = TB.install(get)
    r = bag._names_in_bag(['巴巴洛的許可證', '風的鎖', '龍王的守護'])
    check('name 模式：名字樣板找到兩樣、找不到的 None、零 OCR、1 張截圖', r['found'] == {'巴巴洛的許可證': sa, '風的鎖': sk, '龍王的守護': None}
          and r['by'] == {'巴巴洛的許可證': 'name', '風的鎖': 'name'} and not st['ocr'] and st['shots'] == 1 and r['free'] == 13, r)
    st = TB.install(get, popups={sa: '巴巴洛的許可證'})
    i = bag.find_item('巴巴洛的許可證')
    check('find_item：名字樣板認出 → 直接回格號（不開彈窗；動作前呼叫端照舊核對）', i == sa and not st['popup'], (i, st['popup']))
    d2 = bag.read_bag_items()
    check('list：名字樣板的格 by name、名稱是樣板標籤', d2['by'] == {sa: 'name', sk: 'name'} and d2['slots'][sa] == '巴巴洛的許可證', d2)
    check('item_slots：名字樣板命中', bag.item_slots('風的鎖') == [sk])

    # auto 模式、沒有樣板 → 彈窗核對後學會 → 第二次直接認得
    clear_tpl()
    bag.ITEM_MATCH = 'auto'
    bag._CUR.clear(), bag._SHOT.clear()
    st = TB.install(get, popups={sa: '巴巴洛的許可證', sk: '風的鎖[風]'})
    bag.icon_match_slots = lambda want, depot=False: None              # 沒圖示樣板 → 走格名 OCR（讀不到）→ 逐格彈窗
    i = bag.find_item('巴巴洛的許可證')
    check('auto 沒樣板：逐格彈窗找到（照舊路徑）', i == sa and sa in st['popup'], st['popup'])
    check('彈窗核對過 → 學會那格名字樣板', N.n_templates(N.load_tpl(reload=True)) == 1 and '巴巴洛的許可證' in N.load_tpl()['bag'], N.load_tpl()['bag'].keys())
    st = TB.install(get, popups={sa: '巴巴洛的許可證'})
    bag.icon_match_slots = lambda want, depot=False: None
    i = bag.find_item('巴巴洛的許可證')
    check('第二次：名字樣板直接認出、不開彈窗、不 OCR', i == sa and not st['popup'] and not st['ocr'], (i, st))

    # OCR 精確命中 Item 表 → 學
    clear_tpl()
    bag._SHOT.clear()
    st = TB.install(get, texts={sk: '風的鎖 [風]', sa: '巴巴洛的許 可證'})
    d3 = bag.read_bag_items()
    tp = N.load_tpl(reload=True)['bag']
    check('list：OCR 精確命中 Item 表（兩行 / 帶 [風]）→ 兩格都學', set(map(bag.norm_name, tp)) == {'巴巴洛的許可證', '風的鎖'}, (list(tp), d3['by']))
    clear_tpl()
    bag._SHOT.clear()
    st = TB.install(get, texts={sa: '巴巴洛的許'})
    bag.read_bag_items()
    check('OCR 只讀到片段（不是 Item 表名稱）→ 不學', not N.load_tpl(reload=True)['bag'])
    check('ocr_exact_name：「巴巴洛的許 可證」→ 巴巴洛的許可證；「巴巴洛的許」→ None',
          bag.ocr_exact_name('巴巴洛的許 可證') == '巴巴洛的許可證' and bag.ocr_exact_name('巴巴洛的許') is None)

    # 不學的情形
    clear_tpl()
    bag._CUR.clear(), bag._SHOT.clear()
    TB.install(get)
    bag.icon_read('bag', ['巴巴洛的許可證'], pool=[])
    bag._CUR['role'] = 'DKBO2'                                          # 截圖之後換了人
    check('換角色後的舊截圖 → 不學', not bag._learn_verified('bag', sa, '巴巴洛的許可證'))
    bag._CUR.clear()
    bag.icon_read('bag', ['巴巴洛的許可證'], pool=[])
    keep_clock = uikit.clock
    t = uikit.clock()
    uikit.clock = lambda: t + bag.ITEM_SHOT_MAX_AGE_S + 1
    check('截圖太舊 → 不學', not bag._learn_verified('bag', sa, '巴巴洛的許可證'))
    uikit.clock = keep_clock
    bag.icon_read('bag', ['巴巴洛的許可證'], pool=[])
    bag._SHOT['bag']['cells'][sa] = {'ok': True, 'by': 'icon', 'names': ['龍王的守護', '合成石7'], 'name': None}
    check('縮圖認出的圖不屬於這個名稱 → 不學', not bag._learn_verified('bag', sa, '巴巴洛的許可證'))
    bag.icon_read('bag', ['巴巴洛的許可證'], pool=[])
    check('空格 → 不學', not bag._learn_verified('bag', 14, '巴巴洛的許可證'))
    check('核對過的格 → 學', bag._learn_verified('bag', sa, '巴巴洛的許可證'))
    check('同點陣標成別的名稱 → 不學（標籤可疑）', not bag._learn_verified('bag', sa, '風的鎖'))
    # 只差數字的同族名稱（2026-10-15）：格名 OCR 的數字不可靠 → OCR 來源不學；彈窗核對過才學
    import json
    one = N.rows_decode(json.loads(FAMILY_FILE.read_text(encoding='utf-8'))['images'][0]['b64'], 'bag')
    clear_tpl()
    bag._CUR.clear(), bag._SHOT.clear()
    TB.install(synth({('bag', sa): one}))
    bag.icon_read('bag', ['1轉新手禮盒'], pool=[])
    check('同族名稱：格名 OCR 精確命中（「1轉新手禮盒」）→ 不學（OCR 常把 1 / 2 讀錯）', not bag._learn_verified('bag', sa, '1轉新手禮盒', 'OCR '))
    check('同族名稱：彈窗核對過 → 學', bag._learn_verified('bag', sa, '1轉新手禮盒'))
    import actlog
    check('學到名字樣板 → 寫操作 log（itemname 類，帶角色 / 來源；之前只印 stderr，錯樣板查不到來源）',
          any('itemname' in ln and '1轉新手禮盒' in ln and '彈窗核對' in ln for ln in actlog.LOG.read_text(encoding='utf-8').splitlines()))
    # list：名字樣板分不清的同族格標成不確定
    clear_tpl()
    N.save_tpl({'bag': {'2轉新手禮盒': [format(petmatch.pack(pick(d, '2轉新手禮盒')[1]), 'x')]}, 'depot': {}})
    bag._CUR.clear(), bag._SHOT.clear()
    bag.ITEM_MATCH = 'name'
    TB.install(synth({('bag', sa): one}))
    d4 = bag.read_bag_items()
    check('list（name 模式）：1轉格不被認成 2轉、列在 uncertain（near 2轉新手禮盒）', sa not in d4['slots'] and sa in d4['uncertain'] and sa in d4['unread'], d4)
    r = bag._names_in_bag(['2轉新手禮盒'])
    check('find（name 模式）：要找 2轉、背包只有 1轉 → 找不到（舊版：名字樣板 IoU 0.89 → 回 1轉那格）', r['found'] == {'2轉新手禮盒': None}, r)
    bag.ITEM_MATCH = 'auto'
    clear_tpl()

    bag.ITEM_MATCH = 'iconocr'
    check('iconocr 模式：不學', not bag._learn_verified('bag', sk, '風的鎖'))

    # iconocr：不看名字樣板（舊 auto）
    seed_tpl(d)
    bag._SHOT.clear()
    st = TB.install(get, texts={sa: '巴巴洛的許可證'})
    r = bag._names_in_bag(['巴巴洛的許可證'])
    check('iconocr 模式：有樣板也不用（by 不是 name）', r['by'].get('巴巴洛的許可證') != 'name', r['by'])

    # 動作前核對不省：use_item 仍開彈窗核對名稱
    bag.ITEM_MATCH = 'name'
    bag._SHOT.clear()
    st = TB.install(get, popups={sa: '風的鎖'})
    bag.open_slot_popup = lambda i, depot=False: (st['popup'].append(i), True)[1]
    bag.popup_name = lambda want=None: '風的鎖'
    rc = bag.use_item('DKBO', '巴巴洛的許可證')
    check('use_item：名字樣板認出的格，彈窗名稱不符 → 96 不按使用', rc == bag.EXIT_NAME and st['popup'] == [sa], (rc, st['popup']))

    bag.ITEM_MATCH = keep_mode
    bag.icon_match_slots = keep_ims
    clear_tpl()


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if '--make-fixtures' in argv:
        return make_fixtures()
    d = N.load_samples()
    if not d['images']:
        print('FAIL 沒有 fixtures/itemname_samples.json')
        return 1
    check('testenv：名字樣板目錄在暫存（不碰 tools/.cache）', 'psatest-' in str(N.TPL_DIR), N.TPL_DIR)
    test_accuracy(d)
    test_learn_rules(d)
    test_read_page(d)
    test_digit_family(d)
    try:
        import itemimg_match
        itemimg_match.index()
        test_bag(d)
    except FileNotFoundError:
        print('SKIP bag 接線測試（沒有 tools/.cache/item-images；先跑 tools/extract/item_images.py）')
    print('全部通過' if not fails else f'{fails} 項失敗')
    return 1 if fails else 0


if __name__ == '__main__':
    sys.exit(main())
