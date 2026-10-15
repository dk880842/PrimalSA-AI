#!/usr/bin/env python3
"""網路異常自動重連（只用標準函式庫）。遊戲跳出「提示：網路異常，是否重連?」時點「確定」。

實測（2026-10-10）：點確定後遊戲**直接回到登入畫面**（帳號 / 密碼欄由遊戲自動帶入、登錄 / 註冊鈕），不會自動重連。
使用者授權（2026-10-10，AGENTS.md 鐵則 2 的例外，只限這樣）：登入畫面**只點「登錄」**（用遊戲自動帶入的帳密），
之後處理「選擇角色 → 一鍵全登」→ 載入 → 進遊戲 → 清當前角色 → 檢查隊伍（失散時 team.form）→ 自動跑 grind.py ensure 一次（P8：重設 5 人快速 / 自動戰鬥、開遇敵；失敗只記 errlog 不重試）。密碼欄絕不碰（帳號欄只在下面「帳號核對」時重打）、不點鑰匙 / 註冊、
不讀 savepwd.txt 或登錄檔、不把帳號寫進任何 log。帳密欄空的 / 登錄後出現提示視窗 / 連續 3 次登錄失敗 / 看不懂的畫面 → halt 停手通知使用者。
多視窗（2026-10-15 使用者決定，auto_login_check）：非主視窗（PSA_CLIENT ≠ PrimalSA）一律不按登錄；主視窗偵測到還有別的 PrimalSA* 程序在跑也不按
（遊戲記住的帳號是所有視窗共用的，自動登錄可能登錯帳號、互踢）→ 照樣偵測斷線、點「網路異常」的確定，回到登入畫面就 halt 通知使用者。
只有單一視窗時維持自動登錄。查不到程序清單 = 讀取失敗：本輪不點，連續 5 輪才 halt。
帳號核對（2026-10-15 使用者新規則，accounts.py；未實機）：本機設定檔 tools/gui/accounts.local.json（不進 git）有「本視窗 → 帳號」時，
不管單 / 多視窗都改走帳號核對、不看程序清單：OCR 讀帳號欄（多倍數一致才算讀得出）→ = 本視窗帳號 → 按登錄；
≠（帳號記憶共用，常態）→ 拿全視窗共用的登入輸入鎖 login-input.lock → 點帳號欄 → 清空 → 確認空 → 只打帳號（gui typeq，PostMessage 到本視窗 hwnd、
log 只記字數）→ 再讀一次 = 本視窗帳號才按登錄、放鎖；重打後仍不符 / 讀不出 / 清不掉 / 密碼欄變空 / 畫面不是登入畫面 → halt。密碼欄絕對不碰。
沒設定檔 / 本視窗不在對照表 / 設定檔格式錯 → 上面的舊行為逐字不變。log / errlog 只寫「帳號欄核對：符合 / 不符 / 讀不出」，不寫帳號名。
全視窗驗證停手旗標（verifyhalt.py）存在 → check_and_reconnect 回 status 'verify'、guard sys.exit(9)，什麼都不點。

  import netwatch
  r = netwatch.guard('quest')            # 腳本迴圈每輪呼叫；要停手時直接 sys.exit(10 / 11)，否則回傳 dict
  r = netwatch.check_and_reconnect()     # 不 exit 的版本，回傳 {'status': ...}
status：ok（沒事）/ reconnected（重連 / 重新登錄成功，已恢復）/ halt（要人類）/ fatal（連續失敗 3 次）/ verify（全視窗驗證停手旗標）
命令列：
  python tools/gui/netwatch.py --once                 檢查一次
  python tools/gui/netwatch.py --watch [--interval 10]  常駐（沒有其他腳本在跑、只是掛機時用）
  python tools/gui/netwatch.py --status                印目前 halt / 失敗計數
退出碼：0 正常、9 全視窗驗證停手旗標、10 需要人類登入（halt）、11 連續重連失敗、2 版面不支援。
狀態檔（tools/.cache/，非主視窗在 tools/.cache/clients/<程序名>/；不進 git）：netwatch.halt（存在 = 已停手，等人類登入；HUD 回來後自動刪除）、
netwatch.json（連續失敗計數）、netwatch.act.lock（動作鎖：同時只有一支腳本在處理重連，不會互相亂點）、netwatch.lock（--watch 單例）。
"""
import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import accounts  # noqa: E402
import actlog  # noqa: E402
import clients  # noqa: E402
import errlog  # noqa: E402
import layout  # noqa: E402
import screen_sigs  # noqa: E402
import winenv  # noqa: E402
from walk import gui, log  # noqa: E402

PS_TIMEOUT = 40                      # 單次 PowerShell 呼叫上限（秒）；逾時當讀取失敗
READ_FAIL_MAX = 5                    # 登入畫面連續 N 輪讀不到帳密欄 / 遊戲畫面 → halt

CACHE = clients.cache_dir()          # 每個視窗一份（主視窗 = tools/.cache，與改版前相同；PSA_CLIENT=PrimalSA2 → tools/.cache/clients/PrimalSA2）
HALT = CACHE / 'netwatch.halt'
STATE = CACHE / 'netwatch.json'
ACT_LOCK = CACHE / 'netwatch.act.lock'
WATCH_LOCK = CACHE / 'netwatch.lock'

EXIT_HALT = 10
EXIT_FATAL = 11
EXIT_VERIFY = 9                      # 全視窗驗證停手旗標（verifyhalt.py）= uikit.EXIT_UNKNOWN_SCREEN
MAX_FAILS = 3
TOL = screen_sigs.NET_TOL

# ---- 特徵（2880×1659 版面，截圖座標；2026-10-10 實測）----
CONFIRM = (715, 557)                 # 提示視窗唯一的藍色「確定」
# 米色「提示」視窗：左右 + 按鈕列兩側是米色（兩顆鈕的對話框兩側會是藍 / 米，所以左右 600 / 830 也要米色）、中間按鈕是藍
SIG_DIALOG = screen_sigs.sig_str(screen_sigs.NET_DIALOG)
# 登入畫面：登錄鈕橘、註冊鈕藍、面板米色
SIG_LOGIN = screen_sigs.sig_str(screen_sigs.NET_LOGIN)
MSG_BOX = (585, 370, 260, 40)        # 提示視窗訊息文字（OCR 輔助確認，白字深邊）
MSG_KEYS = ('網', '路', '異', '重', '連')
LOGIN_BOX = (460, 380, 520, 130)     # 登入畫面「帳號 / 密碼」標籤（只讀標籤，不讀欄位內容）
SWITCH_BTN = (763, 760)
# 登錄流程（2026-10-10 實測）
LOGIN_BTN = (590, 585)               # 登入畫面橘色「登錄」（唯一允許在登入畫面點的東西）
ACCT_BOX = (700, 900, 400, 425)      # 帳號欄 x0,x1,y0,y1（數深色像素判斷「非空 / 清空了沒」；帳號樣本 93 點、空欄 0 點）
# 帳號核對（accounts.local.json 有本視窗帳號時才用；fixture net5.png 量：欄位 610～970 × 392～432，置中深棕粗字 742～834）
ACCT_OCR = (610, 392, 360, 40)       # 帳號欄 OCR 框（ocr.ps1 -Dark 120，2 / 3 / 4 倍各讀一次，三者一致才算讀得出）
ACCT_OCR_OPTS = ('-Zooms', '2,3,4', '-Dark', '120')
ACCT_FIELD = (930, 411)              # 點帳號欄的位置（欄位右段空白處：游標落在字尾；不點左邊「帳號」標籤、不碰密碼欄 / 鑰匙）
ACCT_CLEAR_N = 40                    # 清空：{END} + {BS}×N 再 {HOME} + {DEL}×N（游標在哪都清得乾淨；帳號最長 32 字）
EMPTY_MAX = 10                       # 深色點 < 10 = 空（同 login_fields_filled；游標細線最多約 9 點）
LOGIN_INPUT_LOCK = clients.SHARED_CACHE / 'login-input.lock'   # 全視窗共用：同一時間只有一個視窗在登入畫面打字（點欄位 → 清空 → 打字 → 核對 → 登錄）
LOGIN_INPUT_STALE = 120              # 鎖超過幾秒沒放 = 持有者死了，接手
LOGIN_INPUT_WAIT = 90                # 最多等別的視窗打完幾秒
PWD_BOX = (690, 880, 484, 502)       # 密碼欄（星號）
ALL_LOGIN_BTN = (740, 640)           # 選擇角色面板「一鍵全登」
# 選擇角色面板：全登鈕橘、面板米色、右上紅 X、角色列棕
SIG_CHARSEL = screen_sigs.sig_str(screen_sigs.NET_CHARSEL)
SWITCH_ALL_BTN = (716, 578)          # 切換角色面板「全部登錄」
LOGIN_TIMEOUT = 120                  # 登錄後等進遊戲的上限（秒）
CARDS_BOX = (560, 280, 450, 230)     # 切換角色面板的角色卡片（讀「單人 / 隊長 / 隊員」）


def _scale_sig(sig: str) -> str:
    """1920×1017 版面：截圖座標 × 2/3（顏色不變）。未實測，只當備援"""
    if layout.resolve() != '1920x1017':
        return sig
    out = []
    for p in sig.split('/'):
        v = p.split(',')
        out.append(','.join([str(round(int(v[0]) * 2 / 3)), str(round(int(v[1]) * 2 / 3))] + v[2:]))
    return '/'.join(out)


# ---- 讀取失敗追蹤（errlog 限頻：同一段連續失敗只記一筆，恢復後補 fix；psa-hud 會顯示 errlog，不能洗版）----
_fail_id: list = []                  # 目前這段連續失敗對應的 errlog id（空 = 沒在失敗中）


def _read_failed(what: str) -> None:
    if not _fail_id:
        _fail_id.append(errlog.add(f'netwatch 讀不到遊戲畫面（{what}：PowerShell 失敗 / 截圖失敗 / 輸出異常），暫不判斷、不點擊',
                                   source='netwatch'))


def _read_ok() -> None:
    if _fail_id:
        i = _fail_id.pop()
        if i is not None:
            errlog.fix(i, '已恢復（下一次讀取成功）')


def _ps(*args: str) -> tuple[int, str]:
    """直接呼叫 gui.ps1，回 (returncode, 輸出)。逾時 / 無法執行 → (-1, '')。
    （walk.gui 只回字串、丟掉 returncode，這裡才分得出 PS 失敗與「沒符合」）"""
    try:
        r = winenv.run_ps('gui.ps1', *args, timeout=PS_TIMEOUT)
    except (OSError, subprocess.SubprocessError):
        return -1, ''
    return r.returncode, (r.stdout.strip() or r.stderr.strip())


def _match(sig: str) -> bool | None:
    """用 waitpix 單次檢查（逾時 0）。三態：True = 全部符合；False = 確定不符合（timeout）；
    None = 讀不到（rc≠0、空輸出、pwfail、其他）— 已重試一次。呼叫端 None 時不點、不宣告成功。"""
    for _ in range(2):
        rc, out = _ps('seq', f'waitpix 0 {_scale_sig(sig)} {TOL}')
        lines = out.splitlines()
        head = lines[-1].split()[0] if rc == 0 and lines and lines[-1].split() else ''
        if head == 'ok':
            _read_ok()
            return True
        if head == 'timeout':
            _read_ok()
            return False
    _read_failed('waitpix')
    return None


def _ocr_lines(box, *opts) -> list:
    """ocr.ps1 的 lines（每行 dict：text / x / y / zoom）；PS 失敗 / 逾時 / 輸出異常 → []"""
    try:
        r = winenv.run_ps('ocr.ps1', *map(str, box), *map(str, opts), timeout=PS_TIMEOUT)
    except (OSError, subprocess.SubprocessError):
        return []
    try:
        d = json.loads((r.stdout.strip().splitlines() or [''])[-1])
    except ValueError:
        return []
    return [l for l in d.get('lines', []) if isinstance(l, dict)] if d.get('ok') else []


def _ocr(box, *opts) -> list:
    return [l.get('text', '') for l in _ocr_lines(box, *opts)]


def hud_ok() -> bool:
    """主畫面 HUD 讀得到（stat.ps1 ok）= 已在遊戲裡"""
    from walk import stat
    s = stat()
    # stat.ps1 在登入畫面也回 ok:true（全空欄位），所以要求讀得到地圖座標或等級，且不是登入畫面
    # _match 讀不到（None）時不確定是不是登入畫面 → 當作 HUD 沒到，不宣告成功
    return bool(s.get('ok') and (s.get('pos') or s.get('level'))) and _match(SIG_LOGIN) is False


def detect() -> str | None:
    """'dialog'（網路異常提示）/ 'login'（登入畫面）/ None。不點任何東西。
    提示視窗：像素特徵符合 → OCR 訊息若讀到文字卻不含 網路異常 相關字，就當成別種提示（不亂點）；OCR 讀不到則信任像素。"""
    if _match(SIG_DIALOG) is True:          # None（讀不到）當「不是對話框」往下判斷
        txt = ''.join(_ocr(MSG_BOX, '-Light', 200, '-Zooms', '2,3'))
        if txt and not any(k in txt for k in MSG_KEYS):
            log(f'netwatch：像素像提示視窗，但訊息是「{txt}」不是網路異常，不處理', act=False)
            return None
        return 'dialog'
    if _match(SIG_LOGIN) is True:
        return 'login'
    return None


# ---------------- 狀態檔 ----------------
def _load() -> dict:
    try:
        return json.loads(STATE.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return {'fails': 0}


def _save(d: dict) -> None:
    try:
        CACHE.mkdir(parents=True, exist_ok=True)
        STATE.write_text(json.dumps(d), encoding='utf-8')
    except OSError:
        pass


def _take(lock: Path, stale: int) -> bool:
    """O_EXCL 建鎖檔；超過 stale 秒的舊鎖直接接手"""
    lock.parent.mkdir(parents=True, exist_ok=True)
    for _ in range(2):
        try:
            fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.write(fd, f'{os.getpid()} {int(time.time())}'.encode())
            os.close(fd)
            return True
        except FileExistsError:
            try:
                if time.time() - lock.stat().st_mtime > stale:
                    lock.unlink()
                    continue
            except OSError:
                pass
            return False
    return False


def _release(lock: Path) -> None:
    try:
        lock.unlink()
    except OSError:
        pass


def _dark_count(box) -> int | None:
    """欄位框內的深棕色（文字 / 星號）像素數；只看有沒有字，不讀內容。
    PS 失敗或回傳點數少於預期（讀不完整）→ 重試一次，仍失敗回 None（不是 0，0 代表「確定是空的」）"""
    x0, x1, y0, y1 = box
    coords = [(x, y) for y in range(y0, y1, 3) for x in range(x0, x1, 3)]
    pts = ' '.join(f'{x},{y}' for x, y in coords)
    for _ in range(2):
        rc, out = _ps('pixel', pts)
        vals = []
        for p in out.split():
            try:
                r, g, _b = (int(v) for v in p.split(','))
            except ValueError:
                continue
            vals.append((r, g))
        if rc == 0 and len(vals) == len(coords):
            _read_ok()
            return sum(1 for r, g in vals if r < 130 and g < 90)
    _read_failed('pixel')
    return None


def login_fields_filled() -> bool | None:
    """帳號、密碼欄都有內容（遊戲自動帶入）。True = 都有；False = 確定有一欄是空的（絕不自己填）；
    None = 讀不到（不能當成「空」halt，由 relogin 重試、有次數上限）"""
    a = _dark_count(ACCT_BOX)
    if a is None:
        return None
    if a < 10:
        return False
    p = _dark_count(PWD_BOX)
    if p is None:
        return None
    return p >= 10


def halt(reason: str, src: str) -> dict:
    """停手：寫 halt 檔、errlog、大聲警告。密碼欄絕不碰"""
    try:
        CACHE.mkdir(parents=True, exist_ok=True)
        HALT.write_text(f'{time.strftime("%Y-%m-%d %H:%M:%S")} {reason}\n', encoding='utf-8')
    except OSError:
        pass
    errlog.add(f'斷線重登停手：{reason}（{src}）', source='netwatch')
    actlog.add('netwatch', f'HALT {reason}')
    bar = '!' * 64
    print(f'\n{bar}\n!!! 遊戲回到登入畫面 / 需要人類登入：{reason}\n'
          f'!!! 所有自動化已停止（退出碼 {EXIT_HALT}）。請使用者自己登入並進入遊戲（鐵則 2：AI 絕不碰密碼欄；帳號欄只在本機帳號對照核對時重打）。\n'
          f'!!! 人類登入後恢復：確認 5 人同隊（/psa-quick-team）、原地遇敵開著，再重新啟動腳本。\n{bar}\n', flush=True)
    return {'status': 'halt', 'reason': reason}


# ---------------- 恢復 ----------------
CARD_BADGES = [(450, 272, 70, 32), (730, 272, 70, 32), (450, 357, 70, 32), (730, 357, 70, 32), (450, 442, 70, 32)]


def team_report() -> dict:
    """開切換角色面板存圖，逐張卡片 OCR 隊伍標籤（整個區域一起讀很不準，單一標籤才準）：
    長 = 隊長、員 = 隊員、單 / 人 = 單人，讀不出來算 unknown。只回報，不組隊。"""
    shot = CACHE / 'netwatch_team.png'
    gui('seq', f'key {{ESC}}; wait 300; click {SWITCH_BTN[0]} {SWITCH_BTN[1]}; wait 900; shot {shot}')
    n = {'leader': 0, 'member': 0, 'solo': 0, 'unknown': 0}
    for box in CARD_BADGES:
        txt = ''.join(_ocr(box, '-Zooms', '2,3,4'))
        if '長' in txt:
            n['leader'] += 1
        elif '員' in txt:
            n['member'] += 1
        elif '單' in txt or '人' in txt:
            n['solo'] += 1
        else:
            n['unknown'] += 1
    gui('key', '{ESC}')
    n['shot'] = str(shot)
    return n


def fix_team(t: dict) -> dict:
    """隊伍不全：先「全部登錄」讓離線角色上線；若全員單人再 team.form 快速組隊（P8：取代舊的盲點座標序列，
    form 會逐步驗證、組好才按、最後確認，失敗不亂點）。回傳新的 team_report"""
    log('netwatch：隊伍不全，點「全部登錄」並視情況快速組隊')
    gui('seq', f'key {{ESC}}; wait 300; click {SWITCH_BTN[0]} {SWITCH_BTN[1]}; wait 900; '
               f'click {SWITCH_ALL_BTN[0]} {SWITCH_ALL_BTN[1]}; wait 4000; key {{ESC}}', note='全部登錄')
    t = team_report()
    if t['solo'] >= 4 and t['leader'] + t['member'] == 0:
        try:
            import team as team_mod            # 延後 import：team → uikit → netwatch（避免循環）
            rc = team_mod.form()
        except SystemExit:
            raise
        except Exception as e:
            rc = f'例外 {e}'
        log(f'netwatch：team.form 退出碼 {rc}')
        if rc != 0:
            errlog.add(f'netwatch 重登後 team.form 失敗（{rc}）', source='netwatch')
        t = team_report()
    return t


def _forget_char() -> None:
    """重登後當前角色未知（實測重登後當前會變 DKBO5）→ 清 current-char.json；之後 char.ensure 現場讀切換面板"""
    try:
        import charstate
        charstate.clear()
    except Exception:
        pass


def run_grind_ensure(src: str) -> dict:
    """重登 / 人類登入回來後自動跑 grind.ensure（重設 5 人快速 + 自動戰鬥、隊長當前、開遇敵、確認 EXP）。
    只跑一次：失敗只記 errlog + 印警告，不重試、不 halt（SystemExit 停手訊號照常往外丟）。
    grind 已在跑（巢狀）→ 略過；quest 的 battle.lock 有效 → grind 自己回 8（不搶畫面、不動遇敵）。"""
    try:
        import grind
    except Exception as e:
        return {'rc': None, 'error': f'import grind 失敗：{e}'}
    if getattr(grind, 'ACTIVE', False):
        return {'rc': None, 'skipped': 'grind 執行中'}
    log('netwatch：重登後自動跑 grind.py ensure（約 25 秒）')
    try:
        rc = grind.run('ensure', ignore_watchers=True)
    except SystemExit:
        raise
    except Exception as e:
        rc = None
        errlog.add(f'netwatch 重登後 grind.ensure 例外：{e}', source='netwatch')
        print(f'!!! 重登後 grind ensure 例外：{e}；請手動跑 grind.py ensure', flush=True)
        return {'rc': None, 'error': str(e)}
    if rc != 0:
        errlog.add(f'netwatch 重登後 grind.ensure 失敗（退出碼 {rc}）', source='netwatch')
        print(f'!!! 重登後 grind ensure 失敗（退出碼 {rc}，見 grind.py 檔頭 / tools/.cache/grind.json）；請手動處理，netwatch 不重試', flush=True)
    return {'rc': rc}


def recover(src: str, encounter: bool = True, team: bool = True, grind_ensure: bool = False) -> dict:
    """人類登入 / 重連完成後：檢查隊伍、（grind_ensure）跑 grind.ensure、確認原地遇敵。回傳摘要（也會 log）。
    grind_ensure（只有重登 / 人類登入回來時開）：重登必定重設快速戰鬥 → 自動跑 grind.ensure 一次（它自己會處理隊長 / 遇敵）"""
    info: dict = {}
    if team:
        try:
            info['team'] = team_report()
            t = info['team']
            log(f'netwatch：隊伍檢查 隊長 {t["leader"]} / 隊員 {t["member"]} / 單人 {t["solo"]} / 讀不出 {t["unknown"]}（{t["shot"]}）')
            if t['solo']:
                t = info['team'] = fix_team(t)
            if t['solo'] or t['leader'] + t['member'] + t['unknown'] < 5:
                print('!!! 隊伍可能散了：請看截圖確認，不同隊就照 /psa-quick-team 組回（組隊前先確認真的散了）', flush=True)
        except Exception as e:
            info['team'] = f'error {e}'
    if grind_ensure:
        info['grind'] = run_grind_ensure(src)
        if info['grind'].get('rc') == 0:
            encounter = False                       # ensure 已確認遇敵開著且有 EXP
    if encounter:
        try:
            import heal
            if not heal.encounter_on():
                log('netwatch：原地遇敵沒開，重新開啟')
                heal.set_encounter(True)
                info['encounter'] = 'reopened'
            else:
                info['encounter'] = 'on'
        except Exception as e:      # 不讓恢復流程拖垮呼叫端
            info['encounter'] = f'error {e}'
    return info


MULTI_HALT = '多視窗不自動按登錄'      # halt 理由開頭（relogin.py 擋重登也用）


def auto_login_check(procs=None) -> tuple:
    """多視窗不自動按「登錄」（2026-10-15 使用者決定：遊戲記住的帳號是所有視窗共用的，自動登錄可能登錯帳號、互踢）。
    → ('ok', '') 單一視窗、可以照舊自動登錄；('block', 理由) 非主視窗 / 主視窗但還有別的 PrimalSA* 在跑；
    ('unknown', 理由) 主視窗但查不到程序清單（呼叫端當讀取失敗：本輪不點、連續幾輪才 halt）。procs 給測試用"""
    if not clients.is_default():
        return 'block', f'{MULTI_HALT}：非主視窗 {clients.name()} 只偵測斷線、不按登錄（記住的帳號是共用的，可能登錯帳號互踢），請人登入'
    others = clients.others_running(procs=procs)
    if others is None:
        return 'unknown', '查不到正在執行的遊戲程序清單（判斷不了是不是多視窗）'
    if others:
        return 'block', f'{MULTI_HALT}：還有其他視窗在跑（{"、".join(others)}），記住的帳號是共用的，可能登錯帳號互踢，請人登入'
    return 'ok', ''


# ---------------- 帳號核對（accounts.local.json；2026-10-15，未實機）----------------
VERDICT_TXT = {'self': '符合', 'other': '不符', 'unreadable': '讀不出'}


def login_mode(procs=None) -> tuple:
    """斷線重登要走哪一套 → (how, why, 帳號)：
    ('account', '', 帳號)：本機設定檔有本視窗帳號 → 帳號核對（單 / 多視窗都一樣，不看程序清單）；
    否則 auto_login_check() 的 ('ok' | 'block' | 'unknown', 理由, '')（舊行為逐字不變）。理由不含帳號名"""
    st, acct = accounts.for_client()
    if st == 'ok':
        return 'account', '', acct
    if st == 'invalid':
        log(f'netwatch：帳號對照設定檔格式錯（{acct}），照舊規則', act=False)
    how, why = auto_login_check(procs)
    return how, why, ''


def read_account(mine: str, tries: int = 2) -> str:
    """OCR 帳號欄 → 'self' / 'other' / 'unreadable'（accounts.classify：2 / 3 / 4 倍各自的整欄文字一致才算讀得出）。
    讀不出時重讀一次。只回判定，**讀到的字不回傳、不 log**"""
    v = 'unreadable'
    for _ in range(tries):
        by_zoom: dict = {}
        for l in _ocr_lines(ACCT_OCR, *ACCT_OCR_OPTS):
            by_zoom.setdefault(l.get('zoom'), []).append(l)
        texts = [''.join(str(l.get('text', '')) for l in sorted(ls, key=lambda l: l.get('x', 0))) for ls in by_zoom.values()]
        v = accounts.classify(texts, mine)
        if v != 'unreadable':
            return v
        time.sleep(0.5)
    return v


def _log_verdict(v: str, stage: str = '') -> None:
    msg = f'帳號欄核對{stage}：{VERDICT_TXT.get(v, v)}'
    log(f'netwatch：{msg}')                 # walk.log 會寫 actions.log（只有判定，沒有帳號名）


def _take_wait(lock: Path, stale: int, wait: float) -> bool:
    """等鎖（每秒試一次）最多 wait 秒"""
    end = time.time() + wait
    while True:
        if _take(lock, stale):
            return True
        if time.time() >= end:
            return False
        time.sleep(1)


def retype_account(mine: str) -> str:
    """登入畫面帳號欄是別的帳號：點帳號欄 → 清空 → 確認空 → 只打本視窗帳號 → 再讀核對。回 '' = 成功（帳號欄 = 本視窗帳號），
    否則回 halt 理由（不含帳號名）。呼叫端必須已拿 LOGIN_INPUT_LOCK。密碼欄不點、不清、不打；每步前確認還是登入畫面、密碼欄還有字"""
    def still_login() -> str:
        if _match(SIG_LOGIN) is not True:
            return '畫面不是 / 讀不到登入畫面'
        p = _dark_count(PWD_BOX)
        if p is None:
            return '讀不到密碼欄'
        if p < EMPTY_MAX:
            return '密碼欄變成空的'
        return ''
    why = still_login()
    if why:
        return f'重打帳號前{why}，不動'
    try:
        gui('click', str(ACCT_FIELD[0]), str(ACCT_FIELD[1]), note='點帳號欄（重打帳號）')
        time.sleep(0.4)
        gui('key', '{END}' + '{BS}' * ACCT_CLEAR_N + '{HOME}' + '{DEL}' * ACCT_CLEAR_N, note='清空帳號欄')
        time.sleep(0.4)
        d = _dark_count(ACCT_BOX)
        if d is None:
            return '清空後讀不到帳號欄，不打字'
        if d >= EMPTY_MAX:
            return '帳號欄清不掉（清空後仍有字），不打字'
        why = still_login()
        if why:
            return f'清空帳號欄後{why}，不打字'
        gui('typeq', mine, note='重打帳號欄')
        time.sleep(0.6)
    except Exception as e:          # noqa: BLE001  例外訊息可能帶指令參數（帳號）→ 只留型別
        return f'重打帳號時出錯（{type(e).__name__}），停手'
    v = read_account(mine)
    _log_verdict(v, '（重打後）')
    if v != 'self':
        return f'重打帳號後核對{VERDICT_TXT.get(v, v)}，不按登錄'
    why = still_login()
    if why:
        return f'重打帳號後{why}，不按登錄'
    return ''


def relogin(src: str, grind_ensure: bool = True, encounter: bool = True, team: bool = True) -> dict:
    """登入畫面 → 檢查帳密欄有內容 → 點「登錄」→ 處理選擇角色 / 載入 → 回到遊戲 → recover。
    失敗規則：欄位空 / 出現提示視窗（密碼錯誤、封停、維護、驗證）/ 看不懂的畫面逾時 / 連續 3 次 → halt（不重試）"""
    if not _take(ACT_LOCK, 300):
        return {'status': 'ok', 'busy': True}
    try:
        st = _load()
        if st.get('login_fails', 0) >= MAX_FAILS:
            return halt(f'連續 {MAX_FAILS} 次登錄失敗', src) | {'status': 'fatal'}
        how, why, acct = login_mode()
        if how == 'block':
            return halt(why, src)
        if how == 'unknown':
            # 跟讀不到帳密欄同一套：本輪不點登錄，連續 READ_FAIL_MAX 輪才 halt
            st['read_fails'] = st.get('read_fails', 0) + 1
            _save(st)
            if st['read_fails'] >= READ_FAIL_MAX:
                return halt(f'連續 {READ_FAIL_MAX} 輪{why}，不自動登錄', src)
            log(f'netwatch：{why}（{st["read_fails"]}/{READ_FAIL_MAX}），本輪不點登錄')
            return {'status': 'ok', 'failed': True}
        filled = login_fields_filled()
        if filled is None:
            # 讀取失敗：不點登錄、不以「欄位空」halt；下輪再試，連續 READ_FAIL_MAX 輪讀不到才 halt
            st['read_fails'] = st.get('read_fails', 0) + 1
            _save(st)
            if st['read_fails'] >= READ_FAIL_MAX:
                return halt(f'連續 {READ_FAIL_MAX} 輪讀不到帳密欄 / 遊戲畫面（不是欄位空）', src)
            log(f'netwatch：登入畫面讀不到帳密欄（{st["read_fails"]}/{READ_FAIL_MAX}），本輪不點登錄')
            return {'status': 'ok', 'failed': True}
        if st.get('read_fails'):
            st['read_fails'] = 0
            _save(st)
        if not filled:
            return halt('登入畫面的帳號 / 密碼欄是空的（遊戲沒自動帶入），不自己填', src)
        held = False                     # 帳號重打時拿的全視窗登入輸入鎖（按完登錄就放）
        try:
            if how == 'account':
                v = read_account(acct)
                _log_verdict(v)
                if v == 'unreadable':
                    return halt('帳號欄讀不出（OCR 各倍數不一致 / 讀不到），不自動登錄', src)
                if v == 'other':
                    if not _take_wait(LOGIN_INPUT_LOCK, LOGIN_INPUT_STALE, LOGIN_INPUT_WAIT):
                        return halt(f'別的視窗佔著登入輸入鎖超過 {LOGIN_INPUT_WAIT} 秒，不重打帳號', src)
                    held = True
                    why = retype_account(acct)
                    if why:
                        return halt(why, src)
            i = errlog.add('斷線回到登入畫面，自動按「登錄」重新登入（使用者授權'
                           + ('；帳號欄核對符合' if how == 'account' else '') + '）', source=src)
            log('netwatch：登入畫面，' + ('帳號欄核對符合' if how == 'account' else '帳密欄已有內容') + ' → 按登錄')
            gui('click', str(LOGIN_BTN[0]), str(LOGIN_BTN[1]), note='按登錄')
        finally:
            if held:
                _release(LOGIN_INPUT_LOCK)
        deadline = time.time() + LOGIN_TIMEOUT
        picked = 0                       # 一鍵全登最多點 2 次
        t0 = time.time()
        while time.time() < deadline:
            time.sleep(2)
            if hud_ok():
                st['login_fails'] = 0
                st['fails'] = 0
                _save(st)
                _release(HALT)
                errlog.fix(i, '登錄 → 一鍵全登 → 進遊戲成功，已做恢復檢查（netwatch.relogin）')
                actlog.add('netwatch', '自動登錄成功')
                log(f'netwatch：登錄成功，{int(time.time() - t0)} 秒回到遊戲')
                _forget_char()
                time.sleep(2)
                return {'status': 'reconnected', 'relogin': True, 'recover': recover(src, encounter, team, grind_ensure=grind_ensure)}
            if _match(SIG_CHARSEL) is True:
                if picked >= 2:
                    break
                picked += 1
                log('netwatch：選擇角色面板 → 一鍵全登')
                gui('click', str(ALL_LOGIN_BTN[0]), str(ALL_LOGIN_BTN[1]), note='一鍵全登')
                continue
            if _match(SIG_DIALOG) is True:
                # 登錄後的提示視窗（密碼錯誤 / 封停 / 維護 / 驗證…）：不點、不重試
                return halt('登錄後出現提示視窗（可能是密碼錯誤 / 封停 / 維護 / 驗證），不處理', src)
        st['login_fails'] = st.get('login_fails', 0) + 1
        _save(st)
        errlog.fix(i, f'登錄後 {LOGIN_TIMEOUT} 秒沒進遊戲（失敗 {st["login_fails"]}/{MAX_FAILS}），停手')
        return halt(f'登錄後 {LOGIN_TIMEOUT} 秒沒進遊戲 / 畫面不明（第 {st["login_fails"]} 次）', src)
    finally:
        _release(ACT_LOCK)


# ---------------- 主流程 ----------------
def check_and_reconnect(shot=None, src: str = 'netwatch', encounter: bool = True, team: bool = True, grind_ensure: bool = True) -> dict:
    """檢查「網路異常」提示 / 登入畫面；有就處理。shot 參數保留相容（目前自己取樣，不用外部截圖）。
    回傳 {'status': 'ok'|'reconnected'|'halt'|'fatal'|'verify', ...}；status 為 halt / fatal / verify 時呼叫端必須停手。
    verify = 全視窗驗證停手旗標（verifyhalt.py，多視窗時任一視窗出現驗證視窗）：什麼都不點，連重連都不做"""
    import verifyhalt
    vh = verifyhalt.active()
    if vh:
        return {'status': 'verify', 'reason': verifyhalt.message(vh)}
    if HALT.exists():
        if hud_ok():                         # 人類已登入回來
            _release(HALT)
            _save({'fails': 0})
            log('netwatch：偵測到已重新登入（HUD 回來了），清除 halt，做恢復檢查')
            actlog.add('netwatch', '人類登入後恢復')
            _forget_char()
            return {'status': 'reconnected', 'relogin': True, 'recover': recover(src, encounter, team, grind_ensure=grind_ensure)}
        return {'status': 'halt', 'reason': '已停手等使用者處理（netwatch.halt 存在；處理完刪掉該檔）'}
    kind = detect()
    if kind is None:
        return {'status': 'ok'}
    if kind == 'login':
        return relogin(src, grind_ensure=grind_ensure)
    if not _take(ACT_LOCK, 180):
        return {'status': 'ok', 'busy': True}      # 別的腳本正在處理
    try:
        st = _load()
        i = errlog.add('網路斷線：遊戲跳出「網路異常，是否重連?」', source=src)
        log('netwatch：偵測到「網路異常，是否重連?」，點確定')
        gui('click', str(CONFIRM[0]), str(CONFIRM[1]), note='網路異常→確定')
        deadline = time.time() + 45
        while time.time() < deadline:
            time.sleep(2)
            if _match(SIG_LOGIN) is True:
                _release(ACT_LOCK)                  # relogin 自己會拿鎖
                return relogin(src, grind_ensure=grind_ensure)
            if hud_ok() and _match(SIG_DIALOG) is False:     # 讀不到（None）不宣告成功
                st['fails'] = 0
                _save(st)
                errlog.fix(i, '點確定後回到遊戲，已做恢復檢查（netwatch.py）')
                log('netwatch：重連成功，回到遊戲')
                return {'status': 'reconnected', 'recover': recover(src, encounter, team)}
            if _match(SIG_DIALOG) is True:
                gui('click', str(CONFIRM[0]), str(CONFIRM[1]), note='網路異常→確定（再按）')
        st['fails'] = st.get('fails', 0) + 1
        _save(st)
        log(f'netwatch：點確定後 45 秒沒回到遊戲（連續失敗 {st["fails"]}/{MAX_FAILS}）')
        if st['fails'] >= MAX_FAILS:
            halt(f'連續 {MAX_FAILS} 次重連失敗', src)
            return {'status': 'fatal', 'reason': f'連續 {MAX_FAILS} 次重連失敗'}
        return {'status': 'ok', 'failed': True}
    finally:
        _release(ACT_LOCK)


def guard(src: str, **kw) -> dict:
    """給腳本迴圈用：要停手（halt / fatal / verify）就直接 sys.exit(10 / 11 / 9)（會跑 finally），重連成功回傳 dict（呼叫端依 'reconnected' 重設自己的狀態）"""
    r = check_and_reconnect(src=src, **kw)
    if r['status'] == 'verify':
        print(f'{src}：{r["reason"]}', file=sys.stderr, flush=True)
        sys.exit(EXIT_VERIFY)
    if r['status'] == 'halt':
        sys.exit(EXIT_HALT)
    if r['status'] == 'fatal':
        sys.exit(EXIT_FATAL)
    return r


def main() -> int:
    ap = argparse.ArgumentParser(description='網路異常自動重連 / 登入畫面停手')
    ap.add_argument('--once', action='store_true')
    ap.add_argument('--watch', action='store_true', help='常駐；沒有其他腳本在跑時用')
    ap.add_argument('--interval', type=int, default=10)
    ap.add_argument('--status', action='store_true')
    ap.add_argument('--no-team', action='store_true', help='恢復時不檢查隊伍')
    ap.add_argument('--no-encounter', action='store_true', help='恢復時不管原地遇敵')
    ap.add_argument('--no-grind', action='store_true', help='重登後不自動跑 grind.py ensure')
    a = ap.parse_args()
    if a.status:
        print('halt:', HALT.read_text(encoding='utf-8').strip() if HALT.exists() else '無', '| 狀態:', _load())
        return 0
    if layout.current() != '2880x1659':
        log(f'netwatch 只量過 2880×1659，目前 {layout.current()}')
        return 2
    kw = {'src': 'netwatch', 'team': not a.no_team, 'encounter': not a.no_encounter, 'grind_ensure': not a.no_grind}
    if not a.watch:
        r = check_and_reconnect(**kw)
        print(json.dumps(r, ensure_ascii=False, default=str))
        return {'halt': EXIT_HALT, 'fatal': EXIT_FATAL, 'verify': EXIT_VERIFY}.get(r['status'], 0)
    if not _take(WATCH_LOCK, 120):
        log('已有另一支 netwatch --watch 在跑（tools/.cache/netwatch.lock）')
        return 3
    log(f'netwatch 常駐：每 {a.interval} 秒檢查網路異常提示（其他腳本在跑時它們自己會檢查，這支只在單獨掛機時用）')
    try:
        while True:
            try:
                WATCH_LOCK.touch()
            except OSError:
                pass
            r = check_and_reconnect(**kw)
            if r['status'] == 'verify':
                log(r['reason'])
                return EXIT_VERIFY
            if r['status'] in ('halt', 'fatal'):
                return EXIT_HALT if r['status'] == 'halt' else EXIT_FATAL   # 人類登入後重新啟動即可（halt 檔會自動清）
            time.sleep(a.interval)
    except KeyboardInterrupt:
        log('netwatch Ctrl+C，結束')
    finally:
        _release(WATCH_LOCK)
    return 0


if __name__ == '__main__':
    sys.exit(main())
