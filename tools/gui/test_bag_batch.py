#!/usr/bin/env python3
"""bag.depot_take_items / depot_store_many 批次存取離線測試（不碰遊戲；2026-10-17 daily 倉庫批次化）。
用法：uv run --no-project python tools/gui/test_bag_batch.py
低階（Session / select_role / open_depot / find_item / take_slot / store_slot / goto_page）全換假的，數：面板開幾次、倉庫子分頁切幾次、切回背包頁幾次。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import testenv  # noqa: E402,F401
import bag  # noqa: E402

fails = 0


def check(name, cond, extra=''):
    global fails
    print(('PASS' if cond else 'FAIL'), name, extra)
    if not cond:
        fails += 1


class Rec:
    def __init__(self, **kw):
        self.opens = self.selects = self.sub_switch = self.bag_pages = 0
        self.cur_sub = None
        self.takes, self.stores = [], []
        self.missing_depot, self.bag_has = set(), None
        self.store_fail = {}
        self.__dict__.update(kw)


R = Rec()


class FakeSession:
    rc = 0

    def __enter__(self):
        R.opens += 1
        return self

    def __exit__(self, *a):
        return False


def fake_open_depot(sub):
    if R.cur_sub != sub:
        R.sub_switch += 1
        R.cur_sub = sub
    return 0


def fake_goto(page):
    if page == 'bag':
        R.bag_pages += 1
        R.cur_sub = None
    return 0


def fake_find(want, depot=False, **k):
    if depot:
        return None if want in R.missing_depot else abs(hash(want)) % 15
    return None if (R.bag_has is not None and want not in R.bag_has) else abs(hash(want)) % 15


def fake_take(i, want, sub='personal', kind='consumable', dclick=False):
    assert dclick, '批次取出必須走 dclick'
    fake_open_depot(sub)
    R.takes.append((want, sub))
    return 0, [0]


def fake_store(i, want, sub='public'):
    fake_open_depot(sub)                                  # 真 store_slot 內部先 open_depot（已在該分頁不點）
    R.stores.append((want, sub))
    return R.store_fail.get(want, 0)


def install():
    global R
    R = Rec()
    bag.Session = FakeSession
    bag.select_role = lambda role, ctx=None: (setattr(R, 'selects', R.selects + 1) or 0)
    bag.open_depot, bag.goto_page, bag.find_item = fake_open_depot, fake_goto, fake_find
    bag.take_slot, bag.store_slot = fake_take, fake_store
    bag.log = lambda m: None


items5 = [('A', 'personal'), ('C', 'public'), ('B', 'personal'), ('P', 'personal'), ('D', 'public')]
install()
rc, res = bag.depot_take_items('DKBO3', items5)
check('取 5 樣（3 個人 + 2 公共）：rc 0、全 0', rc == 0 and all(v == 0 for v in res.values()) and len(res) == 5, f'{rc} {res}')
check('面板只開 1 次、選角 1 次', R.opens == 1 and R.selects == 1, f'{R.opens} {R.selects}')
check('倉庫分頁只切 2 次（personal + public 各 1）', R.sub_switch == 2, str(R.sub_switch))
check('切回背包頁：整批結束只 1 次（不是每樣）', R.bag_pages == 1, str(R.bag_pages))
check('個人先取（照 items 先出現的順序）：A B P → C D', R.takes == [('A', 'personal'), ('B', 'personal'), ('P', 'personal'), ('C', 'public'), ('D', 'public')], str(R.takes))

install()
R.missing_depot = {'B'}
got = []
rc, res = bag.depot_take_items('DKBO3', items5, on_item=lambda n, s, r: got.append((n, r)))
check('倉庫找不到 B → 該樣 92、其餘照取、整體 rc 0；on_item 每樣都回呼', rc == 0 and res['B'] == 92 and res['A'] == 0 and len(got) == 5, f'{rc} {res} {got}')

install()
R.bag_has = {'A', 'B', 'C', 'P'}                      # 批次後核對：D 在背包讀不到 → 95
rc, res = bag.depot_take_items('DKBO3', items5)
check('整批結束核對：D 取了但背包讀不到 → 該樣 95、整體 rc 95（不重做）', rc == 95 and res['D'] == 95 and len(R.takes) == 5, f'{rc} {res}')

install()
bag.take_slot = lambda i, w, s='personal', k='consumable', dclick=False: (95, []) if w == 'B' else fake_take(i, w, s, k, dclick)
rc, res = bag.depot_take_items('DKBO3', items5)
check('B 取出失敗 95 → 立即停，後面沒處理的不在結果裡', rc == 95 and res == {'A': 0, 'B': 95}, f'{rc} {res}')

install()
st = [('A', 'personal'), ('B', 'personal'), ('C', 'public'), ('D', 'personal')]
rc, res = bag.depot_store_many('DKBO3', st)
check('存 4 樣（3 個人 + 1 公共）：面板 1 次、分頁各 1 次（共 2）、切回背包頁 1 次', rc == 0 and R.opens == 1 and R.sub_switch == 2 and R.bag_pages == 1, f'{rc} {R.opens} {R.sub_switch} {R.bag_pages}')
check('公共先存、個人後存', R.stores == [('C', 'public'), ('A', 'personal'), ('B', 'personal'), ('D', 'personal')], str(R.stores))

install()
R.bag_has = {'A', 'C'}
rc, res = bag.depot_store_many('DKBO3', st)
check('背包找不到的 B / D → 92 繼續；其餘照存', rc == 0 and res['B'] == 92 and res['D'] == 92 and res['A'] == 0 and res['C'] == 0, f'{rc} {res}')

install()
R.store_fail = {'A': 95}
rc, res = bag.depot_store_many('DKBO3', st)
check('A 存入 95（倉庫滿）→ 停手並切回背包頁、回 95；C 已存、B / D 不在結果', rc == 95 and res.get('A') == 95 and 'B' not in res and res.get('C') == 0 and R.bag_pages == 1, f'{rc} {res}')

print('ALL PASS' if not fails else f'FAILED {fails}')
sys.exit(1 if fails else 0)
