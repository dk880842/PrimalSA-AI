#!/usr/bin/env python3
"""買「溫蒂妮Lv5的金幣」（競技場道具屋 500 石幣）→ 穿上 → 外掛隊長人物首次動作 = 風的精靈Lv.5 並打勾 → 回村 → 組隊 → 去練功。只用標準函式庫。

背景：金幣附帶技能「風的精靈Lv.5」，裝備後外掛「人物首次動作」下拉才會出現這個選項（ui/ass.md）；解任務 BOSS 戰靠它（ass.QUEST_BATTLE）。
新角色開局（newchar.py buy 步驟）與任何新視窗的隊長都要做一次。2026-10-09 主視窗 DKBO 手動做過（notes/leveling.md 03:11）。
**實機驗證狀態（2026-10-15 寫成時）**：手動探路只走到「便利店面板開著、已選好溫蒂妮Lv5的金幣、價格 500、數量 1」就被 watch 的全視窗驗證旗標擋下
（便利店面板不在 screen_sigs 認得清單，開著超過 10 秒 watch 判「連續 10 秒不認得」寫 verify-halt.json）→ **購買 / 穿戴 / 首次動作 / 回村 腳本沒有實機跑過**；
座標來自該次手動截圖（進競技場 / 道具屋 / 便利店 / 背包裝備格）與 ui/*.md 既有實測。

用法（專案根目錄；WSL / Windows 原生指令相同；PSA_CLIENT=PrimalSA2 → 隊長 DKBO6）：
  uv run --no-project python tools/gui/buywendy.py plan                       # 只讀（開一次背包看裝備 / 背包、不點購買）：已有金幣 → 買 / 穿都跳過
  uv run --no-project python tools/gui/buywendy.py run --confirm-buy [--no-form] [--no-grind] [--dry-run]
    --confirm-buy   花 500 石幣（沒給只做 plan，不買；已有金幣不需要這個旗標）
    --no-form       回村後不 team.form（預設會組隊）
    --no-grind      組隊後不去練功（預設 grind.go）
    --dry-run       同 plan
  可 import：buywendy.run(confirm_buy=False, dry_run=False, form=True, grind=True, tools=None) → 退出碼；結果 dict 在 buywendy.LAST

流程（每步先看狀態：已完成就跳過，可從任何中斷點重跑；進度只靠遊戲現況，不靠進度檔）：
  check   preflight → 當前角色 = 隊長（char.ensure）→ 背包面板開一次：背包有沒有 / 裝備格（2 個飾品格 + 腰飾格）彈窗名稱有沒有「溫蒂妮Lv5的金幣」+ 讀石幣（OCR）
          已穿 → 直接做 first；在背包 → 直接 wear；都沒有 → 要買（沒 --confirm-buy 就停，回 201）
  buy     停 follow（grind.stop_follow）→ 關原地遇敵 + 等戰鬥結束 → 城鎮傳送薩姆吉爾（1000）→ team.disband（隊員無法和 NPC 互動；本來單人也行）→
          走到 1000:55,61 點「鬥技場嚮導」(56,59) →「進入競技場」948,461 → 130:52,19 → 走到 130:46,6 點「鬥技場的道具屋」(43,3) →「道具商店」948,461 →
          便利店面板（**開著超過約 10 秒 watch 會寫全視窗停手旗標，所以商店內動作壓在 ~6 秒：選項 → 讀一次名稱 → 買 → 關**）：
          點溫蒂妮Lv5的金幣 700,440 → OCR 右側標題核對「溫蒂妮Lv5的金幣」（不吻合 = 不買、關店、回 205）→ 購買 995,592 → 提示「確定」615,557 → ESC
          → 開背包驗：背包有金幣 + 石幣少剛好 500（讀得到才驗；少 ≠ 500 回 205 不再買）
  wear    bag.wear_item（找格 → 彈窗名稱核對 → 穿戴 618,662 → 驗格子變空）→ 重看裝備格確認真的穿上
  first   外掛面板（ass._many）選隊長 → 戰鬥設置頂端：人物首次動作下拉 1137,313 → OCR 清單找「風的精靈」→ 點選項 → OCR 讀回 → 勾選框 656,313 沒勾就勾（像素讀回）
          已是「風的精靈」+ 已勾 = 不點
  back    城鎮傳送回薩姆吉爾（競技場內可直接開傳送）→ team.form（--no-form 跳過）→ grind.go 去練功（--no-grind 跳過；依等級選點、follow 由 grind.go 起）

退出碼（共用 0 / 1 / 2 / 8 / 9 / 10 見 uikit；其他工具 40～184；本檔 200～209，2026-10-15 grep 過沒人用）：
  200 參數 / 這個 PSA_CLIENT 沒有名單
  201 preflight / 切回隊長失敗；要買但沒給 --confirm-buy
  202 讀背包 / 裝備失敗（info.bag_rc：90～96）
  203 停 follow / 關遇敵 / 回薩姆吉爾 / 解散隊伍失敗
  204 進競技場 / 走到道具屋 / 點不開對話框 / 沒到 130
  205 商店：沒開 / 名稱不符 / 買了沒進背包 / 石幣少的不是 500
  206 穿戴失敗（info.bag_rc）或穿完看不到金幣在裝備格
  207 外掛首次動作失敗（info.ass_rc：ass 退出碼；12 = 下拉裡沒有風的精靈 = 金幣沒穿上）
  208 回村 / 組隊失敗（info.team_rc）
  209 去練功失敗（info.grind_rc：50～59）
  8 / 9 / 10：任何一步的工具回這三個 → 原碼停手（佔用 / 疑似驗證視窗 / 斷線，鐵則 5）
"""
import argparse
import json
import re
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import clients  # noqa: E402
import logpaths  # noqa: E402
import uikit  # noqa: E402

SRC = 'buywendy'
EVENT_LOG = logpaths.p(clients.npath('quest-events.log'))     # 主視窗 = notes/；其他 = notes/clients/<程序名>/

EXIT_ARGS, EXIT_PRE, EXIT_BAG, EXIT_TOWN, EXIT_ARENA, EXIT_SHOP, EXIT_WEAR, EXIT_FIRST, EXIT_BACK, EXIT_GRIND = range(200, 210)
PASS = (uikit.EXIT_IN_BATTLE, uikit.EXIT_UNKNOWN_SCREEN, uikit.EXIT_HALT)   # 8 / 9 / 10 原碼停手

ITEM = '溫蒂妮Lv5的金幣'
PRICE = 500
SKILL = '風的精靈'                       # 附帶技能；外掛首次動作下拉選項是「風的精靈Lv.5」
ALL_ROLES = clients.roster()
LEADER = ALL_ROLES[0] if ALL_ROLES else ''

# ---- 版面（2026-10-15 PrimalSA2 實測；截圖座標 1440×830，鏡頭最左）----
GUIDE, GUIDE_STAND = (56, 59), (55, 61)          # 薩姆吉爾村 1000：鬥技場嚮導（門票販賣員 50,62 旁）；站 55,61 時身體在截圖 ≈690,305（walk.npc_screen 算 683,312）
ENTER_BTN = (948, 461)                           # 嚮導對話框「進入競技場」
ROLE_FIRST_DD = (1137, 313)                      # 外掛 戰鬥設置：人物 首次動作 下拉 ▼（ui/ass.md；選項在欄位下方每列 +42，x=944）
VILLAGE, ARENA = 1000, 130
SHOP_NPC, SHOP_STAND = (43, 3), (46, 6)          # 競技場 130：鬥技場的道具屋（走 46,6 後點她，身體 ≈527,375）；牆在 y=4，只能從南邊點
SHOP_BTN = (948, 461)                            # 道具屋對話框「道具商店」
ITEM_XY = (700, 440)                             # 便利店左欄第 3 列右邊「溫蒂妮Lv5的金幣」卡（清單未捲動）
TITLE_BOX = (880, 185, 230, 45)                  # 便利店右側標題（選中的商品名；紅底米白字）
SKILL_BOX = (850, 285, 300, 36)                  # 右側「技能　風的精靈Lv.5」列
PRICE_BOX = (900, 505, 200, 40)                  # 右側總價（石幣圖示右邊）
BUY_BTN, CONFIRM_BTN = (995, 592), (615, 557)    # 購買 / 提示「確定」（同 shopbuy）
COIN_BOX = (285, 8, 130, 30)                     # 背包 / 商店面板頂端「石幣 150,000」（面板開著才有這條）
# 裝備格（背包頁中間人物圖兩側）：左上 / 右上 = 飾品格、下中 = 腰飾格；2026-10-15 DKBO6 實測三格都是空剪影、金幣沒穿
ACC_SLOTS = [(234, 210), (624, 210), (425, 455)]
EQUIP_POPUP_WAIT_S = 1.0                         # 點裝備格後等彈窗；空格不會開彈窗


def event(msg: str) -> None:
    line = f'{time.strftime("%Y-%m-%d %H:%M:%S")} [buywendy] {msg}'
    print(line, flush=True)
    try:
        EVENT_LOG.parent.mkdir(parents=True, exist_ok=True)
        with open(EVENT_LOG, 'a', encoding='utf-8') as f:
            f.write(line + '\n')
    except OSError:
        pass


# ---- 純函式 ----
def parse_coin(text) -> int | None:
    """「150,000」（OCR 可能夾空白 / 句點 / 多倍率重複）→ 150000；讀不到 None。多倍率串接（-Zooms）會把同一串數字重複 2～3 次 → 整段等分重複只取一份"""
    t = re.sub(r'[\s,.，。]', '', str(text or ''))
    if not t.isdigit():
        t = ''.join(re.findall(r'\d+', t))
    for n in (4, 3, 2):
        if t and len(t) % n == 0 and len(t) // n >= 3 and t[:len(t) // n] * n == t:
            t = t[:len(t) // n]
            break
    return int(t) if t else None


def title_ok(text) -> bool:
    """便利店右側標題是不是「溫蒂妮Lv5的金幣」：要有「蒂妮」+ Lv5 + 金幣，且不是豎琴（Lv4）/ 芙雷美雅 / 阿薩 等同系列兄弟（同價 500）。
    OCR 容錯：Lv 的 v 可能被讀成 V / u、數字 5 可能讀成 S（只放寬 Lv 與 5 的字形，不放寬名字）"""
    t = re.sub(r'\s+', '', str(text or ''))
    if not t:
        return False
    if any(b in t for b in ('豎琴', '芙雷', '美雅', '阿薩', '阿昆', '貝鈴', '鳴子', '木笛')):
        return False
    return '蒂妮' in t and '金幣' in t and bool(re.search(r'L[vVuU][5SsＳ]', t))


def option_pos(lines, want: str):
    """下拉清單 OCR 行 [(文字, x, y)] → 唯一吻合「want」的 (x, y)；完全相等優先；多筆不同位置 / 沒有 → None。與 ass.find_option 同規則（不依賴它的固定欄位）"""
    exact = [(x, y) for t, x, y in lines if t.replace(' ', '') == want]
    hits = exact or [(x, y) for t, x, y in lines if want in t.replace(' ', '')]
    uniq = []
    for x, y in hits:                                                     # 多倍率 OCR 同一列會讀 2～3 次（座標差 1～3px）→ 8px 內視為同一列
        if not any(abs(x - ux) <= 8 and abs(y - uy) <= 8 for ux, uy in uniq):
            uniq.append((x, y))
    return uniq[0] if len(uniq) == 1 else None


def coin_delta_ok(before, after, price: int = PRICE) -> bool | None:
    """石幣前後差剛好 price → True；差不是 price → False；任一讀不到 → None（呼叫端改看背包有沒有道具）"""
    if before is None or after is None:
        return None
    return before - after == price


# ---- 碰遊戲的動作（既有工具的薄包裝；測試換成 FakeTools）----
class Tools:
    def preflight(self):
        return uikit.preflight(SRC)

    def char_ensure(self, name):
        import char
        return char.ensure(name)

    def sleep(self, s):
        uikit.sleep(s)

    # -- 讀狀態 --
    def inspect(self) -> tuple:
        """背包面板開一次 → (rc, {'bag': 格號|None, 'worn': bool, 'coin': 石幣|None})。
        背包找名稱 → 沒有再點三個裝備格讀彈窗名稱（空格不開彈窗；彈窗只讀不按任何鈕，ESC 關）→ 讀頂端石幣"""
        import bag
        out = {'bag': None, 'worn': False, 'coin': None}
        with bag.Session() as s:
            if s.rc:
                return s.rc, out
            rc = bag.select_role(LEADER)
            if rc:
                return rc, out
            r = bag._names_in_bag([ITEM])
            out['bag'] = r['found'].get(ITEM)
            out['coin'] = self.read_coin()
            if out['bag'] is None:
                for x, y in ACC_SLOTS:
                    if not bag._click(x, y, bag.BAG, f'buywendy 點裝備格 ({x},{y}) 看名稱'):
                        continue
                    if not bag._wait(bag.popup_open, EQUIP_POPUP_WAIT_S):
                        continue
                    nm = bag.popup_name(ITEM)
                    bag.close_popup()
                    if bag.name_match(nm, ITEM):
                        out['worn'] = True
                        break
        return 0, out

    def read_coin(self):
        """面板開著時讀頂端石幣；讀不到 None"""
        return parse_coin(''.join(uikit.ocr(COIN_BOX, '-Zooms', '2,3')))

    # -- 前置 --
    def stop_follow(self) -> bool:
        import grind
        return grind.stop_follow('買溫蒂妮金幣（要離開練功點、解散隊伍）')

    def encounter_off(self) -> None:
        import heal
        heal.set_encounter(False)
        heal.gui('seq', f'waitpix 30000 {heal.SIG_NO_BATTLE} 40')

    def pos(self):
        import walk
        return walk.pos()

    def to_town(self) -> bool:
        """城鎮傳送薩姆吉爾（競技場裡也能開）；第一下常被剛換地圖的畫面吃掉 → heal.teleport 內建重試"""
        import heal
        try:
            heal.teleport(heal.TAB_TOWN, heal.SAMUGIL, heal.VILLAGE, '薩姆吉爾', want_xy=heal.VILLAGE_START)
        except RuntimeError as e:
            print(f'{SRC}：{e}', file=sys.stderr)
            return False
        return True

    def disband(self) -> int:
        import team
        rc = team.disband()
        if rc == 40:                                           # 切換面板剛換地圖後第一下常打不開（2026-10-15 實機）→ 等一下再來一次
            uikit.sleep(2.0)
            rc = team.disband()
        return rc

    # -- 走 / 對話 --
    def walk_to(self, map_id, x, y) -> bool:
        import walk
        try:
            walk.walk_to(map_id, x, y)
        except RuntimeError as e:
            print(f'{SRC}：走到 {map_id}:{x},{y} 失敗：{e}', file=sys.stderr)
            return False
        return True

    def talk(self, npc, at, then='') -> bool:
        """點 NPC → 輪詢對話框 → then（例 'click 948 461'）；剛走到的第 1 下常被吃掉，最多 3 次。回對話框有沒有出現"""
        import walk
        for _ in range(3):
            if walk.talk_npc(npc, at, then=then):
                return True
        return False

    def wait_map(self, map_id, tries=10) -> bool:
        import walk
        p = walk.wait_pos(tries, map_id, 0.6)
        return bool(p and p[0] == map_id)

    # -- 商店 --
    def shop_open(self) -> bool:
        import shopbuy
        return shopbuy._shop_open()

    def shop_select_read(self) -> tuple:
        """點商品卡 → 等 0.5 秒 → 讀標題 / 技能 / 總價 OCR → (title, skill, price_text)"""
        uikit.gui('seq', f'click {ITEM_XY[0]} {ITEM_XY[1]}; wait 500', note=f'buywendy 選商品 {ITEM}')
        title = ''.join(uikit.ocr(TITLE_BOX, '-Zooms', '2,3'))
        skill = ''.join(uikit.ocr(SKILL_BOX, '-Zooms', '2,3'))
        price = ''.join(uikit.ocr(PRICE_BOX, '-Zooms', '2,3'))
        return title, skill, price

    def shop_buy(self) -> None:
        uikit.gui('seq', f'click {BUY_BTN[0]} {BUY_BTN[1]}; wait 700; click {CONFIRM_BTN[0]} {CONFIRM_BTN[1]}; wait 900',
                  note=f'buywendy 買 {ITEM} ×1（{PRICE} 石幣）')

    def shop_close(self) -> None:
        """ESC 關便利店；買完可能還疊著提示窗 → 面板還在就再 ESC（最多 3 次）"""
        for _ in range(3):
            uikit.gui('key', '{ESC}')
            uikit.sleep(0.4)
            if not self.shop_open():
                return

    # -- 穿 / 首次動作 --
    def wear(self) -> int:
        import bag
        return bag.wear_item(LEADER, ITEM)

    def set_first(self, dry_run=False) -> tuple:
        """外掛面板選隊長 → 人物首次動作 = 風的精靈 + 打勾。回 (rc, 狀態 dict, 訊息)"""
        import ass
        rc, st, msg, _ = ass._many({LEADER: None}, lambda role: _visit_first(role, dry_run))
        return rc, st.get(LEADER) or {}, msg

    # -- 收尾 --
    def team_form(self) -> int:
        import team
        return team.form(LEADER, len(ALL_ROLES))

    def grind_go(self) -> int:
        import grind
        return grind.go()


# ---- 外掛：隊長人物首次動作（ass._many 的 visit）----
def _visit_first(role: str, dry_run: bool = False):
    """面板開著、角色已選好。人物首次動作值含「風的精靈」→ 不動；不是 → 開下拉、OCR 找唯一「風的精靈」選項、點、讀回；
    再看勾選框（像素），沒勾就點、讀回。回 (退出碼, 狀態 dict, 訊息, 改了哪些)。dry_run 只讀。
    ass.py 的既有函式只借用（常數 / OCR / 像素讀取），不改它們。"""
    import ass
    todo = []
    if not ass.pet_on_top():
        return ass.EXIT_NOT_TOP, None, f'{role}：右半面板不在頂端（讀不到「戰寵動作」標題）；不讀 / 不點人物首次動作', todo
    rf = ass.read_role_first(ocr=True)
    if rf is None:
        return ass.EXIT_PANEL_LOST, None, f'{role} 讀不到人物首次動作勾選框', todo
    st = {'人物首次動作': rf['first'], '人物首次勾選': rf['first_on']}
    if SKILL not in (rf['first'] or ''):
        if dry_run:
            st['wrong'] = ['人物首次動作']
        else:
            x, y = ROLE_FIRST_DD
            if not ass.panel_open() or ass.selected_role() != role:
                return ass.EXIT_PANEL_LOST, st, f'{role}：開下拉前面板已不在 / 角色不對 → 不點', todo
            ass.gui('seq', f'click {x} {y}; wait 500', note=f'buywendy {role} 人物首次動作 開下拉')
            lines = ass._ocr_lines((ass.PET_LIST_X, y + ass.PET_LIST_DY, ass.PET_LIST_W, ass.PET_LIST_H), '-Zooms', '2,3,4')
            pos = option_pos(lines, SKILL)
            if pos is None:
                ass.gui('seq', f'click {x} {y}; wait 500', note=f'buywendy {role} 收下拉（沒有「{SKILL}」）')
                return ass.EXIT_NO_OPTION, st, f'{role}：首次動作下拉裡找不到唯一的「{SKILL}」（金幣沒穿上？OCR 讀不到？）；不亂點', todo
            if not ass.panel_open():
                return ass.EXIT_PANEL_LOST, st, f'{role}：開下拉後面板消失', todo
            ass.gui('seq', f'click {ass.PET_OPT_X} {pos[1]}; wait 500', note=f'buywendy {role} 人物首次動作 → {SKILL}')
            todo.append('人物首次動作')
            for w in (ass.CONFIRM_WAIT, ass.CONFIRM_WAIT2):
                ass.sleep(w)
                if not ass.panel_open():
                    return ass.EXIT_PANEL_LOST, st, f'{role}：選 {SKILL} 後面板消失', todo
                now = ass.read_role_first(ocr=True)
                if now and SKILL in (now['first'] or ''):
                    st['人物首次動作'], rf = now['first'], now
                    ass.log(f'ass：{role} 人物首次動作 → {now["first"]}（已確認）')
                    break
            else:
                return ass.EXIT_CONFIRM, st, f'{role}：選了 {SKILL} 但讀回仍是「{now["first"] if now else "?"}」（不補點；請 shot 確認）', todo
    if not rf['first_on']:
        if dry_run:
            st.setdefault('wrong', []).append('人物首次勾選')
        else:
            if not ass.panel_open() or ass.selected_role() != role or not ass.pet_on_top():
                return ass.EXIT_PANEL_LOST, st, f'{role}：點勾選前面板已不在 / 角色不對 / 被捲動 → 不點', todo
            ass.gui('seq', f'click {ass.ROLE_FIRST_CHK[0]} {ass.ROLE_FIRST_CHK[1]}; wait 300', note=f'buywendy {role} 人物首次動作勾選 → 勾')
            todo.append('人物首次勾選')
            for w in (ass.CONFIRM_WAIT, ass.CONFIRM_WAIT2):
                ass.sleep(w)
                if not ass.panel_open():
                    return ass.EXIT_PANEL_LOST, st, f'{role}：點勾選後面板消失', todo
                now = ass.read_role_first(ocr=False)
                if now and now['first_on']:
                    st['人物首次勾選'] = True
                    ass.log(f'ass：{role} 人物首次動作勾選 → 勾（已確認）')
                    break
            else:
                return ass.EXIT_CONFIRM, st, f'{role}：人物首次動作勾選點了沒變（不補點）', todo
    return ass.EXIT_OK, st, '', todo


# ---- 流程 ----
LAST: dict = {}


class Run:
    def __init__(self, T, o):
        self.T, self.o, self.info = T, o, {}

    def stop(self, rc, msg, **kw):
        self.info.update(kw)
        event(f'停手（{rc}）：{msg}')
        return rc

    def fail(self, tool_rc, my_rc, msg, **kw):
        """工具回 8 / 9 / 10 → 原碼；其他 → 本檔對應碼"""
        return self.stop(tool_rc if tool_rc in PASS else my_rc, msg, **kw)

    def check(self):
        rc = self.T.preflight()
        if rc:
            return self.stop(rc, 'preflight 失敗')
        rc = self.T.char_ensure(LEADER)
        if rc:
            return self.fail(rc, EXIT_PRE, f'當前角色切不到隊長 {LEADER}（char rc {rc}）', char_rc=rc)
        rc, st = self.T.inspect()
        if rc:
            return self.fail(rc, EXIT_BAG, f'讀背包 / 裝備失敗（bag rc {rc}）', bag_rc=rc)
        self.st = st
        self.info.update(coin_before=st['coin'], in_bag=st['bag'] is not None, worn=st['worn'])
        event(f'{LEADER}：{ITEM} {"已穿上" if st["worn"] else ("在背包第 %d 格" % (st["bag"] + 1) if st["bag"] is not None else "沒有")}；石幣 {st["coin"]}')
        return 0

    def need_buy(self):
        return not self.st['worn'] and self.st['bag'] is None

    # -- 買 --
    def buy(self):
        T = self.T
        self.info['went_out'] = True
        if not T.stop_follow():
            return self.stop(EXIT_TOWN, 'follow 停不掉（60 秒內沒結束）')
        T.encounter_off()
        p = T.pos()
        if not p or p[0] not in (VILLAGE, ARENA):
            if not T.to_town():
                return self.stop(EXIT_TOWN, '傳送薩姆吉爾失敗')
            T.sleep(1.0)
        rc = T.disband()
        if rc:
            return self.fail(rc, EXIT_TOWN, f'解散隊伍失敗（team rc {rc}）', team_rc=rc)
        p = T.pos()
        if not p or p[0] != ARENA:
            rc = self.enter_arena()
            if rc:
                return rc
        if not T.walk_to(ARENA, *SHOP_STAND):
            return self.stop(EXIT_ARENA, f'走不到競技場 {SHOP_STAND}')
        if not T.talk(SHOP_NPC, SHOP_STAND, then=f'click {SHOP_BTN[0]} {SHOP_BTN[1]}'):
            return self.stop(EXIT_ARENA, '點不開鬥技場的道具屋對話框（3 次）')
        return self.shop()

    def enter_arena(self):
        T = self.T
        p = T.pos()
        if not p or p[0] != VILLAGE:
            if not T.to_town():
                return self.stop(EXIT_TOWN, '傳送薩姆吉爾失敗')
        if not T.walk_to(VILLAGE, *GUIDE_STAND):
            return self.stop(EXIT_ARENA, f'走不到薩姆吉爾 {GUIDE_STAND}')
        if not T.talk(GUIDE, GUIDE_STAND, then=f'click {ENTER_BTN[0]} {ENTER_BTN[1]}'):
            return self.stop(EXIT_ARENA, '點不開鬥技場嚮導對話框（3 次）')
        if not T.wait_map(ARENA):
            return self.stop(EXIT_ARENA, '按了「進入競技場」但沒到 130')
        return 0

    def shop(self):
        """商店內壓在約 6 秒：開 → 選 → 讀 → 買 → 關（便利店面板不在 screen_sigs，開太久 watch 會寫全視窗停手旗標）"""
        T = self.T
        for _ in range(6):
            if T.shop_open():
                break
            T.sleep(0.5)
        else:
            return self.stop(EXIT_SHOP, '便利店面板沒開')
        title, skill, price = T.shop_select_read()
        self.info.update(shop_title=title, shop_skill=skill, shop_price=price)
        if not title_ok(title):
            T.shop_close()
            return self.stop(EXIT_SHOP, f'便利店標題 OCR 是 {title!r}，不是「{ITEM}」（不買、已關店）')
        if str(PRICE) not in re.sub(r'[\s,]', '', price):
            T.shop_close()
            return self.stop(EXIT_SHOP, f'便利店總價 OCR 是 {price!r}，不是 {PRICE}（不買、已關店）')
        T.shop_buy()
        T.shop_close()
        return 0

    def verify_bought(self):
        """買完開背包驗：背包有道具 + 石幣少 500（讀得到才驗）"""
        rc, st = self.T.inspect()
        if rc:
            return self.fail(rc, EXIT_BAG, f'買完讀背包失敗（bag rc {rc}）', bag_rc=rc)
        ok = coin_delta_ok(self.st['coin'], st['coin'])
        self.info.update(coin_after=st['coin'], coin_delta_ok=ok)
        got = st['bag'] is not None or st['worn']
        if ok is False:
            return self.stop(EXIT_SHOP, f'石幣 {self.st["coin"]} → {st["coin"]}，少的不是 {PRICE}（道具{"有" if got else "沒"}進背包）；不再買，請人看', )
        if not got:
            return self.stop(EXIT_SHOP, f'按了購買但背包沒有「{ITEM}」（石幣 {self.st["coin"]} → {st["coin"]}）；不重買，請人看畫面')
        event(f'買到了：石幣 {self.st["coin"]} → {st["coin"]}' + ('' if ok else '（石幣沒讀到，以背包有道具為準）'))
        self.st = st
        return 0

    # -- 穿 / 首次動作 / 回去 --
    def wear(self):
        rc = self.T.wear()
        if rc:
            return self.fail(rc, EXIT_WEAR, f'穿戴失敗（bag rc {rc}）', bag_rc=rc)
        rc, st = self.T.inspect()
        if rc:
            return self.fail(rc, EXIT_BAG, f'穿完讀裝備失敗（bag rc {rc}）', bag_rc=rc)
        if not st['worn']:
            return self.stop(EXIT_WEAR, f'穿戴按了，但三個裝備格都看不到「{ITEM}」（背包{"還有" if st["bag"] is not None else "沒有"}）')
        event('已穿上')
        return 0

    def first(self):
        rc, st, msg = self.T.set_first(self.o.get('dry_run', False))
        self.info.update(first=st)
        if rc:
            return self.fail(rc, EXIT_FIRST, msg or f'外掛首次動作失敗（ass rc {rc}）', ass_rc=rc)
        event(f'人物首次動作 {st.get("人物首次動作")}、勾選 {st.get("人物首次勾選")}')
        return 0

    def back(self):
        T = self.T
        p = T.pos()
        if not p or p[0] != VILLAGE:
            if not T.to_town():
                return self.stop(EXIT_BACK, '傳送薩姆吉爾失敗')
        if self.o.get('form', True):
            rc = T.team_form()
            if rc:
                return self.fail(rc, EXIT_BACK, f'組隊失敗（team rc {rc}）', team_rc=rc)
        if self.o.get('grind', True):
            rc = T.grind_go()
            if rc:
                return self.fail(rc, EXIT_GRIND, f'去練功失敗（grind rc {rc}）', grind_rc=rc)
        return 0


def plan_lines(st: dict | None) -> list:
    if st is None:
        return [f'check：背包 / 裝備格找「{ITEM}」→ 已穿 = 只做 first；在背包 = 從 wear；沒有 = 要買',
                f'buy（--confirm-buy）：停 follow → 關遇敵 → 傳薩姆吉爾 → 解散 → 嚮導 → 競技場 → 道具屋 → 便利店買 1 個（{PRICE} 石幣）',
                f'wear：穿 {ITEM}', f'first：外掛 {LEADER} 人物首次動作 = {SKILL}Lv.5 + 勾選', 'back：傳薩姆吉爾 → team.form → grind.go']
    out = []
    if st['worn']:
        out.append(f'（已穿 {ITEM}）buy / wear 跳過')
    elif st['bag'] is not None:
        out.append(f'（{ITEM} 在背包第 {st["bag"] + 1} 格）buy 跳過 → wear')
    else:
        out.append(f'要買 {ITEM}（{PRICE} 石幣；石幣 {st["coin"]}）→ wear')
    out.append(f'first：外掛 {LEADER} 人物首次動作 = {SKILL}Lv.5 + 勾選（已是就不點）')
    return out


def run(confirm_buy: bool = False, dry_run: bool = False, form: bool = True, grind: bool = True, tools=None) -> int:
    LAST.clear()
    if not ALL_ROLES:
        print(f'{SRC}：PSA_CLIENT={clients.name()} 沒有名單（clients.ROSTERS）', file=sys.stderr)
        return EXIT_ARGS
    R = Run(tools or Tools(), dict(confirm_buy=confirm_buy, dry_run=dry_run, form=form, grind=grind))
    event(f'開始：{LEADER}（{clients.name()}）confirm_buy={confirm_buy} dry_run={dry_run} form={form} grind={grind}')
    rc = R.check()
    if not rc:
        if dry_run:
            for ln in plan_lines(R.st):
                print('  ' + ln)
            rc = R.first() if R.st['worn'] else 0          # 已穿才讀首次動作（沒穿下拉沒有選項）；dry_run 只讀不點
        else:
            rc = _flow(R, confirm_buy)
    LAST.update(R.info, ok=rc == 0, rc=rc)
    if not rc:
        event('完成')
    return rc


def _flow(R: Run, confirm_buy: bool) -> int:
    if R.need_buy():
        if not confirm_buy:
            return R.stop(EXIT_PRE, f'{ITEM} 要花 {PRICE} 石幣，沒給 --confirm-buy → 不買')
        rc = R.buy()
        if not rc:
            rc = R.verify_bought()
        if rc:
            return rc
    if not R.st['worn']:
        rc = R.wear()
        if rc:
            return rc
    rc = R.first()
    if rc:
        return rc
    p = R.T.pos()
    if R.info.get('went_out') or (p and p[0] in (VILLAGE, ARENA)):
        return R.back()                           # 這次出過門（買）或人還在村 / 競技場（上次中斷）→ 回村、組隊、練功
    return 0


def main(argv=None) -> int:
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('cmd', choices=['plan', 'run'])
    ap.add_argument('--confirm-buy', action='store_true', help=f'花 {PRICE} 石幣買 {ITEM}（沒給 = 不買）')
    ap.add_argument('--no-form', action='store_true', help='回村後不 team.form')
    ap.add_argument('--no-grind', action='store_true', help='組隊後不去練功')
    ap.add_argument('--dry-run', action='store_true', help='同 plan：只讀背包 / 裝備與外掛，不買不穿不點')
    a = ap.parse_args(argv)
    if not ALL_ROLES:
        print(f'{SRC}：PSA_CLIENT={clients.name()} 沒有名單', file=sys.stderr)
        return EXIT_ARGS
    dry = a.dry_run or a.cmd == 'plan'
    import winenv
    winenv.enable_server()
    rc = run(a.confirm_buy, dry, not a.no_form, not a.no_grind)
    print(json.dumps(dict(LAST, rc=rc), ensure_ascii=False, default=str))
    return rc


if __name__ == '__main__':
    sys.exit(main())
