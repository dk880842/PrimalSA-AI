#!/usr/bin/env python3
"""轉生任務（漆黑洞窟 N 轉）的獨立小步驟：接任務、轉生獎勵寵偵測 / 丟棄。rebirth.py 只負責串階段，這裡每個函式 / 子指令都能單獨呼叫。只用標準函式庫。

用法（專案根目錄；WSL / Windows 原生相同）：
  uv run --no-project python tools/gui/rebirth_steps.py accept --trans 3            # 接「漆黑洞窟(三轉)」（任務詳情 → 傳送到瑪麗娜絲村長 → 選單頁翻頁 → 接受 → 驗證進行中）
  uv run --no-project python tools/gui/rebirth_steps.py snapshot                    # 唯讀：讀 5 人寵物欄存成轉生前快照（tools/.cache/rebirth_pets_before.json）
  uv run --no-project python tools/gui/rebirth_steps.py drop-reward --trans 3 [--dry-run]   # 轉生後丟 5 人的獎勵寵（見下）
  可 import：accept_task(n, T=None)、reward_name(n)、find_new_lv1(before, after)、drop_rewards(n, before, T=None, dry_run=False)

接任務（accept_task）：用 questdetail.accept(「漆黑洞窟(N轉)」, skip_ok=True)。任務詳情列表 / 中間標題用樣板精確比對（(三轉) / (五轉) 只差一字也分得開，
  標題對不上就不傳送、不亂點）；傳送到村長後對話框第 1 頁是選單（左鈕「漆黑洞窟」）→ 先點左鈕翻頁（questdetail 2d0e38d 的選單頁邏輯）→ 第 2 頁「接受」→
  重開詳情驗證「進行中」。已進行中 = 跳過（回 0）；已完成 = 失敗（轉生 / 封印書後任務會重置，已完成表示轉數不對）。
轉生獎勵寵：一轉 = 烏力斯坦、二轉 = 奇娜（REWARD，實機）；三轉起沒有對照表 → 轉生前後寵物欄 diff：
  每人要「剛好 1 隻新出現的 Lv1 寵物」、名字讀得出且不是騎寵 / 戰寵（狀態等待）、不在第 1 格，名字 + Lv1 都驗過才丟（petdrop --slot --max-level 1）；
  任何不確定（沒有快照、0 / 多隻候選、名字讀不出、等級讀不出）→ 一律不丟、回 98，不碰騎寵 / 戰寵。
退出碼：0 成功；97 接任務失敗（info.accept_rc = questdetail 退出碼，120～129 見 questdetail.py）；98 獎勵寵無法確認 / 丟棄失敗（info.why）；
  9 / 10 驗證視窗 / 斷線 透傳。
"""
import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import uikit  # noqa: E402

SRC = 'rebirth_steps'
EXIT_ACCEPT, EXIT_REWARD = 97, 98
CN = {1: '一', 2: '二', 3: '三', 4: '四', 5: '五'}
ALL_ROLES = ['DKBO', 'DKBO2', 'DKBO3', 'DKBO4', 'DKBO5']
REWARD = {1: '烏力斯坦', 2: '奇娜'}                  # 轉生獎勵寵（實機：一轉烏力斯坦、二轉奇娜；其餘轉數靠 diff）
SNAPSHOT = uikit.CACHE / 'rebirth_pets_before.json'
LAST: dict = {}


def task_name(n: int) -> str:
    return f'漆黑洞窟({CN[n]}轉)'


def reward_name(n: int):
    return REWARD.get(n)


# ---- 接任務 ----
def accept_task(n: int, T=None) -> int:
    """接漆黑洞窟(N轉)。T 可換（測試）：T.accept(title) → 退出碼、T.accept_state() → 'doing' / 'done' / 'accepted' / None"""
    LAST.clear()
    title = task_name(n)
    T = T or _AcceptTools()
    rc = T.accept(title)
    st = T.accept_state()
    LAST.update(accept_rc=rc, state=st)
    if rc in (uikit.EXIT_UNKNOWN_SCREEN, uikit.EXIT_HALT):
        return rc
    if rc:
        return uikit.fail(SRC, EXIT_ACCEPT, f'接「{title}」失敗（questdetail rc={rc}）')
    if st == 'done':
        return uikit.fail(SRC, EXIT_ACCEPT, f'「{title}」狀態是已完成，不是待接取 / 進行中（轉數不對？轉生後任務會重置），不接')
    print(f'{SRC}：「{title}」' + ('已在進行中，跳過' if st == 'doing' else '已接取'), flush=True)
    return 0


class _AcceptTools:
    def accept(self, title):
        import questdetail
        return questdetail.accept(title, skip_ok=True)

    def accept_state(self):
        import questdetail
        return questdetail.LAST.get('state')


# ---- 轉生獎勵寵 ----
def snapshot_pets(slots_by_role: dict) -> dict:
    """pet.list_role 的結果 → 精簡快照 {role: [{slot, empty, name, level, state}]}（可存 json）"""
    out = {}
    for r, sl in (slots_by_role or {}).items():
        out[r] = [{'slot': s.get('slot'), 'empty': bool(s.get('empty')), 'name': s.get('name'), 'level': s.get('level'), 'state': s.get('state'),
                   'unnamed': s.get('unnamed'), 'mountlike': bool(s.get('mountlike'))} for s in sl or []]
    return out


def find_new_lv1(before: list, after: list) -> tuple:
    """單人：轉生前 / 後寵物欄（snapshot 格式）→ (候選 [slot dict], 理由)。
    候選 = 轉生前是空格（或名字不同）、轉生後有寵物、Lv1、名字讀得出、不是騎寵 / 戰寵（state 不是 騎乘 / 出戰）、不在第 1 格。
    只有「恰好 1 隻」才算確定；其他情況候選照回，理由說明不確定在哪（純函式）"""
    bef = {s['slot']: s for s in before or []}
    cand, why = [], ''
    for s in after or []:
        if s.get('empty'):
            continue
        b = bef.get(s['slot'])
        if b and not b.get('empty') and b.get('name') and b.get('name') == s.get('name'):
            continue                                                  # 原本就在
        if s['slot'] == 1:
            why = '新寵物在第 1 格（通常是騎寵）→ 不丟'
            continue
        if s.get('state') in ('騎乘', '出戰') or s.get('mountlike'):
            why = f'第 {s["slot"]} 格狀態 / 名字像騎寵戰寵 → 不丟'
            continue
        if s.get('level') != 1:
            why = f'第 {s["slot"]} 格新寵物等級 {s.get("level")} 不是 1（讀不出也算）→ 不丟'
            continue
        if not s.get('name'):
            why = f'第 {s["slot"]} 格新寵物名字讀不出 → 不丟'
            continue
        cand.append(s)
    if len(cand) == 1:
        return cand, ''
    if not cand:
        return cand, why or '轉生前後寵物欄沒有新出現的寵物'
    return cand, f'新出現 {len(cand)} 隻 Lv1 寵物（格 {[c["slot"] for c in cand]}），要剛好 1 隻'


def save_snapshot(snap: dict, path=None) -> None:
    p = Path(path or SNAPSHOT)
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(snap, ensure_ascii=False, indent=1), encoding='utf-8')
    except OSError:
        pass


def load_snapshot(path=None) -> dict:
    try:
        return json.loads(Path(path or SNAPSHOT).read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return {}


class _PetTools:
    def pets(self, roles):
        """開一次寵物面板逐人讀 → (rc, {role: slots})"""
        import pet
        ctx = pet.load_ctx(True)
        out = {}
        with pet.Session(False, True) as s:
            if s.rc:
                return s.rc, out
            for r in roles:
                rc, slots = pet.list_role(r, ctx)
                out[r] = slots
                if rc:
                    pet.save_ctx(ctx)
                    return rc, out
            pet.save_ctx(ctx)
        return 0, out

    def drop(self, role, name, slot=None, dry_run=False):
        import petdrop
        return petdrop.drop(role, name, name, slot_no=slot, dry_run=dry_run, max_level=1)


def take_snapshot(T=None, roles=None) -> int:
    T = T or _PetTools()
    rc, pets = T.pets(list(roles or ALL_ROLES))
    if rc:
        return rc
    save_snapshot(snapshot_pets(pets))
    return 0


def drop_rewards(n: int, before: dict | None = None, T=None, dry_run: bool = False, roles=None) -> int:
    """丟轉生獎勵寵。有對照表（一轉烏力斯坦 / 二轉奇娜）→ 名稱 + Lv1（petdrop --max-level 1）；沒有 → 用 before（轉生前快照）做 diff。
    回 0 / 98（diff 路徑不確定）/ 9 / 10 / petdrop 的碼（對照表路徑原碼透傳）。LAST['dropped'] = {角色: 名字}"""
    LAST.clear()
    T = T or _PetTools()
    roles = list(roles or ALL_ROLES)
    name = reward_name(n)
    if name:
        rc = T.drop('all', name, None, dry_run)
        if rc:
            return rc                                              # petdrop 原碼（70～79）；呼叫端對應
        LAST['dropped'] = {r: name for r in roles}
        return 0
    if not before:
        return uikit.fail(SRC, EXIT_REWARD, f'第 {n} 轉沒有獎勵寵對照表，也沒有轉生前的寵物欄快照（rebirth 階段沒跑過？）→ 不丟，請人確認')
    rc, after = T.pets(roles)
    if rc:
        return rc
    after = snapshot_pets(after)
    plan = {}
    for r in roles:
        cand, why = find_new_lv1(before.get(r), after.get(r))
        if len(cand) != 1:
            LAST['why'] = f'{r}：{why}'
            return uikit.fail(SRC, EXIT_REWARD, f'{r} 轉生獎勵寵無法確認：{why} → 全部都不丟（沒碰騎寵 / 戰寵）')
        plan[r] = cand[0]
    LAST['plan'] = {r: [s['slot'], s['name'], s['level']] for r, s in plan.items()}
    for r, s in plan.items():
        rc = T.drop(r, s['name'], s['slot'], dry_run)
        if rc:
            return rc if rc in (uikit.EXIT_UNKNOWN_SCREEN, uikit.EXIT_HALT) else uikit.fail(SRC, EXIT_REWARD, f'{r} 丟第 {s["slot"]} 格「{s["name"]}」失敗（petdrop rc={rc}）')
        LAST.setdefault('dropped', {})[r] = s['name']
    return 0


def main(argv=None) -> int:
    import winenv
    winenv.enable_server()
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    sub = ap.add_subparsers(dest='cmd', required=True)
    p = sub.add_parser('accept'); p.add_argument('--trans', type=int, required=True)
    sub.add_parser('snapshot')
    p = sub.add_parser('drop-reward'); p.add_argument('--trans', type=int, required=True); p.add_argument('--dry-run', action='store_true')
    a = ap.parse_args(argv)
    if getattr(a, 'trans', 1) not in CN:
        print(f'{SRC}：--trans 要 1～5', file=sys.stderr)
        return uikit.EXIT_USAGE
    if a.cmd == 'accept':
        rc = accept_task(a.trans)
    elif a.cmd == 'snapshot':
        rc = take_snapshot()
    else:
        rc = drop_rewards(a.trans, load_snapshot(), dry_run=a.dry_run)
    print(json.dumps(dict(LAST, ok=rc == 0, rc=rc), ensure_ascii=False, default=str))
    return rc


if __name__ == '__main__':
    sys.exit(main())
