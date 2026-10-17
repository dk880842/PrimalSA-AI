#!/usr/bin/env python3
"""每日任務（委託接取）離線純函式（daily.py 用；離線測試只 import 這支）。只用標準函式庫，不碰遊戲畫面。

內容（notes/plan-daily.md v3 §4.1 / §4.3 / §4.5 / §4.6）：
  知識庫   load_recipes（item-book.md → 配方）、load_stores（npc-shops.md 1009 / 2009 → 店 / 材料歸屬 / 商品順序）
  名稱     norm / snap_item（OCR 讀到的成品名 → 配方表裡的名字；ocrfix 修正 + 相似度，歧義不猜）、vote_lines（多倍率逐倍率 snap 投票）、
           resolve_name / match_mats / snap_mats / digit_family（名稱不確定 → 快速合成彈窗大字 + 材料列核對；同族數字不互認）
           pop_rows / pop_mats / mats_fit / pop_check / arrow_on（快速合成彈窗第二輪：材料列整欄分列、▼ 捲動合併、依序比對配方、要有大字證據）
  計畫     plan_role（每人 10 項 → 每環是否支援、薩村 / 漁村 / 胡椒購買清單、石幣估算）、store_route（店順序 = 店員 y 由小到大）
  背包模型 Ledger（背包 / 個人倉庫 / 公倉的材料種類與數量；**不讀背包 / 倉庫格數**，改用「背包材料種類上限 BAG_KINDS_MAX」模型決定何時存倉）、
           choose_evict / make_room（放不下時存最晚環才用到的種類）、craftable / ring_ready（可合成 / 可提交判斷）
  進度檔   team_path / role_path（每視窗各自）、load / save（原子寫入）、check_date（跨 00:00 → 220）
  退出碼   EXIT_*（220～229，見 §4.5）

鐵則 3（每日任務例外，使用者 2026-10-17）：整個流程不讀石幣、不讀鑽石；本檔只做石幣「估算」給人看。
**未實機**：一切離線。
"""
import collections
import difflib
import json
import os
import re
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
import clients  # noqa: E402
import ocrfix  # noqa: E402

# ---- 退出碼（共用 0 / 1 / 2 / 8 / 9 / 10 見 uikit；本檔 220～229，2026-10-17 grep 過沒人用）----
EXIT_ARGS, EXIT_NOBUY, EXIT_PEPPER, EXIT_PREP, EXIT_WALK, EXIT_READ, EXIT_NOROLE, EXIT_BUY, EXIT_DEPOT, EXIT_CRAFT = range(220, 230)
EXIT_NAMES = {
    EXIT_ARGS: '參數 / 沒名單 / 今天全部已完成 / 跨過 00:00', EXIT_NOBUY: '要花石幣但沒給 --confirm-buy', EXIT_PEPPER: '計畫用到胡椒但公倉取不到',
    EXIT_PREP: '停練功 / 傳送 / 解散 / 組隊 / 切當前角色失敗', EXIT_WALK: '走不到醫院 / 1009 / 2009 或委託面板開不了', EXIT_READ: '讀清單失敗',
    EXIT_NOROLE: '某人全部環都不支援', EXIT_BUY: '購買失敗', EXIT_DEPOT: '個人倉庫 / 公倉存取失敗', EXIT_CRAFT: '合成 / 提交失敗',
}

STAGES = ('prep', 'read', 'plan', 'sam', 'mid', 'fish', 'final', 'finish')
SAM_MAP, FISH_MAP = 1009, 2009
MAP_STAGE = {SAM_MAP: 'sam', FISH_MAP: 'fish'}
PEPPERS = ('普通的胡椒', '黑胡椒', '香味濃厚的胡椒')     # 胡椒 1～3（12174～12176）不在 1009 / 2009 店賣；使用者先放公共倉庫，腳本只取用、用剩存回，絕不買。
                                                        # 塔姆塔姆產的胡椒（12177，胡椒 4）2825 地方特產品販賣員有賣 → 不在這裡，load_stores 當一般材料照買
BAG_KINDS_MAX = 13                                      # 背包同時放的材料 / 成品種類上限（背包可見 15 格，留 2 格給合成成品；fork 同值）
MAT_PRICE, CRAFT_PRICE = 500, 1000
RINGS = 5
PRODUCT_PREFIX = '成品:'                                 # Ledger 裡合成成品（尚未提交）的鍵前綴：佔背包格、不可存倉

NPC_SHOPS = ROOT / 'knowledge' / 'economy' / 'npc-shops.md'
ITEM_BOOK = ROOT / 'knowledge' / 'crafting' / 'item-book.md'


# ---------------- 名稱 ----------------
def norm(name) -> str:
    """去空白（遊戲顯示「合成爪 7」、item-book 也是；比對一律去空白）"""
    return re.sub(r'\s+', '', str(name or ''))


# ---------------- 知識庫 ----------------
class Store:
    __slots__ = ('name', 'npc', 'map', 'x', 'y', 'items')

    def __init__(self, name, npc, map_, x, y, items=None):
        self.name, self.npc, self.map, self.x, self.y = name, npc, map_, x, y
        self.items = items or []                 # 商品順序（遊戲清單順序：2 欄先左後右）

    def __repr__(self):
        return f'Store({self.name}#{self.npc}@{self.map} {self.x},{self.y} ×{len(self.items)})'


def load_recipes(path=None) -> dict:
    """item-book.md → {成品名(去空白): [[(材料, 數量)...], ...]}（同名可能多組）；材料名也去空白"""
    out = collections.defaultdict(list)
    for ln in Path(path or ITEM_BOOK).read_text(encoding='utf-8').splitlines():
        m = re.match(r'\|\s*\d+\s*\|[^|]*\|\s*(.+?)\((\d+)\)\s*\|\s*(.+?)\s*\|', ln)
        if not m:
            continue
        mats = []
        for part in m.group(3).split('、'):
            mm = re.match(r'(.+?)\(\d+\)×(\d+)$', part.strip())
            if mm:
                mats.append((norm(mm.group(1)), int(mm.group(2))))
        if mats:
            out[norm(m.group(1))].append(mats)
    return dict(out)


def load_stores(path=None, maps=(SAM_MAP, FISH_MAP)) -> tuple:
    """npc-shops.md → ({npc: Store}, {材料(去空白): npc})。只收 maps（1009 / 2009）；同一材料多店賣取檔案裡最先出現的"""
    stores, where, cur = {}, {}, None
    for ln in Path(path or NPC_SHOPS).read_text(encoding='utf-8').splitlines():
        m = re.match(r'## (.+?) \(NPC (\d+)\) @ (.+?)\((\d+)\) (\d+),(\d+)', ln)
        if m:
            cur = Store(m.group(1), int(m.group(2)), int(m.group(4)), int(m.group(5)), int(m.group(6))) if int(m.group(4)) in maps else None
            if cur:
                stores[cur.npc] = cur
            continue
        m = re.match(r'\| (.+?) \| \d+ \| \d+ 石幣', ln)
        if m and cur:
            nm = norm(m.group(1))
            cur.items.append(nm)
            where.setdefault(nm, cur.npc)
    return stores, where


def snap_item(text, known, cutoff: float = 0.8):
    """OCR 讀到的成品 / 材料名 → known（配方表鍵）裡的名字。ocrfix 修正 + 去空白後：完全相等 → 該名；
    否則相似度 ≥ cutoff 且**唯一最高**（第二名差 < 0.05 視為歧義）才吻合；數字不同的同族名（合成爪 7 / 合成爪 3）不互認。讀不到 / 歧義 → None"""
    t = norm(ocrfix.fix(text))
    if not t:
        return None
    known = list(known)
    if t in known:
        return t
    dt = re.findall(r'\d+', t)
    scored = []
    for k in known:
        dk = re.findall(r'\d+', k)
        if dt != dk and (dt or dk):
            continue
        scored.append((difflib.SequenceMatcher(None, t, k).ratio(), k))
    scored.sort(reverse=True)
    if not scored or scored[0][0] < cutoff:
        return None
    if len(scored) > 1 and scored[0][0] - scored[1][0] < 0.05:
        return None
    return scored[0][1]


def vote_lines(lines, known, cutoff: float = 0.8) -> dict:
    """OCR 原始行（uikit.ocr_lines；-Zooms 多倍率時每行帶 zoom）→ **逐倍率各自拼行再 snap，投票**。
    舊讀法把各倍率結果 ''.join 成一串（例「合成弓箭8口成弓箭8」= 2 倍 + 3 倍疊字）→ snap 全不過（2026-10-17 p1 225；離線量 50 項只 3 項過）。
    lines 也可給字串（單行，測試 / 舊呼叫端）或 None。回 dict：
      name      唯一得票名（多個倍率 snap 到不同名 = conflict → None）
      votes     {名: 票數}；texts 各倍率原字（報錯用）
      sure      name 有、沒衝突，且名字不含數字或至少 2 個倍率同意（數字尾碼「合成爪 7 / 3」單票不算確定 → 呼叫端開彈窗核對材料列）"""
    if lines is None:
        lines = []
    elif isinstance(lines, str):
        lines = [{'text': lines}]
    groups = collections.defaultdict(list)
    for ln in lines:
        if isinstance(ln, str):
            ln = {'text': ln}
        if str(ln.get('text', '')).strip():
            groups[ln.get('zoom')].append(ln)
    votes, texts = collections.Counter(), []
    for z in sorted(groups, key=str):
        t = ''.join(str(ln.get('text', '')) for ln in sorted(groups[z], key=lambda ln: ln.get('x') or 0))
        texts.append(t)
        nm = snap_item(t, known, cutoff)
        if nm:
            votes[nm] += 1
    name = next(iter(votes)) if len(votes) == 1 else None
    sure = bool(name) and (not re.search(r'\d', name) or votes[name] >= 2)
    return {'name': name, 'votes': dict(votes), 'conflict': len(votes) > 1, 'sure': sure, 'texts': texts}


def digit_family(name, known) -> list:
    """同族只差數字的名字（合成爪 7 → 合成爪 1～10）；名字不含數字 → [name]"""
    n = norm(name)
    if not re.search(r'\d', n):
        return [n]
    skel = re.sub(r'\d+', '#', n)
    return sorted({k for k in known if re.sub(r'\d+', '#', k) == skel} | {n})


def mat_names(recipes: dict) -> list:
    """配方表出現過的所有材料名（快速合成彈窗材料列 snap 用）"""
    return sorted({n for cands in recipes.values() for c in cands for n, _ in c})


def snap_mats(texts, recipes: dict) -> list:
    """彈窗材料列 OCR（每列一個字串或 ocr_lines 清單）→ 材料名；「石幣」列與讀不出的列略過"""
    known = mat_names(recipes)
    out = []
    for t in texts or []:
        v = vote_lines(t, known)
        if v['name'] and v['name'] not in out:
            out.append(v['name'])
    return out


# 快速合成彈窗材料列（2026-10-17 第二輪，p1 樣本 99 張：5 人 × 10 項 + 捲動版）：
#   版面：列表視野 y 228～630，列距 92；最多 4 列完整 + 半列；材料依 item-book 配方順序排，最後一列「石幣 1000」（綠字）。
#   超過 4 列 → 下緣黃色 ▼（(820,626) 一帶）；捲動後上緣出現黃色 ▲（(820,242) 一帶）。**短清單被拖過也會冒 ▲、而且蓋住第 1 列右半**
#   （「有光澤的地瓜」只剩「有光澤的」→ 會 snap 成「有光澤的皮」），所以 ▲ 亮時 y < POP_ARROW_TOP 的行一律不收。
#   紅字計數「0/1」Windows OCR 讀不到（不二值化 / -Dark / -Light 都不行）→ 數量不從畫面核對（每日成品配方的材料幾乎都 ×1；配方吻合 = 名稱與順序都對）。
POP_MAT_ROWS = 4                  # 一眼看得到的完整材料列數（含「石幣」列；5 種材料 + 石幣要捲動）
POP_LIST_BAND = (240, 600)        # 材料名行中心 y 的有效範圍（下緣半列 y≈620 不收）
POP_ARROW_TOP = 275               # ▲ 亮時，y 小於這個的行（被 ▲ 蓋住的第 1 列）不收
COIN = '石幣'


def arrow_on(colors) -> bool:
    """▼ / ▲ 取樣點（黃 251,228,20 一帶）任一亮 → True。colors = [(r, g, b)...]；None / 空 → False"""
    return any(c and c[0] > 200 and c[1] > 150 and c[2] < 100 for c in (colors or []))


def _has_cjk(t) -> bool:
    return any('一' <= ch <= '鿿' for ch in str(t or ''))


def pop_rows(lines, recipes: dict, up: bool = False) -> list:
    """彈窗材料列「高框一次讀」的 OCR 原始行（每行帶 y / zoom）→ 由上到下的列名（材料名或「石幣」）。
    同一列（各倍率 y 差 ≤ 20）合併後逐倍率投票（vote_lines）；只有數字的行（「1000」）、讀不出的列略過；up = ▲ 亮 → 第 1 列被蓋住的行不收"""
    known = mat_names(recipes) + [COIN]
    top = max(POP_LIST_BAND[0], POP_ARROW_TOP if up else 0)
    ls = sorted((ln for ln in (lines or []) if isinstance(ln, dict) and _has_cjk(ln.get('text'))
                 and top <= (ln.get('y') or 0) <= POP_LIST_BAND[1]), key=lambda ln: ln.get('y') or 0)
    groups = []
    for ln in ls:
        if groups and abs((ln.get('y') or 0) - (groups[-1][-1].get('y') or 0)) <= 20:
            groups[-1].append(ln)
        else:
            groups.append([ln])
    out = []
    for g in groups:
        nm = vote_lines(g, known)['name']
        if nm and nm not in out:
            out.append(nm)
    return out


def pop_mats(pop: dict, recipes: dict) -> dict:
    """彈窗讀值 → {'seq': [材料名（由上到下）], 'complete': 看到整張清單（從第 1 列到「石幣」）}。
    pop 鍵：list（材料列高框 OCR 原始行）、up（▲ 亮）、down（▼ 亮）；捲一次後再讀的 list2 / up2（可無）。
    舊格式 mats = [每列 OCR 原始行或字串]（離線測試 / 舊 fixture）也收：有讀到「石幣」列 = complete。
    第一張（剛開彈窗、▲ 不亮）看到石幣 → complete；▼ 亮 = 還有更多 → 有 list2（捲到底、看到石幣）就把兩張依序合併（重疊的列只算一次）"""
    pop = pop or {}
    if pop.get('list') is None and pop.get('mats') is not None:
        known = mat_names(recipes) + [COIN]
        rows = []
        for t in pop.get('mats') or []:
            nm = vote_lines(t, known)['name']
            if nm and nm not in rows:
                rows.append(nm)
        return {'seq': [r for r in rows if r != COIN], 'complete': COIN in rows}
    up = bool(pop.get('up'))
    rows = pop_rows(pop.get('list'), recipes, up)
    seq = [r for r in rows if r != COIN]
    complete = COIN in rows and not up
    if not complete and not up and pop.get('list2') is not None:
        rows2 = pop_rows(pop.get('list2'), recipes, bool(pop.get('up2')))
        if COIN in rows2:
            seq = seq + [r for r in rows2 if r != COIN and r not in seq]
            complete = True
    return {'seq': seq, 'complete': complete}


def _as_info(mats) -> dict:
    """match_mats / resolve_name 的材料參數：pop_mats 的 dict，或舊的材料名 list（有「石幣」= 看到整張）"""
    if isinstance(mats, dict):
        return mats
    mats = [m for m in (mats or []) if m]
    return {'seq': [m for m in mats if m != COIN], 'complete': COIN in mats}


def _subseq(a, b) -> bool:
    """a 是 b 的「依序子序列」（中間可略過讀不出的列，但順序不能亂）"""
    it = iter(b)
    return all(x in it for x in a)


def mats_fit(name, mats, recipes: dict):
    """材料列和 name 的配方比：'full'（看到整張且名稱、順序完全相同）/ 'partial'（沒看全：讀到的都在配方裡且順序對）/
    False（矛盾：有配方外的材料、順序不對，或看到整張卻和配方不同 —— 列讀漏也算，寧可停手）/ None（沒讀到任何材料列）。
    同名多組配方取最好的那組。數量不比：item-book 裡「材料名單相同、數量不同」的配方 0 組（2026-10-17 查），名單吻合 = 數量也吻合"""
    info = _as_info(mats)
    seq = list(info.get('seq') or [])
    if not seq:
        return None
    best = False
    for rec in recipes.get(norm(name), []):
        names = [n for n, _ in rec]
        if seq == names and info.get('complete'):
            return 'full'
        if not info.get('complete') and _subseq(seq, names):
            best = 'partial'
    return best


def match_mats(cands, mats, recipes: dict) -> list:
    """候選成品裡材料列吻合的那些：有 'full' 的只回 full 的；沒有才回 'partial' 的（mats = pop_mats 結果或材料名 list）"""
    fits = {norm(c): mats_fit(c, mats, recipes) for c in cands}
    full = [c for c, f in fits.items() if f == 'full']
    return full or [c for c, f in fits.items() if f == 'partial']


def resolve_name(panel: dict, pop: dict, mats, recipes: dict):
    """面板名稱不確定時的第二層（快速合成彈窗）：panel / pop = vote_lines 結果，mats = pop_mats 結果（或材料名 list）。
    有讀到材料列 → 候選（兩邊得票名 + 同族只差數字的名）裡材料吻合的**唯一**一個；材料列讀不到 → 只在面板與彈窗大字同名、
    或彈窗大字 sure 且面板沒投給別的名字時才接受。其他一律 None（呼叫端 225，不猜）"""
    names = set(panel.get('votes') or {}) | set(pop.get('votes') or {})
    pool = sorted({f for n in names for f in digit_family(n, recipes)})
    ok = set(pool)
    if _as_info(mats).get('seq'):
        m = match_mats(pool, mats, recipes)
        if len(m) == 1:
            return m[0]
        ok = {c for c in pool if mats_fit(c, mats, recipes)}      # 材料列漏讀 / 沒看全：至少不能和配方矛盾
    nm = pop.get('name')
    if nm not in ok:
        return None
    if panel.get('name') == nm and not panel.get('conflict') and not pop.get('conflict'):
        return nm
    if pop.get('sure') and set(panel.get('votes') or {}) <= {nm}:
        return nm
    return None


def pop_check(name, pop: dict, recipes: dict):
    """合成前核對快速合成彈窗是不是 name → True / False / None（看不全 / 大字讀不到、還不能確定 → 呼叫端 ▼ 亮就捲一次再讀，仍 None 就不合成）。
    pop = {'name': 大字原始行, 'list' / 'up' / 'down' / 'list2' / 'up2'（見 pop_mats）}（舊格式 'mats' 也收）。
    **一定要有大字證據**：item-book 有 38 組「材料完全相同」的不同成品（厚肉塊串燒 / 鹽味獸肉串燒、葉子烤蕃薯 / 半熟的芋頭、
    合成投擲斧頭 N / 合成斧頭 N、合成石 N / 合成迴旋標 N、合成兜 N / 合成鎧 N…），只看材料會互認。
      大字有倍率投給 name 同族（只差數字）以外的成品 → False；材料列和配方矛盾 → False
      大字沒有任何倍率讀到同族名 → None
      同族數字（合成爪 1～10）：材料列在同族裡唯一吻合 name → True（大字數字讀錯以材料為準）
      無數字名：大字得票 = name 且材料 full / partial → True；沒讀到材料列 → 大字 sure 才 True"""
    n = norm(name)
    fam = digit_family(n, recipes)
    gv = vote_lines((pop or {}).get('name'), recipes)
    if any(v not in fam for v in gv['votes']):
        return False
    info = pop_mats(pop, recipes)
    fit = mats_fit(n, info, recipes)
    if fit is False:
        return False
    if not gv['votes']:
        return None
    if fit is None:
        return True if (gv['name'] == n and gv['sure']) else None
    if len(fam) > 1:
        return True if match_mats(fam, info, recipes) == [n] else None
    return True


def pop_is(name, pop: dict, recipes: dict) -> bool:
    """pop_check 為 True 才算（False / None 都不合成）"""
    return pop_check(name, pop, recipes) is True


# ---------------- 計畫 ----------------
def pick_recipe(item, recipes: dict, where: dict) -> tuple:
    """成品名 → (材料 list [(名, 數)], None) 或 (None, 原因)。優先「全部材料在 1009 / 2009 店或是胡椒」的那組；都不行 → 不支援（合成品材料 / 遠程店）"""
    cands = recipes.get(norm(item), [])
    if not cands:
        return None, f'知識庫查不到「{item}」的配方'
    bad = None
    for c in cands:
        miss = [n for n, _ in c if n not in where and n not in PEPPERS]
        if not miss:
            return list(c), None
        bad = bad or miss
    return None, f'「{item}」的材料 {"、".join(bad)} 不在 1009 / 2009 店（合成品 / 遠程店；第一版不支援）'


def plan_role(items, recipes: dict, where: dict, stores: dict, done=None) -> dict:
    """items = 5 環 × [上, 下] 成品名（讀不到 None）；done = 5 環 × [bool, bool]（已 1/1 綠，不用再做）。
    → {'rings': [{'ring': n, 'items': [{'name','mats','reason','done'} ×2], 'supported', 'reason'}],
       'buy': {'sam': {材料: 量}, 'fish': {…}}, 'pepper': {材料: 量}, 'first_use': {材料: 最早用到的環},
       'cost': {'mat','craft','total'}（估算）, 'supported_rings': [n…]}
    一環只要有一項不支援 → 整環跳過（兩項都不買）；環不用依序（遊戲沒規定）"""
    done = done or [[False, False] for _ in range(RINGS)]
    rings, buy = [], {'sam': collections.Counter(), 'fish': collections.Counter()}
    pepper, first_use = collections.Counter(), {}
    n_craft = 0
    for ri in range(RINGS):
        pair = list(items[ri]) if ri < len(items) else [None, None]
        its, reasons = [], []
        for k in range(2):
            nm = pair[k] if k < len(pair) else None
            d = bool(done[ri][k]) if ri < len(done) else False
            if not nm:
                its.append({'name': None, 'mats': None, 'reason': '沒讀到名稱', 'done': d})
                reasons.append('沒讀到名稱')
                continue
            mats, why = pick_recipe(nm, recipes, where)
            its.append({'name': norm(nm), 'mats': mats, 'reason': why, 'done': d})
            if why:
                reasons.append(why)
        ok = not reasons
        rings.append({'ring': ri + 1, 'items': its, 'supported': ok, 'reason': '；'.join(reasons) or None})
        if not ok:
            continue
        for it in its:
            if it['done']:
                continue
            n_craft += 1
            for n, q in it['mats']:
                first_use.setdefault(n, ri + 1)
                if n in PEPPERS:
                    pepper[n] += q
                else:
                    buy[MAP_STAGE[stores[where[n]].map]][n] += q
    n_mat = sum(sum(c.values()) for c in buy.values())
    return {'rings': rings, 'buy': {k: dict(v) for k, v in buy.items()}, 'pepper': dict(pepper), 'first_use': first_use,
            'cost': {'mat': n_mat * MAT_PRICE, 'craft': n_craft * CRAFT_PRICE, 'total': n_mat * MAT_PRICE + n_craft * CRAFT_PRICE},
            'supported_rings': [r['ring'] for r in rings if r['supported']]}


def store_route(stage: str, wanted: dict, where: dict, stores: dict, first_use: dict | None = None) -> list:
    """某段要買的 {材料: 量} → [(Store, [(材料, 量)…])]：店順序 = 店員 y 由小到大（全在 x=27 一直線，走一趟不折返）；
    店內材料順序 = 該店商品清單 index 由小到大（= 遊戲清單由上往下、2 欄先左後右；2026-10-17 修 227：舊版「早環先買」讓清單靠前的商品
    排在後面買、已被往下捲出視野 → 選不到）。first_use 保留參數但不再影響順序；背包放不下的存倉由 make_room / choose_evict（看 _next_use）決定，與購買順序無關"""
    per = collections.defaultdict(list)
    for n, q in wanted.items():
        if q > 0 and n in where:
            per[where[n]].append((n, q))
    out = []
    for npc in sorted(per, key=lambda k: (stores[k].y, stores[k].x)):
        st = stores[npc]
        out.append((st, sorted(per[npc], key=lambda nq: (st.items.index(nq[0]) if nq[0] in st.items else 999, nq[0]))))
    return out


def remaining_buy(plan: dict, stage: str, bought: dict) -> dict:
    """該段還要買的 {材料: 量}（扣掉進度檔 bought 已核對買到的）"""
    out = {}
    for n, q in (plan['buy'].get(stage) or {}).items():
        r = q - int((bought or {}).get(n, 0))
        if r > 0:
            out[n] = r
    return out


def plan_lines(role: str, plan: dict, stores: dict, where: dict) -> list:
    """給人看的計畫（印出用）"""
    out = [f'{role}：支援的環 {plan["supported_rings"] or "（無）"}；石幣估算 材料 {plan["cost"]["mat"]:,} + 合成 {plan["cost"]["craft"]:,} = {plan["cost"]["total"]:,}']
    for r in plan['rings']:
        names = ' / '.join((i['name'] or '?') + ('（已完成）' if i['done'] else '') for i in r['items'])
        out.append(f'  第 {r["ring"]} 環：{names}' + ('' if r['supported'] else f'  → 跳過：{r["reason"]}'))
    for stage, label in (('sam', '薩姆吉爾 1009'), ('fish', '瑪麗娜絲 2009')):
        route = store_route(stage, plan['buy'].get(stage) or {}, where, stores, plan['first_use'])
        kinds = sum(len(v) for _, v in route)
        out.append(f'  {label}：{kinds} 種 / {sum(q for _, v in route for _, q in v)} 個，{len(route)} 間店')
        for st, v in route:
            out.append(f'    {st.name}（{st.npc} @{st.x},{st.y}）：' + '、'.join(f'{n}×{q}' for n, q in v))
    if plan['pepper']:
        out.append('  胡椒（公共倉庫取用、用剩存回，不買）：' + '、'.join(f'{n}×{q}' for n, q in plan['pepper'].items()))
    return out


# ---------------- 背包 / 倉庫模型 ----------------
class Ledger:
    """材料帳：bag / personal / public 各 {名稱: 量}。**不讀遊戲、純記帳**（購買驗證後 buy、存倉驗證後 evict、取出驗證後 take、合成後 craft）。
    背包「格數」用種類數近似（Item overlay=1 的都疊成 1 格）；成品（PRODUCT_PREFIX）佔格、不可存倉。"""

    def __init__(self, d: dict | None = None):
        d = d or {}
        self.bag = collections.Counter(d.get('bag') or {})
        self.personal = collections.Counter(d.get('personal') or {})
        self.public = collections.Counter(d.get('public') or {})

    def to_dict(self) -> dict:
        return {'bag': dict(self.bag), 'personal': dict(self.personal), 'public': dict(self.public)}

    def kinds(self) -> int:
        return sum(1 for v in self.bag.values() if v > 0)

    def buy(self, mat: str, q: int) -> None:
        self.bag[mat] += q

    def evict(self, mat: str, sub: str) -> int:
        """整疊（背包 → sub 倉庫）；回搬運量"""
        q = self.bag.pop(mat, 0)
        if q:
            getattr(self, sub)[mat] += q
        return q

    def take(self, mat: str, sub: str) -> int:
        """整疊（sub 倉庫 → 背包）；公倉胡椒是使用者放的，帳上沒有量 → 回 0 但呼叫端仍視為取到（take_pepper）"""
        q = self.__dict__[sub].pop(mat, 0)
        if q:
            self.bag[mat] += q
        return q

    def craft(self, mats, product: str) -> bool:
        """扣材料、加成品；背包材料不夠 → False（不動）。胡椒（公倉取來的整疊，帳上量未知）不扣"""
        for n, q in mats:
            if n not in PEPPERS and self.bag.get(n, 0) < q:
                return False
        for n, q in mats:
            if n not in PEPPERS:
                self.bag[n] -= q
                if self.bag[n] <= 0:
                    del self.bag[n]
        self.bag[PRODUCT_PREFIX + product] += 1
        return True

    def consume(self, mats) -> list:
        """手動合成補記用：材料已被用掉，帳上依 背包 → 個人倉庫 → 公倉 扣（胡椒不扣）；回帳上找不到的 [(名稱, 缺量)]"""
        miss = []
        for n, q in mats:
            if n in PEPPERS:
                continue
            for box in (self.bag, self.personal, self.public):
                take = min(q, box.get(n, 0))
                if take:
                    box[n] -= take
                    q -= take
                    if box[n] <= 0:
                        del box[n]
            if q > 0:
                miss.append((n, q))
        return miss

    def submit(self, products) -> None:
        for p in products:
            k = PRODUCT_PREFIX + p
            self.bag[k] -= 1
            if self.bag[k] <= 0:
                del self.bag[k]

    def holds(self, mat: str) -> str | None:
        """材料現在在哪：'bag' / 'personal' / 'public' / None（背包優先）"""
        for sub in ('bag', 'personal', 'public'):
            if getattr(self, sub).get(mat, 0) > 0:
                return sub
        return None


def need_of_unfinished(plan: dict, rings_state: list) -> dict:
    """尚未合成的項目（支援的環、未提交）還需要的材料 {材料: 量}（胡椒也算）"""
    out = collections.Counter()
    for r, st in zip(plan['rings'], rings_state):
        if not r['supported'] or st.get('submitted'):
            continue
        for k, it in enumerate(r['items']):
            if it['done'] or st['crafted'][k]:
                continue
            for n, q in it['mats']:
                out[n] += q
    return dict(out)


def _next_use(plan: dict, rings_state: list, mat: str) -> int:
    """材料最早還要用到的環（沒有 = 99：最先被存倉的候選）"""
    for r, st in zip(plan['rings'], rings_state):
        if not r['supported'] or st.get('submitted'):
            continue
        for k, it in enumerate(r['items']):
            if it['done'] or st['crafted'][k]:
                continue
            if any(n == mat for n, _ in it['mats']):
                return r['ring']
    return 99


def choose_evict(ledger: Ledger, plan: dict, rings_state: list, protect=()) -> str | None:
    """背包放不下 → 挑要存倉的材料：不含成品 / protect；「最晚才用到」的環優先（沒用到 = 最優先）；同分取名稱大者（確定性）。沒得挑 → None"""
    cands = [m for m, v in ledger.bag.items() if v > 0 and not m.startswith(PRODUCT_PREFIX) and m not in protect and m not in PEPPERS]
    if not cands:
        return None
    return max(cands, key=lambda m: (_next_use(plan, rings_state, m), m))


def make_room(ledger: Ledger, plan: dict, rings_state: list, incoming, cap: int = BAG_KINDS_MAX, protect=()) -> list | None:
    """incoming = 即將進背包的材料名；回「要先存倉的材料」順序 list（可空）；挑不出足夠候選 → None。
    只算種類：已在背包的 incoming 不增格；protect ∪ incoming 不被存倉。**不改 ledger**（呼叫端存倉成功才 evict）"""
    inc = set(incoming)
    bag = {m for m, v in ledger.bag.items() if v > 0}
    new = inc - bag
    sim = Ledger(ledger.to_dict())
    out = []
    while sim.kinds() + len(new) > cap:
        m = choose_evict(sim, plan, rings_state, set(protect) | inc)
        if m is None:
            return None
        sim.evict(m, 'personal')
        out.append(m)
    return out


def craftable(it: dict, ledger: Ledger, bag_only: bool) -> bool:
    """項目（plan 的 item dict）材料是否湊齊：bag_only（mid）= 只算背包、不含胡椒；否則（final）背包 + 倉庫都算，胡椒視為公倉有"""
    for n, q in it['mats']:
        if n in PEPPERS:
            if bag_only:
                return False
            continue
        have = ledger.bag.get(n, 0) if bag_only else sum(getattr(ledger, s).get(n, 0) for s in ('bag', 'personal', 'public'))
        if have < q:
            return False
    return True


def ring_ready(st: dict, items: list) -> bool:
    """該環兩項都已完成（crafted 或遊戲已 1/1 綠）→ 可提交"""
    return all(it['done'] or st['crafted'][k] for k, it in enumerate(items)) and not st.get('submitted')


# ---------------- 畫面讀值（純函式；像素 / OCR 文字 → 判斷）----------------
def count_state(rgb) -> str:
    """委託面板每項計數「0/1」的字色：紅（0/1，255,0,0）→ 'red'；綠（1/1，估 135,255,91，**綠色值未實機量過**）→ 'green'；其他 / None → '?'"""
    if not rgb:
        return '?'
    r, g, b = rgb[:3]
    if r > 200 and g < 70 and b < 70:
        return 'red'
    if g > 140 and r < 190 and b < 170:
        return 'green'
    return '?'


def green_strict(rgb) -> bool:
    """委託面板計數的綠字（1/1，估 135,255,91）嚴格版：G 要明顯高過 R、B。
    count_state 的寬鬆綠（g>140 且 r<190）會把面板米色底的暗邊（例 170,150,120）也當綠 → 字區多點取樣不能用它。"""
    if not rgb:
        return False
    r, g, b = rgb[:3]
    return g > 180 and g - r > 50 and g - b > 60


def count_area(colors, min_n: int = 3) -> str:
    """委託面板一項計數「0/1」/「1/1」第一個字的字區多點顏色（daily.STATE_GRID）→ 'red' | 'green' | '?'。
    紅點（255,0,0 系）≥ min_n → red；否則嚴格綠點 ≥ min_n → green；其他 '?'（看不出就當不知道，呼叫端照舊流程）。
    為什麼不用單點：舊 STATE_PX 390,291 落在「0」的左筆畫，「1/1」的「1」是細直筆，單點很可能落在米色底（2026-10-17 dev-pop-live 量紅字字區 x 390～398 × y 284～299）"""
    cs = [c for c in (colors or []) if c]
    if sum(1 for c in cs if count_state(c) == 'red') >= min_n:
        return 'red'
    if sum(1 for c in cs if green_strict(c)) >= min_n:
        return 'green'
    return '?'


def mark_item(st: dict, ring_plan: dict, k: int, what: str) -> str:
    """進度檔補記一項已完成（面板已 1/1 綠 / 手動補完）。st = 每人進度、ring_plan = plan_role 的該環、k = 0 上 / 1 下。
    crafted：rings[].crafted[k] = True；帳上照合成扣材料、加成品；背包帳上不夠 → Ledger.consume 依 背包 → 個人倉庫 → 公倉 扣
      （人手動合成前一定已把料取到背包；帳不扣的話後面存倉 / 取倉會找不到東西 → 92 / 228），扣完歸 0 的從 in_personal / in_public 拿掉。
    submitted：整環（k 不看）兩項沒記 crafted 的先照 crafted 記、再 submitted = True、帳上扣成品。回一行說明（已記過回空字串）"""
    rs = st['rings'][ring_plan['ring'] - 1]
    led = Ledger(st.get('ledger'))
    notes = []

    def craft_one(i):
        it = ring_plan['items'][i]
        if it.get('done') or rs['crafted'][i]:
            return
        if not led.craft(it.get('mats') or [], it['name']):
            miss = led.consume(it.get('mats') or [])
            led.bag[PRODUCT_PREFIX + it['name']] += 1
            notes.append(f'「{it["name"]}」材料從背包 / 倉庫帳上扣' + (f'（帳上沒有：{"、".join(f"{n}×{q}" for n, q in miss)}，只加成品）' if miss else ''))
        rs['crafted'][i] = True
        notes.append(f'「{it["name"]}」記為已合成')
    if what == 'crafted':
        if rs.get('submitted') or ring_plan['items'][k].get('done') or rs['crafted'][k]:
            return ''
        craft_one(k)
    elif what == 'submitted':
        if rs.get('submitted'):
            return ''
        for i in range(len(ring_plan['items'])):
            craft_one(i)
        led.submit([it['name'] for it in ring_plan['items'] if not it.get('done')])
        rs['submitted'] = True
        notes.append(f'第 {ring_plan["ring"]} 環記為已提交')
    else:
        raise ValueError(f'mark 只收 crafted / submitted：{what}')
    st['ledger'] = led.to_dict()
    used = {n for it in ring_plan['items'] for n, _ in (it.get('mats') or [])}
    for key, box in (('in_personal', led.personal), ('in_public', led.public)):
        if key in st:                                   # 只動這環材料：倉庫帳扣到 0 的從清單拿掉
            st[key] = [n for n in st[key] if n not in used or box.get(n, 0) > 0]
    return '；'.join(notes)


def popup_short(colors) -> bool:
    """快速合成彈窗右側計數（材料列的「0/1」整串紅字）任一格是紅 → 材料不足（不按彈窗「合成」）。colors = 各列計數位置的 (r, g, b) list"""
    return any(count_state(c) == 'red' for c in (colors or []))


def parse_reward(text) -> int | None:
    """「完成所有任務額外獎勵 n/5」計數框 OCR → n（0～5）；多倍率重複 / 夾雜字都容忍；讀不到 None"""
    m = re.findall(r'([0-5])\s*[/／]\s*5', str(text or ''))
    return int(m[-1]) if m else None


def parse_page(text) -> int | None:
    """頁碼框「n/5」OCR → n（1～5）；讀不到 None"""
    m = re.findall(r'([1-5])\s*[/／]\s*5', str(text or ''))
    return int(m[-1]) if m else None


# ---------------- 進度檔 ----------------
def today(now=None) -> str:
    return time.strftime('%Y-%m-%d', now if now else time.localtime())


def team_path() -> Path:
    return clients.cpath('daily-team.json')


def role_path(role: str) -> Path:
    return clients.cpath(f'daily-{role}.json')


def load(path) -> dict | None:
    try:
        d = json.loads(Path(path).read_text(encoding='utf-8'))
        return d if isinstance(d, dict) else None
    except (OSError, ValueError):
        return None


def save(path, obj: dict) -> None:
    """原子寫入（先寫 .tmp 再 replace；中途被砍不會留半個檔）"""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(p.suffix + '.tmp')
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=1), encoding='utf-8')
    os.replace(tmp, p)


def new_role_state(role: str, date: str | None = None) -> dict:
    return {'role': role, 'date': date or today(), 'read': False, 'items': [], 'done': [], 'reward': None,
            'rings': [{'crafted': [False, False], 'submitted': False} for _ in range(RINGS)],
            'bought': {}, 'ledger': Ledger().to_dict(), 'in_personal': [], 'in_public': [], 'stages': {}}


def new_team_state(roles, date: str | None = None) -> dict:
    return {'date': date or today(), 'roles': list(roles), 'stage': 'prep', 'skipped': []}


def load_role(role: str, date: str | None = None, fresh: bool = False) -> dict:
    """讀本人進度；沒有 / 不是今天（且不 fresh 的跨日由呼叫端先 check_date）/ fresh → 新的。**跨日的舊檔不在這裡丟**：呼叫端用 check_date 決定停手或 --fresh"""
    d = None if fresh else load(role_path(role))
    return d if d else new_role_state(role, date)


def stale(state: dict | None, now_date: str | None = None) -> bool:
    """進度檔日期不是今天（遊戲每日 0 點環數清 0）"""
    return bool(state) and state.get('date') != (now_date or today())


def check_date(state: dict | None, now_date: str | None = None) -> bool:
    """True = 還是同一天（沒檔案也算）；False = 跨過 00:00 → 呼叫端回 220 停手、不自動重讀"""
    return not stale(state, now_date)


def stage_index(name: str) -> int:
    return STAGES.index(name)
