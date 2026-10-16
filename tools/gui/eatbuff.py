#!/usr/bin/env python3
"""吃 buff 道具（2倍智慧果 / 龍王的守護）的共用邏輯：吃前靜下來、用 buff 剩餘時間判斷吃到沒、確實關背包。只用標準函式庫。
depot_use.py（取出 → 吃 → 存回）與 `bag.py use`（背包已有、使用者明確要多吃）共用，不各寫一份。

2026-10-16 p2 DKBO6 事件：
- 09:52 bag.py use 2倍智慧果 → 回 ok、buff=true，但剩餘時間沒變 / 數量沒少（buff 本來就有，圖示在 = 假陽性）；12:54 回 ok 但 buff=false。
  兩次都是遇敵開著、掛機快速戰鬥中；12:56 先關遇敵並等戰鬥結束再吃才吃到（推測：戰鬥中點「使用」無效，未證實）。
- use 後背包面板沒關（同因推測：點下去時戰鬥剛好開打、畫面被蓋住，close_leftover 看不到背包外框）。
做法：
1. 吃前 heal.encounter_off_wait()（關原地遇敵 + 等 VS 牌消失；questrun 交接同一個）。吃完是否開回由呼叫端決定：
   depot_use / bag.py use 預設開回（原本就是掛機中才吃；`--no-reopen` 跑任務時不開）。
2. 判斷改看 buff 剩餘時間（不比道具數量）：吃前讀剩餘（沒圖示 = 0）→ 吃後讀 → 增加量 ≥ 持續時間 − 容許（智慧果 6 小時 − 5 分、龍王 10 分 − 3 分 20 秒）才算吃到，
   沒增加 = EXIT_VERIFY（95）。吃前有圖示卻讀不出剩餘時間 → 不吃（不知道基準，吃了也驗不出）。
   吃前沒圖示 → 吃後圖示出現就算吃到（時間讀不出時以圖示為準並 record_eaten 寫預計到期，只記警告）；吃前有 buff 一定要讀到時間才算。
   龍王若是「重置成滿」而非疊加：吃後剩餘 ≥ 持續時間 − 60 秒且比吃前多 60 秒以上也算（智慧果是疊加，不套這條）。
3. 使用後確實關背包：use_item 回來若背包外框還在 → bag.close_leftover 再關一次。
"""
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import bag  # noqa: E402
import bufftime  # noqa: E402
import heal  # noqa: E402
import uikit  # noqa: E402

TOL_S = 300                 # 吃到的判斷容許誤差上限（吃的動作耗時 + OCR 讀分鐘）


def log(msg: str) -> None:
    print(f'eatbuff：{msg}', file=sys.stderr, flush=True)


def need_gain(kind: str) -> int:
    """剩餘時間至少要增加幾秒才算吃到：持續時間 − min(5 分, 持續時間/3)"""
    dur = bufftime.EAT_DURATION_S[kind]
    return dur - min(TOL_S, dur // 3)


def judge(kind: str, before_s: int, after_s: int) -> bool:
    """吃前 / 吃後剩餘秒數 → 吃到了嗎（純函式）"""
    dur = bufftime.EAT_DURATION_S[kind]
    if after_s - before_s >= need_gain(kind):
        return True
    return kind == 'dragon' and after_s >= dur - 60 and after_s - before_s >= 60       # 重置成滿（若遊戲不疊加）


def remaining(kind: str) -> tuple:
    """buff 剩餘秒數 → (秒 | None, rc)。沒圖示 = (0, 0)；圖示像素讀不到 / 時間讀不出 = (None, rc)。
    用 bufftime.read 讀（點圖示開浮窗 OCR 再關；順便把實際值寫 bufftime.json）。背包要已關（buff 列被面板蓋住）"""
    st = bag.buff_state(kind)
    if st is None:
        return None, bufftime.EXIT_ROW
    if not st:
        return 0, 0
    res = bufftime.read(kind)
    ent = next((b for b in res.get('buffs', []) if b.get('kind') == kind), None)
    if ent:
        return int(ent['remaining_s']), 0
    return None, res.get('rc') or bufftime.EXIT_TIME


def verify(kind: str, before_s: int, eat_ts: float, info: dict) -> int:
    """吃完、背包已關後驗證：0 = 吃到；bag.EXIT_VERIFY = 沒吃到 / 驗不出。結果寫進 info（buff / remain_before / remain_after / bufftime / warn_buff）"""
    info['remain_before'] = before_s
    icon = bag._wait(lambda: bag.has_buff(kind), 4.0)
    info['buff'] = icon
    if not icon:
        info['warn_buff'] = f'使用後 buff 列沒看到 {kind} 圖示（沒吃到）'
        return bag.EXIT_VERIFY
    after, rc = remaining(kind)
    info['remain_after'] = after
    if after is not None:
        if judge(kind, before_s, after):
            info['bufftime'] = 'read'                                   # bufftime.read 已把實際讀值寫進 bufftime.json
            return 0
        info['buff'] = False
        info['warn_buff'] = (f'{kind} 剩餘時間沒增加（吃前 {before_s} 秒 → 吃後 {after} 秒，要增加 ≥ {need_gain(kind)} 秒）：沒吃到'
                             '（道具數量不拿來判斷）')
        uikit.snap('eat-nogain')
        return bag.EXIT_VERIFY
    if before_s == 0:                                                   # 吃前沒圖示、吃後有 = 吃到了；時間讀不出就用預計值
        info['warn_time'] = f'吃後剩餘時間讀不出（rc {rc}）：吃前沒 buff、吃後圖示出現，視為吃到'
        try:
            if bufftime.record_eaten(kind, eat_ts):
                info['bufftime'] = 'eat'
        except Exception as e:                                          # noqa: BLE001
            info['warn_bufftime'] = f'寫到期快取失敗：{e}'
        return 0
    info['buff'] = False
    info['warn_buff'] = f'吃前已有 {kind}（剩 {before_s} 秒），吃後剩餘時間讀不出（rc {rc}）：無法確認有沒有吃到'
    return bag.EXIT_VERIFY


def close_bag_leftover(info: dict) -> None:
    """use 之後背包外框還在（戰鬥剛好開打蓋住 / 彈窗殘留）→ 再關一次"""
    if uikit.is_open(bag.BAGANY) or bag.popup_open():
        t = bag.close_leftover(dialog_esc=True)
        info['closed_leftover'] = t or 'none'
        log(f'use 後背包還開著 → close_leftover：{t!r}')


def eat_have(role: str, item: str, reopen: bool = True) -> tuple:
    """背包已有 item：關遇敵 + 等戰鬥結束 → 讀吃前剩餘 → bag.use_item → 關背包 → 驗剩餘時間增加 → 視 reopen 開回遇敵。→ (rc, info)。
    不是 buff 道具（沒得讀時間）→ 只 use_item。bag.py use 走這裡"""
    info = {'role': role, 'item': item}
    kind = bag.buff_kind(item)
    rc = 1
    try:
        heal.encounter_off_wait()
        before = 0
        if kind:
            before, brc = remaining(kind)
            if before is None:
                info.update(step='before', warn_buff=f'吃前讀不出 {kind} 剩餘時間（rc {brc}），不吃')
                rc = bag.EXIT_VERIFY
                return rc, info
        eat_ts = time.time()
        rc = bag.use_item(role, item)
        info['step'] = 'use'
        close_bag_leftover(info)
        if not rc and kind:
            rc = verify(kind, before, eat_ts, info)
            info['step'] = 'verify' if rc else 'done'
        return rc, info
    finally:
        if reopen:
            try:
                heal.set_encounter(True)
            except RuntimeError as e:
                info['enc_warn'] = str(e)
