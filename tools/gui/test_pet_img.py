#!/usr/bin/env python3
"""pet.py ↔ petimg_match 接線離線測試（不碰遊戲）：名字 / 登錄檔認不出時縮圖比知識庫頭像的備援。
用法：uv run --no-project python tools/gui/test_pet_img.py
需要 tools/.cache/pet-images（tools/extract/pet_images.py 匯出）與 tools/.cache/bn_0.png；沒有就整個略過（回 0）。
驗：list 讀格會填 img_species / species_src='img'、不寫進 species（store / set-state 身分不變）、騎寵只會更嚴、None 不猜、
take 的補充驗名（img_target）只在名字框認不出時生效、IMG_ON 關掉不讀。"""
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import testenv  # noqa: E402,F401  紀錄檔轉向暫存
import petimg_match as M  # noqa: E402
import petmatch  # noqa: E402
import pngread  # noqa: E402
import uikit  # noqa: E402
import pet  # noqa: E402

CACHE = HERE.parents[1] / 'tools' / '.cache'
fails = 0


def check(name, cond, extra=''):
    global fails
    print(('PASS' if cond else 'FAIL'), name, extra)
    if not cond:
        fails += 1


def ctx0():
    """受控 ctx：沒有名字樣板、空的物種登錄檔 → 第一輪候選只有騎寵 + IMG_EXTRA"""
    return {'tpl': {'name': {}}, 'learn': False, 'dirty': False, 'reg': {'thumb': {}, 'growth': {}}}


def use_shot(path):
    """uikit.px 改讀截圖（記讀點數 / 次數）"""
    w, h, bpp, rows = pngread.decode(Path(path).read_bytes())
    get = M.rows_getter(rows, bpp)
    stat = {'calls': 0, 'pts': 0}

    def px(pts):
        pts = list(pts)
        stat['calls'] += 1
        stat['pts'] += len(pts)
        return [get(x, y) for x, y in pts]
    uikit.px = px
    return stat


def fake_grab(state='等待'):
    """名字框 / 等級框全空（名字讀不出、等級讀不出），狀態鈕 state 亮"""
    def grab(specs, extra=()):
        rows = [['0' * w] * h for _, _, w, h, _ in specs]
        cols = []
        for s in pet.STATES:
            cols += [(150, 100, 50) if s == state else (230, 200, 150)] * 2
        return rows, cols[:len(extra)]
    return grab


def main() -> int:
    if not (M.IMG_DIR / 'index.tsv').exists() or not (CACHE / 'bn_0.png').exists():
        print('SKIP 沒有 tools/.cache/pet-images 或 bn_0.png')
        return 0
    pet.IMG_ON = True
    petmatch.grab = fake_grab('等待')
    stat = use_shot(CACHE / 'bn_0.png')

    # ---- read_slot：名字讀不出 → 縮圖認物種（只放 img_*，不進 species）----
    ctx = ctx0()
    t0 = time.time()
    d = pet.read_slot(0, ctx)                 # bn_0 格 1 = 瑪斯貝卡（在第一輪候選）
    ms1 = (time.time() - t0) * 1000
    check('格 1 名字讀不出 → img 瑪斯貝卡', d.get('img_species') == '瑪斯貝卡' and d.get('species_src') == 'img', {k: d.get(k) for k in ('img_species', 'img_score', 'img_stage')})
    check('img 結果不寫進 species', 'species' not in d or d['species'] is None)
    check('img 認成騎寵 → mountlike（更嚴）', d['mountlike'] is True)
    check('img-only 格沒有身分（slot_ident None → store / set-state 找不到）', pet.slot_ident(d) is None)
    why = pet.guard_store(d, allow_slot1=True)
    check('img-only 格存倉一律拒絕（附註只供參考）', bool(why) and '只供參考' in why, why)
    check('find_slot 用物種名找不到 img-only 格', pet.find_slot([d], '瑪斯貝卡', None)[0] is None)
    check('一格只讀一次 px（read_cell 整格）', stat['calls'] == 1 and stat['pts'] > 4000, stat)
    print(f'     格 1 比對 {ms1:.0f} ms（{d.get("img_stage")}），讀 {stat["pts"]} 點')

    stat.update(calls=0, pts=0)
    t0 = time.time()
    d = pet.read_slot(1, ctx)                 # 格 2 = 奇寶（不在第一輪候選 → 放寬到全部 Monster）
    ms2 = (time.time() - t0) * 1000
    check('不在已知清單 → 放寬全部 Monster 認出奇寶', d.get('img_species') == '奇寶' and d.get('img_stage') == 'all', {k: d.get(k) for k in ('img_species', 'img_score', 'img_stage')})
    check('非騎寵 img 不影響 mountlike', d['mountlike'] is False)
    print(f'     格 2 比對 {ms2:.0f} ms（all）')

    # 已知清單有兄弟（火雞系）時第二輪加同系別：名字樣板學過「奇寶」→ 格 3 克克洛斯 不會被認成奇寶
    ctx2 = ctx0()
    ctx2['tpl'] = {'name': {'奇寶': []}}
    d = pet.read_slot(2, ctx2)
    check('第二輪同系別：克克洛斯 不被兄弟奇寶頂替', d.get('img_species') == '克克洛斯' and d.get('img_stage') == 'family', {k: d.get(k) for k in ('img_species', 'img_score', 'img_stage')})

    # ---- None 不猜：畫面跟任何頭像都對不起來 ----
    uikit.px = lambda pts: [(30, 160, 30)] * len(list(pts))
    d = pet.read_slot(3, ctx0())
    check('對不起來 → img_species None、沒有 species_src', d.get('img_species') is None and 'species_src' not in d, {k: d.get(k) for k in ('img_best', 'img_score', 'img_stage')})
    check('None 時 mountlike 照舊 False', d['mountlike'] is False)
    use_shot(CACHE / 'bn_0.png')

    # ---- 騎乘狀態的騎寵判斷不受 img 影響（狀態=騎乘照擋）----
    petmatch.grab = fake_grab('騎乘')
    d = pet.read_slot(4, ctx0())              # 格 5 火雞，狀態騎乘
    check('狀態騎乘照擋存倉（img 是火雞也一樣）', d['state'] == '騎乘' and 'guard' not in d and '騎乘' in (pet.guard_store({**d, 'name': '火雞'}, True) or ''))
    petmatch.grab = fake_grab('等待')

    # ---- 名字 / 登錄檔認得 → 不呼叫 img ----
    called = []
    real = pet.img_ident
    pet.img_ident = lambda *a, **k: called.append(a) or None
    ctx3 = ctx0()
    ctx3['reg'] = {'thumb': {}, 'growth': {'49/9/8/2': '布拉奇多斯'}}
    real_ri = pet.resolve_ident
    pet.resolve_ident = lambda rows, c: {'name': None, 'via': 'growth', 'raw': None, 'growth': '49/9/8/2'}
    real_is = pet.ident_species
    pet.ident_species = lambda i, g, c: '布拉奇多斯'
    d = pet.read_slot(0, ctx3)
    check('登錄檔認得 → species_src reg、不呼叫 img', d.get('species') == '布拉奇多斯' and d.get('species_src') == 'reg' and not called)
    pet.resolve_ident = lambda rows, c: {'name': '朵拉比斯', 'via': 'tpl', 'raw': None, 'growth': None}
    d = pet.read_slot(1, ctx3)
    check('名字樣板認得 → 不呼叫 img', d['name'] == '朵拉比斯' and not called)
    pet.resolve_ident, pet.ident_species, pet.img_ident = real_ri, real_is, real

    # ---- IMG_ON 關 → 不讀 ----
    pet.IMG_ON = False
    stat = use_shot(CACHE / 'bn_0.png')
    check('IMG_ON=False → img_ident None、零 px', pet.img_ident('slot', 0, ctx0()) is None and stat['calls'] == 0)
    pet.IMG_ON = True

    # ---- take 補充驗名 img_target（倉庫卡；bn_0 卡 2 = 克邦凱斯）----
    c = ctx0()
    unk = {'name': None, 'growth': '50/10/6/9'}
    info = {}
    check('卡片沒名字 + 字串沒登錄 + 縮圖 = 目標 → True', pet.img_target('card', 1, unk, {'name': '克邦凱斯'}, c, info) is True, info.get('img'))
    check('縮圖 ≠ 目標 → False', pet.img_target('card', 1, unk, {'name': '加格'}, c) is False)
    check('卡片有名字 → 不用 img（False）', pet.img_target('card', 1, {'name': '加格', 'growth': None}, {'name': '克邦凱斯'}, c) is False)
    check('目標指定成長字串 → 不用 img', pet.img_target('card', 1, unk, {'name': '克邦凱斯', 'growth': '50/10/6/9'}, c) is False)
    c['reg'] = {'thumb': {}, 'growth': {'50/10/6/9': '加格'}}
    check('字串已登錄（別的物種）→ 不用 img', pet.img_target('card', 1, unk, {'name': '克邦凱斯'}, c) is False)
    check('target 只有等級 → 不用 img', pet.img_target('card', 1, unk, {'level': 5}, ctx0()) is False)

    # ---- fmt_slot 顯示 ----
    s = pet.fmt_slot({'slot': 1, 'raw_name': '?(49/9/8/2)', 'img_species': '布拉奇多斯', 'img_score': 0.9, 'state': '騎乘', 'level': 126})
    check('fmt_slot 顯示 ≈物種(圖分數)', '≈布拉奇多斯(圖0.90)' in s, s)

    task_candidates()
    print('全部通過' if not fails else f'{fails} 項失敗')
    return 1 if fails else 0


SHARKS = ['克邦凱斯', '加克拉', '加格', '邦恩吉']
TURKEYS = ['火雞', '克克洛斯', '霍爾克', '奇寶']


def task_candidates():
    """--candidates（ctx['img_only']）：卡坦 4 鯊 / 4 雞實機截圖（2026-10-13 卡坦分配時；每人寵物欄 4 隻各一種、任務已交成功）"""
    shots = {'s3.png': (TURKEYS, {1: '火雞', 2: '霍爾克', 3: '奇寶', 4: '克克洛斯'}),
             's5.png': (TURKEYS, {1: '奇寶', 2: '火雞', 3: '克克洛斯', 4: '霍爾克'}),
             'z.png': (SHARKS, {1: '克邦凱斯', 2: '加克拉', 3: '邦恩吉', 4: '加格'})}
    real_ri = pet.resolve_ident
    for fn, (cand, want) in shots.items():
        if not (CACHE / fn).exists():
            print('SKIP 截圖不在', fn)
            continue
        use_shot(CACHE / fn)
        got = {}
        for i in want:
            pet.resolve_ident = lambda rows, c, i=i: {'name': None, 'via': 'growth', 'raw': None, 'growth': f'9/9/9/{i}'}
            c = {**ctx0(), 'img_only': cand}
            got[i] = pet.read_slot(i, c).get('species')
        check(f'--candidates {fn}：沒名字的新寵物在候選內相對比較認出物種（進 species）', got == want, str(got))
        # 登錄檔記的是別隻（成長字串撞號 / 錯標）→ 矛盾 → None（不亂分）
        pet.resolve_ident = lambda rows, c: {'name': None, 'via': 'growth', 'raw': None, 'growth': '1/2/3/4'}
        c = {**ctx0(), 'img_only': cand, 'reg': {'thumb': {}, 'growth': {'1/2/3/4': [n for n in cand if n != want[1]][0]}}}
        d = pet.read_slot(1, c)
        check(f'--candidates {fn}：登錄檔跟縮圖矛盾 → species None', d.get('species') is None, str({k: d.get(k) for k in ('species', 'img_species')}))
        c = {**ctx0(), 'img_only': cand, 'reg': {'thumb': {}, 'growth': {'1/2/3/4': want[1]}}}
        d = pet.read_slot(1, c)
        check(f'--candidates {fn}：登錄檔與縮圖一致 → species_src img+reg', d.get('species') == want[1] and d.get('species_src') == 'img+reg', str(d.get('species_src')))
    pet.resolve_ident = real_ri
    p = CACHE / 'z.png'
    if p.exists():                                            # 候選裡沒有這隻（拿雞的候選看鯊魚）→ 不猜
        use_shot(p)
        pet.resolve_ident = lambda rows, c: {'name': None, 'via': 'growth', 'raw': None, 'growth': '9/9/9/9'}
        d = pet.read_slot(1, {**ctx0(), 'img_only': TURKEYS})
        check('--candidates 候選裡沒有 → species / img_species 都 None', d.get('species') is None and d.get('img_species') is None, str(d.get('img_best')))
        pet.resolve_ident = real_ri
    p = CACHE / 'dep2.png'
    if p.exists():                                            # 倉庫卡（公共）：火雞 / 霍爾克 / 克克洛斯
        use_shot(p)
        c = {**ctx0(), 'img_only': TURKEYS}
        unk = {'name': None, 'growth': '33/7/3/8'}
        got = [pet.img_target('card', k, unk, {'name': n}, c) for k, n in ((0, '火雞'), (1, '霍爾克'), (3, '克克洛斯'), (0, '奇寶'))]
        check('--candidates 倉庫卡 img_target：火雞 / 霍爾克 / 克克洛斯 對、火雞卡不是奇寶', got == [True, True, True, False], str(got))
    # rank_among 主色特徵：鯊魚換色版分差明顯
    if (CACHE / 'z.png').exists():
        w, h, bpp, rows = pngread.decode((CACHE / 'z.png').read_bytes())
        r = M.rank_among(M.rows_getter(rows, bpp), 'slot', M.SLOT_X, M.SLOT_Y[2], SHARKS)
        check('rank_among：加克拉 inlier + 主色都第一（主色分差 ≥ 0.3）', r['species'] == '加克拉' and r['hist'] - r['hist_second'] >= 0.3, str(r['ranked']))


if __name__ == '__main__':
    sys.exit(main())
