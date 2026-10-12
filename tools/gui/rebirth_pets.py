#!/usr/bin/env python3
"""轉生後寵物重整：舊寵物全存個人倉庫 → DKBO2 抓 N 隻騎寵（預設布拉奇多斯）→ 經公共倉庫分給 5 人 → 設騎乘 → 取出戰寵（預設朵拉比斯）設出戰
→ 外掛重新鎖定騎寵 / 戰寵。2026-10-11 第一次手動做完（notes/quest-log.md「轉生後寵物重整」），本檔是把它腳本化。只用標準函式庫。

**實機驗證狀態（2026-10-11 寫成時）**：只有離線測試（test_rebirth_pets.py，假 Tools）。寫的當下遊戲被別的 agent 接手掛機，沒能實機跑。
- 寵物存取 / 設狀態 / 認沒名字的新寵物 = pet.py（pet 的新功能也只有離線驗證；store / take 舊功能實機驗證過）。
- 背包 / 公共倉庫道具 = bag.py（另一位 dev 寫的，同樣沒實機驗證）；**拆分誘餌**（拆分鈕 + 數量鍵盤）是本檔自己寫的，座標取自 notes/plan-dino-katan.md 的手動實測。
- **外掛「捉寵設置」與「鎖定騎寵 / 戰寵」是本檔自己寫的**：座標取自 ui/ass.md 與 plan-dino-katan.md 的手動實測，但下拉清單的「讀字找列」範圍
  （CATCH_LIST_FAMILY / CATCH_LIST_PET / LOCK_LIST_* / 各 OCR 框）是**猜的**，第一次實跑要看 snap 修正；所有點擊前都先 OCR 驗證（讀不到就停、不盲點），
  下拉選項用 ocr.ps1 回傳的文字座標點（不是固定列距）。這些框沒量過 → 標「待實機量」，見 ui/ass.md。

用法（專案根目錄；WSL / Windows 原生指令相同）：
  uv run --no-project python tools/gui/rebirth_pets.py [--trans N] [--mount-species 布拉奇多斯] [--battle-pet 朵拉比斯] [--catcher DKBO2] [--count 5]
        [--family 雷龍系] [--store-mount 瑪斯貝卡] [--from 階段] [--to 階段] [--dry-run] [--no-boxes]
    --trans N          剛轉到第 N 轉（開「N轉新手禮盒」；預設 1；下一個 N+1 轉新手禮盒存個人）
    --mount-species    要抓 / 設騎乘 / 鎖定的物種（預設 布拉奇多斯；也是 pet.py 的 MOUNTS 之一）
    --family           外掛捉寵設置的系別（預設依物種：布拉奇多斯 = 雷龍系；其他物種要明講）
    --battle-pet       戰寵（預設 朵拉比斯，從個人倉庫取、設出戰、鎖定）
    --catcher          負責抓的角色（預設 DKBO2；不是當前角色，勾自動抓寵也照抓）
    --count N          共要幾隻（預設 5，每人 1 隻；DKBO 以外 4 人由公共倉庫分）
    --store-mount 名   **使用者當次明講才用**：舊騎寵（例 瑪斯貝卡）也存個人倉庫（先設等待、再 pet.py store --allow-mount-store）；沒給 = 舊騎寵不碰
    --from 階段        從這個階段開始（中斷後接著做；進度記在 tools/.cache/rebirth_pets.json）；--to 階段 = 做到該階段（含）就停
    --dry-run          只印計畫（階段 / 動作 / 退出碼），完全不碰遊戲
  可 import：rebirth_pets.run(trans=1, ..., tools=None) → 退出碼；結果 dict 在 rebirth_pets.LAST

階段：
  preflight   當前角色 = DKBO（不是就 char.ensure）→ team.disband（沒隊伍 = 不點）→ 外掛鎖定騎寵 / 戰寵 5 人先取消 → 讀 5 人寵物欄（舊寵物清單）
  boxes       5 人各：背包找「N轉新手禮盒」→ 使用 → 內容（寵物誘餌 / 離線水晶8H / 2倍智慧果 / 安撫之素）存公共；「N+1轉新手禮盒」禁止存公共 → 存個人（--no-boxes 跳過）
  store       5 人寵物欄所有寵物存個人倉庫（pet.py store-many；騎寵只在 --store-mount 時、先設等待）
  catch       catcher 從公共取誘餌（拆分只留 1）→ 外掛捉寵設置（系別 → 物種 → 可抓捕數 = 1）→ 勾自動存倉庫 / 自動抓寵 → 等抓完 →
              確認多 1 隻沒名字的新寵物 → pet.py learn-species（登錄縮圖 / 成長字串）→ 再留 N-1 個誘餌重複 → 確認共 N 隻、物種都確認
  distribute  catcher 把 N-1 隻（取最後格）存公共 → 其他 4 人各從公共取 1 隻（pet.py take-many，現場逐張找、沒名字的靠成長字串登錄檔）
  ride        5 人把騎乘物種設騎乘（pet.py set-state --allow-mount）
  battle      5 人從個人倉庫取戰寵（pet.py take-many，現場逐張找名字）→ 設出戰
  lock        5 人外掛：鎖定騎寵 = 騎乘寵（下拉顯示成長字串 → 逐項 OCR 比對再點）、鎖定戰寵 = 戰寵（名字）→ 兩項都勾
  cleanup     catcher 背包多餘誘餌存回公共 → 確認當前 DKBO、遇敵關 → 讀最後寵物欄 → 寫 notes/quest-log.md 摘要

退出碼（共用 0 / 1 / 2 / 8 / 9 / 10 見 uikit；其他工具 40～79 / 80～89 rebirth / 90～96 bag；本檔 100～109）：
  100 preflight 失敗（當前角色切不回 DKBO、解散失敗、外掛解鎖失敗、讀寵物欄失敗）
  101 boxes 失敗（背包 / 倉庫操作，info.bag_rc）
  102 store 失敗（pet.py 退出碼在 info.pet_rc；舊騎寵沒給 --store-mount 又佔位 → 也是 102）
  103 catch 失敗（取誘餌 / 外掛設定 / 抓寵逾時 / 新寵物數量不對 / 物種登錄失敗 / 欄位不夠）
  104 distribute 失敗
  105 ride 失敗
  106 battle 失敗（倉庫沒有戰寵、取出 / 出戰失敗）
  107 lock 失敗（OCR 找不到該下拉選項、勾選點了沒變）
  108 cleanup 失敗
  109 參數 / 進度檔不一致（--from 的階段前置沒做、角色名不認得）
驗證視窗（uikit 回 9）→ 一律回 9 並停手（鐵則 5）；斷線（netwatch halt）→ 10；其他腳本佔用畫面 → 8。

安全：騎寵（uikit.MOUNTS）存倉只在 --store-mount 名字完全相同時放行；不碰捉寵設置的「+」（可抓捕數購買）與「丟棄不滿足條件的寵物」區塊；
  只點讀字確認過的下拉選項；不花石幣 / 鑽石（誘餌用禮盒送的）。
"""
import argparse
import json
import re
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import uikit  # noqa: E402

SRC = 'rebirth_pets'
ROOT = uikit.ROOT
import logpaths  # noqa: E402
EVENT_LOG = logpaths.p(ROOT / 'notes' / 'quest-events.log')
QUEST_LOG = logpaths.p(ROOT / 'notes' / 'quest-log.md')
PROGRESS = logpaths.p(uikit.CACHE / 'rebirth_pets.json')

EXIT_PRE, EXIT_BOX, EXIT_STORE, EXIT_CATCH, EXIT_DIST, EXIT_RIDE, EXIT_BATTLE, EXIT_LOCK, EXIT_CLEAN, EXIT_ARGS = 100, 101, 102, 103, 104, 105, 106, 107, 108, 109

STAGES = ['preflight', 'boxes', 'store', 'catch', 'distribute', 'ride', 'battle', 'lock', 'cleanup']
LEADER = 'DKBO'
ALL_ROLES = ['DKBO', 'DKBO2', 'DKBO3', 'DKBO4', 'DKBO5']
FAMILY_NEIGHBORS = {'鯊魚系': (('犀牛', '牛系'), ('飛天蛙', '飛夭蛙', '蛙系'))}          # 外掛系別清單的上下鄰居（2026-10-12 實機）
SPECIES_ORDER = {'鯊魚系': ['克邦凱斯', '加克拉', '加格', '邦恩吉'], '火雞系': ['火雞', '克克洛斯', '霍爾克', '奇寶']}   # 寵物下拉的列順序（第一列 y=421、列距 42、x=1115）；選中的藍底白字 OCR 讀不到時用位置
FAMILY_OF = {'布拉奇多斯': '雷龍系'}            # 物種 → 外掛捉寵設置的系別（PetData 第 27 組；其他物種用 --family）
BAIT = '寵物誘餌'
BOX_CONTENTS = ['寵物誘餌', '離線水晶8H', '2倍智慧果', '安撫之素']      # 1轉新手禮盒內容（quest-log 實測）；存公共
CATCH_POLL_S, CATCH_TIMEOUT_S = 30.0, 1200.0
LAST: dict = {}

# ---- 外掛座標（ui/ass.md / plan-dino-katan.md 手動實測；2880×1659 截圖座標）----
ASS_TAB = {'general': (850, 212), 'catch': (984, 212)}
LOCK_XY = {'騎寵': {'check': (656, 313), 'dd': (1285, 312)}, '戰寵': {'check': (656, 377), 'dd': (1285, 377)}}
CATCH_XY = {'auto': (656, 315), 'store': (820, 315), 'family_dd': (921, 377), 'pet_dd': (1283, 377), 'scroll': ((750, 650), (750, 480))}
# 下面全是「待實機量」的 OCR 框（x, y, w, h）：讀字用，錯了只會讀不到 → 停手，不會亂點
OCR_TAB_GENERAL = (640, 295, 520, 110)          # 一般設置：含 鎖定騎寵 / 鎖定戰寵 兩列
OCR_TAB_CATCH = (640, 296, 700, 40)             # 捉寵設置：自動抓寵 / 自動存倉庫 / 可抓捕數 那一列
OCR_FAMILY_FIELD = (640, 360, 230, 34)           # 2026-10-12 實機量：欄位 x 637～868（舊框 780 起切掉字）
OCR_PET_FIELD = (1000, 360, 230, 34)              # 欄位 x 1000～1230
CATCH_LIST_FAMILY = (700, 400, 300, 300)        # 系別下拉清單（8 項可見，要拖曳捲）
CATCH_LIST_PET = (1040, 400, 320, 300)          # 寵物下拉清單
LOCK_FIELD_W, LOCK_LIST_W, LOCK_LIST_H = 330, 330, 260   # 鎖定下拉：欄位 / 清單寬高（欄位 x 從 940 起，欄位 y ± 17；清單從欄位下方 +22 起）
LOCK_LIST_X = 940

GROWTH_RE = re.compile(r'(\d{1,3})\s*/\s*(\d{1,3})\s*/\s*(\d{1,3})\s*/\s*(\d{1,3})')


# ---- 純函式（測試直接餵）----
def level_n(trans) -> int:
    return max(1, int(trans))


def box_names(trans: int) -> tuple:
    """(這次要開的禮盒, 開出來的下一個禮盒)"""
    return f'{trans}轉新手禮盒', f'{trans + 1}轉新手禮盒'


def family_for(species: str, family: str | None) -> str | None:
    return family or FAMILY_OF.get(species)


def parse_growth_line(text) -> str | None:
    """一行 OCR 文字 → 'a/b/c/d'（整行恰好是成長字串才算；多一堆別的字 → None）"""
    t = re.sub(r'\s+', '', str(text or ''))
    m = GROWTH_RE.fullmatch(t)
    return '/'.join(str(int(g)) for g in m.groups()) if m else None


def pick_row(lines: list, ident: tuple) -> tuple:
    """下拉選項 [(文字, x, y)] 與身分 ('name', 名) / ('growth', 'a/b/c/d') → (命中的 (文字, x, y) | None, 說明)。
    必須「剛好一列」吻合：名字用 uikit.snap_pet 對到同一個正式名；成長字串整行完全相同。0 列或 ≥ 2 列 → None（不猜）"""
    kind, val = ident
    hits = []
    for t, x, y in lines:
        if kind == 'growth':
            ok = parse_growth_line(t) == val
        else:
            ok = uikit.snap_pet(t) == val
        if ok and not any(abs(y - h[2]) <= 15 for h in hits):          # 多個放大倍數會重複回同一列：y 差 ≤ 15 併成一個（2026-10-12）
            hits.append((t, x, y))
    if len(hits) == 1:
        return hits[0], ''
    return None, f'{kind} {val!r}：下拉讀到 {[t for t, _, _ in lines]}，吻合 {len(hits)} 列（要剛好 1 列）'


def role_ident(slots: list, species: str, battle_pet: str, which: str) -> tuple | None:
    """鎖定下拉要選誰：騎寵 = 該角色寵物欄中物種 = species 的那隻（沒名字 → ('growth', 成長字串)；有名字 → ('name', 名)）；戰寵 = ('name', battle_pet)。
    找不到 / 有多隻 → None"""
    if which == '戰寵':
        return ('name', battle_pet) if any(s.get('name') == battle_pet for s in slots if not s.get('empty')) else None
    hits = [s for s in slots if not s.get('empty') and ((s.get('unnamed') and s.get('species') == species) or s.get('name') == species)]
    if len(hits) != 1:
        return None
    s = hits[0]
    return ('growth', s['unnamed']) if s.get('unnamed') else ('name', s['name'])


def stores_for(slots: list, store_mount: str | None, keep: list | None = None) -> tuple:
    """role 的寵物欄 → (要存的名單 [寵物名], 要先設等待的騎寵名 | None, 留在欄位的清單 [(slot, 原因)])。
    空格略過；有名字的存（同名多隻就重複列）；沒名字但物種已確認的存物種名；沒名字又沒確認 → 留下並回報（不猜）；
    騎寵名單（uikit.MOUNTS）只在 name == store_mount 時存（其餘留下）"""
    names, left, mount = [], [], None
    for s in slots:
        if s.get('empty'):
            continue
        nm = s.get('name') or (s.get('species') if s.get('unnamed') else None)
        if not nm:
            left.append((s['slot'], f'名字讀不出來 / 沒名字且物種未確認：{s.get("raw_name") or "?"}'))
            continue
        if keep and nm in keep:
            left.append((s['slot'], f'{nm} 在 --keep'))
            continue
        if nm in uikit.MOUNTS or s.get('mountlike'):
            if store_mount and nm == store_mount:
                mount = nm
                names.append(nm)
            else:
                left.append((s['slot'], f'{nm} 是騎寵，沒給 --store-mount {nm}（不碰）'))
            continue
        names.append(nm)
    return names, mount, left


def new_unnamed(before: list, after: list) -> list:
    """抓寵前後寵物欄 → 新增的沒名字寵物（slot dict 清單）：前一次是空格、這次有、且沒名字"""
    was_empty = {s['slot'] for s in before if s.get('empty')}
    return [s for s in after if not s.get('empty') and s['slot'] in was_empty and s.get('unnamed')]


def parse_count(text) -> int | None:
    """OCR「自動抓寵 自動存倉庫 可抓捕數：5 +」→ 5；讀不到 / 多個不同數字 → None"""
    m = re.search(r'可抓捕數\D{0,4}(\d{1,3})', re.sub(r'\s+', '', str(text or '')))
    return int(m.group(1)) if m else None


def plan(o: dict) -> list:
    """--dry-run / 說明用：(階段, [動作文字])"""
    sp, bp, ct, n = o['mount_species'], o['battle_pet'], o['catcher'], o['count']
    fam = family_for(sp, o.get('family')) or '（--family 必填）'
    box, nxt = box_names(o['trans'])
    return [
        ('preflight', ['確認當前 = DKBO', '解散隊伍', '外掛：5 人鎖定騎寵 / 戰寵先取消', '讀 5 人寵物欄']),
        ('boxes', [f'5 人開 {box}（內容存公共，{nxt} 存個人）'] if not o['no_boxes'] else ['（--no-boxes 跳過）']),
        ('store', ['5 人寵物欄全存個人倉庫'] + ([f'舊騎寵 {o["store_mount"]} 先設等待再存（--store-mount）'] if o['store_mount'] else ['舊騎寵不碰（沒給 --store-mount）'])),
        ('catch', [f'{ct} 公共倉庫取誘餌、拆到只剩 1', f'外掛捉寵設置 {fam} → {sp}、可抓捕數 1、自動存倉庫 + 自動抓寵', f'等抓完 → 學物種 {sp}', f'再留 {n - 1} 個誘餌重複', f'確認 {ct} 共 {n} 隻 {sp}']),
        ('distribute', [f'{ct} 存 {n - 1} 隻 {sp} 進公共（取最後格）', f'其他 {n - 1} 人各從公共取 1 隻']),
        ('ride', [f'5 人 {sp} 設騎乘']),
        ('battle', [f'5 人從個人倉庫取 {bp}、設出戰']),
        ('lock', [f'外掛 5 人：鎖定騎寵 = {sp}（成長字串逐項讀字）、鎖定戰寵 = {bp}、兩項都勾']),
        ('cleanup', [f'{ct} 多餘誘餌存回公共', '當前 DKBO、遇敵關', '寫 quest-log']),
    ]


def print_plan(o: dict, from_stage: str, to_stage: str) -> None:
    on = False
    for st, acts in plan(o):
        on = on or st == from_stage
        print(f'  {"✓" if on else "·"} {st}')
        if on:
            for a in acts:
                print(f'      - {a}')
        if st == to_stage:
            on = False


# ---- 紀錄 ----
def event(msg: str) -> None:
    line = f'{time.strftime("%Y-%m-%d %H:%M:%S")} [rebirth_pets] {msg}'
    print(line, flush=True)
    try:
        EVENT_LOG.parent.mkdir(exist_ok=True)
        with open(EVENT_LOG, 'a', encoding='utf-8') as f:
            f.write(line + '\n')
    except OSError:
        pass


def load_progress() -> dict:
    try:
        return json.loads(PROGRESS.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return {}


def save_progress(d: dict) -> None:
    try:
        PROGRESS.parent.mkdir(parents=True, exist_ok=True)
        PROGRESS.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding='utf-8')
    except OSError:
        pass


# ---- 真實工具（測試換成 FakeTools，介面相同）----
def ocr_lines(box, *opts) -> list:
    """ocr.ps1 → [(文字, x, y)]（x / y = 文字中心，截圖座標）；逾時 / 失敗 []"""
    import subprocess
    import winenv
    try:
        r = winenv.run_ps('ocr.ps1', *map(str, box), *map(str, opts))
        d = json.loads((r.stdout.strip().splitlines() or [''])[-1])
    except (subprocess.TimeoutExpired, ValueError):
        return []
    return [(ln['text'], ln.get('x', 0), ln.get('y', 0)) for ln in d.get('lines', [])] if d.get('ok') else []


class Tools:
    """碰遊戲的全部動作（pet.py / bag.py / ass.py / team.py / char.py 的薄包裝；外掛捉寵 / 鎖定 / 拆分誘餌是本類自己寫的）"""

    def sleep(self, s):
        uikit.sleep(s)

    def preflight(self):
        return uikit.preflight(SRC)

    def current(self):
        import char
        rc = char.current(True)
        return rc, char.LAST.get('current')

    def char_ensure(self, name):
        import char
        return char.ensure(name)

    def team_disband(self):
        import team
        return team.disband()

    def encounter_on(self):
        import heal
        return heal.encounter_on()

    def snap(self, tag):
        return uikit.snap(tag)

    # ---- 寵物（pet.py）----
    def pets_list(self, roles):
        import pet
        ctx = pet.load_ctx(True)
        out = {}
        with pet.Session(False, False) as s:
            if s.rc:
                return s.rc, out
            for r in roles:
                rc, slots = pet.list_role(r, ctx)
                if rc:
                    pet.save_ctx(ctx)
                    return rc, out
                out[r] = slots
            pet.save_ctx(ctx)
        return 0, out

    def pet_set_state(self, role, name, state, allow_mount=False):
        import pet
        return pet.set_state(role, name, state, None, allow_mount, True)

    def pet_store_many(self, roles, pets, depot, allow_slot1=False, allow_mount_store=None, pick=None):
        import pet
        rc = pet.store_many(','.join(roles), pets, depot, allow_slot1, allow_mount_store or [], False, True, True, pick)
        return rc, dict(pet.LAST)

    def pet_take_many(self, roles, pets, depot):
        import pet
        rc = pet.take_many(','.join(roles), pets, depot, False, True, True)
        return rc, dict(pet.LAST)

    def learn_species(self, role, slot, species, growth):
        import pet
        return pet.learn_species_cmd(role, slot, species, growth, True)

    # ---- 背包（bag.py + 拆分）----
    def box_open(self, role, trans):
        """開禮盒並存倉。→ (rc, info)。背包沒有禮盒 = 'skipped'（已開過，不算失敗）"""
        import bag
        box, nxt = box_names(trans)
        info = {'stored': [], 'personal': []}
        rc, found = bag.find_items(role, [box])
        if rc:
            return rc, info
        if found.get(box) is None:
            info['skipped'] = f'背包沒有 {box}'
            return 0, info
        rc = bag.use_item(role, box)
        if rc:
            return rc, info
        for nm in BOX_CONTENTS:
            rc = bag.depot_store(role, nm, 'public')
            if rc == bag.EXIT_ITEM:                          # 這次禮盒沒開出這項
                continue
            if rc:
                info['failed'] = nm
                return rc, info
            info['stored'].append(nm)
        rc = bag.depot_store(role, nxt, 'personal')          # banPubDepot=1：禁止存公共，直接存個人
        if rc and rc != bag.EXIT_ITEM:
            info['failed'] = nxt
            return rc, info
        if not rc:
            info['personal'].append(nxt)
        return 0, info

    def bait_take(self, role, keep):
        """公共倉庫取誘餌（整疊）→ 拆分出 keep 個 → 其餘（原疊，排在前面）存回公共，背包只剩 keep 個。**拆分流程只有手動實測過**"""
        import bag
        rc, found = bag.find_items(role, [BAIT])                 # 上次中斷時整疊可能已在背包（2026-10-12）→ 不重取
        if rc:
            return rc
        if found.get(BAIT) is None:
            rc = bag.depot_take(role, BAIT, 'public')
            if rc:
                return rc
        self.split_noop = False
        rc = self._split(role, BAIT, keep)
        if rc:
            return rc
        if self.split_noop:
            return 0
        return bag.depot_store(role, BAIT, 'public', keep_ok=True)   # find_item 取第一格 = 原疊（新疊在隔壁格，排後面）；拆分後背包仍有新疊，不驗消失（2026-10-12 實機）

    def _split(self, role, name, n):
        """背包第一格 name → 拆分鈕 → 數量鍵盤輸入 n → 確定；之後隔壁格要有 name。座標：notes/plan-dino-katan.md（手動實測）"""
        import bag
        if not 1 <= n <= 99:
            return uikit.fail(SRC, EXIT_CATCH, f'拆分數量 {n} 不合理')
        with bag.Session() as s:
            if s.rc:
                return s.rc
            rc = bag.select_role(role)
            if rc:
                return rc
            i = bag.find_item(name)
            if i is None:
                return uikit.fail(SRC, bag.EXIT_ITEM, f'{role} 背包找不到 {name}（拆分）')
            if not bag.open_slot_popup(i):
                return uikit.fail(SRC, bag.EXIT_PANEL, '拆分：點道具沒開彈窗')
            if not bag.name_match(bag.popup_name(), name):
                bag.close_popup()
                return uikit.fail(SRC, bag.EXIT_NAME, '拆分：彈窗名稱不符')
            txt = bag._ocr_join(bag.POPUP_BTN_BOX, bag.BTN_OPTS)
            if '拆分' not in re.sub(r'\s+', '', txt):
                bag.close_popup()
                return uikit.fail(SRC, bag.EXIT_NAME, f'拆分：彈窗按鈕列 OCR {txt!r} 沒有「拆分」（疊數只有 1？）')
            if not bag._click(628, 648, bag.POPUP, f'rebirth_pets 拆分 {name}', wait_ms=700):
                return uikit.fail(SRC, bag.EXIT_PANEL, '拆分：彈窗特徵消失，沒點拆分')
            dlg = ' '.join(t for t, _, _ in ocr_lines((480, 170, 480, 420), '-Zooms', '2,3'))
            if not any(k in dlg for k in ('數量', '拆分', '輸入', '確定')):      # 2026-10-12 實機：視窗標題「數量輸入」在 y≈190，舊框 y 300 起只讀到道具名
                uikit.snap('rebirth-split-dialog')
                return uikit.fail(SRC, bag.EXIT_NAME, f'拆分：數量輸入視窗 OCR {dlg!r}（待實機量）不是預期，停手')
            mq = re.search(r'\d{1,3}', ' '.join(t for t, _, _ in ocr_lines((670, 430, 170, 45), '-Zooms', '2,3')))
            qty = int(mq.group()) if mq else None
            if qty == n:                                          # 整疊剛好 = 要的數量：拆分會失敗（#284「拆分失敗！」）→ 取消，呼叫端不必存回
                uikit.gui('seq', 'click 828 545; wait 600', note='rebirth_pets 拆分：整疊就是要的數量，取消')
                self.split_noop = True
                return 0
            keys = {'1': (491, 334), '2': (615, 334), '3': (742, 334), '4': (491, 454), '5': (615, 454), '6': (740, 454),
                    '7': (491, 574), '8': (615, 574), '9': (740, 574), '0': (863, 334)}
            uikit.gui('seq', 'click 755 451; wait 500', note='rebirth_pets 拆分數量欄')
            for ch in str(n):
                x, y = keys[ch]
                uikit.gui('seq', f'click {x} {y}; wait 300', note=f'rebirth_pets 拆分鍵盤 {ch}')
            uikit.gui('seq', 'click 908 574; wait 500', note='rebirth_pets 拆分鍵盤 確認')
            uikit.gui('seq', 'click 610 545; wait 900', note='rebirth_pets 拆分 確定')
            if not uikit.is_open(bag.BAGANY):
                return uikit.fail(SRC, bag.EXIT_PANEL, '拆分後背包面板消失')
            nxt = bag.read_slot_name(i + 1)
            if not (nxt and bag.name_match(nxt, name)):
                uikit.snap('rebirth-split-after')
                return uikit.fail(SRC, bag.EXIT_VERIFY, f'拆分後隔壁格讀到 {nxt!r}，不是 {name}（待實機量；不重點）')
        return 0

    def bait_return(self, role):
        """背包還有誘餌就存回公共；沒有 = 0（不算失敗）"""
        import bag
        rc, found = bag.find_items(role, [BAIT])
        if rc:
            return rc
        if found.get(BAIT) is None:
            return 0
        return bag.depot_store(role, BAIT, 'public')

    # ---- 外掛（ass 面板；本類自己寫的部分）----
    def _ass_open(self, role, tab):
        import ass
        ok, why = ass.wait_not_battle(False)
        if not ok:
            return uikit.fail(SRC, uikit.EXIT_IN_BATTLE, why)
        if not ass.open_panel():
            return uikit.fail(SRC, 2, '外掛面板打不開')
        if not ass.select_role(role):
            return uikit.fail(SRC, 3, f'外掛選不到 {role}')
        x, y = ASS_TAB[tab]
        uikit.gui('seq', f'click {x} {y}; wait 600', note=f'rebirth_pets 外掛分頁 {tab}')
        box, need = (OCR_TAB_GENERAL, ('鎖定騎寵', '鎖定戰寵')) if tab == 'general' else (OCR_TAB_CATCH, ('抓寵',))
        txt = ''.join(t for t, _, _ in ocr_lines(box, '-Zooms', '2,3,4'))
        if not all(k in txt for k in need):
            uikit.snap(f'rebirth-ass-tab-{tab}')
            return uikit.fail(SRC, 4, f'外掛分頁 {tab} OCR {txt!r} 沒有 {need}（待實機量的 OCR 框；沒點任何勾選）')
        return 0

    def _checked(self, xy):
        import ass
        cols = ass._px([xy])
        return None if not cols else cols[0] != ass.UNCHECKED

    def _toggle(self, xy, want, note):
        import ass
        cur = self._checked(xy)
        if cur is None:
            return uikit.fail(SRC, 6, f'{note}：讀不到勾選框')
        if cur == want:
            return 0
        if not ass.panel_open():
            return uikit.fail(SRC, 6, f'{note}：外掛面板消失，沒點')
        uikit.gui('seq', f'click {xy[0]} {xy[1]}; wait 500', note=f'rebirth_pets {note}')
        if self._checked(xy) != want:
            uikit.snap('rebirth-ass-toggle')
            return uikit.fail(SRC, 4, f'{note}：點了勾選沒變（不重點）')
        return 0

    def lock_get(self, role):
        import ass
        rc = self._ass_open(role, 'general')
        if rc:
            return rc, None
        out = {w: self._checked(xy['check']) for w, xy in LOCK_XY.items()}
        ass.close_panel()
        return 0, out

    def lock_set(self, role, which, on, ident=None):
        """which = '騎寵' / '戰寵'。on=False：只取消勾選；on=True：先（需要時）選下拉再勾。ident 見 pick_row"""
        import ass
        xy = LOCK_XY[which]
        rc = self._ass_open(role, 'general')
        if rc:
            return rc
        try:
            if not on:
                return self._toggle(xy['check'], False, f'{role} 取消鎖定{which}')
            if not ident:
                return uikit.fail(SRC, 7, '鎖定要有 ident（要選哪一隻）')
            dx, dy = xy['dd']
            uikit.gui('seq', f'click {dx} {dy}; wait 500', note=f'rebirth_pets {role} 鎖定{which} 下拉')
            lines = ocr_lines((LOCK_LIST_X, dy + 22, LOCK_LIST_W, LOCK_LIST_H), '-Zooms', '2,3,4')
            hit, why = pick_row(lines, ident)
            if not hit:
                uikit.snap(f'rebirth-lock-{which}')
                uikit.gui('seq', f'click {dx} {dy}; wait 400', note='rebirth_pets 收下拉（點回欄位）')
                return uikit.fail(SRC, 7, f'{role} 鎖定{which}：{why}（OCR 框待實機量；沒選、沒勾）')
            if not ass.panel_open():
                return uikit.fail(SRC, 6, '下拉選項點之前外掛面板消失')
            uikit.gui('seq', f'click {hit[1]} {hit[2]}; wait 500', note=f'rebirth_pets {role} 鎖定{which} 選 {hit[0]}')
            fld = ocr_lines((LOCK_LIST_X, dy - 17, LOCK_FIELD_W, 34), '-Zooms', '2,3,4')
            h2, _ = pick_row(fld, ident)
            if not h2:
                uikit.snap(f'rebirth-lock-{which}-field')
                return uikit.fail(SRC, 7, f'{role} 鎖定{which}：選了「{hit[0]}」但欄位 OCR {[t for t, _, _ in fld]} 對不上 {ident}（不勾）')
            return self._toggle(xy['check'], True, f'{role} 勾鎖定{which}')
        finally:
            ass.close_panel()

    def catch_setup(self, role, family, species, count):
        """捉寵設置：系別 → 物種 → 讀可抓捕數 = count。**不點「+」、不碰丟棄區**。留著面板開著給 catch_start（同一個 session）"""
        rc = self._ass_open(role, 'catch')
        if rc:
            return rc
        rc = self._catch_setup_pick(role, family, species, count)
        if rc:                                                   # 失敗時關面板：下拉清單開著的狀態會讓下次點下拉變成「關」
            import ass
            ass.close_panel()
        return rc

    def _field_is(self, box, name):
        txt = ' '.join(t for t, _, _ in ocr_lines(box, '-Zooms', '2,3,4'))
        return bool(txt) and (name in txt or (name[0] in txt and sum(c in txt for c in name) >= len(name) - 1))

    def _catch_setup_pick(self, role, family, species, count):
        fam_ok = self._field_is(OCR_FAMILY_FIELD, family)         # 欄位已經是目標（上次設過 / 預設）就不再開下拉（下拉開關狀態難判斷）
        pet_ok = fam_ok and self._field_is(OCR_PET_FIELD, species)
        if fam_ok and pet_ok:
            n = parse_count(''.join(t for t, _, _ in ocr_lines(OCR_TAB_CATCH, '-Zooms', '2,3,4')))
            if n != count:
                uikit.snap('rebirth-catch-count')
                return uikit.fail(SRC, 4, f'可抓捕數讀到 {n}，要 {count}（背包誘餌數不對？不勾自動抓寵）')
            return 0
        if not self._pick_dropdown(CATCH_XY['family_dd'], CATCH_LIST_FAMILY, OCR_FAMILY_FIELD, ('name', family), scroll=True, snap_tag='family', plain=family):
            return uikit.fail(SRC, 4, f'捉寵系別選不到 {family}')
        if not self._pick_dropdown(CATCH_XY['pet_dd'], CATCH_LIST_PET, OCR_PET_FIELD, ('name', species), scroll=False, snap_tag='species', fam_species=SPECIES_ORDER.get(family)):
            return uikit.fail(SRC, 4, f'捉寵物種選不到 {species}')
        n = parse_count(''.join(t for t, _, _ in ocr_lines(OCR_TAB_CATCH, '-Zooms', '2,3,4')))
        if n != count:
            uikit.snap('rebirth-catch-count')
            return uikit.fail(SRC, 4, f'可抓捕數讀到 {n}，要 {count}（背包誘餌數不對？不勾自動抓寵）')
        return 0

    def _pick_dropdown(self, dd, list_box, field_box, ident, scroll, snap_tag, plain=None, fam_species=None):
        import ass
        uikit.gui('seq', f'click {dd[0]} {dd[1]}; wait 500', note=f'rebirth_pets 捉寵下拉 {snap_tag}')
        if scroll:                                              # 清單會記住上次捲動位置：先往上拖 4 次回到頂，再小步往下找（2026-10-12 實機）
            for _ in range(4):
                uikit.gui('drag', '750', '480', '750', '650', note='rebirth_pets 捉寵清單回頂')
            uikit.sleep(1.0)
        for k in range(14):
            lines = ocr_lines(list_box, '-Zooms', '2,3,4')
            if plain:                                                   # 系別名不在 Monster 表 → 直接比文字
                hits = []
                for t, x, y in lines:                                   # 多個放大倍數會重複回同一列：y 差 ≤ 15 併成一個（2026-10-12 實機：重複 → 誤判 0 命中）
                    if plain in t and not any(abs(y - h[2]) <= 15 for h in hits):
                        hits.append((t, x, y))
                hit = hits[0] if len(hits) == 1 else None
            else:
                hit, _ = pick_row(lines, ident)
            if not hit and plain in FAMILY_NEIGHBORS:                # OCR 讀不到這列（鯊魚系常讀不出）：上下鄰居都讀到、間距約 2 列 → 取中間
                prv, nxt = FAMILY_NEIGHBORS[plain]
                ys = {k: [(x, y) for t, x, y in lines if any(n in t for n in alts)] for k, alts in (('p', prv), ('n', nxt))}
                for (x1, y1) in ys['p']:
                    for (_, y2) in ys['n']:
                        if 70 <= y2 - y1 <= 100 and hit is None:
                            hit = (plain, x1, (y1 + y2) // 2)
            if not hit and not scroll and ident[0] == 'name' and fam_species and ident[1] in fam_species:
                hit = (ident[1], 1115, 421 + 42 * fam_species.index(ident[1]))      # 位置備援：只在 OCR 沒讀到時；點完照樣讀欄位驗證
            if hit:
                if not ass.panel_open():
                    return False
                uikit.gui('seq', f'click {hit[1]} {hit[2]}; wait 500', note=f'rebirth_pets 捉寵 選 {hit[0]}')
                fld = ' '.join(t for t, _, _ in ocr_lines(field_box, '-Zooms', '2,3,4'))
                if plain:                                                    # OCR 常漏字（鯊魚系 → 鯊系）：首字在、至少吻合 len-1 個字
                    return plain[0] in fld and sum(c in fld for c in plain) >= len(plain) - 1
                return uikit.snap_pet(fld) == ident[1] or ident[1] in fld
            if not scroll or k == 13:
                break
            (x0, y0), (x1, y1) = (750, 650), (750, 600)     # 50px ≈ 2 列；大拖會慣性亂跳過目標列
            uikit.gui('drag', str(x0), str(y0), str(x1), str(y1), note='rebirth_pets 捉寵清單捲動')
            uikit.sleep(1.0)                                        # 清單有慣性滑動：等停下來再讀（不等會點到差一列的項目，2026-10-12 實機點成飛天蛙系）   # gui 參數要分開（一整串會被當成單一參數 → 不捲）
        uikit.snap(f'rebirth-catch-{snap_tag}')
        return False

    def catch_start(self, role, count):
        """面板已在捉寵設置（catch_setup 後）：自動存倉庫 → 自動抓寵 勾選，關面板"""
        import ass
        try:
            rc = self._toggle(CATCH_XY['store'], True, f'{role} 勾自動存倉庫')
            if rc:
                return rc
            return self._toggle(CATCH_XY['auto'], True, f'{role} 勾自動抓寵')
        finally:
            ass.close_panel()

    def catch_wait(self, role, timeout=CATCH_TIMEOUT_S):
        """每 CATCH_POLL_S 重開外掛讀可抓捕數 + 自動抓寵勾選；數 = 0 且自動抓寵已被遊戲取消 → (0, 0)；逾時 (rc, 剩幾隻)"""
        import ass
        end = uikit.clock() + timeout
        left = None
        while True:
            self.sleep(CATCH_POLL_S)
            rc = self._ass_open(role, 'catch')
            if rc:
                return rc, left
            left = parse_count(''.join(t for t, _, _ in ocr_lines(OCR_TAB_CATCH, '-Zooms', '2,3,4')))
            auto = self._checked(CATCH_XY['auto'])
            ass.close_panel()
            if auto is False and left in (0, None):                       # 可抓捕數 OCR 常讀不到；遊戲抓完自己取消勾選（2026-10-12 實機）
                return 0, 0
            if uikit.clock() >= end:
                return uikit.fail(SRC, EXIT_CATCH, f'抓寵 {timeout:.0f} 秒內沒抓完（可抓捕數 {left}、自動抓寵 {auto}）'), left


# ---- 流程 ----
class Run:
    def __init__(self, T, o: dict):
        self.T, self.o = T, o
        self.prog = load_progress() if o.get('resume', True) else {}
        self.info: dict = {}

    def stop(self, rc: int, msg: str, **extra):
        self.info.update(extra, rc=rc, msg=msg)
        event(f'失敗 rc={rc}：{msg}')
        self.T.snap('rebirth-pets-fail')
        return rc

    def done(self, stage: str, **data):
        self.prog.setdefault('done', [])
        if stage not in self.prog['done']:
            self.prog['done'].append(stage)
        self.prog.setdefault('data', {}).update(data)
        save_progress(self.prog)
        event(f'階段 {stage} 完成')

    def need(self, stage: str) -> bool:
        return stage in self.prog.get('done', [])

    # ---- 階段 ----
    def preflight(self):
        T, o = self.T, self.o
        rc = T.preflight()
        if rc:
            return rc
        rc, cur = T.current()
        if rc:
            return self.stop(EXIT_PRE, f'讀不到當前角色（char rc {rc}）')
        import charstate
        if not charstate.same(cur, LEADER):
            rc = T.char_ensure(LEADER)
            if rc:
                return self.stop(EXIT_PRE, f'當前是 {cur}，切回 {LEADER} 失敗（char rc {rc}）')
        rc = T.team_disband()
        if rc:
            return self.stop(EXIT_PRE, f'解散隊伍失敗（team rc {rc}）')
        for r in ALL_ROLES:
            rc, st = T.lock_get(r)
            if rc:
                return self.stop(EXIT_PRE, f'{r} 讀外掛鎖定狀態失敗（rc {rc}）')
            for w in ('騎寵', '戰寵'):
                if st.get(w):
                    rc = T.lock_set(r, w, False)
                    if rc:
                        return self.stop(EXIT_PRE, f'{r} 取消鎖定{w}失敗（rc {rc}）')
        rc, pets = T.pets_list(ALL_ROLES)
        if rc:
            return self.stop(EXIT_PRE, f'讀 5 人寵物欄失敗（pet rc {rc}）')
        self.info['pets_before'] = {r: [(s.get('name') or s.get('raw_name'), s.get('state')) for s in sl if not s.get('empty')] for r, sl in pets.items()}
        if o['catcher'] not in ALL_ROLES:
            return self.stop(EXIT_ARGS, f'--catcher {o["catcher"]} 不是 {ALL_ROLES} 之一')
        self.done('preflight', pets_before=self.info['pets_before'])
        return 0

    def boxes(self):
        o = self.o
        if o['no_boxes']:
            self.done('boxes', skipped=True)
            return 0
        res = {}
        for r in ALL_ROLES:
            rc, info = self.T.box_open(r, o['trans'])
            res[r] = info
            if rc:
                return self.stop(EXIT_BOX, f'{r} 禮盒 / 存倉失敗（bag rc {rc}）', bag_rc=rc, boxes=res)
        self.done('boxes', boxes=res)
        return 0

    def store(self):
        T, o = self.T, self.o
        rc, pets = T.pets_list(ALL_ROLES)
        if rc:
            return self.stop(EXIT_STORE, f'讀寵物欄失敗（pet rc {rc}）', pet_rc=rc)
        groups: dict = {}
        notes = {}
        for r in ALL_ROLES:
            names, mount, left = stores_for(pets[r], o['store_mount'])
            notes[r] = left
            if mount:                                                      # 使用者當次明講：騎寵先設等待
                rc = T.pet_set_state(r, mount, '等待', True)
                if rc:
                    return self.stop(EXIT_STORE, f'{r} 的 {mount} 設等待失敗（pet rc {rc}；外掛鎖定騎寵沒取消？）', pet_rc=rc)
            if names:
                groups.setdefault((tuple(names), bool(mount)), []).append(r)
        for (names, has_mount), roles in groups.items():
            rc, info = T.pet_store_many(roles, list(names), 'personal', allow_slot1=True, allow_mount_store=[o['store_mount']] if has_mount and o['store_mount'] else [])
            if rc:
                return self.stop(EXIT_STORE, f'{roles} 存 {list(names)} 失敗（pet rc {rc}：{info.get("msg", "")}）', pet_rc=rc)
        stuck = {r: l for r, l in notes.items() if l}
        for r, l in stuck.items():
            event(f'{r} 留在寵物欄：{l}')
        self.info['left_in_bar'] = stuck
        self.done('store', left_in_bar=stuck)
        return 0

    def catch(self):
        T, o = self.T, self.o
        sp, ct, n = o['mount_species'], o['catcher'], o['count']
        fam = family_for(sp, o.get('family'))
        if not fam:
            return self.stop(EXIT_ARGS, f'{sp} 沒有預設系別，請給 --family')
        rc, pets = T.pets_list([ct])
        if rc:
            return self.stop(EXIT_CATCH, f'讀 {ct} 寵物欄失敗（pet rc {rc}）')
        have = [s for s in pets[ct] if not s.get('empty') and (s.get('species') == sp or s.get('name') == sp)]
        empties = sum(1 for s in pets[ct] if s.get('empty'))
        need = max(0, n - len(have))
        if need == 0:
            self.done('catch', caught=len(have))
            return 0
        if empties < need:
            return self.stop(EXIT_CATCH, f'{ct} 寵物欄空格 {empties} < 還要抓的 {need}（舊寵物沒存完 / 舊騎寵沒給 --store-mount？）')
        before = pets[ct]
        # 先試抓 1 隻
        if not any(s.get('unnamed') and s.get('species') == sp for s in before) and len(have) == 0:
            rc = self._catch_round(ct, fam, sp, 1)
            if rc:
                return rc
            rc, pets = T.pets_list([ct])
            if rc:
                return self.stop(EXIT_CATCH, f'試抓後讀寵物欄失敗（pet rc {rc}）')
            fresh = new_unnamed(before, pets[ct])
            if len(fresh) != 1:
                return self.stop(EXIT_CATCH, f'試抓 1 隻後寵物欄多了 {len(fresh)} 隻沒名字的寵物（要剛好 1）', new=[s.get('raw_name') for s in fresh])
            s0 = fresh[0]
            if not s0.get('species'):                                      # 三重確認：外掛選的物種 + 剛好多 1 隻沒名字 + 誘餌 1 → 1；才登錄
                rc = T.learn_species(ct, s0['slot'], sp, s0['unnamed'])
                if rc:
                    return self.stop(EXIT_CATCH, f'登錄物種失敗（pet rc {rc}）', pet_rc=rc)
            need -= 1
        if need > 0:
            rc = self._catch_round(ct, fam, sp, need)
            if rc:
                return rc
        rc, pets = T.pets_list([ct])
        if rc:
            return self.stop(EXIT_CATCH, f'抓完讀寵物欄失敗（pet rc {rc}）')
        got = [s for s in pets[ct] if not s.get('empty') and (s.get('species') == sp or s.get('name') == sp)]
        if len(got) != n:
            return self.stop(EXIT_CATCH, f'{ct} 寵物欄物種確認的 {sp} 有 {len(got)} 隻，要 {n}（其他沒名字的：{[s.get("raw_name") for s in pets[ct] if s.get("unnamed") and not s.get("species")]}）')
        self.done('catch', caught=len(got), growths={ct: [s.get('unnamed') for s in got]})
        return 0

    def _catch_round(self, ct, fam, sp, k):
        T = self.T
        rc = T.bait_take(ct, k)
        if rc:
            return self.stop(EXIT_CATCH, f'{ct} 取 {k} 個誘餌失敗（rc {rc}）', bag_rc=rc)
        rc = T.catch_setup(ct, fam, sp, k)
        if rc:
            return self.stop(EXIT_CATCH, f'{ct} 外掛捉寵設置失敗（rc {rc}）')
        rc = T.catch_start(ct, k)
        if rc:
            return self.stop(EXIT_CATCH, f'{ct} 勾自動抓寵失敗（rc {rc}）')
        event(f'{ct} 開始自動抓 {k} 隻 {sp}')
        rc, left = T.catch_wait(ct)
        if rc:
            return self.stop(EXIT_CATCH, f'等抓寵失敗（rc {rc}，剩 {left}）')
        return 0

    def distribute(self):
        T, o = self.T, self.o
        sp, ct, n = o['mount_species'], o['catcher'], o['count']
        others = [r for r in ALL_ROLES if r != ct]
        if len(others) != n - 1:
            return self.stop(EXIT_ARGS, f'--count {n} 與其他角色數 {len(others)} 不合（要 count = 角色數）')
        rc, info = T.pet_store_many([ct], [sp] * (n - 1), 'public', allow_slot1=False, allow_mount_store=[sp], pick='last')
        if rc:
            return self.stop(EXIT_DIST, f'{ct} 存 {n - 1} 隻 {sp} 進公共失敗（pet rc {rc}：{info.get("msg", "")}）', pet_rc=rc)
        rc, info = T.pet_take_many(others, [sp], 'public')
        if rc:
            return self.stop(EXIT_DIST, f'{others} 從公共取 {sp} 失敗（pet rc {rc}：{info.get("msg", "")}）', pet_rc=rc)
        self.done('distribute')
        return 0

    def ride(self):
        T, sp = self.T, self.o['mount_species']
        for r in ALL_ROLES:
            rc = T.pet_set_state(r, sp, '騎乘', True)
            if rc:
                return self.stop(EXIT_RIDE, f'{r} 設 {sp} 騎乘失敗（pet rc {rc}）', pet_rc=rc, role=r)
        self.done('ride')
        return 0

    def battle(self):
        T, bp = self.T, self.o['battle_pet']
        rc, info = T.pet_take_many(ALL_ROLES, [bp], 'personal')
        if rc:
            return self.stop(EXIT_BATTLE, f'從個人倉庫取 {bp} 失敗（pet rc {rc}：{info.get("msg", "")}）', pet_rc=rc)
        for r in ALL_ROLES:
            rc = T.pet_set_state(r, bp, '出戰', False)
            if rc:
                return self.stop(EXIT_BATTLE, f'{r} 的 {bp} 設出戰失敗（pet rc {rc}）', pet_rc=rc, role=r)
        self.done('battle')
        return 0

    def lock(self):
        T, o = self.T, self.o
        rc, pets = T.pets_list(ALL_ROLES)
        if rc:
            return self.stop(EXIT_LOCK, f'讀寵物欄失敗（pet rc {rc}）', pet_rc=rc)
        for r in ALL_ROLES:
            for w in ('騎寵', '戰寵'):
                ident = role_ident(pets[r], o['mount_species'], o['battle_pet'], w)
                if ident is None:
                    return self.stop(EXIT_LOCK, f'{r} 的{w}在寵物欄裡找不到唯一一隻（讀到 {[s.get("name") or s.get("raw_name") for s in pets[r] if not s.get("empty")]}）')
                rc = T.lock_set(r, w, True, ident)
                if rc:
                    return self.stop(EXIT_LOCK, f'{r} 鎖定{w}（{ident}）失敗（rc {rc}）', role=r)
        self.done('lock')
        return 0

    def cleanup(self):
        T, o = self.T, self.o
        rc = T.bait_return(o['catcher'])
        if rc:
            return self.stop(EXIT_CLEAN, f'{o["catcher"]} 誘餌存回公共失敗（bag rc {rc}）', bag_rc=rc)
        rc, cur = T.current()
        import charstate
        if rc or not charstate.same(cur, LEADER):
            rc = T.char_ensure(LEADER)
            if rc:
                return self.stop(EXIT_CLEAN, f'收尾切回 {LEADER} 失敗（char rc {rc}）')
        try:
            if T.encounter_on():
                return self.stop(EXIT_CLEAN, '收尾時原地遇敵是開的（本流程不該開），請人確認')
        except Exception:
            pass
        rc, pets = T.pets_list(ALL_ROLES)
        final = {r: [(s.get('name') or s.get('raw_name') or '?', s.get('state')) for s in sl if not s.get('empty')] for r, sl in (pets or {}).items()} if not rc else {}
        write_quest_log(o, self.prog, final)
        self.done('cleanup', final=final)
        return 0


def write_quest_log(o: dict, prog: dict, final: dict) -> None:
    lines = [f'\n## 轉生後寵物重整（腳本 rebirth_pets.py，{time.strftime("%Y-%m-%d")}）',
             f'- 參數：轉 {o["trans"]}、騎寵 {o["mount_species"]}、戰寵 {o["battle_pet"]}、捉寵角色 {o["catcher"]}、{o["count"]} 隻、--store-mount {o["store_mount"] or "（無）"}。',
             f'- 完成階段：{"、".join(prog.get("done", []))}。']
    left = prog.get('data', {}).get('left_in_bar')
    if left:
        lines.append(f'- 存倉後仍留在寵物欄：{left}')
    if final:
        lines.append('- 結束寵物欄：' + '；'.join(f'{r} ' + ' / '.join(f'{n}({s})' for n, s in v) for r, v in final.items()) + '。')
    try:
        with open(QUEST_LOG, 'a', encoding='utf-8') as f:
            f.write('\n'.join(lines) + '\n')
    except OSError:
        pass


DEFAULTS = dict(trans=1, mount_species='布拉奇多斯', battle_pet='朵拉比斯', catcher='DKBO2', count=5, family=None, store_mount=None,
                no_boxes=False)


def run(trans=1, from_stage: str = 'preflight', to_stage: str = 'cleanup', dry_run: bool = False, tools=None, **kw) -> int:
    o = dict(DEFAULTS, trans=level_n(trans), **kw)
    LAST.clear()
    import charstate
    cc = charstate.norm_char(o['catcher'])
    if cc is None or charstate.display(cc) not in ALL_ROLES:
        print(f'{SRC}：--catcher {o["catcher"]!r} 不認得（DKBO / DKBO2～5）', file=sys.stderr)
        return EXIT_ARGS
    o['catcher'] = charstate.display(cc)
    if from_stage not in STAGES or to_stage not in STAGES or STAGES.index(from_stage) > STAGES.index(to_stage):
        print(f'{SRC}：--from / --to 階段不對（{STAGES}）', file=sys.stderr)
        return EXIT_ARGS
    uk = {uikit.snap_pet(o['mount_species']), uikit.snap_pet(o['battle_pet'])}
    if None in uk:
        print(f'{SRC}：--mount-species / --battle-pet 不在 Monster 表', file=sys.stderr)
        return EXIT_ARGS
    o['mount_species'], o['battle_pet'] = uikit.snap_pet(o['mount_species']), uikit.snap_pet(o['battle_pet'])
    if o['store_mount']:
        sm = uikit.snap_pet(o['store_mount'])
        if not sm or sm not in uikit.MOUNTS:
            print(f'{SRC}：--store-mount {o["store_mount"]!r} 不是騎寵名單 {uikit.MOUNTS} 之一', file=sys.stderr)
            return EXIT_ARGS
        o['store_mount'] = sm
    if not 2 <= o['count'] <= 5:
        print(f'{SRC}：--count 要 2～5', file=sys.stderr)
        return EXIT_ARGS
    if dry_run:
        print(f'{SRC} --dry-run（不碰遊戲）：參數 {o}')
        print_plan(o, from_stage, to_stage)
        LAST.update(ok=True, rc=0, dry_run=True, plan=[s for s, _ in plan(o)])
        return 0
    T = tools or Tools()
    R = Run(T, o)
    if from_stage != 'preflight':                                        # 續跑：前面的階段要在進度檔裡有紀錄
        missing = [s for s in STAGES[:STAGES.index(from_stage)] if s not in R.prog.get('done', []) and not (s == 'boxes' and o['no_boxes'])]
        if missing:
            print(f'{SRC}：--from {from_stage} 但進度檔裡沒有完成 {missing}（先照順序跑，或刪 tools/.cache/rebirth_pets.json 重來）', file=sys.stderr)
            return EXIT_ARGS
    else:
        R.prog = {'done': [], 'data': {}, 'started': time.strftime('%F %T'), 'opts': {k: v for k, v in o.items()}}
    event(f'開始：from={from_stage} to={to_stage} {o}')
    rc = 0
    for st in STAGES[STAGES.index(from_stage):STAGES.index(to_stage) + 1]:
        event(f'階段 {st}')
        rc = getattr(R, st)()
        if rc:
            break
    LAST.update(R.info, ok=rc == 0, rc=rc)
    LAST['done'] = list(R.prog.get('done', []))
    return rc


def main(argv=None) -> int:
    import winenv
    winenv.enable_server()
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--trans', type=int, default=1)
    ap.add_argument('--mount-species', default=DEFAULTS['mount_species'])
    ap.add_argument('--battle-pet', default=DEFAULTS['battle_pet'])
    ap.add_argument('--catcher', default=DEFAULTS['catcher'])
    ap.add_argument('--count', type=int, default=DEFAULTS['count'])
    ap.add_argument('--family', default=None)
    ap.add_argument('--store-mount', default=None, help='使用者當次明講才用：舊騎寵（例 瑪斯貝卡）也存個人倉庫')
    ap.add_argument('--from', dest='from_stage', default='preflight', choices=STAGES)
    ap.add_argument('--to', dest='to_stage', default='cleanup', choices=STAGES)
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--no-boxes', action='store_true')
    a = ap.parse_args(argv)
    rc = run(a.trans, a.from_stage, a.to_stage, a.dry_run, None, mount_species=a.mount_species, battle_pet=a.battle_pet, catcher=a.catcher,
             count=a.count, family=a.family, store_mount=a.store_mount, no_boxes=a.no_boxes)
    print(json.dumps(dict(LAST, rc=rc), ensure_ascii=False, default=str))
    return rc


if __name__ == '__main__':
    sys.exit(main())
