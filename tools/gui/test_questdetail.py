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
REAL_READ_LIST = qd.read_list          # install() / task_status 測試會換掉 qd.read_list，這裡先存真的
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


# ---- 6. 捲動：一次捲「可見列數 − 1 列」、漏列退回小步（模擬列表，不碰遊戲）----
check('page_dy：5 列 → 約 147、夾在 [100, 150]', qd.page_dy(5) == 147 and qd.page_dy(1) == qd.DEFAULT_DY and qd.page_dy(9) == qd.MAX_DY, str(qd.page_dy(5)))
check('page_dy 比舊的 100 大（每頁多 ≥ 1 列）', qd.page_dy(5) * qd.SCROLL_RATIO >= 100 * qd.SCROLL_RATIO + 80 - 1)


class World:
    """模擬任務列表：N 列、列距 80、可視 5 列；drag dy 位移 = dy × ratio（真實比例 ratio，與程式假設的 2.17 可不同）"""
    def __init__(self, n=23, ratio=2.17):
        self.n, self.ratio, self.off = n, ratio, 0.0
        self.names = [f'T{i}' for i in range(n)]
        self.scrolls = []

    def rows(self):
        first = int(self.off // 80)
        out = []
        for i in range(first, min(self.n, first + 6)):
            top = 266 + i * 80 - self.off
            if top >= 262 and top + 80 <= 722 + 20:
                out.append({'title': self.names[i], 'status': '待接取', 'top': top, 'cy': top, 'bm': 0, 'how': 'tpl', 'score': 1.0})
        return out[:5]

    def scroll(self, down, dy=qd.DEFAULT_DY):
        self.scrolls.append((down, dy))
        self.off = max(0, min((self.n - 5) * 80, self.off + (1 if down else -1) * dy * self.ratio))


def run_world(w):
    qd.scroll = w.scroll
    qd._stable_shot = lambda max_tries=4: object()
    qd.parse = lambda img, tpl=None, ocr_fn=None: w.rows()
    qd._learn_page = lambda *a, **k: None
    qd.select_tab = lambda tab: True
    qd.scroll_top = lambda dy=qd.TOP_DY: True
    qd.load_tpl = lambda path=None: {'row': {}, 'head': {}}
    return REAL_READ_LIST('支線')


_keep = (qd.scroll, qd._stable_shot, qd.parse, qd._learn_page, qd.select_tab, qd.scroll_top, qd.load_tpl, qd.read_list)
w = World(23, 2.17)
r = run_world(w)
names_got = [x['title'] for x in r['rows']]
check('模擬列表（比例相符）：23 列全讀到、不漏、無 gaps', names_got == w.names and r['gaps'] == 0, f'{len(names_got)} gaps={r["gaps"]}')
big_pages = r['pages']
check('大步頁數比舊的 dy=100 少（舊約 23/2.75 = 9 頁）', big_pages <= 7 and all(dy >= 140 for d, dy in w.scrolls if d), f'{big_pages} 頁 {w.scrolls[:3]}')
check('比例相符時不需要退回小步', r['fallbacks'] == 0)
w = World(23, 3.2)                                     # 實際位移比假設大 → 大步會漏列，要偵測到並退回小步
r = run_world(w)
names_got = [x['title'] for x in r['rows']]
check('位移比預期大（漏列）→ 偵測沒重疊、退回小步、仍全讀到', names_got == w.names and r['fallbacks'] >= 1, f'{len(names_got)} fb={r["fallbacks"]} gaps={r["gaps"]}')
check('退回時先往上捲回再小步（有 down=False 與 dy=100 的 down=True）', any(not d for d, _ in w.scrolls) and any(d and dy == qd.DEFAULT_DY for d, dy in w.scrolls))
# overlaps 純函式
a = [{'title': 'A', 'bm': 0}, {'title': 'B', 'bm': 0}]
check('overlaps：上一頁最後一列在新頁 = 有重疊', qd.overlaps(a, [{'title': 'B', 'bm': 0}, {'title': 'C', 'bm': 0}]))
check('overlaps：只剩第一列重疊（最後一列不見）= 視為漏列', not qd.overlaps(a, [{'title': 'A', 'bm': 0}]))
check('overlaps：最後一列不在新頁 = 沒重疊', not qd.overlaps(a, [{'title': 'C', 'bm': 0}, {'title': 'D', 'bm': 0}]))
check('overlaps：空頁不擋', qd.overlaps([], a) and qd.overlaps(a, []))
qd.scroll, qd._stable_shot, qd.parse, qd._learn_page, qd.select_tab, qd.scroll_top, qd.load_tpl, qd.read_list = _keep
# 真實截圖頁序（scroll_3 → scroll_4 有共同列、scroll_2 → scroll_3 / up_1 → up_2 沒有）
if all(f in have for f in ('scroll_2.png', 'scroll_3.png', 'scroll_4.png', 'up_1.png', 'up_2.png')):
    pg = {f: qd.parse(have[f], tpl_all) for f in ('scroll_2.png', 'scroll_3.png', 'scroll_4.png', 'up_1.png', 'up_2.png')}
    check('真實截圖：scroll_3 → scroll_4 有重疊（最後一列在新頁）', qd.overlaps(pg['scroll_3.png'], pg['scroll_4.png']))
    check('真實截圖：up_1 → up_2 沒有重疊 = 會觸發退回小步', not qd.overlaps(pg['up_1.png'], pg['up_2.png']))


# ---- status_all：逐人讀（假 char / 假詳情；2026-10-12 四寶玉之謎 DKBO3 / DKBO5 沒完成）----
class FakeAll:
    def __init__(self, cur='DKBO', st=None, sw_rc=None, rd_rc=None):
        self.cur, self.calls = cur, []
        self.st, self.sw_rc, self.rd_rc = st or {}, sw_rc or {}, rd_rc or {}

    def current(self):
        return 0, self.cur

    def switch(self, who):
        self.calls.append(('switch', who))
        rc = self.sw_rc.get(who, 0)
        if not rc:
            self.cur = who
        return rc

    def ensure(self, who):
        self.calls.append(('ensure', who))
        self.cur = who
        return 0

    def read(self, names, dy=None):
        self.calls.append(('read', self.cur))
        rc = self.rd_rc.get(self.cur, 0)
        return rc, ({} if rc else {n: self.st.get(self.cur, qd.DONE) for n in names})


T4 = '四寶玉之謎(1.82)'
F = FakeAll(cur='DKBO3', st={'DKBO3': qd.DOING, 'DKBO5': qd.DOING})
rc, res = qd.status_all([T4], tools=F)
check('status_all：當前 DKBO3 先讀、切 4 次、最後 ensure DKBO', rc == 0 and F.calls[0] == ('read', 'DKBO3')
      and sum(1 for c in F.calls if c[0] == 'switch') == 4 and F.calls[-1] == ('ensure', 'DKBO'), str(F.calls))
check('laggards = DKBO3、DKBO5', sorted(qd.laggards(res, T4)) == ['DKBO3', 'DKBO5'], str(res))
F = FakeAll(cur='DKBO')
rc, res = qd.status_all([T4], roles=['DKBO', 'DKBO2'], tools=F)
check('status_all：當前 DKBO 先讀、只切 DKBO2、讀完切回 DKBO', rc == 0 and F.calls == [('read', 'DKBO'), ('switch', 'DKBO2'), ('read', 'DKBO2'), ('ensure', 'DKBO')], str(F.calls))
F = FakeAll(sw_rc={'DKBO4': 61})
rc, res = qd.status_all([T4], tools=F)
check('切不到 DKBO4 → 該人 None、其他照讀、rc 61', rc == 61 and res['DKBO4'] is None and res['DKBO5'] == {T4: qd.DONE} and 'DKBO4' in qd.laggards(res, T4))
F = FakeAll(rd_rc={'DKBO2': 9})
rc, res = qd.status_all([T4], tools=F)
check('讀到驗證視窗 9 → 立即停（不再切人、不 ensure）', rc == 9 and ('switch', 'DKBO3') not in F.calls and not any(c[0] == 'ensure' for c in F.calls), str(F.calls))
rc, res = qd.status_all(['不存在的任務名稱XYZ'], tools=FakeAll())
check('任務名不在 TaskExplan → 用法錯、不碰', rc == 1 and res == {})
rows = [{'title': T4, 'status': qd.DOING}, {'title': '黃金羚羊之謎(1.82)', 'status': qd.UNKNOWN}]
check('all_found：狀態 ? 不算找到', qd.all_found(rows, [T4]) and not qd.all_found(rows, [T4, '黃金羚羊之謎(1.82)']))

print('\n失敗 %d 項' % fails if fails else '\n全部通過')
sys.exit(1 if fails else 0)
