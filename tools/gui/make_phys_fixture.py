#!/usr/bin/env python3
"""重產 fixtures/phys_1728x995_px.json：外接螢幕（遊戲客戶區 1728×995）全解析度樣本的像素凍結檔（給 test_screen_sigs 的 PHYS_OVERRIDES 測試用）。
樣本 = P0 實測存的 tools/.cache/p0_fit_full.png（遇敵關）、p0_fit_full_enc.png（遇敵開）；只有主畫面。
取樣 = 計畫 §3.4 方案 a：邏輯座標 (x, y) → 實體像素 (⌊x·W/1440⌋, ⌊y·H/829.5⌋)。取樣點 = 原特徵點 + 覆寫表點（兩種版面的 points / panel_points / annot_points 聯集）。
用法：uv run --no-project python tools/gui/make_phys_fixture.py（純離線；沒有 tools/.cache 樣本就什麼都不做）"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import pngread  # noqa: E402
import screen_sigs as S  # noqa: E402

SAMPLES = {'off': 'p0_fit_full.png', 'enc': 'p0_fit_full_enc.png'}
KEY = '1728x995'


def main():
    cache = HERE.parent / '.cache'
    pts = set()
    for k in (None, KEY):
        S.set_layout(k)
        pts |= set(S.points() + S.panel_points() + S.annot_points())
    S.set_layout(None)
    pts = sorted(pts)
    out = {'key': KEY, 'points': [list(p) for p in pts], 'samples': {}}
    for name, fn in SAMPLES.items():
        f = cache / fn
        if not f.exists():
            raise SystemExit('缺樣本：' + str(f))
        w, h, bpp, rows = pngread.decode(f.read_bytes())
        assert (w, h) == (1728, 995), (w, h)
        sx, sy = w / 1440, h / 829.5
        hx = ''
        for x, y in pts:
            r = rows[min(int(y * sy), h - 1)]
            o = min(int(x * sx), w - 1) * bpp
            hx += '%02x%02x%02x' % (r[o], r[o + 1], r[o + 2])
        out['samples'][name] = hx
    (HERE / 'fixtures' / 'phys_1728x995_px.json').write_text(json.dumps(out, separators=(',', ':')), encoding='utf-8')
    print('寫入 fixtures/phys_1728x995_px.json：%d 點 × %d 樣本' % (len(pts), len(out['samples'])))


if __name__ == '__main__':
    main()
