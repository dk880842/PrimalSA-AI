#!/usr/bin/env python3
"""全視窗驗證停手旗標 tools/.cache/verify-halt.json（只用標準函式庫；2026-10-15 使用者決定，多視窗第 3a 步）。

鐵則 5：出現答題 / 驗證視窗要立刻停手。多視窗時任一視窗出事（uikit 回 9、watch 標 verify_suspect / unknown_long、
quest.py 的驗證警報）→ 寫這個**全部視窗共用**的旗標，所有視窗的常駐程式 / 腳本看到就停：
  - uikit.preflight（每支腳本開跑）→ 9；uikit.watch_preflight_ok → False
  - netwatch.guard / check_and_reconnect（quest / follow / heal --watch / petwatch / grind 迴圈每輪都叫）→ sys.exit(9)
  - watchstate.VerifyGuard.check（heal --watch / petwatch）→ 'timeout'（呼叫端停止）
  - follow 每輪開頭 → 9
  - gui.ps1 的 click / dclick / drag / key（psawin.ps1 Test-PsaVerifyHalt）→ 不送輸入、exit 9（最後一道保險）
  - watch.py 不停（零輸入），state.flags.verify_halt = True
旗標**不會自己消失**：人處理完驗證視窗後手動清 `uv run --no-project python tools/gui/verifyhalt.py clear`。

只在「多視窗情境」才寫（clients.multi_window：非主視窗，或主視窗時還有別的 PrimalSA* 在跑；查不到程序清單當作多視窗）。
單一視窗時不寫，行為與改版前完全相同（那個腳本本來就停了，使用者處理完重跑即可）。

  import verifyhalt
  verifyhalt.trip('畫面連 3 次不認得', src='grind')   # 多視窗才寫；回 True = 有寫 / 已經有
  verifyhalt.active()                                  # → dict（旗標內容）或 None
命令列：
  python tools/gui/verifyhalt.py [status]   印旗標（退出碼 0 = 沒有、9 = 有）
  python tools/gui/verifyhalt.py clear      人處理完驗證視窗後清除
  python tools/gui/verifyhalt.py set 原因   手動設（例：人看到別的視窗有驗證，要全部停）
"""
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import clients  # noqa: E402
import logpaths  # noqa: E402

FILE = logpaths.p(clients.SHARED_CACHE / 'verify-halt.json')     # 全部視窗共用（不分 PSA_CLIENT）；測試轉向暫存
EXIT_VERIFY = 9                                                  # = uikit.EXIT_UNKNOWN_SCREEN


def active(path=None) -> dict | None:
    """旗標存在 → 內容 dict（壞檔也算存在，回 {'reason': '（旗標檔讀不懂）'}）；不存在 None"""
    p = Path(path or FILE)
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


def describe(d: dict | None) -> str:
    if not d:
        return '無'
    t = d.get('ts')
    when = time.strftime('%m-%d %H:%M:%S', time.localtime(t)) if isinstance(t, (int, float)) else '?'
    return f'{when} {d.get("client", "?")} {d.get("src", "?")}：{d.get("reason", "")}'


def message(d: dict | None) -> str:
    """給腳本印的停手訊息"""
    return (f'全視窗驗證停手旗標存在（{describe(d)}）→ 不動作（鐵則 5）；人處理完驗證視窗後清：'
            'uv run --no-project python tools/gui/verifyhalt.py clear')


def write(reason: str, src: str = '', path=None) -> bool:
    """無條件寫旗標（已存在就保留第一筆，不覆蓋）；寫入失敗回 False"""
    p = Path(path or FILE)
    if p.exists():
        return True
    d = {'ts': time.time(), 'client': clients.name(), 'src': src, 'reason': str(reason)[:300], 'pid': os.getpid()}
    tmp = p.with_name(p.name + f'.{os.getpid()}.tmp')
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp.write_text(json.dumps(d, ensure_ascii=False), encoding='utf-8')
        os.replace(tmp, p)
    except OSError:
        return False
    try:
        import errlog
        errlog.add(f'全視窗驗證停手：{reason}（{clients.name()} {src}）；所有視窗的腳本會停，處理完跑 verifyhalt.py clear', source=src or 'verifyhalt')
    except Exception:      # noqa: BLE001  紀錄失敗不影響停手
        pass
    try:
        import actlog
        actlog.add('verifyhalt', f'SET {src}：{reason}')
    except Exception:      # noqa: BLE001
        pass
    print(f'!!! 全視窗驗證停手旗標已設（{clients.name()} {src}：{reason}）；所有視窗的腳本都會停（鐵則 5）', file=sys.stderr, flush=True)
    return True


def trip(reason: str, src: str = '', multi=None, path=None) -> bool:
    """偵測到驗證 / 答題視窗時呼叫：多視窗情境才寫旗標（multi 可直接給，測試用；None = clients.multi_window()）。
    回 True = 有寫（或本來就有）；False = 單一視窗不寫 / 寫入失敗。永不丟例外（停手流程不能被它拖垮）"""
    try:
        if Path(path or FILE).exists():
            return True
        if not (clients.multi_window() if multi is None else multi):
            return False
        return write(reason, src, path)
    except Exception:      # noqa: BLE001
        return False


def clear(path=None) -> bool:
    p = Path(path or FILE)
    try:
        p.unlink()
    except FileNotFoundError:
        return False
    try:
        import actlog
        actlog.add('verifyhalt', 'CLEAR（人工清除）')
    except Exception:      # noqa: BLE001
        pass
    return True


def main(argv=None) -> int:
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    a = list(sys.argv[1:] if argv is None else argv)
    cmd = a[0] if a else 'status'
    if cmd == 'status':
        d = active()
        print('verify-halt：', describe(d))
        return EXIT_VERIFY if d else 0
    if cmd == 'clear':
        print('已清除' if clear() else '本來就沒有旗標')
        return 0
    if cmd == 'set' and len(a) >= 2:
        return 0 if write(' '.join(a[1:]), src='manual') else 1
    print(__doc__)
    return 1


if __name__ == '__main__':
    sys.exit(main())
