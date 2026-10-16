#!/usr/bin/env python3
"""依等級自動換練功點（grind.py follow）。只用標準函式庫。

用法（專案根目錄；WSL / Windows 原生指令相同）：
  uv run --no-project python tools/gui/grind.py follow [--every 15] [--buffer 0] [--spot-table real] [--trans 1] [--until-level N] [--dry-run]
        [--no-heal] [--hp 40] [--mp 20] [--check-every 20] [--stall-min 45]
  uv run --no-project python tools/gui/grind.py follow --stop        # 結束另一個在跑的 follow
背景常駐：平常不用手動起——「去練功」（grind.py start 不給 --spot，grind.go）確認掛機後，未滿地雷區會自動背景起
  `grind.py follow --no-heal --trans N`（ensure_running → winenv.spawn_detached；WSL = setsid 新 session、Windows = DETACHED_PROCESS；輸出 tools/.cache/follow.log；
  已有同轉數的在跑不重開、轉數不同先停再起）。手動起（WSL）：nohup setsid uv run --no-project python tools/gui/grind.py follow --no-heal --trans N > tools/.cache/follow.log 2>&1 &
結束條件（使用者 2026-10-15）：換到最高一檔（地雷區 / 地雷區2，spots.is_top）且 grind start 確認掛機 → 退出 0 + quest-events.log 一行；
  啟動 / 某一輪時已在最高一檔（且掛機沒有未恢復）→ 同樣結束（≥120 在地雷區不再監測）。dry-run 不結束。

做什麼：每 --every 秒讀隊長等級（state.hud.level，即 psa-hud 狀態列那個數字；watch 不在才退回 heal.stat()，連續 2 次一致才採用；
轉數用 --trans（預設 1，不從 HUD 讀，因為轉數位會被讀錯；等級文字容忍「0轉26級 / 1轉26級 / 轉24, / 24,」，見 level_of；地圖 ID 取 state.hud.map.id；轉生後要重啟）、等級只升不降，讀到比已確認低的視為誤讀）→ 依換點表（spots.FOLLOW，實測真門檻：1 柯奧龜洞、10 阿布龜洞、20 海主人隧道、45 五兄弟洞窟、
60 柯奧4F龜洞、80 波拉島、120 地雷區；1 轉以上沿用、未實測）算出該在的點，等級到門檻 + --buffer（預設 0）就換 →
隊長等級想換點時才讀一次隊伍 5 人等級（read_team_levels = 背包一次讀，快取 TEAM_TTL 300 秒、失敗 TEAM_FAIL_TTL 60 秒；使用者 2026-10-16）取最低（轉, 級），
再與傳送被擋記下的上限（spots.set_cap / team-cap.json）取小選點：隊友不夠就不換、不整支退出。和目前地圖不同時呼叫 grind.run('start', spot=...)（關遇敵 → 等戰鬥 → 傳送 → 外掛 → 開遇敵 → EXP 橫幅確認）。
傳送被擋（聊天「未達到N轉M級禁止傳送」，只在傳送失敗時 OCR 一次聊天區）→ errlog + 把該點門檻修正存 tools/.cache/spot-thresholds.json
（spots.learn）；擋住的是隊友（要求 <= 隊長）另記隊伍上限（spots.set_cap，0 轉也有效、之後選點不再選到該點），留在原點（grind.run('ensure')）、10 分鐘內不再試該點。
補血：隊長血 / 魔低（連 2 次）→ heal.heal_trip(目前點) → grind.run('ensure')。健康檢查：每 --check-every 分鐘（或等級 --stall-min 分鐘沒動）
grind.run('check')，快速 / 自動戰鬥關了或遇敵鈕關了 → grind.run('ensure')（自動修）。
暫停：battle.lock（quest / pet 在動）、petwatch / 別的 grind / heal --watch 在跑時不動作。watch 標 verify_suspect 時先讀一次畫面，
主畫面（idle / walking / battle）= 誤報忽略；已知面板 = 暫停；不認得 = 進入「unknown 暫停」（不點擊、不補血、不 ensure，只讀 state；
第一次寫 errlog 附 watch 警報截圖；畫面恢復自動繼續；不累計 BAD_MAX），連續超過 UNKNOWN_STOP_MIN（10）分鐘才停手（9）+ errlog（鐵則 5）。netwatch halt → 10。
狀態：tools/.cache/follow.json（等級、所在點、下一點、上次換點時間）；每次換點 / 升級寫 notes/quest-events.log 一行（「follow：…」）。
鎖：tools/.cache/follow.pid（單一實例）、換點之間持 grind.lock；--stop 寫 tools/.cache/follow.stop 通知結束。

退出碼（grind 50～59 段；共用 0 / 8 / 9 / 10 見 uikit）：
  0 到 --until-level、被 --stop、或已在 / 換到最高點（地雷區）並確認掛機    8 已有另一個 follow 在跑    9 疑似驗證視窗    10 netwatch halt
掛機未恢復（ensure / start 失敗）：每 30 秒重試 ensure 直到成功；另外 watch 讀到遇敵鈕關超過 60 秒也補 ensure；連 3 次失敗才停。
  57 補血失敗    59 連續讀不到等級    其餘 = grind.run 連 3 次失敗的退出碼（50～58）
"""
import json
import os
import re
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import errlog  # noqa: E402
import grind  # noqa: E402
import heal  # noqa: E402
import spots  # noqa: E402
import uikit  # noqa: E402
import watchstate  # noqa: E402

SRC = 'follow'
EXIT_NO_LEVEL = 59
CACHE = uikit.CACHE
PID_FILE, STOP_FILE, STATE_FILE = CACHE / 'follow.pid', CACHE / 'follow.stop', CACHE / 'follow.json'
import logpaths  # noqa: E402
import clients  # noqa: E402
EVENT_LOG = logpaths.p(clients.npath('quest-events.log'))     # 主視窗 = notes/quest-events.log；其他 = notes/clients/<程序名>/
BLOCK_RE = re.compile(r'未\s*達\s*到?\s*(\d+)\s*轉\s*(\d+)\s*級')
MAP_NAME_BOX = (1085, 30, 225, 80)    # 右上地圖名（兩行時 HUD 的 pos / map 欄會讀不到，例：五兄弟的山寨地下６樓）
CHAT_BOX = (65, 650, 460, 180)        # 左下聊天區（截圖座標；只在傳送失敗時 OCR）
MAIN_STATES = ('idle', 'walking', 'battle')
READ_GAP = 3.0                        # 等級兩次讀之間（watch 約 3 s 更新一次 HUD）
BAD_MAX = 40                          # 連續幾輪讀不到等級就停（每輪 --every 秒；15 s × 40 ≈ 10 分鐘。HUD 偶爾被蓋住 1～2 分鐘，10 輪太容易誤停，2026-10-11 實機）
FAIL_MAX = 3
BLOCK_COOLDOWN = 600.0
TEAM_TTL = 300.0                      # 隊伍最低等級讀一次的有效秒數（隊長等級想換點、隊友還不夠時，最多每 5 分鐘開一次背包讀）
TEAM_FAIL_TTL = 60.0                  # 讀隊伍失敗後多久再試
RETRY_GAP = 30.0                      # 掛機未恢復（ensure / start 失敗）後，每隔多久再試一次 ensure
ENC_OFF_SECS = 60.0                   # 練功點上遇敵鈕關超過這麼久（watch 零輸入讀到）就補 ensure
ENC_MAX_AGE = 5.0                     # state.screen 資料年齡上限
PANEL_PAUSE_MAX = 1800.0              # 使用者開著面板（watch 認得的：寵物 / 背包…）最多暫停這麼久；超過就照常跑（面板殘留不能讓 follow 永遠卡住）
UNKNOWN_STOP_MIN = 10                 # 畫面不認得（疑似驗證視窗）暫停最久幾分鐘；超過才退出 9。暫停期間不點擊、不補血、不 ensure，只讀 state（鐵則 5 要的是停止自動操作並通知）
sleep = time.sleep
clock = time.time


def log(msg: str) -> None:
    print(f'{time.strftime("%H:%M:%S")} follow：{msg}', flush=True)


def note(msg: str) -> None:
    """換點 / 升級事件：印出 + 寫 notes/quest-events.log"""
    log(msg)
    try:
        EVENT_LOG.parent.mkdir(exist_ok=True)
        with open(EVENT_LOG, 'a', encoding='utf-8') as f:
            f.write(f'{time.strftime("%Y-%m-%d %H:%M:%S")} follow：{msg}\n')
    except OSError:
        pass


level_of = spots.level_num            # HUD 等級文字 → 等級整數（轉數不採用；實作在 spots.level_num，grind 去練功也用）


# ---- 讀取（測試替換）----
def read_status() -> tuple:
    """→ (等級整數或 None, 地圖 ID 或 None)。只取「N級」的數字（HUD 的轉數位會讀錯，轉數用 --trans）。優先 state.hud.level / pos（零輸入）；watch 不在 / 太舊才退回 heal.stat()"""
    lv = level_of(watchstate.hud_field('level', 10.0))
    pos = watchstate.hud_field('pos', 10.0)
    mid = hud_map_id()
    if lv is None:
        try:
            s = heal.stat()
        except Exception:
            s = {}
        lv, pos = level_of(s.get('level')), s.get('pos') or pos
        m = re.match(r'(\d+):', str(pos or ''))
        mid = int(m[1]) if m else mid
    return lv, mid


def read_team_levels() -> dict | None:
    """背包面板一次讀 5 人 (轉, 級)（grind.read_team_bag，約 8 秒）→ {角色: (轉, 級) | None}；讀不到 / 出錯 None（測試替換）"""
    try:
        return grind.read_team_bag()
    except Exception as e:
        log(f'讀隊伍等級失敗：{e}')
        return None


def spot_by_name(text) -> str | None:
    """地圖名 OCR 文字 → 練功點名：只吃「唯一」吻合（地圖名連續 4 字出現在文字裡；柯奧龜洞 1 樓 / 4 樓同名前綴 → 兩個都吻合 = 不確定 None）"""
    s = re.sub(r'[^\u4e00-\u9fff]', '', str(text or ''))
    hit = []
    for n, v in spots.SPOTS.items():
        nm = re.sub(r'[^\u4e00-\u9fff]', '', v[4])
        if len(nm) >= 4 and any(nm[i:i + 4] in s for i in range(len(nm) - 3)):   # 連續 4 字（3 字太鬆：2026-10-13 海底通路被誤認五兄弟洞窟）
            hit.append(n)
    return hit[0] if len(hit) == 1 else None


def where_by_name() -> str | None:
    """HUD 地圖 ID 讀不到時（地圖名兩行）：OCR 右上地圖名判斷人在哪個練功點；讀不出 / 不確定 None"""
    for o in (('-Light', 170, '-Zooms', '2,3'), ('-Dark', 0, '-Zooms', '2,3')):
        n = spot_by_name(' '.join(uikit.ocr(MAP_NAME_BOX, *o)))
        if n:
            return n
    return None


def arrived_at(target: str) -> bool:
    """傳送失敗（EXIT_TELEPORT）後判斷人是否其實已在 target：以地圖 ID 為準（HUD id 讀得到就只比 ID，不吻合 = 沒到）；
    ID 讀不到才退回精確地圖名（where_by_name）"""
    mid = hud_map_id()
    if mid is not None:
        return mid == spots.SPOTS[target][2]
    return where_by_name() == target


def hud_map_id() -> int | None:
    """state.hud.map.id（HUD 地圖名右下「10001:40,6」那個 ID）；pos 欄位是座標 list，不含地圖 ID"""
    st = watchstate.fresh(10.0)
    mp = ((st or {}).get('hud') or {}).get('map') or {}
    i, ts = mp.get('id'), mp.get('ts')
    return i if isinstance(i, int) and isinstance(ts, (int, float)) and time.time() - ts <= 10.0 else None   # 欄位本身也要新（讀不到時 watch 留著舊值）


def verify_screen_state() -> str:
    """現場讀一次畫面（full=True：連寵物 / 背包 / 外掛等 watch 認得的面板也認，回 'panel'；不認得才是 unknown）"""
    return uikit.screen(full=True).get('state', 'error')


def read_block_msg() -> tuple | None:
    """傳送失敗後 OCR 聊天區：有「未達到N轉M級」→ (N, M)；有「未達 / 禁止傳送」但讀不出數字 → (None, None)；沒有 None"""
    text = ''.join(uikit.ocr(CHAT_BOX, '-Zooms', '2,3', '-Dark', 0))
    m = BLOCK_RE.search(text)
    if m:
        return int(m[1]), int(m[2])
    return (None, None) if ('未達' in text or '禁止傳送' in text) else None


def guard() -> None:
    import netwatch
    netwatch.guard('follow')


def stop_requested() -> bool:
    return STOP_FILE.exists()


def nap(secs: float) -> None:
    end = clock() + secs
    while clock() < end and not stop_requested():
        sleep(min(1.0, max(0.0, end - clock())))


def other_busy() -> str | None:
    import battleguard
    lk = battleguard.locked()
    if lk:
        return f'battle.lock（{lk.get("note", "")}）'
    return grind._other_running()


class Follow:
    def __init__(self, a):
        self.a = a
        self.good = None            # 已確認 (轉, 級)
        self.pending = None
        self.cur = None             # 目前所在練功點名
        self.cur_map = None
        self.bad = self.fails = 0
        self.block_until: dict = {}
        self.last_switch = None
        self.level_since = clock()
        self.last_check = clock()
        self.paused_note = None
        self.verify_note = 0.0
        self.unrecovered = False    # 掛機未恢復：ensure / start 失敗後為 True，每 RETRY_GAP 秒重試 ensure 直到成功
        self.retry_at = 0.0
        self.enc_off_since = None   # watch 讀到遇敵鈕關的起點（clock）
        self.panel_since = None     # watch 讀到面板開著的起點（clock）；None = 沒有面板
        self.panel_noted = None
        self.team_val = None        # 隊伍最低 (轉, 級)（背包讀 5 人；None = 沒讀到 → 只看隊長）
        self.team_at = None         # 上次讀隊伍的時間（clock）
        self.eff = None             # 這一輪選點用的有效 (轉, 級)（隊長 / 隊伍最低 / 被擋上限取小）
        self.unk_since = None       # 畫面不認得的起點（clock）；None = 沒在 unknown 暫停
        self.unk_logged = False

    # ---- 等級 ----
    def feed(self, lv) -> bool:
        """餵一次讀數；回 True = 這次讀數 == 已確認值（穩定）"""
        if lv is None:
            return False
        if self.good and lv == self.good:
            self.pending = None
            return True
        if self.good and lv[0] == self.good[0] and lv[1] < self.good[1]:
            log(f'讀到 {lv[0]}轉{lv[1]}級，比已確認的 {self.good[0]}轉{self.good[1]}級低，視為誤讀')
            self.pending = None
            return False
        if self.pending == lv:                       # 連續 2 次一致 → 採用
            if self.good:
                note(f'升級：{self.good[0]}轉{self.good[1]}級 → {lv[0]}轉{lv[1]}級')
            self.good, self.pending = lv, None
            self.level_since = clock()
            return True
        self.pending = lv
        return False

    def confirm_level(self):
        for i in range(3):
            lvl, self.cur_map = read_status()
            lv = (self.a.trans, lvl) if lvl else None
            if lv is None:
                self.bad += 1
            else:
                self.bad = 0
            if self.feed(lv):
                break
            if i < 2:
                nap(READ_GAP)
        return self.good if self.bad == 0 else None

    def eff_level(self) -> tuple:
        """選點用的有效 (轉, 級) = 隊長 / 隊伍最低 / 傳送被擋記下的上限 三者取小（使用者 2026-10-16）。
        只在「隊長等級想換點」時才呼叫：背包讀 5 人（一次約 8 秒），成功快取 TEAM_TTL 秒、失敗 TEAM_FAIL_TTL 秒內不重讀（失敗 = 只看隊長 + 上限，傳送被擋會自己退點）"""
        now = clock()
        ttl = TEAM_TTL if self.team_val else TEAM_FAIL_TTL
        if self.team_at is None or now - self.team_at >= ttl:
            lv = read_team_levels()
            self.team_at = now
            self.team_val = spots.team_min(lv)
            if self.team_val:
                note(f'隊伍最低 {self.team_val[0]}轉{self.team_val[1]}級（隊長 {self.good[0]}轉{self.good[1]}級）')
            else:
                log('隊伍等級讀不到，這輪只看隊長（傳送被擋會自動退點）')
        return spots.effective(self.good, self.team_val, spots.load_cap())

    # ---- 面板（使用者自己開的）----
    def panel_pause(self) -> bool:
        """watch 認得面板開著（state=panel，例：使用者在看寵物視窗）→ True = 暫停這一輪（不讀 HUD 等級、不點任何東西、不算 bad 輪）。
        最多暫停 PANEL_PAUSE_MAX 秒，超過照常跑（log 一次）；面板關了 / watch 讀不到就恢復。不是驗證警報、不退出"""
        sc = watchstate.screen(ENC_MAX_AGE)
        pn = (sc.get('panel') or '?') if isinstance(sc, dict) and sc.get('state') == 'panel' else None
        if pn is None:
            if self.panel_since is not None:
                log('面板已關，恢復')
            self.panel_since = self.panel_noted = None
            return False
        now = clock()
        if self.panel_since is None:
            self.panel_since = now
        if now - self.panel_since > PANEL_PAUSE_MAX:
            if self.panel_noted != 'max':
                log(f'面板（{pn}）開著超過 {int(PANEL_PAUSE_MAX / 60)} 分鐘，不再暫停，照常跑')
                self.panel_noted = 'max'
            return False
        if self.panel_noted != pn:
            log(f'面板（{pn}）開著（使用者操作中？），暫停這一輪')
            self.panel_noted = pn
        self.write_state('paused')
        return True

    # ---- 驗證 ----
    def alert_shot(self) -> str | None:
        """watch 警報附的截圖路徑（state.alerts[].shot）；沒有 / 讀不到 → None"""
        st = watchstate.fresh(10.0) or {}
        for a in st.get('alerts') or []:
            if isinstance(a, dict) and a.get('shot'):
                return str(a['shot'])
        return None

    def verify_check(self):
        """None = 沒事；-1 = 暫停這輪（面板 / 畫面不認得，不點任何東西）；其他整數 = 要結束的退出碼。
        watch 標旗 → 先現場讀畫面：主畫面 = 誤報；已知面板 = 暫停；不認得 = 進入 unknown 暫停，連續超過 UNKNOWN_STOP_MIN 分鐘才退出 9。
        暫停中（unk_since 有值）不管旗標，每輪都現場讀畫面，恢復成主畫面 / 已知面板就自動恢復。"""
        if self.unk_since is None and watchstate.verify_suspect() is not True:
            return None
        st = verify_screen_state()
        if st in MAIN_STATES or st == 'panel':
            if self.unk_since is not None:
                log(f'畫面恢復（{st}），follow 繼續（unknown 暫停了 {int(clock() - self.unk_since)} 秒）')
                self.unk_since, self.unk_logged = None, False
                self.verify_note = clock()
            elif st in MAIN_STATES and clock() - self.verify_note > 300:
                log(f'watch 標 verify_suspect 但畫面是 {st}（主畫面），視為誤報，繼續')
                self.verify_note = clock()
            return -1 if st == 'panel' else None      # 有面板開著：暫停這輪
        now = clock()
        if self.unk_since is None:
            self.unk_since = now
        if now - self.unk_since > UNKNOWN_STOP_MIN * 60:
            errlog.add(f'畫面不認得（{st}）超過 {UNKNOWN_STOP_MIN} 分鐘，follow 停止，請人工檢查畫面（鐵則 5）', source=SRC)
            log(f'畫面不認得超過 {UNKNOWN_STOP_MIN} 分鐘 → 停手通知使用者')
            uikit.trip_verify(f'畫面不認得（{st}）超過 {UNKNOWN_STOP_MIN} 分鐘', SRC)   # 答題介面正面命中才設本視窗旗標（其餘 watch 3 分鐘兜底，2026-10-16）
            return uikit.EXIT_UNKNOWN_SCREEN
        if not self.unk_logged:
            shot = self.alert_shot()
            errlog.add('畫面不認得，follow 暫停中，請人工確認' + (f'（watch 警報截圖：{shot}）' if shot else ''), source=SRC)
            log(f'畫面不認得（{st}），暫停（不點擊、不補血、不 ensure），最多 {UNKNOWN_STOP_MIN} 分鐘')
            self.unk_logged = True
        self.write_state('paused')
        return -1

    # ---- 狀態檔 ----
    def write_state(self, state='running'):
        g = self.good
        nxt = None
        if g:
            for lo, name in reversed(spots.FOLLOW):
                need = spots.stage_min(name, g[0])
                if g[1] < need + self.a.buffer and name != self.cur:
                    nxt = {'spot': name, 'level': need + self.a.buffer}
                    break
        d = {'ts': int(time.time()), 'pid': os.getpid(), 'state': state, 'trans': g[0] if g else None, 'level': g[1] if g else None,
             'spot': self.cur, 'next': nxt, 'last_switch': self.last_switch, 'dry_run': bool(self.a.dry_run)}
        try:
            STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
            STATE_FILE.write_text(json.dumps(d, ensure_ascii=False), encoding='utf-8')
        except OSError:
            pass

    # ---- grind 呼叫 ----
    def grind_run(self, mode, spot=None) -> int:
        try:
            return grind.run(mode, spot=spot, confirm_secs=grind.CONFIRM_SECS, fix=True)
        finally:
            grind.take_lock()                         # grind.run 結束會刪 grind.lock；換點之間自己再持

    def switch(self, target: str):
        trans, level = self.good
        old = self.cur
        if self.a.dry_run:
            note(f'[dry-run] {trans}轉{level}級：{old or "?"} → {target}')
            self.cur, self.last_switch = target, int(time.time())
            return None
        note(f'{trans}轉{level}級：{old or "?"} → {target}（grind start）')
        rc = self.grind_run('start', target)
        if rc == 0:
            self.cur, self.last_switch, self.fails, self.unrecovered = target, int(time.time()), 0, False
            note(f'已換到 {target} 掛機中')
            return self.top_done(target)
        if rc in (uikit.EXIT_IN_BATTLE,):
            return None                               # 有人在用畫面：下一輪再試
        if rc in (uikit.EXIT_UNKNOWN_SCREEN, uikit.EXIT_HALT):
            return rc
        if rc == grind.EXIT_TELEPORT:
            if arrived_at(target):                    # 其實傳過去了（地圖 ID 吻合；ID 讀不到才看精確地圖名）→ 當成功，補 ensure
                note(f'傳送驗證讀不到座標，但地圖 ID / 名稱確認是 {target}：視為已抵達，補 grind ensure')
                self.cur, self.last_switch, self.fails = target, int(time.time()), 0
                rc2 = self.grind_run('ensure')
                self.unrecovered = bool(rc2)
                return self.fail(rc2, f'抵達 {target} 後 ensure 失敗（{rc2}）') if rc2 else self.top_done(target)
            return self.on_blocked(target, old)
        return self.fail(rc, f'換到 {target} 失敗（grind 退出碼 {rc}）')

    def top_done(self, target):
        """換到最高一檔（地雷區，spots.is_top）且掛機已確認 → 0 = follow 結束（使用者 2026-10-15：≥120 在地雷區就不再監測）；其他 None 繼續。dry-run 不結束"""
        if self.a.dry_run or not spots.is_top(target):
            return None
        note(f'已在最高練功點 {target} 掛機（確認過），follow 結束')
        self.write_state('stopped')
        return 0

    def fail(self, rc, msg):
        self.fails += 1
        log(f'{msg}（連續 {self.fails}/{FAIL_MAX}）')
        self.unrecovered, self.retry_at = True, clock() + RETRY_GAP
        return rc if self.fails >= FAIL_MAX else None

    def recover(self, why):
        """掛機未恢復 / 遇敵鈕關太久 → 再跑 grind ensure。None = 繼續；整數 = 要結束的退出碼（連 FAIL_MAX 次失敗）"""
        note(f'{why}，重試 grind ensure')
        rc = self.grind_run('ensure')
        self.enc_off_since = None
        if rc == 0:
            if self.unrecovered:
                note('grind ensure 重試成功，掛機已恢復')
            self.unrecovered, self.fails = False, 0
            return None
        if rc == uikit.EXIT_IN_BATTLE:
            self.retry_at = clock() + RETRY_GAP
            return None
        if rc in (uikit.EXIT_UNKNOWN_SCREEN, uikit.EXIT_HALT):
            return rc
        r = self.fail(rc, f'重試 ensure 失敗（{rc}）')
        if r is not None:
            errlog.add(f'follow：grind ensure 連續 {FAIL_MAX} 次失敗（最後 rc={rc}），掛機未恢復，停止', source=SRC)
        return r

    def enc_watch(self):
        """保險：在練功點、無暫停條件，watch 讀到遇敵鈕關超過 ENC_OFF_SECS → ensure。讀不到 enc_on 就略過"""
        if self.a.dry_run or not self.cur:
            return None
        sc = watchstate.screen(ENC_MAX_AGE)
        on = sc.get('enc_on') if isinstance(sc, dict) else None
        now = clock()
        if on is not False:
            self.enc_off_since = None
            return None
        if self.enc_off_since is None:
            self.enc_off_since = now
            return None
        if now - self.enc_off_since < ENC_OFF_SECS:
            return None
        return self.recover(f'遇敵鈕關了超過 {int(ENC_OFF_SECS)} 秒（{self.cur}）')

    def on_blocked(self, target, old):
        trans, level = self.good
        blk = read_block_msg()
        self.block_until[target] = clock() + BLOCK_COOLDOWN
        if blk and blk[1] is not None:
            t, n = blk
            need = spots.UNREACHABLE if t > trans else n
            saved = spots.learn(target, trans, need)
            cap = spots.block_cap(blk, self.good)       # 擋住的是隊友（要求 <= 隊長）：記下上限，選點不再回到這點（0 轉沒有 learn，靠這個）
            capmsg = f'；隊伍有人低於 {cap[0]}轉{cap[1] + 1}級，選點上限記為 {spots.set_cap(*cap)}' if cap else ''
            msg = f'傳送 {target} 被擋（未達到{t}轉{n}級）：{trans}轉門檻修正為 {saved} 級{capmsg}，留在 {old or "原地"}'
        else:
            msg = f'傳送 {target} 失敗，聊天區沒讀到「未達到…」（{"有禁止傳送字樣但讀不出數字" if blk else "原因不明：戰鬥中 / 其他"}），10 分鐘後再試，不修正門檻'
        errlog.add(msg, source=SRC)
        note(msg)
        rc = self.grind_run('ensure')                 # 失敗的 start 已關遇敵：回原點恢復掛機
        if rc:
            return self.fail(rc, f'留在原點恢復掛機失敗（grind ensure 退出碼 {rc}）')
        self.unrecovered = False
        return None

    # ---- 補血 / 健康 ----
    def heal_check(self):
        if self.a.no_heal or self.a.dry_run or not self.cur or self.cur not in heal.SPOTS:
            return None
        s, ts = heal.read_vitals()
        if not heal.low(s, self.a.hp, self.a.mp):
            return None
        s2, _ = heal.read_vitals(ts)
        if not heal.low(s2, self.a.hp, self.a.mp):
            return None
        note(f'血 / 魔太低（HP {s2.get("hpPct")}% MP {s2.get("mpPct")}%），回村補血後回 {self.cur}')
        try:
            heal.heal_trip(self.cur, reopen=False)   # 接著 ensure 本來就會先關遇敵
        except RuntimeError as e:
            errlog.add(f'follow 補血失敗：{e}', source=SRC)
            return grind.EXIT_HEAL
        rc = self.grind_run('ensure')
        return self.fail(rc, f'補血後 ensure 失敗（{rc}）') if rc else None

    def health_check(self):
        if self.a.dry_run:
            return None
        now = clock()
        stalled = now - self.level_since >= self.a.stall_min * 60
        if now - self.last_check < self.a.check_every * 60:
            return None
        self.last_check = now
        rc = self.grind_run('check')
        if rc == 0:
            return None
        note(f'健康檢查 rc={rc}{"（等級停滯）" if stalled else ""}，自動修（grind ensure）')
        if rc in (uikit.EXIT_IN_BATTLE,):
            return None
        if rc in (uikit.EXIT_UNKNOWN_SCREEN, uikit.EXIT_HALT):
            return rc
        rc2 = self.grind_run('ensure')
        return self.fail(rc2, f'ensure 失敗（{rc2}）') if rc2 else None

    # ---- 一輪 ----
    def step(self):
        """None = 繼續；整數 = 結束的退出碼"""
        if stop_requested():
            return 0
        guard()
        busy = other_busy()
        if busy:
            if self.paused_note != busy:
                log(f'{busy} 在動，暫停')
                self.paused_note = busy
            self.write_state('paused')
            return None
        self.paused_note = None
        if self.panel_pause():
            return None
        v = self.verify_check()
        if v == -1:
            return None
        if v:
            return v
        lv = self.confirm_level()
        if lv is None:
            if self.bad >= BAD_MAX:
                errlog.add(f'follow 連續 {BAD_MAX} 輪讀不到等級（HUD 被蓋住？），停止', source=SRC)
                return EXIT_NO_LEVEL
            log(f'讀不到 / 未穩定的等級（{self.bad}/{BAD_MAX}）')
            return None
        trans, level = lv
        if self.a.until_level and level >= self.a.until_level:
            note(f'隊長已達 {trans}轉{level}級 ≥ --until-level {self.a.until_level}，結束 follow（只看隊長）')
            self.write_state('stopped')
            return 0
        if self.cur_map is not None:
            self.cur = spots.spot_of_map(self.cur_map)
        else:
            self.cur = where_by_name() or self.cur   # HUD 讀不到地圖 ID：用地圖名
        table = spots.FOLLOW
        target = spots.spot_for(trans, level, self.a.buffer, table)
        same = self.cur and target and (self.cur == target or spots.same_tier(self.cur, target))
        self.eff = self.good
        if target and not same:                      # 隊長想換點 → 看隊伍最低等級 / 被擋上限，可能不換或換到較低的點
            self.eff = self.eff_level()
            if self.eff != self.good:
                target = spots.spot_for(self.eff[0], self.eff[1], self.a.buffer, table)
                same = self.cur and target and (self.cur == target or spots.same_tier(self.cur, target))
        if same and spots.is_top(target) and not self.a.dry_run and not self.unrecovered:
            note(f'{trans}轉{level}級已在最高練功點 {self.cur}，不再監測，follow 結束')
            self.write_state('stopped')
            return 0
        if target and not same and clock() >= self.block_until.get(target, 0):
            rc = self.switch(target)
            if rc is not None:
                return rc
        else:
            rc = self.heal_check()
            if rc is None and self.unrecovered and not self.a.dry_run and clock() >= self.retry_at:
                rc = self.recover('掛機未恢復')
            if rc is None:
                rc = self.health_check()
            if rc is None:
                rc = self.enc_watch()
            if rc is not None:
                return rc
        self.write_state()
        return None


def alive_other() -> int | None:
    import battleguard
    try:
        pid = int(PID_FILE.read_text().strip())
    except (OSError, ValueError):
        return None
    return pid if pid != os.getpid() and battleguard.pid_alive(pid) else None


def stop_other() -> int:
    pid = alive_other()
    if not pid:
        print('follow：沒有在跑的 follow')
        return 0
    STOP_FILE.write_text(str(os.getpid()))
    import battleguard
    for _ in range(60):
        if not battleguard.pid_alive(pid):
            break
        time.sleep(1)
    try:
        STOP_FILE.unlink()
    except OSError:
        pass
    print(f'follow：已通知 pid {pid} 結束' + ('' if not battleguard.pid_alive(pid) else '（60 秒內還沒結束，可能正在換點）'))
    return 0


def read_state() -> dict:
    """tools/.cache/follow.json（在跑的 follow 自己寫的狀態：trans / level / spot …）；讀不到 {}"""
    try:
        d = json.loads(STATE_FILE.read_text(encoding='utf-8'))
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


LOG_FILE = CACHE / 'follow.log'
SPAWN_WAIT = 15.0                     # 背景起 follow 後等它寫 follow.pid 的上限（秒）


def ensure_running(trans: int, no_heal: bool = True, spawn=None, wait: float = SPAWN_WAIT) -> dict:
    """「去練功」用：確保有一支 follow（帶 --trans trans、預設 --no-heal）在背景跑。
    已有 follow 在跑且轉數相同（follow.json 的 trans；讀不到也算相同）→ 不重開；轉數不同 → 先 --stop 再起新的。
    背景起法 = winenv.spawn_detached（WSL：setsid 新 session；Windows：DETACHED_PROCESS），輸出附加到 tools/.cache/follow.log。
    回 {'action': 'running' | 'started' | 'fail', 'pid': …, 'why': …}；spawn 可換（測試）"""
    pid = alive_other()
    if pid:
        st = read_state()
        t = st.get('trans')
        if st.get('pid') != pid or t in (None, trans):              # 狀態檔不是它寫的（剛起）/ 轉數相同 → 當作同一支，不重開
            return {'action': 'running', 'pid': pid}
        log(f'在跑的 follow（pid {pid}）轉數 {t} ≠ {trans} → 先停掉再起')
        stop_other()
    import winenv
    argv = [sys.executable, str(HERE / 'grind.py'), 'follow', '--trans', str(int(trans))] + (['--no-heal'] if no_heal else [])
    try:
        CACHE.mkdir(parents=True, exist_ok=True)
        spid = (spawn or winenv.spawn_detached)(argv, LOG_FILE)
    except OSError as e:
        return {'action': 'fail', 'pid': None, 'why': f'起不來：{e}'}
    end = clock() + wait
    while clock() < end:
        got = alive_other()
        if got:
            return {'action': 'started', 'pid': got}
        sleep(0.5)
    return {'action': 'fail', 'pid': spid, 'why': f'{wait:.0f} 秒內沒看到 follow.pid（看 {LOG_FILE}）'}


def run(a) -> int:
    if a.stop:
        return stop_other()
    pid = alive_other()
    if pid:
        print(f'follow：已有另一個 follow 在跑（pid {pid}）', file=sys.stderr)
        return uikit.EXIT_IN_BATTLE
    try:
        STOP_FILE.unlink()
    except OSError:
        pass
    PID_FILE.parent.mkdir(parents=True, exist_ok=True)
    PID_FILE.write_text(str(os.getpid()))
    grind.take_lock()
    f = Follow(a)
    log(f'開始：{a.trans} 轉，每 {a.every}s 讀等級，門檻 ' + '、'.join(f'{lo}→{n}' for lo, n in reversed(spots.FOLLOW)) + f'，buffer {a.buffer}'
        + (f'，到 {a.until_level} 級停' if a.until_level else '') + ('，dry-run' if a.dry_run else ''))
    rc = 0
    try:
        while True:
            rc = f.step()
            if rc is not None:
                break
            nap(a.every)
            if stop_requested():
                rc = 0
                break
    except SystemExit as e:
        rc = int(e.code or 0) or uikit.EXIT_HALT
        errlog.add(f'follow 因 netwatch / 停手退出（{rc}）', source=SRC)
        raise
    except KeyboardInterrupt:
        rc = 0
    finally:
        f.write_state('stopped')
        grind.release_lock()
        try:
            if PID_FILE.read_text().strip() == str(os.getpid()):
                PID_FILE.unlink()
        except OSError:
            pass
        try:
            STOP_FILE.unlink()
        except OSError:
            pass
    log(f'結束（rc {rc}）')
    return rc


def add_parser(sub) -> None:
    p = sub.add_parser('follow', help='依等級自動換練功點（常駐）')
    p.add_argument('--every', type=int, default=15, help='讀等級間隔秒數（預設 15；讀 state.json 零輸入；連續 2 次一致才採用，最慢約 30 秒發現升級）')
    p.add_argument('--buffer', type=int, default=0, help='門檻再加幾級才換（預設 0 = 到門檻就換）')
    p.add_argument('--spot-table', choices=['real'], default='real', help='換點表（real = 實測真門檻 spots.FOLLOW）')
    p.add_argument('--until-level', type=int, default=0, help='隊長到這個等級就停（預設不停）')
    p.add_argument('--dry-run', action='store_true', help='只印會換到哪，不傳送')
    p.add_argument('--no-heal', action='store_true')
    p.add_argument('--hp', type=int, default=40)
    p.add_argument('--mp', type=int, default=20)
    p.add_argument('--check-every', type=int, default=20, help='幾分鐘做一次 grind check（預設 20）')
    p.add_argument('--stall-min', type=int, default=45, help='等級幾分鐘沒動就在 log 標「停滯」（預設 45）')
    p.add_argument('--trans', type=int, default=1, help='轉生數（預設 1；HUD 的轉數位會讀錯，所以不從畫面讀，轉生後要重啟 follow 改這個值）')
    p.add_argument('--stop', action='store_true', help='結束另一個在跑的 follow')
