#!/usr/bin/env python3
"""questrun 的特殊步驟 handler（計畫 notes/plan-182-script.md §2.2）。只用標準函式庫；P2 只有 walk（成人儀式步 1）。

handler 都吃一個 tools 物件（questrun.Tools 或測試的 Fake），不直接碰遊戲，方便離線測。回 (rc, info)：rc 0 = 完成。

walk_step：遊戲「點追蹤不巡路」的步驟（成人儀式步 1：差使在 10204:188,13，路徑起點 14,7 → 188,14 但實測不動）。
  迴圈：讀座標 → 已到目標（±tol 格，同地圖）就結束；不在目標地圖 → 點追蹤讓遊戲巡路過去（最多 2 次、各等 CROSS_WAIT_S）；
  在目標地圖 → walk.walk_to。walk.py 遇敵後讀不到座標會丟 RuntimeError（2026-10-09 成人儀式實測要重跑數次）→ 外層重試。
  走到 188,13 附近差使對話框自己會開，之後交還 quest.py 預設模式按對話框。
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

EXIT_STEP = 112                  # 與 questrun.EXIT_STEP 同值（handler 不 import questrun，避免循環）
ARRIVE_TOL = 2
MAX_TRIES = 18                   # walk_to 外層重試上限
CROSS_WAIT_S = 25.0              # 點追蹤後等換地圖 / 巡路的秒數
CROSS_TRIES = 2


def arrived(pos, want: tuple, tol: int = ARRIVE_TOL) -> bool:
    """pos = (地圖, x, y) 或 None；want = (地圖, x, y)"""
    return bool(pos) and pos[0] == want[0] and abs(pos[1] - want[1]) <= tol and abs(pos[2] - want[2]) <= tol


def walk_step(T, track: str, sd: dict, log=print, on_loop=None, max_tries: int = MAX_TRIES) -> tuple:
    """sd = questdefs steps 的一項：dict(kind='walk', map=, xy=(x, y))。on_loop() 每圈呼叫（questrun 用來續吃龍王的守護）"""
    want = (sd['map'], sd['xy'][0], sd['xy'][1])
    info = {'want': want, 'tries': 0, 'errors': []}
    cross = 0
    for i in range(max_tries):
        info['tries'] = i + 1
        pos = T.read_pos()
        info['pos'] = pos
        if arrived(pos, want):
            log(f'walk：已到 {pos}（目標 {want}）')
            return 0, info
        if on_loop:
            on_loop()
        if pos is None:
            log('walk：讀不到座標，等 2 秒重讀')
            T.sleep(2)
            continue
        if pos[0] != want[0]:
            if cross >= CROSS_TRIES:
                info['msg'] = f'點追蹤 {cross} 次仍不在地圖 {want[0]}（目前 {pos}）'
                return EXIT_STEP, info
            cross += 1
            log(f'walk：目前在地圖 {pos[0]}，不是 {want[0]} → 點追蹤「{track}」讓遊戲巡路過去（第 {cross} 次）')
            T.track(track)
            waited = 0.0
            while waited < CROSS_WAIT_S:
                T.sleep(3)
                waited += 3
                p = T.read_pos()
                if p and p[0] == want[0]:
                    break
            continue
        try:
            got = T.walk_to(want[0], want[1], want[2])
            log(f'walk：walk_to 回 {got}')
        except RuntimeError as e:                              # 遇敵 / 讀不到座標中斷：外層重試
            info['errors'].append(str(e)[:80])
            log(f'walk：中斷（{str(e)[:80]}），重試')
            T.sleep(1)
    info['msg'] = f'走了 {max_tries} 圈仍沒到 {want}（最後位置 {info.get("pos")}）'
    return EXIT_STEP, info
