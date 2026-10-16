#!/usr/bin/env python3
"""轉生任務（漆黑洞窟 N 轉）的獨立小步驟：接任務、轉生獎勵寵偵測 / 丟棄。rebirth.py 只負責串階段，這裡每個函式 / 子指令都能單獨呼叫。只用標準函式庫。

用法（專案根目錄；WSL / Windows 原生相同）：
  uv run --no-project python tools/gui/rebirth_steps.py accept --trans 3            # 接「漆黑洞窟(三轉)」（任務詳情 → 傳送到瑪麗娜絲村長 → 選單頁翻頁 → 接受 → 驗證進行中）
  uv run --no-project python tools/gui/rebirth_steps.py gate --trans 4                # 點追蹤卡當等級檢查（有傳送 = 5 人達標；跳未達條件視窗 → 關掉，印 JSON 結果）
  uv run --no-project python tools/gui/rebirth_steps.py snapshot                    # 唯讀：讀 5 人寵物欄存成轉生前快照（tools/.cache/rebirth_pets_before.json）
  uv run --no-project python tools/gui/rebirth_steps.py drop-reward --trans 3 [--dry-run]   # 轉生後丟 5 人的獎勵寵（見下）
  可 import：accept_task(n, T=None)、level_gate(n, T=None)、judge_gate_text(text)、reward_name(n)、find_new_lv1(before, after)、drop_rewards(n, before, T=None, dry_run=False)
  （2026-10-16 起 rebirth.py cleanup 不再用本檔丟獎勵寵：改 petdrop.drop_first_slot 固定動作，見 rebirth.py；本檔 drop_rewards 仍給 questrun 等舊路徑）

接任務（accept_task）：畫面已開著對話框（--from accept 時 preflight 留下的村長選單）→ 是「漆黑洞窟 / 再見」選單就直接接（翻頁 → 接受 → 驗進行中），
  別的對話框 → 不點、97。否則先看任務追蹤欄——有標題精確等於「漆黑洞窟(N轉)」的卡片（titlematch 圖樣板；沒樣板 / 不確定不用 OCR）→ quest.track_task 點卡片巡路到村長 →
  questdetail._after_transfer（選單頁翻頁 → 接受 → 驗進行中）；沒有卡、或點卡後 20 秒沒對話框才 fallback：questdetail.accept(「漆黑洞窟(N轉)」, skip_ok=True)。任務詳情列表 / 中間標題用樣板精確比對（(三轉) / (五轉) 只差一字也分得開，
  標題對不上就不傳送、不亂點）；傳送到村長後對話框第 1 頁是選單（左鈕「漆黑洞窟」）→ 先點左鈕翻頁（questdetail 2d0e38d 的選單頁邏輯）→ 第 2 頁「接受」→
  重開詳情驗證「進行中」。已進行中 = 跳過（回 0）；已完成 = 失敗（轉生 / 封印書後任務會重置，已完成表示轉數不對）。
轉生獎勵寵：一轉 = 烏力斯坦、二轉 = 奇娜（REWARD，實機）；三轉起沒有對照表 → 轉生前後寵物欄 diff：
  每人要「剛好 1 隻新出現的 Lv1 寵物」、名字讀得出且不是騎寵 / 戰寵（狀態等待）、不在第 1 格，名字 + Lv1 都驗過才丟（petdrop --slot --max-level 1）；
  任何不確定（沒有快照、0 / 多隻候選、名字讀不出、等級讀不出）→ 一律不丟、回 98，不碰騎寵 / 戰寵。
退出碼：0 成功；97 接任務失敗（info.accept_rc = questdetail 退出碼，120～129 見 questdetail.py）；98 獎勵寵無法確認 / 丟棄失敗（info.why）；
  9 / 10 驗證視窗 / 斷線 透傳。
"""
import argparse
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import clients  # noqa: E402
import uikit  # noqa: E402

SRC = 'rebirth_steps'
EXIT_ACCEPT, EXIT_REWARD = 97, 98
CN = {1: '一', 2: '二', 3: '三', 4: '四', 5: '五'}
ALL_ROLES = clients.roster()        # 這個視窗（PSA_CLIENT）的名單：主視窗 DKBO、DKBO2～5
REWARD = {1: '烏力斯坦', 2: '奇娜'}                  # 轉生獎勵寵（實機：一轉烏力斯坦、二轉奇娜；其餘轉數靠 diff）
SNAPSHOT = uikit.CACHE / 'rebirth_pets_before.json'
LAST: dict = {}


def task_name(n: int) -> str:
    return f'漆黑洞窟({CN[n]}轉)'


def reward_name(n: int):
    return REWARD.get(n)


# ---- 接任務 ----
def accept_task(n: int, T=None) -> int:
    """接漆黑洞窟(N轉)。T 可換（測試）：T.accept(title) → 退出碼、T.accept_state() → 'doing' / 'done' / 'accepted' / None"""
    LAST.clear()
    title = task_name(n)
    T = T or _AcceptTools()
    rc = None
    # 對話框已開著（2026-10-15 四轉：preflight 點卡被傳到村長選單、84 停下後 --from accept 被對話框擋住 → 97）：
    # 是村長選單「漆黑洞窟 / 再見」→ 直接在這個對話框接（翻頁 → 接受 → 驗進行中）；是別的對話框 → 不點、失敗
    try:
        btns = T.open_dialog_buttons()
    except AttributeError:                                           # 測試用假 T 沒實作 → 當沒有對話框
        btns = None
    if btns is not None:
        if not is_menu_dialog(btns, title):
            LAST.update(via='dialog', accept_rc=None, buttons=btns)
            return uikit.fail(SRC, EXIT_ACCEPT, f'畫面停在別的 NPC 對話框（按鈕 {btns}），不是瑪麗娜絲村長選單「漆黑洞窟 / 再見」→ 不點，請人工關掉再跑')
        print(f'{SRC}：對話框開著且是村長選單「漆黑洞窟 / 再見」→ 直接接「{title}」', flush=True)
        LAST['via'] = 'dialog'
        rc = T.accept_open_dialog(title)
    # 先看任務追蹤欄（使用者規定）：有標題「精確」相符的卡片 → 點卡片自動巡路到村長 → 選單翻頁 → 接受 → 驗進行中；
    # 沒有卡 / 比對不確定（沒樣板、分數不夠）→ 才走任務詳情 fallback。卡片路徑只在「點了卡但 20 秒沒出現對話框」時退回 fallback（沒按過任何鈕）
    try:
        card = False if rc is not None else T.card_visible(title)
    except AttributeError:                                           # 測試用假 T 沒實作 → 當沒有卡
        card = False
    LAST.setdefault('via', 'detail')
    if rc is not None:
        pass
    elif card:
        LAST['via'] = 'tracker'
        print(f'{SRC}：追蹤欄有「{title}」卡片 → 點卡片巡路到村長接取', flush=True)
        rc = T.accept_card(title)
        if rc == _NO_DIALOG:
            print(f'{SRC}：點卡片後沒出現對話框 → 退回任務詳情接取', flush=True)
            LAST['via'] = 'detail'
            rc = None
    else:
        print(f'{SRC}：追蹤欄沒有（或比對不確定）「{title}」→ 任務詳情接取', flush=True)
    if rc is None:
        rc = T.accept(title)
    st = T.accept_state()
    LAST.update(accept_rc=rc, state=st)
    if rc in (uikit.EXIT_UNKNOWN_SCREEN, uikit.EXIT_HALT):
        return rc
    if rc:
        return uikit.fail(SRC, EXIT_ACCEPT, f'接「{title}」失敗（questdetail rc={rc}）')
    if st == 'done':
        return uikit.fail(SRC, EXIT_ACCEPT, f'「{title}」狀態是已完成，不是待接取 / 進行中（轉數不對？轉生後任務會重置），不接')
    print(f'{SRC}：「{title}」' + ('已在進行中，跳過' if st == 'doing' else '已接取'), flush=True)
    return 0


_NO_DIALOG = 125                                                     # = questdetail.EXIT_NO_DIALOG


class _AcceptTools:
    def open_dialog_buttons(self):
        """畫面上已有 NPC 對話框 → 按鈕文字 list（含不可逆關鍵字 / 內文讀不到 → []，不會被當成選單）；沒有對話框 → None"""
        if uikit.screen().get('state') != 'dialog':
            return None
        import quest
        g = quest.check_dialog_irreversible()
        return [] if g.get('blocked') else list(g.get('buttons') or [])

    def accept_open_dialog(self, title):
        import questdetail
        return questdetail._after_transfer(SRC, title, 2, True)

    def card_visible(self, title):
        """追蹤欄目前這頁有標題精確等於 title 的卡片（titlematch 圖樣板，(三轉) / (五轉) 分得開；沒樣板 / 不確定 = False，不用 OCR 模糊比對）"""
        import quest
        import titlematch
        if uikit.preflight(SRC):
            return False
        quest.ensure_task_tab()
        return titlematch.has_templates(title) and titlematch.find(title) is not None

    def accept_card(self, title):
        """點追蹤卡（quest.track_task，標題相符才點）→ 等村長對話框 → questdetail 既有的對話處理（選單頁翻頁 → 接受 → 重開詳情驗進行中）"""
        import quest
        import questdetail
        if quest.track_task(title) is not True:
            return _NO_DIALOG
        return questdetail._after_transfer(SRC, title, 2, True)

    def accept(self, title):
        import questdetail
        return questdetail.accept(title, skip_ok=True)

    def accept_state(self):
        import questdetail
        return questdetail.LAST.get('state')


def is_menu_dialog(buttons, title: str) -> bool:
    """純函式：對話框按鈕是不是瑪麗娜絲村長的選單頁（左鈕 = 任務名去括號「漆黑洞窟」、後面有「再見」；2026-10-12 / 10-15 實機）"""
    import questdetail
    b = [str(x or '') for x in (buttons or [])]
    return len(b) >= 2 and questdetail.menu_button_matches(b[0], title) and any('再見' in x for x in b[1:])


# ---- 等級門檻：點追蹤卡 = 等級檢查（2026-10-14 使用者說法）----
# 任務已接時追蹤欄「漆黑洞窟(N轉) / 進入漆黑」卡片一點就自動傳送到吉魯島（300）→ 守門人 → 漆黑 1F；
# 隊伍裡有人未達門檻 → 遊戲跳視窗擋住（知識庫字串 text 71266「{0}未達到{1}轉{2}級禁止傳送」、2004「條件不足,無法傳送」、「等級不足」），不傳送。
# 所以「有傳送 = 全隊達標」，比 bag.levels 逐人開面板讀等級快又準。
GATE_MAPS = (300,) + tuple(range(32001, 32022))        # 吉魯島 / 漆黑 1F～21F：在這裡 = 已過傳送門檻
GATE_WORDS = ('未達到', '禁止傳送', '條件不足', '等級不足')
GATE_RE = re.compile(r'([A-Za-z0-9]+)?\s*未\s*達\s*到?\s*(\d+)\s*轉\s*(\d+)\s*級')
GATE_WAIT_S = 20.0               # 點卡後等傳送 / 視窗的上限（實測整段到 1F 約 15 秒，2026-10-12 notes 2004 段）
GATE_UNKNOWN_N = 3               # 不認得的畫面（非轉場）連續這麼多次才讀字判斷
# 截圖座標（1440×830）。提示視窗：✕ 946,208、確定 714,557（questdetail.NOTICE_*），內文在兩者之間（未實機量測，估計值）
NOTICE_TEXT_BOX = (480, 235, 465, 300)
CENTER_TEXT_BOX = (300, 150, 840, 500)    # 不認得的視窗：讀畫面中央一大塊


def past_gate(pos) -> bool:
    """純函式：目前位置已在吉魯島 / 漆黑洞窟（已過傳送門檻）"""
    return bool(pos) and pos[0] in GATE_MAPS


def judge_gate_text(text: str):
    """純函式：視窗 / 聊天文字 → 未達條件 {'who', 'trans', 'level', 'text'}（who 讀不到 = None）；不含任何關鍵字 → None"""
    t = re.sub(r'\s+', '', text or '')
    if not any(w in t for w in GATE_WORDS):
        return None
    m = GATE_RE.search(t)
    who = trans = lv = None
    if m:
        trans, lv = int(m[2]), int(m[3])
        if m[1]:
            try:
                import charname
                import charstate
                who = charstate.norm_char(m[1], ALL_ROLES) or charname.canon(m[1]).replace('DKB0', 'DKBO')   # 名單內 → 真名；名單外照舊正規化
            except Exception:
                who = m[1]
    return {'who': who, 'trans': trans, 'level': lv, 'text': t[:80]}


def level_gate(n: int, T=None, wait_s: float = GATE_WAIT_S) -> dict:
    """點追蹤卡「漆黑洞窟(N轉)」當等級檢查（呼叫前：原地遇敵已關、DKBO 當前、5 人隊伍）。回 dict，kind：
    already  點之前就在吉魯島 / 漆黑（已過門檻，沒點）
    teleport 點卡後地圖變成吉魯島 / 漆黑 → 全隊達標（遊戲接著自動巡路往守門人）
    blocked  跳「未達條件」視窗（提示視窗 → 已點 ✕ 關掉，closed=True；別種視窗讀到關鍵字 → closed=False 沒點）或聊天區有同樣訊息；who = 誰不夠
    nocard   追蹤欄掃完沒有這張卡（標題對不上絕不點；任務多半沒接）
    unknown  跳出視窗但讀不出「未達到 / 禁止傳送 / 條件不足 / 等級不足」→ 可能是驗證視窗，什麼都沒點（呼叫端回 9）
    dialog   點卡後出現 NPC 對話框（沒傳送）且不是瑪麗娜絲村長的選單頁「漆黑洞窟 / 再見」→ 沒按
             （2026-10-15 四轉實跑：任務其實還沒接，點卡被傳到村長選單 → 舊版直接 84。現在認得選單頁就 accept_dialog
               〔questdetail._after_transfer：左鈕「漆黑洞窟」翻頁 → 「接受」→ 重開詳情驗進行中〕→ 再點卡做門檻，結果帶 accepted=True；
               接取失敗 → accept_fail（rc = questdetail 退出碼）；接完再點卡又是對話框 → dialog）
    moved    換到別張地圖（不是吉魯島 / 漆黑）
    screen   掃追蹤欄途中畫面不再是主畫面（戰鬥等），沒點
    timeout  wait_s 秒內沒傳送、沒視窗、聊天區也沒有未達訊息"""
    title = task_name(n)
    T = T or _GateTools()
    pos0 = T.pos()
    if past_gate(pos0):
        return {'kind': 'already', 'pos': pos0}
    hit = T.click_card(title)
    if hit is None:
        return {'kind': 'screen', 'pos': pos0}
    if not hit:
        return {'kind': 'nocard', 'pos': pos0}
    t_end = T.clock() + wait_s
    unk = 0
    pos = pos0
    accepted = False
    while T.clock() < t_end:
        T.sleep(1.0)
        if T.notice():                                              # 米色「提示」視窗（questdetail 同一個特徵）
            text = T.notice_text()
            j = judge_gate_text(text)
            if not j:
                return {'kind': 'unknown', 'text': (text or '')[:80], 'pos': pos}
            closed = T.dismiss()
            return dict(j, kind='blocked', via='notice', closed=closed, pos=pos)
        p = T.pos()
        if p:
            pos = p
            if past_gate(p):
                return {'kind': 'teleport', 'pos': p, 'accepted': accepted}
            if pos0 and p[0] != pos0[0]:
                return {'kind': 'moved', 'pos': p}
        st = T.state()
        if st == 'dialog':
            if accepted or not is_menu_dialog(T.dialog_buttons(), title):
                return {'kind': 'dialog', 'pos': pos, 'accepted': accepted}
            print(f'{SRC}：點卡後是瑪麗娜絲村長選單「漆黑洞窟 / 再見」（任務還沒接）→ 接任務後再點卡做門檻', flush=True)
            arc = T.accept_dialog(title)
            if arc:
                return {'kind': 'accept_fail', 'rc': arc, 'pos': pos, 'accepted': False}
            accepted = True
            pos0 = T.pos() or pos                                   # 人現在在村子：之後換圖要跟這裡比
            hit = T.click_card(title)
            if not hit:
                return {'kind': 'screen' if hit is None else 'nocard', 'pos': pos0, 'accepted': True}
            t_end, unk = T.clock() + wait_s, 0
            continue
        if st in ('unknown', 'error') and not T.transition():
            unk += 1
            if unk >= GATE_UNKNOWN_N:
                text = T.center_text()
                j = judge_gate_text(text)
                if not j:
                    return {'kind': 'unknown', 'text': (text or '')[:80], 'pos': pos}
                return dict(j, kind='blocked', via='window', closed=False, pos=pos)
        else:
            unk = 0
    j = judge_gate_text(T.chat_text())                              # 沒視窗：系統訊息可能只出在聊天區（follow.py 練級點傳送被擋就是這樣）
    if j:
        return dict(j, kind='blocked', via='chat', closed=True, pos=pos)
    return {'kind': 'timeout', 'pos': pos}


class _GateTools:
    def clock(self):
        import time
        return time.monotonic()

    def sleep(self, s):
        uikit.sleep(s)

    def pos(self):
        import quest
        return quest.read_pos()

    def click_card(self, title):
        """quest.track_task：標題相符才點（樣板 / OCR 都對不上 → False，不點）"""
        import quest
        if uikit.preflight(SRC):
            return None
        return quest.track_task(title)

    def notice(self):
        import questdetail
        return questdetail.notice_open()

    def dialog_buttons(self):
        """目前對話框按鈕文字（quest.check_dialog_irreversible；含不可逆關鍵字 / 內文讀不到 → [] = 不當選單）"""
        import quest
        g = quest.check_dialog_irreversible()
        return [] if g.get('blocked') else list(g.get('buttons') or [])

    def accept_dialog(self, title):
        """對話框已開在村長選單頁：questdetail._after_transfer（左鈕翻頁 → 接受 → 重開詳情驗進行中）→ questdetail 退出碼"""
        import questdetail
        return questdetail._after_transfer(SRC, title, 2, True)

    def notice_text(self):
        return ''.join(uikit.ocr(NOTICE_TEXT_BOX, '-Zooms', '2,3'))

    def dismiss(self):
        import questdetail
        uikit.snap('rebirth-gate-blocked')
        return questdetail.dismiss_notice()

    def state(self):
        return uikit.screen().get('state')

    def transition(self):
        return uikit.transition_now()

    def center_text(self):
        uikit.snap('rebirth-gate-unknown')
        return ''.join(uikit.ocr(CENTER_TEXT_BOX, '-Zooms', '2,3'))

    def chat_text(self):
        import follow
        return ''.join(uikit.ocr(follow.CHAT_BOX, '-Zooms', '2,3', '-Dark', 0))


# ---- 轉生獎勵寵 ----
def snapshot_pets(slots_by_role: dict) -> dict:
    """pet.list_role 的結果 → 精簡快照 {role: [{slot, empty, name, level, state}]}（可存 json）"""
    out = {}
    for r, sl in (slots_by_role or {}).items():
        out[r] = [{'slot': s.get('slot'), 'empty': bool(s.get('empty')), 'name': s.get('name'), 'level': s.get('level'), 'state': s.get('state'),
                   'unnamed': s.get('unnamed'), 'mountlike': bool(s.get('mountlike'))} for s in sl or []]
    return out


def find_new_lv1(before: list, after: list) -> tuple:
    """單人：轉生前 / 後寵物欄（snapshot 格式）→ (候選 [slot dict], 理由)。
    候選 = 轉生前是空格（或名字不同）、轉生後有寵物、Lv1、名字讀得出、不是騎寵 / 戰寵（state 不是 騎乘 / 出戰）、不在第 1 格。
    只有「恰好 1 隻」才算確定；其他情況候選照回，理由說明不確定在哪（純函式）"""
    bef = {s['slot']: s for s in before or []}
    cand, why = [], ''
    for s in after or []:
        if s.get('empty'):
            continue
        b = bef.get(s['slot'])
        if b and not b.get('empty') and b.get('name') and b.get('name') == s.get('name'):
            continue                                                  # 原本就在
        if s['slot'] == 1:
            why = '新寵物在第 1 格（通常是騎寵）→ 不丟'
            continue
        if s.get('state') in ('騎乘', '出戰') or s.get('mountlike'):
            why = f'第 {s["slot"]} 格狀態 / 名字像騎寵戰寵 → 不丟'
            continue
        if s.get('level') != 1:
            why = f'第 {s["slot"]} 格新寵物等級 {s.get("level")} 不是 1（讀不出也算）→ 不丟'
            continue
        if not s.get('name'):
            why = f'第 {s["slot"]} 格新寵物名字讀不出 → 不丟'
            continue
        cand.append(s)
    if len(cand) == 1:
        return cand, ''
    if not cand:
        return cand, why or '轉生前後寵物欄沒有新出現的寵物'
    return cand, f'新出現 {len(cand)} 隻 Lv1 寵物（格 {[c["slot"] for c in cand]}），要剛好 1 隻'


def save_snapshot(snap: dict, path=None) -> None:
    p = Path(path or SNAPSHOT)
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(snap, ensure_ascii=False, indent=1), encoding='utf-8')
    except OSError:
        pass


def load_snapshot(path=None) -> dict:
    try:
        return json.loads(Path(path or SNAPSHOT).read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return {}


class _PetTools:
    def pets(self, roles):
        """開一次寵物面板逐人讀 → (rc, {role: slots})"""
        import pet
        ctx = pet.load_ctx(True)
        out = {}
        with pet.Session(False, True) as s:
            if s.rc:
                return s.rc, out
            for r in roles:
                rc, slots = pet.list_role(r, ctx)
                out[r] = slots
                if rc:
                    pet.save_ctx(ctx)
                    return rc, out
            pet.save_ctx(ctx)
        return 0, out

    def drop(self, role, name, slot=None, dry_run=False):
        import petdrop
        return petdrop.drop(role, name, name, slot_no=slot, dry_run=dry_run, max_level=1)


def take_snapshot(T=None, roles=None) -> int:
    T = T or _PetTools()
    rc, pets = T.pets(list(roles or ALL_ROLES))
    if rc:
        return rc
    save_snapshot(snapshot_pets(pets))
    return 0


def drop_rewards(n: int, before: dict | None = None, T=None, dry_run: bool = False, roles=None) -> int:
    """丟轉生獎勵寵。有對照表（一轉烏力斯坦 / 二轉奇娜）→ 名稱 + Lv1（petdrop --max-level 1）；沒有 → 用 before（轉生前快照）做 diff。
    回 0 / 98（diff 路徑不確定）/ 9 / 10 / petdrop 的碼（對照表路徑原碼透傳）。LAST['dropped'] = {角色: 名字}"""
    LAST.clear()
    T = T or _PetTools()
    roles = list(roles or ALL_ROLES)
    name = reward_name(n)
    if name:
        rc = T.drop('all', name, None, dry_run)
        if rc:
            return rc                                              # petdrop 原碼（70～79）；呼叫端對應
        LAST['dropped'] = {r: name for r in roles}
        return 0
    if not before:
        return uikit.fail(SRC, EXIT_REWARD, f'第 {n} 轉沒有獎勵寵對照表，也沒有轉生前的寵物欄快照（rebirth 階段沒跑過？）→ 不丟，請人確認')
    rc, after = T.pets(roles)
    if rc:
        return rc
    after = snapshot_pets(after)
    plan = {}
    for r in roles:
        cand, why = find_new_lv1(before.get(r), after.get(r))
        if len(cand) != 1:
            LAST['why'] = f'{r}：{why}'
            return uikit.fail(SRC, EXIT_REWARD, f'{r} 轉生獎勵寵無法確認：{why} → 全部都不丟（沒碰騎寵 / 戰寵）')
        plan[r] = cand[0]
    LAST['plan'] = {r: [s['slot'], s['name'], s['level']] for r, s in plan.items()}
    for r, s in plan.items():
        rc = T.drop(r, s['name'], s['slot'], dry_run)
        if rc:
            return rc if rc in (uikit.EXIT_UNKNOWN_SCREEN, uikit.EXIT_HALT) else uikit.fail(SRC, EXIT_REWARD, f'{r} 丟第 {s["slot"]} 格「{s["name"]}」失敗（petdrop rc={rc}）')
        LAST.setdefault('dropped', {})[r] = s['name']
    return 0


def main(argv=None) -> int:
    import winenv
    winenv.enable_server()
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    sub = ap.add_subparsers(dest='cmd', required=True)
    p = sub.add_parser('accept'); p.add_argument('--trans', type=int, required=True)
    p = sub.add_parser('gate'); p.add_argument('--trans', type=int, required=True)
    sub.add_parser('snapshot')
    p = sub.add_parser('drop-reward'); p.add_argument('--trans', type=int, required=True); p.add_argument('--dry-run', action='store_true')
    a = ap.parse_args(argv)
    if getattr(a, 'trans', 1) not in CN:
        print(f'{SRC}：--trans 要 1～5', file=sys.stderr)
        return uikit.EXIT_USAGE
    if a.cmd == 'accept':
        rc = accept_task(a.trans)
    elif a.cmd == 'gate':                                        # 0 = 已過門檻（傳送 / 已在吉魯島漆黑）、9 = 不認得的視窗、1 = 其他（看 JSON kind）
        g = level_gate(a.trans)
        LAST.update(gate=g)
        rc = 0 if g['kind'] in ('teleport', 'already') else uikit.EXIT_UNKNOWN_SCREEN if g['kind'] == 'unknown' else 1
    elif a.cmd == 'snapshot':
        rc = take_snapshot()
    else:
        rc = drop_rewards(a.trans, load_snapshot(), dry_run=a.dry_run)
    print(json.dumps(dict(LAST, ok=rc == 0, rc=rc), ensure_ascii=False, default=str))
    return rc


if __name__ == '__main__':
    sys.exit(main())
