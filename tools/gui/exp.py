#!/usr/bin/env python3
"""5 人經驗值唯讀讀取 + 升級時間估計（人物資訊面板底部 EXP 條「目前/本級所需」+ 中間「N轉M級」）。只用標準函式庫。

用法（專案根目錄；WSL / Windows 原生相同；角色名 DKBO / DKB0 都收）：
  uv run --no-project python tools/gui/exp.py read [--role all|DKBO,DKBO3] [--json] [--dry-run]
      開人物資訊一次（主畫面頭像 119,68），左欄頭像逐人切，OCR 讀 轉數 / 等級 / 目前經驗 / 本級所需；
      讀不出重讀 3 次，仍讀不出該欄給 None（不猜）；最後切回 DKBO、關面板。每次讀取附加到 tools/.cache/exp-history.jsonl。
  uv run --no-project python tools/gui/exp.py eta [--target 131] [--interval 300] [--role ...] [--from-history [--min-age 120]] [--dry-run]
      讀兩次（間隔 interval 秒，期間不碰遊戲）→ 每分鐘經驗（跨級用經驗表補算）→ 到 target 的剩餘經驗與預估時間。
      --from-history：只讀一次，第一次取 history 內該角色「同轉數、至少 min-age 秒前」最新的一筆（之後免等 300 秒）。
最後一行 JSON {"ok","rc","roles":{角色:{trans,level,cur,need,total,rate_per_min,remaining,eta_min}}}。
快速戰鬥掛機中可直接開面板（不停遇敵）：面板特徵暫時消失（戰鬥畫面擋住）就等最多 30 秒，不點任何東西。

經驗表：knowledge/data/tables/Exp.jsonl，ID=等級，exp = 該級升下一級所需（128 級 69,487,425 實測相符）。
讀值交叉驗證：讀到的「本級所需」必須等於經驗表 Exp[等級]，對不上 → 該筆整組 None（不猜、不反推）。

退出碼（共用 0 / 1 / 2 / 8 / 9 / 10 見 uikit；exp 自己 100～102）：
  100 人物資訊面板打不開 / 中途消失（沒點面板內座標）
  101 左欄角色沒選到（黃框不對）
  102 至少一人讀不出（其餘照常輸出；全部 None 才算失敗）
紅區：屬性重置 / 潛力重置 / 改名 / 裝扮（forbidden）；只點頭像、開關面板。驗證視窗（preflight 連 3 次不認得）→ 9 停手。
"""
import argparse
import json
import re
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import charstate  # noqa: E402
import petmatch  # noqa: E402
import uikit  # noqa: E402

SRC = 'exp'
EXIT_PANEL, EXIT_SELECT, EXIT_READ = 100, 101, 102
ROOT = uikit.ROOT
EXP_TABLE = ROOT / 'knowledge' / 'data' / 'tables' / 'Exp.jsonl'
HISTORY = uikit.CACHE / 'exp-history.jsonl'
ROLES = list(petmatch.AVATAR_Y)

OPEN_XY, CLOSE_XY = (119, 68), (1336, 112)
LEVEL_BOX = (178, 664, 432, 36)             # 「1轉128級(10001154)」綠字
EXP_BOX = (560, 778, 400, 28)               # 底部 EXP 條「58756681/69487425」白字
LEVEL_OPTS = [('-Dark', 0, '-Zooms', '2,3'), ('-Light', 120, '-Zooms', '2,3'), ('-Dark', 120, '-Zooms', '2,3,4')]
EXP_OPTS = [('-Light', 170, '-Zooms', '2,3'), ('-Light', 120, '-Zooms', '2,3'), ('-Dark', 0, '-Zooms', '2,3,4')]
FORBID = {'attr_reset': uikit.rect(1207, 280, 70), 'pot_reset': uikit.rect(1207, 718, 70),
          'rename': uikit.rect(573, 180, 30), 'costume': uikit.rect(395, 627, 80)}
SIG = [(1336, 112, 197, 73, 49, 40), (730, 100, 124, 79, 43, 25), (660, 100, 131, 85, 49, 25)]
ROLEINFO = uikit.Panel('ROLEINFO', OPEN_XY, SIG, CLOSE_XY, forbidden=FORBID)
PANEL_WAIT_S = 30.0
READ_TRIES = 3
LAST: dict = {}


def log(msg: str) -> None:
    print(f'exp：{msg}', file=sys.stderr, flush=True)


# ---- 純函式 ----
def load_table(path=None) -> dict:
    """{等級: 升下一級所需}（-1 = 無下一級的末列略過）"""
    t = {}
    for ln in Path(path or EXP_TABLE).read_text(encoding='utf-8').splitlines():
        if ln.strip():
            d = json.loads(ln)
            if d.get('exp', -1) > 0:
                t[int(d['ID'])] = int(d['exp'])
    return t


def cum_before(level: int, table: dict) -> int:
    """到達 level 級（0 經驗）時的累積經驗 = Σ Exp[1..level-1]"""
    return sum(table[i] for i in range(1, level))


def total_exp(level: int, cur: int, table: dict) -> int:
    return cum_before(level, table) + cur


def parse_exp(text) -> tuple | None:
    """'58756681/69487425' → (58756681, 69487425)；目前 ≤ 所需 且所需 > 0，否則 None。OCR 常把 / 讀成 l、1、|"""
    t = re.sub(r'\s+', '', str(text or ''))
    m = re.search(r'(\d{1,10})[/|l\\](\d{1,10})', t)
    if not m:
        return None
    a, b = int(m[1]), int(m[2])
    return (a, b) if 0 < b and a <= b else None


def parse_level(text) -> tuple | None:
    """'1轉128級(10001154)' → (1, 128)；容許 OCR 把「轉」讀成別字"""
    t = re.sub(r'\s+', '', str(text or ''))
    m = re.search(r'(\d)轉(\d{1,3})級', t) or re.search(r'(\d)\D{1,2}(\d{1,3})級', t)
    return (int(m[1]), int(m[2])) if m else None


def reconcile(lv, ex, table: dict) -> dict | None:
    """OCR 的等級 (trans, level) / 經驗 (cur, need) 交叉驗證 → {trans, level, cur, need, total} 或 None（不猜）。
    本級所需必須 = 經驗表 Exp[level]"""
    if not ex or not lv:
        return None
    trans, level = lv
    cur, need = ex
    if table.get(level) != need:
        return None
    return {'trans': trans, 'level': level, 'cur': cur, 'need': need, 'total': total_exp(level, cur, table)}


def rate_per_min(a: dict, b: dict, table: dict) -> float | None:
    """兩筆讀值（含 ts / trans / level / cur）的每分鐘經驗；轉數不同（期間轉生）/ 時間 ≤ 0 / 經驗倒退 → None"""
    if not a or not b or a['trans'] != b['trans']:
        return None
    dt = b['ts'] - a['ts']
    if dt <= 0:
        return None
    d = total_exp(b['level'], b['cur'], table) - total_exp(a['level'], a['cur'], table)
    return d / dt * 60.0 if d >= 0 else None


def remaining(level: int, cur: int, target: int, table: dict) -> int | None:
    """到 target 級（0 經驗）還差多少經驗；已達標 0；表不夠 None"""
    if level >= target:
        return 0
    if target not in table and target - 1 not in table:
        return None
    return cum_before(target, table) - total_exp(level, cur, table)


def eta_minutes(rem, rate) -> float | None:
    if rem is None or not rate or rate <= 0:
        return 0.0 if rem == 0 else None
    return rem / rate


def fmt_min(m) -> str:
    if m is None:
        return '—'
    h, mm = divmod(int(round(m)), 60)
    return f'{h} 小時 {mm} 分' if h else f'{mm} 分'


def norm_roles(spec: str) -> list:
    if spec.strip().lower() == 'all':
        return list(ROLES)
    out = []
    for t in spec.split(','):
        r = charstate.norm_char(t.strip()) or t.strip()
        hit = next((x for x in ROLES if charstate.same(x, r)), None)
        if not hit:
            raise ValueError(f'角色 {t!r} 不在五人白名單')
        out.append(hit)
    return out


# ---- 歷史 ----
def history_add(rec: dict, path=None) -> None:
    p = Path(path or HISTORY)
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open('a', encoding='utf-8') as f:
            f.write(json.dumps(rec, ensure_ascii=False) + '\n')
    except OSError:
        pass


def history_load(path=None) -> list:
    p = Path(path or HISTORY)
    out = []
    if p.exists():
        for ln in p.read_text(encoding='utf-8').splitlines():
            try:
                out.append(json.loads(ln))
            except ValueError:
                pass
    return out


def history_pick(hist: list, role: str, trans: int, now: float, min_age: float):
    """role 同轉數、至少 min_age 秒前的最新一筆"""
    c = [h for h in hist if h.get('role') == role and h.get('trans') == trans and now - h.get('ts', now) >= min_age]
    return max(c, key=lambda h: h['ts']) if c else None


# ---- 畫面 ----
def _fail(rc: int, msg: str, tag: str = '') -> int:
    if tag:
        uikit.snap(tag)
    return uikit.fail(SRC, rc, msg)


def _click(x, y, note, wait_ms=450) -> bool:
    return uikit.safe_click(x, y, ROLEINFO, note=note, wait_ms=wait_ms)


def _wait(pred, secs: float, poll: float = 0.15) -> bool:
    end = uikit.clock() + secs
    while True:
        if pred():
            return True
        if uikit.clock() >= end:
            return False
        uikit.sleep(poll)


def _avatar_sel(role: str) -> bool:
    import pet
    cols = uikit.px([(83, petmatch.AVATAR_TOP_Y[r]) for r in ROLES])
    return bool(cols) and [pet.is_avatar_sel(c) for c in cols] == [r == role for r in ROLES]


def select_role(role: str) -> int:
    """左欄點頭像 → 黃框剛好只有該角色（0 / 100 / 101）。面板特徵暫時不在（戰鬥畫面擋住）先等"""
    for _ in range(2):
        if not _wait(lambda: uikit.is_open(ROLEINFO), PANEL_WAIT_S):
            return _fail(EXIT_PANEL, '人物資訊面板特徵不在（戰鬥畫面擋住逾時或被關），沒點頭像；若畫面有驗證視窗請人看', 'exp-panel-lost')
        if _avatar_sel(role):
            return 0
        _click(83, petmatch.AVATAR_Y[role], f'exp 選角色 {role}', wait_ms=500)
        if _wait(lambda: _avatar_sel(role), 1.5):
            return 0
    return _fail(EXIT_SELECT, f'點了 {role} 頭像但黃框不對', f'exp-select-{role}')


def vote(lines, parse):
    """OCR 各行分別 parse，取出現最多次的值（多個 zoom 會回多行，其中常有一兩行錯字）；沒有 → None"""
    cnt = {}
    for t in lines:
        v = parse(t)
        if v:
            cnt[v] = cnt.get(v, 0) + 1
    return max(cnt, key=lambda k: cnt[k]) if cnt else None


def _ocr_first(box, optsets, parse, accept=None):
    """每組參數讀各行、投票；第一個 parse 成功（且 accept 通過）的回傳"""
    for o in optsets:
        lines = [t for t in uikit.ocr(box, *o) if t.strip()]
        cands = {}
        for t in lines:
            v = parse(t)
            if v and (accept is None or accept(v)):
                cands[v] = cands.get(v, 0) + 1
        if cands:
            return max(cands, key=lambda k: cands[k])
    return None


def read_current(table: dict) -> dict | None:
    """目前選中角色的讀值（reconcile 後）；3 次仍不過 None"""
    for i in range(READ_TRIES):
        lv = _ocr_first(LEVEL_BOX, LEVEL_OPTS, parse_level)
        ex = _ocr_first(EXP_BOX, EXP_OPTS, parse_exp, accept=lambda v: not lv or table.get(lv[1]) == v[1])
        r = reconcile(lv, ex, table)
        if r:
            return r
        LAST['raw'] = {'level': lv, 'exp': ex}
        uikit.sleep(0.5)
    return None


def read_all(roles, table=None, dry_run: bool = False) -> tuple:
    """開人物資訊一次逐人讀 → (rc, {role: dict|None})。每筆加 ts；已寫入 history。最後切回 DKBO 並關面板"""
    table = table or load_table()
    out = {}
    if dry_run:
        log(f'dry-run：會開人物資訊面板讀 {",".join(roles)}，不點任何東西')
        return 0, {r: None for r in roles}
    rc = uikit.preflight(SRC)
    if rc:
        return rc, out
    was_open = uikit.is_open(ROLEINFO)
    if not was_open:
        ok, _ = uikit.open_panel_ex(ROLEINFO, timeout=4.0, hud_wait=PANEL_WAIT_S)
        if not ok:
            return _fail(EXIT_PANEL, '人物資訊面板打不開（沒看到主畫面 HUD 或面板特徵）；沒點任何面板內座標', 'exp-open-fail'), out
    rc = 0
    try:
        for r in roles:
            rc = select_role(r)
            if rc:
                break
            v = read_current(table)
            if v:
                v['ts'] = time.time()
                history_add(dict(v, role=r))
            out[r] = v
        if not rc and roles[-1] != 'DKBO' and uikit.is_open(ROLEINFO):
            rc = select_role('DKBO')
    finally:
        if not was_open and uikit.is_open(ROLEINFO):
            uikit.close_panel(ROLEINFO, known_open=True)
    return rc, out


def build_eta(first: dict, second: dict, target: int, table: dict) -> dict:
    """純函式：first / second = {role: 讀值或 None} → {role: 結果}"""
    res = {}
    for r, b in second.items():
        a = first.get(r)
        if not b:
            res[r] = None
            continue
        rate = rate_per_min(a, b, table) if a else None
        rem = remaining(b['level'], b['cur'], target, table) if b['trans'] is not None else None
        res[r] = {'trans': b['trans'], 'level': b['level'], 'cur': b['cur'], 'need': b['need'], 'total': b['total'],
                  'rate_per_min': None if rate is None else round(rate), 'remaining': rem,
                  'eta_min': None if eta_minutes(rem, rate) is None else round(eta_minutes(rem, rate), 1)}
    return res


def eta(roles, target: int, interval: float, from_history: bool = False, min_age: float = 120.0, dry_run: bool = False) -> tuple:
    table = load_table()
    if dry_run:
        log(f'dry-run：讀 {",".join(roles)} → {"" if from_history else f"等 {interval:.0f} 秒再讀一次 → "}算到 {target} 級')
        return 0, {}
    hist = history_load() if from_history else []
    first = {}
    if not from_history:
        rc, first = read_all(roles, table)
        if rc:
            return rc, {}
        log(f'第一次讀完，等 {interval:.0f} 秒（期間不碰遊戲）')
        uikit.sleep(interval)
    rc, second = read_all(roles, table)
    if rc:
        return rc, {}
    if from_history:
        for r, b in second.items():
            if b:
                h = history_pick([x for x in hist if x.get('ts') != b.get('ts')], r, b['trans'], b['ts'], min_age)
                first[r] = h
    return 0, build_eta(first, second, target, table)


def print_table(res: dict, target: int) -> None:
    print(f'角色    等級     目前經驗 / 本級所需        每分鐘經驗   到 {target} 級剩餘    預估')
    for r, v in res.items():
        if not v:
            print(f'{charstate.display(r):6}  讀不出')
            continue
        rate = '—' if v['rate_per_min'] is None else f'{v["rate_per_min"]:,}'
        rem = '—' if v['remaining'] is None else f'{v["remaining"]:,}'
        print(f'{charstate.display(r):6}  {v["trans"]}轉{v["level"]}級  {v["cur"]:>11,} / {v["need"]:<11,}  {rate:>10}  {rem:>14}   {fmt_min(v["eta_min"])}')


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description='5 人經驗值唯讀讀取 + 升級時間估計')
    sub = ap.add_subparsers(dest='cmd', required=True)
    p1 = sub.add_parser('read')
    p2 = sub.add_parser('eta')
    for p in (p1, p2):
        p.add_argument('--role', default='all')
        p.add_argument('--dry-run', action='store_true')
        p.add_argument('--json', action='store_true')
    p2.add_argument('--target', type=int, default=131)
    p2.add_argument('--interval', type=float, default=300)
    p2.add_argument('--from-history', action='store_true')
    p2.add_argument('--min-age', type=float, default=120)
    a = ap.parse_args(argv)
    try:
        roles = norm_roles(a.role)
    except ValueError as e:
        print(f'exp：{e}', file=sys.stderr)
        return uikit.EXIT_USAGE
    if a.cmd == 'read':
        rc, out = read_all(roles, dry_run=a.dry_run)
        if not rc and not a.dry_run and any(v is None for v in out.values()):
            rc = EXIT_READ
        payload = {r: (None if not v else {k: v[k] for k in ('trans', 'level', 'cur', 'need', 'total')}) for r, v in out.items()}
        if not a.json and not a.dry_run:
            for r, v in payload.items():
                print(f'{charstate.display(r):6}  ' + ('讀不出' if not v else f'{v["trans"]}轉{v["level"]}級  {v["cur"]:,} / {v["need"]:,}'))
        print(json.dumps({'ok': rc == 0, 'rc': rc, 'roles': payload}, ensure_ascii=False))
        return rc
    rc, res = eta(roles, a.target, a.interval, a.from_history, a.min_age, a.dry_run)
    if not rc and not a.dry_run and any(v is None for v in res.values()):
        rc = EXIT_READ
    if res and not a.json:
        print_table(res, a.target)
    print(json.dumps({'ok': rc == 0, 'rc': rc, 'target': a.target, 'roles': res}, ensure_ascii=False))
    return rc


if __name__ == '__main__':
    sys.exit(main())
