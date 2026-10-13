#!/usr/bin/env python3
"""卡住自動重登的共用邏輯（questrun 與 rebirth 共用；只用標準函式庫）。

quest.py 回 19（自動巡路卡住，刷新角色 / 點地面 / 走出口都無效）、42（快速戰鬥 VS 牌卡死）= 客戶端 / 伺服器端狀態卡住，
解法是全員重登（relogin.py --stuck --confirm；登入畫面只按遊戲已帶入帳密的「登錄」，鐵則 2）→ 重登後 relogin 自己 team.check，
退出碼 105 = 進遊戲了但隊伍不對 → 呼叫端的重組函式（team.form --regroup）。
本檔只放「判斷 + 呼叫順序 + 計次」，呼叫端各自負責重登前後的善後（questrun：戰鬥設定 / HP / 遇敵；rebirth：龍王的守護重吃）。

  is_stuck(rc)                       quest.py 退出碼是不是這類（19 / 42）
  allowed(done, max_n=RELOGIN_MAX)   已重登 done 次，還能不能再來（每任務 / 每階段最多 RELOGIN_MAX=2 次）
  relogin_team(relogin_fn, regroup_fn, log)  → (status, code)：status = 'ok' / 'halt'（9 驗證視窗、10 斷線，code 原碼透傳，一律停手）/
                                      'relogin_fail'（relogin 非 0 / 105，code = relogin 退出碼）/ 'regroup_fail'（105 後重組失敗，code = team 退出碼）
  real_relogin()                     relogin.run(confirm=True, stuck=True)
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import uikit  # noqa: E402

STUCK_RC = (19, 42)
RELOGIN_TEAM = 105               # relogin.py：重登進遊戲了但隊伍檢查 / 組隊失敗
RELOGIN_MAX = 2                  # 每個任務 / 階段最多自動全員重登幾次
HALT_RC = (uikit.EXIT_UNKNOWN_SCREEN, uikit.EXIT_HALT)


def is_stuck(rc) -> bool:
    return rc in STUCK_RC


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


def main() -> int:
    """CLI：只印規則（不動遊戲）；要重登請直接用 relogin.py --stuck --confirm"""
    print(__doc__)
    return 0


if __name__ == '__main__':
    sys.exit(main())
