#!/usr/bin/env python3
"""離線 fixture 抽取（P0；只用標準函式庫、不碰遊戲）：用 shotcache（像素快取，底層 pngread 解碼一次）從 tools/.cache 既有 1440×830 截圖抽像素，
存成 tools/gui/fixtures/{switch,pet,depot,exp}_px.json，給 uikit / char / team / pet / grind 的離線測試用。
截圖不存在就印出「跳過」並回報（不報錯）。計畫：notes/plan-scriptify.md §1.4。
用法：uv run --no-project python tools/gui/make_fixtures.py [--only bag_slots,leader_badge,world,panel,popup,shop]
注意：來源是舊截圖（新帳號 Lv1、別的地圖），各值要在對應實機量測時重確認。"""
import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import pngread  # noqa: E402
import shotcache  # noqa: E402
import screen_sigs  # noqa: E402

CACHE = HERE.parent / '.cache'
OUT = HERE / 'fixtures'

# 切換面板：卡片列 y（DKB0/02 同列 300、03/04 385、05 470）× 狀態框邊線 x（422/446）與米色底 416；右欄 = 左欄 + 310
CARD_YS = (300, 385, 470)
CARD_XS = (416, 422, 446)
SWITCH_PTS = [(x + dx, y) for dx in (0, 310) for y in CARD_YS for x in CARD_XS] + [(x, y) for x, y, *_ in screen_sigs.SIG_PANEL]
# 寵物面板：出戰 / 騎乘 / 休息鈕、左欄頭像頂邊（頭像中心 y − 36）、右上紅 ✕
AVATAR_CY = (195, 322, 450, 580, 700)
PET_PTS = [(345, 702), (360, 685), (480, 702), (620, 702)] + [(83, cy - 36) for cy in AVATAR_CY] + [(1310, 108)]
# 倉庫：存入 / 取出鈕文字區（粗取樣）+ 倉庫格（5 欄 × 4 列）
DEPOT_PTS = [(x, y) for y in range(675, 721, 15) for x in range(440, 621, 30)] + \
            [(x, y) for y in (275, 380, 487, 593) for x in (818, 924, 1030, 1136, 1242)]
# EXP 橫幅：掃描點與紫色判定都用 grind.py 的（P-R1 實測：矩形稀疏掃），不在這裡複製
os.environ.setdefault('PSA_LAYOUT', '2880x1659')       # grind → heal → walk 載入時會問版面；離線不碰遊戲
import grind  # noqa: E402
EXP_SRC = [(f'watch-m0/p{i}.png', f'p{i}') for i in range(1, 21)] + [(f'exp-r1/r{i:02d}.png', f'r{i:02d}') for i in range(1, 41)] + [('exp-r1/now.png', 'now')]
# 人工確認有橫幅的張（舊 p14 p16 p19；P-R1 的 now 與 r07 r10 r12 r15 r18 r20 r22 r25 r27 r30 r32 r35 r37 r40）
EXP_POSITIVE = ['p14', 'p16', 'p19', 'now'] + [f'r{i:02d}' for i in (7, 10, 12, 15, 18, 20, 22, 25, 27, 30, 32, 35, 37, 40)]


def grab(path: Path, pts) -> dict:
    """取點：優先走 shotcache 像素快取（tools/gui/shotcache.py；沒有就自動補建），非 1440×830 或快取失敗才退回 pngread 解碼"""
    try:
        px = shotcache.get(path).pixels(pts)
    except (ValueError, OSError):
        w, h, bpp, rows = pngread.decode(path.read_bytes())
        px = pngread.pixels(rows, bpp, pts)
    return {f'{x},{y}': list(c) for (x, y), c in px.items()}


def write(name: str, data: dict) -> None:
    OUT.mkdir(exist_ok=True)
    (OUT / name).write_text(json.dumps(data, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    print('寫入', name)


# ---- 面板辨識樣本（watch / screen_sigs.panel_of）：人工指定檔案 → 期望面板名（None = 不是這些面板的負例）----
# 正例標籤來自獨立證據（右上 ✕ 紅圓的位置叢集 / 外掛面板的橘 ✕ + 5 個角色圓鈕），不是 PANEL_PTS 本身；挑選 = 每種面板等距取 5 張 + 今天（2026-10-11）使用者開的寵物視窗 2 張。
PANEL_POS = {
    'at_210_322.png': 'pet',
    'catch-m0/p_02.png': 'pet',
    'm1.png': 'pet',
    'pp599.png': 'pet',
    'v695.png': 'pet',
    'b1.png': 'bag',
    'd0.png': 'bag',
    'dep_195.png': 'bag',
    'k4.png': 'bag',
    'w2.png': 'bag',
    'g.png': 'quest',
    'scroll_1.png': 'quest',
    'scroll_4.png': 'quest',
    'ui/detail.png': 'quest',
    'up_3.png': 'quest',
    'catch-m0/switch0.png': 'switch',
    'm-a0.png': 'switch',
    'p3_b_pre.png': 'switch',
    't.png': 'switch',
    'ui/switch.png': 'switch',
    'm-a1.png': 'qteam',
    'm-a2.png': 'qteam',
    'm-a3.png': 'qteam',
    'm-a4.png': 'qteam',
    't1.png': 'transfer',
    'ui/i_tp.png': 'transfer',
    'ui/i_tphero.png': 'transfer',
    'ui/i_tplevel.png': 'transfer',
    'ui/transfer.png': 'transfer',
    'ui/j_chat.png': 'setting',
    'ui/j_other.png': 'setting',
    'ui/j_set.png': 'setting',
    'ui/j_sound.png': 'setting',
    'ui/setting.png': 'setting',
    'team4.png': 'team',
    'team_solo.png': 'team',
    'ui/team.png': 'team',
    'a1.png': 'ass',
    'g4.png': 'ass',
    's7.png': 'ass',
    't_pre5.png': 'ass',
    'w5.png': 'ass',
    'watch-panels/pet-0.png': 'pet',
    'watch-panels/pet-1.png': 'pet',
    'watch-panels/role-0.png': 'role',       # 人物資訊（2026-10-11 使用者開的 + 唯讀補截；role-3 原是 watch 的 unknown 警報截圖）
    'watch-panels/role-1.png': 'role',
    'watch-panels/role-2.png': 'role',
    'watch-panels/role-3.png': 'role',
}
# 負例：各種不是這些面板的畫面（主畫面 / 行走 / 對話 / 獲得物品 / 戰鬥 / 選擇對象 / 提示視窗 / 登入 / 載入 / 面板上疊彈窗…）等距各取 6 張
PANEL_NEG = [
    'a.png',
    'quest-log/094534-dialog.png',
    'quest-log/143725-dialog.png',
    'quest-log/171153-dialog.png',
    'quest-log/221622-dialog.png',
    'quest-log/221920-dialog.png',
    'al_620_385.png',
    'exp-r1/r03.png',
    'exp-r1/r35.png',
    'quest-log/151602-disbanded.png',
    'ui/e_mail_esc.png',
    'watch-m0/p9.png',
    'b3.png',
    'd2.png',
    'i1.png',
    'ui-log/025725-pet-store-nochange.png',
    'ui/e_mail.png',
    'w3.png',
    'b_a1.png',
    'battle-samples/seq_4.png',
    'battle-samples/vs_13.png',
    'battle-samples/vs_9.png',
    'watch-m0/p10.png',
    'watch-m0/s1.png',
    'battle-samples/neg_reward.png',
    'battle-samples/neg_reward_b2_3.png',
    'battle-samples/neg_reward_b2_6.png',
    'quest-log/143259-reward.png',
    'quest-log/171854-reward.png',
    'quest-log/184457-reward.png',
    'kr322.png',
    'kr450.png',
    'kr580.png',
    'kr700.png',
    'net1.png',
    'm.png',
    'o.png',
    'ui/sponsor.png',
    'net5.png',
    'net6.png',
    'p3_a_1.png',
    'quest-log/172356-no-npc.png',
]


def make_panel_fixture() -> list:
    """panel_px.json：points = screen_sigs.points() + annot_points()（watch 實際讀的點）；每張樣本存各點 hex 與當時 classify / annotate 的凍結結果。回缺的檔案"""
    pts = screen_sigs.points() + screen_sigs.annot_points()
    samples, miss = [], []
    for rel, want in list(PANEL_POS.items()) + [(r, None) for r in PANEL_NEG]:
        p = CACHE / rel
        if not p.exists():
            miss.append(rel)
            continue
        px = {tuple(map(int, k.split(','))): tuple(v) for k, v in grab(p, pts).items()}
        c = screen_sigs.classify(px)
        samples.append({'f': rel, 'expect_panel': want, 'state': c['state'], 'panel': c['panel'], 'annot': screen_sigs.annotate(px, c),
                        'px': ''.join('%02x%02x%02x' % px[pt] for pt in pts)})
    write('panel_px.json', {'note': 'watch 面板辨識樣本（2026-10-11）：expect_panel = 獨立證據的標籤；state / panel / annot = 當時 classify / annotate 的凍結結果（px 格式同 annot_px.json）',
                            'points': [list(p) for p in pts], 'samples': samples})
    return miss


# ---- NPC 商店（screen_sigs.SHOP_X / SHOP_PTS；2026-10-15，watch 對 p2 競技場便利店報 unknown_long 誤警報）----
# 只存 ✕ + 16 點（不把整張圖塞進 repo、也不動既有 panel_px / popup_px 的點清單）。正例 = 同一家店 2 張；負例 = tools/.cache/ui 全部全螢幕 / 面板截圖
# （含商城 ui/shop.png、交易所 bourse、LuckyCard lucky、贊助 sponsor）+ 面板 / 彈窗樣本 + 主畫面 / 洞窟地圖
SHOP_POS = ['clients/PrimalSA2/watch-alerts/unknown-1792043285.png', 'clients/PrimalSA2/watch-alerts/unknown-1792043435.png']
SHOP_NEG_EXTRA = ['clients/PrimalSA2/shot.png']


def make_shop_fixture() -> list:
    """shop_px.json：points = [SHOP_X 座標] + SHOP_PTS 座標；每張存 hex 與期望（True = 商店）。回缺的檔案"""
    pts = [screen_sigs.SHOP_X[:2]] + [(x, y) for x, y, *_ in screen_sigs.SHOP_PTS]
    negs = sorted(set(['ui/' + f.name for f in (CACHE / 'ui').glob('*.png')] + list(PANEL_POS) + PANEL_NEG + list(POPUP_SRC) + SHOP_NEG_EXTRA))
    samples, miss = [], []
    for rel, want in [(r, True) for r in SHOP_POS] + [(r, False) for r in negs]:
        p = CACHE / rel
        if not p.exists():
            miss.append(rel)
            continue
        px = {tuple(map(int, k.split(','))): tuple(v) for k, v in grab(p, pts).items()}
        samples.append({'f': rel, 'expect_shop': want, 'px': ''.join('%02x%02x%02x' % px[pt] for pt in pts)})
    write('shop_px.json', {'note': 'NPC 商店辨識樣本（2026-10-15）：points = ✕ + SHOP_PTS；expect_shop = 人工看圖的標籤（正例 = p2 競技場便利店 2 張，其餘是各種不是商店的畫面）',
                           'points': [list(p) for p in pts], 'samples': samples})
    return miss


# ---- 面板上疊已知彈窗（screen_sigs.popup_over_panel；watch 誤報 #243 #244 #254 #261 #264，2026-10-12）----
# 檔名 → 期望 (面板, 彈窗種類) 或 None（負例：壓暗的面板上疊「不認得」的彈窗 / 其他 unknown 畫面，必須仍是 unknown）；人工看圖確認
POPUP_SRC = {
    'watch-alerts/unknown-1791750847.png': ('bag', 'keypad'), 'watch-alerts/unknown-1791750914.png': ('bag', 'keypad'), 'f3.png': ('bag', 'keypad'),
    'watch-alerts/unknown-1791756186.png': ('bag', 'qty'), 'watch-alerts/unknown-1791756276.png': ('bag', 'qty'), 'f4.png': ('bag', 'qty'),
    'h5.png': ('bag', 'qty'), 'i1.png': ('bag', 'qty'), 'catch-m0/split.png': ('bag', 'qty'), 'ui-log/060258-rebirth-split-dialog.png': ('bag', 'qty'),
    'watch-alerts/unknown-1791754960.png': ('pet', 'confirm'), 'c470.png': ('pet', 'confirm'), 'c599.png': ('pet', 'confirm'), 'c695.png': ('pet', 'confirm'),
    'now.png': ('pet', 'confirm'), 'p1.png': ('pet', 'confirm'), 'p210.png': ('pet', 'confirm'), 'p340.png': ('pet', 'confirm'), 'p5.png': ('pet', 'confirm'),
    'ui-log/025725-pet-store-nochange.png': ('pet', 'confirm'),
    # 負例：背包道具詳情彈窗（穿戴 / 丟棄）、背包其他彈窗、任務詳情上的彈窗、其他不認得畫面
    'watch-alerts/unknown-1791708455.png': None, 'watch-alerts/unknown-1791709188.png': None, 'e3.png': None, 'eq1.png': None,
    'ui-log/164242-bag-noitem.png': None, 'ui-log/165858-bag-depot-verify.png': None, 'qd-after.png': None,
    'watch-alerts/unknown-1791706006.png': None, 'watch-alerts/unknown-1791709473.png': None,
}


def make_popup_fixture() -> list:
    """popup_px.json：points = points() + annot_points()；每張存 hex 與期望 / 凍結的 annotate 結果。回缺的檔案"""
    pts = screen_sigs.points() + screen_sigs.annot_points()
    samples, miss = [], []
    for rel, want in POPUP_SRC.items():
        p = CACHE / rel
        if not p.exists():
            miss.append(rel)
            continue
        px = {tuple(map(int, k.split(','))): tuple(v) for k, v in grab(p, pts).items()}
        c = screen_sigs.classify(px)
        samples.append({'f': rel, 'expect': list(want) if want else None, 'state': c['state'], 'annot': screen_sigs.annotate(px, c),
                        'px': ''.join('%02x%02x%02x' % px[pt] for pt in pts)})
    write('popup_px.json', {'note': '面板上疊已知彈窗樣本（2026-10-12）：expect = 人工看圖的 [面板, 彈窗] 或 null（負例須仍 unknown）；annot = 當時凍結結果',
                            'points': [list(p) for p in pts], 'samples': samples})
    return miss


# ---- 追蹤列表 ▲ / ▼ 捲動箭頭（quest.classify_arrows；2026-10-12 解救老爺爺冗餘捲動修正）----
# 檔名 → 期望 {'up','down'}（None = 遮罩 / 不可信）；人工看圖確認
QUESTLIST_SRC = {
    'ui-log/003824-team-panel-open-fail.png': {'up': False, 'down': True},    # 列表在頂：漆黑洞窟(二轉) + 解救老爺爺（y=425 被裁）+ ▼
    'quest-log/004047-task-done.png': {'up': True, 'down': False},            # 只剩 1 張卡，▲ 殘留（不能當「可以往上捲」的證據）
    'watch-m0/p1.png': {'up': False, 'down': False},                          # 只有 1 張卡，沒有箭頭
    'quest-log/003950-reward.png': None,                                      # 領獎視窗半透明遮罩：分頁鈕暗掉 → 不可信
}


def make_questlist_fixture() -> list:
    import quest
    pts = quest.ARROW_UP_PTS + quest.ARROW_DOWN_PTS + [quest.ARROW_SANITY]
    imgs, miss = {}, []
    for rel, want in QUESTLIST_SRC.items():
        p = CACHE / rel
        if not p.exists():
            miss.append(rel)
            continue
        imgs[rel] = {'expect': want, 'px': grab(p, pts)}
    if imgs:
        write('questlist_px.json', {'note': '任務追蹤列表 ▲ / ▼ 捲動箭頭樣本（quest.classify_arrows；2026-10-12）。expect None = 遮罩、不可信', 'points': pts, 'images': imgs})
    return miss


# ---- 背包格空 / 有道具（bag.slot_occupied；2026-10-12 S3「顯示道具名」被關、find 回全 null 修正）----
# 檔名 → 人工看圖的 15 格標記（X = 有道具、. = 空）
BAG_SLOTS_SRC = {
    'bag-names-off.png': 'XXXX...........',                      # 「顯示道具名」關：只有圖示（2026-10-12 04:07 DKBO 實機）
    'ui-log/173724-bag-noitem.png': 'XXXXXXXXX......',          # 名稱開：儀之兜…空想的衣服 9 件
    'ui-log/232817-bag-depot-btn.png': '...............',       # 倉庫頁：右半背包全空
    'itemident/bag-DKBO-noname.png': 'XXXXX.XX.......',         # 名字關：格號 6 = 風的鎖（空心細線，舊 25 點探針漏判；2026-10-14）
}
LEGACY_PROBE = [(dx, dy) for dx in (-24, -12, 0, 12, 24) for dy in (-20, -10, 0, 10, 20)]   # 2026-10-14 前的 25 點探針


def make_bag_slots_fixture() -> list:
    """每張圖存 probe（取點清單）＋像素：bag.SLOT_PROBE 改了就重抽；來源截圖已經不在的舊樣本照舊保留（沒有 probe 欄 = LEGACY_PROBE）"""
    import bag
    pts = [(x + dx, y + dy) for i in range(bag.n_slots()) for x, y in [bag.slot_xy(i)] for dx, dy in bag.SLOT_PROBE]
    try:
        old = json.loads((OUT / 'bag_slots_px.json').read_text(encoding='utf-8')).get('images', {})
    except (OSError, ValueError):
        old = {}
    imgs, miss = {}, []
    for rel, want in BAG_SLOTS_SRC.items():
        p = CACHE / rel
        if not p.exists():
            miss.append(rel)
            if rel in old:
                imgs[rel] = old[rel]
            continue
        px = grab(p, pts)
        imgs[rel] = {'expect': want, 'probe': [list(t) for t in bag.SLOT_PROBE],
                     'px': ['%02x%02x%02x' % tuple(px[f'{x},{y}']) for x, y in pts]}
    if imgs:
        write('bag_slots_px.json', {'note': '背包 15 格 × probe 像素（順序 = 格 0..14、每格 probe 順序；沒有 probe 欄 = 舊 25 點 LEGACY_PROBE）；'
                                    'expect = 人工標記 X 有道具 / . 空（2026-10-12，10-14 加名字關著的風的鎖樣本、改 169 點）', 'images': imgs})
    return miss


# ---- 左側組隊分頁隊長標（quest.has_leader_badge；2026-10-12 S3：舊紅「隊」字標換成小「L」標）----
# 檔名 → 期望（True = 隊長列有標、False = 沒隊伍 / 已解散）；人工看圖
LEADER_BADGE_SRC = {
    'quest-log/020133-disband-already-solo.png': True,      # 新版小「L」標（DKBO 隊長，4 人）
    'quest-log/031326-disband-already-solo.png': True,
    'quest-log/140029-disband-no-tab.png': True,            # 舊版紅「隊」字標（2026-10-10）
    'quest-log/013914-disbanded.png': False,
    'quest-log/142426-disbanded.png': False,
    'quest-log/151602-disbanded.png': False,
}


def make_leader_badge_fixture() -> list:
    import quest
    pts = quest.LEADER_BADGE_PTS
    imgs, miss = {}, []
    for rel, want in LEADER_BADGE_SRC.items():
        p = CACHE / rel
        if not p.exists():
            miss.append(rel)
            continue
        px = grab(p, pts)
        imgs[rel] = {'expect': want, 'px': ''.join('%02x%02x%02x' % tuple(px[f'{x},{y}']) for x, y in pts)}
    if imgs:
        write('leader_badge_px.json', {'note': '左側組隊分頁隊長列頭像左上角的隊長標（舊紅「隊」字 / 新小「L」）；px 順序 = quest.LEADER_BADGE_PTS（2026-10-12）', 'images': imgs})
    return miss


# ---- 巡路卡住的畫面備援（quest.world_same；座標讀不到時比世界畫面取樣）----
# 每張圖取 WORLD_PTS 與「鏡頭往右上捲 1 格」(+32,-23) 的同一組點：同一張 = 鏡頭沒動、位移 = 鏡頭動了
WORLD_SRC = ['quest-log/140029-disband-no-tab.png', 'quest-log/020133-disband-already-solo.png', 'shot-31706-idle.png']


def make_world_fixture() -> list:
    import quest
    imgs, miss = {}, []
    for rel in WORLD_SRC:
        p = CACHE / rel
        if not p.exists():
            miss.append(rel)
            continue
        base = grab(p, quest.WORLD_PTS)
        moved = grab(p, [(x + 32, y - 23) for x, y in quest.WORLD_PTS])
        imgs[rel] = {'base': ['%02x%02x%02x' % tuple(base[f'{x},{y}']) for x, y in quest.WORLD_PTS],
                     'moved': ['%02x%02x%02x' % tuple(moved[f'{x + 32},{y - 23}']) for x, y in quest.WORLD_PTS]}
    if imgs:
        write('world_px.json', {'note': 'quest.WORLD_PTS 取樣：base = 原位、moved = 同圖位移 (+32,-23)（模擬鏡頭捲 1 格）；2026-10-12', 'images': imgs})
    return miss


def main() -> int:
    if '--only' in sys.argv:                      # 只產指定的 fixture（不重產其他檔）：--only bag_slots,leader_badge
        names = sys.argv[sys.argv.index('--only') + 1].split(',')
        for n in names:
            miss = {'bag_slots': make_bag_slots_fixture, 'leader_badge': make_leader_badge_fixture, 'world': make_world_fixture,
                    'panel': make_panel_fixture, 'popup': make_popup_fixture, 'shop': make_shop_fixture}[n]()
            print(n, '缺', miss) if miss else None
        return 0
    done, skipped = [], []

    def need(*rel):
        ps = [CACHE / r for r in rel]
        miss = [str(p.relative_to(CACHE)) for p in ps if not p.exists()]
        return ps, miss

    ps, miss = need('ui/switch.png')
    if miss:
        skipped.append(('switch_px.json', miss))
    else:
        write('switch_px.json', {'note': '切換面板（DKB05 當前、其餘線上、全單人），來源 ui/switch.png；右欄 = 左欄 x+310；2026-10-10 離線抽取',
                                 'source': 'ui/switch.png', 'points': SWITCH_PTS, 'px': grab(ps[0], SWITCH_PTS)})
        done.append('switch_px.json')

    ps, miss = need('pet322.png')
    if miss:
        skipped.append(('pet_px.json', miss))
    else:
        write('pet_px.json', {'note': '寵物分頁（DKB02 選中、出戰亮），來源 pet322.png；頭像頂邊 y = 頭像中心 − 36', 'source': 'pet322.png',
                              'points': PET_PTS, 'px': grab(ps[0], PET_PTS)})
        done.append('pet_px.json')

    ps, miss = need('q567.png', 'q5.png')
    if miss:
        skipped.append(('depot_px.json', miss))
    else:
        write('depot_px.json', {'note': '寵物倉庫；q567 = 存入寵物（選中背包寵物）、q5 = 取出寵物（選中倉庫寵物）', 'points': DEPOT_PTS,
                                'q567': grab(ps[0], DEPOT_PTS), 'q5': grab(ps[1], DEPOT_PTS)})
        done.append('depot_px.json')

    imgs, miss_exp = {}, []
    for rel, tag in EXP_SRC:
        p = CACHE / rel
        if not p.exists():
            miss_exp.append(rel)
            continue
        px = grab(p, grind.EXP_PTS)
        purple = {k: v for k, v in px.items() if grind.is_exp_purple(v)}
        imgs[tag] = {'purple_n': len(purple), 'purple': purple}
    if not imgs:
        skipped.append(('exp_px.json', miss_exp))
    else:
        write('exp_px.json', {'note': 'EXP 橫幅偵測樣本（P-R1，2026-10-11）：每張只存紫點（grind.is_exp_purple）；掃描點 = grind.EXP_PTS（y 140～262 每 6、x 450～1000 每 4）；positive 為人工確認有橫幅，其餘沒有',
                              'rows': [grind.EXP_YS[0], grind.EXP_YS[-1], 6], 'xs': [grind.EXP_XS[0], grind.EXP_XS[-1], 4],
                              'positive': [t for t in EXP_POSITIVE if t in imgs], 'images': imgs})
        done.append('exp_px.json' + (f'（缺 {miss_exp}）' if miss_exp else ''))

    miss_panel = make_panel_fixture()
    done.append('panel_px.json' + (f'（缺 {miss_panel}）' if miss_panel else ''))
    miss_pp = make_popup_fixture()
    done.append('popup_px.json' + (f'（缺 {miss_pp}）' if miss_pp else ''))
    miss_shop = make_shop_fixture()
    done.append('shop_px.json' + (f'（缺 {miss_shop}）' if miss_shop else ''))
    miss_ql = make_questlist_fixture()
    done.append('questlist_px.json' + (f'（缺 {miss_ql}）' if miss_ql else ''))
    for n, fn in (('bag_slots_px.json', make_bag_slots_fixture), ('leader_badge_px.json', make_leader_badge_fixture), ('world_px.json', make_world_fixture)):
        m = fn()
        done.append(n + (f'（缺 {m}）' if m else ''))
    print('完成：', done)
    for n, m in skipped:
        print('跳過', n, '缺', m)
    return 0


if __name__ == '__main__':
    sys.exit(main())
