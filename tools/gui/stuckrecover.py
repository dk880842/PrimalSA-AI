#!/usr/bin/env python3
"""卡住自動重登的共用邏輯（questrun 與 rebirth 共用；只用標準函式庫）。

quest.py 回 19（自動巡路卡住，刷新角色 / 點地面 / 走出口都無效）、42（快速戰鬥 VS 牌卡死）= 客戶端 / 伺服器端狀態卡住，
解法是全員重登（relogin.py --stuck --confirm；登入畫面只按遊戲已帶入帳密的「登錄」，鐵則 2；有本機帳號對照 accounts.local.json 時先核對帳號欄、不符只重打帳號欄，多視窗也照跑，否則多視窗 109）→ 重登後 relogin 自己 team.check，
退出碼 105 = 進遊戲了但隊伍不對 → 呼叫端的重組函式（team.form --regroup）。
本檔只放「判斷 + 呼叫順序 + 計次」，呼叫端各自負責重登前後的善後（questrun：戰鬥設定 / HP / 遇敵；rebirth：龍王的守護重吃）。

  is_stuck(rc)                       quest.py 退出碼是不是這類（19 / 42）
  is_retry(rc)                       quest.py 退出碼是不是「不用重登、重跑同一片就好」（43 載入 / 轉場畫面卡 60 秒；載入中沒有 HUD，relogin 也登出不了）
  allowed(done, max_n=RELOGIN_MAX)   已重登 done 次，還能不能再來（每任務 / 每階段最多 RELOGIN_MAX=2 次）
  relogin_team(relogin_fn, regroup_fn, log)  → (status, code)：status = 'ok' / 'halt'（9 驗證視窗、10 斷線，code 原碼透傳，一律停手）/
                                      'relogin_fail'（relogin 非 0 / 105，code = relogin 退出碼）/ 'regroup_fail'（105 後重組失敗，code = team 退出碼）
  real_relogin()                     relogin.run(confirm=True, stuck=True)

「出口來回跳 / 原地不前進」偵測（2026-10-14 碧青洞窟 08:48～09:10：加魯卡 200 (139,1007/1008) ↔ 奇喀喀村 3400 (60,40/41)，
quest.py 3 / 30 交替 20 分鐘，舊版只會刷新 + 重踏出口，從沒觸發重登；09:10～09:15 手動 全員重登 → 組隊 → 走出口到對面 → 離開出口十幾格 → 點追蹤 = 解開）：
  junction(positions, warps)         純函式：每片結束讀到的座標都落在同一對互通地圖 A↔B 的出口附近（NEAR_EXIT 格內）→ (目前那張, 對面那張)；不是 → None
  no_progress(positions, warps, n)   純函式：最後 n 片座標沒進展 → {'kind': 'junction', 'pair': (A, B)} / {'kind': 'same'}（同圖 SAME_SPOT 格內原地）/ None
                                     （讀得到的座標 < 2 個 = 沒證據 → None）
  呼叫端（questrun）：同一任務連續 STUCK_SLICES 片 quest.py 都是 3 / 30、步號沒前進、no_progress 成立 → 全員重登（relogin_team）→ 組隊 →
  pair 有值時 walk.leave_junction(A, B)：走出口到對面、再離開對面那排回頭出口 ≥ AWAY_MIN 格 → 再點追蹤。不寫死任何一對地圖，出口資料一律讀 MapWarp。
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import uikit  # noqa: E402

STUCK_RC = (19, 42)
RETRY_RC = (43,)                 # quest.EXIT_LOADING_STUCK：載入畫面卡住 → 重跑同一片（quest.py 會再等一輪 60 秒），每任務 / 階段最多 RELOGIN_MAX 次
RELOGIN_TEAM = 105               # relogin.py：重登進遊戲了但隊伍檢查 / 組隊失敗
RELOGIN_MAX = 2                  # 每個任務 / 階段最多自動全員重登幾次
HALT_RC = (uikit.EXIT_UNKNOWN_SCREEN, uikit.EXIT_HALT)
BOUNCE_RC = (3, 30)               # quest.py 3 追蹤沒反應 / 30 隊伍不符：碧青 2026-10-14 兩者交替出現
STUCK_SLICES = 4                  # 同一任務連續幾片 BOUNCE_RC 且座標沒進展 → 卡住，走重登 + 離開交界
NEAR_EXIT = 5                     # 離「通往另一張圖的出口」幾格內（切比雪夫）算在交界
SAME_SPOT = 3                     # 同一張圖、都在第一個座標幾格內 = 原地沒進展


def is_stuck(rc) -> bool:
    return rc in STUCK_RC


def is_retry(rc) -> bool:
    return rc in RETRY_RC


def allowed(done: int, max_n: int = RELOGIN_MAX) -> bool:
    return done < max_n


def real_relogin() -> int:
    import relogin
    return relogin.run(confirm=True, stuck=True)


def relogin_team(relogin_fn, regroup_fn, log=print) -> tuple:
    """全員重登 → 105 時重組。回 (status, code)，見檔頭"""
    rr = relogin_fn()
    log(f'全員重登 rc={rr}')
    if rr in HALT_RC:
        return 'halt', rr
    if rr not in (0, RELOGIN_TEAM):
        return 'relogin_fail', rr
    if rr == RELOGIN_TEAM:
        rc = regroup_fn()
        if rc:
            return ('halt' if rc in HALT_RC else 'regroup_fail'), rc
    return 'ok', rr


def _near_to(m: int, x: int, y: int, warps, near: int) -> set:
    """(m, x, y) 附近 near 格內的換圖出口通往哪些地圖"""
    return {w['tMap'] for w in warps
            if w.get('fMap') == m and not w.get('isNotUse') and w.get('tMap') != m
            and max(abs(w['fX'] - x), abs(w['fY'] - y)) <= near}


def junction(positions, warps, near: int = NEAR_EXIT):
    """純函式：positions = [(地圖, x, y) | None …]（每片結束各讀一次）。全部讀得到的座標都在 A↔B 這對互通地圖的出口 near 格內
    → (最後一個座標所在的圖, 對面那張)；只在 A 一張圖也算（都在通往 B 的出口旁）；三張圖以上 / 不在出口旁 → None"""
    pts = [p for p in positions or [] if p]
    if len(pts) < 2:
        return None
    maps = sorted({p[0] for p in pts})
    if len(maps) > 2:
        return None
    if len(maps) == 2:
        a, b = maps
        for m, x, y in pts:
            if (b if m == a else a) not in _near_to(m, x, y, warps, near):
                return None
        cur = pts[-1][0]
        return cur, (b if cur == a else a)
    cand = None
    for m, x, y in pts:
        t = _near_to(m, x, y, warps, near)
        cand = t if cand is None else cand & t
    if not cand:
        return None
    return maps[0], min(cand)


def no_progress(positions, warps, n: int = STUCK_SLICES, near: int = NEAR_EXIT, same: int = SAME_SPOT):
    """純函式：最後 n 片的座標沒進展嗎 → {'kind': 'junction', 'pair': (目前圖, 對面圖)} / {'kind': 'same'} / None。
    呼叫端自己保證這 n 片都是 BOUNCE_RC、步號沒前進（這裡只看座標）"""
    tail = list(positions or [])[-n:]
    if len(tail) < n:
        return None
    pair = junction(tail, warps, near)
    if pair:
        return {'kind': 'junction', 'pair': pair}
    pts = [p for p in tail if p]
    if len(pts) >= 2 and len({p[0] for p in pts}) == 1 and all(max(abs(p[1] - pts[0][1]), abs(p[2] - pts[0][2])) <= same for p in pts):
        return {'kind': 'same'}
    return None


def map_warps():
    """MapWarp 全表（knowledge/data/tables，經 psa.py 讀；讀不到 = []）"""
    try:
        import walk
        return walk.psa.T('MapWarp')
    except Exception:                                                   # noqa: BLE001
        return []


def main() -> int:
    """CLI：只印規則（不動遊戲）；要重登請直接用 relogin.py --stuck --confirm"""
    print(__doc__)
    return 0


if __name__ == '__main__':
    sys.exit(main())
