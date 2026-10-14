#!/usr/bin/env python3
"""rebirth.py / bag.py / petdrop.py 離線測試：完全不碰遊戲（假 Tools、假背包 FakeBag、假寵物面板函式）。
用法：uv run --no-project python tools/gui/test_rebirth.py"""
import contextlib
import io
import os
import re
import sys
import tempfile
import types
from pathlib import Path

os.environ.setdefault('PSA_LAYOUT', '2880x1659')
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import testenv  # noqa: E402,F401  紀錄檔轉向暫存（不污染真 actions.log / quest-events.log / errlog）
import bag  # noqa: E402
import errlog  # noqa: E402
import petdrop  # noqa: E402
import rebirth  # noqa: E402
import uikit  # noqa: E402

TMP = Path(tempfile.mkdtemp())
rebirth.EVENT_LOG, rebirth.QUEST_LOG, rebirth.PROGRESS = TMP / 'ev.log', TMP / 'ql.md', TMP / 'rb.json'
errlog.LOG = TMP / 'errlog.jsonl'
fails = 0


def check(name, cond, extra=''):
    global fails
    print(('PASS' if cond else 'FAIL'), name, extra)
    if not cond:
        fails += 1


def quiet(fn, *a, **k):
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        return fn(*a, **k)


# ================= 純函式 =================
check('norm_name 去括號 / 空白', bag.norm_name('火的羽毛飾 品[火]') == '火的羽毛飾品')
check('name_match 完全 / 模糊 / 不同', bag.name_match('精靈王之弓', '精靈王之弓') and bag.name_match('精靈王之号', '精靈王之弓') and not bag.name_match('合成弓箭 9', '精靈王之弓'))
check('name_match 前後多字', bag.name_match('Lv80 精靈王之弓 綁', '精靈王之弓'))
check('parse_level', bag.parse_level('0轉133級') == (0, 133) and bag.parse_level('1 轉 1 級') == (1, 1) and bag.parse_level('xx') is None)
check('popup_buttons 座標表', bag.popup_buttons('穿戴 丟棄')['穿戴'] == (618, 662) and bag.popup_buttons('使用 更多')['使用'] == (618, 648)
      and bag.popup_buttons('使用 丟棄')['丟棄'] == (838, 648) and bag.popup_buttons('使用')['使用'] == (732, 648) and bag.popup_buttons('取出')['取出'] == (732, 648))
check('protected 精靈王之弓', bag.protected('精靈王之弓') and not bag.protected('合成弓箭 9'))
check('level_min / task', rebirth.level_min(1) == 131 and rebirth.level_min(5) == 140 and rebirth.task_name(2) == '漆黑洞窟(二轉)' and rebirth.task_group(3) == 2006)

J = rebirth.judge_rebirth_dialog
BODY_ROLE = ['你真是厲害，居然打敗了帖拉所伊朵來到我這裏。', '那我就如你所願，來進行轉生的儀式吧。轉生是把你最強的力量給激發出來，把你的身體回復到剛出生時']
KING = (32021, 31, 29)
check('judge：角色轉生 + 精靈王旁 → role', J({'body': BODY_ROLE, 'buttons': ['完成', '再見'], 'body_ok': True}, KING)[0] == 'role')
check('judge：位置讀不到仍可 role', J({'body': BODY_ROLE, 'buttons': ['完成'], 'body_ok': True}, None)[0] == 'role')
check('judge：寵物轉生 → pet', J({'body': ['來進行寵物轉生吧'], 'buttons': ['完成'], 'body_ok': True}, KING)[0] == 'pet')
check('judge：瑪雷菲雅 → pet', J({'body': ['把瑪雷菲雅帶來'], 'buttons': [], 'body_ok': True}, KING)[0] == 'pet')
check('judge：內文讀不到 → unknown', J({'body': [], 'buttons': ['完成'], 'body_ok': False}, KING)[0] == 'unknown')
check('judge：守門人位置（y=51）→ unknown', J({'body': BODY_ROLE, 'buttons': ['完成'], 'body_ok': True}, (32021, 31, 51))[0] == 'unknown')
check('judge：只有「轉生」沒有儀式 → unknown', J({'body': ['轉生很危險'], 'buttons': [], 'body_ok': True}, KING)[0] == 'unknown')


# ================= FakeTools（rebirth 流程）=================
class Card:
    def __init__(self, name, label):
        self.name, self.label = name, label


class FakeTools:
    def __init__(self, **kw):
        self.calls = []
        self.pos = kw.get('pos', (300, 100, 100))
        self.quest_script = kw.get('quest', [])        # [(rc, 新位置)]
        self.levels_map = kw.get('levels', {r: (0, 133) for r in rebirth.ALL_ROLES})
        self.after_levels = {r: (1, 1) for r in rebirth.ALL_ROLES}
        self.rebirthed = False
        self.team_checks = kw.get('team_checks', [0, 0, 0])
        self.cards = kw.get('cards')
        self.dialog = kw.get('dialog', {'body': BODY_ROLE, 'buttons': ['完成', '再見'], 'body_ok': True})
        self.use_rcs = kw.get('use_rcs', [])
        self.swap_rc = kw.get('swap_rc', 0)
        self.store_rc = kw.get('store_rc', 0)
        self.drop_rc = kw.get('drop_rc', 0)
        self.fight_rc = kw.get('fight_rc', 0)
        self.items = kw.get('items')
        self.ass_rc = kw.get('ass_rc', (0, {'normal': '忠犬'}, ''))
        self.pet_empty = kw.get('pet_empty', {r: 3 for r in rebirth.ALL_ROLES})
        self.cur = kw.get('cur', 'DKBO')
        self.team_form_rc = kw.get('team_form_rc', 0)
        self.team_form_rcs = kw.get('team_form_rcs', [])
        self.wins = kw.get('wins', {})
        self.accept_rc = kw.get('accept_rc', 0)
        self.relogin_rcs = kw.get('relogin_rcs', [])
        self.snap_rc = kw.get('snap_rc', 0)
        self.diff_rc = kw.get('diff_rc', 0)

    def c(self, *a):
        self.calls.append(a)

    def names(self):
        return [x[0] for x in self.calls]

    def sleep(self, s): pass
    def preflight(self): self.c('preflight'); return 0
    def current(self): self.c('current'); return 0, self.cur
    def char_switch(self, n): self.c('char_switch', n); self.pos = (1000, 92, 99); return 0
    def char_ensure(self, n): self.c('char_ensure', n); return 0
    def team_form(self):
        self.c('team_form')
        return self.team_form_rcs.pop(0) if self.team_form_rcs else self.team_form_rc
    def team_check(self): self.c('team_check'); return self.team_checks.pop(0) if self.team_checks else 0
    def team_cards(self): self.c('team_cards'); return self.cards, ''

    def levels(self, roles):
        self.c('levels', tuple(roles))
        src = self.after_levels if self.rebirthed else self.levels_map
        return 0, {r: src.get(r) for r in roles}

    def find_items(self, role, names):
        self.c('find_items', role)
        d = {n: 0 for n in names}
        d.update(self.items.get(role, {}) if self.items else {})
        d['_free'] = 8
        return 0, d

    def pet_empties(self): self.c('pet_empties'); return 0, self.pet_empty
    def heal(self): self.c('heal')
    def ass_pet(self, role, act): self.c('ass_pet', role, act); return self.ass_rc
    def teleport20(self): self.c('teleport20'); self.pos = (32021, 31, 29)

    def quest(self, args, timeout=0):
        self.c('quest', tuple(args))
        if '--fight' in args:
            if self.fight_rc == 0:
                self.pos = (32011, 56, 36)
            return self.fight_rc, []
        if '--allow-irreversible' in args:
            self.rebirthed = True
            return 0, []
        rc, pos = self.quest_script.pop(0)
        if pos:
            self.pos = pos
        return rc, []

    def read_pos(self): return self.pos
    def track(self, task): self.c('track', task); self.pos = (32010, 54, 31); return True
    def dialog_texts(self): self.c('dialog_texts'); return self.dialog
    def press_dialog(self): self.c('press_dialog')

    def bag_use(self, role, name):
        self.c('bag_use', role, name)
        rc = self.use_rcs.pop(0) if self.use_rcs else 0
        return rc, {'buff': True}

    def bag_take(self, role, name): self.c('bag_take', role, name); return 0
    def bag_store(self, role, name): self.c('bag_store', role, name); return self.store_rc

    def swap_weapon(self, role, keep_old):
        self.c('swap_weapon', role, keep_old)
        return self.swap_rc, {'old': '合成弓箭 9', 'dropped': None if keep_old else '合成弓箭 9'}

    def drop_pet(self, name): self.c('drop_pet', name); return self.drop_rc
    def accept(self, n): self.c('accept', n); return self.accept_rc
    def relogin(self): self.c('relogin'); return self.relogin_rcs.pop(0) if self.relogin_rcs else 0
    def pet_snapshot(self): self.c('pet_snapshot'); return self.snap_rc, {'DKBO': []}
    def drop_new_lv1(self, n, before): self.c('drop_new_lv1', n, before); return self.diff_rc, {'why': 'x'}
    def encounter_on(self): return False
    def encounter_off(self): self.c('enc_off')
    def snap(self, tag): self.c('snap', tag)


def fresh():
    rebirth.PROGRESS.unlink(missing_ok=True)


FULL_QUEST = [(0, (32001, 5, 5)), (37, (32011, 56, 36)), (0, (32016, 31, 40)), (37, (32021, 29, 57)), (39, (32021, 31, 29))]

# ---- 完整順序 ----
fresh()
T = FakeTools(quest=list(FULL_QUEST))
rc = quiet(rebirth.run, tools=T)
seq = [c for c in T.calls if c[0] in ('quest', 'swap_weapon', 'heal', 'teleport20', 'press_dialog', 'drop_pet', 'bag_store', 'ass_pet')]
qs = [c[1] for c in seq if c[0] == 'quest']
check('完整流程 rc 0', rc == 0, str(rebirth.LAST.get('info')))
check('trans 自動 = 目前轉數 + 1 = 1（任務 漆黑洞窟(一轉)）', rebirth.LAST['trans'] == 1 and '漆黑洞窟(一轉)' in qs[0])
check('quest 呼叫順序：enter → boss10 → bow16 → boss20 → rebirth → allow 收尾',
      '--stop-after-dialog' in qs[0] and '--max-seconds' in qs[1] and '--stop-after-rewards' in qs[2] and qs[3][0] == '--task' and '--allow-irreversible' in qs[5], str(qs))
order = [c[0] for c in seq]
check('階段順序：quest < swap×5 < heal < ass×5 < teleport < quest < press < drop_pet < bag_store',
      order.index('swap_weapon') > order.index('quest') and max(i for i, x in enumerate(order) if x == 'heal') > max(i for i, x in enumerate(order) if x == 'swap_weapon')
      and order.index('teleport20') > order.index('ass_pet') and order.index('press_dialog') > order.index('teleport20')
      and order.index('drop_pet') > order.index('press_dialog') and order.index('bag_store') > order.index('drop_pet'), str(order))
check('swap 5 人、ass 5 人忠犬', order.count('swap_weapon') == 5 and [c for c in T.calls if c[0] == 'ass_pet'][0][2] == '忠犬' and order.count('ass_pet') == 5)
check('龍王的守護存回公共（隊長）', ('bag_store', 'DKBO', '龍王的守護') in T.calls)
check('進度檔記 10 階段 ok（含 accept）', all(v['status'] == 'ok' for v in rebirth.LAST['stages'].values()) and len(rebirth.LAST['stages']) == 10)
check('event log / quest-log 有寫', '階段 cleanup 結束' in rebirth.EVENT_LOG.read_text(encoding='utf-8') and '漆黑洞窟(一轉)' in rebirth.QUEST_LOG.read_text(encoding='utf-8'))

# ---- --trans / --from ----
fresh()
T = FakeTools(quest=[(37, (32021, 29, 57)), (39, (32021, 31, 29))])
T.after_levels = {r: (2, 1) for r in rebirth.ALL_ROLES}
rc = quiet(rebirth.run, trans=2, from_stage='boss20', tools=T)
check('--from boss20 --trans 2：略過 preflight / enter / swap，用二轉任務', rc == 0 and 'swap_weapon' not in T.names() and 'levels' in T.names()
      and all('漆黑洞窟(二轉)' in c[1] for c in T.calls if c[0] == 'quest' and '--allow-irreversible' not in c[1]), str(T.names()))
check('--from 從中途沒進度檔又沒 --trans → 1', quiet(lambda: (fresh(), rebirth.run(from_stage='heal', tools=FakeTools()))[1]) == 1)
fresh()
T = FakeTools(levels={r: (1, 135) for r in rebirth.ALL_ROLES}, quest=list(FULL_QUEST))
T.after_levels = {r: (2, 1) for r in rebirth.ALL_ROLES}
rc = quiet(rebirth.run, tools=T)
check('目前 1 轉 → 自動轉到第 2 轉（任務 2005）', rc == 0 and rebirth.LAST['trans'] == 2)
check('--dry-run 完全不呼叫 Tools', quiet(rebirth.run, dry_run=True, trans=3, tools=types.SimpleNamespace()) == 0)

# ---- 前置檢查各分項 ----
fresh()
check('當前不是 DKBO → 83', quiet(rebirth.run, tools=FakeTools(cur='DKBO3', quest=[])) == 83)
fresh()
check('team.form 失敗（team.check 也不滿）→ 83', quiet(rebirth.run, tools=FakeTools(team_form_rc=41, team_checks=[41])) == 83)
fresh()
check('等級不足（130）→ 80', quiet(rebirth.run, trans=1, tools=FakeTools(levels={**{r: (0, 133) for r in rebirth.ALL_ROLES}, 'DKBO4': (0, 130)})) == 80)
fresh()
check('轉數不符 → 80', quiet(rebirth.run, trans=1, tools=FakeTools(levels={r: (1, 140) for r in rebirth.ALL_ROLES})) == 80)
fresh()
T = FakeTools(items={'DKBO2': {'水的戒指': None}}, quest=[(37, (32011, 1, 1))])
check('缺證明不再擋 preflight（不回 81、不查證明）', quiet(rebirth.run, tools=T) != 81 and 'missing' not in rebirth.LAST.get('info', {}))
fresh()
check('寵物欄空位不足 → 82', quiet(rebirth.run, tools=FakeTools(pet_empty={**{r: 3 for r in rebirth.ALL_ROLES}, 'DKBO5': 1})) == 82)
fresh()
check('preflight 全過（heal 有跑）', quiet(rebirth.run, tools=(t := FakeTools(quest=[(37, (32011, 1, 1))]))) != 80 and 'heal' in t.names())

# ---- 38 重打分支 ----
CARDS = [Card('DKBO', 'leader'), Card('DKBO2', 'member'), Card('DKBO3', 'solo'), Card('DKBO4', 'member'), Card('DKBO5', 'member')]
fresh()
T = FakeTools(quest=[(38, (32011, 56, 36))], team_checks=[1, 0], cards=CARDS)
rc = quiet(rebirth.run, trans=1, from_stage='boss10', to_stage='boss10', tools=T)
n = T.names()
check('38：char.switch DKBO3 → track → quest --fight → char.ensure DKBO → team.form → team.check', rc == 0
      and n.index('char_switch') < n.index('track') < max(i for i, x in enumerate(n) if x == 'quest') < n.index('char_ensure') < n.index('team_form') < len(n) - 1
      and ('char_switch', 'DKBO3') in T.calls, str(n))
fq = [c for c in T.calls if c[0] == 'quest' and '--fight' in c[1]][0][1]
check('重打指令：--fight --npc auto --team-size 1', '--npc' in fq and 'auto' in fq and fq[fq.index('--team-size') + 1] == '1', str(fq))
fresh()
T = FakeTools(quest=[(38, (32011, 56, 36))], team_checks=[1], cards=CARDS, fight_rc=35)
check('38：重打沒贏（--fight 35）→ 85，仍切回隊長', quiet(rebirth.run, trans=1, from_stage='boss10', to_stage='boss10', tools=T) == 85 and ('char_ensure', 'DKBO') in T.calls)
fresh()
T = FakeTools(quest=[(38, (32011, 56, 36))], team_checks=[1, 1], cards=CARDS)
check('38：重打後 team.check 仍不滿 → 85', quiet(rebirth.run, trans=1, from_stage='boss10', to_stage='boss10', tools=T) == 85)
fresh()
T = FakeTools(quest=[(38, (32011, 56, 36))], team_checks=[1], cards=[Card('DKBO', 'leader'), Card(None, 'solo')] + CARDS[1:2])
check('38：不在隊的人名字讀不出 → 85，不亂切', quiet(rebirth.run, trans=1, from_stage='boss10', to_stage='boss10', tools=T) == 85 and 'char_switch' not in T.names())
fresh()
T = FakeTools(quest=[(37, (32010, 54, 30))])
check('37 但位置不是 11F（沒贏）→ 85', quiet(rebirth.run, trans=1, from_stage='boss10', to_stage='boss10', tools=T) == 85)
fresh()
T = FakeTools(quest=[(2, None)])
check('quest 回 2（不認得畫面）→ 9 停手', quiet(rebirth.run, trans=1, from_stage='boss10', to_stage='boss10', tools=T) == 9)
fresh()
T = FakeTools(quest=[(21, None)])
check('quest 回 21 → 84', quiet(rebirth.run, trans=1, from_stage='boss10', to_stage='boss10', tools=T) == 84)

# ---- boss20：傳到 21F 後往回走備援 ----
class FT20(FakeTools):
    """boss20：人在 32021:31,29；追蹤 quest 回 rc 不動；備援走 walk、--fight 贏 → 32021:29,57"""
    def __init__(self, track_rc=3, walk_ok=(True, True), fight_rc=0, band=True, **kw):
        super().__init__(**kw)
        self.track_rc, self.walk_ok, self.f_rc, self.band = track_rc, list(walk_ok), fight_rc, band
        self.pos = kw.get('pos', (32021, 31, 29))

    def walk(self, m, x, y, exit_map=None):
        self.c('walk', m, x, y, exit_map)
        if (m, x, y) == (32021, 31, 47):             # 傳送帶：同圖，座標變 31,53（band=False 不傳）
            self.pos = (32021, 31, 53) if self.band else (32021, 31, 47)
            return self.pos
        ok = self.walk_ok.pop(0) if self.walk_ok else True
        if not ok:
            return None
        self.pos = (exit_map or m, x, y)
        return self.pos

    def quest(self, args, timeout=0):
        self.c('quest', tuple(args))
        if '--fight' in args:
            if self.f_rc == 0:
                self.pos = (32021, 29, 57)
            return self.f_rc, []
        return self.track_rc, []


def b20(**kw):
    fresh()
    T = FT20(**kw)
    return T, quiet(rebirth.run, trans=2, from_stage='boss20', to_stage='boss20', tools=T)


T, rc = b20()
n = T.names()
w = [c for c in T.calls if c[0] == 'walk']
fq = [c[1] for c in T.calls if c[0] == 'quest' and '--fight' in c[1]]
check('boss20：追蹤 rc 3 人在 32021:31,29 → walk 傳送帶 31,47（座標進 y>=50）→ 出口 28,59（換圖 32020）→ team.check → walk 20,11 → --fight → 0',
      rc == 0 and w == [('walk', 32021, 31, 47, None), ('walk', 32021, 28, 59, 32020), ('walk', 32020, 20, 11, None)] and len(fq) == 1 and '--npc' in fq[0] and 'auto' in fq[0]
      and n.index('walk') < n.index('team_check') < len(n) - 1, str(n))
check('boss20 備援：walk 前 preflight', [i for i, x in enumerate(n) if x == 'preflight'][0] < n.index('walk'))
T, rc = b20(track_rc=19)
check('boss20：追蹤卡住（19）同樣走備援', rc == 0 and len([c for c in T.calls if c[0] == 'walk']) == 3)
T, rc = b20(walk_ok=(False,))
check('boss20：出口走不過去 → 84（backtrack=exit）、不開打', rc == 84 and rebirth.LAST['info'].get('backtrack') == 'exit' and not any('--fight' in c[1] for c in T.calls if c[0] == 'quest'))
T, rc = b20(pos=(32021, 31, 50))
w = [c[1:] for c in T.calls if c[0] == 'walk']
check('boss20：已在南區（y>=50 且非勝利落點）→ 跳過傳送帶，只走出口 + 20,11', rc == 0 and w == [(32021, 28, 59, 32020), (32020, 20, 11, None)], str(w))
T, rc = b20(band=False)
check('boss20：傳送帶沒傳（座標一直 y<50）→ 84（backtrack=band），不走出口、不開打',
      rc == 84 and rebirth.LAST['info'].get('backtrack') == 'band' and [c[1:] for c in T.calls if c[0] == 'walk'] == [(32021, 31, 47, None)]
      and not any('--fight' in c[1] for c in T.calls if c[0] == 'quest'))
T, rc = b20(walk_ok=(True, False))
check('boss20：走不到 20,11 → 84（backtrack=spot）', rc == 84 and rebirth.LAST['info'].get('backtrack') == 'spot')
T, rc = b20(fight_rc=35)
check('boss20：備援開打沒贏（35）→ 85，且備援只試一次', rc == 85 and len([c for c in T.calls if c[0] == 'walk']) == 3)
T, rc = b20(team_checks=[1, 0])
check('boss20：換圖後隊伍散了 → team.form 再走', rc == 0 and 'team_form' in T.names())
T, rc = b20(team_checks=[1, 1], team_form_rc=41)
check('boss20：換圖後 team.form 失敗 → 83', rc == 83)
T, rc = b20(track_rc=2)
check('boss20：quest 回 2（驗證視窗）→ 9，不走備援', rc == 9 and 'walk' not in T.names())
T, rc = b20(pos=(32020, 20, 11))
check('boss20：已在 32020 → 不走 walk（quest 預設模式自己處理，非 21F 不備援）', 'walk' not in T.names() and rc == 84)
fresh()
T = FT20(pos=(32020, 20, 11))
T.quest = lambda args, timeout=0: (T.calls.append(('quest', tuple(args))), (37, None))[1]
T.pos = (32021, 29, 57)
check('boss20：quest 回 37 且落點對 → 不備援', quiet(rebirth.run, trans=2, from_stage='boss20', to_stage='boss20', tools=T) == 0 and 'walk' not in T.names())
# refight：被打飛者追蹤把人傳到 21F → 先走回 20F 再重打
CARDS20 = [Card('DKBO', 'leader'), Card('DKBO2', 'member'), Card('DKBO3', 'solo'), Card('DKBO4', 'member'), Card('DKBO5', 'member')]
fresh()
T = FT20(track_rc=38, team_checks=[1, 0], cards=CARDS20)
T.pos = (32021, 29, 57)
T.char_switch = lambda n: (T.c('char_switch', n), setattr(T, 'pos', (1000, 92, 99)), 0)[2]
T.track = lambda task: (T.c('track', task), setattr(T, 'pos', (32021, 31, 29)), True)[2]
rc = quiet(rebirth.run, trans=2, from_stage='boss20', to_stage='boss20', tools=T)
n = T.names()
check('boss20 refight：追蹤傳到 21F → walk 回 20F（不 team.check）→ --fight --team-size 1', rc == 0 and n.index('track') < n.index('walk')
      and [c[1:] for c in T.calls if c[0] == 'walk'] == [(32021, 31, 47, None), (32021, 28, 59, 32020), (32020, 20, 11, None)] and ('char_ensure', 'DKBO') in T.calls, str(n))

# ---- 39 轉生確認 ----
fresh()
T = FakeTools(quest=[(39, KING)], dialog={'body': ['來進行寵物轉生吧'], 'buttons': ['完成'], 'body_ok': True})
rc = quiet(rebirth.run, trans=1, from_stage='rebirth', to_stage='rebirth', tools=T)
check('39：寵物轉生 → 88，沒按對話鈕、沒 allow', rc == 88 and 'press_dialog' not in T.names() and not any('--allow-irreversible' in c[1] for c in T.calls if c[0] == 'quest'))
fresh()
T = FakeTools(quest=[(39, KING)], dialog={'body': [], 'buttons': [], 'body_ok': False})
check('39：對話讀不到 → 88', quiet(rebirth.run, trans=1, from_stage='rebirth', to_stage='rebirth', tools=T) == 88 and 'press_dialog' not in T.names())
fresh()
T = FakeTools(quest=[(39, KING)])
rc = quiet(rebirth.run, trans=1, from_stage='rebirth', to_stage='rebirth', confirm_rebirth=True, tools=T)
check('39：角色轉生 + --confirm-rebirth → 89，沒按', rc == 89 and 'press_dialog' not in T.names())
fresh()
T = FakeTools(quest=[(39, KING)])
rc = quiet(rebirth.run, trans=1, from_stage='rebirth', to_stage='rebirth', tools=T)
check('39：角色轉生預設 → 按完成 + --allow-irreversible 收尾 + 轉數確認', rc == 0 and 'press_dialog' in T.names() and any('--allow-irreversible' in c[1] for c in T.calls if c[0] == 'quest')
      and T.names().index('dialog_texts') < T.names().index('press_dialog'))
fresh()
T = FakeTools(quest=[(39, KING)])
T.after_levels = {r: (0, 133) for r in rebirth.ALL_ROLES}
check('轉生後轉數沒變 → 88', quiet(rebirth.run, trans=1, from_stage='rebirth', to_stage='rebirth', tools=T) == 88)

# ---- 龍王 / 收尾 ----
fresh()
T = FakeTools(quest=[(37, (32011, 56, 36))], use_rcs=[92, 0])
rc = quiet(rebirth.run, trans=1, from_stage='boss10', to_stage='boss10', tools=T)
check('龍王：背包沒有(92)→ 公共倉庫取出 → 再使用', ('bag_take', 'DKBO', '龍王的守護') in T.calls and T.names().count('bag_use') == 2 and rc == 0)
fresh()
T = FakeTools(quest=[(37, (32011, 56, 36))], use_rcs=[95])
rc = quiet(rebirth.run, trans=1, from_stage='boss10', to_stage='boss10', tools=T)
check('龍王使用失敗只警告、流程繼續', rc == 0 and any('龍王' in w for w in rebirth.LAST['warnings']))
fresh()
T = FakeTools(quest=[(0, (32010, 1, 1)), (37, (32011, 56, 36))])
rc = quiet(rebirth.run, trans=1, from_stage='boss10', to_stage='boss10', tools=T)
check('boss10：第一段逾時（回 0 沒進 11F）→ 強制再吃龍王再跑一段', rc == 0 and T.names().count('bag_use') >= 2)
fresh()
T = FakeTools(store_rc=92)
check('cleanup：龍王背包沒有(92)視為略過', quiet(rebirth.run, trans=1, from_stage='cleanup', to_stage='cleanup', tools=T) == 0)
fresh()
T = FakeTools(store_rc=94)
check('cleanup：存回失敗(94)→ 86', quiet(rebirth.run, trans=1, from_stage='cleanup', to_stage='cleanup', tools=T) == 86)
fresh()
T = FakeTools(drop_rc=73)
check('cleanup：丟烏力斯坦失敗 → 86，且不繼續存龍王', quiet(rebirth.run, trans=1, from_stage='cleanup', to_stage='cleanup', tools=T) == 86 and 'bag_store' not in T.names())
fresh()
T = FakeTools(swap_rc=96)
check('swap：失敗 → 86', quiet(rebirth.run, trans=1, from_stage='swap', to_stage='swap', tools=T) == 86 and T.names().count('swap_weapon') == 1)
fresh()
T = FakeTools(quest=[(37, (32021, 29, 57))], ass_rc=(4, {'normal': None}, '讀回 None'))
rc = quiet(rebirth.run, trans=1, from_stage='heal', to_stage='heal', tools=T)
check('ass 回 4 且讀回 None → 警告不算失敗', rc == 0 and any('OCR' in w for w in rebirth.LAST['warnings']) and T.names().count('ass_pet') == 5, str(rc))
fresh()
T = FakeTools(ass_rc=(4, {'normal': '攻擊'}, '讀回攻擊'))
check('ass 回 4 但讀回別的值 → 87', quiet(rebirth.run, trans=1, from_stage='heal', to_stage='heal', tools=T) == 87)
fresh()
T = FakeTools(quest=[(37, (32021, 29, 57))])
rc = quiet(rebirth.run, trans=1, from_stage='heal', to_stage='heal', pet_action='none', tools=T)
check('--pet-action none 不動外掛', 'ass_pet' not in T.names())

# ================= FakeBag（bag.py 防護）=================
class FakeBag:
    KIND = {'精靈王之弓': 'equip', '合成弓箭 9': 'equip', '龍王的守護': 'stack', '大地的羈絆': 'single'}

    def __init__(self, items, weapon='合成弓箭 9'):
        self.slots = list(items) + [None] * (15 - len(items))
        self.depot = [None] * 20
        self.weapon = weapon
        self.page, self.role, self.popup, self.confirm = 'bag', 'DKBO', None, None
        self.clicks, self.discarded, self.used = [], [], 0
        self.open = True
        self.confirm_style = 'pet'                         # 'pet' = pet.CONFIRM 版 / 'drop2' = 丟棄 613,543 版
        self.names_shown = True                           # 「顯示道具名」開關（False = 格子只有圖示，名稱 OCR 全空）

    def install(self):
        bag.load_icons = lambda: {}                       # 假背包沒有真實圖示像素：走名稱 OCR / 彈窗核對的舊路徑
        uikit.preflight = lambda src, fast=True: 0
        uikit.sleep = lambda s: None
        uikit.snap = lambda tag: None
        uikit.fail = lambda src, rc, msg: (print(f'{src}: {msg}', file=sys.stderr), rc)[1]
        uikit.is_open = self.is_open
        uikit.gui = self.gui
        uikit.ocr = self.ocr
        uikit.ocr_lines = lambda box, *o: [{'text': t} for t in self.ocr(box, *o)]   # 絕不呼叫真的 ocr.ps1（會截遊戲畫面）
        uikit.px = self.px
        uikit.open_panel_ex = lambda p, **k: (True, True)
        uikit.close_panel = lambda p, known_open=False: True
        bag._avatar_sel = lambda role: self.role == role
        bag._sub_on = lambda sub: True
        bag._buff_icon = lambda: True
        return self

    def is_open(self, p):
        if p.name == 'PETCONFIRM':
            return self.confirm is not None and self.confirm_style == 'pet'
        if p.name == 'BAGDROP2':
            return self.confirm is not None and self.confirm_style == 'drop2'
        if self.confirm is not None:
            return False
        if p.name == 'BAGPOPUP':
            return self.popup is not None
        if self.popup is not None:
            return False
        return {'BAGANY': True, 'BAG': self.page == 'bag', 'BAGDEPOT': self.page == 'depot'}.get(p.name, False)

    def slot_at(self, x, y):
        for i in range(15):
            sx, sy = bag.slot_xy(i)
            if abs(x - sx) < 50 and abs(y - sy) < 50:
                return i
        return None

    def px(self, pts):
        """背包格內的點：空格回空格棕、有道具回紅；其他點回黑"""
        out = []
        for x, y in pts:
            i = self.slot_at(x, y) if self.page == 'bag' and self.popup is None else None
            out.append((0, 0, 0) if i is None else (bag.SLOT_EMPTY if self.slots[i] is None else (200, 40, 40)))
        return out

    def gui(self, *args, note=''):
        cmd = args[1] if args and args[0] == 'seq' else ''
        m = re.match(r'click (\d+) (\d+)', cmd)
        if cmd.startswith('key {ESC}'):
            self.popup = None
        elif m:
            self.click(int(m[1]), int(m[2]))
        return ''

    def click(self, x, y):
        self.clicks.append((x, y))
        if self.confirm is not None:
            ok = (abs(x - 613) < 8 and abs(y - 543) < 8) if self.confirm_style == 'drop2' else (abs(x - 612) < 8 and abs(y - 551) < 8)
            if ok:
                name = self.confirm
                self.discarded.append(name)
                if name in self.slots:
                    self.slots[self.slots.index(name)] = None
            self.confirm = None
            return
        if self.popup is not None:
            name, kind = self.popup
            if kind == 'equip' and (x, y) == (618, 662):                      # 穿戴
                i = self.slots.index(name)
                self.slots[i], self.weapon = self.weapon, name
                self.popup = None
            elif kind == 'equip' and (x, y) == (826, 662):                    # 丟棄
                self.popup, self.confirm = None, name
            elif kind == 'stack' and (x, y) == (618, 648):
                self.used += 1
                self.popup = None
            return
        if (x, y) == bag.NAMES_BTN:
            self.names_shown = not self.names_shown
            return
        if (x, y) == bag.WEAPON_SLOT:
            if self.weapon:
                self.popup = (self.weapon, 'equip')
            return
        if 83 == x:
            self.role = [r for r, yy in __import__('petmatch').AVATAR_Y.items() if yy == y][0]
            return
        i = self.slot_at(x, y)
        if i is not None and self.slots[i]:
            self.popup = (self.slots[i], self.KIND.get(self.slots[i], 'single'))

    def ocr(self, box, *opts):
        import pet
        box = tuple(box)
        if box == bag.POPUP_NAME_BOX:
            return [self.popup[0]] if self.popup else []
        if box == bag.POPUP_BTN_BOX:
            return {'equip': ['穿戴', '丟棄'], 'stack': ['使用', '更多'], 'single': ['使用']}.get(self.popup[1], []) if self.popup else []
        if box in (pet.CONFIRM_BOX, bag.DROP2_NAME_BOX) and box == (pet.CONFIRM_BOX if self.confirm_style == 'pet' else bag.DROP2_NAME_BOX):
            return [f'確定要丟棄 {self.confirm} ?'] if self.confirm else []
        if box == bag.NAME_BOX:
            return [self.role]
        if box == bag.LEVEL_BOX:
            return ['0轉133級']
        for i in range(15):
            sx, sy = bag.slot_xy(i)
            dx, dy, w, h = bag.SLOT_NAME_R
            if box == (sx - dx, sy - dy, w, h):
                return [self.slots[i]] if self.slots[i] and self.names_shown else []
        return []


fb = FakeBag(['龍王的守護', '精靈王之弓', '大地的羈絆']).install()
rc = quiet(bag.swap_weapon, 'DKBO')
check('swap_weapon：穿弓、舊武器丟掉、弓還在武器格', rc == 0 and fb.weapon == '精靈王之弓' and fb.discarded == ['合成弓箭 9'] and '精靈王之弓' not in fb.discarded and '合成弓箭 9' not in fb.slots)
check('swap_weapon：丟棄鈕只在彈窗名稱核對後才點（826,662 恰 1 次）', fb.clicks.count((826, 662)) == 1)

fb = FakeBag(['龍王的守護', '精靈王之弓']).install()
rc = quiet(bag.swap_weapon, 'DKBO', keep_old=True)
check('--keep-old-weapon：不丟', rc == 0 and fb.discarded == [] and '合成弓箭 9' in fb.slots and (826, 662) not in fb.clicks)

fb = FakeBag(['精靈王之弓'], weapon='精靈王之弓').install()
rc = quiet(bag.swap_weapon, 'DKBO')
check('武器格已是弓 + 背包多一把 → 丟背包那把（allow_protected），武器格不動', rc == 0 and fb.discarded == ['精靈王之弓'] and fb.weapon == '精靈王之弓'
      and '精靈王之弓' not in fb.slots and (618, 662) not in fb.clicks and bag.LAST.get('already') and bag.LAST.get('spare') == 1, str(fb.discarded))
fb = FakeBag(['龍王的守護'], weapon='精靈王之弓').install()
rc = quiet(bag.swap_weapon, 'DKBO')
check('武器格已是弓 + 背包沒有弓 → 不丟（續跑安全）', rc == 0 and fb.discarded == [] and bag.LAST.get('spare') == 0)
fb = FakeBag(['精靈王之弓'], weapon='精靈王之弓').install()
rc = quiet(bag.swap_weapon, 'DKBO', keep_old=True)
check('已是弓 + --keep-old-weapon → 多的也不丟', rc == 0 and fb.discarded == [])
fb = FakeBag(['精靈王之弓'], weapon='合成弓箭 9').install()
rc = quiet(bag.drop_spare_bow, 'DKBO')
check('drop_spare_bow：武器格不是弓 → 93 不丟（背包那把可能是唯一一把）', rc == bag.EXIT_GUARD and fb.discarded == [])
fb = FakeBag(['精靈王之弓'], weapon='精靈王之弓').install()
rc = quiet(bag.drop_spare_bow, 'DKBO')
check('drop_spare_bow：武器格是弓 → 丟 1 把', rc == 0 and fb.discarded == ['精靈王之弓'] and fb.weapon == '精靈王之弓')

fb = FakeBag(['龍王的守護']).install()
check('背包沒有弓 → 92，沒點穿戴 / 丟棄', quiet(bag.swap_weapon, 'DKBO') == 92 and (618, 662) not in fb.clicks and (826, 662) not in fb.clicks)

# 防護：要丟的名稱是弓 / 彈窗名稱對不上
fb = FakeBag(['精靈王之弓']).install()
check('discard_item：expect 是弓 → 93，零點擊', quiet(bag.discard_item, 'DKBO', 0, '精靈王之弓') == 93 and fb.clicks == [])
fb = FakeBag(['精靈王之弓']).install()
check('discard_item：彈窗實際是弓、預期是合成弓箭 → 96，沒按丟棄', quiet(bag.discard_item, 'DKBO', 0, '合成弓箭 9') == 96 and (826, 662) not in fb.clicks and fb.discarded == [])
fb = FakeBag(['合成弓箭 9']).install()
check('discard_item：名稱相符 → 丟掉', quiet(bag.discard_item, 'DKBO', 0, '合成弓箭 9') == 0 and fb.discarded == ['合成弓箭 9'])
fb = FakeBag(['合成弓箭 9']).install()
fb = FakeBag(['精靈王之弓', '合成弓箭 9']).install()
fb.confirm_style = 'drop2'
check('discard_item：drop2 版提示窗（丟棄 613,543）名稱相符 → 丟掉、點 613,543', quiet(bag.discard_item, 'DKBO', 1, '合成弓箭 9') == 0 and fb.discarded == ['合成弓箭 9'] and (613, 543) in fb.clicks and bag.LAST.get('drop_confirm') == 'drop2')
fb = FakeBag(['精靈王之弓', '合成弓箭 9']).install()
fb.confirm_style = 'drop2'
_o = fb.ocr
fb.ocr = lambda box, *o: ['精靈王之弓'] if tuple(box) == bag.DROP2_NAME_BOX else _o(box, *o)
uikit.ocr = fb.ocr
check('discard_item：drop2 版提示窗名稱對不上 → 96、點取消 820,543、沒丟', quiet(bag.discard_item, 'DKBO', 1, '合成弓箭 9') == 96 and (820, 543) in fb.clicks and (613, 543) not in fb.clicks and fb.discarded == [])
# 真截圖 fixture：丟棄提示窗另一版型（2026-10-12 22:17 實機）：DROP2 特徵吻合、舊 pet.CONFIRM 不吻合；單鈕刪除提示窗也不吻合
_drop_png = HERE.parent / '.cache' / 'ui-log' / '221743-bag-drop-noconfirm.png'
if _drop_png.exists():
    import questdetail as _qd
    import screen_sigs as _ss
    import pet as _pet
    _im = _qd.Img.from_file(_drop_png)
    _m = lambda sig: all(_ss.close(_im(x, y), (r, g, b), t) for x, y, r, g, b, t in sig)
    check('fixture：221743 drop2 特徵吻合 / pet.CONFIRM 與單鈕刪除窗不吻合', _m(bag.DROP2_SIG) and not _m(_pet.CONFIRM_SIG) and not _m(bag.DELCONFIRM_SIG))
else:
    print('SKIP fixture 221743（缺檔）')
check('discard_item：forbid 含該名 → 93', quiet(bag.discard_item, 'DKBO', 0, '合成弓箭 9', ['合成弓箭 9']) == 93 and fb.discarded == [])
# 提示窗名稱不符（彈窗對、提示窗被換成弓）→ 取消
fb = FakeBag(['合成弓箭 9']).install()
orig_ocr = fb.ocr


def bad_confirm_ocr(box, *o):
    import pet
    if tuple(box) == pet.CONFIRM_BOX:
        return ['確定要丟棄 精靈王之弓 ?']
    return orig_ocr(box, *o)


uikit.ocr = bad_confirm_ocr
rc = quiet(bag.discard_item, 'DKBO', 0, '合成弓箭 9')
check('提示窗名稱是弓 → 96、不按確定（取消）', rc == 96 and fb.discarded == [] and (612, 551) not in fb.clicks and (813, 557) in fb.clicks)
fb = FakeBag(['合成弓箭 9']).install()
check('drop_item：--confirm-name 不同 → 93', quiet(bag.drop_item, 'DKBO', '合成弓箭 9', '別的') == 93 and fb.clicks == [])
fb = FakeBag(['龍王的守護']).install()
check('depot_store：保護名單（弓）→ 93', quiet(bag.depot_store, 'DKBO', '精靈王之弓') == 93)

# 龍王使用
fb = FakeBag(['大地的羈絆', '龍王的守護']).install()
check('use_item：找到龍王、彈窗核對、按使用（618,648）', quiet(bag.use_item, 'DKBO', '龍王的守護', True) == 0 and fb.used == 1 and fb.clicks[-1] == (618, 648))
fb = FakeBag(['大地的羈絆']).install()
check('use_item：沒有 → 92，沒點使用', quiet(bag.use_item, 'DKBO', '龍王的守護') == 92 and fb.used == 0)
fb = FakeBag(['龍王的守護']).install()
fb.KIND = dict(FakeBag.KIND)
uikit_ocr = fb.ocr
uikit.ocr = lambda box, *o: (['大地的羈絆'] if tuple(box) == bag.POPUP_NAME_BOX else uikit_ocr(box, *o))
check('use_item：彈窗名稱不符 → 96，不使用', quiet(bag.use_item, 'DKBO', '龍王的守護') == 96 and fb.used == 0)

# 證明 / 等級讀取
fb = FakeBag(['大地的羈絆', None, '龍王的守護']).install()
rc, d = quiet(bag.find_items, 'DKBO', ['大地的羈絆', '水的戒指'])
check('find_items：找到 / 沒找到 / 空格數', rc == 0 and d['大地的羈絆'] == 0 and d['水的戒指'] is None and d['_free'] == 13, str(d))
check('find_items：名稱開著不點開關', bag.NAMES_BTN not in fb.clicks)
# 2026-10-12 S3：「顯示道具名」被關 → 舊版回全 null、_free 15；現在像素判空格 + 點開關一次再讀
fb = FakeBag(['大地的羈絆', None, '龍王的守護']).install()
fb.names_shown = False
rc, d = quiet(bag.find_items, 'DKBO', ['大地的羈絆', '龍王的守護', '水的戒指'])
check('find_items：名稱被關 → 點開關 1 次、找到、空格數用像素', rc == 0 and d['大地的羈絆'] == 0 and d['龍王的守護'] == 2 and d['水的戒指'] is None
      and d['_free'] == 13 and fb.clicks.count(bag.NAMES_BTN) == 1 and fb.names_shown and d['_unread'] == [], str(d))
fb = FakeBag([]).install()
rc, d = quiet(bag.find_items, 'DKBO', ['大地的羈絆'])
check('find_items：全空 → _free 15、不點開關', rc == 0 and d['_free'] == 15 and d['大地的羈絆'] is None and bag.NAMES_BTN not in fb.clicks, str(d))
fb = FakeBag(['大地的羈絆']).install()
fb.names_shown = False
fb.click = (lambda orig: (lambda x, y: None if (x, y) == bag.NAMES_BTN else orig(x, y)))(fb.click)   # 開關點了沒反應
rc, d = quiet(bag.find_items, 'DKBO', ['大地的羈絆'])
check('find_items：開關點了沒反應 → 不重點、回 _unread', rc == 0 and d['大地的羈絆'] is None and d['_unread'] == [0] and d['_free'] == 14, str(d))
check('names_hidden 純函式', bag.names_hidden([True, False], {0: ''}) and not bag.names_hidden([True, False], {0: '儀之兜'}) and not bag.names_hidden([False], {}))
# 實機像素樣本（fixtures/bag_slots_px.json）：名稱關 / 開兩種背包，空格判定要與人工標記一致
import json as _json
_fx = _json.loads((Path(__file__).resolve().parent / 'fixtures' / 'bag_slots_px.json').read_text(encoding='utf-8'))
for _name, _img in _fx['images'].items():
    _k = len(bag.SLOT_PROBE)
    _cols = [tuple(int(h[j:j + 2], 16) for j in (0, 2, 4)) for h in _img['px']]
    _occ = ''.join('X' if bag.slot_occupied(_cols[i * _k:(i + 1) * _k]) else '.' for i in range(15))
    check(f'slot_occupied 實機樣本 {_name}', _occ == _img['expect'], _occ)
rc, lv = quiet(bag.levels, ['DKBO', 'DKBO2'])
check('levels：兩人 (0,133)', rc == 0 and lv == {'DKBO': (0, 133), 'DKBO2': (0, 133)}, str(lv))

# ================= bag.py purge（刪除管理，2026-10-12）=================
B = ['巴巴洛的許可證']
check('del_entries：行串接、去 *數量、去「是否」行', bag.del_entries(['巴巴洛的許可證*1|千年龜', '的殼*1|', '是否批量刪除道具?']) == ['巴巴洛的許可證', '千年龜的殼'])
check('del_entries：丨（U+4E28）當分隔（2026-10-12 DKBO2 四條實機）', bag.del_entries(['薩頓家的秘藥*1|山賊的羽飾', '*1|杉的手環1丨月光的手鐲*1|', '是否捇量刪除道具?']) == ['薩頓家的秘藥', '山賊的羽飾', '杉的手環', '月光的手鐲'])
check('del_entry_name：完全 / 掉字（巴巴洛→巴洛）/ 掉 *', bag.del_entry_name('巴巴洛的許可證', B) and bag.del_entry_name('巴洛的許可證', B) and bag.del_entry_name('巴巴洛的許可證1', B))
check('del_entry_name：兩條黏在一起 / 名單外 / 保護道具 → None', bag.del_entry_name('巴巴洛的許可證千年龜的殼', B) is None
      and bag.del_entry_name('千年龜的殼', B) is None and bag.del_entry_name('精靈王之弓', ['精靈王之弓']) is None and bag.del_entry_name('大地的羈絆', ['大地的羈絆']) is None)
REAL = {'2': ['巴巴洛的許可證*1|', '是否刪除道具?'], '3': ['巴巴洛的許可證1|', '是否捇量刪除道具?']}       # 2026-10-12 DKBO2 實機 OCR
check('del_list_ok：實機 OCR（zoom 2 / 3）→ 過', bag.del_list_ok(REAL, B, 1)[0])
check('del_list_ok：多一條名單外 → 不過', not bag.del_list_ok({'2': ['巴巴洛的許可證*1|千年龜的殼*1|']}, B, 1)[0])
check('del_list_ok：條數 > 勾選數 → 不過', not bag.del_list_ok({'2': ['巴巴洛的許可證*1|巴巴洛的許可證*1|']}, B, 1)[0])
check('del_list_ok：條數 < 勾選數（每個 zoom 都少）→ 不過', not bag.del_list_ok({'2': ['巴巴洛的許可證*1|'], '3': ['巴巴洛的許可證1|']}, B, 2)[0])
check('del_list_ok：讀不到 → 不過', not bag.del_list_ok({'2': ['是否批量刪除道具?']}, B, 1)[0])
# 2026-10-14：3 種以上整行漏讀 / 馬祖的矛「1丐祖的矛」/ 空想的豎琴「的豎琴」被當風的豎琴 → 96（實樣 fixtures/bag_dellist_ocr.json）
check('del_entries：問句黏在清單同一行 → 截掉問句、清單保留', bag.del_entries(['馬祖的矛*1|是否批量刪除道具?']) == ['馬祖的矛'])
check("del_entries：* 讀成 + / '、數量掉、| 讀成 l", bag.del_entries(["儀之兜'1|亞姆亞姆的斧頭'龍", '的魅力之笛+1丨龍之槍*ll老爺爺', '的護身符+1|'])
      == ['儀之兜', '亞姆亞姆的斧頭', '龍的魅力之笛', '龍之槍', '老爺爺的護身符'])
_T = ['空想的豎琴', '馬祖的矛', '巴巴洛的許可證']
check('del_classify：1丐祖的矛 / 祖的矛 → 馬祖的矛', bag.del_classify('1丐祖的矛', _T) == ('target', '馬祖的矛') and bag.del_classify('祖的矛', _T) == ('target', '馬祖的矛'))
check('del_classify：「的豎琴」是空想的豎琴也是風的豎琴的片段 → unknown（不判保護、也不判勾選）', bag.del_classify('的豎琴', _T) == ('unknown', None))
check('del_classify：風的豎琴 / 黏著風的豎琴 / 2倍智慧果 → protected', bag.del_classify('風的豎琴', _T)[0] == 'protected'
      and bag.del_classify('空想的豎琴風的豎琴', _T)[0] == 'protected' and bag.del_classify('倍智慧果', _T)[0] == 'protected')
check('del_classify：名單外的真道具（龍之鎧）→ other', bag.del_classify('龍之鎧', ['龍之槍']) == ('other', '龍之鎧'))
check('del_list_ok：「的豎琴」單獨 → 不過；別的 zoom 讀到全名 → 過',
      not bag.del_list_ok({'2': ['的豎琴*1|']}, ['空想的豎琴'], 1)[0] and bag.del_list_ok({'2': ['的豎琴*1|'], '3': ['空想的豎琴*1|']}, ['空想的豎琴'], 1)[0])
check('del_list_ok：任何 zoom 讀到保護道具 → 不過', not bag.del_list_ok({'2': ['空想的豎琴*1|'], '3': ['風的豎琴*1|']}, ['空想的豎琴'], 1)[0])
check('del_list_ok：兩個候選 zoom 同位置判成不同名稱 → 不過',
      not bag.del_list_ok({'2': ['龍之槍*1|龍之鎧*1|'], '3': ['龍之鎧*1|龍之槍*1|']}, ['龍之槍', '龍之鎧'], 2)[0])
_DL = _json.loads((Path(__file__).resolve().parent / 'fixtures' / 'bag_dellist_ocr.json').read_text(encoding='utf-8'))['cases']
for _name, _c in _DL.items():
    _n = _c['names']
    _g = {k: v for k, v in _c['readings'].items() if k.startswith('g')}
    check(f'del_list_ok 實樣 {_name}：兩輪 / 只有綠字一輪都過', bag.del_list_ok(_c['readings'], _n, len(_n))[0] and bag.del_list_ok(_g, _n, len(_n))[0],
          str(bag.del_list_ok(_c['readings'], _n, len(_n))))
_c = _DL['062858-5items']
_d = {k: v for k, v in _c['readings'].items() if k.startswith('d')}
check('del_list_ok 實樣：不二值化一輪 zoom 2/3/5 漏中間行 → 只採沒漏行的 zoom 4，仍過', bag.del_list_ok(_d, _c['names'], 5)[0])
check('del_list_ok 實樣：漏行的 zoom 單獨 → 不過（舊版 96 的情況，不會誤過）', not bag.del_list_ok({'d2': _d['d2']}, _c['names'], 5)[0])
_c = _DL['062554-6items']
check('del_list_ok 實樣：名單把龍之鎧換成龍之槍 → 不過', not bag.del_list_ok(_c['readings'], [n.replace('龍之鎧', '龍之槍') for n in _c['names']], 6)[0])
check('del_list_ok 實樣：馬祖的矛當成馬祖的斧頭 → 不過；勾選數 2 → 不過',
      not bag.del_list_ok(_DL['mazu-spear']['readings'], ['馬祖的斧頭'], 1)[0] and not bag.del_list_ok(_DL['mazu-spear']['readings'], ['馬祖的矛'] * 2, 2)[0])
_calls = []
_orig_ol = uikit.ocr_lines
uikit.ocr_lines = lambda box, *o: (_calls.append(o[0]), [{'text': '的豎琴*1|', 'y': 369, 'zoom': 2}] if o[0] == '-Green' else [{'text': '空想的豎琴*1|', 'y': 369, 'zoom': 2}, {'text': '是否批量刪除道具?', 'y': 447, 'zoom': 2}])[1]
_ok, _why, _rd = bag.del_list_check(['空想的豎琴'], 1)
check('del_list_check：綠字一輪判不過 → 加不二值化一輪合併判', _ok and _calls == ['-Green', '-Dark'] and set(_rd) == {'g2', 'd2'}, str((_ok, _why, _calls)))
uikit.ocr_lines = _orig_ol
check('purge_target：名單內 / 名單外 / 保護', bag.purge_target('巴巴洛的許 可證 巴巴洛的許 可證', B) == '巴巴洛的許可證'
      and bag.purge_target('千年龜的殼', B) is None and bag.purge_target('精靈王之弓', ['精靈王之弓']) is None)
_mk = _json.loads((Path(__file__).resolve().parent / 'fixtures' / 'bag_mark_px.json').read_text(encoding='utf-8'))
for _name, _img in _mk['images'].items():
    _k = len(bag.MARK_PROBE)
    _cols = [tuple(int(h[j:j + 2], 16) for j in (0, 2, 4)) for h in _img['px']]
    _got = ''.join('X' if bag.slot_marked(_cols[i * _k:(i + 1) * _k]) else '.' for i in range(15))
    check(f'slot_marked 實機樣本 {_name}', _got == _img['expect'], _got)


class FakeDelBag(FakeBag):
    """FakeBag + 刪除模式：DEL_BTN 進模式 / 刪除選中、單擊格子勾選、提示窗清單、確定刪掉勾的格；roles = {角色: 格子清單}"""

    def __init__(self, roles, list_override=None, drop_first_mark=False):
        super().__init__(roles[next(iter(roles))])
        self.bags = {r: list(v) + [None] * (15 - len(v)) for r, v in roles.items()}
        self.role = next(iter(roles))
        self.slots = self.bags[self.role]
        self.mode, self.marks, self.delconfirm = 'normal', set(), False
        self.list_override, self.drop_first_mark, self.dropped_once = list_override, drop_first_mark, False
        self.deleted = []

    def is_open(self, p):
        if self.delconfirm:
            return p.name == 'BAGDELOK'
        if p.name == 'BAGDELOK':
            return False
        if p.name == 'BAGDEL':
            return self.mode == 'del'
        if self.mode == 'del':
            return False                              # 刪除模式下普通背包特徵（整理背包藍鈕）不在
        return super().is_open(p)

    def px(self, pts):
        out = []
        for x, y in pts:
            hit = None
            for i in range(15):
                sx, sy = bag.slot_xy(i)
                if 20 <= x - sx <= 38 and -36 <= y - sy <= -18:
                    hit = i
            if hit is not None and self.mode == 'del':
                out.append((243, 69, 84) if hit in self.marks else (255, 255, 255))
            elif hit is not None:
                out.append((255, 255, 255))
            else:
                out += super().px([(x, y)])
        return out

    def click(self, x, y):
        self.clicks.append((x, y))
        if self.delconfirm:
            if (x, y) == bag.DELOK_XY:
                for i in sorted(self.marks):
                    self.deleted.append(self.slots[i])
                    self.slots[i] = None
                self.marks.clear()
            self.delconfirm = False
            return
        if self.mode == 'del':
            if (x, y) == bag.DEL_BTN:
                self.delconfirm = bool(self.marks)
            elif (x, y) == bag.DEL_CANCEL:
                self.mode, self.marks = 'normal', set()
            else:
                i = self.slot_at(x, y)
                if i is not None and self.slots[i]:
                    if self.drop_first_mark and not self.dropped_once:
                        self.dropped_once = True              # 勾選偶爾沒吃到
                        return
                    self.marks ^= {i}
            return
        if (x, y) == bag.DEL_BTN:
            self.mode = 'del'
            return
        if x == 83:
            super().click(x, y)
            self.slots = self.bags[self.role]
            return
        super().click(x, y)

    def ocr(self, box, *opts):
        if tuple(box) == bag.DEL_LIST_BOX:
            if not self.delconfirm:
                return []
            if self.list_override is not None:
                return list(self.list_override)
            return [''.join(f'{self.slots[i]}*1|' for i in sorted(self.marks)), '是否批量刪除道具?']
        return super().ocr(box, *opts)


W = ['薩頓家的秘藥', '千年龜的殼', '巴巴洛的許可證', '月光的手鐲']
fb = FakeDelBag({'DKBO2': W}).install()
rc, d = quiet(bag.purge, ['DKBO2'], B)
check('purge：只勾巴巴洛、確定、回普通模式、其他格不動', rc == 0 and fb.deleted == ['巴巴洛的許可證'] and fb.mode == 'normal'
      and fb.slots[:4] == ['薩頓家的秘藥', '千年龜的殼', None, '月光的手鐲'] and d['DKBO2']['deleted'] == B, str((rc, d, fb.deleted)))
fb = FakeDelBag({'DKBO2': W, 'DKBO3': ['巴巴洛的許可證', '千年龜的殼'], 'DKBO4': ['千年龜的殼']}).install()
rc, d = quiet(bag.purge, ['DKBO2', 'DKBO3', 'DKBO4'], B)
check('purge 多人：面板開一次逐人切、沒有的人 targets 空', rc == 0 and fb.deleted == ['巴巴洛的許可證'] * 2 and d['DKBO4']['targets'] == {} and fb.bags['DKBO4'][0] == '千年龜的殼')
fb = FakeDelBag({'DKBO2': W}).install()
rc, d = quiet(bag.purge, ['DKBO2'], ['巴巴洛的許可證', '精靈王之弓'])
check('purge：名單含精靈王之弓 → 93、零點擊', rc == 93 and fb.clicks == [] and fb.deleted == [])
fb = FakeDelBag({'DKBO2': W}).install()
rc, d = quiet(bag.purge, ['DKBO2'], ['巴巴洛的許可證', '大地的羈絆'])
check('purge：名單含四大洞窟產物 → 93、零點擊', rc == 93 and fb.clicks == [])
fb = FakeDelBag({'DKBO2': W}, list_override=['巴巴洛的許可證*1|千年龜的殼*1|', '是否批量刪除道具?']).install()
rc, d = quiet(bag.purge, ['DKBO2'], B)
check('purge：提示窗多一條名單外 → 96、按 X、取消刪除、沒刪', rc == 96 and fb.deleted == [] and bag.DELX_XY in fb.clicks and bag.DELOK_XY not in fb.clicks and fb.mode == 'normal')
fb = FakeDelBag({'DKBO2': W}, list_override=['巴洛的許可證1|', '是否量刪除道具?、']).install()
rc, d = quiet(bag.purge, ['DKBO2'], B)
check('purge：OCR 掉字 / 掉 * 仍過', rc == 0 and fb.deleted == B)
fb = FakeDelBag({'DKBO2': W}, list_override=['風的豎琴*1|', '是否批量刪除道具?']).install()
_snaps = []
uikit.snap = lambda tag: (_snaps.append((tag, fb.delconfirm)), None)[1]
rc, d = quiet(bag.purge, ['DKBO2'], B)
check('purge：核對不過 → 提示窗還開著時存圖、再按 X、96', rc == 96 and _snaps == [('bag-purge-list-DKBO2', True)] and fb.deleted == [] and bag.DELX_XY in fb.clicks, str(_snaps))
fb = FakeDelBag({'DKBO2': W}, drop_first_mark=True).install()
rc, d = quiet(bag.purge, ['DKBO2'], B)
check('purge：第一下勾沒吃到 → 補點一次成功', rc == 0 and fb.deleted == B and fb.clicks.count(bag.slot_xy(2)) == 2)
fb = FakeDelBag({'DKBO2': W}).install()
_c = fb.click
def _stuck(x, y):
    _c(x, y)
    if (x, y) == bag.DEL_BTN and fb.mode == 'del' and not fb.delconfirm:
        fb.marks.add(1)                                       # 一進模式就有別格（千年龜的殼）被勾
fb.click = _stuck
rc, d = quiet(bag.purge, ['DKBO2'], B)
check('purge：進模式就有名單外的勾 → 93、取消、沒刪', rc == 93 and fb.deleted == [] and fb.mode == 'normal' and bag.DELOK_XY not in fb.clicks)
fb = FakeDelBag({'DKBO2': W}).install()
rc, d = quiet(bag.purge, ['DKBO2'], B, True)
check('purge --dry-run：列出目標、不按刪除管理', rc == 0 and d['DKBO2']['targets'] == {2: '巴巴洛的許可證'} and bag.DEL_BTN not in fb.clicks and fb.deleted == [])
try:
    uikit.check_forbidden(bag.DELMODE, *bag.DEL_BTN)
    check('DELMODE 刪除選中鈕是禁區（沒 allow 會擋）', False)
except uikit.ForbiddenClick:
    check('DELMODE 刪除選中鈕是禁區（沒 allow 會擋）', True)

# ================= petdrop =================
check('guard_target：第 1 格 / 騎乘 / 出戰 / 騎寵名 / 名字不符 / 正常',
      petdrop.guard_target({'slot': 1, 'name': '烏力斯坦', 'state': '等待'}, '烏力斯坦') is not None
      and petdrop.guard_target({'slot': 3, 'name': '烏力斯坦', 'state': '騎乘'}, '烏力斯坦') is not None
      and petdrop.guard_target({'slot': 3, 'name': '烏力斯坦', 'state': '出戰'}, '烏力斯坦') is not None
      and petdrop.guard_target({'slot': 2, 'name': '瑪斯貝卡', 'state': '等待'}, '烏力斯坦') is not None
      and petdrop.guard_target({'slot': 2, 'name': '迪基格斯', 'state': '等待'}, '烏力斯坦') is not None
      and petdrop.guard_target({'slot': 3, 'name': '烏力斯坦', 'state': '等待'}, '烏力斯坦') is None)


class FakePets:
    """替換 pet.list_role / scan_frames / select_slot / read_slot / CONFIRM，驗 drop_role 流程與防護"""

    def __init__(self, slots, confirm_text='確定要丟棄【烏力斯坦】嗎? 回收站保存48小時!'):
        self.slots, self.sel, self.confirm_open = slots, None, False
        self.confirm_text, self.clicks = confirm_text, []
        import pet
        self.pet = pet
        pet.list_role = lambda role, ctx: (0, [dict(s) for s in self.slots])
        pet.scan_frames = lambda: {'sel': [False] * 5, 'empty': [bool(s.get('empty')) for s in self.slots] + [True] * (5 - len(self.slots))}
        pet.select_slot = lambda i, f: (setattr(self, 'sel', i), 0)[1]
        pet.read_slot = lambda i, ctx: dict(self.slots[i])
        uikit.preflight = lambda *a, **k: 0
        uikit.sleep = lambda s: None
        uikit.snap = lambda tag: None
        uikit.fail = lambda src, rc, msg: (print(f'{src}: {msg}', file=sys.stderr), rc)[1]
        uikit.is_open = lambda p: self.confirm_open if p.name == 'PETCONFIRM' else True
        uikit.safe_click = self.click
        uikit.ocr = lambda box, *o: [self.confirm_text] if self.confirm_open else []

    def click(self, x, y, panel, note='', allow=(), wait_ms=300):
        uikit.check_forbidden(panel, x, y, allow)
        self.clicks.append((x, y))
        if (x, y) == petdrop.TRASH_XY:
            self.confirm_open = True
        elif self.confirm_open:
            if (x, y) == petdrop.CONFIRM_OK:
                self.slots[self.sel] = {'slot': self.sel + 1, 'empty': True}
            self.confirm_open = False
        return True


PETS = [{'slot': 1, 'name': '瑪斯貝卡', 'state': '騎乘'}, {'slot': 2, 'name': '迪基格斯', 'state': '出戰'}, {'slot': 3, 'name': '烏力斯坦', 'state': '等待'}]
fp = FakePets([dict(s) for s in PETS])
rc = quiet(petdrop.drop_role, 'DKBO', '烏力斯坦', {})
check('petdrop：只丟第 3 格烏力斯坦（垃圾桶 1 次、確定 1 次）', rc == 0 and fp.slots[2].get('empty') and fp.slots[0]['name'] == '瑪斯貝卡' and fp.clicks == [petdrop.TRASH_XY, petdrop.CONFIRM_OK], str(fp.clicks))
fp = FakePets([dict(s) for s in PETS], confirm_text='確定要丟棄【瑪斯貝卡】嗎? 回收站保存48小時!')
rc = quiet(petdrop.drop_role, 'DKBO', '烏力斯坦', {})
check('petdrop：提示窗名稱是騎寵 → 76、按取消不按確定', rc == 76 and petdrop.CONFIRM_OK not in fp.clicks and petdrop.CONFIRM_CANCEL in fp.clicks and not fp.slots[2].get('empty'))
fp = FakePets([dict(s) for s in PETS], confirm_text='')
check('petdrop：提示窗讀不到文字 → 76 不丟', quiet(petdrop.drop_role, 'DKBO', '烏力斯坦', {}) == 76 and petdrop.CONFIRM_OK not in fp.clicks)
fp = FakePets([dict(s) for s in PETS[:2]])
check('petdrop：沒有這隻 = 已完成（0、零點擊）', quiet(petdrop.drop_role, 'DKBO', '烏力斯坦', {}) == 0 and fp.clicks == [])
fp = FakePets(PETS[:2] + [{'slot': 3, 'name': '烏力斯坦', 'state': '等待'}, {'slot': 4, 'name': '烏力斯坦', 'state': '等待'}])
check('petdrop：同名兩隻沒給 --slot → 79', quiet(petdrop.drop_role, 'DKBO', '烏力斯坦', {}) == 79 and fp.clicks == [])
fp = FakePets([dict(s) for s in PETS])
check('petdrop：--dry-run 零點擊', quiet(petdrop.drop_role, 'DKBO', '烏力斯坦', {}, None, True) == 0 and fp.clicks == [])
check('petdrop.drop：confirm-name 不同 → 1', quiet(petdrop.drop, 'DKBO', '烏力斯坦', '別的') == 1)
# --max-level（questrun --drop-reward 固定 1：剛拿到的獎勵寵 1 級，練過的同名寵不丟）
check('guard_target max_level：1 級可丟、12 級擋、等級讀不出擋、不給 = 不看等級',
      petdrop.guard_target({'slot': 3, 'name': '左迪洛斯', 'state': '等待', 'level': 1}, '左迪洛斯', 1) is None
      and '12 > 1' in (petdrop.guard_target({'slot': 3, 'name': '左迪洛斯', 'state': '等待', 'level': 12}, '左迪洛斯', 1) or '')
      and '讀不出' in (petdrop.guard_target({'slot': 3, 'name': '左迪洛斯', 'state': '等待', 'level': None}, '左迪洛斯', 1) or '')
      and petdrop.guard_target({'slot': 3, 'name': '左迪洛斯', 'state': '等待', 'level': 50}, '左迪洛斯') is None)
LV = [{'slot': 1, 'name': '瑪斯貝卡', 'state': '騎乘', 'level': 127}, {'slot': 2, 'name': '迪基格斯', 'state': '出戰', 'level': 129}]
fp = FakePets(LV + [{'slot': 3, 'name': '烏力斯坦', 'state': '等待', 'level': 30}])
check('petdrop max_level=1：30 級 → 73 零點擊', quiet(petdrop.drop_role, 'DKBO', '烏力斯坦', {}, None, False, 1) == 73 and fp.clicks == [])
fp = FakePets(LV + [{'slot': 3, 'name': '烏力斯坦', 'state': '等待', 'level': 30}, {'slot': 4, 'name': '烏力斯坦', 'state': '等待', 'level': 1}])
rc = quiet(petdrop.drop_role, 'DKBO', '烏力斯坦', {}, None, False, 1)
check('petdrop max_level=1：同名 30 級 + 1 級 → 只丟第 4 格 1 級', rc == 0 and fp.slots[3].get('empty') and not fp.slots[2].get('empty'), str(fp.slots))
fp = FakePets(LV + [{'slot': 3, 'name': '烏力斯坦', 'state': '等待', 'level': 1}, {'slot': 4, 'name': '烏力斯坦', 'state': '等待', 'level': 1}])
check('petdrop max_level=1：兩隻都 1 級 → 79 不猜', quiet(petdrop.drop_role, 'DKBO', '烏力斯坦', {}, None, False, 1) == 79 and fp.clicks == [])


# ================= 2026-10-13 二轉實跑後續：accept 階段 / 卡住自動重登 / 獎勵寵 / team.form 9 重試 =================
import stuckrecover  # noqa: E402
import rebirth_steps  # noqa: E402

fresh()
T = FakeTools(quest=list(FULL_QUEST))
rc = quiet(rebirth.run, tools=T)
nm = T.names()
check('accept 階段在 preflight 之後、第一個 quest（enter）之前，帶轉數', ('accept', 1) in T.calls and nm.index('accept') > nm.index('heal') and nm.index('accept') < nm.index('quest'), str(nm[:12]))
fresh()
T = FakeTools(accept_rc=126)
rc = quiet(rebirth.run, trans=2, from_stage='accept', to_stage='accept', tools=T)
check('accept 失敗 → 97、不往下、info.accept_rc', rc == 97 and rebirth.LAST['info'].get('accept_rc') == 126 and 'quest' not in T.names())
fresh()
check('accept 遇驗證視窗 / 斷線 → 原碼 9 / 10', quiet(rebirth.run, trans=2, from_stage='accept', to_stage='accept', tools=FakeTools(accept_rc=9)) == 9
      and quiet(rebirth.run, trans=2, from_stage='accept', to_stage='accept', tools=FakeTools(accept_rc=10)) == 10)

# ---- 卡住自動重登 ----
fresh()
T = FakeTools(quest=[(19, None), (37, (32011, 56, 36))])
rc = quiet(rebirth.run, trans=2, from_stage='boss10', to_stage='boss10', tools=T, use_dragon=False)
check('boss10 quest 19 → 全員重登 1 次 → team.check → 重跑同指令 → 37 成功', rc == 0 and T.names().count('relogin') == 1 and T.names().count('quest') == 2
      and T.calls[[c[0] for c in T.calls].index('relogin') + 1][0] == 'team_check', str(T.names()))
fresh()
T = FakeTools(quest=[(42, None), (19, None), (19, None)])
rc = quiet(rebirth.run, trans=2, from_stage='boss10', to_stage='boss10', tools=T, use_dragon=False)
check('每階段最多重登 2 次：第 3 次卡住 → 84', rc == 84 and T.names().count('relogin') == 2 and T.names().count('quest') == 3, str(T.names()))
fresh()
T = FakeTools(quest=[(19, None)], relogin_rcs=[104])
rc = quiet(rebirth.run, trans=2, from_stage='boss10', to_stage='boss10', tools=T, use_dragon=False)
check('重登失敗（relogin 104）→ 84，info.relogin_rc', rc == 84 and rebirth.LAST['info'].get('relogin_rc') == 104 and T.names().count('quest') == 1)
fresh()
T = FakeTools(quest=[(19, None)], relogin_rcs=[9])
check('重登遇驗證視窗 9 → 原碼 9 停手', quiet(rebirth.run, trans=2, from_stage='boss10', to_stage='boss10', tools=T, use_dragon=False) == 9)
fresh()
T = FakeTools(quest=[(19, None), (37, (32011, 56, 36))], relogin_rcs=[105])
rc = quiet(rebirth.run, trans=2, from_stage='boss10', to_stage='boss10', tools=T, use_dragon=False)
check('relogin 105（隊伍不對）→ team.form 後續跑', rc == 0 and T.names().count('team_form') >= 1)
fresh()
T = FakeTools(quest=[(19, None), (37, (32011, 56, 36))], team_checks=[41, 0])
rc = quiet(rebirth.run, trans=2, from_stage='boss10', to_stage='boss10', tools=T, use_dragon=False)
check('重登後 team.check 非 0 → team.form', rc == 0 and T.names().count('team_form') == 1)
fresh()
T = FakeTools(quest=[(19, None), (37, (32011, 56, 36))])
rc = quiet(rebirth.run, trans=2, from_stage='boss10', to_stage='boss10', tools=T)
check('重登後重吃龍王（force）', rc == 0 and T.names().count('bag_use') == 2, str(T.names()))

# ---- boss20 備援 --fight 帶 --step 4（不靠追蹤文字 OCR）----
fresh()
T = FakeTools(quest=[(0, (32021, 31, 29)), (0, (32021, 31, 29))], levels={r: (1, 135) for r in rebirth.ALL_ROLES})
r_ = rebirth.Run(2, T, {'dragon': False})
T.pos = (32021, 29, 57)
T.walk = lambda *a, **k: (32020, 20, 11)
r_.backtracked = False
quiet(r_.backtrack_fight, 'boss20', lambda p: True, rebirth.MAP_20F)
fq = [c[1] for c in T.calls if c[0] == 'quest' and '--fight' in c[1]]
check('boss20 備援 quest.py --fight 帶 --step 4', fq and fq[0][fq[0].index('--step') + 1] == 4, str(fq))

# ---- 2026-10-13 三轉實跑寫回：preflight 先關遇敵、boss10 / bow16 以地圖為準 ----
check('floor_of：32001→1、32021→21、村子 / None → None', rebirth.floor_of((32001, 1, 1)) == 1 and rebirth.floor_of((32021, 29, 57)) == 21
      and rebirth.floor_of((1000, 1, 1)) is None and rebirth.floor_of(None) is None)
check('bow16_progress：16F todo、17～20F bow、21F boss20、村子 todo',
      [rebirth.bow16_progress(p_) for p_ in ((32016, 1, 1), (32017, 1, 1), (32020, 20, 11), (32021, 29, 57), (1000, 1, 1), None)] == ['todo', 'bow', 'bow', 'boss20', 'todo', 'todo'])
check('past_boss10：11F 以上才算（10F / 1F 不算）', rebirth.past_boss10((32011, 1, 1)) and rebirth.past_boss10((32016, 1, 1)) and not rebirth.past_boss10((32010, 1, 1)) and not rebirth.past_boss10(None))

fresh()
T = FakeTools()
rc = quiet(rebirth.run, tools=T, to_stage='preflight')
nm_ = T.names()
check('preflight：先關原地遇敵（在 current / team_form / levels 之前）', rc == 0 and 'enc_off' in nm_ and nm_.index('enc_off') < nm_.index('current') < nm_.index('team_form'), str(nm_[:6]))
class _EncFail(FakeTools):
    def encounter_off(self):
        raise RuntimeError('切換原地遇敵失敗')
fresh()
T = _EncFail()
check('preflight：關遇敵失敗 → 87，不讀等級', quiet(rebirth.run, trans=1, tools=T, to_stage='preflight') == 87 and 'levels' not in T.names())

fresh()
T = FakeTools(pos=(32010, 54, 31), quest=[(37, (32012, 5, 5))])
check('boss10：37 且已在 12F（地圖為準）→ 0', quiet(rebirth.run, trans=1, from_stage='boss10', to_stage='boss10', tools=T) == 0)
fresh()
T = FakeTools(pos=(32010, 54, 31), quest=[(37, (32010, 54, 31))])
check('boss10：37（戰鬥 0）但人還在 10F → 85，不往下', quiet(rebirth.run, trans=1, from_stage='boss10', to_stage='boss10', tools=T) == 85)

fresh()
T = FakeTools(pos=(32011, 56, 36), quest=[(37, (32021, 29, 57)), (39, (32021, 31, 29))])
rc = quiet(rebirth.run, trans=1, from_stage='bow16', tools=T)
qs = [c[1] for c in T.calls if c[0] == 'quest']
check('bow16 回 37 但人已在 21F（三轉 21:38）→ 記 boss20_done、swap 後跳過 heal / boss20 直接 rebirth → 0',
      rc == 0 and 'heal' not in T.names() and 'teleport20' not in T.names() and T.names().count('swap_weapon') == 5
      and len(qs) == 3 and '--stop-after-rewards' in qs[0] and '--allow-irreversible' in qs[2] and 'team_check' in T.names()
      and rebirth.LAST['stages']['heal']['status'] == 'ok', str(qs))
check('bow16 跳過 boss20 時 event 有寫', 'boss20：bow16 時已打完 20F' in rebirth.EVENT_LOG.read_text(encoding='utf-8'))
fresh()
T = FakeTools(pos=(32011, 56, 36), quest=[(0, (32018, 5, 5)), (37, (32021, 29, 57))])
rc = quiet(rebirth.run, trans=1, from_stage='bow16', to_stage='boss20', tools=T)
check('bow16 回 0、人在 18F（弓已拿到、20F 還沒打）→ 照常 heal / 傳送 / boss20', rc == 0 and 'heal' in T.names() and 'teleport20' in T.names(), str(T.names()))
fresh()
T = FakeTools(pos=(32021, 29, 57), quest=[(39, (32021, 31, 29))])
rc = quiet(rebirth.run, trans=1, from_stage='bow16', tools=T)
check('續跑 --from bow16 時人已在 21F → bow16 不跑 quest、after_boss 驗隊伍 → swap → rebirth',
      rc == 0 and len([c for c in T.calls if c[0] == 'quest']) == 2 and 'heal' not in T.names())
fresh()
T = FakeTools(pos=(32011, 56, 36), quest=[(37, (32016, 31, 40))])
check('bow16 回 37 但人在 16F → 84（不是已過 16F）', quiet(rebirth.run, trans=1, from_stage='bow16', to_stage='bow16', tools=T) == 84)
fresh()
T = FakeTools(pos=(32011, 56, 36), quest=[(37, (32021, 29, 57))], team_checks=[1], cards=[])
check('bow16 回 37 在 21F 但隊伍不滿、找不出被打飛的人 → 85（after_boss）', quiet(rebirth.run, trans=1, from_stage='bow16', to_stage='bow16', tools=T) == 85)
fresh()
T = FakeTools(pos=(32011, 56, 36), quest=[(37, (32021, 29, 57))])
quiet(rebirth.run, trans=1, from_stage='bow16', to_stage='bow16', tools=T)
T2 = FakeTools(pos=(32021, 29, 57), quest=[(39, (32021, 31, 29))])
rc = quiet(rebirth.run, trans=1, from_stage='swap', tools=T2)
check('bow16 記的 boss20_done 寫進度檔：之後 --from swap 續跑也跳過 heal / boss20', rc == 0 and 'heal' not in T2.names() and 'teleport20' not in T2.names())

# ---- team.form 回 9 → 等 20 秒只重試一次 ----
fresh()
T = FakeTools(team_form_rcs=[9, 0])
r_ = rebirth.Run(2, T, {})
check('form()：9 → 重試一次成功 → 0', quiet(r_.form) == 0 and T.names().count('team_form') == 2)
T = FakeTools(team_form_rcs=[9, 9])
r_ = rebirth.Run(2, T, {})
check('form()：連 2 次 9（真的驗證視窗）→ 9 停手', quiet(r_.form) == 9 and T.names().count('team_form') == 2)
T = FakeTools(team_form_rcs=[42], team_checks=[0])
r_ = rebirth.Run(2, T, {})
check('form()：42 但 team.check 滿 5 人（2026-10-13 三轉 preflight）→ 0，不再 form', quiet(r_.form) == 0 and T.names().count('team_form') == 1 and T.names().count('team_check') == 1)
T = FakeTools(team_form_rcs=[42, 0], team_checks=[42])
r_ = rebirth.Run(2, T, {})
check('form()：42、team.check 也不滿 → 再 form 一次成功 → 0', quiet(r_.form) == 0 and T.names().count('team_form') == 2)
T = FakeTools(team_form_rcs=[42, 42], team_checks=[42])
r_ = rebirth.Run(2, T, {})
check('form()：42 → check 不滿 → 再 form 仍 42 → 42（只重試一次）', quiet(r_.form) == 42 and T.names().count('team_form') == 2)

# ---- 轉生獎勵寵 ----
for n, nm_ in ((1, '烏力斯坦'), (2, '奇娜')):
    fresh()
    T = FakeTools()
    rc = quiet(rebirth.run, trans=n, from_stage='cleanup', tools=T)
    check(f'cleanup 第 {n} 轉：丟「{nm_}」（對照表）、不做 diff', rc == 0 and ('drop_pet', nm_) in T.calls and 'drop_new_lv1' not in T.names() and 'pet_snapshot' not in T.names())
fresh()
T = FakeTools(quest=[(39, (32021, 31, 29))])
T.after_levels = {r: (3, 1) for r in rebirth.ALL_ROLES}
T.levels_map = {r: (2, 131) for r in rebirth.ALL_ROLES}
rc = quiet(rebirth.run, trans=3, from_stage='rebirth', tools=T)
nm = T.names()
check('第 3 轉：rebirth 階段先拍寵物欄快照（在 quest 之前）→ cleanup 做 diff 丟、不用 drop_pet', rc == 0 and nm.index('pet_snapshot') < nm.index('quest') and 'drop_new_lv1' in nm and 'drop_pet' not in nm, str(nm))
check('快照存進進度檔', rebirth.load_progress().get('pets_before') == {'DKBO': []})
fresh()
T = FakeTools(quest=[(39, (32021, 31, 29))], snap_rc=71)
rc = quiet(rebirth.run, trans=3, from_stage='rebirth', tools=T)
check('第 3 轉：快照讀失敗 → 98，不轉生（沒呼叫 quest）', rc == 98 and 'quest' not in T.names())
fresh()
T = FakeTools(diff_rc=98)
rc = quiet(rebirth.run, trans=3, from_stage='cleanup', tools=T)
check('第 3 轉 cleanup：diff 不確定 → 98，龍王不動', rc == 98 and 'bag_store' not in T.names())
fresh()
T = FakeTools(diff_rc=9)
check('第 3 轉 cleanup：diff 時驗證視窗 → 9', quiet(rebirth.run, trans=3, from_stage='cleanup', tools=T) == 9)
_buf = io.StringIO()
with contextlib.redirect_stdout(_buf):
    rebirth.run(dry_run=True, trans=3, tools=types.SimpleNamespace())
check('dry-run 計畫含 accept / 獎勵寵 / 97 98 碼', '[accept]' in _buf.getvalue() and '97 接任務' in _buf.getvalue() and '98 獎勵寵' in _buf.getvalue())

print(f'\n{"全部通過" if not fails else f"失敗 {fails} 項"}')
sys.exit(1 if fails else 0)
