#!/usr/bin/env python3
"""畫面像素特徵與分類（純函式、純標準函式庫，不 import winenv，不碰遊戲）。

從 quest.py / netwatch.py / heal.py 搬出的共用特徵；quest.read_screen、netwatch、（之後的）watch 都用同一份。
特徵 = 清單，每點 tuple (x, y, r, g, b, tol)：座標是 2880×1659 版面的截圖座標（1440×830 縮圖座標），
tol 是該特徵原本使用的容差（搬移時逐一保留，不要統一）。
classify(px) 與搬出前的 quest.read_screen 判定逐點相同（fixtures/screen_px.json 驗證）。
驗證停手相關（使用者 2026-10-16 定案）：quiz_screen = 答題 / 驗證介面正面辨識（npcanswer prefab 推出，未實機；命中立刻設旗標）；
net_lost = 網路異常窗（框 + 白字字形，交給 netwatch）；normal_screen = 旗標自動清認的已知正常畫面。annotate 依序先判 quiz、net_lost。
"""
import battleguard

# ---- 容差原值 ----
TOL = 40                             # quest 預設：對話框 / 獲得物品 / 切換面板 / 選擇對象 / HUD / VS 牌
TOL_BATTLE = 25
TOL_CMD = 25
TOL_AUTO_OFF = 20
TOL_CLOSE_ROW = 22
TOL_SWITCH_BTN = 30                  # 底部「切換」鈕圖示
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
               'switch': '切換角色', 'ass': '外掛', 'role': '人物資訊', 'shop': 'NPC 商店'}

# ---- NPC 商店（便利店 / 道具商店；2026-10-15，watch 對它報過 unknown_long 誤警報）----
# 框架：木框大面板 + 左側商品格兩欄 + 右側紅色卷軸（商品說明）+ 數量 −/＋ + 藍色「購買」鈕 + 右上紅圈 ✕；標題木牌的字隨 NPC 不同（便利店…），所以**不看標題字**，
# 只取「各家商店一樣的結構色」：卷軸紅邊 6 點、數量 −/＋ 黃符號 2 點、購買鈕藍 3 點、面板下緣米色帶 3 點、商品格暗框 2 點 = 16 點 + ✕。
# 判定 = ✕（tol 40）+ 16 點中 SHOP_NEED 個在 SHOP_TOL 內（panel_strict 另要 SHOP_NEED_STRICT）。
# 樣本只有 p2 競技場「便利店」2 張（watch-alerts/unknown-1792043285 / 1792043435，同一家店）；離線掃 tools/.cache 2550 張 1440×830 負例
#（含商城 ui/shop.png、交易所、各面板、對話框、戰鬥）最多只命中 1 / 16，所以門檻 12 有 11 點餘裕。別家店若因商品格 / 卷軸內容不同被蓋住 1～4 點仍認得。
# 商城（newstore，紅區）框架完全不同（牛角標題板 + 綠色數量鈕 + 金色購買鈕 + 右側鑽石 / 活力分頁），0 點命中，不會混淆；交易所 / LuckyCard 是全螢幕，也不命中。
SHOP_X = (1207, 107, 190, 74, 49, TOL)
SHOP_PTS = [(840, 190, 175, 72, 74), (1160, 300, 179, 78, 76), (1165, 400, 180, 85, 70), (1165, 250, 152, 59, 67), (880, 160, 196, 78, 81), (1120, 160, 169, 69, 70),
            (880, 465, 255, 227, 89), (1112, 465, 255, 226, 91),
            (910, 595, 119, 160, 214), (1085, 595, 97, 137, 188), (1000, 620, 58, 102, 158),
            (600, 700, 235, 204, 167), (760, 700, 235, 204, 167), (440, 700, 235, 204, 167),
            (280, 300, 150, 117, 84), (805, 400, 124, 94, 67)]
SHOP_TOL = 16
SHOP_NEED = 12               # panel_of（watch 顯示用）
SHOP_NEED_STRICT = 14        # panel_strict（要動手點 ✕ 關時用）

# ---- 每日任務（委託接取）面板 / 快速合成彈窗（2026-10-17 daily.py；取自 notes/daily-probe.md 探路截圖 07 / 12，**單張樣本、未實機**）----
# 沒放進 PANEL_X / PANEL_PTS / PANEL_TITLE（那三張表要每面板 8 個「多張正例都穩定、其餘負例都不符」的統計點 + test_screen_sigs 的 fixture 涵蓋；
# 只有探路 1 次的樣本不夠）→ watch 還不認得這兩個畫面（HUD 會顯示「不認得的畫面」、停留 3 分鐘才會兜底設旗標）；daily.py 每次停留 < 1 分鐘。
# 這裡的 sig 只給 uikit.DAILY / QCRAFT（safe_click 的面板在不在判斷）用：✕ 紅圓 + 標題板 + 木框，格式同 SIG_*（(x, y, r, g, b, tol)）。
DAILY_TOL = 20
DAILY_SIG = [(1193, 98, 197, 73, 49, 40), (712, 92, 146, 93, 49, DAILY_TOL), (600, 92, 136, 86, 51, DAILY_TOL), (820, 92, 139, 89, 56, DAILY_TOL),
             (250, 120, 90, 62, 41, DAILY_TOL), (250, 400, 104, 74, 42, DAILY_TOL), (1180, 400, 96, 65, 41, DAILY_TOL),
             (735, 265, 66, 113, 167, 30), (735, 370, 66, 113, 167, 30)]       # 最後兩點 = 兩顆藍色「合成」鈕
QCRAFT_SIG = [(1080, 156, 195, 73, 49, 40), (720, 143, 144, 90, 61, DAILY_TOL), (480, 552, 66, 113, 167, 30)]      # ✕ + 「快速合成」標題板 + 彈窗內藍色「合成」鈕

# ---- 標題板字（面板辨識主判據，2026-10-11）----
# 每個面板頂端都有木框標題板（寵物 / 背包 / 任務詳情 / 地圖傳送 / 設置 / 組隊 / 提示 / 切換角色 / 人物資訊；外掛是灰米色 Automatic Synchronized System 橫條），
# 位置「每種面板各自固定」（不是全部同一位置：只有寵物 / 人物資訊共用同一塊帶牛角的大板，約 x 600～870、y 70～120，其餘各在自己的 y），字是淺色筆畫（外掛是深色字）。
# 標題板是最上層，不太會被 EXP 浮字 / 特效蓋住；框線點與 ✕ 偶爾會被蓋，所以標題命中就直接認得（不再要求 ✕）。
# 每面板 8 點 = 6 個字的筆畫中心點（各正例穩定）+ 2 個板面背景點（字間 / 字邊的棕色木板，當反例）；要求 TITLE_NEED 個在 TITLE_TOL 內。
# 點用該面板全部正例（pet 220 / bag 78 / ass 64 / quest 13 / switch 10 / transfer 6 / setting 5 / role 5 / qteam 4 / team 3）挑「各正例穩定、其餘 700 多張負例最多只命中 3 / 8」的點。
# 標題都不中才退回 ✕ + PANEL_PTS 8 點（見 panel_of）。切換角色的標題在 EXP 橫幅出現時（橫幅蓋住 y≈180）會被蓋，那種情況走備援。
# 右側直式分頁（寵物 / 倉庫 / 圖鑑、基礎 / 精靈）是子分頁，有選中 / 未選中兩種外觀，不作主判據。
TITLE_TOL = 16
TITLE_NEED = 7
PANEL_TITLE = {
    'pet': [(717, 78, 231, 186, 132), (779, 78, 241, 195, 139), (791, 78, 231, 186, 131), (702, 80, 217, 174, 123), (708, 80, 234, 189, 134), (723, 80, 234, 189, 134), (786, 66, 129, 80, 45), (691, 66, 129, 82, 47)],
    'bag': [(695, 92, 212, 185, 138), (735, 92, 214, 187, 139), (724, 93, 226, 198, 148), (680, 92, 226, 198, 148), (688, 92, 232, 204, 153), (712, 92, 237, 209, 156), (694, 93, 117, 89, 64), (661, 92, 152, 94, 63)],
    'quest': [(666, 66, 233, 188, 133), (677, 66, 212, 170, 120), (683, 66, 225, 181, 128), (697, 66, 238, 193, 136), (703, 66, 230, 185, 131), (709, 66, 221, 177, 126), (673, 66, 121, 88, 61), (651, 66, 147, 89, 57)],
    'transfer': [(778, 85, 212, 184, 137), (682, 86, 218, 190, 143), (688, 86, 210, 182, 136), (665, 85, 224, 196, 147), (723, 85, 229, 201, 151), (736, 85, 240, 212, 159), (679, 85, 98, 58, 35), (636, 85, 128, 77, 46)],
    'setting': [(675, 74, 218, 174, 124), (685, 75, 242, 198, 139), (693, 75, 234, 189, 134), (743, 75, 244, 198, 140), (749, 75, 239, 193, 137), (755, 75, 239, 193, 137), (684, 72, 86, 52, 33), (661, 72, 147, 89, 57)],
    'team': [(674, 59, 227, 182, 129), (757, 59, 231, 186, 132), (766, 59, 225, 181, 128), (742, 60, 215, 172, 121), (749, 60, 217, 174, 123), (684, 61, 238, 194, 137), (671, 58, 141, 85, 57), (661, 58, 148, 89, 60)],
    'qteam': [(693, 160, 234, 206, 155), (703, 160, 229, 201, 150), (709, 160, 229, 201, 150), (715, 160, 229, 201, 150), (727, 161, 237, 209, 157), (733, 161, 228, 200, 149), (744, 158, 127, 80, 56), (681, 152, 158, 100, 70)],
    'switch': [(663, 180, 245, 204, 137), (709, 180, 250, 209, 141), (752, 180, 243, 203, 137), (675, 180, 244, 203, 137), (684, 180, 244, 203, 137), (695, 180, 244, 203, 137), (703, 181, 145, 113, 71), (645, 181, 146, 93, 49)],
    'ass': [(666, 75, 35, 31, 23), (804, 75, 45, 45, 34), (746, 77, 18, 16, 11), (843, 75, 77, 69, 51), (570, 76, 36, 32, 24), (576, 76, 35, 31, 23), (665, 74, 90, 80, 60), (803, 74, 89, 80, 59)],
    'role': [(678, 84, 228, 221, 195), (704, 84, 225, 218, 191), (714, 84, 241, 235, 209), (746, 84, 255, 255, 242), (769, 84, 238, 235, 213), (734, 85, 255, 255, 237), (681, 81, 106, 68, 36), (671, 80, 147, 96, 54)],
}

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
# 載入畫面背景插畫會換（2026-10-12 實機看到恐龍騎士 / 長毛象新圖；舊三點剛好仍中，但只靠背景色不可靠）；quest.py 原本完全不認載入畫面
# → 換圖轉場 6 秒被當 unknown 連 3 次、退出碼 2 誤報驗證視窗。下方「加載中...」白字的形狀兩張圖逐點相同 → 加字形遮罩：
# '#' = 白字（min(rgb) > LOADING_WHITE）、'.' = 不是白字。x 665..735 每 2 px、y 718..736 每 3 px；tools/.cache 1334 張截圖只有 2 張載入畫面命中、0 誤判
LOADING_TEXT_MASK = (
    '..#............##...#.#.......##....',
    '######.####.....#...#.....##########',
    '..#.##.#..#.........#.....#...##...#',
    '..#.#..#..#.....#...#.#...#...##...#',
    '.#..#..#..#.......#.###...##########',
    '.#..#..#..#..##.#.#.##........##....',
    '##..#..####..#########.#......##....',
)
LOADING_WHITE = 220
LOADING_ON_MIN, LOADING_OFF_MAX = 0.95, 0.10              # 白字點至少 95% 是白、非字點最多 10% 是白（背景亮的圖也不會全白）
LOADING_TEXT_PTS = [(665 + 2 * i, 718 + 3 * j, ch == '#') for j, row in enumerate(LOADING_TEXT_MASK) for i, ch in enumerate(row)]


def loading_text(px: dict) -> bool:
    """「加載中...」字形遮罩比對（缺點 → False）"""
    on = [px.get((x, y)) for x, y, w in LOADING_TEXT_PTS if w]
    off = [px.get((x, y)) for x, y, w in LOADING_TEXT_PTS if not w]
    if any(c is None for c in on + off):
        return False
    white = lambda c: min(c) > LOADING_WHITE
    return sum(map(white, on)) >= LOADING_ON_MIN * len(on) and sum(map(white, off)) <= LOADING_OFF_MAX * len(off)


# 英文版載入圖（2026-10-14 03:17 quest-log/031712-UNKNOWN.png：「Loading...」黃字 + 底部綠 / 橘雙進度條，切換地圖時出現）。
# 舊版（10ca3a6）只取綠條 x=200/400 + 橘條兩點 = 要求進度已過 x=400；剛開始載入時綠條還短 / 空 → 不認 → 仍可能連 3 次 unknown。
# 改成「進度無關」：(1) 兩條進度條的米色外框三橫線（y 704 / 740 / 775，x 250～1150 四點，不透明 UI、整條同色，背景插畫換了也不變）
# (2) 兩條軌道各 3 點（x 300 / 700 / 1100）= 填色（綠 / 橘）或空軌深棕，且左→右單調（填色後面才可以是空軌，不可空了又填）。
LOADING_BAR_TOL = 22
LOADING_BAR_FRAME = [(x, y, r, g, b, LOADING_BAR_TOL) for y, (r, g, b) in ((704, (169, 148, 117)), (740, (175, 155, 123)), (775, (189, 168, 133)))
                     for x in (250, 550, 850, 1150)]
LOADING_BAR_TRACK_X = (300, 700, 1100)
LOADING_BAR_TRACKS = ((725, 'green'), (758, 'orange'))      # (y, 填色)


def _bar_cell(c, fill: str) -> str | None:
    """進度條軌道一點 → 'fill'（綠 8,255,18 / 橘 255,170,13）、'empty'（空軌深棕 56,48,38）或 None（都不像）"""
    r, g, b = c
    if fill == 'green' and g >= 200 and r <= 80 and b <= 80:
        return 'fill'
    if fill == 'orange' and r >= 230 and 130 <= g <= 215 and b <= 80:
        return 'fill'
    if max(c) <= 90 and r >= b and abs(r - 56) <= 30 and abs(g - 48) <= 30 and abs(b - 38) <= 30:
        return 'empty'
    return None


def loading_bar(px: dict) -> bool:
    """英文版載入圖雙進度條（外框 12 點全中 + 兩條軌道單調填色）；缺點 → False"""
    if not _match_safe(px, LOADING_BAR_FRAME):
        return False
    for y, fill in LOADING_BAR_TRACKS:
        if any((x, y) not in px for x in LOADING_BAR_TRACK_X):
            return False
        cells = [_bar_cell(px[(x, y)], fill) for x in LOADING_BAR_TRACK_X]
        if None in cells:
            return False
        if 'empty' in cells and 'fill' in cells[cells.index('empty'):]:      # 空了又填 = 不是進度條
            return False
    return True


def loading_bar_points() -> list:
    return [(x, y) for x, y, *_ in LOADING_BAR_FRAME] + [(x, y) for y, _ in LOADING_BAR_TRACKS for x in LOADING_BAR_TRACK_X]


def loading_probe_points() -> list:
    """現場判斷載入畫面要讀的全部點（舊三點 + 「加載中」字形 + 英文版進度條；quest.loading_screen / uikit.loading_now 共用）"""
    seen, out = set(), []
    for pt in [(x, y) for x, y, *_ in SIG_LOADING] + [(x, y) for x, y, _ in LOADING_TEXT_PTS] + loading_bar_points():
        if pt not in seen:
            seen.add(pt)
            out.append(pt)
    return out


def is_loading(px: dict) -> bool:
    """載入畫面：舊三點特徵、「加載中」字形、英文版「Loading」雙進度條（進度無關）任一成立"""
    return _match_safe(px, SIG_LOADING) or loading_text(px) or loading_bar(px)
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
# 底部「切換」鈕圖示露出（黃色雙箭頭 5 點 + 中央深綠 + 右側暗點）：完整戰鬥版面在 850,765（按鈕列右移），主畫面 / 快速戰鬥在 763,760（同一圖示 -87,-5）。
# 2026-10-13 用 tools/.cache 1,700+ 張 1440×830 截圖離線核對（容差 30）：完整戰鬥 90 張 = 切換露出 18 / 快速戰鬥（主畫面版）14 / 關閉列蓋住 58，三者互斥無遺漏；
# 主畫面 idle 407 張主畫面版全中、850 版 0 張（主畫面 850,765 是「組隊」鈕）；非戰鬥畫面 850 版唯一命中的是一張被標成 dialog 的戰鬥圖。
# quest.refresh_characters 點切換前要看到它：切換鈕被「關閉 + 頭像」列蓋住 / 轉場中 / 戰鬥剛結束（主畫面 850,765 = 組隊）都不點。
SIG_SWITCH_FULL = _t([(868, 753, 253, 209, 0), (865, 768, 245, 188, 0), (835, 756, 255, 226, 6), (841, 747, 246, 202, 0),
                      (838, 771, 229, 173, 10), (850, 765, 79, 87, 74), (871, 759, 37, 15, 7)], TOL_SWITCH_BTN)
SIG_SWITCH_MAIN = [(x - 87, y - 5, r, g, b, t) for x, y, r, g, b, t in SIG_SWITCH_FULL]
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

# ---- 主畫面左側信封鈕（178,583）「有新信」發亮（2026-10-13 背包滿 → 任務道具進信箱「這是您丟失的物品」）----
# 正常信封是暗棕圓鈕；有信時整顆變亮黃（會閃：同一段時間 3 張發亮、1 張正常）。tools/.cache 1800 多張 1440×830 樣本只有
# quest-log/060732-boss-done、064721-boss-done、064813-boss-done 3 張發亮（都在 06:07 頭盔進信箱～領信之間），其餘 0 張。
# 只當「可能有信」的觸發：真正領之前 mail.py 會 OCR 郵件文字含「丟失」才領；沒看到發亮不代表沒信（閃爍 / 被對話框蓋住）
MAIL_GLOW = _t([(155, 565, 255, 255, 209), (200, 565, 255, 249, 199), (200, 600, 237, 213, 17), (178, 606, 236, 211, 16)], TOL)
MAIL_GLOW_NEED = 3


def mail_glow(px: dict) -> bool:
    """純函式：信封鈕 4 點至少 MAIL_GLOW_NEED 點是發亮色（缺點當不符）"""
    return _count_ok(px, [(x, y, r, g, b) for x, y, r, g, b, _ in MAIL_GLOW], TOL) >= MAIL_GLOW_NEED


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
    cand = [(x, y) for x, y, *_ in PANEL_X.values()] + [(x, y) for pts in PANEL_PTS.values() for x, y, *_ in pts] + [(x, y) for pts in PANEL_TITLE.values() for x, y, *_ in pts] + \
           [(x, y) for pts in HUD_GROUPS.values() for x, y, *_ in pts] + BLACK_PTS + [SHOP_X[:2]] + [(x, y) for x, y, *_ in SHOP_PTS]     # 商店點放最後（annot_points 以 panel_points 結尾，舊 fixture 的點清單仍是前綴）
    for pt in cand:
        if pt not in seen:
            seen.add(pt)
            out.append(pt)
    return out


def _count_ok(px: dict, pts, tol: int) -> int:
    return sum(1 for x, y, r, g, b in pts if (x, y) in px and close(px[(x, y)], (r, g, b), tol))


def panel_of(px: dict):
    """認得的面板名（PANEL_X 的 key）或 None。缺點（呼叫端沒讀 panel_points）一律當不符合。
    主判據 = 頂部標題板的字（PANEL_TITLE，8 中 TITLE_NEED）；標題都不中才退回 ✕ + PANEL_PTS 8 中 PANEL_NEED"""
    for name, pts in PANEL_TITLE.items():
        if _count_ok(px, pts, TITLE_TOL) >= TITLE_NEED:
            return name
    for name, (x, y, r, g, b, tol) in PANEL_X.items():
        if (x, y) in px and close(px[(x, y)], (r, g, b), tol) and _count_ok(px, PANEL_PTS[name], PANEL_TOL) >= PANEL_NEED:
            return name
    if shop_hit(px, SHOP_NEED):
        return 'shop'
    return None


def shop_hit(px: dict, need: int) -> bool:
    """NPC 商店：✕ 命中 + SHOP_PTS 至少 need 點命中（缺點當不符）"""
    x, y, r, g, b, tol = SHOP_X
    return (x, y) in px and close(px[(x, y)], (r, g, b), tol) and _count_ok(px, SHOP_PTS, SHOP_TOL) >= need


def panel_strict(px: dict):
    """要「動手關」時用的嚴格面板判斷 → 面板名或 None：標題板字（PANEL_TITLE 8 中 TITLE_NEED）**且**該面板的 ✕（PANEL_X）都要命中。
    panel_of 只要其一（給 watch 顯示用）；這裡兩個都要，避免把蓋在面板上的驗證 / 不認得視窗當成面板去點 ✕
    （被模態視窗壓暗的面板，標題 ×0.5 不會命中 → None，照不認得處理）。缺點一律不符"""
    for name, pts in PANEL_TITLE.items():
        x, y, r, g, b, tol = PANEL_X[name]
        if _count_ok(px, pts, TITLE_TOL) >= TITLE_NEED and (x, y) in px and close(px[(x, y)], (r, g, b), tol):
            return name
    if shop_hit(px, SHOP_NEED_STRICT):               # NPC 商店：✕ 關閉不會買東西（購買鈕在 ✕ 的另一邊，不會點到）
        return 'shop'
    return None


def hud_main(px: dict) -> bool:
    """主畫面多組判斷：G1 外掛紅字、G2 底部圖示列、G3 右下按鈕，任一組命中"""
    if _match_safe(px, SIG_HUD):
        return True
    return any(_count_ok(px, pts, HUD_TOL) >= len(pts) - HUD_MISS for pts in HUD_GROUPS.values())


def is_black(px: dict) -> bool:
    return all(pt in px and max(px[pt]) < BLACK_MAX for pt in BLACK_PTS)


TRANSITION_MAX_S = 60.0          # 轉場畫面（載入圖 / 全黑）最多等這麼久；超過當卡住（quest.py 43、uikit.preflight 照舊 9）


def transition_points() -> list:
    """transition() 要讀的全部點（載入畫面三種特徵 + 全黑 10 點，不重複）"""
    pts = loading_probe_points()
    seen = set(pts)
    return pts + [pt for pt in BLACK_PTS if pt not in seen]


def transition(px: dict) -> str | None:
    """地圖轉場畫面（腳本「等它過去、不點、不算不認得」）→ 'loading'（任一種載入圖）/ 'black'（全黑）/ None。
    只在 classify = unknown 時才問（有 HUD 的畫面不可能是轉場）；驗證 / 答題視窗不會有進度條外框、字形或全黑 10 點"""
    if is_loading(px):
        return 'loading'
    if is_black(px):
        return 'black'
    return None


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
# 沒有可靠特徵 / 沒有正例所以**不上線**：通用彈窗（popup；只有「壓暗的背包 / 寵物面板 + 三種已知彈窗」例外，見下方 POPUP_SIGS）、背包 / 寵物 / 外掛面板（沙地與米色面板太像，沒有樣本證明 0 誤判）、驗證 / 答題視窗（沒有任何樣本）
ANNOT_SIGS = {'notice_dialog': NET_DIALOG, 'login': NET_LOGIN, 'charsel': NET_CHARSEL}

# ---- 面板上疊「已知彈窗」（2026-10-12，errlog #243 #244 #254 #261 #264 誤報 verify_suspect）----
# 遊戲的模態彈窗會把底下整個畫面壓暗成約 ×0.5（實測背包 ×0.49～0.50、寵物 ×0.47，每點每通道比例一致），所以面板標題板的字仍在、只是變暗。
# 判定 = 底下是「壓暗的已知面板」（PANEL_TITLE 8 點同一個比例 k ∈ DIM_K、TITLE_NEED 點在 DIM_TOL 內）**且** 彈窗本身吻合下列其中一種（8 點至少 POPUP_NEED）：
#   keypad  = 拆分 / 數量的數字鍵盤（0～9、✕、↵ 大鍵，watch-alerts/unknown-1791750847 / 1791750914）
#   qty     = 「數量輸入」視窗（− 數量 ＋、確定 / 取消，unknown-1791756186 / 1791756276）
#   confirm = 「提示」確定（藍）/ 取消（橘）兩顆鈕的確認窗（丟寵 / 存入戰鬥寵；前 6 點與 pet.CONFIRM_SIG 相同，unknown-1791754960）
# 兩個條件缺一不可：驗證 / 答題視窗（選項是圖片）、網路異常提示（只有一顆確定鈕）、其他沒見過的彈窗即使疊在面板上也仍是 unknown（10 s 截圖報「不認得的畫面」）。
DIM_K = (0.40, 0.56)
DIM_TOL = 10
POPUP_TOL = 16
POPUP_NEED = 7
POPUP_SIGS = {
    'keypad': [(465, 335, 201, 175, 128), (838, 335, 201, 175, 128), (465, 574, 197, 173, 122), (715, 574, 198, 173, 122),
               (840, 440, 205, 177, 122), (980, 590, 209, 177, 122), (552, 395, 70, 61, 50), (437, 300, 53, 47, 39)],
    'qty': [(612, 190, 140, 86, 56), (950, 205, 194, 74, 49), (560, 545, 193, 133, 69), (770, 545, 177, 69, 45),
            (620, 440, 135, 153, 38), (890, 440, 135, 153, 38), (560, 300, 240, 212, 175), (520, 400, 242, 213, 175)],
    'confirm': [(946, 208, 197, 73, 49), (550, 545, 58, 105, 167), (670, 545, 66, 113, 171), (750, 545, 179, 69, 44),
                (870, 545, 193, 87, 53), (700, 460, 243, 215, 179), (715, 190, 139, 85, 57), (700, 300, 241, 213, 176)],
}
POPUP_PANELS = ('bag', 'pet')          # 只有這兩種面板上有正例樣本；其他面板上的彈窗仍不認得

# ---- 背包「刪除管理」：刪除模式 + 「刪除選中」後的單鈕刪除確認窗（2026-10-15，watch / bag.py 共用）----
# 根因（10-15 23:32～23:39 p1 bag.py purge）：
#  (1) 快速戰鬥中「獲得 EXP」浮動橫幅（約 x 470～1000、y 140～310，可疊 3 條）蓋住舊 DELMODE 點 965,192（紅框上緣）
#      → bag.py 以為刪除模式消失（rc 90）且「取消刪除」也不點 → 背包卡在刪除模式 → 重跑時背包外框（BAGANY）不認得 → preflight 連 3 次 unknown → 誤設驗證停手旗標。
#  (2) 刪除確認窗（綠字清單 + 「是否批量刪除道具?」+ 單顆「確定」）會把整個背包壓暗 ×0.48，watch 只認得兩顆鈕的確認窗（POPUP_SIGS['confirm']）
#      → 核對清單 OCR 期間 unknown 超過 10 秒 → watch 誤設停手旗標。
# 刪除模式特徵：紅框左 / 右 / 下緣 + 「刪除選中」紅、「取消刪除」金 + 背包 ✕；全部避開 EXP 橫幅區，7 點中 BAG_DELMODE_NEED 點吻合即可
# （tools/.cache 3034 張 1440×830 樣本：刪除模式 5 張 7/7、其餘任一點 neg 0～1 張；紅框點在普通背包是棕 / 米色）。
BAG_DELMODE_SIG = [(1280, 113, 197, 70, 43, 30), (700, 410, 246, 70, 83, 26), (1232, 350, 246, 70, 83, 26), (1232, 410, 245, 69, 82, 26),
                   (1050, 508, 244, 68, 82, 26), (1150, 688, 191, 127, 63, 26), (1150, 625, 177, 70, 38, 30)]
BAG_DELMODE_NEED = 6
# 刪除確認窗本體：「提示」單鈕窗的框（✕、標題板、藍「確定」兩側、米色底；避開清單 / 問句字的範圍，5 行清單 + 問句也不碰）。
# 這個框和網路異常 / 「接取任務條件不達標」等所有單鈕「提示」窗**完全相同**（kr322 / qd-after / net1 樣本；網路異常 2026-10-16 起另有字形 net_lost），所以只當 bag.py 腳本內的「窗開了沒」；
# watch 要認成已知畫面還得加下面三個條件。
BAG_DELOK_FRAME = [(946, 208, 197, 73, 49, 24), (715, 190, 139, 85, 57, 24), (645, 557, 56, 99, 156, 24), (785, 557, 56, 104, 161, 24),
                   (560, 545, 244, 215, 177, 24), (880, 545, 245, 217, 179, 24), (520, 520, 237, 209, 171, 24), (900, 500, 243, 213, 175, 24)]
BAG_DELOK_NEED = 7
# 條件 2：窗外露出的是「壓暗 ×0.48 的刪除模式背包」（BAG_DELMODE_SIG 在確認窗外面的點，6 點中 5 點），加上 dim_panel = bag（標題板）
DELOK_DIM_K = 0.48
DELOK_DIM_TOL = 16
_DELOK_BOX = (470, 175, 495, 465)                  # 確認窗範圍 (x, y, w, h)：BAG_DELMODE_SIG 落在這裡的點被窗蓋住，不拿來當壓暗背景
BAG_DELOK_CTX = [(x, y, round(r * DELOK_DIM_K), round(g * DELOK_DIM_K), round(b * DELOK_DIM_K)) for x, y, r, g, b, _ in BAG_DELMODE_SIG
                 if not (_DELOK_BOX[0] <= x < _DELOK_BOX[0] + _DELOK_BOX[2] and _DELOK_BOX[1] <= y < _DELOK_BOX[1] + _DELOK_BOX[3])]
BAG_DELOK_CTX_NEED = len(BAG_DELOK_CTX) - 1
# 條件 3：窗內有亮綠字清單（40,240,0）。清單垂直置中、行距 41：奇數行時中間行在 y 354～383、偶數行時中間兩行在 333～363 / 374～404，
# 所以 y 356 / 366 / 376 / 386 四列一定穿過某一行字；x 642～786 是最短清單（單條「馬祖的斧頭*1|」x 628～797）也會蓋到的中段。
# 12 張正例（1～5 行）命中 10～44 點，其餘 3000 多張（含「提示」單鈕窗、獎勵窗）最多 13 點、而且都不滿足條件 1 + 2。
DELOK_GREEN_PTS = [(x, y) for y in (356, 366, 376, 386) for x in range(642, 790, 6)]
DELOK_GREEN_MIN = 4


def _green_text(c) -> bool:
    r, g, b = c
    return g >= 190 and r <= 110 and b <= 70


def need_match(px: dict, sig, need: int) -> bool:
    """sig（6 元素）至少 need 點在各自容差內；缺點當不符"""
    return sum(1 for x, y, r, g, b, tol in sig if (x, y) in px and close(px[(x, y)], (r, g, b), tol)) >= need


def bag_delmode(px: dict) -> bool:
    """背包刪除模式（紅框 + 刪除選中 / 取消刪除鈕），容許 1 點被 EXP 橫幅等蓋住"""
    return need_match(px, BAG_DELMODE_SIG, BAG_DELMODE_NEED)


def bag_delok(px: dict) -> bool:
    """壓暗的刪除模式背包上疊「刪除確認窗」（watch 認成已知畫面用）：四個條件全要——
    單鈕提示窗框 7/8、窗外是壓暗的刪除模式紅框 + 按鈕、背包標題板壓暗（dim_panel = bag）、窗內有亮綠字清單。
    驗證 / 答題視窗（選項是圖片）、網路異常提示（白字、沒有綠字清單）、疊在普通背包或其他面板上的提示窗都不符 → 照舊 unknown"""
    if not need_match(px, BAG_DELOK_FRAME, BAG_DELOK_NEED):
        return False
    if _count_ok(px, BAG_DELOK_CTX, DELOK_DIM_TOL) < BAG_DELOK_CTX_NEED:
        return False
    if dim_panel(px) != 'bag':
        return False
    return sum(1 for pt in DELOK_GREEN_PTS if pt in px and _green_text(px[pt])) >= DELOK_GREEN_MIN


def delok_points() -> list:
    """bag_delok 要讀的全部點（框 + 壓暗背景 + 綠字探測格 + dim_panel 要的各面板標題板點），不重複"""
    pts = [(x, y) for x, y, *_ in BAG_DELOK_FRAME] + [(x, y) for x, y, *_ in BAG_DELOK_CTX] + DELOK_GREEN_PTS + \
          [(x, y) for ps in PANEL_TITLE.values() for x, y, *_ in ps]
    return list(dict.fromkeys(pts))


# ---- 背包 / 倉庫頁「道具說明彈窗」（點道具格跳出：圖示 + 名稱 + 詳細介紹 + 拆分 / 丟棄 / 穿戴 / 取出 / 存入鈕；2026-10-16，watch / uikit 共用）----
# 根因（10-16 p2 三次誤設驗證停手旗標，最後一次 02:40:05 watch-alerts/unknown-1792089604）：腳本 / 人開著道具彈窗超過 10 秒，
# 整個背包被壓暗（消耗品彈窗 ×0.60、裝備彈窗 ×0.45，每點每通道同一比例；不在 dim_panel 的 0.40～0.56 內、標題板還常被跑馬燈蓋）→ unknown。
# 三個條件全要（驗證 / 答題視窗、網路提示、別的彈窗不可能同時滿足）：
#   1. 窗外是「同一比例壓暗的背包外框」：✕、刪除管理、整理背包 + 右半米色底 5 點（背包頁 / 倉庫頁右半都是背包格，兩頁一樣），8 中 7；
#   2. 彈窗金框左右兩邊：消耗品版 x 492 / 968、裝備版 x 482 / 958（y 520 / 600 / 690 三列），其中一版 6 點全中；
#   3. 彈窗底部有藍色按鈕（拆分 / 丟棄 / 穿戴 / 取出；y 640 / 650 兩列至少 ITEMPOP_BTN_MIN 點藍）。
# 樣本：clients/PrimalSA2/s6.png、watch-alerts/unknown-1792085490 / 1792089604 / 1792044006、p4/depot_popup、ui-log/052337（跑馬燈蓋標題）等，fixtures/bag_itempop_px.json。
BAG_ITEMPOP_BG = [(1280, 113, 197, 70, 43), (1150, 625, 177, 70, 38), (1150, 688, 58, 106, 162), (990, 300, 223, 187, 147),
                  (1240, 300, 244, 219, 183), (990, 520, 223, 187, 147), (1240, 520, 244, 219, 187), (1255, 745, 229, 199, 163)]
ITEMPOP_DIM_K = (0.40, 0.66)
ITEMPOP_DIM_TOL = 12
ITEMPOP_BG_NEED = 7
ITEMPOP_GOLD = (186, 129, 65)
ITEMPOP_GOLD_TOL = 28
ITEMPOP_FRAMES = ([(x, y) for x in (492, 968) for y in (520, 600, 690)],     # 消耗品 / 倉庫取出版（x 492～968）
                  [(x, y) for x in (482, 958) for y in (520, 600, 690)])     # 裝備版（穿戴 / 丟棄，x 482～958）
ITEMPOP_BTN_PTS = [(x, y) for y in (640, 650) for x in range(540, 930, 6)]
ITEMPOP_BTN_MIN = 6


def _blue_btn(c) -> bool:
    r, g, b = c
    return b >= 140 and b - r >= 70 and r <= 120


def _dim_k(px: dict, pts):
    """pts（x, y, r, g, b）同一比例壓暗的 k（中位數）與吻合點數 → (k, n)；缺點當不符"""
    ratios = sorted(c / ref for x, y, *refc in pts if (x, y) in px for c, ref in zip(px[(x, y)], refc) if ref >= 80)
    if not ratios:
        return None, 0
    k = ratios[len(ratios) // 2]
    n = sum(1 for x, y, r, g, b in pts if (x, y) in px and all(abs(c - ref * k) <= ITEMPOP_DIM_TOL for c, ref in zip(px[(x, y)], (r, g, b))))
    return k, n


def bag_itempop(px: dict) -> bool:
    """壓暗的背包（或倉庫頁）上疊「道具說明彈窗」（三個條件見上方註解）。缺點一律不符"""
    k, n = _dim_k(px, BAG_ITEMPOP_BG)
    if k is None or not ITEMPOP_DIM_K[0] <= k <= ITEMPOP_DIM_K[1] or n < ITEMPOP_BG_NEED:
        return False
    if not any(all(pt in px and close(px[pt], ITEMPOP_GOLD, ITEMPOP_GOLD_TOL) for pt in fr) for fr in ITEMPOP_FRAMES):
        return False
    return sum(1 for pt in ITEMPOP_BTN_PTS if pt in px and _blue_btn(px[pt])) >= ITEMPOP_BTN_MIN


def itempop_points() -> list:
    """bag_itempop 要讀的全部點（不重複）"""
    pts = [(x, y) for x, y, *_ in BAG_ITEMPOP_BG] + [pt for fr in ITEMPOP_FRAMES for pt in fr] + ITEMPOP_BTN_PTS
    return list(dict.fromkeys(pts))


def dim_panel(px: dict):
    """被模態彈窗壓暗的已知面板名（PANEL_TITLE 同一比例 k 縮暗）或 None。缺點一律不符。未壓暗（k≈1）的面板不算"""
    for name, pts in PANEL_TITLE.items():
        if not all((x, y) in px for x, y, *_ in pts):
            return None
        ratios = sorted(c / ref for x, y, *refc in pts for c, ref in zip(px[(x, y)], refc) if ref >= 80)
        if not ratios:
            continue
        k = ratios[len(ratios) // 2]
        if not DIM_K[0] <= k <= DIM_K[1]:
            continue
        ok = sum(1 for x, y, r, g, b in pts if all(abs(c - ref * k) <= DIM_TOL for c, ref in zip(px[(x, y)], (r, g, b))))
        if ok >= TITLE_NEED:
            return name
    return None


def popup_over_panel(px: dict):
    """面板上疊已知彈窗 → (面板名, 彈窗種類) 或 None（兩個條件見上方註解）"""
    kinds = [k for k, pts in POPUP_SIGS.items() if _count_ok(px, pts, POPUP_TOL) >= POPUP_NEED]
    if len(kinds) != 1:
        return None
    pn = dim_panel(px)
    return (pn, kinds[0]) if pn in POPUP_PANELS else None


ANNOT_KNOWN = ('login', 'charsel', 'loading', 'black', 'net_lost', 'popup_keypad', 'popup_qty', 'popup_confirm', 'popup_delok', 'popup_item')    # 這些畫面本來就是「已知畫面」：不算 unknown（登入 / 選角 / 網路異常窗是 netwatch 那一層；載入 / 全黑是地圖轉場；popup_* = 面板上疊已知彈窗；popup_delok = 背包刪除確認窗；popup_item = 背包道具說明彈窗）。答題介面 quiz 刻意不在這裡（它是「認得的危險畫面」）


# ---- 網路異常提示窗（「提示：網路異常，是否重連?」，2026-10-16 使用者定案：交給 netwatch、不設驗證停手旗標）----
# 根因（10-16 08:00 三個視窗同時斷線）：網路異常窗的框和「接取任務條件不達標」、刪除確認等單鈕「提示」窗完全相同（NET_DIALOG / BAG_DELOK_FRAME），
# watch 只能當 unknown → 10 秒設旗標 → netwatch 看到旗標 exit 9 不點 → 窗不會自己消失 → 旗標永遠清不掉（死結）。
# 解法：框（NET_DIALOG）+ 訊息白字字形都符合 → 'net_lost'（已知畫面），watch 叫 netwatch 處理；字形不用 OCR，比像素（同 LOADING_TEXT_MASK 的做法）。
# 字形點：net1.png（10-10）與 10-16 08:00 三個視窗的 watch-alerts（unknown-1792108847 / 1792108852 / 1792108855）白字（min(rgb) > 220）
# 逐點完全相同（字在 586～842 × 374～399）；ON = 筆畫內部（自己與上下左右都白）、OFF = 3×3 內都不白，各平均取 48 點。
# 負例：同框的「接取任務條件不達標 / 請到任務詳情進行查閱」（kr322、qd-after，白字在 y 395～418）ON 命中率遠低於門檻。
NET_MSG_ON = [(646, 376), (652, 376), (660, 376), (728, 376), (790, 376), (820, 376), (628, 378), (634, 378), (680, 378), (688, 378), (790, 378), (840, 378),
              (646, 380), (652, 380), (660, 380), (790, 380), (588, 382), (622, 382), (762, 382), (768, 382), (648, 384), (686, 384), (790, 384), (808, 384),
              (826, 384), (840, 384), (790, 386), (588, 388), (626, 388), (648, 388), (656, 388), (658, 388), (798, 388), (838, 388), (756, 390), (790, 390),
              (648, 392), (658, 392), (728, 392), (770, 392), (620, 394), (770, 394), (810, 394), (838, 394), (634, 396), (726, 396), (736, 396), (770, 396)]
NET_MSG_OFF = [(586, 374), (614, 374), (642, 374), (700, 374), (724, 374), (768, 374), (804, 374), (836, 374), (666, 376), (706, 376), (750, 376), (642, 378),
               (710, 378), (804, 378), (696, 380), (720, 380), (776, 380), (642, 382), (710, 382), (774, 382), (626, 384), (704, 384), (748, 384), (600, 386),
               (692, 386), (716, 386), (780, 386), (670, 388), (712, 388), (780, 388), (638, 390), (670, 390), (720, 390), (804, 390), (668, 392), (720, 392),
               (774, 392), (638, 394), (698, 394), (742, 394), (776, 394), (834, 394), (676, 396), (716, 396), (594, 398), (652, 398), (698, 398), (748, 398)]
NET_MSG_WHITE = 220
NET_MSG_ON_MIN, NET_MSG_OFF_MAX = 0.90, 0.10              # 筆畫點至少 90% 白、非筆畫點最多 10% 白


def net_msg(px: dict) -> bool:
    """「網路異常，是否重連?」白字字形比對（缺點 → False）"""
    on = [px.get(pt) for pt in NET_MSG_ON]
    off = [px.get(pt) for pt in NET_MSG_OFF]
    if any(c is None for c in on + off):
        return False
    white = lambda c: min(c) > NET_MSG_WHITE
    return sum(map(white, on)) >= NET_MSG_ON_MIN * len(on) and sum(map(white, off)) <= NET_MSG_OFF_MAX * len(off)


def net_lost(px: dict) -> bool:
    """網路異常提示窗：NET_DIALOG 框 6 點全中 + 訊息字形符合（netwatch.detect / watch annotate 共用）"""
    return _match_safe(px, NET_DIALOG) and net_msg(px)


def net_points() -> list:
    """net_lost 要讀的全部點（框 + 字形），不重複"""
    return list(dict.fromkeys([(x, y) for x, y, *_ in NET_DIALOG] + NET_MSG_ON + NET_MSG_OFF))


# ---- 答題 / 防腳本驗證介面（npcanswer = UInpcanswerScreen；鐵則 5：正面命中 → 立刻設驗證停手旗標，使用者 2026-10-16 定案）----
# **沒有實機截圖**（猜謎三兄弟不會再跑到答題）：特徵來自 GameClient 的 prefab（uiuinpcanswer_yhkrn.assetbundle，唯讀抽取）合成的模擬圖，
# 產生器 tools/extract/uimock.py（輸出 tools/.cache/npcanswer-extract/mock_*.png、layout.json）。版面（1440×830 截圖座標，畫布比例 k≈1.0546
# 由 10-09 爬塔實測的點擊座標反推：選項 463 / 643 / 822 / 1002, 430、確認 735, 610 三者一致）：
#   大彈窗 bg_2（米色、木框）約 x 312～1157 × y 185～703；標題板「知識答題」約 x 577～893 × y 149～219；
#   題目白字 y 257～304；4 張棕色選項卡（bg_qh_stone，171×244）x 377 起每 179 px、y 304～548，卡內是寵物全身圖；
#   卡下方 img_beijing 淺棕底條 y 548～564；藍色「確認」鈕 x 628～843 × y 560～657；背景整片壓暗 ×0.4（maskCol 黑 α0.6）。
# 判定（quiz_screen）：7 組點（左右米色邊條、題目上方米色、卡下淺棕條、確認鈕藍、標題板木色、彈窗下緣木框）共 QUIZ_N（34）點，
# 至少 QUIZ_NEED 點在 QUIZ_TOL 內，且至少 QUIZ_GROUPS_NEED 組有一半以上吻合（容許實機版面和推算有出入時整組不中）；
# 點都避開文字與卡內寵物圖（題目 / 選項每次不同）。
# 點是在 20 張模擬圖（4 種實機背景 × k 1.0466 / 1.0546 / 1.062 × 位移 ±6 px）全部穩定（各色差 ≤ 10）的位置平均挑的；
# 2026-10-16 掃 tools/.cache 全部 3108 張 1440×830 實機截圖：0 張命中，最高 15 / 34 點、4 / 7 組（設置面板 ui/j_*、組隊面板）；模擬圖 20 / 20 張 34 / 34。
# 可信度：未實機（版面照 prefab 推，實際有出入就只能靠 watch 3 分鐘兜底）。
QUIZ_TOL = 24
QUIZ_GROUPS = {
    'side_l': [(356, 320, 239, 213, 178), (364, 368, 244, 217, 181), (352, 420, 241, 216, 180), (360, 468, 244, 217, 181), (368, 516, 244, 215, 181)],
    'side_r': [(1132, 320, 222, 187, 148), (1100, 372, 241, 216, 181), (1112, 420, 239, 215, 181), (1100, 472, 242, 216, 180), (1116, 516, 241, 215, 181)],
    'top': [(412, 224, 234, 210, 176), (472, 248, 239, 209, 173), (536, 240, 241, 212, 175), (928, 232, 239, 208, 167), (992, 224, 238, 209, 173), (1056, 236, 239, 211, 174)],
    'tan': [(456, 552, 225, 189, 148), (572, 552, 225, 189, 148), (684, 552, 225, 189, 148), (800, 552, 225, 189, 148), (916, 552, 225, 189, 148), (1028, 552, 225, 189, 148)],
    'btn': [(668, 624, 50, 99, 159), (684, 620, 61, 107, 168), (796, 596, 61, 109, 168), (808, 608, 52, 96, 160)],
    'title': [(640, 172, 145, 89, 60), (652, 188, 148, 92, 64), (812, 196, 146, 94, 63), (832, 172, 146, 88, 57)],
    'bottom': [(624, 688, 105, 69, 43), (724, 688, 104, 71, 46), (860, 688, 105, 69, 45), (992, 688, 101, 69, 43)],
}
QUIZ_N = sum(len(v) for v in QUIZ_GROUPS.values())
QUIZ_NEED = 26
QUIZ_GROUPS_NEED = 6


def quiz_screen(px: dict) -> bool:
    """答題 / 驗證介面（npcanswer）正面命中。缺點一律不符"""
    total = groups = 0
    for pts in QUIZ_GROUPS.values():
        n = _count_ok(px, pts, QUIZ_TOL)
        total += n
        groups += n * 2 >= len(pts)
    return total >= QUIZ_NEED and groups >= QUIZ_GROUPS_NEED


def quiz_points() -> list:
    return list(dict.fromkeys((x, y) for pts in QUIZ_GROUPS.values() for x, y, *_ in pts))


NORMAL_STATES = ('idle', 'walking', 'battle', 'panel')   # 驗證停手旗標自動清認的「已知正常畫面」（verifyhalt.AutoClear，使用者 2026-10-16）
NORMAL_ANNOT = ('login', 'charsel', 'loading', 'net_lost')   # 這些附註也算已知正常（登入 / 選角 / 載入 / 網路異常窗，使用者 2026-10-16：netwatch 那一層的畫面要能自動清旗標，否則斷線會死結）


def normal_screen(state, annot=()) -> bool:
    """驗證停手旗標可以自動清的畫面（watch 每輪 / uikit.preflight 現場讀共用）：
    主畫面 idle / 自動跑路 walking / 戰鬥 battle / 認得的面板 panel，而且沒有任何附註（提示視窗 notice_dialog 等）；
    或 unknown 但附註是面板上疊已知彈窗（popup_*，ANNOT_KNOWN）或登入 / 選角 / 載入 / 網路異常窗（NORMAL_ANNOT）。
    答題介面（annot quiz）任何情況都不算。
    刻意不算：對話框 dialog（驗證視窗是 NpcScript，可能長得像對話框）、獲得物品 reward、選擇對象 select、
    全黑、其他 unknown、讀不到 / 最小化 / 沒開遊戲"""
    annot = list(annot or [])
    if 'quiz' in annot:
        return False
    if state in NORMAL_STATES:
        return not annot
    if state == 'unknown':
        return any((a.startswith('popup_') and a in ANNOT_KNOWN) or a in NORMAL_ANNOT for a in annot)
    return False


def annot_points() -> list:
    """annotate 需要的取樣點（不在 points() 裡；watch 的 pixel 呼叫把兩組一起讀，classify 的 points() 不變）"""
    seen, out = set(points()), []
    for sig in list(ANNOT_SIGS.values()) + [ENC_ON, SIG_LOADING] + list(POPUP_SIGS.values()):
        for x, y, *_ in sig:
            if (x, y) not in seen:
                seen.add((x, y))
                out.append((x, y))
    for pt in panel_points():
        if pt not in seen:
            seen.add(pt)
            out.append(pt)
    return out


def loading_points() -> list:
    """watch 另外加讀的點：「加載中」字形遮罩 + 英文版進度條 + 背包刪除確認窗（delok_points，2026-10-15）+ 背包道具說明彈窗（itempop_points，2026-10-16）
    + 網路異常窗字形（net_points）+ 答題介面（quiz_points，2026-10-16）。
    不在 points() / annot_points()（那兩組被凍結 fixture 綁住）"""
    seen, out = set(points()) | set(annot_points()), []
    for pt in [(x, y) for x, y, _ in LOADING_TEXT_PTS] + loading_bar_points() + delok_points() + itempop_points() + net_points() + quiz_points():
        if pt not in seen:
            seen.add(pt)
            out.append(pt)
    return out


def _match_safe(px: dict, sig) -> bool:
    """像 match，但缺點（呼叫端沒讀這些點，例如只有 classify 用的 fixture）一律當不符合"""
    return all((x, y) in px and close(px[(x, y)], (r, g, b), tol) for x, y, r, g, b, tol in sig)


def annotate(px: dict, base: dict) -> list:
    """watch 專用附註 → ['quiz'] / ['net_lost'] / ['notice_dialog' | 'login' | 'charsel'] / ['loading'] / ['black'] / ['popup_*', 'over_面板']。不影響 classify。
    quiz（答題 / 驗證介面）不看 classify 結果、最先判（它可能被 classify 判成 dialog / panel 等）；
    net_lost（網路異常窗：框 + 字形）取代原本的 notice_dialog。遇敵鈕（enc_on）不在這裡：用 enc_on() 另外取"""
    if quiz_screen(px):
        return ['quiz']
    if net_lost(px):
        return ['net_lost']
    if base.get('state') == 'unknown' and bag_delok(px):      # 刪除確認窗的框和「提示」單鈕窗相同（notice_dialog 也會中），所以先判
        return ['popup_delok', 'over_bag']
    if base.get('state') == 'unknown' and bag_itempop(px):    # 道具說明彈窗：窗外背包壓暗 ×0.45～0.60（dim_panel 不認）
        return ['popup_item', 'over_bag']
    for name, sig in ANNOT_SIGS.items():
        if _match_safe(px, sig):
            return [name]
    if base.get('state') == 'unknown':          # 載入 / 全黑只在 classify 不認得時才附註（有 HUD 的畫面不可能是轉場）
        if is_loading(px):
            return ['loading']
        if is_black(px):
            return ['black']
        hit = popup_over_panel(px)
        if hit:
            return ['popup_' + hit[1], 'over_' + hit[0]]
    return []


def enc_on(px: dict, base: dict):
    """主畫面右下「取消遇敵」紅龍頭：True = 原地遇敵開著；False = 主畫面（idle / walking）且沒看到；其他畫面 / 缺點 → None"""
    if _match_safe(px, ENC_ON):
        return True
    if base.get('state') in ('idle', 'walking') and all(pt in px for pt in [(x, y) for x, y, *_ in ENC_ON]):
        return False
    return None


_LABELS = {'idle': '主畫面', 'walking': '自動跑路中', 'dialog': '對話框', 'reward': '獲得物品視窗',
           'select': '選擇對象面板', 'panel': '切換角色面板', 'unknown': '不認得的畫面',
           'no_game': '遊戲未執行', 'minimized': '遊戲視窗最小化', 'error': '讀取畫面失敗', 'unsupported': '版面不支援（非 2880×1659）'}

_ANNOT_TEXT = {'notice_dialog': '提示視窗', 'login': '登入畫面', 'charsel': '選角畫面', 'loading': '載入畫面', 'black': '黑畫面（轉場）',
               'net_lost': '網路異常窗（交給 netwatch）', 'quiz': '答題 / 驗證視窗',
               'popup_keypad': '數字鍵盤', 'popup_qty': '數量輸入視窗', 'popup_confirm': '確定 / 取消提示窗', 'popup_delok': '刪除確認窗', 'popup_item': '道具說明彈窗'}


def label(d: dict, annot=None) -> str:
    """給人看的狀態文字（watch 寫進 state.json 的 screen.label）。
    idle 標「主畫面」（只代表沒認出已知視窗，不等於沒有驗證視窗）：特徵只認得有限幾種視窗，所以任何標籤都不准出現「安全」「無驗證」之類的保證（單元測試檢查）"""
    st = d.get('state')
    annot = list(annot or [])
    if 'quiz' in annot:                     # 答題介面正面命中：不管 classify 判成什麼都標這個（鐵則 5 停手）
        return '答題 / 驗證視窗（停手，請人工處理）'
    if st == 'unknown':                     # 登入 / 選角畫面沒有 HUD → classify 是 unknown，但那是認得的畫面
        for k in ANNOT_KNOWN:
            if k in annot:
                if k.startswith('popup_'):              # 面板上疊已知彈窗：「面板：背包＋數量輸入視窗」
                    pn = next((a[5:] for a in annot if a.startswith('over_')), None)
                    return f'面板：{PANEL_NAMES.get(pn, pn)}＋{_ANNOT_TEXT[k]}'
                return _ANNOT_TEXT[k]
    if st == 'panel' and d.get('panel'):
        base = '面板：' + PANEL_NAMES.get(d['panel'], d['panel'])
    elif st == 'battle':
        base = '戰鬥中（完整・下指令）' if d.get('cmd') else '戰鬥中（完整・演出中）' if d.get('full') else '戰鬥中（快速）'
    else:
        base = _LABELS.get(st, f'未知狀態 {st}')
    return base + ('（' + '、'.join(_ANNOT_TEXT.get(a, a) for a in annot) + '）' if annot else '')
