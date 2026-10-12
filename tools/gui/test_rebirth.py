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
        self.wins = kw.get('wins', {})

    def c(self, *a):
        self.calls.append(a)

    def names(self):
        return [x[0] for x in self.calls]

    def sleep(self, s): pass
    def preflight(self): self.c('preflight'); return 0
    def current(self): self.c('current'); return 0, self.cur
    def char_switch(self, n): self.c('char_switch', n); self.pos = (1000, 92, 99); return 0
    def char_ensure(self, n): self.c('char_ensure', n); return 0
    def team_form(self): self.c('team_form'); return self.team_form_rc
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
check('進度檔記 9 階段 ok', all(v['status'] == 'ok' for v in rebirth.LAST['stages'].values()) and len(rebirth.LAST['stages']) == 9)
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
check('team.form 失敗 → 83', quiet(rebirth.run, tools=FakeTools(team_form_rc=41)) == 83)
fresh()
check('等級不足（130）→ 80', quiet(rebirth.run, trans=1, tools=FakeTools(levels={**{r: (0, 133) for r in rebirth.ALL_ROLES}, 'DKBO4': (0, 130)})) == 80)
fresh()
check('轉數不符 → 80', quiet(rebirth.run, trans=1, tools=FakeTools(levels={r: (1, 140) for r in rebirth.ALL_ROLES})) == 80)
fresh()
T = FakeTools(items={'DKBO2': {'水的戒指': None}})
check('缺證明 → 81', quiet(rebirth.run, tools=T) == 81 and rebirth.LAST['info']['missing'] == {'DKBO2': ['水的戒指']})
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
T, rc = b20(team_checks=[1], team_form_rc=41)
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
        uikit.px = self.px
        uikit.open_panel_ex = lambda p, **k: (True, True)
        uikit.close_panel = lambda p, known_open=False: True
        bag._avatar_sel = lambda role: self.role == role
        bag._sub_on = lambda sub: True
        bag._buff_icon = lambda: True
        return self

    def is_open(self, p):
        if p.name == 'PETCONFIRM':
            return self.confirm is not None
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
            if abs(x - 612) < 8 and abs(y - 551) < 8:
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
        if box == pet.CONFIRM_BOX:
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
check('武器格已是弓 → 不動、不丟（續跑安全）', rc == 0 and fb.discarded == [] and (618, 662) not in fb.clicks)

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

print(f'\n{"全部通過" if not fails else f"失敗 {fails} 項"}')
sys.exit(1 if fails else 0)
