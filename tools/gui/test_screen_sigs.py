#!/usr/bin/env python3
"""screen_sigs 測試（不碰遊戲）：
1. fixture 等價：fixtures/screen_px.json 是重構前（quest.read_screen 舊邏輯）對已存截圖凍結的像素與分類，classify 必須 0 差異。
   （樣本是 1440×830 縮圖，只證明重構前後等價，不證明實機容差；實機容差靠 2 的邊界測試 + --dump-px）
2. 邊界：每組特徵在 tol 命中、tol+1 不命中（合成像素）。
3. netwatch / heal 的 waitpix 字串與重構前逐字相同；screen_sigs 不 import winenv。
用法：uv run --no-project python tools/gui/test_screen_sigs.py"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import testenv  # noqa: E402,F401  紀錄檔轉向暫存（不污染真 actions.log / quest-events.log / errlog）
import screen_sigs as S  # noqa: E402

fails = 0


def check(name, cond, extra=''):
    global fails
    print(('PASS' if cond else 'FAIL'), name, extra)
    if not cond:
        fails += 1


# ---- 1. fixture 等價 ----
fx = json.loads((HERE / 'fixtures' / 'screen_px.json').read_text(encoding='utf-8'))
pts = [tuple(p) for p in fx['points']]
check('fixture 取樣點順序 == screen_sigs.points()', pts == S.points())
diff = []
for smp in fx['samples']:
    h = smp['px']
    px = {pt: (int(h[i * 6:i * 6 + 2], 16), int(h[i * 6 + 2:i * 6 + 4], 16), int(h[i * 6 + 4:i * 6 + 6], 16)) for i, pt in enumerate(pts)}
    got = S.classify(px)
    want = {k: smp[k] for k in ('state', 'gold', 'full', 'cmd', 'auto_off')}
    if {k: got[k] for k in want} != want or got['panel'] not in (None, 'switch'):     # 舊 fixture 沒帶 panel_points：只會認出切換面板
        diff.append((smp['name'], want, got))
    if smp['state'] == 'panel' and got['panel'] != 'switch':
        diff.append((smp['name'], 'panel 名應為 switch', got['panel']))
check(f'fixture {len(fx["samples"])} 筆新舊判斷 0 差異', not diff, str(diff[:3]))
states = {}
for smp in fx['samples']:
    states[smp['state']] = states.get(smp['state'], 0) + 1
check('fixture 涵蓋 dialog/reward/battle/panel/select/walking/idle/unknown', set(states) >= {'dialog', 'reward', 'battle', 'panel', 'select', 'walking', 'idle', 'unknown'}, str(states))


# ---- 2. 邊界 ----
def shifted(c, d):
    """每個通道往遠離 0 / 255 較遠的一側偏 d（保證在 0～255 內且差值剛好 d）"""
    return tuple(v + d if v + d <= 255 else v - d for v in c)


def px_of(sig, delta=0, who=None):
    """sig 全部點 = 參考色；第 who 個點偏 delta"""
    px = {}
    for i, (x, y, r, g, b, tol) in enumerate(sig):
        px[(x, y)] = shifted((r, g, b), delta) if i == who else (r, g, b)
    return px


GROUPS = {'DIALOG': S.SIG_DIALOG, 'REWARD': S.SIG_REWARD, 'PANEL': S.SIG_PANEL, 'SELECT': S.SIG_SELECT, 'HUD': S.SIG_HUD,
          'BATTLE': S.SIG_BATTLE, 'CMD': S.SIG_CMD, 'AUTO_OFF': S.SIG_AUTO_OFF, 'CLOSE_ROW': S.SIG_CLOSE_ROW, 'SWITCH_FULL': S.SIG_SWITCH_FULL, 'SWITCH_MAIN': S.SIG_SWITCH_MAIN,
          'NET_DIALOG': S.NET_DIALOG, 'NET_LOGIN': S.NET_LOGIN, 'NET_CHARSEL': S.NET_CHARSEL, 'ENC_ON': S.ENC_ON}
EXPECT_TOL = {'DIALOG': 40, 'REWARD': 40, 'PANEL': 40, 'SELECT': 40, 'HUD': 40, 'BATTLE': 25, 'CMD': 25, 'AUTO_OFF': 20,
              'CLOSE_ROW': 22, 'SWITCH_FULL': 30, 'SWITCH_MAIN': 30, 'NET_DIALOG': 25, 'NET_LOGIN': 25, 'NET_CHARSEL': 25, 'ENC_ON': 50}
for name, sig in GROUPS.items():
    tol = EXPECT_TOL[name]
    check(f'{name} 容差原值 {tol}', all(t[5] == tol for t in sig))
    ok_all = S.match(px_of(sig), sig) and S.match(px_of(sig, tol, who=-1), sig)
    check(f'{name} tol 命中（全部點各偏 tol）', ok_all and all(S.match(px_of(sig, tol, who=i), sig) for i in range(len(sig))))
    check(f'{name} tol+1 不命中（任一點偏 tol+1）', all(not S.match(px_of(sig, tol + 1, who=i), sig) for i in range(len(sig))))
# VS 牌（40）
vs = {S.VS_PROBE: S.VS_COLOR}
check('VS 牌 tol 命中', S.close(shifted(S.VS_COLOR, 40), S.VS_COLOR, S.VS_TOL))
check('VS 牌 tol+1 不命中', not S.close(shifted(S.VS_COLOR, 41), S.VS_COLOR, S.VS_TOL))


# classify 層級：空白畫面 + 疊上單一特徵
def blank():
    return {pt: (0, 0, 0) for pt in S.points()}


def with_sig(*sigs, delta=0, who=None):
    px = blank()
    for sig in sigs:
        px.update(px_of(sig, delta, who))
    return px


check('classify：空白 = unknown', S.classify(blank())['state'] == 'unknown')
for st, sig in (('dialog', S.SIG_DIALOG), ('reward', S.SIG_REWARD), ('panel', S.SIG_PANEL), ('select', S.SIG_SELECT), ('idle', S.SIG_HUD)):
    check(f'classify：{st} tol 命中', S.classify(with_sig(sig, delta=40, who=0))['state'] == st)
    check(f'classify：{st} tol+1 不命中', S.classify(with_sig(sig, delta=41, who=0))['state'] == 'unknown')
b = S.classify(with_sig(S.SIG_BATTLE, delta=25, who=0))
check('classify：battle(full) tol 25', b['state'] == 'battle' and b['full'] and not b['cmd'] and not b['auto_off'])
check('classify：battle tol+1 不命中', S.classify(with_sig(S.SIG_BATTLE, delta=26, who=0))['state'] == 'unknown')
check('classify：cmd 全中', S.classify(with_sig(S.SIG_BATTLE, S.SIG_CMD))['cmd'] is True)
p = with_sig(S.SIG_BATTLE); p.update(px_of(S.SIG_CMD, 25, 0))
check('classify：cmd 偏 25 命中', S.classify(p)['cmd'] is True)
p = with_sig(S.SIG_BATTLE); p.update(px_of(S.SIG_CMD, 26, 0))
check('classify：cmd 偏 26 不命中', S.classify(p)['cmd'] is False)
p = with_sig(S.SIG_BATTLE); p.update(px_of(S.SIG_AUTO_OFF, 20, 0))
check('classify：auto_off 偏 20 命中', S.classify(p)['auto_off'] is True)
p = with_sig(S.SIG_BATTLE); p.update(px_of(S.SIG_AUTO_OFF, 21, 0))
check('classify：auto_off 偏 21 不命中', S.classify(p)['auto_off'] is False)
p = blank(); p[S.VS_PROBE] = shifted(S.VS_COLOR, 40)
check('classify：VS 牌偏 40 = battle（非 full）', S.classify(p)['state'] == 'battle' and not S.classify(p)['full'])
p[S.VS_PROBE] = shifted(S.VS_COLOR, 41)
check('classify：VS 牌偏 41 不命中', S.classify(p)['state'] == 'unknown')
p = blank()
for pt in S.AW_POINTS[:S.AW_MIN]:
    p[pt] = (230, 180, 10)
check('classify：金黃點 = AW_MIN → walking', S.classify(p)['state'] == 'walking')
p[S.AW_POINTS[0]] = (0, 0, 0)
check('classify：金黃點 AW_MIN-1 → unknown', S.classify(p)['state'] == 'unknown')
# 優先序：戰鬥 + HUD 紅字 → battle；選擇面板 + HUD → select
check('classify：戰鬥 + HUD 紅字 = battle', S.classify(with_sig(S.SIG_BATTLE, S.SIG_HUD))['state'] == 'battle')
check('classify：選擇面板 + HUD 紅字 = select', S.classify(with_sig(S.SIG_SELECT, S.SIG_HUD))['state'] == 'select')

# ---- 3. 字串逐字相同、不 import winenv ----
check('SIG_DIALOG(net) 字串', S.sig_str(S.NET_DIALOG) == '520,570,245,217,179/880,570,245,217,179/600,300,243,213,175/600,557,243,213,175/830,557,243,213,175/640,557,61,106,167')
check('SIG_LOGIN 字串', S.sig_str(S.NET_LOGIN) == '500,570,179,127,63/760,565,93,137,187/440,520,243,217,179')
check('SIG_CHARSEL 字串', S.sig_str(S.NET_CHARSEL) == '640,640,197,134,70/500,250,241,213,179/1186,190,196,72,48/350,330,169,117,70')
check('ENC_ON / OFF 字串', S.sig_str(S.ENC_ON) == '1380,630,129,6,0/1360,632,179,12,0' and S.sig_str(S.ENC_ON, neg=True) == '1380,630,129,6,0!/1360,632,179,12,0!')
check('quest 面板 waitpix 字串', S.sig_str(S.SIG_PANEL) == '1064,208,197,69,41/880,590,55,67,13')
import ast  # noqa: E402
mods = set()
for n in ast.walk(ast.parse((HERE / 'screen_sigs.py').read_text(encoding='utf-8'))):
    if isinstance(n, ast.Import):
        mods |= {a.name for a in n.names}
    elif isinstance(n, ast.ImportFrom):
        mods.add(n.module)
check('screen_sigs 不 import winenv', 'winenv' not in mods, str(mods))
check('annotate：沒有取樣點（只有 classify 用的 fixture）→ 空清單、enc_on None', S.annotate({}, {}) == [] and S.enc_on({}, {'state': 'idle'}) is None)

# ---- 4. annotate / enc_on（樣本驗證）----
AX = json.loads((HERE / 'fixtures' / 'annot_px.json').read_text(encoding='utf-8'))
apts = [tuple(p) for p in AX['points']]
bad, pos = [], {'notice_dialog': 0, 'login': 0, 'charsel': 0, 'enc_on': 0}
for smp in AX['samples']:
    h = smp['px']
    px = {pt: (int(h[i * 6:i * 6 + 2], 16), int(h[i * 6 + 2:i * 6 + 4], 16), int(h[i * 6 + 4:i * 6 + 6], 16)) for i, pt in enumerate(apts)}
    a, e = S.annotate(px, {}), S.enc_on(px, {'state': 'idle'})
    if a != smp['annot'] or e != smp['enc_on']:
        bad.append(smp['f'])
    for k in a:
        pos[k] += 1
    pos['enc_on'] += bool(e)
check(f'annotate / enc_on：{len(AX["samples"])} 張樣本結果與凍結結果一致', not bad, str(bad[:3]))
check('每個上線特徵至少一張正例（提示視窗 / 登入 / 選角 / 遇敵鈕）', all(v >= 1 for v in pos.values()), str(pos))
check('annot_points 與 classify 的 points 不重複', not (set(S.annot_points()) & set(S.points())))
# 容差邊界：NET_LOGIN 偏 25 命中、26 不命中；ENC_ON 偏 50 / 51
for name, sig, tol in (('login', S.NET_LOGIN, 25), ('enc_on', S.ENC_ON, 50)):
    for off, want in ((tol, True), (tol + 1, False)):
        px = {(x, y): (min(255, r + off), g, b) for x, y, r, g, b, t in sig}
        got = (S.annotate(px, {}) == ['login']) if name == 'login' else (S.enc_on(px, {'state': 'idle'}) is True)
        check(f'{name} 偏 {off} → {"命中" if want else "不命中"}', got == want)
check('enc_on：主畫面看不到紅龍 = False；戰鬥等其他畫面 = None', S.enc_on({(x, y): (0, 0, 0) for x, y, *_ in S.ENC_ON}, {'state': 'walking'}) is False
      and S.enc_on({(x, y): (0, 0, 0) for x, y, *_ in S.ENC_ON}, {'state': 'battle'}) is None)
check('label：登入 / 選角（classify=unknown）顯示認得的畫面名', S.label({'state': 'unknown'}, ['login']) == '登入畫面' and S.label({'state': 'unknown'}, ['charsel']) == '選角畫面')
check('label：idle + 提示視窗', S.label({'state': 'idle'}, ['notice_dialog']) == '主畫面（提示視窗）')
check('label：任何 annotate 組合都不出現「安全」「無驗證」', all(not any(w in S.label({'state': st}, an) for w in ('安全', '無驗證')) for st in ('idle', 'unknown', 'dialog') for an in ([], ['login'], ['notice_dialog'])))

# ---- 5. 面板辨識（2026-10-11）：樣本 fixture + 邊界 + 主畫面多組 + 載入 / 黑畫面 ----
PX = json.loads((HERE / 'fixtures' / 'panel_px.json').read_text(encoding='utf-8'))
ppts = [tuple(p) for p in PX['points']]
check('panel fixture 取樣點 == points() + annot_points()', ppts == S.points() + S.annot_points())
bad, pos_n, neg_n, per = [], 0, 0, {}
for smp in PX['samples']:
    h = smp['px']
    px = {pt: (int(h[i * 6:i * 6 + 2], 16), int(h[i * 6 + 2:i * 6 + 4], 16), int(h[i * 6 + 4:i * 6 + 6], 16)) for i, pt in enumerate(ppts)}
    c = S.classify(px)
    a = S.annotate(px, c)
    if c['state'] != smp['state'] or c['panel'] != smp['panel'] or a != smp['annot']:
        bad.append((smp['f'], 'frozen'))
    if smp['expect_panel']:
        pos_n += 1
        per[smp['expect_panel']] = per.get(smp['expect_panel'], 0) + 1
        if c['state'] != 'panel' or c['panel'] != smp['expect_panel']:
            bad.append((smp['f'], 'recall', c['state'], c['panel']))
    else:
        neg_n += 1
        if c['panel'] is not None or c['state'] == 'panel':
            bad.append((smp['f'], 'FP', c['state'], c['panel']))
check(f'panel fixture：{pos_n} 張正例 100% 認對面板名、{neg_n} 張負例 0 誤判、凍結結果一致', not bad, str(bad[:4]))
title_hit = {}
cover_bad = []
for smp in PX['samples']:
    if not smp['expect_panel']:
        continue
    h = smp['px']
    px = {pt: (int(h[i * 6:i * 6 + 2], 16), int(h[i * 6 + 2:i * 6 + 4], 16), int(h[i * 6 + 4:i * 6 + 6], 16)) for i, pt in enumerate(ppts)}
    nm = smp['expect_panel']
    if S._count_ok(px, S.PANEL_TITLE[nm], S.TITLE_TOL) >= S.TITLE_NEED:
        title_hit[nm] = title_hit.get(nm, 0) + 1
        # 框線被蓋：✕ 與 PANEL_PTS 全蓋成灰，標題還在 → 仍認得
        p2 = dict(px)
        for pt in [S.PANEL_X[nm][:2]] + [q[:2] for q in S.PANEL_PTS[nm]]:
            p2[pt] = (70, 70, 70)
        if S.panel_of(p2) != nm:
            cover_bad.append((smp['f'], 'frame-covered'))
    # 標題被蓋：標題點全蓋成灰，框線備援仍認得（原本 ✕ + PANEL_PTS 就認得的樣本）
    p3 = dict(px)
    for pt in [q[:2] for q in S.PANEL_TITLE[nm]]:
        p3[pt] = (70, 70, 70)
    if S.panel_of(p3) != nm:
        cover_bad.append((smp['f'], 'title-covered'))
check('正例：標題點命中（每種面板至少一張；全部正例僅 switch 被 EXP 橫幅蓋住的 1 張例外）', set(title_hit) == set(S.PANEL_X)
      and sum(title_hit.values()) >= pos_n - 1, str(title_hit))
check('框線點（✕ + 8 點）被蓋但標題在 → 仍認得；標題被蓋 → 退回框線備援（含 role 樣本）', not cover_bad, str(cover_bad[:3]))
check('panel fixture 涵蓋 pet / bag / ass / quest / switch / transfer / setting / team / qteam / role', set(per) == set(S.PANEL_X), str(per))
check('panel fixture 有人物資訊 4 張正例（watch-panels/role-0～3）', {f'watch-panels/role-{i}.png' for i in range(4)} <= {x['f'] for x in PX['samples'] if x['expect_panel'] == 'role'})
check('panel fixture 有今天使用者開的寵物視窗（watch-panels/pet-0、pet-1）', {'watch-panels/pet-0.png', 'watch-panels/pet-1.png'} <= {x['f'] for x in PX['samples']})
check('panel fixture 負例涵蓋 unknown / idle / dialog / battle / loading / login', {x['state'] for x in PX['samples'] if not x['expect_panel']} >= {'unknown', 'idle', 'dialog', 'battle'}
      and any(x['annot'] == ['loading'] for x in PX['samples']) and any(x['annot'] == ['login'] for x in PX['samples']))
check('PANEL_X / PANEL_PTS / PANEL_NAMES 的面板一致、每面板 8 點', set(S.PANEL_X) == set(S.PANEL_PTS) == set(S.PANEL_NAMES) and all(len(v) == 8 for v in S.PANEL_PTS.values()))
check('PANEL_TITLE 每面板 8 點、都在 panel_points() 內', set(S.PANEL_TITLE) == set(S.PANEL_X) and all(len(v) == 8 for v in S.PANEL_TITLE.values())
      and all((x, y) in set(S.panel_points()) for v in S.PANEL_TITLE.values() for x, y, *_ in v))
check('panel_points 與 classify 的 points 不重複', not (set(S.panel_points()) & set(S.points())))
import uikit  # noqa: E402
check('uikit 沿用 screen_sigs 的 ✕ 特徵（PET / TEAMPANEL / QTEAM / SWITCH）', uikit.PET.sig == [S.X_PET] and uikit.TEAMPANEL.sig[0] == S.X_TEAM
      and uikit.QTEAM.sig[0] == S.X_QTEAM and S.PANEL_X['switch'] == uikit.SWITCH.sig[0])


def panel_px(name, miss=0, delta=0, x_delta=0):
    """合成：全灰底 + 某面板的 ✕ 與 8 點；前 miss 個點偏 delta、✕ 偏 x_delta"""
    px = {pt: (70, 70, 70) for pt in S.points() + S.panel_points()}
    for i, (x, y, r, g, b) in enumerate(S.PANEL_PTS[name]):
        px[(x, y)] = shifted((r, g, b), delta) if i < miss else (r, g, b)
    x, y, r, g, b, t = S.PANEL_X[name]
    px[(x, y)] = shifted((r, g, b), x_delta)
    return px


for nm in S.PANEL_X:
    ok = S.classify(panel_px(nm))
    check(f'{nm}：8 點全中 → panel={nm}', ok['state'] == 'panel' and ok['panel'] == nm)
    check(f'{nm}：2 點不符（偏 PANEL_TOL+1）仍認得（容許被內容蓋住）', S.classify(panel_px(nm, 2, S.PANEL_TOL + 1))['panel'] == nm)
    check(f'{nm}：3 點不符 → 不認得（unknown）', S.classify(panel_px(nm, 3, S.PANEL_TOL + 1))['state'] == 'unknown')
    check(f'{nm}：點偏 PANEL_TOL 剛好仍中', S.classify(panel_px(nm, 8, S.PANEL_TOL))['panel'] == nm)
    check(f'{nm}：✕ 偏 tol+1 → 不認得', S.classify(panel_px(nm, 0, 0, S.PANEL_X[nm][5] + 1))['state'] == 'unknown')


def title_px(name, miss=0, delta=0):
    """合成：全灰底 + 某面板標題 8 點（框線 / ✕ 不給）；前 miss 個點偏 delta"""
    px = {pt: (70, 70, 70) for pt in S.points() + S.panel_points()}
    for i, (x, y, r, g, b) in enumerate(S.PANEL_TITLE[name]):
        px[(x, y)] = shifted((r, g, b), delta) if i < miss else (r, g, b)
    return px


for nm in S.PANEL_X:
    check(f'{nm}：只有標題（沒有 ✕ / 框線）→ panel={nm}', S.classify(title_px(nm))['panel'] == nm)
    check(f'{nm}：標題 1 點不符仍認得、2 點不符 → 不認得', S.classify(title_px(nm, 1, S.TITLE_TOL + 1))['panel'] == nm and S.classify(title_px(nm, 2, S.TITLE_TOL + 1))['state'] == 'unknown')
    check(f'{nm}：標題點偏 TITLE_TOL 剛好仍中', S.classify(title_px(nm, 8, S.TITLE_TOL))['panel'] == nm)
check('沒讀 panel_points（舊 fixture / quest.read_screen）→ 不認得新面板、不丟例外', S.classify({pt: (70, 70, 70) for pt in S.points()})['panel'] is None)
check('label：面板：寵物 / 外掛 / 快速組隊；舊切換面板', S.label({'state': 'panel', 'panel': 'pet'}) == '面板：寵物' and S.label({'state': 'panel', 'panel': 'ass'}) == '面板：外掛'
      and S.label({'state': 'panel', 'panel': 'qteam'}) == '面板：快速組隊' and S.label({'state': 'panel'}) == '切換角色面板')


# 主畫面多組：任一組命中 = idle；一組允許 1 點不符
def hud_px(*groups, miss=0, delta=60):
    px = {pt: (70, 70, 70) for pt in S.points() + S.panel_points()}
    for g in groups:
        for i, (x, y, r, gg, b) in enumerate(S.HUD_GROUPS[g]):
            px[(x, y)] = shifted((r, gg, b), delta) if i < miss else (r, gg, b)
    return px


check('主畫面：沒有任何一組 = unknown', S.classify(hud_px())['state'] == 'unknown')
check('主畫面：只有底部圖示列（G2，外掛紅字被特效蓋住）= idle', S.classify(hud_px('bottom'))['state'] == 'idle')
check('主畫面：只有右下按鈕（G3）= idle', S.classify(hud_px('right'))['state'] == 'idle')
check('主畫面：G2 有 1 點不符仍 idle、2 點不符 = unknown', S.classify(hud_px('bottom', miss=1))['state'] == 'idle' and S.classify(hud_px('bottom', miss=2))['state'] == 'unknown')
p = {pt: (70, 70, 70) for pt in S.points() + S.panel_points()}
p.update(px_of(S.SIG_HUD))
check('主畫面：只有外掛紅字（舊判斷）仍 idle', S.classify(p)['state'] == 'idle')
check('主畫面圖示列在面板開著時被蓋住不成立（面板優先，且不靠 HUD 組）', S.classify({**hud_px('bottom'), **panel_px('pet')})['panel'] == 'pet')
# 戰鬥 / 對話框優先於 idle
check('戰鬥 + 主畫面圖示列 = battle', S.classify({**hud_px('bottom'), **{pt: c for pt, c in px_of(S.SIG_BATTLE).items()}})['state'] == 'battle')
# 載入 / 黑畫面：annotate 才認（classify 仍是 unknown，腳本的 preflight 不會把它當正常畫面）
ld = {pt: (70, 70, 70) for pt in S.points() + S.annot_points()}
ld.update(px_of(S.SIG_LOADING))
c = S.classify(ld)
check('載入畫面：classify=unknown、annotate=[loading]、label=載入畫面', c['state'] == 'unknown' and S.annotate(ld, c) == ['loading'] and S.label(c, ['loading']) == '載入畫面')
bk = {pt: (0, 0, 0) for pt in S.points() + S.annot_points()}
c = S.classify(bk)
check('全黑轉場：annotate=[black]、label=黑畫面（轉場）', c['state'] == 'unknown' and S.annotate(bk, c) == ['black'] and S.label(c, ['black']) == '黑畫面（轉場）')
bk[S.BLACK_PTS[3]] = (S.BLACK_MAX, 0, 0)
check('黑畫面：任一點亮度 ≥ BLACK_MAX → 不是黑畫面', S.annotate(bk, S.classify(bk)) == [])
check('黑 / 載入只在 classify=unknown 時附註（idle 畫面剛好暗不算）', S.annotate({**bk, **{pt: (0, 0, 0) for pt in S.BLACK_PTS}}, {'state': 'idle'}) == [])
check('ANNOT_KNOWN = login / charsel / loading / black + 三種面板上已知彈窗', set(S.ANNOT_KNOWN) == {'login', 'charsel', 'loading', 'black', 'popup_keypad', 'popup_qty', 'popup_confirm'})

# ---- 6. 面板上疊已知彈窗（2026-10-12，watch 誤報 #243 #244 #254 #261 #264）----
PP = json.loads((HERE / 'fixtures' / 'popup_px.json').read_text(encoding='utf-8'))
qpts = [tuple(p) for p in PP['points']]
check('popup fixture 取樣點 == points() + annot_points()', qpts == S.points() + S.annot_points())
bad, npos, nneg, kinds = [], 0, 0, {}
for smp in PP['samples']:
    h = smp['px']
    px = {pt: (int(h[i * 6:i * 6 + 2], 16), int(h[i * 6 + 2:i * 6 + 4], 16), int(h[i * 6 + 4:i * 6 + 6], 16)) for i, pt in enumerate(qpts)}
    c = S.classify(px)
    a = S.annotate(px, c)
    hit = S.popup_over_panel(px)
    if a != smp['annot']:
        bad.append((smp['f'], 'frozen', a))
    if smp['expect']:
        npos += 1
        kinds[smp['expect'][1]] = kinds.get(smp['expect'][1], 0) + 1
        if c['state'] != 'unknown' or list(hit or []) != smp['expect'] or not any(k in a for k in S.ANNOT_KNOWN):
            bad.append((smp['f'], 'recall', hit))
    else:
        nneg += 1
        if hit or any(k in a for k in S.ANNOT_KNOWN):
            bad.append((smp['f'], 'FP', a))
check(f'popup fixture：{npos} 張正例（{kinds}）全認對、{nneg} 張負例（含壓暗背包上的道具詳情彈窗）仍 unknown', not bad and npos >= 20 and nneg >= 7, str(bad[:4]))
# 既有 panel 樣本：除了本來就是彈窗正例的（i1 / store-nochange）以外，沒有任何一張被當成「面板上已知彈窗」
PXS = json.loads((HERE / 'fixtures' / 'panel_px.json').read_text(encoding='utf-8'))
pos_files = {smp['f'] for smp in PP['samples'] if smp['expect']}
fp = []
for smp in PXS['samples']:
    if smp['f'] in pos_files:
        continue
    h = smp['px']
    px = {pt: (int(h[i * 6:i * 6 + 2], 16), int(h[i * 6 + 2:i * 6 + 4], 16), int(h[i * 6 + 4:i * 6 + 6], 16)) for i, pt in enumerate(ppts)}
    if S.popup_over_panel(px):
        fp.append(smp['f'])
check(f'panel fixture {len(PXS["samples"])} 張（扣掉彈窗正例）：0 張被認成面板上彈窗', not fp, str(fp[:3]))


def dim_title(name, k):
    return {(x, y): (round(r * k), round(g * k), round(b * k)) for x, y, r, g, b in S.PANEL_TITLE[name]}


def popup_px(kind):
    return {(x, y): (r, g, b) for x, y, r, g, b, *_ in S.POPUP_SIGS[kind]}


base = {pt: (70, 70, 70) for pt in S.points() + S.annot_points()}
for kind in S.POPUP_SIGS:
    for pn in S.POPUP_PANELS:
        q = {**base, **dim_title(pn, 0.5), **popup_px(kind)}
        c = S.classify(q)
        check(f'合成：壓暗 {pn} ×0.5 + {kind} → annotate 認得、不算 unknown', c['state'] == 'unknown' and S.annotate(q, c) == ['popup_' + kind, 'over_' + pn])
q = {**base, **popup_px('qty')}
check('只有彈窗、底下不是壓暗的面板 → 不認（驗證視窗若長得像也要有面板才放行）', S.annotate(q, S.classify(q)) == [])
q = {**base, **dim_title('bag', 0.5)}
check('壓暗的背包、彈窗不認得（驗證視窗 / 道具詳情）→ 仍 unknown', S.annotate(q, S.classify(q)) == [] and S.dim_panel(q) == 'bag')
q = {**base, **dim_title('bag', 1.0), **popup_px('qty')}
check('背包沒壓暗（k=1）+ 彈窗特徵 → 不是模態彈窗，不認', S.dim_panel(q) is None and S.popup_over_panel(q) is None)
q = {**base, **dim_title('quest', 0.5), **popup_px('confirm')}
check('壓暗的任務詳情 + 確認窗 → 沒有正例樣本的面板不放行', S.popup_over_panel(q) is None)
for kind in S.POPUP_SIGS:
    q = {**base, **dim_title('bag', 0.5), **popup_px(kind)}
    pts_k = S.POPUP_SIGS[kind]
    for x, y, *_ in pts_k[:len(pts_k) - S.POPUP_NEED + 1]:
        q[(x, y)] = (0, 255, 0)
    check(f'{kind}：{len(pts_k) - S.POPUP_NEED + 1} 點不符 → 不認', S.popup_over_panel(q) is None)
check('label：面板上已知彈窗顯示面板名 + 彈窗名', S.label({'state': 'unknown'}, ['popup_qty', 'over_bag']) == '面板：背包＋數量輸入視窗'
      and S.label({'state': 'unknown'}, ['popup_confirm', 'over_pet']) == '面板：寵物＋確定 / 取消提示窗')

# ---- 載入畫面「加載中」字形（2026-10-12：新插畫載入圖 SIG_LOADING 落空 → quest.py 誤報驗證視窗退出碼 2）----
import json as _json
_fx = _json.loads((Path(__file__).resolve().parent / 'fixtures' / 'loading_px.json').read_text(encoding='utf-8'))
_pts = [tuple(p) for p in _fx['pts']]
_bad = [smp['file'] for smp in _fx['samples'] if S.loading_text(dict(zip(_pts, [tuple(c) for c in smp['px']]))) != smp['loading']]
check(f'loading_text：{len(_fx["samples"])} 張樣本（2 張載入畫面、其餘不是）全對', not _bad, str(_bad))
_new = next(smp for smp in _fx['samples'] if 'UNKNOWN' in smp['file'] and smp['loading'])
_px = dict(zip(_pts, [tuple(c) for c in _new['px']]))
_only_text = {k: v for k, v in _px.items() if k in {(x, y) for x, y, _ in S.LOADING_TEXT_PTS}}
check('只有字形點（沒有舊三點）也認得載入畫面', S.is_loading(_only_text) and not S._match_safe(_only_text, S.SIG_LOADING))
check('新插畫載入圖：is_loading 中、annotate = loading', S.is_loading(_px)
      and S.annotate(_px, {'state': 'unknown'}) == ['loading'])
check('loading_text 缺點 → False', not S.loading_text({}))
# 英文版 Loading... 雙進度條（2026-10-14 實機 quest rc 9 誤報）
_bar = {(x, y): (r, g, b) for x, y, r, g, b, _ in S.SIG_LOADING_BAR}
check('英文版載入圖（綠 / 橘雙進度條）：is_loading 中', S.is_loading(_bar))
_bar2 = dict(_bar); _bar2[(200, 758)] = (56, 48, 38)
check('橘條缺 → 不認載入畫面', not S.is_loading(_bar2))

print('\n全部通過' if not fails else f'\n{fails} 項失敗')
sys.exit(1 if fails else 0)
