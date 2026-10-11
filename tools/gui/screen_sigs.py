#!/usr/bin/env python3
"""畫面像素特徵與分類（純函式、純標準函式庫，不 import winenv，不碰遊戲）。

從 quest.py / netwatch.py / heal.py 搬出的共用特徵；quest.read_screen、netwatch、（之後的）watch 都用同一份。
特徵 = 清單，每點 tuple (x, y, r, g, b, tol)：座標是 2880×1659 版面的截圖座標（1440×830 縮圖座標），
tol 是該特徵原本使用的容差（搬移時逐一保留，不要統一）。
classify(px) 與搬出前的 quest.read_screen 判定逐點相同（fixtures/screen_px.json 驗證）。
"""
import battleguard

# ---- 容差原值 ----
TOL = 40                             # quest 預設：對話框 / 獲得物品 / 切換面板 / 選擇對象 / HUD / VS 牌
TOL_BATTLE = 25
TOL_CMD = 25
TOL_AUTO_OFF = 20
TOL_CLOSE_ROW = 22
NET_TOL = 25                         # netwatch waitpix
ENC_TOL = 50                         # heal 遇敵鈕（紅龍頭）


def close(c, ref, tol=TOL):
    return all(abs(a - b) <= tol for a, b in zip(c, ref))


def _t(points, tol):
    """5 元素 (x,y,r,g,b) 清單 → 6 元素 (x,y,r,g,b,tol)"""
    return [(x, y, r, g, b, tol) for x, y, r, g, b in points]


# ---- quest 特徵（說明與實測紀錄見 quest.py 原註解 / ui/*.md）----
# 對話框：棕底 2 點 + 兩顆米色鈕（主畫面沙地很像米色，所以一定要配棕底）
SIG_DIALOG = _t([(1360, 300, 107, 70, 44), (1100, 350, 107, 70, 44), (948, 445, 229, 197, 155), (1220, 445, 229, 197, 155)], TOL)
SIG_REWARD = _t([(720, 572, 62, 106, 158), (680, 560, 82, 125, 178), (560, 620, 233, 203, 161), (720, 640, 104, 72, 46)], TOL)
SIG_PANEL = _t([(1064, 208, 197, 69, 41), (880, 590, 55, 67, 13)], TOL)    # 切換角色面板：右上紅 ✕ + 刷新鈕深綠
SIG_HUD = _t([(1300, 745, 254, 0, 0)], TOL)                                  # 外掛鈕 ASS 紅字（對話框開著時整個 UI 隱藏）
# 已量好的面板右上 ✕ 紅圓（uikit.PET / TEAMPANEL / QTEAM 沿用這幾個，不重量）
X_PET = (1310, 108, 197, 71, 49, TOL)
X_TEAM = (1250, 77, 197, 72, 48, TOL)
X_QTEAM = (1052, 167, 195, 73, 49, TOL)

# ---- 常見面板（2026-10-11 以 tools/.cache 767 張 1440×830 樣本學出；watch 用，classify 認得就回 state=panel + panel 名）----
# 判定 = ✕ 必須命中（PANEL_X，tol 40）+ 該面板的 8 個「框 / 標題板 / 邊緣」點至少 PANEL_NEED 個在 PANEL_TOL 內（容許個別點被遊戲內容 / 特效蓋住）。
# 8 點是用該面板全部正例（pet 219 / bag 78 / ass 64 / quest 13 / switch 9 / transfer 6 / setting 5 / team 3 / qteam 4 / role 4）挑「各正例都穩定、其餘 700 多張都不符」的點；
# 離線驗證：全部樣本 0 誤判（見 test_screen_sigs.py）。切換角色面板仍用既有 SIG_PANEL（2 點）優先判，這裡的 switch 只是補它被蓋 / 暗化時。
# 沒有可靠樣本所以**不上線**：圖鑑、商城、家族、排行榜、信箱等（見 ui/README.md「watch 認得的畫面」）。
PANEL_TOL = 16
PANEL_NEED = 6
PANEL_X = {
    'pet': X_PET,
    'bag': (1280, 113, 197, 70, 43, TOL),
    'quest': (1360, 80, 197, 72, 48, TOL),
    'transfer': (1288, 96, 197, 73, 50, TOL),
    'setting': (1340, 85, 197, 73, 49, TOL),
    'team': X_TEAM,
    'qteam': X_QTEAM,
    'switch': SIG_PANEL[0],
    'ass': (1318, 90, 195, 127, 8, TOL),
    'role': (1335, 112, 197, 73, 49, TOL),
}
PANEL_PTS = {
    'pet': [(536, 70, 194, 155, 112), (1322, 778, 62, 38, 25), (182, 772, 129, 91, 55), (1298, 82, 144, 99, 63), (752, 778, 143, 100, 67), (170, 322, 148, 99, 58), (920, 106, 90, 55, 23), (1310, 430, 107, 68, 41)],
    'bag': [(540, 76, 195, 140, 95), (1296, 760, 59, 33, 17), (150, 784, 104, 67, 45), (1272, 82, 56, 36, 22), (678, 772, 188, 154, 117), (156, 268, 219, 179, 135), (894, 106, 83, 43, 26), (1290, 424, 46, 24, 10)],
    'quest': [(502, 60, 186, 127, 87), (1372, 768, 49, 22, 12), (106, 768, 105, 70, 47), (1216, 72, 60, 29, 18), (736, 732, 184, 153, 122), (100, 288, 89, 55, 36), (1366, 402, 121, 80, 55), (1054, 738, 177, 142, 103)],
    'transfer': [(158, 66, 85, 49, 25), (1310, 714, 116, 107, 44), (530, 756, 116, 77, 48), (920, 66, 178, 112, 73), (128, 528, 85, 51, 24), (1310, 276, 82, 45, 24), (920, 756, 114, 76, 48), (536, 102, 139, 86, 54)],
    'setting': [(172, 60, 123, 93, 25), (1354, 738, 126, 90, 63), (556, 756, 171, 64, 33), (952, 66, 198, 142, 108), (88, 564, 78, 39, 19), (1348, 288, 135, 84, 48), (952, 714, 205, 147, 79), (550, 102, 154, 90, 60)],
    'team': [(488, 50, 175, 117, 77), (1256, 746, 112, 76, 52), (188, 758, 70, 43, 35), (1238, 50, 141, 96, 61), (722, 734, 231, 203, 163), (200, 344, 237, 205, 162), (884, 92, 159, 96, 59), (1226, 398, 245, 229, 204)],
    'qteam': [(438, 140, 67, 56, 41), (1062, 716, 86, 53, 33), (378, 716, 85, 57, 33), (1032, 140, 17, 12, 5), (720, 674, 24, 47, 76), (732, 164, 181, 153, 114), (1068, 410, 42, 28, 17), (300, 368, 20, 15, 8)],
    'switch': [(426, 160, 136, 106, 73), (1062, 664, 66, 38, 20), (1002, 160, 201, 163, 119), (1068, 406, 138, 92, 56), (1050, 532, 146, 115, 82), (1068, 280, 123, 84, 53), (300, 328, 122, 110, 90), (738, 730, 118, 114, 98)],
    'ass': [(334, 60, 168, 144, 99), (1354, 774, 225, 210, 177), (1096, 60, 229, 210, 163), (592, 774, 221, 221, 219), (100, 558, 223, 204, 164), (1354, 372, 232, 218, 188), (718, 102, 115, 100, 74), (970, 738, 255, 255, 255)],
    'role': [(1116, 274, 158, 124, 89), (996, 546, 76, 77, 32), (1148, 714, 179, 71, 42), (300, 610, 197, 142, 75), (1380, 698, 83, 46, 31), (596, 98, 228, 188, 140), (676, 578, 155, 121, 82), (996, 330, 201, 162, 113)],
}
PANEL_NAMES = {'pet': '寵物', 'bag': '背包', 'quest': '任務', 'transfer': '傳送', 'setting': '設置', 'team': '組隊', 'qteam': '快速組隊',
               'switch': '切換角色', 'ass': '外掛', 'role': '人物資訊'}

# ---- 主畫面多組特徵（任一組命中 = 主畫面 idle）----
# G1 = 外掛鈕紅字（舊 SIG_HUD，單點、暗地圖 / 特效時會失敗）；G2 = 底部圖示列（切換～外掛 7 顆石頭圓鈕的框）；G3 = 右下（遇敵鈕 / 收合箭頭周圍）。
# G2 / G3 都是不透明的 UI 圖示，不受地圖顏色影響；每組 6 點允許 1 點不符（HUD_TOL 16）。
# 刻意不放「左上血條框 / 右上地圖名框」當單獨判據：寵物、背包等大面板開著時它們仍然露在外面，會把沒認得的面板（含驗證視窗）誤當主畫面。
# 底部圖示列與右下按鈕會被所有大面板蓋住，所以兩組都不成立 → 還是 unknown。
HUD_TOL = 16
HUD_MISS = 1
HUD_GROUPS = {
    'bottom': [(760, 720, 81, 78, 73), (1068, 756, 187, 171, 140), (908, 784, 190, 169, 97), (852, 720, 95, 86, 74), (992, 784, 74, 93, 49), (732, 796, 126, 97, 65)],
    'right': [(1336, 648, 170, 154, 119), (1300, 796, 171, 153, 126), (1372, 700, 28, 28, 28), (1304, 724, 155, 138, 111), (1336, 764, 176, 160, 122), (1300, 760, 147, 147, 146)],
}
# 全黑轉場：HUD 各處 + 畫面中央共 10 點全暗（max < BLACK_MAX）。洞窟地圖大片黑但 HUD 圖示不黑，所以不會誤判（沒有實測樣本，只有合成測試）
BLACK_PTS = [(216, 58), (1200, 70), (1130, 765), (1300, 745), (1380, 660), (90, 70), (100, 790), (720, 400), (1250, 450), (300, 300)]
BLACK_MAX = 24

# 切換角色後的全螢幕「加載中」畫面（P-I3 實測，約 0.25～0.5 s；此時 SIG_HUD 不成立、classify = unknown；只給 char.py 等切換用，不進 classify）
SIG_LOADING = _t([(1000, 40, 96, 183, 243), (30, 780, 231, 189, 76), (668, 727, 255, 255, 255)], TOL)
# 「選擇對象」面板（點 NPC 後右側跳出的米色面板）
SIG_SELECT = _t([(1112, 300, 104, 79, 48), (1112, 400, 104, 79, 48), (1112, 470, 104, 79, 48), (1416, 300, 93, 68, 36), (1416, 470, 93, 68, 36),
                 (1120, 470, 247, 216, 177), (1250, 490, 245, 229, 191), (1410, 470, 246, 219, 182)], TOL)
# 完整戰鬥畫面上方中央棕框外框 9 點（定義在 battleguard.py，ass.py 共用，這裡再匯出並加上容差）；VS 牌 = 快速戰鬥
SIG_BATTLE = _t(battleguard.SIG_BATTLE, TOL_BATTLE)
VS_PROBE = battleguard.VS_PROBE
VS_COLOR = battleguard.VS_COLOR
VS_TOL = TOL
# 下指令階段（右上指令框 + 上方「N回合 / 剩餘時間」）
SIG_CMD = _t([(1283, 168, 143, 119, 102), (1100, 170, 139, 117, 98), (1100, 60, 187, 161, 131), (1250, 60, 187, 161, 131), (1060, 200, 133, 100, 72)], TOL_CMD)
# 自動戰鬥鈕「關」= 靜止紅色圖示（「開」是擺動的刀劍動畫，顏色不固定 → 只判斷「是不是關」）
SIG_AUTO_OFF = _t([(1380, 600, 75, 29, 16), (1375, 605, 249, 181, 100)], TOL_AUTO_OFF)
# 戰鬥中底部「關閉」直式鈕（左側 4 點米灰；右側頭像列 2 點很暗，另判 max < 95，不在這裡）
SIG_CLOSE_ROW = _t([(480, 745, 188, 162, 134), (500, 710, 188, 162, 134), (490, 800, 182, 158, 130), (520, 745, 188, 162, 135)], TOL_CLOSE_ROW)
# 「Auto Walking」金黃字：畫面中央 550～1000 × 500～540 取樣，金黃點（r>225, 150<g<205, b<50）≥ AW_MIN 個
AW_POINTS = [(x, y) for y in range(500, 541, 8) for x in range(552, 1000, 12)]
AW_MIN = 10

# ---- netwatch 特徵（waitpix 字串由 tuple 產生；容差 NET_TOL 由呼叫端帶）----
NET_DIALOG = _t([(520, 570, 245, 217, 179), (880, 570, 245, 217, 179), (600, 300, 243, 213, 175), (600, 557, 243, 213, 175),
                 (830, 557, 243, 213, 175), (640, 557, 61, 106, 167)], NET_TOL)      # 米色「提示」視窗：兩側米色 + 中間藍鈕
NET_LOGIN = _t([(500, 570, 179, 127, 63), (760, 565, 93, 137, 187), (440, 520, 243, 217, 179)], NET_TOL)   # 登錄鈕橘、註冊鈕藍、面板米色
NET_CHARSEL = _t([(640, 640, 197, 134, 70), (500, 250, 241, 213, 179), (1186, 190, 196, 72, 48), (350, 330, 169, 117, 70)], NET_TOL)  # 全登鈕橘、米色面板、紅 X、角色列棕

# ---- heal 特徵：主畫面「取消遇敵」紅龍頭（容差 50）----
ENC_ON = _t([(1380, 630, 129, 6, 0), (1360, 632, 179, 12, 0)], ENC_TOL)


def sig_str(sig, neg: bool = False) -> str:
    """tuple 清單 → gui.ps1 waitpix 字串 'x,y,r,g,b/x,y,r,g,b'；neg = 每點加 '!'（不是這個顏色）。容差由呼叫端另帶"""
    return '/'.join(f'{x},{y},{r},{g},{b}{"!" if neg else ""}' for x, y, r, g, b, _ in sig)


def match(px: dict, sig) -> bool:
    """px = {(x, y): (r, g, b)}；sig 全部點都在各自容差內"""
    return all(close(px[(x, y)], (r, g, b), tol) for x, y, r, g, b, tol in sig)


def points() -> list:
    """classify 需要的所有取樣點（順序固定，fixture 也照這個順序）"""
    return [(x, y) for x, y, *_ in SIG_DIALOG + SIG_REWARD + SIG_PANEL + SIG_SELECT + SIG_HUD + SIG_BATTLE + SIG_CMD + SIG_AUTO_OFF] + [VS_PROBE] + AW_POINTS


def panel_points() -> list:
    """面板 / 主畫面多組 / 載入 / 黑畫面要的取樣點（不在 points() 裡，讓 screen_px.json 與 quest / uikit 的 classify 不變；watch 另外讀）"""
    seen, out = set(points()), []
    cand = [(x, y) for x, y, *_ in PANEL_X.values()] + [(x, y) for pts in PANEL_PTS.values() for x, y, *_ in pts] + \
           [(x, y) for pts in HUD_GROUPS.values() for x, y, *_ in pts] + BLACK_PTS
    for pt in cand:
        if pt not in seen:
            seen.add(pt)
            out.append(pt)
    return out


def _count_ok(px: dict, pts, tol: int) -> int:
    return sum(1 for x, y, r, g, b in pts if (x, y) in px and close(px[(x, y)], (r, g, b), tol))


def panel_of(px: dict):
    """認得的面板名（PANEL_X 的 key）或 None。缺點（呼叫端沒讀 panel_points）一律當不符合"""
    for name, (x, y, r, g, b, tol) in PANEL_X.items():
        if (x, y) in px and close(px[(x, y)], (r, g, b), tol) and _count_ok(px, PANEL_PTS[name], PANEL_TOL) >= PANEL_NEED:
            return name
    return None


def hud_main(px: dict) -> bool:
    """主畫面多組判斷：G1 外掛紅字、G2 底部圖示列、G3 右下按鈕，任一組命中"""
    if _match_safe(px, SIG_HUD):
        return True
    return any(_count_ok(px, pts, HUD_TOL) >= len(pts) - HUD_MISS for pts in HUD_GROUPS.values())


def is_black(px: dict) -> bool:
    return all(pt in px and max(px[pt]) < BLACK_MAX for pt in BLACK_PTS)


def classify(px: dict) -> dict:
    """px 含 points() 的所有點 → {'state', 'gold', 'full', 'cmd', 'auto_off'}。
    state：dialog / reward / battle / panel / select / walking / idle / unknown（優先序不可動：HUD 紅字在戰鬥 / 選擇面板時還在，所以 idle 排最後）
    panel：state=panel 時是面板名（switch / pet / bag …，見 PANEL_NAMES），其他 None。px 沒帶 panel_points() 的點時只認 switch（舊行為）、主畫面只看 G1。"""
    full = False
    pn = None
    gold = sum(1 for x, y in AW_POINTS if px[(x, y)][0] > 225 and 150 < px[(x, y)][1] < 205 and px[(x, y)][2] < 50)
    if match(px, SIG_DIALOG):
        st = 'dialog'
    elif match(px, SIG_REWARD):
        st = 'reward'
    elif match(px, SIG_BATTLE):
        st, full = 'battle', True
    elif match(px, SIG_PANEL):
        st, pn = 'panel', 'switch'
    elif (pn := panel_of(px)):
        st = 'panel'
    elif match(px, SIG_SELECT):
        st = 'select'
    elif close(px[VS_PROBE], VS_COLOR, VS_TOL):
        st = 'battle'
    elif gold >= AW_MIN:
        st = 'walking'
    elif hud_main(px):
        st = 'idle'
    else:
        st = 'unknown'
    cmd = full and match(px, SIG_CMD)                 # 完整戰鬥且在下指令階段
    auto_off = full and match(px, SIG_AUTO_OFF)       # 自動戰鬥鈕是關的
    return {'state': st, 'gold': gold, 'full': full, 'cmd': cmd, 'auto_off': auto_off, 'panel': pn}


# ---- annotate 特徵（watch 專用附註；只上「有正例樣本」的特徵，2026-10-10 以 tools/.cache 等 677 張 1440×830 樣本驗證：
# 4 種各有正例（提示視窗 1、登入 2、選角 1、遇敵鈕 30）、其餘樣本 0 誤判，見 fixtures/annot_px.json）----
# 沒有可靠特徵 / 沒有正例所以**不上線**：通用彈窗（popup）、背包 / 寵物 / 外掛面板（沙地與米色面板太像，沒有樣本證明 0 誤判）、驗證 / 答題視窗（沒有任何樣本）
ANNOT_SIGS = {'notice_dialog': NET_DIALOG, 'login': NET_LOGIN, 'charsel': NET_CHARSEL}
ANNOT_KNOWN = ('login', 'charsel', 'loading', 'black')    # 這些畫面本來就是「已知畫面」：不算 unknown（登入 / 選角是 netwatch 那一層；載入 / 全黑是地圖轉場）


def annot_points() -> list:
    """annotate 需要的取樣點（不在 points() 裡；watch 的 pixel 呼叫把兩組一起讀，classify 的 points() 不變）"""
    seen, out = set(points()), []
    for sig in list(ANNOT_SIGS.values()) + [ENC_ON, SIG_LOADING]:
        for x, y, *_ in sig:
            if (x, y) not in seen:
                seen.add((x, y))
                out.append((x, y))
    for pt in panel_points():
        if pt not in seen:
            seen.add(pt)
            out.append(pt)
    return out


def _match_safe(px: dict, sig) -> bool:
    """像 match，但缺點（呼叫端沒讀這些點，例如只有 classify 用的 fixture）一律當不符合"""
    return all((x, y) in px and close(px[(x, y)], (r, g, b), tol) for x, y, r, g, b, tol in sig)


def annotate(px: dict, base: dict) -> list:
    """watch 專用附註 → ['notice_dialog' | 'login' | 'charsel']（至多一個）。不影響 classify。
    遇敵鈕（enc_on）不在這裡：用 enc_on() 另外取"""
    for name, sig in ANNOT_SIGS.items():
        if _match_safe(px, sig):
            return [name]
    if base.get('state') == 'unknown':          # 載入 / 全黑只在 classify 不認得時才附註（有 HUD 的畫面不可能是轉場）
        if _match_safe(px, SIG_LOADING):
            return ['loading']
        if is_black(px):
            return ['black']
    return []


def enc_on(px: dict, base: dict):
    """主畫面右下「取消遇敵」紅龍頭：True = 原地遇敵開著；False = 主畫面（idle / walking）且沒看到；其他畫面 / 缺點 → None"""
    if _match_safe(px, ENC_ON):
        return True
    if base.get('state') in ('idle', 'walking') and all(pt in px for pt in [(x, y) for x, y, *_ in ENC_ON]):
        return False
    return None


_LABELS = {'idle': '主畫面（未偵測到已知視窗）', 'walking': '自動跑路中', 'dialog': '對話框', 'reward': '獲得物品視窗',
           'select': '選擇對象面板', 'panel': '切換角色面板', 'unknown': '不認得的畫面',
           'no_game': '遊戲未執行', 'minimized': '遊戲視窗最小化', 'error': '讀取畫面失敗', 'unsupported': '版面不支援（非 2880×1659）'}

_ANNOT_TEXT = {'notice_dialog': '提示視窗', 'login': '登入畫面', 'charsel': '選角畫面', 'loading': '載入畫面', 'black': '黑畫面（轉場）'}


def label(d: dict, annot=None) -> str:
    """給人看的狀態文字（watch 寫進 state.json 的 screen.label）。
    idle 一律是「未偵測到已知視窗」：特徵只認得有限幾種視窗，所以任何標籤都不准出現「安全」「無驗證」之類的保證（單元測試檢查）"""
    st = d.get('state')
    annot = list(annot or [])
    if st == 'unknown':                     # 登入 / 選角畫面沒有 HUD → classify 是 unknown，但那是認得的畫面
        for k in ANNOT_KNOWN:
            if k in annot:
                return _ANNOT_TEXT[k]
    if st == 'panel' and d.get('panel'):
        base = '面板：' + PANEL_NAMES.get(d['panel'], d['panel'])
    elif st == 'battle':
        base = '戰鬥中（完整・下指令）' if d.get('cmd') else '戰鬥中（完整・演出中）' if d.get('full') else '戰鬥中（快速）'
    else:
        base = _LABELS.get(st, f'未知狀態 {st}')
    return base + ('（' + '、'.join(_ANNOT_TEXT.get(a, a) for a in annot) + '）' if annot else '')
