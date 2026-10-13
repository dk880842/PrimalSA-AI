#!/usr/bin/env python3
"""petwatch.py 參數化離線測試：不碰遊戲（gui / ocr / 面板函式都換成假的）。
用法：uv run --no-project python tools/gui/test_petwatch.py"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import testenv  # noqa: E402,F401  紀錄檔轉向暫存
import petwatch  # noqa: E402

fails = 0


def check(name, cond, extra=''):
    global fails
    print(('PASS' if cond else 'FAIL'), name, extra)
    if not cond:
        fails += 1


def raises(fn, *a):
    try:
        fn(*a)
    except ValueError:
        return True
    return False


# 預設值 = 轉生後狀態
check('預設練功寵金布伊第 3 格、戰寵朵拉比斯第 2 格',
      (petwatch.PET_NAME, petwatch.PET_SLOT, petwatch.BACK_NAME, petwatch.BACK_SLOT) == ('金布伊', 3, '朵拉比斯', 2))
check('下拉項目 y：第 1～4 格 = 419 / 461 / 503 / 545（與舊表一致）',
      [petwatch.lock_item_xy(n)[1] for n in (1, 2, 3, 4)] == [419, 461, 503, 545] and petwatch.lock_item_xy(1)[0] == 1050)
check('name_key 前 2 字', petwatch.name_key('朵拉比斯') == '朵拉' and petwatch.name_key('迪基格斯') == '迪基')
check('configure 驗證：格號超界 / 同格 / 空名',
      raises(petwatch.configure, '金布伊', 5, '朵拉比斯', 2) and raises(petwatch.configure, '金布伊', 2, '朵拉比斯', 2)
      and raises(petwatch.configure, ' ', 3, '朵拉比斯', 2))
check('configure 失敗不改現值', petwatch.BACK_NAME == '朵拉比斯' and petwatch.PET_SLOT == 3)

# swap_back：假環境記下每個 seq 步驟，核對點的格 / 下拉項目
log, state = [], {'lock': True, 'name': ''}
petwatch.open_ass = lambda: True
petwatch.open_pet = lambda: True
petwatch.close_panel = lambda: None
petwatch.log = lambda *a, **k: None
petwatch.gui = lambda *a, **k: ''
petwatch.winenv.to_windows = lambda p: str(p)


def fake_seq(steps):
    log.append(steps)
    # 點鎖定框 = 切換勾選
    if f'click {petwatch.LOCK_BOX[0]} {petwatch.LOCK_BOX[1]}' in steps:
        state['lock'] = not state['lock']
    return ''


petwatch.seq = fake_seq
petwatch.lock_checked = lambda: state['lock']
petwatch.ocr_name = lambda box=petwatch.NAME_BOX: state['name']


def run(back, back_slot, name_in_game):
    log.clear()
    state.update(lock=True, name=name_in_game)
    petwatch.configure('金布伊', 3, back, back_slot)
    ok = petwatch.swap_back('DKBO')
    return ok, ' | '.join(log)


ok, txt = run('朵拉比斯', 2, '朵拉比斯')
check('預設：朵拉比斯在第 2 格 → 換回成功', ok)
check('預設：點寵物欄第 2 格（y=322）與下拉第 2 項（y=461）',
      f'click {petwatch.SLOT_X} 322' in txt and 'click 1050 461' in txt and 'click 250 200' not in txt)
ok, txt = run('朵拉比斯', 2, '金布伊')
check('第 2 格名字不是戰寵 → 不動作（沒按出戰）', not ok and f'click {petwatch.BTN_FIGHT[0]} {petwatch.BTN_FIGHT[1]}' not in txt)
ok, txt = run('迪基格斯', 1, '迪基格斯')
check('舊流程 --back 迪基格斯 --back-slot 1：y=200 / 下拉 419', ok and f'click {petwatch.SLOT_X} 200' in txt and 'click 1050 419' in txt)
petwatch.configure()
check('configure() 無參數回預設', (petwatch.BACK_NAME, petwatch.BACK_SLOT) == ('朵拉比斯', 2))
# 補血預設關（2026-10-13：練功不自動補血）
check('預設不補血', petwatch.main([], dry_args=True).no_heal is True)
check('--heal 才補血', petwatch.main(['--heal'], dry_args=True).no_heal is False)
check('--no-heal 相容（= 預設）', petwatch.main(['--no-heal'], dry_args=True).no_heal is True and petwatch.main(['--heal', '--no-heal'], dry_args=True).no_heal is True)
check('--once 不補血（只讀）', petwatch.main(['--heal', '--once'], dry_args=True).no_heal is True)
print(f'\n{"全部通過" if not fails else f"失敗 {fails} 項"}')
sys.exit(1 if fails else 0)
