#!/usr/bin/env python3
"""每日任務（委託接取）離線純函式（daily.py 用；離線測試只 import 這支）。只用標準函式庫，不碰遊戲畫面。

內容（notes/plan-daily.md v3 §4.1 / §4.3 / §4.5 / §4.6）：
  知識庫   load_recipes（item-book.md → 配方）、load_stores（npc-shops.md 1009 / 2009 → 店 / 材料歸屬 / 商品順序）
  名稱     norm / snap_item（OCR 讀到的成品名 → 配方表裡的名字；ocrfix 修正 + 相似度，歧義不猜）
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
PEPPERS = ('普通的胡椒', '黑胡椒', '香味濃厚的胡椒')     # 不在 1009 / 2009 店賣；使用者先放公共倉庫，腳本只取用、用剩存回，絕不買
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
    店內材料順序 = 最早用到的環先、其次清單順序（早環材料先買，背包要放不下時被存倉的是晚環的）"""
    fu = first_use or {}
    per = collections.defaultdict(list)
    for n, q in wanted.items():
        if q > 0 and n in where:
            per[where[n]].append((n, q))
    out = []
    for npc in sorted(per, key=lambda k: (stores[k].y, stores[k].x)):
        st = stores[npc]
        out.append((st, sorted(per[npc], key=lambda nq: (fu.get(nq[0], 99), st.items.index(nq[0]) if nq[0] in st.items else 999))))
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
