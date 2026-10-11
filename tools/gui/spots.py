#!/usr/bin/env python3
"""練級傳送點表（只用標準庫）。唯一來源：.claude/skills/psa-game-ui/ui/transfer.md「練級傳送」表（2026-10-09 實測，0 轉）；
改了那張表要同步改這裡。座標 = 截圖座標（2880×1659 版面，練級傳送分頁 259,314 之下的目的地標籤）。
heal.SPOTS 就是 HEAL_SPOTS（P8 起 heal.py `from spots import HEAL_SPOTS as SPOTS`，9 點全支援；1920×1017 版面改用本檔 HEAL_SPOTS_1920，6 點）。
用法：給 grind.py 選點 / 預判等級門檻；`python spots.py` 印表。
"""
import json
import re
import sys
from pathlib import Path

# 名稱 → (x, y, 抵達地圖 ID, 0 轉實際門檻等級, 地圖名)
SPOTS = {
    '柯奧龜洞': (737, 243, 11001, 1, '柯奧山的小洞窟１樓'),
    '阿布龜洞': (540, 326, 10001, 1, '阿布的洞窟地下１樓'),
    '海主人隧道': (862, 656, 31401, 20, '奇努伊的海底通路'),
    '五兄弟洞窟': (703, 445, 31706, 45, '五兄弟的山寨地下６樓'),
    '柯奧4F龜洞': (859, 356, 11004, 60, '柯奧山的小洞窟４樓'),
    '波拉島': (1100, 231, 500, 80, '五十年前波拉島'),
    '波拉島2': (1165, 326, 502, 80, '練功波拉島2'),
    '地雷區': (1165, 400, 60049, 120, '庫塔伊洞窟地下一樓'),
    '地雷區2': (1165, 468, 60050, 120, '庫塔伊洞窟地下二樓'),
}

# 1920×1017 版面（截圖 960×508）的傳送座標：名稱 → (x, y, 抵達地圖 ID)；只有 6 點實測過（2026-10-09），heal.py 在該版面只讀這張
HEAL_SPOTS_1920 = {
    '柯奧4F龜洞': (567, 216, 11004),
    '波拉島': (718, 138, 500),
    '波拉島2': (759, 198, 502),
    '地雷區': (759, 245, 60049),
    '地雷區2': (759, 288, 60050),
    '海主人隧道': (571, 405, 31401),      # 實測
}

# --spot auto：依隊長等級選點（0 轉；skill 表）。(最低等級, 點名)，由高到低
AUTO = [(120, '地雷區'), (80, '波拉島'), (60, '柯奧4F龜洞'), (45, '五兄弟洞窟'), (20, '海主人隧道'), (1, '柯奧龜洞')]

# follow（grind.py follow）換點表：(進場等級, 點名)，由高到低。來源：協作者 kkfaq2222-bit 的 levelwatch.py 實測 0 轉真門檻
# （1 柯奧龜洞、10 阿布龜洞、20 海主人隧道、45 五兄弟洞窟、60 柯奧4F龜洞、80 波拉島、120 地雷區）；
# 阿布龜洞的傳送座標 540,326 是我們自己在 ui/transfer.md 實測的（傳送門檻 1 級，10 級是練級效率的換點）。1 轉以上沿用此表（未實測）。
FOLLOW = [(120, '地雷區'), (80, '波拉島'), (60, '柯奧4F龜洞'), (45, '五兄弟洞窟'), (20, '海主人隧道'), (10, '阿布龜洞'), (1, '柯奧龜洞')]
UNTESTED = '1 轉以上門檻沿用 0 轉表、未實測（被擋時由 follow 學習修正，存 tools/.cache/spot-thresholds.json）'
THRESH_FILE = Path(__file__).resolve().parents[1] / '.cache' / 'spot-thresholds.json'
UNREACHABLE = 999                  # 訊息要求更高轉數 → 這個轉數永遠進不去

# heal.SPOTS 相容格式：名稱 → (x, y, 地圖 ID)
HEAL_SPOTS = {k: v[:3] for k, v in SPOTS.items()}

_LEVEL_RE = re.compile(r'(\d+)\s*轉\s*(\d+)\s*級')


def parse_level(text) -> tuple | None:
    """「0轉130級」→ (0, 130)；讀不出 None"""
    m = _LEVEL_RE.search(text or '')
    return (int(m[1]), int(m[2])) if m else None


# ---- 學習到的門檻（1 轉以上才用；{"轉數:點名": 實際要求的等級}）----
def load_learned(path=None) -> dict:
    try:
        d = json.loads(Path(path or THRESH_FILE).read_text(encoding='utf-8'))
        return {k: int(v) for k, v in d.items()} if isinstance(d, dict) else {}
    except (OSError, ValueError, TypeError):
        return {}


def learned(name: str, trans: int, path=None) -> int:
    """學到的門檻；0 轉不學（表是實測）、沒學到回 0"""
    return load_learned(path).get(f'{trans}:{name}', 0) if trans >= 1 else 0


def learn(name: str, trans: int, need: int, path=None) -> int:
    """記下「這個點 trans 轉至少要 need 級」（只往上改）；回目前存的值。寫檔失敗不丟例外"""
    if trans < 1 or name not in SPOTS:
        return 0
    p = Path(path or THRESH_FILE)
    d = load_learned(p)
    k = f'{trans}:{name}'
    d[k] = max(d.get(k, 0), int(need))
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding='utf-8')
    except OSError:
        pass
    return d[k]


def stage_min(name: str, trans: int, table=None, path=None) -> int:
    """換點表裡這個點的進場等級：表上的值與學到的門檻取大者"""
    base = next((lo for lo, n in (table or FOLLOW) if n == name), SPOTS[name][3])
    return max(base, learned(name, trans, path))


def spot_for(trans: int, level: int, buffer: int = 0, table=None, path=None) -> str | None:
    """依等級選點：由高到低第一個 level >= 進場等級 + buffer 的點（最低一檔不加 buffer）；都不到 None"""
    tb = table or FOLLOW
    lowest = min(lo for lo, _ in tb)
    for lo, name in tb:
        need = stage_min(name, trans, tb, path)
        if level >= need + (buffer if need > lowest else 0):
            return name
    return None


def auto_spot(trans: int, level: int) -> str | None:
    """--spot auto：0 轉用 AUTO 表（實測）；1 轉以上沿用同一張表再疊學到的修正（未實測，見 UNTESTED）；等級 < 1 → None"""
    if trans == 0:
        for lo, name in AUTO:
            if level >= lo:
                return name
        return None
    return spot_for(trans, level, 0, AUTO) if level >= 1 else None


def spot_of_map(map_id) -> str | None:
    """地圖 ID → 練功點名（不在表內 None）"""
    return next((n for n, v in SPOTS.items() if v[2] == map_id), None)


def same_tier(a: str, b: str) -> bool:
    """同一檔門檻的點視為同一區（波拉島 / 波拉島2、地雷區 / 地雷區2）"""
    return a in SPOTS and b in SPOTS and SPOTS[a][3] == SPOTS[b][3] and a != b and SPOTS[a][3] >= 80


def too_low(name: str, trans: int, level: int) -> bool:
    """依表預判被擋：0 轉用實測表；1 轉以上只看「學到的」門檻（沒學到 = 未實測，讓伺服器決定）"""
    if trans == 0:
        return level < SPOTS[name][3]
    return level < learned(name, trans)


if __name__ == '__main__':
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    for n, (x, y, m, lv, mn) in SPOTS.items():
        print(f'{n:8} {x:5},{y:<4} 地圖 {m:<6} 0轉{lv}級  {mn}')
