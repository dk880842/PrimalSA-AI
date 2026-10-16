#!/usr/bin/env python3
"""丟棄寵物（寵物面板垃圾桶）。只用標準函式庫；重用 pet.py 的選角色 / 選格 / 讀名字 / 確認視窗，不改 pet.py。

**實機驗證狀態：沒有在遊戲上跑過**（流程取自 notes/quest-log.md 2004 段：寵物面板 → 頭像 → 第 N 格 → 垃圾桶 708,565 →
提示窗確認名稱 → 確定 615,557；5 人烏力斯坦實機各丟 1 次，但當時是手動）。

用法：
  uv run --no-project python tools/gui/petdrop.py DKBO|all 烏力斯坦 --confirm-name 烏力斯坦 [--max-level 1] [--dry-run]
  --max-level N：只丟等級 ≤ N 的（等級讀不出也不丟 → 73）；questrun --drop-reward 固定帶 1（剛拿到的獎勵寵是 1 級，練過的同名寵不會被丟）
  --lone：寵物欄已全存、這是剛拿到的唯一一隻（rebirth 轉生後 cleanup 用，2026-10-16 **未實機**）：放行第 1 格與「出戰」狀態；仍擋騎乘 / 像騎寵 / 名字不符 / 等級（--max-level）
  可 import：petdrop.drop(role, name, confirm_name, slot_no=None, dry_run=False, max_level=None, lone=False) → 退出碼；結果在 petdrop.LAST
退出碼（pet.py 的 70～78 + 本檔 79）：
  0  丟掉了（或該角色沒有這隻 = 視為已完成，info.already）
  70/71/72 同 pet.py（面板 / 選取 / 名字）
  73 防護擋下（名字是 / 像騎寵、狀態騎乘或出戰、第 1 格、名字不等於 --confirm-name、--max-level 時等級太高 / 讀不出），零丟棄點擊
  76 提示窗名稱對不上 / 丟完驗證失敗（不重點）
  79 同名多隻（沒給 --slot 不丟）
防護：只丟「名字完全等於 --confirm-name」的寵物；第 1 格（通常是騎寵）、騎乘 / 出戰狀態、騎寵名單（uikit.MOUNTS、像騎寵）一律不碰；
垃圾桶只有這裡用 allow=('trash',) 點；提示窗 OCR 名稱必須含該名字才按確定，否則按取消。
"""
import argparse
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import bag  # noqa: E402  只借 name_match
import pet  # noqa: E402
import uikit  # noqa: E402

SRC = 'petdrop'
EXIT_GUARD, EXIT_VERIFY, EXIT_MULTI = 73, 76, 79
TRASH_XY = (708, 565)
CONFIRM_OK, CONFIRM_CANCEL = (615, 557), (813, 557)
# 只框「確定要丟棄【名字】嗎?」那一行（2026-10-12 巴朵蘭恩：整個 CONFIRM_BOX 兩行一起 OCR 會漏掉黃字那行，單行框 -Dark 150 穩定讀到）
NAME_LINE_BOX = (520, 335, 400, 60)
LAST: dict = {}


def _fail(rc: int, msg: str, tag: str = '') -> int:
    if tag:
        uikit.snap(tag)
    return uikit.fail(SRC, rc, msg)


def guard_target(sl: dict, want: str, max_level: int | None = None, lone: bool = False) -> str | None:
    """純函式：這格能不能丟？回拒絕理由或 None。max_level：等級要讀得到且 ≤ 它才丟。
    lone（2026-10-16，轉生 20F 後寵物欄已全存、只剩剛拿到的獎勵寵）：放行第 1 格與「出戰」狀態（全存後唯一一隻會落在第 1 格）；騎乘 / 名字像騎寵 / 名字 / 等級照舊擋"""
    if sl.get('empty'):
        return '空格'
    if sl['slot'] == 1 and not lone:
        return '第 1 格（通常是騎寵）'
    if sl.get('state') in (('騎乘',) if lone else ('騎乘', '出戰')):
        return f'狀態是 {sl["state"]}'
    nm = sl.get('name') or ''
    if any(uikit.is_mount_like(t) for t in [nm] + list(sl.get('ocr') or [])) or sl.get('mountlike'):
        return '名字是 / 像騎寵'
    if bag.norm_name(nm) != bag.norm_name(want):
        return f'名字 {nm!r} 不等於 {want!r}'
    if max_level is not None:
        lv = sl.get('level')
        if lv is None:
            return f'等級讀不出（--max-level {max_level} 要讀到等級才丟）'
        if lv > max_level:
            return f'等級 {lv} > {max_level}（練過的同名寵不丟）'
    return None


def confirm_names_ok(ct: str, want: str) -> bool:
    """提示窗 OCR 文字「確定要丟棄【名字】嗎?」→ 括號內的名字必須（模糊）等於 want。
    （bag.name_match 的 norm_name 會把【…】內容整段刪掉，名字就在括號裡，不能用；2026-10-12 實機 rc 76 的根因。）
    括號內要 OCR 讀得到：括號前後的 OCR 殘字（如 [布克布 嗎?）也算：取「丟棄」之後到「嗎」之前的文字。純函式"""
    import re
    import difflib
    t = re.sub(r'\s+', '', ct or '')
    if re.search(r'丟棄[【\[（(]' + re.escape(re.sub(r'[\W_]+', '', want)) + r'[】\]）)]', t):
        return True                                                # 多組 OCR 串起來時完整的【名字】優先（2026-10-13 多魯寶：殘字「【多魯嗎?」排在前面被非貪婪比對取走）
    m = re.search(r'丟棄[【\[（(]?(.*?)[】\]）)]?嗎', t) or re.search(r'[【\[（(]([^】\]）)]*)[】\]）)]', t)
    if not m:
        return False
    got = re.sub(r'[\W_]+', '', m[1])
    w = re.sub(r'[\W_]+', '', want)
    return bool(got) and (got == w or difflib.SequenceMatcher(None, got, w).ratio() >= 0.85)


def drop_role(role: str, want: str, ctx: dict, slot_no: int | None = None, dry_run: bool = False, max_level: int | None = None, lone: bool = False) -> int:
    """面板已開。選角色 → 找名字 = want 的格 → 選取 → 垃圾桶 → 提示窗驗名 → 確定 → 驗空格"""
    rc, slots = pet.list_role(role, ctx)
    if rc:
        return rc
    hits = [s for s in slots if not s.get('empty') and s.get('name') and bag.norm_name(s['name']) == bag.norm_name(want)]
    if slot_no is not None:
        hits = [s for s in hits if s['slot'] == slot_no]
    if max_level is not None and len(hits) > 1:                   # 同名多隻：只留等級 ≤ max_level 的候選（練過的不算）
        low = [s for s in hits if s.get('level') is not None and s['level'] <= max_level]
        if len(low) == 1:
            hits = low
    if not hits:
        LAST.setdefault('already', []).append(role)
        return 0
    if len(hits) > 1:
        return _fail(EXIT_MULTI, f'{role} 有 {len(hits)} 隻「{want}」（格 {[h["slot"] for h in hits]}），要用 --slot 指定', 'petdrop-multi')
    sl = hits[0]
    why = guard_target(sl, want, max_level, lone)
    if why:
        return _fail(EXIT_GUARD, f'{role} 第 {sl["slot"]} 格不丟：{why}')
    if dry_run:
        LAST.setdefault('would_drop', []).append([role, sl['slot']])
        return 0
    i = sl['slot'] - 1
    f = pet.scan_frames()
    if f is None:
        return _fail(pet.EXIT_PANEL, '讀不到面板像素')
    rc = pet.select_slot(i, f)
    if rc:
        return rc
    again = pet.read_slot(i, ctx)                                  # 選取後再讀一次名字（防補位 / 選錯格）
    if guard_target(again, want, max_level, lone):
        return _fail(EXIT_GUARD, f'{role} 選取第 {sl["slot"]} 格後重讀：{guard_target(again, want, max_level, lone)}', 'petdrop-reread')
    if not uikit.safe_click(TRASH_XY[0], TRASH_XY[1], uikit.PET, note=f'petdrop 垃圾桶（{role} 第 {sl["slot"]} 格 {want}）', allow=('trash',), wait_ms=500):
        return _fail(pet.EXIT_PANEL, '寵物面板特徵不在，沒點垃圾桶')
    end = uikit.clock() + 2.5
    while not uikit.is_open(pet.CONFIRM):
        if uikit.clock() >= end:
            return _fail(EXIT_VERIFY, '按了垃圾桶但提示窗沒出現（不重點）', 'petdrop-noconfirm')
        uikit.sleep(0.15)
    # 2026-10-12 實機：名字那行是黃字（【布克布克】）— -Dark 0 只讀得到「回收站保存48小時!」，-Dark 120 才讀得到「確定要丟棄【布克布克】嗎?」→ 兩組串起來
    ct = ' '.join(uikit.ocr(NAME_LINE_BOX, '-Dark', 150, '-Zooms', '2,3') + uikit.ocr(pet.CONFIRM_BOX, '-Dark', 120, '-Zooms', '2,3') + uikit.ocr(pet.CONFIRM_BOX, '-Dark', 0, '-Zooms', '2,3,4'))
    mounts = [m for m in uikit.MOUNTS if bag.name_match(ct, m, 0.8) or m in ct]
    if not ct or not confirm_names_ok(ct, want) or mounts:
        uikit.snap('petdrop-confirm-name')                         # 取消前先存圖（提示窗還在，才看得到實際文字）
        uikit.safe_click(CONFIRM_CANCEL[0], CONFIRM_CANCEL[1], pet.CONFIRM, note='petdrop 提示窗名稱不符 → 取消')
        return _fail(EXIT_VERIFY, f'提示窗 OCR 是 {ct!r}（要含「{want}」、不含騎寵 {mounts}）→ 已取消')
    if not uikit.safe_click(CONFIRM_OK[0], CONFIRM_OK[1], pet.CONFIRM, note=f'petdrop 確定丟棄 {want}', wait_ms=700):
        return _fail(EXIT_VERIFY, '提示窗特徵消失，沒點確定')
    end = uikit.clock() + 3.0
    while True:
        g = pet.scan_frames()
        if g is not None and g['empty'][i]:
            LAST.setdefault('dropped', []).append([role, sl['slot']])
            return 0
        if uikit.clock() >= end:
            return _fail(EXIT_VERIFY, f'{role} 丟完第 {sl["slot"]} 格不是空格（不重點）', 'petdrop-verify')
        uikit.sleep(0.2)


def drop(role_arg: str, want: str, confirm_name: str, slot_no: int | None = None, dry_run: bool = False, learn: bool = True,
         max_level: int | None = None, lone: bool = False) -> int:
    LAST.clear()
    if bag.norm_name(want) != bag.norm_name(confirm_name):
        return _fail(uikit.EXIT_USAGE, f'--confirm-name {confirm_name!r} 與名稱 {want!r} 不同，不丟')
    roles = pet.role_list(role_arg)
    if not roles:
        return _fail(uikit.EXIT_USAGE, f'角色 {role_arg!r} 不認得')
    ctx = pet.load_ctx(learn)
    with pet.Session(False, True) as s:
        if s.rc:
            return s.rc
        for r in roles:
            rc = drop_role(r, want, ctx, slot_no, dry_run, max_level, lone)
            if rc:
                pet.save_ctx(ctx)
                return rc
        pet.save_ctx(ctx)
    return 0


def main() -> int:
    import winenv
    winenv.enable_server()
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('role')
    ap.add_argument('name')
    ap.add_argument('--confirm-name', required=True)
    ap.add_argument('--slot', type=int, default=None)
    ap.add_argument('--max-level', type=int, default=None, help='只丟等級 ≤ N 的（等級讀不出不丟）')
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--lone', action='store_true', help='寵物欄已全存、只剩這一隻：放行第 1 格 / 出戰（仍擋騎乘 / 像騎寵 / 名字 / 等級）')
    a = ap.parse_args()
    rc = drop(a.role, a.name, a.confirm_name, a.slot, a.dry_run, max_level=a.max_level, lone=a.lone)
    print(json.dumps(dict(LAST, ok=rc == 0, rc=rc), ensure_ascii=False))
    return rc


if __name__ == '__main__':
    sys.exit(main())
