#!/usr/bin/env python3
"""離線 fixture 抽取（P0；只用標準函式庫、不碰遊戲）：用 pngread 從 tools/.cache 既有 1440×830 截圖抽像素，
存成 tools/gui/fixtures/{switch,pet,depot,exp}_px.json，給 uikit / char / team / pet / grind 的離線測試用。
截圖不存在就印出「跳過」並回報（不報錯）。計畫：notes/plan-scriptify.md §1.4。
用法：uv run --no-project python tools/gui/make_fixtures.py
注意：來源是舊截圖（新帳號 Lv1、別的地圖），各值要在對應實機量測時重確認。"""
import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import pngread  # noqa: E402
import screen_sigs  # noqa: E402

CACHE = HERE.parent / '.cache'
OUT = HERE / 'fixtures'

# 切換面板：卡片列 y（DKB0/02 同列 300、03/04 385、05 470）× 狀態框邊線 x（422/446）與米色底 416；右欄 = 左欄 + 310
CARD_YS = (300, 385, 470)
CARD_XS = (416, 422, 446)
SWITCH_PTS = [(x + dx, y) for dx in (0, 310) for y in CARD_YS for x in CARD_XS] + [(x, y) for x, y, *_ in screen_sigs.SIG_PANEL]
# 寵物面板：出戰 / 騎乘 / 休息鈕、左欄頭像頂邊（頭像中心 y − 36）、右上紅 ✕
AVATAR_CY = (195, 322, 450, 580, 700)
PET_PTS = [(345, 702), (360, 685), (480, 702), (620, 702)] + [(83, cy - 36) for cy in AVATAR_CY] + [(1310, 108)]
# 倉庫：存入 / 取出鈕文字區（粗取樣）+ 倉庫格（5 欄 × 4 列）
DEPOT_PTS = [(x, y) for y in range(675, 721, 15) for x in range(440, 621, 30)] + \
            [(x, y) for y in (275, 380, 487, 593) for x in (818, 924, 1030, 1136, 1242)]
# EXP 橫幅：掃描點與紫色判定都用 grind.py 的（P-R1 實測：矩形稀疏掃），不在這裡複製
os.environ.setdefault('PSA_LAYOUT', '2880x1659')       # grind → heal → walk 載入時會問版面；離線不碰遊戲
import grind  # noqa: E402
EXP_SRC = [(f'watch-m0/p{i}.png', f'p{i}') for i in range(1, 21)] + [(f'exp-r1/r{i:02d}.png', f'r{i:02d}') for i in range(1, 41)] + [('exp-r1/now.png', 'now')]
# 人工確認有橫幅的張（舊 p14 p16 p19；P-R1 的 now 與 r07 r10 r12 r15 r18 r20 r22 r25 r27 r30 r32 r35 r37 r40）
EXP_POSITIVE = ['p14', 'p16', 'p19', 'now'] + [f'r{i:02d}' for i in (7, 10, 12, 15, 18, 20, 22, 25, 27, 30, 32, 35, 37, 40)]


def load(path: Path):
    w, h, bpp, rows = pngread.decode(path.read_bytes())
    return rows, bpp


def grab(path: Path, pts) -> dict:
    rows, bpp = load(path)
    px = pngread.pixels(rows, bpp, pts)
    return {f'{x},{y}': list(c) for (x, y), c in px.items()}


def write(name: str, data: dict) -> None:
    OUT.mkdir(exist_ok=True)
    (OUT / name).write_text(json.dumps(data, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    print('寫入', name)


def main() -> int:
    done, skipped = [], []

    def need(*rel):
        ps = [CACHE / r for r in rel]
        miss = [str(p.relative_to(CACHE)) for p in ps if not p.exists()]
        return ps, miss

    ps, miss = need('ui/switch.png')
    if miss:
        skipped.append(('switch_px.json', miss))
    else:
        write('switch_px.json', {'note': '切換面板（DKB05 當前、其餘線上、全單人），來源 ui/switch.png；右欄 = 左欄 x+310；2026-10-10 離線抽取',
                                 'source': 'ui/switch.png', 'points': SWITCH_PTS, 'px': grab(ps[0], SWITCH_PTS)})
        done.append('switch_px.json')

    ps, miss = need('pet322.png')
    if miss:
        skipped.append(('pet_px.json', miss))
    else:
        write('pet_px.json', {'note': '寵物分頁（DKB02 選中、出戰亮），來源 pet322.png；頭像頂邊 y = 頭像中心 − 36', 'source': 'pet322.png',
                              'points': PET_PTS, 'px': grab(ps[0], PET_PTS)})
        done.append('pet_px.json')

    ps, miss = need('q567.png', 'q5.png')
    if miss:
        skipped.append(('depot_px.json', miss))
    else:
        write('depot_px.json', {'note': '寵物倉庫；q567 = 存入寵物（選中背包寵物）、q5 = 取出寵物（選中倉庫寵物）', 'points': DEPOT_PTS,
                                'q567': grab(ps[0], DEPOT_PTS), 'q5': grab(ps[1], DEPOT_PTS)})
        done.append('depot_px.json')

    imgs, miss_exp = {}, []
    for rel, tag in EXP_SRC:
        p = CACHE / rel
        if not p.exists():
            miss_exp.append(rel)
            continue
        px = grab(p, grind.EXP_PTS)
        purple = {k: v for k, v in px.items() if grind.is_exp_purple(v)}
        imgs[tag] = {'purple_n': len(purple), 'purple': purple}
    if not imgs:
        skipped.append(('exp_px.json', miss_exp))
    else:
        write('exp_px.json', {'note': 'EXP 橫幅偵測樣本（P-R1，2026-10-11）：每張只存紫點（grind.is_exp_purple）；掃描點 = grind.EXP_PTS（y 140～262 每 6、x 450～1000 每 4）；positive 為人工確認有橫幅，其餘沒有',
                              'rows': [grind.EXP_YS[0], grind.EXP_YS[-1], 6], 'xs': [grind.EXP_XS[0], grind.EXP_XS[-1], 4],
                              'positive': [t for t in EXP_POSITIVE if t in imgs], 'images': imgs})
        done.append('exp_px.json' + (f'（缺 {miss_exp}）' if miss_exp else ''))

    print('完成：', done)
    for n, m in skipped:
        print('跳過', n, '缺', m)
    return 0


if __name__ == '__main__':
    sys.exit(main())
