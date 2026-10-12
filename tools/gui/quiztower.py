#!/usr/bin/env python3
"""猜謎三兄弟（1.82，任務 3003）步 1「爬塔拿金布伊」：811 → 800～809 每層答守衛的寵物名字題 → 810 伊那多「拿金豬」。只用標準函式庫。

**實機驗證狀態（2026-10-12 寫成時）**：只有離線測試（test_quiztower.py：假 gui 模擬整座塔 + 合成選項圖比對）。
流程、座標取自 notes/quest-log.md 10-09 手動爬塔紀錄；答題視窗的 OCR 範圍、選項圖裁切框、守衛點擊位置、
「點追蹤能不能在塔內巡路」都**待實機驗證**（清單見 .claude/skills/psa-game-ui/ui/quest.md「猜謎三兄弟爬塔」）。第一次實跑請在旁邊看。

用法（專案根目錄；WSL / Windows 原生相同）：
  uv run --no-project python tools/gui/quiztower.py run [--dry-run] [--at 地圖] [--no-track] [--max-min 45]
        從目前位置接著爬（中斷後重跑 = 續跑：讀座標判斷在第幾層、該層答過沒）；--dry-run 只印每層計畫（不碰遊戲，--at 指定起點地圖，預設 811）
  uv run --no-project python tools/gui/quiztower.py bank [名稱]              # 印題庫（名字題 → 正解 imageId / 靜態圖），不碰遊戲
  uv run --no-project python tools/gui/quiztower.py match 截圖.png --question "以下哪只寵物的名字叫做“諾克斯”" [--dump]
        離線比對一張存好的截圖（1440×830）：印 4 個選項分數、選哪個、夠不夠明確；--dump 把 4 張裁切存到 tools/.cache/quiztower/。不碰遊戲
  uv run --no-project python tools/gui/quiztower.py status                   # 唯讀：讀座標 → 印目前在第幾層、下一步
  可 import：quiztower.run(dry_run=False, use_track=True, tools=None, ...) → 退出碼；結果 dict 在 quiztower.LAST

前置：questrun 已接取 3003（questdetail「傳送」→ 受理A「接藍暴任務」→「接受」，人在 811），5 人同隊、原地遇敵關著（questrun 交接已做）。

每層流程（800～809；偶數層守衛 29,19 / 出口 29,13 / 進場 14,26，奇數層守衛 18,19 / 出口 18,13 / 進場 32,26）：
  1 preflight    uikit.preflight（版面 / 斷線 / 畫面連 3 次不認得 → 9）
  2 到守衛正下方 先點任務追蹤卡（quest.track_task「猜謎三兄弟」）讓遊戲自動巡路；點後 TRACK_MOVE_S 秒座標沒變 = 這張圖不能巡路
                 （800～810 屬 noTaskNavigate，10-09 實測沒反應）→ 本次執行之後都不再點追蹤，改 walk.py 走到 (守衛 x, 20)；
                 800 層 maps.bin 沒通行格：從進場點照紀錄點地面 FLOOR800_CLICKS，再 walk.py 直線分段補到 29,20
  3 點守衛       GUARD_CLICKS（紀錄座標）→ 沒對話框再試 walk.npc_screen 算出來的點；對話框按鈕 OCR 要有「猜謎答題」（且在左鈕位置）才按左鈕 948,461
  4 安全閘       見下；不符 → 退出碼 9，不點任何東西
  5 作答         截圖 → 裁 4 張選項圖 → 與題庫 4（～5）張正解候選靜態圖比對 → 最佳指派（排列）選出正解位置；不明確 → 135 交人
                 → 點選項 → 藍「確認」735,610 → 答題視窗要消失（還在 = 疑似答錯 → 136）
  6 走出口       walk.py 走到出口格（exit_map = 上一層）→ 換層等 HUD 載入；走不過去（圍欄沒開）→ 136
  810：伊那多 28,16（先試追蹤，否則走到 28,17 點她）→ 按鈕「拿金豬」→「完成」→ Loading → 傳回 811 = 完成（退出碼 0）

答題安全閘（鐵則 5；四條件全部成立才作答，任一不符 = 當伺服器防腳本驗證，立刻停手、不點任何東西、退出碼 9）：
  ① 目前地圖 800～810（點守衛前讀的座標）
  ② GATE_WINDOW_S 秒內本腳本剛按過守衛對話框的「猜謎答題」鈕（答題視窗是自己觸發的）
  ③ 視窗文字有標題「知識答題」
  ④ 題目是題庫裡的「哪只寵物叫(做) X」名字題（knowledge/quests/answers.md + Answer.jsonl；正解 = 選項中名字剛好是 X 的那張圖）。
     註：10-09 實際出現的題目句型不只「以下哪只寵物的名字叫做“X”」，還有「以下哪只寵物叫做烏寶寶？」「下列圖片中哪只寵物叫加格？」
     「以下圖中哪只寵物叫做朵洛將恩？」「下列圖中哪只寵物叫哥斯哥斯？」（Answer 51 / 52 / 65 / 66），只認字面前綴會在這幾層誤停，
     所以 ④ 認的是「題庫裡的名字題全文」（句型 + 名字都要對上題庫），系別 / 四聖獸 / 「不是 XX」這類題一律不認 → 9。
  殘餘風險：伺服器驗證剛好在 ② 的窗口內跳出、而且長得一模一樣（同標題、同題庫）時分不出來；GATE_WINDOW_S 刻意短。

作答比對（answer_from_image，只用標準函式庫）：
  畫面選項：截圖（1440×830）裁 OPT_XS × OPT_Y 為中心 OPT_W×OPT_H 的框；外圈 3 px 取中位數當底色，與底色差 > BG_TOL 的像素 = 前景，
            剝掉邊緣「整排幾乎全滿」的框線列 / 欄後取前景外框。
  靜態圖：tools/.cache/pet-images/static/（tools/extract/pet_images.py 匯出；imageId → 檔名用 pet_images.find），alpha ≥ 128 = 前景。
  特徵：前景外框縮成 GRID×GRID 格（每格前景比例 + 平均色）+ 4×4×4 色彩直方圖 + 長寬比；相似度 = 形狀 / 格色 / 直方圖 / 長寬比加權。
  決策：4 個選項 × 候選圖的分數矩陣，取總分最高的一對一指派（排列）；正解圖被指派到的選項 = 答案。
        明確度 = 「最佳指派」與「正解放在別的選項的最佳指派」總分差（MIN_MARGIN）、正解圖那一欄第一名與第二名的差（MIN_GAP）、
        正解分數下限（MIN_ABS），任一不夠 → 135 停手交人，不猜。答錯 1 題（確認後視窗沒關 / 圍欄沒開）就停（136）。
  每次作答的 4 張裁切與分數存 tools/.cache/quiztower/（實機校準用，3 天自動清）。

退出碼（共用 0 / 1 / 2 / 8 / 9 / 10 見 uikit；quiztower 自己 130～139）：
  0   拿到金布伊（810 伊那多「完成」後傳回 811）
  130 不在塔內（800～811）且點追蹤也沒進塔 / 地圖讀不到
  131 走路失敗（走不到守衛下方 / 出口、換層逾時）
  132 點守衛沒有對話框，或對話按鈕沒有「猜謎答題」（不在左鈕）
  133 按「猜謎答題」後 QUIZ_WAIT_S 秒內沒出現答題視窗（畫面是已知的主畫面 / 對話框）
  134 答題視窗的選項圖讀不到（截圖失敗 / 正解候選缺靜態圖）
  135 比對不明確（第一、二名差太小 / 分數太低）→ 答題視窗維持開著，交人
  136 確認後答題視窗沒關，或出口走不過去（疑似答錯 / 圍欄沒開）→ 停
  137 810 伊那多對話失敗（按鈕不是「拿金豬」/「完成」、完成後沒回 811）
  138 對話框含不可逆關鍵字（quest.find_irreversible）→ 沒按
  139 超過 --max-min 分鐘
"""
import argparse
import itertools
import json
import os
import re
import struct
import sys
import time
import zlib
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import logpaths  # noqa: E402
import pngread  # noqa: E402
import uikit  # noqa: E402

ROOT = uikit.ROOT
sys.path.insert(0, str(ROOT / 'tools' / 'extract'))
import pet_images  # noqa: E402  imageId → 靜態圖檔（pet_images.find）

SRC = 'quiztower'
TRACK = '猜謎三兄弟'                      # 追蹤列表標題（questdefs 3003 track）
ANSWER_TABLE = ROOT / 'knowledge' / 'data' / 'tables' / 'Answer.jsonl'
ANSWER_MD = ROOT / 'knowledge' / 'quests' / 'answers.md'
STATIC_DIR = Path(pet_images.OUT) / 'static'
DUMP_DIR = uikit.CACHE / 'quiztower'
PROGRESS = logpaths.p(uikit.CACHE / 'quiztower.json')
EVENT_LOG = logpaths.p(ROOT / 'notes' / 'quest-events.log')

(EXIT_NOT_TOWER, EXIT_WALK, EXIT_GUARD, EXIT_NO_QUIZ, EXIT_NO_IMAGE, EXIT_UNSURE,
 EXIT_WRONG, EXIT_INADO, EXIT_IRREV, EXIT_TIME) = range(130, 140)
EXIT_VERIFY = uikit.EXIT_UNKNOWN_SCREEN    # 9：安全閘不符 = 當防腳本驗證

# ---- 塔的資料（knowledge：psa.py map 800～811；test_quiztower 會和 MapWarp / Npc 表核對）----
LOBBY, TOP = 811, 810
LOBBY_EXIT = (29, 13)                      # 811 → 800:14,26
TOWER = range(800, 812)
QUIZ_FLOORS = range(800, 810)              # 有守衛答題的樓層
INADO = (28, 16)                           # 810 伊那多
INADO_STAND = (28, 17)


def floor_info(m: int) -> dict:
    """800～809：偶數層守衛 29,19 / 出口 29,13 / 進場 14,26；奇數層守衛 18,19 / 出口 18,13 / 進場 32,26；上一層 = m + 1"""
    gx = 29 if m % 2 == 0 else 18
    return dict(guard=(gx, 19), stand=(gx, 20), exit=(gx, 13), entry=(14, 26) if m % 2 == 0 else (32, 26), up=m + 1)


# ---- 畫面座標（截圖座標 1440×830；10-09 手動紀錄，待實機量）----
GUARD_CLICKS = {0: [(690, 345)], 1: [(625, 325)]}   # 站在守衛正下方時點守衛身體（偶數層 / 奇數層）；不行再試 walk.npc_screen
FLOOR800_CLICKS = [(438, 318), (655, 335)]          # 800 層從進場 14,26 點地面走到 29,20 附近（maps.bin 沒 800 的通行格）
DIALOG_LEFT = (948, 461)                            # NPC 對話框左鈕（= quest.DIALOG_NEXT）
DIALOG_SPLIT_X = 1085                               # 按鈕文字中心 x < 這個 = 左鈕（右鈕 1220,461 是「再見」）
QUIZ_BOX = (360, 110, 760, 560)                     # 答題視窗整塊 OCR 範圍 x,y,w,h（標題 + 題目都在裡面；寬一點容錯，待實機量）
OPT_XS = (463, 643, 822, 1002)                      # A～D 選項中心 x
OPT_Y = 430
OPT_W, OPT_H = 150, 150                             # 選項圖裁切框（待實機量；間距 180，框不重疊）
CONFIRM = (735, 610)                                # 藍「確認」
QUIZ_CLICKS = {(x, OPT_Y) for x in OPT_XS} | {CONFIRM}   # 答題視窗內只准點這 5 個點

# ---- 時間 ----
TRACK_MOVE_S = 6.0          # 點追蹤後這麼久座標都沒變 = 巡路沒反應（noTaskNavigate）
TRACK_SETTLE_S = 60.0       # 巡路最多等多久停下
POLL_S = 0.7
GATE_WINDOW_S = 15.0        # ② 按「猜謎答題」到看到答題視窗最多隔多久
QUIZ_WAIT_S = 6.0           # 按「猜謎答題」後等答題視窗
QUIZ_CLOSE_S = 4.0          # 確認後等答題視窗消失
HUD_WAIT_S = 8.0            # 換層後等 HUD
LOAD_WAIT_S = 20.0          # 810 完成後等傳回 811
DONE_TRUST_S = 2 * 3600     # 進度檔「這層答過」在這段時間內才採信
MAX_MIN = 45

# ---- 比對參數（合成測試校準；實機要再看 tools/.cache/quiztower/ 的分數）----
GRID = 12
BG_TOL = 40                 # 與底色差（最大通道）超過這個 = 前景
FRAME_FILL = 0.85           # 邊緣整排前景比例 > 這個 = 框線，剝掉
MIN_FG_PX = 60              # 前景像素少於這個 = 這格沒圖
W_SHAPE, W_COLOR, W_HIST, W_ASPECT = 0.30, 0.30, 0.30, 0.10
MIN_MARGIN = 0.04           # 最佳指派 vs 正解放別格的最佳指派
MIN_GAP = 0.03              # 正解圖那一欄：第一名 - 第二名
MIN_ABS = 0.55              # 正解分數下限

LAST: dict = {}


# ================================================================ 題庫
def _norm_q(t: str) -> str:
    """題目正規化：去空白、引號、問號、全形半形標點"""
    return re.sub(r'[\s“”"\'「」『』？?！!。．.,，:：]+', '', str(t or ''))


NAME_RE = re.compile(r'(?:叫做|叫|是)[“"「『]?([^“”"「」『』？?]+?)[”"」』]?[？?]?$')


def name_of_title(title: str) -> str | None:
    """「以下哪只寵物的名字叫做“諾克斯”」→ 諾克斯；不是「哪只…叫 / 是 X」句型 → None（系別 / 屬於 / 不是 題不算）"""
    t = title.strip()
    if not re.search(r'哪[只隻個]', t) or re.search(r'不是|屬於|不屬於', t):
        return None
    m = NAME_RE.search(t)
    return m.group(1).strip() if m else None


def _image_names(img: int) -> set:
    """imageId → 用這張圖的所有怪物繁中名（pet_images 的 index.tsv）"""
    rows = pet_images.find(str(img)) or []
    return {c[1] for c in rows if c[4] == str(img)}


def static_path(img: int) -> Path | None:
    for c in pet_images.find(str(img)) or []:
        if c[4] == str(img) and c[6]:
            return STATIC_DIR / c[6]
    return None


_BANK: dict = {}


def build_bank(md: Path = ANSWER_MD, table: Path = ANSWER_TABLE) -> dict:
    """名字題題庫：名字 → {'correct': imageId, 'cands': [imageId…], 'titles': [題目…], 'ids': [Answer ID…]}。
    同名多筆（例：斑尼迪克 13 / 76 / 80 / 110 選項組不同）合併候選；正解 = 選項中名字剛好是 X 的那張（要剛好一張，否則不收）"""
    key = (str(md), str(table))
    if key in _BANK:
        return _BANK[key]
    titles = {int(m.group(1)): m.group(2) for m in re.finditer(r'^\| (\d+) \| (.*?) \|$', md.read_text(encoding='utf-8'), re.M)}
    bank: dict = {}
    for ln in table.read_text(encoding='utf-8').splitlines():
        if not ln.strip():
            continue
        r = json.loads(ln)
        title = titles.get(r['ID'])
        name = name_of_title(title or '')
        if not name:
            continue
        opts = [a['img'] for a in r.get('answerInfo', [])]
        hit = [i for i in opts if name in _image_names(i)]
        if len(hit) != 1:
            continue
        e = bank.setdefault(name, {'correct': hit[0], 'cands': [], 'titles': [], 'ids': []})
        if e['correct'] != hit[0]:
            e['conflict'] = True
        for i in opts:
            if i not in e['cands']:
                e['cands'].append(i)
        if title not in e['titles']:
            e['titles'].append(title)
        e['ids'].append(r['ID'])
    bank = {k: v for k, v in bank.items() if not v.get('conflict')}
    _BANK[key] = bank
    return bank


def parse_question(texts, bank: dict) -> tuple:
    """OCR 行 → (名字, 題庫項) 或 (None, 理由)。要求：有「哪只 / 哪隻」、名字整段出現在文字裡、文字像題庫裡該名字的某一題全文
    （題目全文相似度 ≥ 0.6，擋掉「不是 X」「屬於 X」）；多個名字都出現取最長（加比 / 加比奧）"""
    flat = _norm_q(''.join(texts))
    if not re.search(r'哪[只隻]', flat):
        return None, '文字裡沒有「哪只 / 哪隻」題目句型'
    if re.search(r'不是|屬於', flat):
        return None, '題目是「不是 / 屬於」類（不是名字題）'
    hits = [n for n in bank if n in flat]
    if not hits:
        return None, '題目裡的名字不在題庫名字題裡'
    n = max(hits, key=len)
    if sum(1 for h in hits if len(h) == len(n)) > 1:
        return None, f'題目同時含多個同長度名字 {hits}'
    import difflib
    best = 0.0
    for t in bank[n]['titles']:
        tn = _norm_q(t)
        i = flat.find(n)
        # 只拿題目附近一段比（OCR 範圍很大，會讀到選項 / 按鈕字）
        seg = flat[max(0, i - len(tn)):i + len(n) + 2]
        best = max(best, difflib.SequenceMatcher(None, tn, seg).ratio(), 1.0 if tn in flat else 0.0)
    if best < 0.6:
        return None, f'題目句型對不上題庫（相似度 {best:.2f}）'
    return n, bank[n]


def title_ok(texts) -> bool:
    flat = _norm_q(''.join(texts))
    return ('答題' in flat or '答题' in flat) and ('知識' in flat or '知识' in flat)


def gate(map_id, quiz_clicked_at, now: float, texts, bank: dict) -> tuple:
    """答題安全閘（純函式）：→ (True, 名字) 或 (False, 不符理由)。四條件見檔頭"""
    if map_id is None or not (800 <= map_id <= 810):
        return False, f'① 地圖 {map_id} 不在 800～810'
    if quiz_clicked_at is None or not (0 <= now - quiz_clicked_at <= GATE_WINDOW_S):
        return False, '② 不是剛按過守衛的「猜謎答題」（答題視窗不是自己觸發的）'
    if not title_ok(texts):
        return False, '③ 標題不是「知識答題」'
    name, e = parse_question(texts, bank)
    if not name:
        return False, f'④ {e}'
    return True, name


# ================================================================ 影像
class Img:
    """w×h 像素，px[y*w+x] = (r, g, b, a)"""
    __slots__ = ('w', 'h', 'px')

    def __init__(self, w: int, h: int, px: list):
        self.w, self.h, self.px = w, h, px

    def at(self, x: int, y: int):
        return self.px[y * self.w + x]

    def crop(self, x0: int, y0: int, w: int, h: int) -> 'Img':
        x0, y0 = max(0, x0), max(0, y0)
        w, h = min(w, self.w - x0), min(h, self.h - y0)
        return Img(w, h, [self.px[(y0 + j) * self.w + x0 + i] for j in range(h) for i in range(w)])


def load_png(path) -> Img:
    w, h, bpp, rows = pngread.decode(Path(path).read_bytes())
    px = []
    for r in rows:
        if bpp == 4:
            px.extend(tuple(r[i:i + 4]) for i in range(0, w * 4, 4))
        else:
            px.extend((r[i], r[i + 1], r[i + 2], 255) for i in range(0, w * 3, 3))
    return Img(w, h, px)


def write_png(path, img: Img) -> None:
    """RGB PNG（除錯用：答題選項裁切）"""
    raw = b''.join(b'\x00' + bytes(v for p in img.px[y * img.w:(y + 1) * img.w] for v in p[:3]) for y in range(img.h))

    def chunk(t, d):
        return struct.pack('>I', len(d)) + t + d + struct.pack('>I', zlib.crc32(t + d) & 0xffffffff)
    Path(path).write_bytes(b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', img.w, img.h, 8, 2, 0, 0, 0))
                           + chunk(b'IDAT', zlib.compress(raw, 6)) + chunk(b'IEND', b''))


def _median(vals):
    s = sorted(vals)
    return s[len(s) // 2]


def mask_static(img: Img) -> list:
    return [p[3] >= 128 for p in img.px]


def mask_screen(img: Img) -> list:
    """畫面裁切的前景：外圈 3 px 中位數當底色，差 > BG_TOL = 前景"""
    ring = [img.at(x, y) for y in range(img.h) for x in range(img.w)
            if x < 3 or y < 3 or x >= img.w - 3 or y >= img.h - 3]
    bg = tuple(_median([p[c] for p in ring]) for c in range(3))
    return [max(abs(p[0] - bg[0]), abs(p[1] - bg[1]), abs(p[2] - bg[2])) > BG_TOL for p in img.px]


def fg_box(img: Img, mask: list, strip_frame: bool = False):
    """前景外框 (x0, y0, x1, y1)（含）；strip_frame = 先剝掉邊緣整排幾乎全滿的框線列 / 欄。前景太少 → None"""
    w, h = img.w, img.h
    rows = [sum(mask[y * w:(y + 1) * w]) for y in range(h)]
    cols = [sum(mask[y * w + x] for y in range(h)) for x in range(w)]
    y0, y1, x0, x1 = 0, h - 1, 0, w - 1
    if strip_frame:
        while y0 < y1 and (rows[y0] > FRAME_FILL * w or rows[y0] == 0):
            y0 += 1
        while y1 > y0 and (rows[y1] > FRAME_FILL * w or rows[y1] == 0):
            y1 -= 1
        while x0 < x1 and (cols[x0] > FRAME_FILL * h or cols[x0] == 0):
            x0 += 1
        while x1 > x0 and (cols[x1] > FRAME_FILL * h or cols[x1] == 0):
            x1 -= 1
        # 框線剝掉後重算（框線的直欄會讓每列都有 2 點前景）
        rows = [sum(mask[y * w + x] for x in range(x0, x1 + 1)) for y in range(h)]
        cols = [sum(mask[y * w + x] for y in range(y0, y1 + 1)) for x in range(w)]
    ys = [y for y in range(y0, y1 + 1) if rows[y] >= 2]
    xs = [x for x in range(x0, x1 + 1) if cols[x] >= 2]
    if not ys or not xs:
        return None
    bx0, bx1, by0, by1 = xs[0], xs[-1], ys[0], ys[-1]
    n = sum(mask[y * w + x] for y in range(by0, by1 + 1) for x in range(bx0, bx1 + 1))
    return (bx0, by0, bx1, by1) if n >= MIN_FG_PX else None


def features(img: Img, mask: list, strip_frame: bool = False) -> dict | None:
    """前景外框縮成 GRID×GRID：每格前景比例 + 平均色；4×4×4 直方圖；長寬比"""
    b = fg_box(img, mask, strip_frame)
    if not b:
        return None
    x0, y0, x1, y1 = b
    bw, bh = x1 - x0 + 1, y1 - y0 + 1
    n = [0] * (GRID * GRID)
    tot = [0] * (GRID * GRID)
    s = [[0, 0, 0] for _ in range(GRID * GRID)]
    hist = [0] * 64
    for y in range(y0, y1 + 1):
        gy = (y - y0) * GRID // bh
        for x in range(x0, x1 + 1):
            k = gy * GRID + (x - x0) * GRID // bw
            tot[k] += 1
            if mask[y * img.w + x]:
                p = img.px[y * img.w + x]
                n[k] += 1
                s[k][0] += p[0]
                s[k][1] += p[1]
                s[k][2] += p[2]
                hist[(p[0] >> 6) * 16 + (p[1] >> 6) * 4 + (p[2] >> 6)] += 1
    m = sum(hist) or 1
    return dict(frac=[n[k] / tot[k] if tot[k] else 0.0 for k in range(GRID * GRID)],
                col=[tuple(c / n[k] for c in s[k]) if n[k] else None for k in range(GRID * GRID)],
                hist=[v / m for v in hist], aspect=bw / bh, n=sum(n))


def similarity(a: dict, b: dict) -> float:
    shape = 1 - sum(abs(x - y) for x, y in zip(a['frac'], b['frac'])) / len(a['frac'])
    d = [sum(abs(p - q) for p, q in zip(ca, cb)) / 765 for ca, cb, fa, fb in zip(a['col'], b['col'], a['frac'], b['frac'])
         if ca and cb and fa >= 0.3 and fb >= 0.3]
    color = 1 - (sum(d) / len(d)) * 2 if d else 0.0
    hist = sum(min(x, y) for x, y in zip(a['hist'], b['hist']))
    import math
    aspect = 1 - min(1.0, abs(math.log(a['aspect'] / b['aspect'])))
    return W_SHAPE * shape + W_COLOR * max(0.0, color) + W_HIST * hist + W_ASPECT * aspect


def decide(S: list, cands: list, correct) -> dict:
    """S[選項][候選] 分數矩陣 → 最佳一對一指派，正解圖被指派到的選項 = 答案。
    回 {'ok', 'choice'（0～3 或 None）, 'margin', 'gap', 'score', 'reason'}"""
    no, nc = len(S), len(cands)
    out = dict(ok=False, choice=None, margin=0.0, gap=0.0, score=0.0, reason='')
    if correct not in cands or nc < no:
        out['reason'] = f'候選圖不足（{nc} 張，選項 {no} 個）或正解不在候選'
        return out
    ci = cands.index(correct)
    best, best_p = -1.0, None
    alt = {}                                   # 正解指派到選項 o（或 None = 沒指派）時的最佳總分
    for perm in itertools.permutations(range(nc), no):
        t = sum(S[o][perm[o]] for o in range(no))
        where = perm.index(ci) if ci in perm else None
        if t > alt.get(where, -1.0):
            alt[where] = t
        if t > best:
            best, best_p = t, perm
    choice = best_p.index(ci) if ci in best_p else None
    if choice is None:
        out['reason'] = '最佳指派沒有把正解圖配給任何選項'
        return out
    other = max((v for k, v in alt.items() if k != choice), default=-1.0)
    colv = sorted((S[o][ci] for o in range(no)), reverse=True)
    out.update(choice=choice, margin=round(best - other, 4), score=round(S[choice][ci], 4),
               gap=round(S[choice][ci] - max(S[o][ci] for o in range(no) if o != choice), 4))
    if S[choice][ci] != colv[0]:
        out['reason'] = '指派結果和正解欄第一名不同'
    elif out['margin'] < MIN_MARGIN:
        out['reason'] = f'指派差 {out["margin"]:.3f} < {MIN_MARGIN}'
    elif out['gap'] < MIN_GAP:
        out['reason'] = f'正解欄第一、二名差 {out["gap"]:.3f} < {MIN_GAP}'
    elif out['score'] < MIN_ABS:
        out['reason'] = f'正解分數 {out["score"]:.3f} < {MIN_ABS}'
    else:
        out['ok'] = True
    return out


_FEAT: dict = {}


def static_feat(img_id: int):
    if img_id not in _FEAT:
        p = static_path(img_id)
        if not p or not p.exists():
            _FEAT[img_id] = None
        else:
            im = load_png(p)
            _FEAT[img_id] = features(im, mask_static(im))
    return _FEAT[img_id]


def option_crops(shot: Img) -> list:
    return [shot.crop(x - OPT_W // 2, OPT_Y - OPT_H // 2, OPT_W, OPT_H) for x in OPT_XS]


def answer_from_image(shot: Img, name: str, bank: dict, dump: str | None = None) -> dict:
    """整張截圖 + 題目名字 → decide 結果（另加 'S'、'cands'、'opt_feat_ok'）；dump = 裁切存檔前綴"""
    e = bank[name]
    cands = list(e['cands'])
    cf = {c: static_feat(c) for c in cands}
    if cf.get(e['correct']) is None:
        return dict(ok=False, choice=None, reason=f'正解圖 {e["correct"]} 沒有靜態圖（先跑 tools/extract/pet_images.py）', cands=cands)
    cands = [c for c in cands if cf[c] is not None]
    crops = option_crops(shot)
    of = [features(c, mask_screen(c), strip_frame=True) for c in crops]
    if dump:
        DUMP_DIR.mkdir(parents=True, exist_ok=True)
        uikit.cleanup_old_shots(folder=DUMP_DIR)
        for i, c in enumerate(crops):
            write_png(DUMP_DIR / f'{dump}-opt{"ABCD"[i]}.png', c)
    if any(f is None for f in of):
        return dict(ok=False, choice=None, reason=f'選項 {[ "ABCD"[i] for i, f in enumerate(of) if f is None]} 裁不到圖（框位置不對？）', cands=cands)
    S = [[round(similarity(f, cf[c]), 4) for c in cands] for f in of]
    r = decide(S, cands, e['correct'])
    r.update(S=S, cands=cands, correct=e['correct'])
    if dump:
        (DUMP_DIR / f'{dump}-scores.json').write_text(json.dumps(dict(name=name, **r), ensure_ascii=False), encoding='utf-8')
    return r


# ================================================================ 真實工具（測試換成 Fake，介面相同）
class Tools:
    def event(self, msg: str, shot: str | None = None) -> None:
        line = f'{time.strftime("%Y-%m-%d %H:%M:%S")} [quiztower] {msg}' + (f' [{shot}]' if shot else '')
        print(line, flush=True)
        try:
            EVENT_LOG.parent.mkdir(exist_ok=True)
            with open(EVENT_LOG, 'a', encoding='utf-8') as f:
                f.write(line + '\n')
        except OSError:
            pass

    def now(self) -> float:
        return time.time()

    def sleep(self, s: float) -> None:
        time.sleep(s)

    def preflight(self) -> int:
        return uikit.preflight(SRC, fast=True)

    def pos(self):
        import walk
        return walk.wait_pos(3, gap=0.4)

    def screen_state(self) -> str:
        return uikit.screen().get('state')

    def hud_ok(self) -> bool:
        return uikit.hud_visible()

    def track(self) -> bool | None:
        import quest
        return quest.track_task(TRACK)

    def walk_to(self, m, x, y, exit_map=None, auto=True):
        import walk
        return walk.walk_to(m, x, y, exit_map=exit_map, auto=auto)

    def has_grid(self, m, a, b) -> bool:
        import walk
        return walk.has_grid(m, a, b)

    def ground_clicks(self, pts) -> None:
        import walk
        walk.gui('seq', walk.PRIMER + '; ' + '; '.join(f'click {x} {y}; waitstill {walk.WAITSTILL_MS}' for x, y in pts),
                 note='quiztower 800 層點地面')

    def npc_xy(self, npc, at):
        import walk
        return walk.npc_screen(npc, at)

    def click(self, x: int, y: int, note: str) -> None:
        import walk
        walk.gui('seq', f'click {x} {y}; wait 300', note=note)

    def primer(self) -> None:
        import walk
        walk.prime()

    def dialog_buttons(self) -> list:
        """對話框兩顆鈕 OCR → [{'text', 'x', 'y'}]"""
        import quest
        r = quest.ps_json('ocr.ps1', *quest.DIALOG_BTN_BOX, '-Zooms', '2,3', '-Dark', quest.DIALOG_BTN_DARK)
        return [ln for ln in r.get('lines', []) if ln.get('text')]

    def dialog_body(self) -> list:
        import quest
        return quest.read_dialog_texts()['body']

    def quiz_texts(self) -> list:
        """答題視窗整塊 OCR（深字 + 不二值化各一次，合併）"""
        import quest
        out = []
        for opt in (('-Dark', 150), ('-Dark', 0)):
            r = quest.ps_json('ocr.ps1', *QUIZ_BOX, '-Zooms', '2,3', *opt)
            out += [ln['text'] for ln in r.get('lines', []) if ln.get('text')]
        return out

    def quiz_click(self, x: int, y: int, note: str) -> bool:
        """答題視窗內點擊：只准 QUIZ_CLICKS；經 uikit.safe_click（視窗特徵 = 標題 OCR 還在）"""
        panel = uikit.Panel('QUIZ', None, None, None, is_open_fn=lambda: title_ok(self.quiz_texts()))
        return uikit.safe_click(x, y, panel, note=note, wait_ms=300)

    def shot(self) -> Img | None:
        import winenv
        p = uikit.CACHE / 'quiztower-shot.png'
        try:
            uikit.gui('shot', winenv.to_windows(p))
            return load_png(p)
        except Exception:
            return None

    def snap(self, tag: str):
        return uikit.snap(f'quiztower-{tag}')

    def errlog(self, msg: str) -> None:
        try:
            import errlog
            errlog.add(msg, source=SRC)
        except Exception:
            pass


# ================================================================ 進度
def load_progress() -> dict:
    try:
        return json.loads(PROGRESS.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return {}


def save_progress(d: dict) -> None:
    try:
        PROGRESS.parent.mkdir(parents=True, exist_ok=True)
        PROGRESS.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding='utf-8')
    except OSError:
        pass


# ================================================================ 流程
class Runner:
    def __init__(self, T, opts: dict):
        self.T, self.o = T, opts
        self.bank = opts.get('bank') or build_bank()
        self.track_dead = not opts.get('use_track', True)
        self.tracked: set = set()            # 這次執行已試過點追蹤的地圖
        self.quiz_clicked_at = None
        self.prog = load_progress()
        self.prog.setdefault('floors', {})
        self.info: dict = {'answers': []}

    # ---- 共用 ----
    def fail(self, rc: int, msg: str, snap: bool = True) -> int:
        shot = self.T.snap(f'rc{rc}') if snap else None
        self.T.event(f'停手 rc={rc}：{msg}', shot)
        self.T.errlog(f'quiztower rc={rc}：{msg}')
        self.info.update(rc=rc, msg=msg)
        return rc

    def answered(self, m: int) -> bool:
        f = self.prog['floors'].get(str(m))
        return bool(f) and 'ts' in f and self.T.now() - f['ts'] < DONE_TRUST_S

    def mark_answered(self, m: int, **kw) -> None:
        self.prog['floors'][str(m)] = dict(ts=self.T.now(), **kw)
        save_progress(self.prog)

    def wait_state(self, want: tuple, timeout: float) -> str | None:
        t0 = self.T.now()
        while True:
            st = self.T.screen_state()
            if st in want:
                return st
            if self.T.now() - t0 >= timeout:
                return st
            self.T.sleep(POLL_S)

    def wait_map(self, m: int, timeout: float = HUD_WAIT_S):
        """等座標進到地圖 m（換層 Loading / HUD 載入）"""
        t0 = self.T.now()
        p = None
        while self.T.now() - t0 < timeout:
            p = self.T.pos()
            if p and p[0] == m and self.T.hud_ok():
                return p
            self.T.sleep(POLL_S)
        return p if p and p[0] == m else None

    # ---- 巡路 ----
    def try_track(self, m: int, start) -> bool:
        """點追蹤卡；TRACK_MOVE_S 秒座標沒變 → 巡路沒反應（之後整次執行都不再試），回 False；有動 → 等停下回 True"""
        if self.track_dead or m in self.tracked:
            return False
        self.tracked.add(m)
        r = self.T.track()
        if not r:
            self.T.event(f'{m}：追蹤列表沒點到「{TRACK}」（{r}）→ 改走路')
            return False
        t0 = self.T.now()
        last, moved = start, False
        while self.T.now() - t0 < TRACK_SETTLE_S:
            self.T.sleep(POLL_S)
            st = self.T.screen_state()
            if st == 'dialog':
                return True
            p = self.T.pos()
            if p and p != last:
                moved, last = True, p
                t_last = self.T.now()
                continue
            if not moved and self.T.now() - t0 >= TRACK_MOVE_S:
                self.track_dead = True
                self.T.event(f'{m}：點追蹤 {TRACK_MOVE_S:.0f} 秒座標沒變（noTaskNavigate）→ 本次之後都改 walk.py')
                return False
            if moved and st != 'walking' and self.T.now() - t_last >= 2 * POLL_S:
                self.T.event(f'{m}：追蹤巡路停在 {last}')
                return True
        return moved

    def walk(self, m: int, xy, exit_map=None) -> bool:
        """walk.py 走到 m 的 xy；800 層沒通行格且在進場點 → 先照紀錄點地面。走到（或換到 exit_map）回 True"""
        for k in range(2):
            try:
                p = self.T.pos()
                if (m == 800 and exit_map is None and p and (p[1], p[2]) == floor_info(800)['entry']
                        and not self.T.has_grid(800, floor_info(800)['entry'], xy)):
                    self.T.event('800 層沒有通行格 → 照 10-09 紀錄點地面 ' + ' '.join(f'{a},{b}' for a, b in FLOOR800_CLICKS))
                    self.T.ground_clicks(FLOOR800_CLICKS)
                p = self.T.walk_to(m, xy[0], xy[1], exit_map=exit_map)
            except RuntimeError as e:
                self.T.event(f'walk.py {m}:{xy} 第 {k + 1} 次失敗：{e}')
                self.T.sleep(1.0)
                continue
            if p and ((exit_map is not None and p[0] == exit_map) or (exit_map is None and p[0] == m and (p[1], p[2]) == tuple(xy))):
                return True
            self.T.event(f'walk.py {m}:{xy} 走完在 {p}')
        return False

    # ---- 對話框 ----
    def buttons(self):
        return self.T.dialog_buttons()

    def left_button_has(self, lines, word: str) -> bool:
        return any(word in re.sub(r'\s+', '', ln['text']) and ln.get('x', 0) < DIALOG_SPLIT_X for ln in lines)

    def check_irrev(self, lines) -> int:
        import quest                            # 不可逆關鍵字表與判斷沿用 quest.py（轉生 / 封印 / 刪除 / 丟棄）
        hits = quest.find_irreversible([ln['text'] for ln in lines] + list(self.T.dialog_body()))
        if hits:
            return self.fail(EXIT_IRREV, f'對話框含不可逆關鍵字 {hits}，沒按')
        return 0

    # ---- 樓層 ----
    def guard_dialog(self, m: int) -> int:
        """站在守衛正下方 → 點守衛 → 對話框（不同點擊位置輪流試）"""
        fi = floor_info(m)
        p = self.T.pos()
        at = (p[1], p[2]) if p and p[0] == m else fi['stand']
        tries = list(GUARD_CLICKS[m % 2]) if at == fi['stand'] else []
        calc = self.T.npc_xy(fi['guard'], at)
        if calc not in tries:
            tries.append(calc)
        self.T.primer()
        for x, y in tries:
            self.T.click(x, y, f'quiztower {m} 點守衛 {fi["guard"]}')
            if self.wait_state(('dialog',), 3.0) == 'dialog':
                return 0
        return self.fail(EXIT_GUARD, f'{m}：點守衛 {tries} 都沒有對話框')

    def quiz_flow(self, m: int) -> int:
        """對話框已開（守衛）→ 驗按鈕「猜謎答題」→ 按 → 安全閘 → 作答 → 確認 → 視窗消失"""
        lines = self.buttons()
        if not self.left_button_has(lines, '猜謎答題'):
            return self.fail(EXIT_GUARD, f'{m}：守衛對話框左鈕不是「猜謎答題」（讀到 {[ln["text"] for ln in lines]}）')
        rc = self.check_irrev(lines)
        if rc:
            return rc
        self.T.click(*DIALOG_LEFT, f'quiztower {m} 守衛對話「猜謎答題」')
        self.quiz_clicked_at = self.T.now()
        texts = []
        while self.T.now() - self.quiz_clicked_at < QUIZ_WAIT_S:
            self.T.sleep(POLL_S)
            texts = self.T.quiz_texts()
            if title_ok(texts):
                break
        if not title_ok(texts) and self.T.screen_state() in ('idle', 'dialog', 'walking'):
            return self.fail(EXIT_NO_QUIZ, f'{m}：按「猜謎答題」後 {QUIZ_WAIT_S:.0f} 秒沒出現答題視窗')
        ok, why = gate(m, self.quiz_clicked_at, self.T.now(), texts, self.bank)   # ① 用點守衛前讀的地圖（答題視窗蓋著時 HUD 可能讀不到）
        if not ok:
            return self.fail(EXIT_VERIFY, f'{m}：答題安全閘不符（{why}）→ 當防腳本驗證，停手不點，請人處理（鐵則 5）；讀到 {texts[:6]}')
        name = why
        shot = self.T.shot()
        if shot is None:
            return self.fail(EXIT_NO_IMAGE, f'{m}：答題截圖失敗')
        tag = f'{time.strftime("%H%M%S")}-{m}'
        r = answer_from_image(shot, name, self.bank, dump=None if self.o.get('no_dump') else tag)
        info = dict(floor=m, name=name, choice=r.get('choice'), ok=r.get('ok'), margin=r.get('margin'), gap=r.get('gap'),
                    score=r.get('score'), reason=r.get('reason'))
        self.info['answers'].append(info)
        if r.get('choice') is None and 'S' not in r:
            return self.fail(EXIT_NO_IMAGE, f'{m}：「{name}」{r.get("reason")}')
        if not r['ok']:
            return self.fail(EXIT_UNSURE, f'{m}：「{name}」比對不明確（{r["reason"]}；分數 {r.get("S")}）→ 答題視窗留著交人')
        c = r['choice']
        self.T.event(f'{m}：題目「{name}」→ 選 {"ABCD"[c]}（正解圖 {r["correct"]}，分數 {r["score"]}、指派差 {r["margin"]}、欄差 {r["gap"]}）')
        for xy, what in (((OPT_XS[c], OPT_Y), f'選項 {"ABCD"[c]}'), (CONFIRM, '確認')):
            if xy not in QUIZ_CLICKS:
                raise uikit.ForbiddenClick(f'答題視窗只准點 {sorted(QUIZ_CLICKS)}，要點 {xy}')
            if not self.T.quiz_click(xy[0], xy[1], f'quiztower {m} {name} {what}'):
                return self.fail(EXIT_WRONG, f'{m}：點{what}前答題視窗不見了')
        t0 = self.T.now()
        while self.T.now() - t0 < QUIZ_CLOSE_S:
            self.T.sleep(POLL_S)
            if not title_ok(self.T.quiz_texts()):
                self.mark_answered(m, name=name, choice='ABCD'[c])
                return 0
        return self.fail(EXIT_WRONG, f'{m}：確認後答題視窗沒關（疑似答錯，後果未知）→ 停')

    def do_floor(self, m: int, p) -> int:
        fi = floor_info(m)
        past_guard = p[2] < fi['guard'][1]       # 已經在圍欄裡（守衛那排以北）= 這層答過
        if not (past_guard or self.answered(m)):
            if self.try_track(m, p):
                return 0                           # 巡路有動：回主迴圈重新看位置 / 對話框
            if (p[1], p[2]) != fi['stand']:
                if not self.walk(m, fi['stand']):
                    return self.fail(EXIT_WALK, f'{m}：走不到守衛正下方 {fi["stand"]}')
            rc = self.guard_dialog(m)
            if rc:
                return rc
            rc = self.quiz_flow(m)
            if rc:
                return rc
        if not self.walk(m, fi['exit'], exit_map=fi['up']):
            p2 = self.T.pos()
            if p2 and p2[0] == m and p2[2] >= fi['guard'][1]:
                if self.answered(m) and not past_guard:
                    self.T.event(f'{m}：進度檔記答過但圍欄走不過 → 清掉這層紀錄，重做守衛')
                    self.prog['floors'].pop(str(m), None)
                    save_progress(self.prog)
                    return 0
                return self.fail(EXIT_WRONG, f'{m}：走不過圍欄（在 {p2}）→ 疑似沒答對 / 圍欄沒開')
            return self.fail(EXIT_WALK, f'{m}：走不到出口 {fi["exit"]}（在 {p2}）')
        if not self.wait_map(fi['up']):
            return self.fail(EXIT_WALK, f'{m}：換到 {fi["up"]} 後 {HUD_WAIT_S:.0f} 秒 HUD / 座標沒好')
        self.T.event(f'{m} → {fi["up"]} 完成')
        return 0

    def do_top(self, p) -> int:
        """810：伊那多「拿金豬」→「完成」→ 傳回 811"""
        if self.T.screen_state() != 'dialog':
            if not self.try_track(TOP, p) or self.T.screen_state() != 'dialog':
                p = self.T.pos()
                if p and (p[1], p[2]) != INADO_STAND and not self.walk(TOP, INADO_STAND):
                    return self.fail(EXIT_WALK, f'810：走不到伊那多前 {INADO_STAND}')
                self.T.primer()
                x, y = self.T.npc_xy(INADO, INADO_STAND)
                self.T.click(x, y, 'quiztower 810 點伊那多')
                if self.wait_state(('dialog',), 3.0) != 'dialog':
                    return self.fail(EXIT_INADO, '810：點伊那多沒有對話框')
        for word in ('拿金豬', '完成'):
            if self.wait_state(('dialog',), 3.0) != 'dialog':
                return self.fail(EXIT_INADO, f'810：等不到「{word}」的對話框')
            lines = self.buttons()
            if not self.left_button_has(lines, word):
                return self.fail(EXIT_INADO, f'810：對話框左鈕不是「{word}」（讀到 {[ln["text"] for ln in lines]}）')
            rc = self.check_irrev(lines)
            if rc:
                return rc
            self.T.click(*DIALOG_LEFT, f'quiztower 810 伊那多「{word}」')
            self.T.sleep(0.5)
        if not self.wait_map(LOBBY, LOAD_WAIT_S):
            return self.fail(EXIT_INADO, f'810：按「完成」後 {LOAD_WAIT_S:.0f} 秒沒回 811')
        self.T.event('810 伊那多「完成」→ 回到 811（應獲得寵物 金布伊；寵物欄請另行確認）')
        self.prog['done_ts'] = self.T.now()
        self.prog['floors'] = {}
        save_progress(self.prog)
        return 0

    def dialog_now(self, p) -> int | None:
        """主迴圈開頭就是對話框（巡路自動開的）：守衛「猜謎答題」/ 伊那多「拿金豬」才接手；其他 → 132 停"""
        lines = self.buttons()
        if p and p[0] in QUIZ_FLOORS and self.left_button_has(lines, '猜謎答題'):
            return self.quiz_flow(p[0]) or None
        if p and p[0] == TOP and self.left_button_has(lines, '拿金豬'):
            return self.do_top(p)
        return self.fail(EXIT_GUARD, f'開著不認得的對話框（{p}，按鈕 {[ln["text"] for ln in lines]}），沒按')

    def run(self) -> int:
        T = self.T
        t0 = T.now()
        rc = T.preflight()
        if rc:
            return self.fail(rc, f'preflight 失敗 rc={rc}', snap=False)
        for _ in range(60):
            if T.now() - t0 > self.o.get('max_min', MAX_MIN) * 60:
                return self.fail(EXIT_TIME, f'超過 {self.o.get("max_min", MAX_MIN)} 分鐘')
            if T.screen_state() == 'battle':
                if self.wait_state(('idle', 'dialog', 'walking'), 60) == 'battle':
                    return self.fail(EXIT_WALK, '戰鬥 60 秒沒結束')
            p = T.pos()
            if not p:
                return self.fail(EXIT_NOT_TOWER, '讀不到座標')
            m = p[0]
            if T.screen_state() == 'dialog':
                rc = self.dialog_now(p)
                if rc is not None:                 # 失敗，或 810 拿完金豬（0）
                    return rc
                continue
            rc = T.preflight()
            if rc:
                return self.fail(rc, f'{m}：preflight 失敗 rc={rc}')
            if m == LOBBY:
                if not self.walk(LOBBY, LOBBY_EXIT, exit_map=800) or not self.wait_map(800):
                    return self.fail(EXIT_WALK, f'811 走不到出口 {LOBBY_EXIT}')
                T.event('811 → 800')
            elif m in QUIZ_FLOORS:
                rc = self.do_floor(m, p)
                if rc:
                    return rc
            elif m == TOP:
                return self.do_top(p)
            else:
                if self.try_track(m, p):
                    p2 = T.pos()
                    if p2 and p2[0] in TOWER:
                        continue
                return self.fail(EXIT_NOT_TOWER, f'目前在 {p}，不在猜謎三兄弟的家（800～811），點追蹤也沒進塔；先用 questrun 接取（會傳到 811）')
        return self.fail(EXIT_TIME, '主迴圈 60 輪仍未完成')


def plan_lines(at: int = LOBBY) -> list:
    """--dry-run：從 at 開始每層要做的事（不碰遊戲）"""
    out = [f'起點 {at}；巡路：每層先點追蹤「{TRACK}」，{TRACK_MOVE_S:.0f} 秒座標沒變 → 本次改 walk.py']
    m = at
    if m == LOBBY:
        out.append(f'811：walk.py 走到出口 {LOBBY_EXIT} → 800')
        m = 800
    while m in QUIZ_FLOORS:
        fi = floor_info(m)
        extra = '（maps.bin 沒通行格：從進場點照紀錄點地面 ' + ' '.join(f'{a},{b}' for a, b in FLOOR800_CLICKS) + '）' if m == 800 else ''
        out.append(f'{m}：到守衛正下方 {fi["stand"]}{extra} → 點守衛 {fi["guard"]}（{GUARD_CLICKS[m % 2]}）→「猜謎答題」→ 安全閘 → 比對作答 → 確認 → 出口 {fi["exit"]} → {fi["up"]}')
        m += 1
    out.append(f'810：伊那多 {INADO}（站 {INADO_STAND}）→「拿金豬」→「完成」→ 傳回 811 = 拿到金布伊')
    out.append('退出碼：0 完成 9 安全閘不符 130 不在塔 131 走路 132 守衛對話 133 沒答題視窗 134 選項圖讀不到 135 比對不明確 136 疑似答錯 137 伊那多 138 不可逆 139 時間')
    return out


def run(dry_run: bool = False, use_track: bool = True, at: int = LOBBY, max_min: float = MAX_MIN, tools=None, no_dump: bool = False) -> int:
    global LAST
    if dry_run:
        for ln in plan_lines(at):
            print(ln)
        LAST = {'dry_run': True}
        return 0
    r = Runner(tools or Tools(), dict(use_track=use_track, max_min=max_min, no_dump=no_dump))
    rc = r.run()
    r.info.setdefault('rc', rc)
    LAST = r.info
    print(json.dumps(dict(rc=rc, answers=r.info['answers']), ensure_ascii=False))
    return rc


# ================================================================ CLI
def cmd_bank(key: str = '') -> int:
    bank = build_bank()
    for n, e in sorted(bank.items(), key=lambda kv: min(kv[1]['ids'])):
        if key and key not in n:
            continue
        p = static_path(e['correct'])
        print(f'{n}：正解 {e["correct"]}（{p.name if p else "無靜態圖"}）候選 {e["cands"]} Answer {e["ids"][:5]}{"…" if len(e["ids"]) > 5 else ""}')
        for t in e['titles']:
            print(f'    {t}')
    return 0


def cmd_match(path: str, question: str, dump: bool) -> int:
    bank = build_bank()
    name, e = parse_question([question], bank)
    if not name:
        print(f'題目對不上題庫：{e}')
        return EXIT_VERIFY
    r = answer_from_image(load_png(path), name, bank, dump=f'match-{time.strftime("%H%M%S")}' if dump else None)
    print(json.dumps(dict(name=name, **r), ensure_ascii=False))
    return 0 if r.get('ok') else EXIT_UNSURE


def cmd_status() -> int:
    T = Tools()
    p = T.pos()
    if not p:
        print('讀不到座標')
        return EXIT_NOT_TOWER
    prog = load_progress()
    m = p[0]
    if m in QUIZ_FLOORS:
        fi = floor_info(m)
        done = p[2] < fi['guard'][1] or str(m) in prog.get('floors', {})
        print(f'{m}（{m - 798} 樓）@ {p[1]},{p[2]}：{"這層已答（走出口 %s）" % (fi["exit"],) if done else "走到 %s 點守衛答題" % (fi["stand"],)}')
    elif m == LOBBY:
        print(f'811 @ {p[1]},{p[2]}：走出口 {LOBBY_EXIT} 上 800')
    elif m == TOP:
        print(f'810 @ {p[1]},{p[2]}：找伊那多 {INADO}「拿金豬」')
    else:
        print(f'{p}：不在塔內')
    return 0


def main() -> int:
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    ap = argparse.ArgumentParser(description='猜謎三兄弟爬塔拿金布伊（3003 步 1）')
    sub = ap.add_subparsers(dest='cmd', required=True)
    r = sub.add_parser('run')
    r.add_argument('--dry-run', action='store_true')
    r.add_argument('--at', type=int, default=LOBBY, help='--dry-run 的起點地圖')
    r.add_argument('--no-track', action='store_true', help='不試點追蹤，一律 walk.py')
    r.add_argument('--max-min', type=float, default=MAX_MIN)
    r.add_argument('--no-dump', action='store_true', help='不存選項裁切')
    b = sub.add_parser('bank')
    b.add_argument('key', nargs='?', default='')
    mt = sub.add_parser('match')
    mt.add_argument('png')
    mt.add_argument('--question', required=True)
    mt.add_argument('--dump', action='store_true')
    sub.add_parser('status')
    a = ap.parse_args()
    if a.cmd == 'bank':
        return cmd_bank(a.key)
    if a.cmd == 'match':
        return cmd_match(a.png, a.question, a.dump)
    if a.cmd == 'status':
        return cmd_status()
    if not a.dry_run:
        import winenv
        winenv.enable_server()
    return run(dry_run=a.dry_run, use_track=not a.no_track, at=a.at, max_min=a.max_min, no_dump=a.no_dump)


if __name__ == '__main__':
    sys.exit(main())
