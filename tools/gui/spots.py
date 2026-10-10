#!/usr/bin/env python3
"""練級傳送點表（只用標準庫）。唯一來源：.claude/skills/psa-game-ui/ui/transfer.md「練級傳送」表（2026-10-09 實測，0 轉）；
改了那張表要同步改這裡。座標 = 截圖座標（2880×1659 版面，練級傳送分頁 259,314 之下的目的地標籤）。
heal.SPOTS 只有其中 6 點；P8 整合時 heal.py 改成 `from spots import HEAL_SPOTS as SPOTS`（補柯奧龜洞 / 阿布龜洞 / 五兄弟洞窟）。
用法：給 grind.py 選點 / 預判等級門檻；`python spots.py` 印表。
"""
import re
import sys

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

# --spot auto：依隊長等級選點（0 轉；skill 表）。(最低等級, 點名)，由高到低
AUTO = [(120, '地雷區'), (80, '波拉島'), (60, '柯奧4F龜洞'), (45, '五兄弟洞窟'), (20, '海主人隧道'), (1, '柯奧龜洞')]

# heal.SPOTS 相容格式：名稱 → (x, y, 地圖 ID)
HEAL_SPOTS = {k: v[:3] for k, v in SPOTS.items()}

_LEVEL_RE = re.compile(r'(\d+)\s*轉\s*(\d+)\s*級')


def parse_level(text) -> tuple | None:
    """「0轉130級」→ (0, 130)；讀不出 None"""
    m = _LEVEL_RE.search(text or '')
    return (int(m[1]), int(m[2])) if m else None


def auto_spot(trans: int, level: int) -> str | None:
    """依等級選點。轉數 ≥ 1 → None（門檻未實測，呼叫端要求明確 --spot）；等級 < 1 → None"""
    if trans != 0:
        return None
    for lo, name in AUTO:
        if level >= lo:
            return name
    return None


def spot_of_map(map_id) -> str | None:
    """地圖 ID → 練功點名（不在表內 None）"""
    return next((n for n, v in SPOTS.items() if v[2] == map_id), None)


def same_tier(a: str, b: str) -> bool:
    """同一檔門檻的點視為同一區（波拉島 / 波拉島2、地雷區 / 地雷區2）"""
    return a in SPOTS and b in SPOTS and SPOTS[a][3] == SPOTS[b][3] and a != b and SPOTS[a][3] >= 80


def too_low(name: str, trans: int, level: int) -> bool:
    """依表預判被擋：只有 0 轉能預判；1 轉以上回 False（未實測，讓伺服器決定）"""
    return trans == 0 and level < SPOTS[name][3]


if __name__ == '__main__':
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    for n, (x, y, m, lv, mn) in SPOTS.items():
        print(f'{n:8} {x:5},{y:<4} 地圖 {m:<6} 0轉{lv}級  {mn}')
