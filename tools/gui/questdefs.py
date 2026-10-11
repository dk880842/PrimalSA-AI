#!/usr/bin/env python3
"""1.82 任務系列資料表（questrun.py 用；計畫 notes/plan-182-script.md §2.3）。只用標準函式庫。

一任務一筆 dict：
  id          任務組 ID（Task / TaskExplan 的 ID）
  detail      任務詳情列表的標題（TaskExplan.nameTn，1.82 任務有「(1.82)」後綴）
  track       追蹤列表的標題（= Task 表 name，沒有「(1.82)」後綴；quest.py --task 用）
  accept_npc  接取任務的 NPC（只給 plan 顯示；實際由 questdetail.accept 用「傳送」直達）
  steps_total 步數（test_questdefs 與 Task.jsonl 核對）
  steps       {步號: dict(kind=...)}；沒列的步驟 = 預設（quest.py 預設模式：點追蹤 → 巡路 → 對話 → 戰鬥）
              kind：walk（遊戲不巡路，要 walk.py 走到 map / xy；handler 在 questhandlers.py）
                    manual（停下交人，退出碼 115）
  bag_slots   開始前每人背包至少要有幾格空位（0 = 不檢查）
  boss        True = 有任務戰 / BOSS 戰（quest.py 預設模式打完回 37 / 38；P2 只收資料，不實跑）
  est_min     預估分鐘（quest-log 0 轉 123 級 5 人隊實跑）
  live        P2 實機驗證過：True；只有資料沒實跑：False
  note        坑 / 提醒
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

Q182 = [
    dict(id=2999, detail='成人儀式', track='成人儀式', accept_npc='儀式的審判 10204:14,6', steps_total=2,
         steps={1: dict(kind='walk', map=10204, xy=(188, 13), npc='儀式審判的差使')},
         bag_slots=1, boss=False, est_min=7, live=True,
         note='1.82 全部任務的前置。步 1（去差使拿儀的玉×15）點追蹤不巡路 → walk handler 走到 10204:188,13；步 2 點追蹤自動巡路回儀式的審判'),
    dict(id=2017, detail='彌生和日美子(1.82)', track='彌生和日美子', accept_npc='彌生 2000:54,97', steps_total=1,
         steps={}, bag_slots=0, boss=False, est_min=3, live=True, note='純巡路（日美子 1000:57,124）'),
    dict(id=2015, detail='亞姆的斧頭(1.82)', track='亞姆的斧頭', accept_npc='亞姆亞姆 1400:69,89', steps_total=2,
         steps={}, bag_slots=0, boss=False, est_min=5, live=True,
         note='純巡路（馬提 1300:18,42 → 亞姆亞姆）；詳情列表拖動有慣性，questdetail 已等 1.5 秒並驗右側標題'),
    dict(id=2027, detail='小豬愛情故事(1.82)', track='小豬愛情故事', accept_npc='烏力斯凱 20401:14,10', steps_total=2,
         steps={}, bag_slots=0, boss=False, est_min=5, live=False, note='純巡路（烏力美 20406:36,34 → 烏力斯凱）；接受要按 2 次'),
    dict(id=2018, detail='馬祖快遞(1.82)', track='馬祖快遞', accept_npc='馬祖 1300:70,51', steps_total=3,
         steps={}, bag_slots=0, boss=False, est_min=11, live=False, note='純巡路（房子主人 120 → 迷宮 119 卡伊特 → 馬祖）；多層迷宮'),
    dict(id=2011, detail='夢幻洞窟(1.82)', track='夢幻洞窟', accept_npc='村中的老人 6000:73,54', steps_total=2,
         steps={}, bag_slots=0, boss=True, est_min=9, live=False,
         note='步 1 任務戰（卡卡金寶）；每轉解一次即可；追蹤清單要先捲到目標（quest.py 已用 titlematch）'),
]

BY_ID = {d['id']: d for d in Q182}
DEFAULT_ORDER = [d['id'] for d in Q182]
STEP_KINDS = ('walk', 'manual')


def get(task_id: int) -> dict | None:
    return BY_ID.get(int(task_id))


def resolve(ids) -> tuple:
    """→ (任務資料列表, 不認得的輸入列表)；ids 空 = 預設順序（全部）；保留輸入順序"""
    if not ids:
        return list(Q182), []
    out, bad = [], []
    for x in ids:
        try:
            d = BY_ID.get(int(x))
        except (TypeError, ValueError):
            d = None
        if d:
            out.append(d)
        else:
            bad.append(x)
    return out, bad


def step_kind(d: dict, step) -> str:
    """步號 → kind（沒列 = 'default'）"""
    return (d.get('steps') or {}).get(step, {}).get('kind', 'default')
