#!/usr/bin/env python3
"""questdetail.py 離線測試（不碰遊戲）：用 tools/.cache 既有的任務詳情截圖當 fixture（缺檔就 SKIP 該段）。
用法：uv run --no-project python tools/gui/test_questdetail.py"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import testenv  # noqa: E402,F401  紀錄檔轉向暫存（不污染真 actions.log / quest-events.log / errlog）
import questdetail as qd  # noqa: E402
import uikit  # noqa: E402

CACHE = HERE.parent / '.cache'
fails = 0


def check(name, cond, extra=''):
    global fails
    print(('PASS' if cond else 'FAIL'), name, extra)
    if not cond:
        fails += 1


S = '(1.82)'
# 人工逐張對過畫面：(檔, [(標題, 狀態)…依列順序，只含完整可見列])
TRUTH = {
    'up_1.png': [('亞姆的斧頭' + S, '已完成'), ('五兄弟之謎' + S, '已完成'), ('強盜的洞穴' + S, '已完成'), ('小豬愛情故事' + S, '已完成'), ('馬祖快遞' + S, '已完成')],
    'up_2.png': [('礦工的比賽' + S, '待接取'), ('夢德洞窟' + S, '待接取'), ('精靈少女', '待接取'), ('天空之島(2.5)', '待接取'), ('解救老爺爺' + S, '已完成')],
    'up_3.png': [('深紅洞窟', '待接取'), ('英雄島前傳（必做）', '待接取'), ('英雄島後傳', '待接取'), ('恐龍博士' + S, '待接取'), ('卡坦的願望' + S, '待接取')],
    'scroll_1.png': [('恐龍博士' + S, '待接取'), ('卡坦的願望' + S, '待接取'), ('四寶玉之謎' + S, '待接取'), ('礦工的比賽' + S, '待接取'), ('夢德洞窟' + S, '待接取')],
    'scroll_2.png': [('解救老爺爺' + S, '已完成'), ('夢幻洞窟' + S, '已完成'), ('亞姆的斧頭' + S, '已完成'), ('五兄弟之謎' + S, '已完成'), ('強盜的洞穴' + S, '已完成')],
    'scroll_3.png': [('馬祖快遞' + S, '已完成'), ('強恩一族' + S, '已完成'), ('伐木證書' + S, '已完成'), ('黃金羚羊之謎' + S, '已完成'), ('龍的巢穴' + S, '已完成')],
    'scroll_4.png': [('伐木證書' + S, '已完成'), ('黃金羚羊之謎' + S, '已完成'), ('龍的巢穴' + S, '已完成'), ('猜謎三兄弟' + S, '已完成'), ('彌生和日美子' + S, '已完成')],
    'g.png': [('成人儀式', '進行中'), ('漆黑洞窟(一轉)', '待接取'), ('漆黑洞窟(二轉)', '待接取'), ('漆黑洞窟(三轉)', '待接取'), ('漆黑洞窟(四轉)', '待接取'), ('漆黑洞窟(五轉)', '待接取')],
    'ui/detail.png': [('初入石器', '進行中'), ('成人儀式', '待接取'), ('漆黑洞窟(一轉)', '待接取'), ('漆黑洞窟(二轉)', '待接取'), ('漆黑洞窟(三轉)', '待接取'), ('漆黑洞窟(四轉)', '待接取')],
}
HEADS = {'up_1.png': '琉璃洞窟', 'scroll_3.png': '琉璃洞窟', 'g.png': '成人儀式', 'ui/detail.png': '初入石器'}
have = {f: qd.Img.from_file(CACHE / f) for f in TRUTH if (CACHE / f).exists()}
if len(have) < len(TRUTH):
    print('SKIP：缺少部分 fixture 截圖', sorted(set(TRUTH) - set(have)))

# ---- 1. 名稱表 / 樣板檔 ----
names = qd.known_names()
check('名稱表含 1.82 清單', '彌生和日美子(1.82)' in names and '成人儀式' in names and len(qd.set_182()) >= 19, str(len(qd.set_182())))
check('分頁：成人儀式 = 主線、彌生 = 支線', qd.tab_of('成人儀式') == '主線' and qd.tab_of('彌生和日美子(1.82)') == '支線')
check('snap_name 容錯', qd.snap_name('彌生和日美子(1.82') == '彌生和日美子(1.82)' and qd.snap_name('彌生和日美子（1.82）') == '彌生和日美子(1.82)' and qd.snap_name('xyz') is None)
tpl_all = qd.load_tpl()
check('樣板檔：列樣板 >= 25 個名稱', len(tpl_all['row']) >= 25, str(len(tpl_all['row'])))
check('樣板鍵都在任務表', all(n in names for n in tpl_all['row']) and all(n in names for n in tpl_all['head']))

# ---- 2. 版面 / 狀態（用全部樣板）----
ok_status = tot = 0
for f, truth in TRUTH.items():
    if f not in have:
        continue
    rows = qd.visible_rows(have[f])
    check(f'{f} 列數 = {len(truth)}', len(rows) == len(truth), str(len(rows)))
    for r, (_, st) in zip(rows, truth):
        tot += 1
        ok_status += r['status'] == st
check('狀態（進行中 / 待接取 / 已完成）全對', ok_status == tot and tot >= 40, f'{ok_status}/{tot}')
if 'g.png' in have and 'up_2.png' in have:
    check('傳送鈕：待接取任務是藍色、進行中（重置任務 / 無鈕）不是', qd.transfer_button(have['up_2.png']) and not qd.transfer_button(have['g.png']) and not qd.transfer_button(have['ui/detail.png']))
    check('分頁判斷', qd.tab_active(have['g.png']) == '主線' and qd.tab_active(have['up_2.png']) == '支線')
if 'up_3.png' in have:
    check('▲ 偵測：捲動後有、未捲動（detail）沒有', qd.arrow_up(have['up_3.png']) and not qd.arrow_up(have['ui/detail.png']))

# ---- 3. 標題：留一張法（樣板排除該張圖自己的列；該任務只在這一張出現的不算分母，但不准讀成別的）----
seen_in = {}
for f, truth in TRUTH.items():
    for t, _ in truth:
        seen_in.setdefault(t, set()).add(f)
right = wrong = unseen_ok = n_seen = n_unseen = 0
for f, truth in TRUTH.items():
    if f not in have:
        continue
    loo = {'row': {}, 'head': {}}
    for g, tr in TRUTH.items():
        if g == f or g not in have:
            continue
        for r, (t, _) in zip(qd.visible_rows(have[g]), tr):
            qd.learn_tpl(loo, 'row', t, r['bm'])
    for r, (t, _) in zip(qd.visible_rows(have[f]), truth):
        got, best, second = qd.match_title(r['bm'], 'row', loo)
        if seen_in[t] - {f}:
            n_seen += 1
            right += got == t
            wrong += got not in (None, t)
        else:
            n_unseen += 1
            unseen_ok += got is None
check('留一張法：看過的標題讀對 >= 95%', n_seen >= 30 and right / n_seen >= 0.95, f'{right}/{n_seen}')
check('留一張法：沒看過的標題不誤讀成別的任務', wrong == 0 and unseen_ok == n_unseen, f'誤讀 {wrong}、沒看過 {n_unseen} 中回 None {unseen_ok}')
# 全樣板：全部讀對
good = total = 0
for f, truth in TRUTH.items():
    if f in have:
        for r, (t, st) in zip(qd.parse(have[f], tpl_all), truth):
            total += 1
            good += r['title'] == t and r['status'] == st and r['how'] == 'tpl'
check('全樣板：標題 + 狀態逐列全對', good == total, f'{good}/{total}')
for f, h in HEADS.items():
    if f in have:
        got = qd.match_title(qd.head_bitmap(have[f]), 'head', tpl_all)[0]
        check(f'中間標題 {f} = {h}', got == h, str(got))

# ---- 4. OCR 退回 + 合併 ----
if 'up_2.png' in have:
    empty = {'row': {}, 'head': {}}
    rows = qd.parse(have['up_2.png'], empty, lambda top: '')
    check('沒樣板 + OCR 空 → 標題 None（不亂猜）', all(r['title'] is None for r in rows))
    tops = [r['top'] for r in qd.visible_rows(have['up_2.png'])]
    seq = ['礦工的比賽(1.82', '夢德洞窟（1.82）', '精靈少女 ', '天空之島(2.5)', 'zzz']
    m = dict(zip(tops, seq))
    rows = qd.parse(have['up_2.png'], empty, lambda top: m[top])
    check('OCR 退回：snap 到表名，how = ocr，亂碼 = None', [r['title'] for r in rows] == ['礦工的比賽(1.82)', '夢德洞窟(1.82)', '精靈少女', '天空之島(2.5)', None] and rows[0]['how'] == 'ocr', str([r['title'] for r in rows]))
    t2 = {'row': {}, 'head': {}}
    for r in rows:
        if r['how'] == 'ocr':
            qd.learn_tpl(t2, 'row', r['title'], r['bm'])
    check('OCR 認出後存樣板，下次走樣板', [r['title'] for r in qd.parse(have['up_2.png'], t2)][:4] == ['礦工的比賽(1.82)', '夢德洞窟(1.82)', '精靈少女', '天空之島(2.5)'])
if 'up_1.png' in have and 'scroll_2.png' in have and 'scroll_3.png' in have:
    pages = [qd.parse(have[f], tpl_all) for f in ('scroll_2.png', 'scroll_3.png')]
    rows, gaps = qd.merge_pages(pages)
    check('合併：scroll_2 → scroll_3 有共同列（馬祖 / 強盜…不同頁各自），去重', gaps in (0, 1) and len({r['title'] for r in rows}) == len(rows))
    pages = [qd.parse(have[f], tpl_all) for f in ('up_1.png', 'up_2.png')]
    rows, gaps = qd.merge_pages(pages)
    check('合併：沒有共同列 → gaps = 1 + 全部列保留', gaps == 1 and len(rows) == 10)
    p1 = qd.parse(have['scroll_1.png'], tpl_all)
    p2 = qd.parse(have['up_2.png'], tpl_all)    # 礦工 / 夢德 與 scroll_1 後 2 列重疊
    rows, gaps = qd.merge_pages([p1, p2])
    check('合併：重疊 2 列 → gaps 0、列數 8', gaps == 0 and len(rows) == 8, f'{gaps} {len(rows)}')

# ---- 5. accept 防呆（fake 遊戲）----
clicks = []
msgs = []


class Game:
    """假遊戲：live() 回固定截圖；gui 記錄動作；其餘依測試設定"""
    def __init__(self, shot):
        self.shot = shot


def install(shot, head=('恐龍博士(1.82)', 'tpl'), transfer=True, states=('dialog',), dialog=None, final='進行中'):
    clicks.clear()
    qd.live = lambda: shot
    qd.sleep = lambda s: None
    uikit.sleep = lambda s: None
    uikit.preflight = lambda src, fast=True: 0
    uikit.is_open = lambda p: True
    uikit.gui = lambda *a, note='': clicks.append(a) or ''
    uikit.fail = lambda src, rc, msg: (msgs.append(msg), rc)[1]
    qd.open_detail = lambda: True
    qd.close_detail = lambda: True
    qd._read_head = lambda img, tpl: head
    qd.transfer_button = lambda img: transfer
    it = iter(states)
    last = {'s': states[-1]}
    uikit.screen = lambda full=False: {'state': next(it, last['s'])}
    qd.clock = lambda: 0
    qd.notice_open = lambda: False
    import quest
    quest.check_dialog_irreversible = lambda: dialog or {'blocked': False, 'reason': '', 'body': ['x'], 'buttons': ['接受', '再見']}
    qd.read_list = lambda tab, dy=250, learn=True: {'ok': True, 'rows': [{'title': '恐龍博士(1.82)', 'status': final}], 'gaps': 0}
    qd.select_tab = lambda tab: True
    qd.save_tpl = lambda *a, **k: None


def clicked(xy):
    return any(a[0] == 'seq' and f'click {xy[0]} {xy[1]}' in a[1] for a in clicks)


if 'up_3.png' in have:
    shot = have['up_3.png']
    install(shot)
    # a. 禁區：一般 safe_click 點傳送鈕位置 → 拒絕
    try:
        uikit.safe_click(qd.BTN[0], qd.BTN[1], qd.PANEL)
        check('forbidden：傳送 / 重置鈕位置一般點擊被擋', False)
    except uikit.ForbiddenClick:
        check('forbidden：傳送 / 重置鈕位置一般點擊被擋', True)
    # b. 標題不符
    install(shot, head=('成人儀式', 'tpl'))
    rc = qd.accept('恐龍博士(1.82)')
    check('標題不符 → 122，沒點傳送', rc == qd.EXIT_HEAD_MISMATCH and not clicked(qd.BTN), str(rc))
    install(shot, head=(None, None))
    rc = qd.accept('恐龍博士(1.82)')
    check('中間標題讀不出 → 122，沒點傳送', rc == qd.EXIT_HEAD_MISMATCH and not clicked(qd.BTN), str(rc))
    # c. 不是藍色傳送鈕（重置任務）
    install(shot, transfer=False)
    rc = qd.accept('恐龍博士(1.82)')
    check('不是藍色傳送鈕 → 124，沒點', rc == qd.EXIT_NOT_TRANSFER and not clicked(qd.BTN), str(rc))
    # d. 狀態不是待接取
    install(have['up_2.png'])
    rc = qd.accept('解救老爺爺(1.82)')
    check('已完成的任務 → 123，沒點任何列 / 傳送', rc == qd.EXIT_NOT_PENDING and not clicked(qd.BTN) and not any(a[0] == 'seq' and a[1].startswith('click 275') for a in clicks), str(rc))
    install(have['up_2.png'])
    rc = qd.accept('礦工的比賽(1.82)', dry_run=True)
    check('dry-run：驗證通過也不點傳送（head 為假值時 → 122）', rc == qd.EXIT_HEAD_MISMATCH and not clicked(qd.BTN), str(rc))
    install(shot)
    rc = qd.accept('恐龍博士(1.82)', dry_run=True)
    check('dry-run 通過：回 0、有點列（選任務）、沒點傳送', rc == 0 and any(a[0] == 'seq' and a[1].startswith('click 275 575') for a in clicks) and not clicked(qd.BTN), str(rc))
    # e. 不在列表 / 不在任務表
    install(have['g.png'])
    rc = qd.accept('恐龍博士(1.82)')
    check('列表裡沒有該任務 → 121', rc == qd.EXIT_NOT_FOUND, str(rc))
    rc = qd.accept('不存在的任務')
    check('不在任務表 → 用法錯誤 1', rc == 1, str(rc))
    # f. 傳送後沒對話框
    install(shot, states=('idle',))
    qd.clock = lambda c=[0]: c.__setitem__(0, c[0] + 5) or c[0]
    rc = qd.accept('恐龍博士(1.82)')
    check('傳送後沒對話框 → 125（不點接受）', rc == qd.EXIT_NO_DIALOG and clicked(qd.BTN) and not clicked((948, 461)), str(rc))
    # f2. 提示視窗（條件不達標）
    install(shot)
    qd.notice_open = lambda: True
    qd.dismiss_notice = lambda: clicks.append(('dismiss',)) or True
    qd.uikit.snap = lambda tag: 'x.png'
    rc = qd.accept('恐龍博士(1.82)')
    check('傳送後跳提示視窗 → 128，關視窗、沒按接受', rc == qd.EXIT_NOT_QUALIFIED and ('dismiss',) in clicks and not clicked((948, 461)), str(rc))
    # g. 對話框防護
    import quest
    install(shot, dialog={'blocked': True, 'reason': '含不可逆關鍵字', 'body': ['轉生'], 'buttons': ['接受']})
    qd.uikit.snap = lambda tag: 'x.png'
    rc = qd.accept('恐龍博士(1.82)')
    check('對話框含不可逆字 → 126，沒按左鈕', rc == qd.EXIT_DIALOG_GUARD and not clicked((948, 461)), str(rc))
    install(shot, dialog={'blocked': False, 'reason': '', 'body': ['x'], 'buttons': ['戰鬥', '再見']})
    rc = qd.accept('恐龍博士(1.82)')
    check('左鈕不是「接受」→ 126，沒按左鈕', rc == qd.EXIT_DIALOG_GUARD and not clicked((948, 461)), str(rc))
    install(shot, dialog={'blocked': False, 'reason': '', 'body': [], 'buttons': []})
    rc = qd.accept('恐龍博士(1.82)')
    check('對話框文字讀不到 → 126，沒按', rc == qd.EXIT_DIALOG_GUARD and not clicked((948, 461)), str(rc))
    # h. 成功 / 驗證失敗
    install(shot, states=('dialog', 'idle'))
    rc = qd.accept('恐龍博士(1.82)')
    check('成功：點傳送 → 按接受 → 重開詳情「進行中」→ 0', rc == 0 and clicked(qd.BTN) and clicked((948, 461)), str(rc))
    install(shot, states=('dialog', 'idle'), final='待接取')
    rc = qd.accept('恐龍博士(1.82)')
    check('接受後仍待接取 → 127', rc == qd.EXIT_NOT_ACCEPTED, str(rc))
    install(shot, states=('dialog', 'idle'))
    rc = qd.accept('恐龍博士(1.82)', verify=False)
    check('verify=False：按接受後不重開詳情、LAST.state=accepted', rc == 0 and qd.LAST.get('state') == 'accepted' and clicked(qd.BTN), str(rc))
    install(shot, states=('dialog', 'dialog'))
    rc = qd.accept('恐龍博士(1.82)', verify=False)
    check('verify=False：對話框還在 → 127', rc == qd.EXIT_NOT_ACCEPTED, str(rc))
    install(shot, states=('dialog', 'dialog', 'dialog'))
    n_before = len(clicks)
    rc = qd.accept('恐龍博士(1.82)', presses=2)
    check('對話框一直在 → 最多按 presses=2 次', sum(1 for a in clicks if a[0] == 'seq' and 'click 948 461' in a[1]) == 2, str(rc))

# ---- task_status（questrun 用）：純邏輯，換掉面板開關與列表讀取 ----
_saved = (qd.open_detail, qd.close_detail, qd.read_list, qd.uikit.preflight)
qd.open_detail, qd.close_detail, qd.uikit.preflight = (lambda: True), (lambda: True), (lambda src, fast=True: 0)
qd.read_list = lambda tab, dy=qd.DEFAULT_DY: {'ok': True, 'rows': [{'title': '彌生和日美子(1.82)', 'status': '進行中', 'how': 'tpl'}], 'gaps': 0, 'tab': tab, 'pages': 1}
check('task_status：找到 → (0, 進行中)', qd.task_status('彌生和日美子(1.82)') == (0, '進行中'))
check('task_status：列表沒有 → (0, None)', qd.task_status('亞姆的斧頭(1.82)') == (0, None))
check('task_status：不在任務表 → (1, None)', qd.task_status('不存在的任務')[0] == 1)
qd.read_list = lambda tab, dy=qd.DEFAULT_DY: {'ok': False, 'why': '截圖失敗', 'rows': [], 'gaps': 0}
check('task_status：讀失敗 → 121', qd.task_status('彌生和日美子(1.82)')[0] == qd.EXIT_NOT_FOUND)
qd.open_detail = lambda: False
check('task_status：面板打不開 → 120', qd.task_status('彌生和日美子(1.82)')[0] == qd.EXIT_NO_PANEL)
qd.open_detail, qd.close_detail, qd.read_list, qd.uikit.preflight = _saved

print('\n失敗 %d 項' % fails if fails else '\n全部通過')
sys.exit(1 if fails else 0)
