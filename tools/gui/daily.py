#!/usr/bin/env python3
"""每日任務（委託接取）腳本：薩姆吉爾醫院 1005 的「委託接取」NPC，5 環 × 2 項成品，各項「快速合成」→ 兩項 1/1 綠 →「提交委託」→ 5/5 領裝備升級石。只用標準函式庫。

設計（notes/plan-daily.md v3 §4，使用者 2026-10-17 定案；**全程未實機**，只有離線測試）：全隊一起移動、各買各的、各合成各的，不經公倉轉手（胡椒除外）。
  prep    停練功 / 關遇敵 / 等戰鬥 → 全隊傳送薩姆吉爾 → 隊長帶隊走進醫院 1005 站 38,48 → 解散
  read    DKBO2 → DKBO3 → DKBO4 → DKBO5 → DKBO 輪流 char.switch：點 NPC 開委託面板 → 讀 5 環 × 上 / 下 → daily-<角色>.json
  plan    離線：每人 10 項 → 配方 → 薩村 1009 / 漁村 2009 / 公倉胡椒 → 每人購買清單（不讀背包 / 倉庫格數）；沒給 --confirm-buy 停 221
  sam     組隊 → 帶隊到 1009 → 解散 → 5 人輪流沿櫃檯逐店買自己的薩村料（背包材料種類模型放不下 → 存個人倉庫；個人倉庫滿 → 公倉並記 in_public）
  mid     組隊 → 傳送薩姆吉爾 → 帶隊回醫院 → 解散 → 5 人輪流：材料齊的項先合成、該環兩項都綠就提交（沒人有事可做就整段跳過）
  fish    組隊 → 傳送瑪麗娜絲 → 帶隊進 2009 → 解散 → 5 人輪流買漁村料
  final   組隊 → 傳送薩姆吉爾 → 帶隊回醫院 → 解散 → 5 人輪流：每環先從個人倉庫 / 公倉取料 → 合成 → 提交，直到 5/5（胡椒從公倉取整疊、用完整疊存回）
  finish  組隊 → grind.go（--no-grind 略）
順序固定 DKBO2 → DKBO3 → DKBO4 → DKBO5 → DKBO（clients.leader_last；結束時當前角色 = 隊長，不用另外切回）。

用法（專案根目錄；WSL / Windows 原生指令相同；PSA_CLIENT=PrimalSA2 → DKBO6～10）：
  uv run --no-project python tools/gui/daily.py read-all [--roles DKBO,DKBO2]      # 只做 prep + read（不花錢）
  uv run --no-project python tools/gui/daily.py plan [--roles ...]                  # 離線：讀進度檔印每人計畫與石幣估算
  uv run --no-project python tools/gui/daily.py show                                # 離線：每人各段 / 各環狀態
  uv run --no-project python tools/gui/daily.py run [--roles ...] [--from 段] [--confirm-buy] [--fresh] [--dry-run] [--no-grind]
    --confirm-buy  買材料（500 / 個）與合成（1000 / 項）都花石幣：沒給 = 讀完清單 + 印計畫就停（221）
    --from 段      prep / read / plan / sam / mid / fish / final / finish；預設從進度檔續跑（段內跳過已完成的人 / 已買的種類 / 已合成的項）
    --fresh        丟掉進度檔重來（跨過 00:00 後想重做時用；材料還在身上 / 倉庫，plan 不知道 → 人要先看過）
    --dry-run      同 plan（不碰遊戲）
  可 import：daily.run(roles=None, confirm_buy=False, from_stage=None, fresh=False, dry_run=False, grind=True, tools=None) → 退出碼；結果 dict 在 daily.LAST

鐵則：3（每日任務例外，使用者 2026-10-17）**不讀石幣、不讀鑽石**：買到沒看數量框歸 0 + 背包名稱；不拆疊、不丟東西、不碰寵物、不買胡椒。
      5 答題介面 → uikit.preflight 正面命中即停；不 clear 旗標。委託面板 / 快速合成 / 便利店內只用 uikit.safe_click（禁區：提交委託 / 彈窗合成 / 獎勵箭頭，動作內 allow 放行）。
      不認得的畫面 / 面板打不開 → 停手，不亂點；絕不點空白處（倉庫左下擴容 = 鑽石提示）。
退出碼：0 / 1 / 2 / 8 / 9 / 10 共用（uikit，原碼回傳）；本檔 220～229（dailyplan.EXIT_NAMES）：
  220 參數 / 沒名單 / 今天全部已完成 / 跨過 00:00   221 要花石幣沒給 --confirm-buy   222 胡椒公倉取不到   223 停練功 / 傳送 / 解散 / 組隊 / 切角色失敗
  224 走不到醫院 38,48 / 1009 / 2009 店員前、面板開不了   225 讀清單失敗   226 某人全部環都不支援   227 購買失敗（含背包放不下）
  228 個人倉庫 / 公倉存取失敗   229 合成 / 提交失敗（兩項不是 1/1 綠不提交；提交後 n/5 沒 +1；5/5 驗證不過）
有環被跳過（不支援）不算失敗：該人其他環照做，結束 rc 0；環不用依序提交（遊戲沒規定）。
"""
import argparse
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import clients  # noqa: E402
import dailyplan as dp  # noqa: E402
import logpaths  # noqa: E402
import shopkit  # noqa: E402
import uikit  # noqa: E402

SRC = 'daily'
EVENT_LOG = logpaths.p(clients.npath('quest-events.log'))
ROLES = clients.roster()
LEADER = ROLES[0] if ROLES else ''
PASS = (uikit.EXIT_IN_BATTLE, uikit.EXIT_UNKNOWN_SCREEN, uikit.EXIT_HALT)        # 8 / 9 / 10：原碼停手
(EXIT_ARGS, EXIT_NOBUY, EXIT_PEPPER, EXIT_PREP, EXIT_WALK, EXIT_READ, EXIT_NOROLE, EXIT_BUY, EXIT_DEPOT, EXIT_CRAFT) = (
    dp.EXIT_ARGS, dp.EXIT_NOBUY, dp.EXIT_PEPPER, dp.EXIT_PREP, dp.EXIT_WALK, dp.EXIT_READ, dp.EXIT_NOROLE, dp.EXIT_BUY, dp.EXIT_DEPOT, dp.EXIT_CRAFT)

# ---- 版面（截圖 1440×830，鏡頭最左；notes/daily-probe.md M1～M13）----
HOSPITAL, VILLAGE, MARINAS_MAP = 1005, 1000, 2000
HOSP_ENTRY = (25, 65)
HOSP_WAYPOINTS = [(31, 60), (36, 60), (38, 55), (38, 48)]       # 醫院無通行格資料：照探路走出來的 waypoint（直接 36,50 會卡在 31,60）
HOSP_STAND = (38, 48)                                            # 站這裡點得到委託接取（41,42）
DAILY_NPC = (41, 42)
MARINAS_XY = (553, 625)                                          # 傳送面板尼斯大陸分頁的「瑪麗娜絲」→ 2000:65,58（ui/transfer.md）
SAM_WALK = (1000, 106, 91)                                       # 薩村 → 1009 出口
FISH_WALK = (2000, 73, 103)                                      # 瑪麗娜絲 → 2009 出口（快速走路卡 67,90 → walk 自動慢速）
NAME_BOXES = [(380, 236, 200, 36), (380, 340, 200, 36)]          # 第 1 / 2 項名稱（x386～540、y242～268 / 346～372）
MERGE_XY = [(735, 265), (735, 370)]                              # 兩顆「合成」藍鈕
STATE_PX = [(390, 291), (390, 396)]                              # 兩項計數「0」紅字像素（1/1 綠字位置相同）
PAGE_BOX = (520, 672, 70, 45)                                    # 頁碼「n/5」
PREV_XY, NEXT_XY = (363, 692), (745, 692)
SUBMIT_XY = (1015, 685)
REWARD_BOX = (960, 350, 110, 45)                                 # 「完成所有任務額外獎勵」計數 n/5（綠字 986～1044 × 358～387）
POP_NAME_BOX = (420, 405, 140, 36)                               # 彈窗成品名（黃字 454～508 × 415～431）
POP_COUNT_PX = [(695, 287), (695, 378), (695, 470)]              # 彈窗材料列計數（紅 = 不足）
POP_CRAFT_XY = (480, 552)
STONE = '裝備升級石'                                              # 5/5 獎勵（Item 93016）
SHOP_STAND_DX = -2                                               # 店員 (27, y) 前 2 格站 (25, y)；點 NPC 會自己走近

MAT_PRICE_TXT = f'{dp.MAT_PRICE:,}'
LAST: dict = {}


def event(msg: str) -> None:
    line = f'{time.strftime("%Y-%m-%d %H:%M:%S")} [daily] {msg}'
    print(line, flush=True)
    try:
        EVENT_LOG.parent.mkdir(parents=True, exist_ok=True)
        with open(EVENT_LOG, 'a', encoding='utf-8') as f:
            f.write(line + '\n')
    except OSError:
        pass


# ======================================================================================
# 碰遊戲的動作（既有工具的薄包裝；離線測試換成 FakeTools）
# ======================================================================================
class Tools:
    # ---- 一般 ----
    def preflight(self):
        return uikit.preflight(SRC)

    def sleep(self, s):
        uikit.sleep(s)

    def lock(self) -> bool:
        """持 grind.lock：grind.run / netwatch 的 grind ensure 看到鎖就不搶畫面（結束 / finish 前 unlock）"""
        import grind
        return grind.take_lock()

    def unlock(self) -> None:
        import grind
        grind.release_lock()

    def stop_follow(self) -> bool:
        import grind
        return grind.stop_follow('每日任務（要離開練功點、解散隊伍）')

    def encounter_off(self) -> None:
        import heal
        heal.set_encounter(False)
        heal.gui('seq', f'waitpix 30000 {heal.SIG_NO_BATTLE} 40')

    def pos(self):
        import walk
        return walk.pos()

    def wait_map(self, map_id, tries=10) -> bool:
        import walk
        p = walk.wait_pos(tries, map_id, 0.6)
        return bool(p and p[0] == map_id)

    def to_town(self) -> bool:
        """城鎮傳送薩姆吉爾（1000:92,99）；heal.teleport 內建重試"""
        import heal
        try:
            heal.teleport(heal.TAB_TOWN, heal.SAMUGIL, heal.VILLAGE, '薩姆吉爾', want_xy=heal.VILLAGE_START)
        except RuntimeError as e:
            print(f'{SRC}：{e}', file=sys.stderr)
            return False
        return True

    def to_marinas(self) -> bool:
        import heal
        try:
            heal.teleport(heal.TAB_TOWN, MARINAS_XY, MARINAS_MAP, '瑪麗娜絲')
        except RuntimeError as e:
            print(f'{SRC}：{e}', file=sys.stderr)
            return False
        return True

    def ensure(self, role) -> int:
        import char
        return char.ensure(role)

    def switch(self, role) -> int:
        import char
        return char.switch(role)

    def form(self) -> int:
        import team
        return team.form(LEADER, len(ROLES))

    def disband(self) -> int:
        import team
        rc = team.disband()
        if rc == 40:                                           # 切換面板剛換地圖後第一下常打不開（buywendy 2026-10-15 實機）→ 等一下再來一次
            uikit.sleep(2.0)
            rc = team.disband()
        return rc

    # ---- 走路 ----
    def walk_to(self, map_id, x, y, exit_map=None) -> bool:
        import walk
        try:
            walk.walk_to(map_id, x, y, exit_map=exit_map)
        except RuntimeError as e:
            print(f'{SRC}：走到 {map_id}:{x},{y} 失敗：{e}', file=sys.stderr)
            return False
        return True

    def into_hospital(self) -> bool:
        """1000:92,99 → 醫院 1005（heal.walk_village）→ 照 waypoint 走到 38,48。已在醫院 → 只補 waypoint（已在站位不動）"""
        import heal
        import walk
        try:
            p = walk.wait_pos(4)
            if not p or p[0] != HOSPITAL:
                heal.walk_village()
            for wx, wy in HOSP_WAYPOINTS:
                walk.step_to(HOSPITAL, wx, wy)
        except RuntimeError as e:
            print(f'{SRC}：走進醫院站位失敗：{e}', file=sys.stderr)
            return False
        return True

    def talk(self, npc, at, then='') -> bool:
        """點 NPC → 輪詢對話框 → then；剛走到第 1 下常被吃掉，最多 3 次"""
        import walk
        for _ in range(3):
            if walk.talk_npc(npc, at, then=then):
                return True
        return False

    # ---- 委託面板 ----
    def daily_open(self) -> bool:
        """點委託接取 NPC 開面板：站位離 NPC 太遠 / 點位會落在 UI 上 → 先 step_to 38,48；點 → 等面板特徵；沒開再點（進醫院後右側小框會吃第一下）"""
        import walk
        for _ in range(4):
            if uikit.is_open(uikit.DAILY):
                return True
            p = walk.wait_pos(3, HOSPITAL)
            if not p or p[0] != HOSPITAL:
                return False
            at = (p[1], p[2])
            nx, ny = walk.npc_screen(DAILY_NPC, at)
            if not walk.safe(nx, ny) or max(abs(at[0] - DAILY_NPC[0]), abs(at[1] - DAILY_NPC[1])) > 8:
                try:
                    walk.step_to(HOSPITAL, *HOSP_STAND)
                except RuntimeError as e:
                    print(f'{SRC}：走回 {HOSP_STAND} 失敗：{e}', file=sys.stderr)
                    return False
                nx, ny = walk.npc_screen(DAILY_NPC, HOSP_STAND)
            uikit.gui('seq', f'click {nx} {ny}; wait 700', note='daily 點委託接取 NPC')
            for _i in range(8):
                if uikit.is_open(uikit.DAILY):
                    return True
                uikit.sleep(0.2)
        return uikit.is_open(uikit.DAILY)

    def daily_close(self) -> None:
        """✕ 關面板（先關快速合成彈窗）；絕不點空白處"""
        if uikit.is_open(uikit.QCRAFT):
            uikit.safe_click(*uikit.QCRAFT.close_xy, uikit.QCRAFT, note='daily 關快速合成彈窗', wait_ms=500)
        if uikit.is_open(uikit.DAILY):
            uikit.close_panel(uikit.DAILY, known_open=True)

    def panel_open(self) -> bool:
        return uikit.is_open(uikit.DAILY)

    def page_no(self):
        return dp.parse_page(''.join(uikit.ocr(PAGE_BOX, '-Zooms', '2,3')))

    def goto_page(self, page: int) -> bool:
        """翻到第 page 頁：讀得到頁碼就照差距點上 / 下一頁（每次 wait 500 後重讀）；頁碼讀不出（OCR 失敗）→ 盲翻：上一頁 4 次到第 1 頁（探路：連點 4 次每次都成功、
        第 1 頁再按上一頁的行為沒量過，假設夾住）再下一頁 page-1 次"""
        if self.page_no() is None:
            print(f'{SRC}：頁碼讀不出 → 盲翻到第 {page} 頁', file=sys.stderr)
            for _ in range(dp.RINGS - 1):
                if not uikit.safe_click(*PREV_XY, uikit.DAILY, note='daily 盲翻：上一頁', wait_ms=400):
                    return False
            for _ in range(page - 1):
                if not uikit.safe_click(*NEXT_XY, uikit.DAILY, note='daily 盲翻：下一頁', wait_ms=400):
                    return False
            return True
        for _ in range(7):
            cur = self.page_no()
            if cur is None:
                return False
            if cur == page:
                return True
            x, y = NEXT_XY if cur < page else PREV_XY
            if not uikit.safe_click(x, y, uikit.DAILY, note=f'daily 翻頁 {cur} → {page}', wait_ms=500):
                return False
        return self.page_no() == page

    def next_page(self) -> bool:
        return uikit.safe_click(*NEXT_XY, uikit.DAILY, note='daily 下一頁', wait_ms=500)

    def read_page(self) -> dict:
        """目前頁：{'names': [OCR 原字 ×2], 'states': ['red'|'green'|'?' ×2]}（名稱不修正，呼叫端 snap）"""
        names = []
        for box in NAME_BOXES:
            t = ''.join(uikit.ocr(box, *shopkit.TITLE_OPTS))
            names.append(t if t.strip() else ''.join(uikit.ocr(box, '-Zooms', '2,3')))
        cols = uikit.px(STATE_PX) or [None, None]
        return {'names': names, 'states': [dp.count_state(c) for c in cols]}

    def peek_item(self, k: int) -> str:
        """名稱讀不出時：開該項快速合成彈窗讀成品名大字（不按彈窗合成）→ 關彈窗"""
        if not uikit.safe_click(*MERGE_XY[k], uikit.DAILY, note=f'daily 開第 {k + 1} 項快速合成（讀名稱）', wait_ms=700):
            return ''
        nm = ''
        for _ in range(6):
            if uikit.is_open(uikit.QCRAFT):
                nm = ''.join(uikit.ocr(POP_NAME_BOX, *shopkit.TITLE_OPTS))
                break
            uikit.sleep(0.2)
        if uikit.is_open(uikit.QCRAFT):
            uikit.safe_click(*uikit.QCRAFT.close_xy, uikit.QCRAFT, note='daily 關快速合成彈窗', wait_ms=500)
        return nm

    def reward_count(self):
        return dp.parse_reward(''.join(uikit.ocr(REWARD_BOX, '-Zooms', '2,3')))

    def craft_item(self, k: int, name: str) -> tuple:
        """第 k 項快速合成：開彈窗 → 成品名核對 → 材料計數不是紅字 → 彈窗「合成」（花 1000 石幣）→ 關彈窗 → 該項變綠。回 (ok, 原因)"""
        if not uikit.safe_click(*MERGE_XY[k], uikit.DAILY, note=f'daily 開第 {k + 1} 項快速合成「{name}」', wait_ms=700):
            return False, '委託面板不在，沒點'
        for _ in range(8):
            if uikit.is_open(uikit.QCRAFT):
                break
            uikit.sleep(0.2)
        else:
            return False, '快速合成彈窗沒開'

        def close_pop():
            uikit.safe_click(*uikit.QCRAFT.close_xy, uikit.QCRAFT, note='daily 關快速合成彈窗', wait_ms=500)
        nm = ''.join(uikit.ocr(POP_NAME_BOX, *shopkit.TITLE_OPTS))
        if dp.snap_item(nm, [dp.norm(name)]) is None:
            close_pop()
            return False, f'彈窗成品名 OCR 是 {nm!r}，不是「{name}」（沒合成）'
        if dp.popup_short(uikit.px(POP_COUNT_PX)):
            close_pop()
            return False, '彈窗材料計數有紅字（材料不足，沒合成）'
        if not uikit.safe_click(*POP_CRAFT_XY, uikit.QCRAFT, note=f'daily 合成「{name}」（1000 石幣）', allow=('craft',), wait_ms=1200):
            return False, '彈窗特徵不在，沒按合成'
        close_pop()
        for _ in range(8):
            if uikit.is_open(uikit.DAILY) and dp.count_state((uikit.px([STATE_PX[k]]) or [None])[0]) == 'green':
                return True, ''
            uikit.sleep(0.3)
        return False, '合成後該項沒變綠'

    def submit(self) -> bool:
        return uikit.safe_click(*SUBMIT_XY, uikit.DAILY, note='daily 提交委託', allow=('submit',), wait_ms=1500)

    def item_states(self) -> list:
        cols = uikit.px(STATE_PX) or [None, None]
        return [dp.count_state(c) for c in cols]

    # ---- 便利店 ----
    def shop_enter(self, store) -> bool:
        """走到店員前 2 格 → 點店員 → 「道具商店」→ 等便利店面板（最多 3 輪）"""
        stand = (store.x + SHOP_STAND_DX, store.y)
        if not self.walk_to(store.map, *stand):
            return False
        for _ in range(3):
            if not self.talk((store.x, store.y), stand, then=f'click {shopkit.SHOP_BTN[0]} {shopkit.SHOP_BTN[1]}'):
                continue
            for _i in range(8):
                if shopkit.shop_open():
                    return True
                uikit.sleep(0.4)
        return False

    def shop_select(self, name, store, state) -> bool:
        return shopkit.select_item(name, store.items, state)

    def shop_set_qty(self, q) -> bool:
        return shopkit.set_qty(q)

    def shop_buy(self) -> None:
        shopkit.buy_once()

    def shop_qty(self):
        return shopkit.qty_now()

    def shop_close(self) -> bool:
        return shopkit.close_shop()

    # ---- 背包 / 倉庫 ----
    def bag_check(self, role, names) -> tuple:
        """背包名稱核對：回 (找不到的名稱 list, 沒認出的格數)。bag.Session 開關背包"""
        import bag
        with bag.Session() as s:
            if s.rc:
                return list(names), -s.rc
            rc = bag.select_role(role)
            if rc:
                return list(names), -rc
            r = bag._names_in_bag(list(names))
        return [n for n in names if r['found'].get(n) is None], len(r.get('unread') or [])

    def depot_store(self, role, name, sub) -> int:
        import bag
        return bag.depot_store(role, name, depot=sub)

    def depot_take(self, role, name, sub) -> int:
        import bag
        return bag.depot_take(role, name, depot=sub)

    # ---- 收尾 ----
    def cleanup(self) -> None:
        """失敗收尾：關快速合成 / 委託面板 / 便利店（都用 ✕）；不認得的畫面不碰"""
        try:
            self.daily_close()
            shopkit.close_shop(2)
        except Exception:                                      # noqa: BLE001
            pass

    def grind_go(self) -> int:
        import grind
        return grind.go()


# ======================================================================================
# 流程
# ======================================================================================
class Stop(Exception):
    def __init__(self, rc: int, msg: str):
        super().__init__(msg)
        self.rc, self.msg = rc, msg


class Daily:
    def __init__(self, T, o: dict, roles: list, recipes=None, stores=None, where=None):
        self.T, self.o, self.roles = T, o, list(roles)
        self.recipes = recipes if recipes is not None else dp.load_recipes()
        if stores is None or where is None:
            stores, where = dp.load_stores()
        self.stores, self.where = stores, where
        order = [r for r in clients.leader_last() if r in self.roles] or list(self.roles)
        self.order = order                                     # DKBO2 → … → DKBO（隊長最後）
        self.leader = LEADER if LEADER in self.roles else self.order[-1]
        self.info = {}
        self.team = {}
        self.st = {}                                           # role → 進度 dict

    # ---- 共用 ----
    def fail(self, rc, msg, **kw):
        self.info.update(kw)
        raise Stop(rc, msg)

    def tool_fail(self, tool_rc, my_rc, msg, **kw):
        """工具回 8 / 9 / 10 → 原碼；其他 → 本檔對應碼"""
        self.fail(tool_rc if tool_rc in PASS else my_rc, msg, **kw)

    def save_role(self, role):
        dp.save(dp.role_path(role), self.st[role])

    def save_team(self):
        dp.save(dp.team_path(), self.team)

    def check_day(self):
        if not dp.check_date(self.team):
            self.fail(EXIT_ARGS, f'跨過 00:00（進度檔日期 {self.team.get("date")}，現在 {dp.today()}）：遊戲環數已清 0，停手；人看過再決定 --fresh', crossed=True)

    def plan_of(self, role) -> dict:
        st = self.st[role]
        done = [[bool(d) for d in pair] for pair in (st.get('done') or [])] or None
        return dp.plan_role(st['items'], self.recipes, self.where, self.stores, done)

    def role_complete(self, role) -> bool:
        st = self.st[role]
        if st.get('reward') == dp.RINGS:
            return True
        if not st.get('items'):
            return False
        plan = self.plan_of(role)
        return all(st['rings'][r['ring'] - 1].get('submitted') for r in plan['rings'] if r['supported']) and bool(plan['supported_rings'])

    def switch_to(self, role):
        rc = self.T.switch(role)
        if rc:
            self.tool_fail(rc, EXIT_PREP, f'切當前角色到 {role} 失敗（char rc {rc}）', char_rc=rc)

    # ---- 搬移（組隊帶隊走）----
    def leader_current(self):
        rc = self.T.ensure(self.leader)
        if rc:
            self.tool_fail(rc, EXIT_PREP, f'當前角色切不到隊長 {self.leader}（char rc {rc}）', char_rc=rc)

    def form_team(self):
        rc = self.T.form()
        if rc:
            self.tool_fail(rc, EXIT_PREP, f'組隊失敗（team rc {rc}）', team_rc=rc)

    def disband_team(self):
        rc = self.T.disband()
        if rc:
            self.tool_fail(rc, EXIT_PREP, f'解散隊伍失敗（team rc {rc}）', team_rc=rc)

    def go_hospital(self):
        """（隊長當前）→ 傳送薩姆吉爾（不在村 / 醫院才傳）→ 進醫院走到 38,48。不含組隊 / 解散"""
        T = self.T
        p = T.pos()
        if not p or p[0] not in (VILLAGE, HOSPITAL):
            if not T.to_town():
                self.fail(EXIT_PREP, '傳送薩姆吉爾失敗')
            T.sleep(1.0)
        if not T.into_hospital():
            self.fail(EXIT_WALK, f'走不到醫院站位 {HOSP_STAND}')

    def go_shops(self, stage: str):
        """（隊長當前）→ 到 1009（sam）/ 2009（fish）。已在目標地圖就不動"""
        T = self.T
        target = dp.SAM_MAP if stage == 'sam' else dp.FISH_MAP
        p = T.pos()
        if p and p[0] == target:
            return
        if stage == 'sam':
            if not p or p[0] != VILLAGE:
                if not T.to_town():
                    self.fail(EXIT_PREP, '傳送薩姆吉爾失敗')
                T.sleep(1.0)
            if not T.walk_to(*SAM_WALK, exit_map=dp.SAM_MAP):
                self.fail(EXIT_WALK, '走不進 1009（薩姆吉爾便利商店）')
        else:
            if not p or p[0] != MARINAS_MAP:
                if not T.to_marinas():
                    self.fail(EXIT_PREP, '傳送瑪麗娜絲失敗')
                T.sleep(1.0)
            if not T.walk_to(*FISH_WALK, exit_map=dp.FISH_MAP):
                self.fail(EXIT_WALK, '走不進 2009（瑪麗娜絲便利商店）')

    def move_team(self, where_: str):
        """隊長帶隊：當前 = 隊長 → 組隊 → 走 → 解散（隊員無法和 NPC 互動，各人要單人點店員 / 委託 NPC）"""
        self.check_day()
        self.leader_current()
        p = self.T.pos()
        target = {'hospital': HOSPITAL, 'sam': dp.SAM_MAP, 'fish': dp.FISH_MAP}[where_]
        already = bool(p and p[0] == target)
        if not already:
            self.form_team()
        if where_ == 'hospital':
            self.go_hospital()
        else:
            self.go_shops(where_)
        self.disband_team()

    # ---- 階段 ----
    def stage_prep(self):
        T = self.T
        rc = T.preflight()
        if rc:
            self.tool_fail(rc, EXIT_PREP, f'preflight 失敗（rc {rc}）')
        if not T.lock():
            event('警告：拿不到 grind.lock（netwatch 重登後可能搶畫面）')
        if not T.stop_follow():
            self.fail(EXIT_PREP, 'follow 停不掉（60 秒內沒結束）')
        T.encounter_off()
        self.leader_current()
        self.go_hospital()
        self.disband_team()

    def stage_read(self):
        for role in self.order:
            st = self.st[role]
            if st.get('read'):
                continue
            self.check_day()
            self.switch_to(role)
            self.read_role(role)
            self.save_role(role)
            event(f'read {role}：' + ' | '.join(f'{a}/{b}' for a, b in st['items']))
        if all(self.role_complete(r) for r in self.order):
            self.info['all_done'] = True
            self.fail(EXIT_ARGS, '今天所有角色都已完成每日委託（5/5）', all_done=True)

    def read_role(self, role):
        """（當前角色 = role）開面板 → 讀獎勵計數 → 1～5 頁 × 2 項。名稱 snap 不到 → 開快速合成彈窗讀大字再 snap；仍不行 → 225"""
        T, st = self.T, self.st[role]
        if not T.daily_open():
            self.fail(EXIT_WALK, f'{role} 委託面板打不開')
        try:
            st['reward'] = T.reward_count()
            if st['reward'] == dp.RINGS:                        # 今天 5/5 已完成：清單畫面可能不是 5 環 × 2 項，不讀、記成已讀
                st.update(read=True, items=[], done=[])
                return
            if T.page_no() not in (None, 1) and not T.goto_page(1):
                self.fail(EXIT_READ, f'{role} 翻不到第 1 頁')
            items, dones = [], []
            for page in range(1, dp.RINGS + 1):
                pg = T.read_page()
                pair = []
                for k in range(2):
                    nm = dp.snap_item(pg['names'][k], self.recipes)
                    if nm is None:
                        nm = dp.snap_item(T.peek_item(k), self.recipes)
                    if nm is None:
                        self.fail(EXIT_READ, f'{role} 第 {page} 環第 {k + 1} 項讀不出成品名（OCR {pg["names"][k]!r}，彈窗也不行）', read_page=page)
                    pair.append(nm)
                items.append(pair)
                dones.append([s == 'green' for s in pg['states']])
                if page < dp.RINGS and not T.next_page():
                    self.fail(EXIT_READ, f'{role} 第 {page} 頁後翻不了下一頁')
            st['items'], st['done'], st['read'] = items, dones, True
        finally:
            T.daily_close()

    def stage_plan(self):
        plans = {}
        total = 0
        for role in self.order:
            if self.role_complete(role):
                print(f'{role}：今天已完成 5/5，略過')
                continue
            plan = self.plan_of(role)
            plans[role] = plan
            for ln in dp.plan_lines(role, plan, self.stores, self.where):
                print(ln)
            for r in plan['rings']:
                if not r['supported']:
                    event(f'{role} 第 {r["ring"]} 環跳過：{r["reason"]}')
            total += plan['cost']['total']
        print(f'全隊石幣估算約 {total:,}（材料 {MAT_PRICE_TXT} / 個 + 合成 1,000 / 項；不讀石幣，只供參考）')
        self.info['cost_estimate'] = total
        for role in plans:
            if not plans[role]['supported_rings']:
                self.fail(EXIT_NOROLE, f'{role} 全部環都不支援（見上面各環原因）；不動作', role=role)
        if time.localtime().tm_hour == 23 and time.localtime().tm_min >= 50:
            event('警告：接近 00:00，預計跑不完（遊戲每日 0 點環數清 0）')
        if not self.o.get('confirm_buy'):
            self.fail(EXIT_NOBUY, '買材料 / 合成要花石幣，沒給 --confirm-buy → 不動作（已印計畫）')

    def stage_buy(self, stage: str):
        who = [r for r in self.order if dp.remaining_buy(self.plan_of(r), stage, self.st[r]['bought']) and not self.role_complete(r)]
        if not who:
            event(f'{stage}：沒有人要買 → 跳過')
            return
        self.move_team(stage)
        for role in who:
            self.check_day()
            self.switch_to(role)
            self.buy_role(role, stage)
            self.st[role]['stages'][stage] = True
            self.save_role(role)

    def evict(self, role, mat):
        """背包 → 個人倉庫（滿 → 公倉並記 in_public）；成功更新 ledger"""
        T, st = self.T, self.st[role]
        led = dp.Ledger(st['ledger'])
        rc = T.depot_store(role, mat, 'personal')
        sub = 'personal'
        if rc:
            if rc in PASS:
                self.fail(rc, f'存倉遇到 rc {rc}', bag_rc=rc)
            event(f'{role} 個人倉庫存「{mat}」失敗（bag rc {rc}）→ 改存公共倉庫')
            rc = T.depot_store(role, mat, 'public')
            sub = 'public'
            if rc:
                self.tool_fail(rc, EXIT_DEPOT, f'{role}「{mat}」個人倉庫和公共倉庫都存不進（bag rc {rc}）', bag_rc=rc)
        led.evict(mat, sub)
        key = 'in_personal' if sub == 'personal' else 'in_public'
        if mat not in st[key]:
            st[key].append(mat)
        st['ledger'] = led.to_dict()
        self.save_role(role)
        event(f'{role} 背包「{mat}」→ {"個人" if sub == "personal" else "公共"}倉庫')

    def buy_role(self, role, stage):
        T, st = self.T, self.st[role]
        plan = self.plan_of(role)
        route = dp.store_route(stage, dp.remaining_buy(plan, stage, st['bought']), self.where, self.stores, plan['first_use'])
        for store, mats in route:
            led = dp.Ledger(st['ledger'])
            incoming = [n for n, _ in mats]
            room = dp.make_room(led, plan, st['rings'], incoming)
            if room is None:
                self.fail(EXIT_BUY, f'{role} 背包放不下「{store.name}」的 {len(incoming)} 種材料，又沒有可存倉的材料', role=role)
            for m in room:
                self.evict(role, m)
            self.buy_at(role, plan, store, mats)

    def buy_at(self, role, plan, store, mats):
        T, st = self.T, self.st[role]
        rc = T.preflight()
        if rc:
            self.tool_fail(rc, EXIT_BUY, f'preflight 失敗（rc {rc}）')
        if not T.shop_enter(store):
            T.cleanup()
            self.fail(EXIT_WALK, f'{role} 走不到 / 點不開「{store.name}」（{store.map}:{store.x},{store.y}）的道具商店', role=role)
        done = []
        try:
            nav = {'drags': 0}
            for name, q in mats:
                ok = self.buy_item(role, plan, store, name, q, nav, protect={n for n, _ in mats})
                if not ok:
                    self.fail(EXIT_BUY, f'{role} 在「{store.name}」買「{name}」×{q} 失敗（不重買、已關店）', role=role, item=name)
                done.append(name)
        finally:
            T.shop_close()
        led_now = dp.Ledger(st['ledger'])
        check_names = [n for n in done if led_now.bag.get(n, 0) > 0]          # 買完又被存倉的（反應式存倉）不核對背包
        missing, unread = T.bag_check(role, check_names) if check_names else ([], 0)
        if missing:
            if unread < 0:
                self.tool_fail(-unread, EXIT_BUY, f'{role} 買完核對背包失敗（bag rc {-unread}）', role=role)
            if len(missing) > unread:                           # 比「沒認出名字的格」還多 → 確定缺
                led = dp.Ledger(st['ledger'])
                for n in missing:
                    st['bought'].pop(n, None)
                    led.bag.pop(n, None)
                st['ledger'] = led.to_dict()
                self.save_role(role)
                self.fail(EXIT_BUY, f'{role} 在「{store.name}」買完，但背包找不到 {"、".join(missing)}（數量框雖歸 0；不重買，請人看）', role=role, missing=missing)
            event(f'{role} 背包名稱核對：{"、".join(missing)} 沒認出（有 {unread} 格沒讀出名字，視為已買）')
        event(f'{role} {store.name} 買完：' + '、'.join(f'{n}×{dict(mats)[n]}' for n in done))

    def buy_item(self, role, plan, store, name, q, nav, protect=()) -> bool:
        """店內一項：選商品（標題核對）→ 數量 q → 購買 → 數量框歸 0。失敗（可能背包放不下）→ 存最晚環的材料再試一次（只一次）。成功才記 bought / ledger"""
        T, st = self.T, self.st[role]
        for attempt in range(2):
            if not T.shop_select(name, store, nav):
                event(f'{role} 選不到商品「{name}」（{store.name}）')
                return False
            if not T.shop_set_qty(q):
                event(f'{role} 數量輸入 {q} 讀回不對（{name}）')
                return False
            T.shop_buy()
            after = T.shop_qty()
            if after == 0:
                led = dp.Ledger(st['ledger'])
                led.buy(name, q)
                st['ledger'] = led.to_dict()
                st['bought'][name] = int(st['bought'].get(name, 0)) + q
                self.save_role(role)
                return True
            event(f'{role} 買「{name}」後數量框讀到 {after!r}（應為 0）' + ('；背包可能已滿 → 存倉再試一次' if attempt == 0 else ''))
            if attempt == 0:
                led = dp.Ledger(st['ledger'])
                m = dp.choose_evict(led, plan, st['rings'], protect={name} | set(protect))
                if m is None:                                   # 同店其他材料以外沒東西可存 → 連同店材料一起考慮
                    m = dp.choose_evict(led, plan, st['rings'], protect={name})
                if m is None:
                    return False
                T.shop_close()                                  # 存倉要開背包（便利店面板擋住）→ 先關店再回來
                self.evict(role, m)
                if not T.shop_enter(store):
                    return False
                nav['drags'] = 0
        return False

    # ---- 合成 / 提交 ----
    def craft_work(self, role, final: bool) -> bool:
        """這個人現在有沒有事可做（mid：背包材料齊的項或該環已可提交；final：任何還沒提交的支援環）"""
        if self.role_complete(role):
            return False
        st, plan = self.st[role], self.plan_of(role)
        led = dp.Ledger(st['ledger'])
        for r, rs in zip(plan['rings'], st['rings']):
            if not r['supported'] or rs.get('submitted'):
                continue
            if final or dp.ring_ready(rs, r['items']):
                return True
            for k, it in enumerate(r['items']):
                if not it['done'] and not rs['crafted'][k] and dp.craftable(it, led, bag_only=True):
                    return True
        return False

    def stage_craft(self, final: bool):
        stage = 'final' if final else 'mid'
        who = [r for r in self.order if self.craft_work(r, final)]
        if not who:
            event(f'{stage}：沒有人有可合成 / 可提交的項 → 跳過')
            return
        self.move_team('hospital')
        for role in who:
            self.check_day()
            self.switch_to(role)
            self.craft_role(role, final)
            self.st[role]['stages'][stage] = True
            self.save_role(role)

    def craft_role(self, role, final: bool):
        T, st = self.T, self.st[role]
        plan = self.plan_of(role)
        opened = False
        try:
            for r, rs in zip(plan['rings'], st['rings']):
                if not r['supported'] or rs.get('submitted'):
                    continue
                ri = r['ring']
                led = dp.Ledger(st['ledger'])
                todo = [k for k, it in enumerate(r['items']) if not it['done'] and not rs['crafted'][k]
                        and (final or dp.craftable(it, led, bag_only=True))]
                if not todo and not dp.ring_ready(rs, r['items']):
                    continue
                if final and todo:
                    if opened:
                        T.daily_close()
                        opened = False
                    self.fetch_materials(role, plan, r, todo)
                if not opened:
                    if not T.daily_open():
                        self.fail(EXIT_WALK, f'{role} 委託面板打不開', role=role)
                    opened = True
                if not T.goto_page(ri):
                    self.fail(EXIT_CRAFT, f'{role} 翻不到第 {ri} 頁', role=role)
                for k in todo:
                    it = r['items'][k]
                    ok, why = T.craft_item(k, it['name'])
                    if not ok:
                        self.fail(EXIT_CRAFT, f'{role} 第 {ri} 環「{it["name"]}」合成失敗：{why}', role=role, ring=ri)
                    led = dp.Ledger(st['ledger'])
                    led.craft(it['mats'], it['name'])
                    st['ledger'] = led.to_dict()
                    rs['crafted'][k] = True
                    self.save_role(role)
                    event(f'{stage_name(final)} {role} 第 {ri} 環「{it["name"]}」合成完成')
                if dp.ring_ready(rs, r['items']):
                    self.submit_ring(role, r, rs)
                    peppers = [n for n, _ in sum((it['mats'] for it in r['items']), []) if n in dp.PEPPERS]
                    if peppers and final:
                        T.daily_close()
                        opened = False
                        self.return_peppers(role, sorted(set(peppers)))
        finally:
            if opened:
                T.daily_close()
        if final:
            self.verify_complete(role, plan)

    def fetch_materials(self, role, plan, ring, todo):
        """final：這環要合成的項的材料先到背包（個人倉庫 / in_public 的公倉 / 胡椒的公倉）。panel 已關。背包放不下 → 先存最晚環的材料"""
        T, st = self.T, self.st[role]
        led = dp.Ledger(st['ledger'])
        need = {}
        for k in todo:
            for n, q in ring['items'][k]['mats']:
                need[n] = need.get(n, 0) + q
        take = []
        for n, q in need.items():
            if n in dp.PEPPERS:
                if led.bag.get(n, 0) <= 0:
                    take.append((n, 'public'))
            elif led.bag.get(n, 0) < q:
                sub = 'personal' if led.personal.get(n, 0) > 0 else ('public' if led.public.get(n, 0) > 0 else None)
                if sub is None:
                    self.fail(EXIT_DEPOT, f'{role} 第 {ring["ring"]} 環要「{n}」×{q}，背包只有 {led.bag.get(n, 0)}、倉庫帳上也沒有', role=role, item=n)
                take.append((n, sub))
        if not take:
            return
        room = dp.make_room(led, plan, st['rings'], [n for n, _ in take], protect=set(need))
        if room is None:
            self.fail(EXIT_BUY, f'{role} 背包放不下第 {ring["ring"]} 環的材料，又沒有可存倉的材料', role=role)
        for m in room:
            self.evict(role, m)
        for n, sub in take:
            rc = T.depot_take(role, n, sub)
            for _ in range(3):                                   # 94 = 背包滿（模型比實際寬鬆，例：背包原本就有雜物）→ 多存一種不需要的再取
                if rc != 94:
                    break
                led = dp.Ledger(st['ledger'])
                m = dp.choose_evict(led, plan, st['rings'], protect=set(need) | {n})
                if m is None:
                    break
                event(f'{role} 取「{n}」時背包滿（bag rc 94）→ 先把「{m}」存倉再取')
                self.evict(role, m)
                rc = T.depot_take(role, n, sub)
            if rc:
                if n in dp.PEPPERS:
                    self.fail(EXIT_PEPPER if rc not in PASS else rc, f'{role} 公共倉庫取不到「{n}」（bag rc {rc}；胡椒要使用者先放公倉，腳本不買）', role=role, item=n, bag_rc=rc)
                self.tool_fail(rc, EXIT_DEPOT, f'{role} 從{sub}倉庫取「{n}」失敗（bag rc {rc}）', role=role, item=n, bag_rc=rc)
            led = dp.Ledger(st['ledger'])
            if n in dp.PEPPERS:
                led.bag[n] = max(1, led.bag.get(n, 0))           # 整疊取出，量未知（使用者備的）；帳上記 1 當「在背包」旗標
            else:
                led.take(n, sub)
                key = 'in_personal' if sub == 'personal' else 'in_public'
                if n in st[key]:
                    st[key].remove(n)
            st['ledger'] = led.to_dict()
            self.save_role(role)
            event(f'final {role} 取回「{n}」（{"個人" if sub == "personal" else "公共"}倉庫 → 背包）')

    def return_peppers(self, role, peppers):
        """胡椒用完整疊存回公共倉庫（借出的道具要還）"""
        T, st = self.T, self.st[role]
        for n in peppers:
            led = dp.Ledger(st['ledger'])
            if led.bag.get(n, 0) <= 0:
                continue
            rc = T.depot_store(role, n, 'public')
            if rc:
                self.tool_fail(rc, EXIT_DEPOT, f'{role}「{n}」存回公共倉庫失敗（bag rc {rc}）；胡椒還在背包，請人處理', role=role, item=n, bag_rc=rc)
            led.bag.pop(n, None)
            st['ledger'] = led.to_dict()
            self.save_role(role)
            event(f'final {role} 胡椒「{n}」整疊存回公共倉庫')

    def submit_ring(self, role, ring, rs):
        """兩項都 1/1 綠才提交；提交後 n/5 +1（讀不到計數才退而求其次看兩項不再是綠）"""
        T, st = self.T, self.st[role]
        states = T.item_states()
        if states != ['green', 'green']:
            self.fail(EXIT_CRAFT, f'{role} 第 {ring["ring"]} 環兩項不是 1/1 綠（{states}）→ 不提交', role=role, ring=ring['ring'])
        before = T.reward_count()
        if not T.submit():
            self.fail(EXIT_CRAFT, f'{role} 提交委託點不到（面板特徵不在）', role=role)
        T.sleep(0.5)
        after = T.reward_count()
        ok = (after == before + 1) if (before is not None and after is not None) else (T.item_states() != ['green', 'green'])
        if not ok:
            self.fail(EXIT_CRAFT, f'{role} 第 {ring["ring"]} 環提交後計數 {before} → {after}（應 +1）', role=role, ring=ring['ring'])
        rs['submitted'] = True
        led = dp.Ledger(st['ledger'])
        led.submit([it['name'] for it in ring['items'] if not it['done']])
        st['ledger'] = led.to_dict()
        if after is not None:
            st['reward'] = after
        self.save_role(role)
        event(f'提交 {role} 第 {ring["ring"]} 環（獎勵計數 {before} → {after}）')

    def verify_complete(self, role, plan):
        """final 後：支援的環都提交了嗎；全 5 環支援時獎勵計數要 5、讀不到才看背包有沒有裝備升級石（兩訊號取一，只是參考）"""
        st = self.st[role]
        left = [r['ring'] for r in plan['rings'] if r['supported'] and not st['rings'][r['ring'] - 1].get('submitted')]
        if left:
            self.fail(EXIT_CRAFT, f'{role} 還有環沒提交：{left}', role=role)
        n_sub = len(plan['supported_rings'])
        cnt = st.get('reward')
        if len(plan['supported_rings']) == dp.RINGS:
            if cnt is not None and cnt != dp.RINGS:
                self.fail(EXIT_CRAFT, f'{role} 5 環都提交了，但獎勵計數是 {cnt}/5', role=role)
            if cnt is None:
                miss, unread = self.T.bag_check(role, [STONE])
                if miss and unread == 0:
                    self.fail(EXIT_CRAFT, f'{role} 5/5 驗證：獎勵計數讀不到、背包也沒有「{STONE}」', role=role)
        event(f'final {role} 完成（{n_sub} 環提交）' + ('' if n_sub == dp.RINGS else f'；{dp.RINGS - n_sub} 環不支援已跳過'))

    def stage_finish(self):
        T = self.T
        self.leader_current()
        T.unlock()
        self.form_team()
        if self.o.get('grind', True):
            rc = T.grind_go()
            if rc:
                self.tool_fail(rc, EXIT_PREP, f'去練功失敗（grind rc {rc}）', grind_rc=rc)

    # ---- 主流程 ----
    def go(self) -> int:
        o = self.o
        today = dp.today()
        team = None if o.get('fresh') else dp.load(dp.team_path())
        if team and dp.stale(team, today):
            if team.get('complete'):
                team = None                                      # 昨天的 run 已經跑完 → 今天新的一輪
            else:
                self.team = team
                self.fail(EXIT_ARGS, f'進度檔是 {team.get("date")} 的、當時沒跑完（今天 {today}）：遊戲環數已清 0，停手；人看過再決定 --fresh')
        if team and team.get('complete') and not o.get('from_stage'):
            self.team = team
            self.fail(EXIT_ARGS, f'今天（{today}）已經完成過一輪（進度檔 complete）；要重跑用 --from 段 或 --fresh', all_done=True)
        if not team or set(team.get('roles') or []) != set(self.roles):
            team = dp.new_team_state(self.roles, today)
            fresh_roles = True
        else:
            fresh_roles = bool(o.get('fresh'))
        self.team = team
        for role in self.roles:
            self.st[role] = dp.load_role(role, today, fresh=fresh_roles)
            if dp.stale(self.st[role], today):
                self.st[role] = dp.new_role_state(role, today)
        stages = list(dp.STAGES)
        start = o.get('from_stage')
        if not start:
            start = next((s for s in stages if s not in team.get('done', [])), 'finish')
        if start not in stages:
            self.fail(EXIT_ARGS, f'--from {start!r} 不是段名 {stages}')
        team.setdefault('done', [])
        stop_after = o.get('stop_after')
        try:
            for s in stages[stages.index(start):]:
                team['stage'] = s
                self.save_team()
                event(f'段 {s} 開始')
                self.dispatch(s)
                if s not in team['done']:
                    team['done'].append(s)
                self.save_team()
                if stop_after and s == stop_after:
                    break
            if stages[-1] in team['done']:
                team['complete'] = True
                self.save_team()
        except Stop as e:
            self.info['stop'] = e.msg
            raise
        return 0

    def dispatch(self, s):
        if s in ('sam', 'fish'):
            self.stage_buy(s)
        elif s == 'mid':
            self.stage_craft(False)
        elif s == 'final':
            self.stage_craft(True)
        else:
            getattr(self, 'stage_' + s)()


def stage_name(final: bool) -> str:
    return 'final' if final else 'mid'


# ======================================================================================
def run(roles=None, confirm_buy: bool = False, from_stage=None, fresh: bool = False, dry_run: bool = False, grind: bool = True,
        tools=None, stop_after=None, recipes=None, stores=None, where=None) -> int:
    LAST.clear()
    roles = list(roles) if roles else list(ROLES)
    if not roles:
        print(f'{SRC}：PSA_CLIENT={clients.name()} 沒有名單（clients.ROSTERS）', file=sys.stderr)
        return EXIT_ARGS
    T = tools or Tools()
    D = Daily(T, dict(confirm_buy=confirm_buy, from_stage=from_stage, fresh=fresh, grind=grind, stop_after=stop_after), roles, recipes, stores, where)
    event(f'開始：{"、".join(roles)}（{clients.name()}）confirm_buy={confirm_buy} from={from_stage} fresh={fresh} dry_run={dry_run} grind={grind}')
    rc = 0
    try:
        if dry_run:
            rc = _plan_only(D)
        else:
            rc = D.go()
    except Stop as e:
        rc = e.rc
        event(f'停手（{rc}）：{e.msg}')
        if rc not in (EXIT_ARGS, EXIT_NOBUY, EXIT_NOROLE):
            try:
                T.cleanup()
            except Exception:                                  # noqa: BLE001
                pass
    except Exception as e:                                     # noqa: BLE001  任何意外都先關面板再往上丟（不留面板擋住後面的腳本）
        try:
            T.cleanup()
        except Exception:                                      # noqa: BLE001
            pass
        event(f'例外：{type(e).__name__}: {e}')
        raise
    finally:
        if not dry_run:
            try:
                T.unlock()
            except Exception:                                  # noqa: BLE001
                pass
    LAST.update(D.info, ok=rc == 0, rc=rc, desc=dp.EXIT_NAMES.get(rc, ''))
    if not rc:
        event('完成')
    return rc


def _plan_only(D: Daily) -> int:
    """離線：讀每人進度檔印計畫（沒讀過清單的人只提示）"""
    today = dp.today()
    n = 0
    for role in D.order:
        st = dp.load_role(role, today)
        if not st.get('read'):
            print(f'{role}：尚未讀清單（先 daily.py read-all）')
            continue
        D.st[role] = st
        for ln in dp.plan_lines(role, D.plan_of(role), D.stores, D.where):
            print(ln)
        n += 1
    return 0 if n else EXIT_ARGS


def show() -> int:
    team = dp.load(dp.team_path())
    print(f'全隊：{json.dumps(team, ensure_ascii=False) if team else "（沒有進度檔）"}')
    for role in ROLES:
        st = dp.load(dp.role_path(role))
        if not st:
            print(f'{role}：（沒有進度檔）')
            continue
        rings = ' '.join(('S' if r.get('submitted') else ('c' if any(r['crafted']) else '-')) for r in st['rings'])
        print(f'{role}：日期 {st["date"]} 已讀={st["read"]} 環(S=提交 c=有合成)={rings} 獎勵計數={st.get("reward")} 已買 {len(st["bought"])} 種 '
              f'個人倉庫 {st["in_personal"]} 公倉 {st["in_public"]} 段 {sorted(st["stages"])}')
    return 0


def main(argv=None) -> int:
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('cmd', choices=['read-all', 'plan', 'show', 'run'])
    ap.add_argument('--roles', help='逗號分隔角色（預設本視窗名單全部）')
    ap.add_argument('--from', dest='from_stage', choices=list(dp.STAGES), help='從這一段開始（預設從進度檔續跑）')
    ap.add_argument('--confirm-buy', action='store_true', help='買材料（500 / 個）與合成（1000 / 項）；沒給 = 讀清單 + 印計畫就停（221）')
    ap.add_argument('--fresh', action='store_true', help='丟掉進度檔重來（跨過 00:00 後）')
    ap.add_argument('--dry-run', action='store_true', help='同 plan（不碰遊戲）')
    ap.add_argument('--no-grind', action='store_true', help='最後不去練功')
    a = ap.parse_args(argv)
    if not ROLES:
        print(f'{SRC}：PSA_CLIENT={clients.name()} 沒有名單', file=sys.stderr)
        return EXIT_ARGS
    roles = [r.strip() for r in a.roles.split(',') if r.strip()] if a.roles else None
    if roles:
        import charname
        roles = [next((x for x in ROLES if charname.canon(x) == charname.canon(r)), r) for r in roles]
        bad = [r for r in roles if r not in ROLES]
        if bad:
            print(f'{SRC}：角色 {bad} 不在本視窗名單 {ROLES}', file=sys.stderr)
            return EXIT_ARGS
    if a.cmd == 'show':
        return show()
    if a.cmd == 'plan' or a.dry_run:
        return _finish_cli(run(roles, dry_run=True))
    import winenv
    winenv.enable_server()
    if a.cmd == 'read-all':
        return _finish_cli(run(roles, from_stage='prep', fresh=a.fresh, stop_after='read'))
    return _finish_cli(run(roles, a.confirm_buy, a.from_stage, a.fresh, False, not a.no_grind))


def _finish_cli(rc: int) -> int:
    print(json.dumps(dict(LAST, rc=rc), ensure_ascii=False, default=str))
    return rc


if __name__ == '__main__':
    sys.exit(main())
