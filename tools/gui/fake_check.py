"""離線測試用：外掛勾選框的假像素（用實機截圖色塊 fixtures/ass_check_px.json，不是自己編的顏色）。

ass.read_check / check_state 是讀框心 ±10 的 36 點正向辨認（2026-10-16 起），假遊戲回 pixel 時要回整個框的樣子：
  color(dx, dy, on)            → 框心偏移 (dx, dy) 的顏色（on = 勾 / 未勾；超出 ±16 夾到邊）
  at(x, y, boxes)              → boxes = [((cx, cy), on), ...]；(x, y) 落在某框 ±R 內就回那框的顏色，否則 None
  sample(name)                 → fixture 某塊的 get(dx, dy)（測 check_state 用）
"""
import json
from pathlib import Path

FIX = Path(__file__).resolve().parent / 'fixtures' / 'ass_check_px.json'
_FX = json.loads(FIX.read_text(encoding='utf-8'))
R = _FX['r']
SAMPLES = _FX['samples']
ON_SAMPLE, OFF_SAMPLE = 'checked_catch_auto', 'unchecked_autoswap_p2'


def sample(name):
    rows = [r.split() for r in SAMPLES[name]['rows']]

    def get(dx, dy):
        dx, dy = max(-R, min(R, dx)), max(-R, min(R, dy))
        h = rows[dy + R][dx + R]
        return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))
    return get


_ON, _OFF = sample(ON_SAMPLE), sample(OFF_SAMPLE)


def color(dx, dy, on):
    return (_ON if on else _OFF)(dx, dy)


def at(x, y, boxes, r=R):
    for (cx, cy), on in boxes:
        if abs(x - cx) <= r and abs(y - cy) <= r:
            return color(x - cx, y - cy, on)
    return None
