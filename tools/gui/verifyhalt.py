#!/usr/bin/env python3
"""每視窗驗證停手旗標 verify-halt.json（只用標準函式庫；多視窗第 3a 步，2026-10-15 使用者改成「各自視窗停手」）。

鐵則 5：出現答題 / 驗證視窗要立刻停手。**什麼時候設（使用者 2026-10-16 定案：正面辨識；2026-10-18 拿掉 3 分鐘兜底）**：
  - 答題 / 驗證介面正面命中（screen_sigs.quiz_screen）：watch 第一輪、uikit.preflight 第一次 unknown、quest.py 立刻 trip
  - 其他不認得的畫面一律**不設**：腳本照樣自己停（uikit.trip_verify / uikit.fail(9) 會現場再確認答題介面，沒認出就不 trip）；
    網路異常窗（screen_sigs.net_lost）交給 netwatch，不設
多視窗時某個視窗出事 → 只寫**那個視窗自己的**旗標，只有那個視窗的常駐程式 / 腳本停，其他視窗照常：
  - 路徑 = clients.cache_dir() / verify-halt.json：主視窗 tools/.cache/verify-halt.json（原路徑），
    其他 tools/.cache/clients/<程序名>/verify-halt.json；trip / active / clear 都只看本視窗（PSA_CLIENT）
  - uikit.preflight（每支腳本開跑）→ 9；uikit.watch_preflight_ok → False
  - netwatch.guard / check_and_reconnect（quest / follow / heal --watch / petwatch / grind 迴圈每輪都叫）→ sys.exit(9)
  - watchstate.VerifyGuard.check（heal --watch / petwatch）→ 'timeout'（呼叫端停止）
  - follow 每輪開頭 → 9
  - gui.ps1 的 click / dclick / drag / key / typeq（psawin.ps1 Test-PsaVerifyHalt，依請求的 PSA_CLIENT）→ 不送輸入、exit 9（最後一道保險）
  - watch.py 不停（零輸入），state.flags.verify_halt = True
**自動清（使用者 2026-10-16：偵測保留、旗標自動清；當天 7 次以上誤設〔刪除確認窗、道具說明彈窗、手動開的面板、新視窗剛開〕）**：
  旗標存在時，本視窗畫面連續 AUTO_CLEAR_S（5）秒、至少 AUTO_CLEAR_N（6）次讀圖都是「已知正常畫面」
  （screen_sigs.normal_screen：主畫面 idle / 自動跑路 walking / 戰鬥 battle / 認得的面板 panel〔沒有提示視窗等附註〕，
  或面板上疊已知彈窗 popup_*，或登入 / 選角 / 載入 / 網路異常窗〔2026-10-16 加：netwatch 那一層，否則斷線會死結〕）→ 自動清掉，寫 actions.log、quest-events.log「verifyhalt 自動清除（畫面已恢復：<狀態>）」、
  把設旗標時那筆 errlog 補 fix（psa-hud 錯誤表看得到）。判斷邏輯 = AutoClear（一份，兩個呼叫端共用）：
  - watch.py（常駐、零輸入、每 0.5 s 讀一次）每輪餵一次 → 主要的清除者
  - watch 沒在跑的視窗：uikit.preflight 遇到旗標時自己現場連讀 6 次（間隔 1 s）判斷，通過就清掉繼續、否則照舊 9
  **絕不清**：任何一次讀到 unknown / 答題介面 / 對話框（驗證視窗是 NpcScript，可能長得像對話框）/ 獲得物品 / 選擇對象 /
  全黑 / 主畫面帶提示視窗 / 最小化 / 讀不到 → 計時歸零；讀圖時間早於旗標時間的不算；`set` 手動設的（src=manual）不自動清。
  手動清照舊：`uv run --no-project python tools/gui/verifyhalt.py clear <程序名>`。

只在「多視窗情境」才寫（clients.multi_window：非主視窗，或主視窗時還有別的 PrimalSA* 在跑；查不到程序清單當作多視窗）。
單一視窗時不寫，行為與改版前完全相同（那個腳本本來就停了，使用者處理完重跑即可；只有自己 = 各自停手）。

舊格式（改版前全部視窗共用一份 tools/.cache/verify-halt.json，非主視窗寫的內含 client 欄）：
  內容 client 不是主視窗 → 歸屬那個視窗（主視窗不受影響；那個視窗照樣停），`clear <程序名>` / 之後寫旗標時搬到該視窗資料夾。

  import verifyhalt
  verifyhalt.trip('答題介面正面命中', src='grind')     # 多視窗才寫（本視窗）；回 True = 有寫 / 已經有（只在上面兩種情況呼叫）
  verifyhalt.active()                                  # → dict（本視窗旗標內容）或 None
  ac = verifyhalt.AutoClear(); ac.feed(flag, normal, now, read_wall)   # True = 該清了 → verifyhalt.auto_clear(flag, 狀態文字, src)
命令列：
  python tools/gui/verifyhalt.py [status [程序名|all]]   列出各視窗旗標（退出碼 0 = 都沒有、9 = 有）；不給 = all
  python tools/gui/verifyhalt.py clear [程序名|all]      手動清除（畫面恢復正常會自動清，這是備用）；不給 = 本視窗（PSA_CLIENT，不設 = PrimalSA）
  python tools/gui/verifyhalt.py set 原因                手動設本視窗（PSA_CLIENT）的旗標（不會自動清）
"""
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import clients  # noqa: E402
import logpaths  # noqa: E402

NAME = 'verify-halt.json'
EXIT_VERIFY = 9                                                  # = uikit.EXIT_UNKNOWN_SCREEN
AUTO_CLEAR_S = 5.0               # 自動清：已知正常畫面要連續這麼久（使用者 2026-10-16）
AUTO_CLEAR_N = 6                 # 而且至少這麼多次讀圖（watch 降頻到 2～4 s 一輪時，時間會拉長到 6 次為止）
MANUAL_SRC = 'manual'            # `verifyhalt.py set` 手動設的旗標：不自動清


def _base() -> Path:
    """旗標的根資料夾：平常 tools/.cache；離線測試（PSA_LOG_DIR，logpaths 同一個變數）改到暫存資料夾，底下一樣分 clients/<程序名>"""
    d = os.environ.get('PSA_LOG_DIR')
    return Path(d) if d else clients.SHARED_CACHE


def path(n: str | None = None) -> Path:
    """某個視窗（不給 = 本視窗 PSA_CLIENT）的旗標路徑：主視窗 <base>/verify-halt.json；其他 <base>/clients/<程序名>/verify-halt.json
    （與 clients.cache_dir 同規則；這裡不建資料夾，write 時才建）"""
    n = clients.name() if n is None else clients.normalize(n)
    if clients.is_default(n):
        return _base() / NAME
    return _base() / 'clients' / clients.dir_name(n) / NAME


FILE = path()                    # 本程序（PSA_CLIENT）的旗標；路徑快照測試用，程式內一律呼叫 path()


def _read(p: Path) -> dict | None:
    """存在 → 內容 dict（壞檔也算存在，回 {'reason': '（旗標檔讀不懂）'}）；不存在 None"""
    try:
        raw = p.read_text(encoding='utf-8')
    except FileNotFoundError:
        return None
    except OSError:
        return {'reason': '（旗標檔讀不到）'}
    try:
        d = json.loads(raw)
        return d if isinstance(d, dict) else {'reason': '（旗標檔讀不懂）'}
    except ValueError:
        return {'reason': '（旗標檔讀不懂）'}


def legacy_owner(d: dict | None) -> str | None:
    """主視窗路徑上的旗標若是舊格式、由別的視窗寫的（client 欄不是主視窗）→ 那個視窗名稱；否則 None"""
    if not d:
        return None
    c = d.get('client')
    if not isinstance(c, str) or not c.strip() or clients.is_default(c):
        return None
    return clients.normalize(c)


def active(p=None, client: str | None = None) -> dict | None:
    """本視窗（或 client 指定的視窗）的旗標內容；沒有 None。p 給路徑 = 直接讀那個檔（測試 / 舊呼叫相容）。
    主視窗路徑上的舊共用旗標：client 欄是別的視窗 → 不算主視窗的，算那個視窗的（回傳時帶 legacy=True）"""
    if p is not None:
        return _read(Path(p))
    n = clients.name() if client is None else clients.normalize(client)
    main = _read(path(clients.DEFAULT))
    owner = legacy_owner(main)
    if clients.is_default(n):
        return None if owner else main
    own = _read(path(n))
    if own:
        return own
    if owner and owner.lower() == n.lower():
        return dict(main, legacy=True)
    return None


def describe(d: dict | None) -> str:
    if not d:
        return '無'
    t = d.get('ts')
    when = time.strftime('%m-%d %H:%M:%S', time.localtime(t)) if isinstance(t, (int, float)) else '?'
    tail = '（舊共用旗標檔）' if d.get('legacy') else ''
    return f'{when} {d.get("client", "?")} {d.get("src", "?")}：{d.get("reason", "")}{tail}'


def clear_cmd(n: str | None = None) -> str:
    n = clients.name() if n is None else clients.normalize(n)
    return f'uv run --no-project python tools/gui/verifyhalt.py clear {n}'


def message(d: dict | None, client: str | None = None) -> str:
    """給腳本印的停手訊息（只停這個視窗）"""
    n = clients.name() if client is None else clients.normalize(client)
    auto = ('手動設的旗標不會自動清' if (d or {}).get('src') == MANUAL_SRC
            else f'畫面回到已知正常狀態穩定 {int(AUTO_CLEAR_S)} 秒會自動清（watch / 下次 preflight）')
    return (f'本視窗（{n}）驗證停手旗標存在（{describe(d)}）→ 不動作（鐵則 5；其他視窗不受影響）；'
            f'{auto}；手動清：{clear_cmd(n)}')


def migrate_legacy() -> str | None:
    """主視窗路徑上的舊共用旗標（別的視窗寫的）搬到那個視窗自己的資料夾；那邊已有就只刪舊檔。回搬給誰（沒有舊檔 None）"""
    mp = path(clients.DEFAULT)
    owner = legacy_owner(_read(mp))
    if not owner:
        return None
    dst = path(owner)
    try:
        dst.parent.mkdir(parents=True, exist_ok=True)
        if dst.exists():
            mp.unlink()
        else:
            os.replace(mp, dst)
    except OSError:
        return None
    return owner


def write(reason: str, src: str = '', p=None) -> bool:
    """無條件寫本視窗旗標（已存在就保留第一筆，不覆蓋）；寫入失敗回 False"""
    n = clients.name()
    if p is None:
        migrate_legacy()                         # 主視窗路徑上若躺著別的視窗的舊旗標，先搬走，免得主視窗以為自己已停手
        p = path(n)
    p = Path(p)
    if p.exists():
        return True
    eid = None
    try:                   # 先寫 errlog 拿 id 存進旗標：自動清時補 fix（psa-hud 錯誤表顯示已恢復）
        import errlog
        eid = errlog.add(f'驗證停手（只停 {n}）：{reason}（{src}）；這個視窗的腳本會停、其他視窗照常；'
                         + ('手動設的不會自動清' if src == MANUAL_SRC else f'畫面恢復正常穩定 {int(AUTO_CLEAR_S)} 秒自動清')
                         + f'，或手動 verifyhalt.py clear {n}', source=src or 'verifyhalt')
    except Exception:      # noqa: BLE001  紀錄失敗不影響停手
        pass
    d = {'ts': time.time(), 'client': n, 'src': src, 'reason': str(reason)[:300], 'pid': os.getpid()}
    if eid is not None:
        d['err_id'] = eid
    tmp = p.with_name(p.name + f'.{os.getpid()}.tmp')
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp.write_text(json.dumps(d, ensure_ascii=False), encoding='utf-8')
        os.replace(tmp, p)
    except OSError:
        return False
    try:
        import actlog
        actlog.add('verifyhalt', f'SET {src}：{reason}')
    except Exception:      # noqa: BLE001
        pass
    print(f'!!! 驗證停手旗標已設（{n} {src}：{reason}）；只停這個視窗的腳本，其他視窗照常（鐵則 5）', file=sys.stderr, flush=True)
    return True


def trip(reason: str, src: str = '', multi=None, p=None) -> bool:
    """偵測到驗證 / 答題視窗時呼叫：多視窗情境才寫本視窗旗標（multi 可直接給，測試用；None = clients.multi_window()）。
    回 True = 有寫（或本來就有）；False = 單一視窗不寫 / 寫入失敗。永不丟例外（停手流程不能被它拖垮）"""
    try:
        if (_read(Path(p)) if p is not None else active()) is not None:
            return True
        if not (clients.multi_window() if multi is None else multi):
            return False
        return write(reason, src, p)
    except Exception:      # noqa: BLE001
        return False


def clear(p=None, client: str | None = None, why: str | None = None) -> bool:
    """清某個視窗（不給 = 本視窗）的旗標；舊共用旗標屬於該視窗也一起清。回 True = 有清掉東西。
    why = actions.log 的說明（不給 = 「CLEAR <程序名>（人工清除）」）"""
    if p is not None:
        targets = [Path(p)]
        n = clients.name()
    else:
        n = clients.name() if client is None else clients.normalize(client)
        mp = path(clients.DEFAULT)
        owner = legacy_owner(_read(mp))
        if clients.is_default(n):
            targets = [] if owner else [mp]
        else:
            targets = [path(n)] + ([mp] if owner and owner.lower() == n.lower() else [])
    done = False
    for t in targets:
        try:
            t.unlink()
            done = True
        except FileNotFoundError:
            pass
    if done:
        try:
            import actlog
            actlog.add('verifyhalt', why or f'CLEAR {n}（人工清除）')
        except Exception:      # noqa: BLE001
            pass
    return done


def _key(d: dict | None):
    """一筆旗標的身分（同一筆 = 時間 / 來源 / 原因都一樣）"""
    return None if not d else (d.get('ts'), d.get('src'), d.get('reason'))


class AutoClear:
    """旗標自動清的計時器（watch 每輪 / preflight 現場連讀共用，判斷只有這一份）。
    feed(旗標, 這次讀圖是否已知正常, 單調時間, 讀圖的牆鐘時間) → True = 該清了：
      - 沒旗標 / 手動設的（src=manual）→ 歸零、False
      - 換了一筆旗標 → 重新計時
      - 不正常（unknown 等，見 screen_sigs.normal_screen）或讀圖早於旗標時間 → 歸零、False
      - 連續正常 ≥ need_s 秒且 ≥ need_n 次 → True"""

    def __init__(self, need_s: float = AUTO_CLEAR_S, need_n: int = AUTO_CLEAR_N):
        self.need_s, self.need_n = need_s, need_n
        self.key = None
        self.reset()

    def reset(self) -> None:
        self.t0 = None
        self.n = 0

    def feed(self, flag: dict | None, normal: bool, now: float, read_wall: float | None = None) -> bool:
        if not flag or flag.get('src') == MANUAL_SRC:
            self.key = None
            self.reset()
            return False
        k = _key(flag)
        if k != self.key:
            self.key = k
            self.reset()
        ts = flag.get('ts')
        if not normal or (isinstance(ts, (int, float)) and read_wall is not None and read_wall < ts):
            self.reset()
            return False
        if self.t0 is None:
            self.t0 = now
        self.n += 1
        return now - self.t0 >= self.need_s and self.n >= self.need_n


def note_event(msg: str) -> None:
    """寫本視窗 quest-events.log 一行（「verifyhalt：…」）；失敗不丟例外"""
    try:
        p = logpaths.p(clients.npath('quest-events.log'))
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, 'a', encoding='utf-8') as f:
            f.write(f'{time.strftime("%Y-%m-%d %H:%M:%S")} verifyhalt：{msg}\n')
    except OSError:
        pass


def auto_clear(expected: dict, label: str, src: str = 'watch') -> bool:
    """AutoClear 判定該清 → 清本視窗旗標（清之前再讀一次：已經換成別筆就不清）。
    寫 actions.log / quest-events.log「verifyhalt 自動清除（畫面已恢復：<label>）」、設旗標那筆 errlog 補 fix、stderr 印一行。回 True = 有清"""
    try:
        n = clients.name()
        cur = active()
        if not cur or _key(cur) != _key(expected) or cur.get('src') == MANUAL_SRC:
            return False
        msg = f'verifyhalt 自動清除（畫面已恢復：{label}）'
        if not clear(why=f'{msg} {n}（{src}；原旗標 {describe(cur)}）'):
            return False
        note_event(f'{msg}；原旗標 {describe(cur)}（{src} 判斷，連續 {int(AUTO_CLEAR_S)} 秒以上已知正常畫面）')
        if cur.get('err_id') is not None:
            try:
                import errlog
                errlog.fix(cur['err_id'], f'{msg}（{src}）')
            except Exception:      # noqa: BLE001
                pass
        print(f'{msg}：{n}（{src}）', file=sys.stderr, flush=True)
        return True
    except Exception:      # noqa: BLE001  清不掉 = 旗標還在 = 照舊停手（安全方向）
        return False


def known_clients() -> list[str]:
    """要列狀態的視窗：ROSTERS 全部 + clients/ 底下有旗標的資料夾 + 舊共用旗標的歸屬（主視窗第一個，去重、大小寫不分）"""
    out = list(clients.ROSTERS)
    try:
        for d in sorted((_base() / 'clients').iterdir()):
            if (d / NAME).exists():
                out.append(d.name)
    except OSError:
        pass
    o = legacy_owner(_read(path(clients.DEFAULT)))
    if o:
        out.append(o)
    seen, res = set(), []
    for n in [clients.DEFAULT] + out:
        if n.lower() not in seen:
            seen.add(n.lower())
            res.append(n)
    return res


def _targets(arg: str | None, default_all: bool) -> list[str]:
    if arg is None:
        return known_clients() if default_all else [clients.name()]
    return known_clients() if arg.lower() == 'all' else [clients.normalize(arg)]


def main(argv=None) -> int:
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    a = list(sys.argv[1:] if argv is None else argv)
    cmd = a[0] if a else 'status'
    arg = a[1] if len(a) >= 2 else None
    if cmd == 'status':
        hit = False
        for n in _targets(arg, True):
            d = active(client=n)
            hit = hit or d is not None
            print(f'verify-halt [{n}]：', describe(d))
        o = legacy_owner(_read(path(clients.DEFAULT)))
        if o:
            print(f'（主視窗路徑上有舊格式共用旗標，歸屬 {o}；主視窗不受影響。清：{clear_cmd(o)}）')
        return EXIT_VERIFY if hit else 0
    if cmd == 'clear':
        for n in _targets(arg, False):
            print(f'[{n}]', '已清除' if clear(client=n) else '本來就沒有旗標')
        return 0
    if cmd == 'set' and arg:
        return 0 if write(' '.join(a[1:]), src='manual') else 1
    print(__doc__)
    return 1


if __name__ == '__main__':
    sys.exit(main())
