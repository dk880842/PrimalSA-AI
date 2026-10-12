#!/usr/bin/env python3
"""pet_catch.py 離線測試（假 Tools，不碰遊戲）。用法：uv run --no-project python tools/gui/test_pet_catch.py"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import testenv  # noqa: E402,F401
import pet_catch  # noqa: E402
import rebirth_pets as rp  # noqa: E402
import petmatch  # noqa: E402

fails = 0


def check(name, ok):
    global fails
    print(('PASS ' if ok else 'FAIL ') + name)
    fails += 0 if ok else 1


check('parse_assign', pet_catch.parse_assign('DKBO2:鯊魚系:克邦凱斯,DKBO3:鯊魚系:加克拉') == [('DKBO2', '鯊魚系', '克邦凱斯'), ('DKBO3', '鯊魚系', '加克拉')])
try:
    pet_catch.parse_assign('DKBO2:鯊魚系')
    check('parse_assign 格式錯 → ValueError', False)
except ValueError:
    check('parse_assign 格式錯 → ValueError', True)


class FakeT:
    def __init__(self, fail_at=None):
        self.calls, self.fail_at = [], fail_at

    def _r(self, tag, role):
        self.calls.append((tag, role))
        return 7 if self.fail_at == (tag, role) else 0

    def bait_take(self, role, keep):
        return self._r('bait', role)

    def catch_setup(self, role, fam, sp, count):
        return self._r('setup', role)

    def catch_start(self, role, count):
        return self._r('start', role)

    def catch_setup_many(self, assign, count):
        self.calls.append(('ass_open', tuple(r for r, _, _ in assign)))
        for r, fam, sp in assign:
            for tag in ('setup', 'start'):
                rc = self._r(tag, r)
                if rc:
                    return rc, r
        return 0, None

    def sleep(self, s):
        pass


A = [('DKBO2', '鯊魚系', '克邦凱斯'), ('DKBO3', '鯊魚系', '加克拉')]
f = FakeT()
check('dry-run 零呼叫', pet_catch.run(A, dry_run=True, tools=f) == 0 and not f.calls)
f = FakeT()
rc = pet_catch.run(A, stages=('setup',), tools=f)
check('setup：外掛面板開 1 次、逐人 setup + start', rc == 0 and f.calls == [('ass_open', ('DKBO2', 'DKBO3')), ('setup', 'DKBO2'), ('start', 'DKBO2'), ('setup', 'DKBO3'), ('start', 'DKBO3')])
f = FakeT(fail_at=('setup', 'DKBO2'))
check('setup 失敗 → 該 rc、不繼續下一人', pet_catch.run(A, stages=('setup',), tools=f) == 7 and f.calls[1:] == [('setup', 'DKBO2')])
f = FakeT(fail_at=('bait', 'DKBO2'))
check('bait 失敗 → rc、不繼續', pet_catch.run(A, stages=('bait',), tools=f) == 7 and f.calls == [('bait', 'DKBO2')])

# register_growths：撞到別的物種 → 刪除（只靠縮圖）
import tempfile
reg = {'thumb': {}, 'growth': {'1/1/1/1': '甲'}}
petmatch.load_species = lambda: reg
petmatch.save_species = lambda r: None
dropped = pet_catch.register_growths({'1/1/1/1': '乙', '2/2/2/2': '乙'})
check('register_growths：新字串登錄、撞別種的刪掉並計數', dropped == 1 and reg['growth'] == {'2/2/2/2': '乙'})

# rebirth_pets 純函式：系別清單鄰居備援表、物種列順序
check('FAMILY_NEIGHBORS / SPECIES_ORDER 有鯊魚系與火雞系', '鯊魚系' in rp.FAMILY_NEIGHBORS and rp.SPECIES_ORDER['鯊魚系'][0] == '克邦凱斯' and rp.SPECIES_ORDER['火雞系'][3] == '奇寶')
class FT2:
    def __init__(self, pets):
        self.pets = pets

    def pets_list(self, roles):
        return 0, self.pets


_ok = {'DKBO': [{'empty': False, 'state': '騎乘'}, {'empty': False, 'state': '出戰'}], 'DKBO4': [{'empty': False, 'state': '騎乘'}, {'empty': False, 'state': '等待'}, {'empty': True}]}
check('missing_battle：騎乘 / 等待 / 空格都不算出戰', pet_catch.missing_battle(_ok) == ['DKBO4'])
check('verify_battle：有人沒出戰寵 → 105；全有 → 0', pet_catch.verify_battle(['DKBO', 'DKBO4'], FT2(_ok)) == 105
      and pet_catch.verify_battle(['DKBO'], FT2({'DKBO': _ok['DKBO']})) == 0)


class FT3(FT2):
    """relock / wait / autoswap 用：記錄外掛開面板次數"""
    def __init__(self, pets, polls=None):
        super().__init__(pets)
        self.opens, self.items, self.polls = [], None, list(polls or [])
        self.locks = {r: {'騎寵': False, '戰寵': False} for r in pets}

    def lock_set_many(self, items):
        self.opens.append('set')
        self.items = items
        for r, w, on, _ in items:
            self.locks[r][w] = on
        return 0, None

    def lock_get_many(self, roles):
        self.opens.append('get')
        return 0, {r: dict(self.locks[r]) for r in roles}

    def catch_poll_many(self, roles):
        self.opens.append(tuple(roles))
        return 0, self.polls.pop(0)

    def ass_each(self, roles, tab, fn):
        self.opens.append(('each', tab, tuple(roles)))
        return 0, {}, None

    def _toggle(self, xy, want, note):
        return 0

    def sleep(self, s):
        pass


BRA, DOR = '布拉奇多斯', '朵拉比斯'
pp = {r: [{'slot': 1, 'empty': False, 'unnamed': '49/9/8/2', 'species': BRA, 'state': '騎乘'}, {'slot': 2, 'empty': False, 'name': DOR, 'state': '出戰'}] for r in ('DKBO', 'DKBO3')}
f3 = FT3(pp)
check('relock：一次 lock_set_many（2 人 × 2 項，騎寵用成長字串）+ 一次讀回 → 0', pet_catch.relock(['DKBO', 'DKBO3'], tools=f3) == 0 and f3.opens == ['set', 'get']
      and ('DKBO3', '騎寵', True, ('growth', '49/9/8/2')) in f3.items and ('DKBO3', '戰寵', True, ('name', DOR)) in f3.items)
f3 = FT3({'DKBO': [{'slot': 1, 'empty': False, 'name': DOR}, {'slot': 2, 'empty': False, 'name': DOR}]})
check('relock：戰寵同名 2 隻 → 107、不開外掛', pet_catch.relock(['DKBO'], which=('戰寵',), tools=f3) == rp.EXIT_LOCK and f3.opens == [])
f3 = FT3({}, polls=[{'DKBO2': (3, True), 'DKBO3': (0, False)}, {'DKBO2': (None, False)}])
check('wait：每輪外掛只開一次讀所有沒抓完的人、抓完的移除', pet_catch.run(A, stages=('wait',), tools=f3) == 0 and f3.opens == [('DKBO2', 'DKBO3'), ('DKBO2',)])
f3 = FT3({})
check('autoswap：ass_each 一次（一般設置分頁）', pet_catch.set_autoswap(['DKBO', 'DKBO2'], False, tools=f3) == 0 and f3.opens == [('each', 'general', ('DKBO', 'DKBO2'))])
print('\n失敗 %d' % fails if fails else '\n全部通過')
sys.exit(1 if fails else 0)
