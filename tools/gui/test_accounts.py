#!/usr/bin/env python3
"""帳號對照 + 登入畫面帳號核對的離線測試（不碰遊戲；只用標準函式庫）。
accounts.py（設定檔、容錯正規化、一致性判定）、netwatch.relogin 的帳號核對流程（符合 → 登錄；不符 → 重打 → 核對 → 登錄；
重打後仍不符 / 讀不出 / 清不掉 / 密碼欄變空 / 鎖被佔 → halt）、沒設定檔時舊行為不變、relogin.py 有設定檔時多視窗不再 109、log 不含帳號名。
測試用假帳號（acct_a / acct_b / test01 / test02），真帳號只在本機 accounts.local.json。
選配：本機有 accounts.local.json 和登入畫面截圖 tools/.cache/net5.png 時，加跑一段「真 OCR 讀 fixture 檔」（ocr.ps1 -Image，只讀檔、不碰遊戲）；
  路徑可用 PSA_FIXTURE_ACCOUNTS / PSA_FIXTURE_SHOT 指定，PSA_SKIP_OCR_FIXTURE=1 跳過。
用法：uv run --no-project python tools/gui/test_accounts.py"""
import contextlib
import io
import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import testenv  # noqa: E402,F401  紀錄檔轉向暫存；PSA_TEST_PROCS=PrimalSA；PSA_ACCOUNTS_FILE=不存在
import accounts  # noqa: E402
import clients  # noqa: E402
import netwatch  # noqa: E402

fails = 0


def check(name, cond, extra=''):
    global fails
    print(('PASS ' if cond else 'FAIL ') + name + (' ' + str(extra) if extra and not cond else ''))
    if not cond:
        fails += 1


TMP = Path(tempfile.mkdtemp(prefix='psatest-acct-'))
NOFILE = os.environ['PSA_ACCOUNTS_FILE']


def use_cfg(d, name='acc.json'):
    p = TMP / name
    p.write_text(d if isinstance(d, str) else json.dumps(d), encoding='utf-8')
    os.environ['PSA_ACCOUNTS_FILE'] = str(p)


def no_cfg():
    os.environ['PSA_ACCOUNTS_FILE'] = NOFILE


# ================================================================ 1) accounts.py
check('testenv：預設沒有設定檔', accounts.load() == ('none', {}) and accounts.for_client() == ('none', ''))
use_cfg({'PrimalSA': 'acct_a', 'PrimalSA2': 'acct_b'})
check('load ok（鍵正規化成小寫程序名）', accounts.load() == ('ok', {'primalsa': 'acct_a', 'primalsa2': 'acct_b'}))
check('for_client 主視窗', accounts.for_client() == ('ok', 'acct_a'))
check('for_client PrimalSA2（大小寫 / .exe 不分）', accounts.for_client('primalsa2.exe') == ('ok', 'acct_b'))
check('for_client 不在對照表 → missing', accounts.for_client('PrimalSA3') == ('missing', ''))
os.environ['PSA_CLIENT'] = 'PrimalSA2'
check('for_client 讀 PSA_CLIENT', accounts.for_client() == ('ok', 'acct_b'))
os.environ.pop('PSA_CLIENT')
use_cfg('not json')
check('壞 JSON → invalid', accounts.load()[0] == 'invalid' and accounts.for_client()[0] == 'invalid')
use_cfg({'PrimalSA': 'a{b}'})
st, why = accounts.load()
check('帳號含特殊字 → invalid，理由不含帳號', st == 'invalid' and 'a{b}' not in why, why)
use_cfg({'PrimalSA': 'dkbo1', 'PrimalSA2': 'DKB01'})
check('兩帳號容錯後相同（o/0）→ invalid', accounts.load()[0] == 'invalid')
use_cfg({'PrimalSA': 'test01', 'PrimalSA2': 'test02'})
check('只差尾碼 1 / 2 → 可區分（ok）', accounts.load()[0] == 'ok')
check('canon：o→0、l/i→1、去空白、小寫', accounts.canon(' TeSt O l i ') == 'test011')
check('classify：三倍數一致 = 本視窗 → self', accounts.classify(['test01', 'testO1', 'TEST01'], 'test01') == 'self')
check('classify：尾碼 2 ≠ 1 → other（不混淆）', accounts.classify(['test02'] * 3, 'test01') == 'other')
check('classify：尾碼 1 ≠ 2 → other', accounts.classify(['test01'] * 3, 'test02') == 'other')
check('classify：倍數之間不一致 → unreadable', accounts.classify(['test01', 'test02', 'test01'], 'test01') == 'unreadable')
check('classify：只有 1 個倍數讀到 → unreadable', accounts.classify(['test01', '', ''], 'test01') == 'unreadable')
check('classify：全空 → unreadable', accounts.classify([], 'test01') == 'unreadable')
check('classify：怪字 → unreadable', accounts.classify(['te$t01'] * 3, 'te$t01') == 'unreadable')
check('實測寫法（字母 o 被讀成 0）：xyzo001 讀成 xyz0001 → self', accounts.classify(['xyz0001'] * 3, 'xyzo001') == 'self')
check('實測寫法：xyz0001 對 xyzo002 → other', accounts.classify(['xyz0001'] * 3, 'xyzo002') == 'other')
# 文字游標容錯（caret=True；2026-10-16 三個視窗重打帳號後核對「不符 / 讀不出」：字尾有游標「|」）
check('caret：字尾 | → self', accounts.classify(['xyz0001|'] * 3, 'xyzo001', caret=True) == 'self')
check('caret：各倍數游標讀法不同（| / I / 沒讀到）→ self', accounts.classify(['xyz0001|', 'xyz0001I', 'xyz0001'], 'xyzo001', caret=True) == 'self')
check('caret 關（舊行為）：字尾 | → other / unreadable 不變', accounts.classify(['xyz0001|'] * 3, 'xyzo001') == 'other'
      and accounts.classify(['xyz0001|', 'xyz0001'], 'xyzo001') == 'unreadable')
check('caret：別的帳號 + 游標 → other', accounts.classify(['xyz0002|'] * 3, 'xyzo001', caret=True) == 'other')
check('caret：本帳號 test0、欄位是設定檔另一帳號 test01 → unreadable（分不出，停手）',
      accounts.classify(['test01'] * 3, 'test0', caret=True, others=['test0', 'test01']) == 'unreadable')
check('caret：本帳號 test01、欄位 test01| → self（others 有 test0 也不混淆：交集只有 test01 / test01 去尾不成立）',
      accounts.classify(['test01|'] * 3, 'test01', caret=True, others=['test0', 'test01']) == 'self')
check('caret：尾碼 2 ≠ 1 → other（游標容錯不吃真數字差）', accounts.classify(['test02'] * 3, 'test01', caret=True) == 'other')
check('caret：只有 1 個倍數讀到 → unreadable', accounts.classify(['test01|', '', ''], 'test01', caret=True) == 'unreadable')
check('caret：倍數之間不一致 → unreadable', accounts.classify(['test01', 'test02', 'test01'], 'test01', caret=True) == 'unreadable')
no_cfg()

# ================================================================ 2) netwatch.relogin 帳號核對（假畫面）
netwatch.CACHE = TMP
netwatch.HALT = TMP / 'netwatch.halt'
netwatch.STATE = TMP / 'netwatch.json'
netwatch.ACT_LOCK = TMP / 'act.lock'
netwatch.LOGIN_INPUT_LOCK = TMP / 'login-input.lock'
netwatch.time.sleep = lambda *_: None
LOGS: list = []                     # 所有可能進 log 的文字（log / actlog / errlog / halt 檔 / stdout）
netwatch.log = lambda msg, act=True: LOGS.append(msg)
netwatch.actlog.add = lambda cat, msg, *a, **k: LOGS.append(msg)
netwatch.errlog.add = lambda text, **k: (LOGS.append(text), len(LOGS))[1]
netwatch.errlog.fix = lambda i, text, **k: LOGS.append(text)
netwatch._forget_char = lambda: None
netwatch.recover = lambda *a, **k: {'stub': 1}


class Screen:
    """假登入畫面：帳號欄文字、密碼欄有沒有字、按了登錄沒。gui / _match / _dark_count / _ocr_lines / hud_ok 都由它回答"""
    def __init__(self, field, pwd=True, ocr_mode='ok', typing='ok', clear_ok=True):
        self.field, self.pwd, self.ocr_mode, self.typing, self.clear_ok = field, pwd, ocr_mode, typing, clear_ok
        self.calls, self.logged_in, self.ocr_n = [], False, 0
        self.lock_seen = []          # 打字當下登入輸入鎖在不在

    def gui(self, *a, note=''):
        self.calls.append(a)
        if a[0] == 'click' and (a[1], a[2]) == (str(netwatch.LOGIN_BTN[0]), str(netwatch.LOGIN_BTN[1])):
            self.logged_in = True
        elif a[0] == 'key' and '{BS}' in a[1] and self.clear_ok:
            self.field = ''
        elif a[0] == 'typeq':
            self.lock_seen.append(netwatch.LOGIN_INPUT_LOCK.exists())
            if self.typing == 'ok':
                self.field = a[1]
            elif self.typing == 'wrong':
                self.field = 'acct_x'
            elif self.typing == 'pwd_gone':
                self.field, self.pwd = a[1], False
        return ''

    def match(self, sig):
        if sig == netwatch.SIG_LOGIN:
            return not self.logged_in
        return False

    def dark(self, box):
        if box == netwatch.ACCT_BOX:
            return 93 if self.field else 0
        return 32 if self.pwd else 0

    def ocr_lines(self, box, *opts):
        self.ocr_n += 1
        if self.ocr_mode == 'blind' or not self.field:
            return []
        t = self.field.replace('o', '0')                 # Windows OCR 實測把 o 讀成 0
        if self.ocr_mode == 'flaky':
            return [{'text': t, 'x': 788, 'zoom': 2}, {'text': t + '7', 'x': 788, 'zoom': 3}]
        return [{'text': t, 'x': 788, 'y': 412, 'zoom': z} for z in (2, 3, 4)]

    def hud(self):
        return self.logged_in


def run(scr, **kw):
    netwatch.gui = scr.gui
    netwatch._match = scr.match
    netwatch._dark_count = scr.dark
    netwatch._ocr_lines = scr.ocr_lines
    netwatch.hud_ok = scr.hud
    netwatch._pixels = lambda pts: None          # 版本錯誤黑條偵測不讀真畫面（None = 讀不到 → 不判黑條）
    netwatch.HALT.unlink(missing_ok=True)
    netwatch.STATE.write_text('{"fails": 0}')
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        r = netwatch.relogin('t', **kw)
    LOGS.append(buf.getvalue())
    if netwatch.HALT.exists():
        LOGS.append(netwatch.HALT.read_text(encoding='utf-8'))
    return r


LOGIN = ('click', str(netwatch.LOGIN_BTN[0]), str(netwatch.LOGIN_BTN[1]))
FIELD = ('click', str(netwatch.ACCT_FIELD[0]), str(netwatch.ACCT_FIELD[1]))
use_cfg({'PrimalSA': 'acct_a', 'PrimalSA2': 'acct_b'})

# 符合 → 直接登錄
s = Screen('acct_a')
r = run(s)
check('符合 → reconnected、只點登錄（不點帳號欄、不打字）', r['status'] == 'reconnected' and s.calls == [LOGIN], s.calls)
check('  log 有「帳號欄核對：符合」', any('帳號欄核對：符合' in x for x in LOGS))

# 不符 → 重打 → 核對 → 登錄
s = Screen('acct_b')
r = run(s)
kinds = [c[0] for c in s.calls]
check('不符 → 點帳號欄 → 清空 → typeq 本視窗帳號 → 登錄', r['status'] == 'reconnected' and s.calls[0] == FIELD and kinds == ['click', 'key', 'typeq', 'click']
      and s.calls[2] == ('typeq', 'acct_a') and s.calls[3] == LOGIN, s.calls)
check('  清空鍵序列含 {END}{BS}…{HOME}{DEL}…、不含 {TAB} / {ENTER}', '{END}' in s.calls[1][1] and '{DEL}' in s.calls[1][1]
      and '{TAB}' not in s.calls[1][1] and '{ENTER}' not in s.calls[1][1])
check('  打字當下拿著全視窗登入輸入鎖、結束後放掉', s.lock_seen == [True] and not netwatch.LOGIN_INPUT_LOCK.exists())
check('  log 有「不符」與「（重打後）：符合」', any('帳號欄核對：不符' in x for x in LOGS) and any('帳號欄核對（重打後）：符合' in x for x in LOGS))
check('  沒有點密碼欄附近 / 鑰匙（只點帳號欄 + 登錄）', all(c in (FIELD, LOGIN) for c in s.calls if c[0] == 'click'))

# 重打後仍不符 → halt、不登錄
s = Screen('acct_b', typing='wrong')
r = run(s)
check('重打後仍不符 → halt、沒按登錄', r['status'] == 'halt' and LOGIN not in s.calls and '核對不符' in r['reason'], r)
check('  halt 也放掉輸入鎖', not netwatch.LOGIN_INPUT_LOCK.exists())
s = Screen('acct_b', typing='lost')          # 打字沒進去（欄位還是空）→ 讀不出
r = run(s)
check('重打後讀不出（打字沒進去）→ halt、沒按登錄', r['status'] == 'halt' and LOGIN not in s.calls and '讀不出' in r['reason'], r)

# 讀不出 → halt、什麼都不點
s = Screen('acct_a', ocr_mode='flaky')
r = run(s)
check('OCR 倍數不一致（讀不出）→ halt、沒點任何東西', r['status'] == 'halt' and not s.calls and '讀不出' in r['reason'], r)
check('  讀不出會重讀（游標會閃，最多 3 次 OCR）', s.ocr_n == 3, s.ocr_n)
s = Screen('acct_a', ocr_mode='blind')
r = run(s)
check('OCR 完全讀不到 → halt、沒點', r['status'] == 'halt' and not s.calls)

# 清不掉 / 密碼欄變空
s = Screen('acct_b', clear_ok=False)
r = run(s)
check('帳號欄清不掉 → halt、沒打字、沒登錄', r['status'] == 'halt' and 'typeq' not in [c[0] for c in s.calls] and LOGIN not in s.calls, s.calls)
s = Screen('acct_b', typing='pwd_gone')
r = run(s)
check('重打後密碼欄變空 → halt、沒登錄', r['status'] == 'halt' and LOGIN not in s.calls and '密碼欄' in r['reason'], r)

# 密碼欄空（遊戲沒帶入）→ 舊規則 halt，不核對帳號
s = Screen('acct_a', pwd=False)
r = run(s)
check('密碼欄空 → halt「空的」、沒讀帳號、沒點', r['status'] == 'halt' and '空的' in r['reason'] and s.ocr_n == 0 and not s.calls)

# 輸入鎖被別的視窗佔著 → halt，不打字
netwatch.LOGIN_INPUT_LOCK.write_text('999 0')
_w = netwatch.LOGIN_INPUT_WAIT
netwatch.LOGIN_INPUT_WAIT = 0
s = Screen('acct_b')
r = run(s)
check('輸入鎖被佔 → halt、沒點帳號欄、沒打字', r['status'] == 'halt' and not s.calls and '輸入鎖' in r['reason'], r)
check('  別人的鎖不會被刪', netwatch.LOGIN_INPUT_LOCK.exists())
netwatch.LOGIN_INPUT_WAIT = _w
netwatch.LOGIN_INPUT_LOCK.unlink()

# 多視窗 + 有設定檔：PrimalSA2 照帳號核對跑（不再 halt）
os.environ['PSA_TEST_PROCS'] = 'PrimalSA,PrimalSA2'
os.environ['PSA_CLIENT'] = 'PrimalSA2'
s = Screen('acct_a')
r = run(s)
check('多視窗 PrimalSA2 + 設定檔：帳號欄是主視窗帳號 → 重打成自己的 → 登錄', r['status'] == 'reconnected' and ('typeq', 'acct_b') in s.calls and s.calls[-1] == LOGIN, s.calls)
os.environ.pop('PSA_CLIENT')
s = Screen('acct_a')
r = run(s)
check('多視窗主視窗 + 設定檔：符合 → 直接登錄', r['status'] == 'reconnected' and s.calls == [LOGIN], s.calls)

# 視窗不在對照表 / 沒設定檔 / 設定檔壞 → 舊行為
os.environ['PSA_CLIENT'] = 'PrimalSA3'
os.environ['PSA_TEST_PROCS'] = 'PrimalSA,PrimalSA3'
s = Screen('acct_a')
r = run(s)
check('不在對照表（PrimalSA3）→ 舊行為：多視窗 halt、沒讀帳號、沒點', r['status'] == 'halt' and netwatch.MULTI_HALT in r['reason'] and s.ocr_n == 0 and not s.calls, r)
os.environ.pop('PSA_CLIENT')
os.environ['PSA_TEST_PROCS'] = 'PrimalSA,PrimalSA2'
no_cfg()
s = Screen('acct_a')
r = run(s)
check('沒設定檔 + 多視窗 → 舊行為 halt（理由逐字同 auto_login_check）', r['status'] == 'halt' and r['reason'] == netwatch.auto_login_check()[1] and not s.calls and s.ocr_n == 0, r)
os.environ['PSA_TEST_PROCS'] = 'PrimalSA'
s = Screen('acct_b')
r = run(s)
check('沒設定檔 + 單一視窗 → 舊行為：不讀帳號、只按登錄', r['status'] == 'reconnected' and s.calls == [LOGIN] and s.ocr_n == 0, s.calls)
check('login_mode 沒設定檔 = auto_login_check', netwatch.login_mode() == ('ok', '', ''))
use_cfg('{broken')
s = Screen('acct_b')
r = run(s)
check('設定檔壞 + 單一視窗 → 舊行為（只按登錄）', r['status'] == 'reconnected' and s.calls == [LOGIN] and s.ocr_n == 0)
use_cfg({'PrimalSA': 'acct_a', 'PrimalSA2': 'acct_b'})
check('login_mode 有設定檔 → account', netwatch.login_mode() == ('account', '', 'acct_a'))

# log 不含帳號名
leak = [x for x in LOGS if 'acct_a' in x or 'acct_b' in x or 'acct_x' in x]
check('所有 log / errlog / halt 檔 / stdout 都不含帳號名', not leak, leak[:3])

# ================================================================ 3) relogin.py：有設定檔時多視窗不再 109
import relogin  # noqa: E402
import uikit  # noqa: E402
rg = []
_pf, _gui, _scr, _fail = uikit.preflight, uikit.gui, uikit.screen, uikit.fail
uikit.preflight = lambda src, fast=True: 0
uikit.gui = lambda *a, **k: rg.append(a)
uikit.screen = lambda *a, **k: {'state': 'idle'}
uikit.fail = lambda src, rc, msg: rc
os.environ['PSA_TEST_PROCS'] = 'PrimalSA,PrimalSA2'
check('relogin.py --dry-run：多視窗 + 設定檔 → 0（不擋）', relogin.run(dry_run=True) == 0 and not rg)
os.environ['PSA_CLIENT'] = 'PrimalSA2'
check('relogin.py --dry-run：PrimalSA2 + 設定檔 → 0', relogin.run(dry_run=True) == 0 and not rg)
os.environ.pop('PSA_CLIENT')
no_cfg()
check('relogin.py --dry-run：多視窗沒設定檔 → 109（舊行為）', relogin.run(dry_run=True) == 109 and not rg)
os.environ['PSA_TEST_PROCS'] = 'PrimalSA'
check('relogin.py --dry-run：單一視窗沒設定檔 → 0（舊行為）', relogin.run(dry_run=True) == 0)
uikit.preflight, uikit.gui, uikit.screen, uikit.fail = _pf, _gui, _scr, _fail

# ================================================================ 4) 靜態：typeq 內容不進 log、只送本視窗
import winenv  # noqa: E402
check('winenv.redact 遮掉 typeq 內容', winenv.redact(['typeq', 'acct_a']) == 'typeq ***' and 'acct_a' not in winenv.redact(['seq', 'click 1 2; typeq acct_a']))
check('winenv.redact 其他指令照舊（前 40 字）', winenv.redact(['click', '1', '2']) == 'click 1 2')
check('typeq 是輸入類指令（逾時不重送）', 'typeq' in winenv.INPUT_CMDS and winenv.is_input_call('gui.ps1', ['typeq', 'x']))
GUI = Path(netwatch.__file__).parent
ps1 = (GUI / 'gui.ps1').read_text(encoding='utf-8-sig')
blk = ps1[ps1.index("  'typeq' {"):ps1.index("  'end' {")]
check('gui.ps1 typeq：ActLog 只記字數、不含 $A1 內容', 'ActLog "typeq（$($A1.Length) 字' in blk and 'ActLog "typeq $A1' not in blk and '$A1"' not in blk.split('ActLog', 1)[1].split('\n', 1)[0])
check('gui.ps1 typeq：只用 BgChar（PostMessage 到 $h），不用 SendKeys', 'BgChar' in blk and '[System.Windows.Forms.SendKeys]' not in blk)
check('gui.ps1 typeq 受驗證停手旗標擋', "-or $Cmd -eq 'typeq') -and ($vhp = Get-PsaVerifyHalt $Client)" in ps1)
check('gui.ps1 維持 BOM', (GUI / 'gui.ps1').read_bytes()[:3] == b'\xef\xbb\xbf')
src = (GUI / 'netwatch.py').read_text(encoding='utf-8')
check('netwatch 登入輸入鎖是全視窗共用路徑（SHARED_CACHE，不是每視窗 CACHE）', "LOGIN_INPUT_LOCK = clients.SHARED_CACHE / 'login-input.lock'" in src)
check('.gitignore 排除 *.local.json', any(l.strip() == 'tools/gui/*.local.json' for l in (GUI.parents[1] / '.gitignore').read_text(encoding='utf-8').splitlines()))

# ================================================================ 5) 選配：真 OCR 讀登入畫面 fixture（本機有設定檔 + 截圖才跑）
real = Path(os.environ.get('PSA_FIXTURE_ACCOUNTS') or accounts.DEFAULT_PATH)     # worktree 裡可用環境變數指到主工作樹的檔
shot = Path(os.environ.get('PSA_FIXTURE_SHOT') or clients.SHARED_CACHE / 'net5.png')
if real.exists() and shot.exists() and os.environ.get('PSA_SKIP_OCR_FIXTURE') != '1':
    os.environ['PSA_ACCOUNTS_FILE'] = str(real)
    st, d = accounts.load()
    if st == 'ok' and 'primalsa' in d:
        import importlib
        nw = importlib.reload(netwatch)          # 拿回真的 _ocr_lines
        img = winenv.to_windows(str(shot))
        orig_run = winenv.run_ps
        nw.winenv.run_ps = lambda script, *a, **k: orig_run(script, *a, '-Image', img, **k)
        v_main = nw.read_account(d['primalsa'])
        others = [v for k, v in d.items() if k != 'primalsa']
        v_other = nw.read_account(others[0]) if others else 'other'
        nw.winenv.run_ps = orig_run
        # fixture 是主視窗登入畫面：主視窗帳號 = self、其他帳號 = other（判定不印帳號）
        check('fixture net5.png 真 OCR：主視窗帳號 → self', v_main == 'self', v_main)
        check('fixture net5.png 真 OCR：其他視窗帳號 → other（尾碼不混淆）', v_other == 'other', v_other)
    else:
        print('SKIP fixture OCR：設定檔沒有 PrimalSA')
else:
    print('SKIP fixture OCR：沒有本機 accounts.local.json 或 tools/.cache/net5.png')

# ================================================================ 6) 選配：真帳號名沒進 git 追蹤的檔（本機有設定檔才跑；不印帳號）
if real.exists():
    os.environ['PSA_ACCOUNTS_FILE'] = str(real)
    names = [a.lower() for a in accounts.all_accounts()]
    root = GUI.parents[1]
    import subprocess
    try:
        tracked = subprocess.run(['git', '-C', str(root), 'ls-files', '-z'], capture_output=True, timeout=30).stdout.decode('utf-8', 'replace').split('\0')
    except (OSError, subprocess.SubprocessError):
        tracked = []
    hit = 0
    for f in tracked:
        fp = root / f
        if not f or not fp.is_file() or fp.stat().st_size > 5_000_000:
            continue
        try:
            low = fp.read_bytes().decode('utf-8', 'ignore').lower()
        except OSError:
            continue
        if any(n in low for n in names):
            hit += 1
            print(f'  帳號名出現在 git 追蹤的檔：{f}')
    check(f'git 追蹤的 {len(tracked)} 個檔都不含本機設定的帳號名', bool(tracked) and names and not hit)
    no_cfg()

print('全部通過' if not fails else f'{fails} 項失敗')
sys.exit(1 if fails else 0)
