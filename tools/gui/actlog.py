#!/usr/bin/env python3
"""AI 操作遊戲畫面的共用 log（只用標準函式庫）：tools/.cache/actions.log，只留最新 2000 行（psa-hud pane、quest.py 等讀它）。
另外每次寫入同時 append 到按小時分檔 tools/.cache/actions/YYYY-MM-DD_HH.log（本地時間、不截斷、保留 14 天；
每小時第一次寫入（新檔建立時）順便刪過期檔），舊細節從分檔查：
  python tools/gui/actlog.py show [--date 2026-10-13] HH:MM-HH:MM [--grep 字串]   # 跨小時檔合併輸出（結束早於開始＝跨午夜）

  import actlog
  actlog.add('walk', '10204 → 188,13')      # 寫一行：「23:14:25 walk 10204 → 188,13」
命令列：python tools/gui/actlog.py <類別> <說明...>
gui.ps1 的 click / drag / key 等也寫同一個檔（格式相同）；寫入失敗一律忽略，不影響操作。
多視窗：設了 PSA_CLIENT 且不是主視窗 PrimalSA 時，時間後面加「[程序名] 」，例「23:14:25 [PrimalSA2] walk …」（gui.ps1 同規則）；主視窗格式不變。
併發：append 單行 + 裁尾，偶爾多個程序同時裁尾可能掉一行，可接受。
"""
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

import clients
import logpaths

LOG = logpaths.p(Path(__file__).resolve().parents[1] / '.cache' / 'actions.log')
KEEP = 2000
KEEP_DAYS = 14


def hourly_dir(path: Path = LOG) -> Path:
    return path.parent / 'actions'


def hourly_file(dt: datetime, path: Path = LOG) -> Path:
    return hourly_dir(path) / f'{dt:%Y-%m-%d_%H}.log'


def prune(path: Path = LOG, days: int = KEEP_DAYS, now: datetime | None = None) -> None:
    """刪掉檔名日期早於 days 天前的分檔（依檔名、不看 mtime）。"""
    cut = (now or datetime.now()) - timedelta(days=days)
    try:
        for f in hourly_dir(path).glob('????-??-??_??.log'):
            try:
                if datetime.strptime(f.stem, '%Y-%m-%d_%H') < cut:
                    f.unlink()
            except (ValueError, OSError):
                pass
    except OSError:
        pass


def _hourly_add(line: str, path: Path, now: datetime) -> None:
    try:
        hf = hourly_file(now, path)
        new = not hf.exists()
        hf.parent.mkdir(parents=True, exist_ok=True)
        with open(hf, 'a', encoding='utf-8', newline='\n') as f:
            f.write(line + '\n')
        if new:
            prune(path, now=now)
    except OSError:
        pass


def add(kind: str, msg: str = '', path: Path = LOG, keep: int = KEEP) -> None:
    now = datetime.now()
    line = f'{now:%H:%M:%S} {clients.log_tag()}{kind} {msg}'.rstrip().replace('\r', ' ').replace('\n', ' ')
    _hourly_add(line, path, now)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, 'a', encoding='utf-8', newline='\n') as f:
            f.write(line + '\n')
        lines = path.read_text(encoding='utf-8', errors='replace').splitlines()
        if len(lines) > keep:
            path.write_text('\n'.join(lines[-keep:]) + '\n', encoding='utf-8', newline='\n')
    except OSError:
        pass


def show(date: str | None, rng: str, grep: str | None = None, path: Path = LOG) -> list[str]:
    """回傳 date 當天 HH:MM-HH:MM（含頭尾分鐘）的行，跨小時檔合併；結束早於開始 = 跨午夜到隔天。"""
    a, b = rng.split('-')
    d0 = datetime.strptime(date, '%Y-%m-%d') if date else datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    t0 = d0 + timedelta(hours=int(a[:2]), minutes=int(a[3:5]))
    t1 = d0 + timedelta(hours=int(b[:2]), minutes=int(b[3:5]), seconds=59)
    if t1 < t0:
        t1 += timedelta(days=1)
    out = []
    h = t0.replace(minute=0, second=0)
    while h <= t1:
        hf = hourly_file(h, path)
        if hf.exists():
            for ln in hf.read_text(encoding='utf-8', errors='replace').splitlines():
                try:
                    t = datetime.strptime(ln[:8], '%H:%M:%S')
                except ValueError:
                    continue
                ts = h.replace(minute=t.minute, second=t.second)
                if t0 <= ts <= t1 and (not grep or grep in ln):
                    out.append(ln)
        h += timedelta(hours=1)
    return out


if __name__ == '__main__':
    if len(sys.argv) < 2:
        sys.exit('用法：actlog.py <類別> <說明...>｜actlog.py show [--date YYYY-MM-DD] HH:MM-HH:MM [--grep 字串]')
    if sys.argv[1] == 'show':
        import argparse
        ap = argparse.ArgumentParser(prog='actlog.py show')
        ap.add_argument('range', help='HH:MM-HH:MM')
        ap.add_argument('--date')
        ap.add_argument('--grep')
        a = ap.parse_args(sys.argv[2:])
        try:
            res = show(a.date, a.range, a.grep)
        except ValueError:
            sys.exit('時間格式錯誤：要 HH:MM-HH:MM，--date 要 YYYY-MM-DD')
        sys.stdout.reconfigure(encoding='utf-8')
        print('\n'.join(res))
        sys.exit(0)
    add(sys.argv[1], ' '.join(sys.argv[2:]))
