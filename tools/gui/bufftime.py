#!/usr/bin/env python3
"""唯讀讀 buff 剩餘時間（2倍智慧果 / 龍王的守護）。只用標準函式庫；p1 = 主視窗（不設 PSA_CLIENT）、p2 = PSA_CLIENT=PrimalSA2。

用法（專案根目錄；WSL / Windows 原生相同）：
  uv run --no-project python tools/gui/bufftime.py read [--kind exp|dragon|all] [--dry-run]
  PSA_CLIENT=PrimalSA2 uv run --no-project python tools/gui/bufftime.py read
流程：preflight → 等主畫面 HUD（戰鬥畫面擋住就等，最多 30 秒）→ bag.buff_row() 像素判斷各格是哪種 buff（不點）
→ 對每個要讀的格：點該格圖示開浮窗（約 1 秒）→ OCR 標題核對是哪個 buff + 剩餘時間「N天N時N分N秒」→ **再點同一格關浮窗**
→ 驗證浮窗已關（沒關就 ESC；仍關不掉 = 133 停手）。沒有 buff → rc 0、buffs = []。
最後一行 JSON {"ok","rc","buffs":[{"kind","name","slot","remaining_s","raw","read_at","expires_at"}],"errors":[...]}
（read_at / expires_at = 本機時間 ISO 字串；另附 read_ts / expires_ts epoch 秒）。
讀完（非 --dry-run、buff 列讀得到）把預計到期寫進**本視窗**快取 `bufftime.json`（主視窗 tools/.cache/、其他 tools/.cache/clients/<程序名>/）：
{"v":1,"ts","buffs":{"exp":{"expires_ts","read_ts","remaining_s"},"dragon":{...}}}；這次要讀的種類圖示列沒有 → 移除該項，
有圖示但讀失敗 → 保留舊值。psa-hud pane 依它倒數顯示「智慧果 剩 H:MM」（watch 零輸入，不會為了讀時間去點畫面）。
可 import：`bufftime.read('exp')` 回上述 dict（給「快到期自動補吃」用）；`parse_remaining(text)` / `expires_at(...)` 是純函式。

座標（2026-10-15 p1 實測，2880x1659 客戶區 / 截圖座標）：buff 圖示第 k 格中心 = bag.BUFF_SLOTS[k] 的中心（第 1 格約 98,172）；
浮窗約 x 432～1006、y 360～468：標題青字（約 536,394）、說明、剩餘時間綠字靠右（約 924,398，裁 x 860～990、y 388～408）。浮窗不是面板，
開著時 uikit.screen() 判 unknown，所以只在點開之前 preflight、浮窗開著期間不 preflight。

退出碼（共用 0 / 1 / 2 / 8 / 9 / 10 見 uikit；bufftime 自己 130～134）：
  130 浮窗沒出現（點了圖示 OCR 讀不到標題 / 時間）
  131 浮窗標題對不上預期的 buff（已關浮窗，其他格照讀）
  132 剩餘時間讀不出（重讀一次仍不行；已關浮窗）
  133 浮窗關不掉（再點同格 + ESC 都不行）→ 立刻停手，不再點
  134 buff 列像素讀不到 / 主畫面 HUD 等 30 秒都沒回來（戰鬥 / 面板擋住）
紅區：只點 buff 圖示本身兩下；不碰外掛 / 遇敵 / 設置。驗證視窗（preflight 連 3 次不認得）→ 9 停手；netwatch halt → 10。
"""
import argparse
import json
import re
import sys
import time
import unicodedata
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import bag  # noqa: E402
import clients  # noqa: E402
import logpaths  # noqa: E402
import uikit  # noqa: E402

SRC = 'bufftime'
EXIT_NOPOPUP, EXIT_TITLE, EXIT_TIME, EXIT_STUCK, EXIT_ROW = 130, 131, 132, 133, 134

# 浮窗各區（截圖座標）。標題 / 時間各裁一框，另有整個浮窗當備援
POPUP_BOX = (432, 360, 574, 108)
TITLE_BOX = (500, 374, 380, 40)
TIME_BOX = (860, 388, 130, 20)
OPEN_WAIT_S = 3.0           # 點圖示後等浮窗的上限（實測約 1 秒）
CLOSE_WAIT_S = 2.0
HUD_WAIT_S = 30.0
POLL_S = 0.4
# 2026-10-15 實測：浮窗深色底 + 亮字，-Dark 0（2,3,4 倍）讀得出標題 / 時間；-Light 120 / 170 都讀不到 → -Dark 排第一（popup_open 只用第 1 組）
OCR_OPTS = [('-Dark', 0, '-Zooms', '2,3,4'), ('-Light', 120, '-Zooms', '2,3')]
TITLE_OPTS = [('-Dark', 0, '-Zooms', '2,3,4'), ('-Light', 120, '-Zooms', '2,3')]

# 標題關鍵字（OCR 容錯：只比部分字）→ buff 種類；名稱用 bag.BUFF_KIND 的反查
TITLE_KEYS = {'exp': ('智慧果', '智慧', '慧果', '倍智'), 'dragon': ('龍王', '守護', '守护', '龙王')}
KIND_NAME = {v: k for k, v in bag.BUFF_KIND.items()}


def log(msg: str) -> None:
    print(f'{SRC}：{msg}', file=sys.stderr, flush=True)


# ---- 純函式 ----
_DIGIT_FIX = str.maketrans({'O': '0', 'o': '0', 'l': '1', 'I': '1', '|': '1', 'S': '5', 'B': '8'})


def parse_remaining(text: str) -> int | None:
    """「0天0時55分6秒」→ 秒數。容錯：全形數字 / 空白、O→0 l→1、時 / 秒被認成別的字、結尾少「秒」。
    一定要有「天」與「分」才算（避免把雜訊當時間）；時 < 24、分 < 60、秒 < 60 才收。讀不出 None"""
    t = unicodedata.normalize('NFKC', text or '')
    t = re.sub(r'\s+', '', t).translate(_DIGIT_FIX)
    m = re.search(r'(\d+)[天夭](\d+)[^\d分兮]{0,2}(\d+)[分兮](\d+)', t)
    if not m:
        return None
    d, h, mi, s = (int(g) for g in m.groups())
    if h >= 24 or mi >= 60 or s >= 60:
        return None
    return ((d * 24 + h) * 60 + mi) * 60 + s


def vote(texts) -> int | None:
    """多行 / 多倍率 OCR 結果各自解析，取出現最多的秒數（平手取第一個）"""
    got = [v for v in (parse_remaining(t) for t in texts) if v is not None]
    if not got:
        return None
    return max(dict.fromkeys(got), key=got.count)


def title_kind(text: str) -> str | None:
    """標題 OCR 文字 → 'exp' / 'dragon' / None"""
    t = unicodedata.normalize('NFKC', text or '')
    for kind, keys in TITLE_KEYS.items():
        if any(k in t for k in keys):
            return kind
    return None


def expires_at(read_ts: float, remaining_s: int) -> float:
    return read_ts + remaining_s


def iso(ts: float) -> str:
    return time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(ts))


def slot_center(k: int) -> tuple:
    x0, y0, w, h = bag.BUFF_SLOTS[k]
    return x0 + w // 2, y0 + h // 2


# ---- 動作（測試時整組替換）----
def click_slot(k: int, note: str) -> None:
    x, y = slot_center(k)
    uikit.gui('seq', f'click {x} {y}; wait 300', note=f'bufftime {note} 格{k + 1} ({x},{y})')


def press_esc() -> None:
    uikit.gui('key', '{ESC}', note='bufftime 浮窗關不掉 → ESC')


def ocr_texts(box, opts_list) -> list:
    out = []
    for opts in opts_list:
        out += uikit.ocr(box, *opts)
    return out


def popup_texts() -> tuple:
    """(標題文字清單, 時間文字清單)；時間框讀不到再用整個浮窗備援"""
    titles = ocr_texts(TITLE_BOX, TITLE_OPTS)
    times = ocr_texts(TIME_BOX, OCR_OPTS)
    if vote(times) is None:
        times += ocr_texts(POPUP_BOX, OCR_OPTS[:1])
    return titles, times


def popup_open(titles=None, times=None) -> bool:
    """浮窗開著嗎：標題認得 buff 名，或讀得到時間。用於等開 / 驗證已關"""
    if titles is None:
        titles = ocr_texts(TITLE_BOX, TITLE_OPTS[:1])
    if any(title_kind(t) for t in titles):
        return True
    if times is None:
        times = ocr_texts(TIME_BOX, OCR_OPTS[:1])
    return vote(times) is not None


def wait_for(pred, secs: float) -> bool:
    end = uikit.clock() + secs
    while True:
        if pred():
            return True
        if uikit.clock() >= end:
            return False
        uikit.sleep(POLL_S)


def wait_hud(secs: float = HUD_WAIT_S) -> bool:
    """戰鬥畫面擋住主畫面 HUD 就等（快戰中開面板 / 點圖示不用停遇敵）"""
    return wait_for(uikit.hud_visible, secs)


# ---- 到期快取（psa-hud 讀）----
CACHE_NAME = 'bufftime.json'


def cache_path() -> Path:
    """本視窗的到期快取（PSA_CLIENT 在呼叫時才讀；測試時 testenv 轉向暫存）"""
    return logpaths.p(clients.cpath(CACHE_NAME))


def merge_cache(old: dict | None, buffs: list, want, row, now: float) -> dict:
    """純函式：舊快取 + 這次讀到的 → 新快取。want = 這次要讀的種類；row = bag.buff_row() 結果。
    讀到 → 更新；圖示列沒有 → 移除（buff 已沒了）；有圖示但讀失敗 → 保留舊值"""
    ob = (old or {}).get('buffs')
    cur = dict(ob) if isinstance(ob, dict) else {}
    got = {b['kind']: b for b in buffs}
    for k in want:
        if k in got:
            b = got[k]
            cur[k] = {'expires_ts': b['expires_ts'], 'read_ts': b['read_ts'], 'remaining_s': b['remaining_s']}
        elif k not in (row or []):
            cur.pop(k, None)
    return {'v': 1, 'ts': now, 'buffs': cur}


def save_cache(buffs: list, want, row, now: float | None = None, path: Path | None = None) -> Path | None:
    """讀改寫本視窗 bufftime.json（暫存檔 + os.replace 原子寫）；寫失敗只記 log 不影響結果"""
    import os
    path = path or cache_path()
    try:
        old = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        old = None
    d = merge_cache(old if isinstance(old, dict) else None, buffs, want, row, now if now is not None else time.time())
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(f'{path.name}.{os.getpid()}.tmp')
        tmp.write_text(json.dumps(d, ensure_ascii=False), encoding='utf-8')
        os.replace(tmp, path)
        return path
    except OSError as e:
        log(f'寫到期快取失敗：{e}')
        return None


# ---- 主流程 ----
def _close_popup(k: int) -> bool:
    """再點同一格關浮窗；沒關 → ESC；回是否已關"""
    click_slot(k, '關浮窗')
    if wait_for(lambda: not popup_open(), CLOSE_WAIT_S):
        return True
    log('再點同一格沒關掉，改按 ESC')
    press_esc()
    return wait_for(lambda: not popup_open(), CLOSE_WAIT_S)


def read_slot(k: int, kind: str, now=None) -> tuple:
    """讀第 k 格（預期 kind）→ (rc, entry|None, error|None)。浮窗一定關回去（關不掉 rc 133）"""
    now = now or time.time
    click_slot(k, '開浮窗')
    if not wait_for(lambda: popup_open(), OPEN_WAIT_S):
        uikit.snap('bufftime-nopopup')
        return EXIT_NOPOPUP, None, f'格{k + 1}：點了圖示浮窗沒出現'
    titles, times = popup_texts()
    secs = vote(times)
    if secs is None:                                  # 讀不出重讀一次
        uikit.sleep(POLL_S)
        titles, times = popup_texts()
        secs = vote(times)
    read_ts = now()
    got_kind = next((c for c in (title_kind(t) for t in titles) if c), None)
    if not _close_popup(k):
        uikit.snap('bufftime-stuck')
        return EXIT_STUCK, None, f'格{k + 1}：浮窗關不掉（再點 + ESC 都不行）'
    if got_kind is not None and got_kind != kind:
        return EXIT_TITLE, None, f'格{k + 1}：標題是 {got_kind}，像素判斷是 {kind}'
    if secs is None:
        return EXIT_TIME, None, f'格{k + 1}：剩餘時間讀不出（OCR {times[:4]}）'
    raw = next((t for t in times if parse_remaining(t) == secs), '')
    ent = {'kind': kind, 'name': KIND_NAME.get(kind, kind), 'slot': k + 1, 'remaining_s': secs, 'raw': raw,
           'title_verified': got_kind == kind, 'read_ts': read_ts, 'read_at': iso(read_ts),
           'expires_ts': expires_at(read_ts, secs), 'expires_at': iso(expires_at(read_ts, secs))}
    return 0, ent, None


def read(kind: str = 'all', dry_run: bool = False) -> dict:
    """讀 buff 剩餘時間 → {"ok","rc","buffs":[...],"errors":[...]}（rc 見檔頭）；kind = exp / dragon / all"""
    res = {'ok': False, 'rc': 0, 'buffs': [], 'errors': []}
    want = ('exp', 'dragon') if kind == 'all' else (kind,)
    rc = uikit.preflight(SRC)
    if rc:
        res['rc'] = rc
        return res
    if not wait_hud():
        res['rc'] = EXIT_ROW
        res['errors'].append('主畫面 HUD 等 30 秒都沒回來（戰鬥 / 面板擋住）')
        return res
    row = bag.buff_row()
    if row is None:
        res['rc'] = EXIT_ROW
        res['errors'].append('buff 列像素讀不到')
        return res
    todo = [(k, c) for k, c in enumerate(row) if c in want]
    log(f'buff 列 {row} → 要讀 {[(k + 1, c) for k, c in todo]}')
    if dry_run:
        res['ok'] = True
        res['plan'] = [{'slot': k + 1, 'kind': c, 'click': slot_center(k)} for k, c in todo]
        return res
    for k, c in todo:
        rc, ent, err = read_slot(k, c)
        if ent:
            res['buffs'].append(ent)
        if err:
            res['errors'].append(err)
            log(err)
        if rc and not res['rc']:
            res['rc'] = rc
        if rc == EXIT_STUCK:
            break
    save_cache(res['buffs'], want, row)
    res['ok'] = res['rc'] == 0
    return res


def fmt(secs: int) -> str:
    d, r = divmod(int(secs), 86400)
    h, r = divmod(r, 3600)
    return f'{d}天{h}時{r // 60}分{r % 60}秒'


def main(argv=None) -> int:
    import winenv
    winenv.enable_server()
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    sub = ap.add_subparsers(dest='cmd', required=True)
    p = sub.add_parser('read')
    p.add_argument('--kind', choices=['exp', 'dragon', 'all'], default='all')
    p.add_argument('--dry-run', action='store_true')
    a = ap.parse_args(argv)
    res = read(a.kind, a.dry_run)
    for b in res['buffs']:
        print(f'{b["name"]}  剩 {fmt(b["remaining_s"])}  預計到期 {b["expires_at"]}')
    if res['ok'] and not res['buffs'] and not a.dry_run:
        print('沒有 buff')
    print(json.dumps(res, ensure_ascii=False))
    return res['rc']


if __name__ == '__main__':
    sys.exit(main())
