#!/usr/bin/env python3
"""follow.py / spots 學習門檻 離線測試：不碰遊戲（grind.run / heal / watchstate / uikit 全假）。
用法：uv run --no-project python tools/gui/test_follow.py"""
import argparse
import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault('PSA_LAYOUT', '2880x1659')
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import follow  # noqa: E402
import spots  # noqa: E402

TMP = Path(tempfile.mkdtemp())
spots.THRESH_FILE = TMP / 'thr.json'
follow.PID_FILE, follow.STOP_FILE, follow.STATE_FILE = TMP / 'f.pid', TMP / 'f.stop', TMP / 'f.json'
follow.EVENT_LOG = TMP / 'events.log'
fails = 0


def check(name, cond, extra=''):
    global fails
    print(('PASS' if cond else 'FAIL'), name, extra)
    if not cond:
        fails += 1


def args(**kw):
    d = dict(every=15, buffer=0, until_level=0, dry_run=False, no_heal=False, hp=40, mp=20, check_every=20, stall_min=45, stop=False, trans=1)
    d.update(kw)
    return argparse.Namespace(**d)


class World:
    def __init__(self, lv=(1, 7), map_=11001):
        self.lv, self.map = lv, map_
        self.runs, self.errs, self.t = [], [], 0.0
        self.start_rc = {}            # 點名 → rc
        self.block = None
        self.busy = None
        self.verify, self.screen = None, 'idle'
        self.hp = 100
        self.reads = []               # 若有，read_status 依序吐出（雜訊測試）
        self.heals = []
        self.enc_on = True
        self.ens_rc = None
        self.panel = None             # 非 None = watch 認得面板開著（state=panel）


def install(w):
    follow.clock = lambda: w.t
    follow.sleep = lambda s: setattr(w, 't', w.t + s)
    follow.guard = lambda: None
    follow.other_busy = lambda: w.busy
    follow.read_status = lambda: (w.reads.pop(0) if w.reads else (w.lv[1], w.map))
    follow.verify_screen_state = lambda: w.screen
    follow.where_by_name = lambda: getattr(w, 'byname', None)
    follow.watchstate.verify_suspect = lambda *a, **k: w.verify
    follow.read_block_msg = lambda: w.block
    follow.errlog.add = lambda msg, **k: w.errs.append(msg)
    follow.heal.read_vitals = lambda last=None, **k: ({'ok': True, 'hpPct': w.hp, 'mpPct': 100}, 1.0)
    follow.heal.heal_trip = lambda spot, no_return=False: w.heals.append(spot)
    follow.grind.take_lock = lambda: True
    def _screen(*a, **k):
        if w.enc_on == 'none':
            return None
        d = {'enc_on': w.enc_on}
        if w.panel:
            d.update(state='panel', panel=w.panel, enc_on=None)
        return d
    follow.watchstate.screen = _screen
    follow.grind.release_lock = lambda: None

    def grun(mode, spot=None, **k):
        w.runs.append((mode, spot))
        if mode == 'ensure' and getattr(w, 'ens_rc', None):
            return w.ens_rc.pop(0) if isinstance(w.ens_rc, list) else w.ens_rc
        if mode == 'start':
            rc = w.start_rc.get(spot, 0)
            if rc == 0:
                w.map = spots.SPOTS[spot][2]
            return rc
        return 0
    follow.grind.run = grun
    return w


def mk(w, **kw):
    return follow.Follow(args(**kw))


# 1) 門檻表 + buffer
check('spot_for buffer 0：9→柯奧 10→阿布 20→海主人 45→五兄弟 60 80 120', [spots.spot_for(1, n, 0) for n in (9, 10, 20, 45, 60, 80, 120)] ==
      ['柯奧龜洞', '阿布龜洞', '海主人隧道', '五兄弟洞窟', '柯奧4F龜洞', '波拉島', '地雷區'])
check('spot_for buffer 2：11 仍柯奧、12 阿布、21 阿布、22 海主人；1 級不加 buffer', [spots.spot_for(1, n, 2) for n in (1, 11, 12, 21, 22)] ==
      ['柯奧龜洞', '柯奧龜洞', '阿布龜洞', '阿布龜洞', '海主人隧道'])
check('阿布龜洞在 SPOTS / HEAL_SPOTS，座標 540,326 地圖 10001', spots.SPOTS['阿布龜洞'][:3] == (540, 326, 10001) and '阿布龜洞' in spots.HEAL_SPOTS)
check('follow --buffer 預設 0、--every 預設 15', (lambda ns: ns.buffer == 0 and ns.every == 15)(
    (lambda p: (follow.add_parser(p.add_subparsers(dest='cmd')), p.parse_args(['follow']))[1])(argparse.ArgumentParser())))

# 2) auto_spot 1 轉
check('auto_spot 1 轉用表（未實測但不拒絕）', spots.auto_spot(1, 7) == '柯奧龜洞' and spots.auto_spot(1, 50) == '五兄弟洞窟' and spots.auto_spot(1, 0) is None)
check('too_low：1 轉沒學到不預判', not spots.too_low('地雷區', 1, 1))

# 3) 等級雜訊：連續 2 次才採用
w = install(World(lv=(1, 12), map_=11001))
f = mk(w)
w.reads = [(12, 11001), (2, 11001), (12, 11001)]
f.feed((1, 7))
f.feed((1, 7))
check('先確認 1轉7級', f.good == (1, 7))
check('單次跳到 12 不採用', not f.feed((1, 12)) and f.good == (1, 7))
check('雜訊 2（漏位數）被擋', not f.feed((1, 2)) and f.good == (1, 7) and f.pending is None)
f.feed((1, 12))
check('連續 2 次 12 才採用', f.feed((1, 12)) and f.good == (1, 12))
check('轉生後 (2,1) 連 2 次可採用', not f.feed((2, 1)) and f.feed((2, 1)) and f.good == (2, 1))

check('level_of 只取等級、無視轉數', follow.level_of('0轉12級') == 12 and follow.level_of('1轉7級') == 7 and follow.level_of('abc') is None)
check('level_of 實際 HUD 格式：0轉26級 / 1轉26級 / 轉24, / 24, / 1轉24,', [follow.level_of(x) for x in ('0轉26級', '1轉26級', '轉24,', '24,', '1轉24,', ' 24 ，')] == [26, 26, 24, 24, 24, 24])
check('level_of 垃圾 → None', all(follow.level_of(x) is None for x in (None, '', '??', '0轉級', '999', '1轉0級')))
w = install(World(lv=(0, 12), map_=11001))      # HUD 轉數誤讀成 0，仍照 --trans 1
f = mk(w)
f.step()
check('HUD 轉數讀成 0 不改用 0 轉判斷（trans 固定 1）', f.good == (1, 12) and spots.stage_min('阿布龜洞', f.good[0]) == 10)

# 4) 換點呼叫 start
w = install(World(lv=(1, 10), map_=11001))
f = mk(w)
rc = f.step()
check('10 級在柯奧龜洞 → start 阿布龜洞', rc is None and ('start', '阿布龜洞') in w.runs and f.cur == '阿布龜洞', str(w.runs))
w.runs.clear()
f.step()
check('已在阿布龜洞 → 不再 start', not any(m == 'start' for m, _ in w.runs))
w.lv = (1, 20)
f.step()
check('20 級 → 海主人隧道', ('start', '海主人隧道') in w.runs)
check('寫了事件 log 與 follow.json', 'follow：' in follow.EVENT_LOG.read_text(encoding='utf-8') and follow.STATE_FILE.exists())

# 5) 被擋：學習修正、ensure、冷卻
w = install(World(lv=(1, 20), map_=10001))
w.start_rc['海主人隧道'] = 51
w.block = (1, 25)
f = mk(w)
rc = f.step()
check('被擋 → 學到 1 轉海主人隧道 25 級', spots.learned('海主人隧道', 1) == 25, str(spots.load_learned()))
check('被擋 → errlog + ensure 留原點', any('被擋' in e for e in w.errs) and ('ensure', None) in w.runs and rc is None)
w.runs.clear()
f.step()
check('冷卻中不重試 start', not any(m == 'start' for m, _ in w.runs))
check('學到的門檻影響選點：24 級仍阿布、25 級海主人', spots.spot_for(1, 24, 0) == '阿布龜洞' and spots.spot_for(1, 25, 0) == '海主人隧道')
check('too_low 用學到的', spots.too_low('海主人隧道', 1, 24))
spots.THRESH_FILE = TMP / 'thr2.json'
w2 = install(World(lv=(1, 20), map_=10001))
w2.start_rc['海主人隧道'] = 51
w2.block = (None, None)
f2 = mk(w2)
f2.step()
check('讀不到數字 → 不修正門檻、有 errlog、10 分鐘冷卻', spots.learned('海主人隧道', 1) == 0 and w2.errs and f2.block_until)

# 6) 暫停
w = install(World(lv=(1, 10), map_=11001))
w.busy = 'battle.lock（quest）'
f = mk(w)
f.step()
check('battle.lock 時不動作', w.runs == [])
w.busy = None
f.step()
check('解除後恢復', ('start', '阿布龜洞') in w.runs)

# 7) verify_suspect
w = install(World(lv=(1, 10), map_=11001))
w.verify, w.screen = True, 'idle'
f = mk(w)
rc = f.step()
check('誤報（主畫面 idle）不停、照常換點', rc is None and ('start', '阿布龜洞') in w.runs)
# 7a) 不認得的畫面：暫停（不退出 9），超過 UNKNOWN_STOP_MIN 分鐘才退出
w = install(World(lv=(1, 10), map_=11001))
w.verify, w.screen = True, 'unknown'
f = mk(w)
rc = f.step()
check('不認得畫面 → 暫停這輪（不退出、不動作、不點擊）+ errlog 一次', rc is None and w.runs == [] and w.heals == [] and len(w.errs) == 1 and '暫停' in w.errs[0], str(w.errs))
for _ in range(5):
    w.t += 15
    f.step()
check('持續 unknown：errlog 只寫一次、仍不動作、不算 BAD_MAX', len(w.errs) == 1 and w.runs == [] and f.bad == 0)
w.verify = False                                       # watch 旗標清掉也要現場讀畫面（暫停中不信旗標）
w.screen = 'unknown'
check('暫停中旗標消失但畫面仍 unknown → 繼續暫停', f.step() is None and w.runs == [] and f.unk_since is not None)
w.screen = 'idle'
rc = f.step()
check('畫面恢復主畫面 → 自動恢復（清暫停、照常換點）', rc is None and f.unk_since is None and ('start', '阿布龜洞') in w.runs)
w.screen, w.verify = 'unknown', True
f.step()
check('恢復後再 unknown → 重新計時並再寫一次 errlog', len(w.errs) == 2)
w.screen = 'panel'
check('unknown 後變已知面板 → 仍暫停但解除 unknown 計時', f.step() is None and f.unk_since is None)
w = install(World(lv=(1, 10), map_=11001))
w.verify, w.screen = True, 'unknown'
f = mk(w)
f.step()
w.t += follow.UNKNOWN_STOP_MIN * 60 - 1
check('未滿 UNKNOWN_STOP_MIN 仍暫停', f.step() is None and w.runs == [])
w.t += 2
rc = f.step()
check('超過 UNKNOWN_STOP_MIN 分鐘 → 退出 9 + errlog、不動作', rc == 9 and len(w.errs) == 2 and '超過' in w.errs[-1] and w.runs == [], str(w.errs))
w = install(World(lv=(1, 10), map_=11001))
w.verify, w.screen = True, 'unknown'
w.reads = [(None, 11001)] * 200
f = mk(w)
for _ in range(follow.BAD_MAX + 10):
    w.t += 5                                           # 總共 < UNKNOWN_STOP_MIN，只測 BAD_MAX
    rc = f.step()
check('unknown 暫停期間不累計 BAD_MAX（即使 HUD 讀不到）、不退出 59', rc is None and f.bad == 0 and len(w.reads) == 200)
w = install(World(lv=(1, 10), map_=11001))
w.verify, w.screen = True, 'battle'
check('戰鬥中旗標也視為主畫面', mk(w).step() is None)

# 7b) 使用者開面板（watch 認得 panel）：暫停這一輪，不是退出 9
w = install(World(lv=(1, 10), map_=11001))
w.panel = 'pet'
f = mk(w)
rc = f.step()
check('面板開著（寵物）→ 暫停這輪：不退出、不動作、不算讀不到等級', rc is None and w.runs == [] and not w.errs and f.bad == 0)
w.t += 600
check('面板開著 10 分鐘仍暫停（不累積 BAD_MAX 停手）', f.step() is None and w.runs == [] and f.bad == 0)
w.panel = None
rc = f.step()
check('面板關了 → 恢復照常（換點 / 檢查）', rc is None and ('start', '阿布龜洞') in w.runs)
w = install(World(lv=(1, 10), map_=11001))
w.panel = 'bag'
f = mk(w)
f.step()
w.t += follow.PANEL_PAUSE_MAX + 5
f.step()
check('面板開超過 PANEL_PAUSE_MAX → 不再暫停（照常跑）', ('start', '阿布龜洞') in w.runs)
w = install(World(lv=(1, 10), map_=11001))
w.verify, w.screen = True, 'panel'
rc = mk(w).step()
check('verify_suspect 但現場畫面是面板 → 暫停這輪（不退出 9、不 errlog）', rc is None and not w.errs and w.runs == [])

# 8) until-level
w = install(World(lv=(1, 30), map_=11001))
f = mk(w, until_level=30)
check('到 --until-level 回 0 且不換點', f.step() == 0 and w.runs == [])
w = install(World(lv=(1, 29), map_=11001))
check('未到則繼續', mk(w, until_level=30).step() is None)

# 9) dry-run / 補血 / 讀不到 / 失敗上限
w = install(World(lv=(1, 45), map_=11001))
f = mk(w, dry_run=True)
f.step()
check('dry-run 不呼叫 grind', w.runs == [] and f.cur == '五兄弟洞窟')
w = install(World(lv=(1, 5), map_=11001))
w.hp = 20
f = mk(w)
f.step()
check('血低（連 2 次）→ heal_trip 目前點 + ensure', w.heals == ['柯奧龜洞'] and ('ensure', None) in w.runs)
w = install(World(lv=(1, 5), map_=11001))
w.reads = [(None, None)] * (follow.BAD_MAX + 5)
f = mk(w)
r = None
for _ in range(follow.BAD_MAX + 2):
    r = f.step()
    if r is not None:
        break
check('連續讀不到等級 → 59', r == 59)
w = install(World(lv=(1, 10), map_=11001))
w.start_rc['阿布龜洞'] = 52
f = mk(w)
r = [f.step() for _ in range(3)]
check('start 連 3 次失敗 → 回該退出碼 52', r == [None, None, 52], str(r))

# 10) --stop / 單一實例
follow.PID_FILE.write_text(str(os.getpid() + 1))
follow.alive_other.__globals__['alive_other']
import battleguard  # noqa: E402
orig = battleguard.pid_alive
battleguard.pid_alive = lambda p: True
check('另一個 follow 在跑 → run 回 8', follow.run(args()) == 8)
battleguard.pid_alive = orig
follow.PID_FILE.unlink()


# 地圖名兩行 → HUD 座標 / 地圖 ID 讀不到：用地圖名 OCR 判斷人在哪
check('spot_by_name 五兄弟（含雜字）', follow.spot_by_name('五兄弟•的山寨地下-6、') == '五兄弟洞窟')
check('spot_by_name 柯奧龜洞 1 / 4 樓同前綴 → 不確定 None', follow.spot_by_name('柯奧山的小洞窟') is None)
check('spot_by_name 垃圾 / 空 → None', follow.spot_by_name('') is None and follow.spot_by_name('3170·5,20') is None)
w = install(World(lv=(1, 45), map_=31401))
w.byname = '五兄弟洞窟'
w.start_rc['五兄弟洞窟'] = follow.grind.EXIT_TELEPORT
f = mk(w)
f.good = (1, 45)
f.cur = '海主人隧道'
rc = f.switch('五兄弟洞窟')
check('傳送驗證失敗但地圖名已是目標 → 視為抵達、補 ensure、不修正門檻', rc is None and f.cur == '五兄弟洞窟' and ('ensure', None) in w.runs and not w.errs)

# 11) 掛機未恢復：補血後 ensure 失敗 → 之後重試；連 3 次失敗停
w = install(World(lv=(1, 5), map_=11001))
w.hp = 20
w.ens_rc = [52, 52, 0]
f = mk(w)
f.step()
check('補血後 ensure 失敗 → 記住未恢復', f.unrecovered and f.fails == 1 and w.runs.count(('ensure', None)) == 1)
w.hp = 100
f.step()
check('30 秒內不重試', w.runs.count(('ensure', None)) == 1)
w.t += follow.RETRY_GAP + 1
f.step()
check('過 30 秒重試 ensure（再失敗 2/3）', w.runs.count(('ensure', None)) == 2 and f.fails == 2 and f.unrecovered)
w.t += follow.RETRY_GAP + 1
f.step()
check('再重試成功 → 恢復、失敗計數歸零', w.runs.count(('ensure', None)) == 3 and not f.unrecovered and f.fails == 0)
w.t += follow.RETRY_GAP + 1
f.step()
check('恢復後不再多跑 ensure', w.runs.count(('ensure', None)) == 3)

w = install(World(lv=(1, 5), map_=11001))
w.hp = 20
w.ens_rc = 52
f = mk(w)
r = [f.step()]
w.hp = 100
for _ in range(2):
    w.t += follow.RETRY_GAP + 1
    r.append(f.step())
check('ensure 連 3 次失敗 → 回 52 + errlog', r == [None, None, 52] and any('連續' in e for e in w.errs) and w.runs.count(('ensure', None)) == 3, str(r))

# 12) 遇敵鈕關超過 60 秒 → ensure
w = install(World(lv=(1, 5), map_=11001))
w.enc_on = False
f = mk(w)
f.step()
check('剛看到遇敵關：不立刻 ensure', ('ensure', None) not in w.runs)
w.t += 30
f.step()
check('30 秒仍不動作', ('ensure', None) not in w.runs)
w.t += 31
f.step()
check('超過 60 秒 → ensure', w.runs.count(('ensure', None)) == 1 and f.enc_off_since is None)
w.t += 10
f.step()
check('ensure 後重新計時，不連發', w.runs.count(('ensure', None)) == 1)

w = install(World(lv=(1, 5), map_=11001))
w.enc_on = False
f = mk(w)
f.step()
w.t += 100
w.busy = 'battle.lock（quest）'
f.step()
w.busy = None
check('有暫停條件（battle.lock）時不觸發', ('ensure', None) not in w.runs)
w = install(World(lv=(1, 5), map_=11001))
w.enc_on = 'none'
f = mk(w)
for _ in range(5):
    f.step()
    w.t += 30
check('讀不到 enc_on → 略過', ('ensure', None) not in w.runs)
w = install(World(lv=(1, 5), map_=11001))
w.enc_on = False
f = mk(w)
f.step()
w.t += 40
w.enc_on = True
f.step()
w.t += 40
w.enc_on = False
f.step()
w.t += 40
f.step()
check('遇敵中途打開會重新計時', ('ensure', None) not in w.runs)
print(f'\n失敗 {fails} 項' if fails else '\n全部通過')
sys.exit(1 if fails else 0)
