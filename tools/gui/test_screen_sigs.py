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
          'BATTLE': S.SIG_BATTLE, 'CMD': S.SIG_CMD, 'AUTO_OFF': S.SIG_AUTO_OFF, 'CLOSE_ROW': S.SIG_CLOSE_ROW,
          'NET_DIALOG': S.NET_DIALOG, 'NET_LOGIN': S.NET_LOGIN, 'NET_CHARSEL': S.NET_CHARSEL, 'ENC_ON': S.ENC_ON}
EXPECT_TOL = {'DIALOG': 40, 'REWARD': 40, 'PANEL': 40, 'SELECT': 40, 'HUD': 40, 'BATTLE': 25, 'CMD': 25, 'AUTO_OFF': 20,
              'CLOSE_ROW': 22, 'NET_DIALOG': 25, 'NET_LOGIN': 25, 'NET_CHARSEL': 25, 'ENC_ON': 50}
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
check('label：idle + 提示視窗', S.label({'state': 'idle'}, ['notice_dialog']) == '主畫面（未偵測到已知視窗）（提示視窗）')
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
check('ANNOT_KNOWN 含 login / charsel / loading / black', set(S.ANNOT_KNOWN) == {'login', 'charsel', 'loading', 'black'})


# ---- 4. 外接螢幕覆寫表 PHYS_OVERRIDES（P4 離線準備；沒有任何程式呼叫 set_layout）----
import importlib.util  # noqa: E402

spec = importlib.util.spec_from_file_location('screen_sigs_pristine', HERE / 'screen_sigs.py')
PRISTINE = importlib.util.module_from_spec(spec)          # 另載一份從沒呼叫過 set_layout 的模組：筆電原值的基準
spec.loader.exec_module(PRISTINE)


def snap(mod):
    return repr([getattr(mod, n) for n in S._OVERRIDABLE] + [mod.points(), mod.panel_points(), mod.annot_points()])

check('覆寫表只有 1728x995，key 都是 WxH', set(S.PHYS_OVERRIDES) == {'1728x995'})
check('預設（沒呼叫 set_layout）= 筆電原值，與另載的原始模組逐位元組相同', snap(S) == snap(PRISTINE) and S.active_layout() is None)
check('layout_key：1728×995 有表、2880×1659 / 1920×1017 沒有（精確比對不猜）', S.layout_key(1728, 995) == '1728x995' and S.layout_key(2880, 1659) is None and S.layout_key(1920, 1017) is None)
check('set_layout(None) / 筆電 key / 沒表的 key 回 False，原值不變', not S.set_layout(None) and not S.set_layout('2880x1659') and not S.set_layout('1920x1017') and snap(S) == snap(PRISTINE))
OVN = set(S.PHYS_OVERRIDES['1728x995'])
_i = PRISTINE.points().index(PRISTINE.VS_PROBE)
check('set_layout(1728x995) 回 True、HUD_GROUPS / ENC_ON / PANEL_TITLE / PANEL_PTS / VS_PROBES 變了、points() 只有 VS 牌點換掉',
      S.set_layout('1728x995') and S.active_layout() == '1728x995' and S.HUD_GROUPS != PRISTINE.HUD_GROUPS and S.ENC_ON != PRISTINE.ENC_ON
      and S.PANEL_TITLE != PRISTINE.PANEL_TITLE and len(S.VS_PROBES) == 5 and S.VS_PROBE == PRISTINE.VS_PROBE
      and S.points() == PRISTINE.points()[:_i] + S.VS_PROBES + PRISTINE.points()[_i + 1:])
check('套用後其餘特徵（SIG_*、PANEL_X、AW…）仍與筆電原值相同（只覆寫表內列的）',
      all(repr(getattr(S, n)) == repr(getattr(PRISTINE, n)) for n in S._OVERRIDABLE if n not in OVN))
import battleguard  # noqa: E402
check('battleguard 的 VS 取樣點跟著覆寫（外接 5 點）', battleguard._vs_probes() == S.VS_PROBES and len(S.VS_PROBES) == 5)
S.set_layout(None)
check('battleguard 的 VS 取樣點還原為筆電 [706,295]', battleguard._vs_probes() == [battleguard.VS_PROBE] == [(706, 295)])
S.set_layout('1728x995')
check('覆寫的點座標都在 1440×830 內、每組點數 ≥ HUD_MISS+3', all(0 <= x < 1440 and 0 <= y < 830 for pts in S.HUD_GROUPS.values() for x, y, *_ in pts + S.ENC_ON) and all(len(v) >= S.HUD_MISS + 3 for v in S.HUD_GROUPS.values()))
_hg, _enc, _bot = S.HUD_GROUPS, S.ENC_ON, S.HUD_GROUPS['bottom']
S.set_layout(None)
S.set_layout('1728x995')
check('from-import 的清單引用在切換後仍有效（原地改寫，物件 id 不變）', S.HUD_GROUPS is _hg and S.ENC_ON is _enc and S.HUD_GROUPS['bottom'] is _bot)
S.set_layout('1728x995')
S.set_layout('1728x995')
check('重複套用冪等', repr(S.HUD_GROUPS) == repr({k: PRISTINE.HUD_GROUPS[k] if k not in S.PHYS_OVERRIDES['1728x995']['HUD_GROUPS'] else S.PHYS_OVERRIDES['1728x995']['HUD_GROUPS'][k] for k in S.HUD_GROUPS}))
S.set_layout(None)
check('1728x995 → None 還原後與筆電原值逐位元組相同', snap(S) == snap(PRISTINE) and S.active_layout() is None)
try:
    S.PHYS_OVERRIDES['x'] = {'NO_SUCH': []}
    S.set_layout('x')
    check('不認得的特徵名會丟 KeyError', False)
except KeyError:
    check('不認得的特徵名會丟 KeyError', True)
finally:
    del S.PHYS_OVERRIDES['x']
    S.set_layout(None)
check('KeyError 測試後仍還原為筆電原值', snap(S) == snap(PRISTINE))

# 外接樣本（fixtures/phys_1728x995_px.json：P0 的 1728×995 全解析度、實體像素 ⌊x·sx⌋ 取樣，只有主畫面；make_phys_fixture.py 重產）
fxp = json.loads((HERE / 'fixtures' / 'phys_1728x995_px.json').read_text(encoding='utf-8'))
ppts = [tuple(p) for p in fxp['points']]


def phys_px(name):
    h = fxp['samples'][name]
    return {pt: (int(h[i * 6:i * 6 + 2], 16), int(h[i * 6 + 2:i * 6 + 4], 16), int(h[i * 6 + 4:i * 6 + 6], 16)) for i, pt in enumerate(ppts)}


def main_pts_ok(mod, px, enc):
    """主畫面 15 點（SIG_HUD 1 + HUD_GROUPS 12→目前表的點 + ENC_ON 2）在各自容差內的 (命中, 總數)；ENC_ON 只在遇敵開的圖算"""
    sigs = [(x, y, r, g, b, tol) for x, y, r, g, b, tol in mod.SIG_HUD] + [(x, y, r, g, b, mod.HUD_TOL) for pts in mod.HUD_GROUPS.values() for x, y, r, g, b in pts]
    if enc:
        sigs += list(mod.ENC_ON)
    return sum(1 for x, y, r, g, b, tol in sigs if S.close(px[(x, y)], (r, g, b), tol)), len(sigs)


# 原值（沒套覆寫）的基準：計畫 §2.4 的 P0 實測值
tot0 = ok0 = tot1 = ok1 = 0
for name, enc in (('off', False), ('enc', True)):
    px = phys_px(name)
    S.set_layout(None)
    a = main_pts_ok(S, px, enc)
    c0, hm0, e0 = S.classify(px), S.hud_main(px), S.enc_on(px, S.classify(px))
    S.set_layout('1728x995')
    b = main_pts_ok(S, px, enc)
    c1, hm1, e1 = S.classify(px), S.hud_main(px), S.enc_on(px, S.classify(px))
    S.set_layout(None)
    ok0, tot0, ok1, tot1 = ok0 + a[0], tot0 + a[1], ok1 + b[0], tot1 + b[1]
    check(f'外接 {name}：原值 classify=idle / hud_main 成立（原本就判對）', c0['state'] == 'idle' and hm0)
    check(f'外接 {name}：套覆寫後 classify 結果不變（idle、panel None、其餘欄位相同）', c1 == c0, str(c1))
    check(f'外接 {name}：hud_main 兩組都滿分（0 點不符）', hm1 and all(sum(1 for x, y, r, g, b in pts if S.close(px[(x, y)], (r, g, b), S.HUD_TOL)) == len(pts) for pts in S.PHYS_OVERRIDES['1728x995']['HUD_GROUPS'].values()))
    check(f'外接 {name}：enc_on 判斷 = {enc}（原值 {e0}、覆寫 {e1}）', e1 is enc)
rate0, rate1 = ok0 / tot0, ok1 / tot1
print(f'  [外接 1728×995 實體取樣] 主畫面特徵點在容差內：原值 {ok0}/{tot0} = {rate0:.1%}，覆寫後 {ok1}/{tot1} = {rate1:.1%}')
check('覆寫後主畫面特徵在容差內比例 ≥ 95%（原值較低）', rate1 >= 0.95 and rate1 > rate0)

# 筆電樣本庫：覆寫後對 tools/.cache 全部 1440×830 樣本的 classify 與原值 0 差異、主畫面 recall 不降（樣本庫是 gitignore 的，不在就略過）
try:
    import shotcache
    idx_ok = shotcache.INDEX.exists()
except Exception:                        # noqa: BLE001
    idx_ok = False
if idx_ok:
    allp = {}
    for k in (None, '1728x995'):
        S.set_layout(k)
        allp[k] = sorted(set(S.points() + S.panel_points() + S.annot_points()))
    S.set_layout(None)
    union = sorted(set(allp[None]) | set(allp['1728x995']))
    n = diff = tp0 = tp1 = pos = 0
    for rel, label, shot in shotcache.iter_shots():
        px = shot.pixels(union)
        S.set_layout(None)
        c0, h0 = S.classify(px), S.hud_main(px)
        S.set_layout('1728x995')
        c1, h1 = S.classify(px), S.hud_main(px)
        S.set_layout(None)
        n += 1
        # 筆電渲染的圖套外接覆寫只是「代理反例」：外接專用點（VS 牌世界座標、面板標題的外接渲染色）在筆電圖上本來就不中（變 idle），
        # 那不是外接的行為；要擋的是覆寫讓別的畫面「多認出」東西（誤判），所以只數 c1 認成具體畫面且與原值不同的
        diff += c0 != c1 and c1['state'] not in ('idle', 'unknown')
        if label in ('idle', 'walking'):
            pos += 1
            tp0 += h0
            tp1 += h1
    print(f'  [筆電樣本庫 {n} 張] 套外接覆寫後多認出 {diff}；主畫面 hud_main 命中 原值 {tp0}/{pos}、覆寫 {tp1}/{pos}')
    check('樣本庫（筆電圖當代理反例）：套外接覆寫後 0 張被「多認出」成別的畫面（外接專用點在筆電圖不中而退成 idle / unknown 的不算）', diff == 0)
    check('樣本庫：覆寫後主畫面 hud_main 命中不低於原值 −1', tp1 >= tp0 - 1)
else:
    print('  （略過）沒有 tools/.cache 樣本索引')
# P4 實機樣本（2026-10-11，外接 1728×995、gui pixel 的四捨五入取樣）：10 面板 + 主畫面 + 對話框 + VS 牌，classify 與人工標籤 100% 相同
S.set_layout('1728x995')
hit = 0
for k, (st_, pn_) in fxp['expect'].items():
    c = S.classify(phys_px(k))
    hit += (c['state'], c['panel']) == (st_, pn_)
    if (c['state'], c['panel']) != (st_, pn_):
        print('   不符', k, c['state'], c['panel'], '期望', st_, pn_)
    if st_ == 'panel':
        px = phys_px(k)
        t = S._count_ok(px, S.PANEL_TITLE[pn_], S.TITLE_TOL)
        check(f'外接 {k}：標題 8 點全中（覆寫後）', t == 8, str(t))
check(f'外接實機樣本 {len(fxp["expect"])} 張：classify 全對（覆寫後）', hit == len(fxp['expect']), f'{hit}/{len(fxp["expect"])}')
S.set_layout(None)
# vs_on：外接樣本中 expect=battle 的（看得到 VS 牌）全部 vs_on 為真、非 battle 的為假；原值（筆電單點）對外接樣本不中（證明需要覆寫）
vs_pos = [k for k, (st_, _) in fxp['expect'].items() if st_ == 'battle']
vs_neg = [k for k in fxp['samples'] if k not in vs_pos]
S.set_layout('1728x995')
check(f'外接 vs_on：{len(vs_pos)} 張 VS 樣本全中', all(S.vs_on(phys_px(k)) for k in vs_pos), str([k for k in vs_pos if not S.vs_on(phys_px(k))]))
check(f'外接 vs_on：其餘 {len(vs_neg)} 張（主畫面 / 面板 / 對話框 / 非 VS）全不中', not any(S.vs_on(phys_px(k)) for k in vs_neg), str([k for k in vs_neg if S.vs_on(phys_px(k))]))
S.set_layout(None)
check('筆電 vs_on：只看 VS_PROBE 單點、缺點視為沒中', S.vs_on({S.VS_PROBE: S.VS_COLOR}) and not S.vs_on({S.VS_PROBE: (0, 0, 0)}) and not S.vs_on({}))
check('筆電 vs_on 外接樣本不中（單點）', not any(S.vs_on(phys_px(k)) for k in vs_pos))
import quest as _Q
check('quest 與 screen_sigs 共用 vs_on', _Q.vs_on is S.vs_on)
check('測試結束時已還原筆電原值', snap(S) == snap(PRISTINE))

print('\n全部通過' if not fails else f'\n{fails} 項失敗')
sys.exit(1 if fails else 0)
