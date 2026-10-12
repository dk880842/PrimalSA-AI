#!/usr/bin/env python3
"""多人同時外掛自動抓寵（卡坦的願望 S6 用；包 rebirth_pets.Tools 的誘餌 / 捉寵設置 / 等待）。只用標準函式庫。

用法（專案根目錄；先關原地遇敵、解散隊伍；DKBO 不抓）：
  uv run --no-project python tools/gui/pet_catch.py --assign "DKBO2:鯊魚系:克邦凱斯,DKBO3:鯊魚系:加克拉,DKBO4:鯊魚系:加格,DKBO5:鯊魚系:邦恩吉" --count 5 [--stages bait,setup,wait] [--dry-run]
    --assign 角色:系別:物種,…   每人抓一種（誘餌數 = 隻數）
    --count N                  每人抓幾隻（預設 5）= 背包放 N 個誘餌 = 可抓捕數
    --stages                   bait（公共倉庫取整疊 → 拆 N → 其餘存回）/ setup（外掛捉寵設置 + 勾自動存倉庫 + 勾自動抓寵）/ wait（輪詢到全部抓完）；預設全做
    --dry-run                  只印計畫
  uv run --no-project python tools/gui/pet_catch.py --lock 騎寵,戰寵 [--battle-pet 朵拉比斯] [--mount-species 布拉奇多斯] [--roles ...]   # 外掛鎖定重勾（下拉讀字選、讀回）
  uv run --no-project python tools/gui/pet_catch.py --autoswap on|off [--roles ...]                 # 自動轉換戰寵
  批次（2026-10-12）：背包（取誘餌）/ 外掛（捉寵設置、輪詢、自動轉換、鎖定）面板都只開一次，逐人切頭像做完再關。
退出碼：0 全部抓完；103 取誘餌 / 設定 / 逾時失敗（rebirth_pets.EXIT_CATCH）；其餘沿用 uikit（8 佔用 / 9 驗證視窗 / 10 斷線）。
安全：不點「+」（花石幣）、不碰丟棄區；沿用 rebirth_pets.Tools 的讀字驗證（讀不到 / 對不上就停，不盲點）。
抓完後新寵物沒名字（成長字串），分配前要 `pet.py learn-species`，見 psa-pet-quest SKILL.md。
"""
import argparse
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import rebirth_pets as rp  # noqa: E402
import uikit  # noqa: E402


def parse_assign(s: str) -> list:
    """'DKBO2:鯊魚系:克邦凱斯,DKBO3:…' → [(role, family, species)]"""
    out = []
    for part in s.split(','):
        bits = [b.strip() for b in part.split(':')]
        if len(bits) != 3 or not all(bits):
            raise ValueError(f'--assign 格式要 角色:系別:物種，收到 {part!r}')
        out.append(tuple(bits))
    return out


def run(assign: list, count: int = 5, stages=('bait', 'setup', 'wait'), dry_run: bool = False, tools=None, timeout: float = rp.CATCH_TIMEOUT_S) -> int:
    T = tools or rp.Tools()
    print(f'計畫：{[(r, f, s, count) for r, f, s in assign]} 階段 {list(stages)}')
    if dry_run:
        return 0
    if 'bait' in stages:
        import contextlib
        import bag
        with (bag.Session() if tools is None else contextlib.nullcontext()) as bs:   # 背包面板只開一次，逐人切頭像（各步驟的 bag.Session 巢狀時不重開 / 不關）
            if bs is not None and bs.rc:
                return bs.rc
            for role, fam, sp in assign:
                rc = T.bait_take(role, count)
                if rc:
                    print(f'pet_catch：{role} 取誘餌失敗 rc {rc}')
                    return rc
                print(f'pet_catch：{role} 背包誘餌 = {count}')
        if tools is None and uikit.is_open(bag.BAGANY):         # 2026-10-12 實機：拆分 / 存入後背包面板仍開著，外掛打不開
            uikit.close_panel(bag.BAGANY, known_open=True)
    if 'setup' in stages:
        rc, bad = T.catch_setup_many(assign, count)              # 外掛面板只開一次：逐人捉寵設置 + 勾自動存倉庫 / 自動抓寵
        if rc:
            print(f'pet_catch：{bad} 捉寵設置 / 勾選失敗 rc {rc}')
            return rc
        for role, fam, sp in assign:
            print(f'pet_catch：{role} 開始抓 {count} 隻 {sp}')
    if 'wait' in stages:
        pending = {r for r, _, _ in assign}
        end = uikit.clock() + timeout
        while pending:
            T.sleep(rp.CATCH_POLL_S)
            rc, st = T.catch_poll_many(sorted(pending))          # 一次開面板讀所有還沒抓完的人
            if rc:
                return rc
            for role, (left, auto) in st.items():
                print(f'pet_catch：{role} 可抓捕數 {left} 自動抓寵 {auto}')
                if auto is False and left in (0, None):                # 可抓捕數 OCR 常讀不到（None）；遊戲抓完會自己取消「自動抓寵」勾選 = 抓完（2026-10-12 實機）
                    pending.discard(role)
            if pending and uikit.clock() >= end:
                print(f'pet_catch：逾時，未抓完 {sorted(pending)}')
                return rp.EXIT_CATCH
    return 0


AUTOSWAP_XY = (656, 440)        # 外掛一般設置「自動轉換戰寵」勾選框（2026-10-12 實機；右邊 SET = 轉換級數，使用者已設 30，不動）


def set_autoswap(roles: list, on: bool, tools=None) -> int:
    """5 人（或指定角色）外掛一般設置「自動轉換戰寵」勾 / 取消：外掛面板只開一次，逐人選角色 → 讀勾選框 → 只在不同時點 1 次 → 讀回驗證。→ 0 / 非 0（rebirth_pets 的外掛退出碼 2～7）"""
    T = tools or rp.Tools()

    def fn(role):
        rc = T._toggle(AUTOSWAP_XY, on, f'{role} {"勾" if on else "取消"}自動轉換戰寵')
        if not rc:
            print(f'pet_catch：{role} 自動轉換戰寵 = {"開" if on else "關"}')
        return rc, None if rc else on
    rc, _, bad = T.ass_each(roles, 'general', fn)
    return rc


def relock(roles: list, battle_pet: str = '朵拉比斯', mount_species: str = '布拉奇多斯', which=('騎寵', '戰寵'), tools=None) -> int:
    """外掛「鎖定騎寵 / 鎖定戰寵」重勾（交寵物任務 / 換戰寵後）：讀寵物欄決定每人要選哪一隻（騎寵沒名字用成長字串）→
    外掛面板只開一次逐人：下拉 OCR 讀字找剛好一列吻合的（每人順序不同，errlog #257）→ 讀回欄位 → 勾 → 讀回勾選（每項當場讀回，不另開面板）。→ 0 / rebirth_pets 退出碼"""
    T = tools or rp.Tools()
    rc, pets = T.pets_list(roles)
    if rc:
        return rc
    items, why = rp.lock_items(pets, roles, mount_species, battle_pet, which)
    if why:
        print(f'pet_catch：{why}')
        return rp.EXIT_LOCK
    rc, bad = T.lock_set_many(items)
    if rc:
        print(f'pet_catch：{bad} 鎖定失敗 rc {rc}')
        return rc
    # 不再另開一次面板讀回：_lock_set_here 每項都讀回欄位 / 勾選（2026-10-12 實機多讀一輪要 14 s，結果相同）
    print(f'pet_catch：{"、".join(which)} 鎖定完成：{roles}')
    return 0


EXIT_NO_BATTLE_PET = 105          # 有人沒有「出戰」的非騎寵（練寵會沒經驗）


def missing_battle(pets: dict) -> list:
    """純函式：pets = {角色: pet.list 的 slots}；回「沒有任何出戰非騎寵」的角色（騎乘狀態、空格不算）"""
    return [r for r, slots in pets.items() if not any((not s.get('empty')) and s.get('state') == '出戰' for s in slots)]


def verify_battle(roles: list, tools=None) -> int:
    """開遇敵練寵前逐人讀回：每人都要有出戰寵（2026-10-12 DKBO4 沒帶戰寵練了一段）。0 = 都有；EXIT_NO_BATTLE_PET = 有人沒有（印出誰）；其餘 = 讀取失敗退出碼"""
    T = tools or rp.Tools()
    rc, pets = T.pets_list(roles)
    if rc:
        return rc
    miss = missing_battle(pets)
    if miss:
        print(f'pet_catch：沒有出戰寵：{miss}（先 pet.py set-state 角色 寵物名 出戰，再開遇敵）')
        return EXIT_NO_BATTLE_PET
    print('pet_catch：5 人都有出戰寵')
    return 0


def register_growths(mapping: dict) -> int:
    """成長字串 → 物種 直接寫進登錄檔（倉庫卡沒縮圖，take-many 只能靠字串找）。字串已屬別的物種 = 不可靠，刪掉（回傳刪了幾個）。
    mapping 來源：抓寵時每人只抓一種，所以「該人名下抓到的寵物成長字串」就是該物種的字串（呼叫端自己從 pet.py list 讀）"""
    import petmatch
    reg = petmatch.load_species()
    g = reg.setdefault('growth', {})
    dropped = 0
    for gr, sp in mapping.items():
        if g.get(gr) not in (None, sp):
            del g[gr]
            dropped += 1
        elif g.get(gr) is None and gr not in g:
            g[gr] = sp
    petmatch.save_species(reg)
    return dropped


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description='多人外掛自動抓寵')
    ap.add_argument('--assign')
    ap.add_argument('--autoswap', choices=['on', 'off'], help='改做：5 人外掛「自動轉換戰寵」勾 / 取消（不抓寵）')
    ap.add_argument('--verify-battle', action='store_true', help='改做：逐人讀回出戰寵（開遇敵練寵前；沒有出戰寵退出碼 105）')
    ap.add_argument('--lock', default=None, metavar='騎寵,戰寵', help='改做：外掛鎖定重勾（騎寵 / 戰寵 / 兩者；下拉讀字選、讀回）')
    ap.add_argument('--battle-pet', default='朵拉比斯')
    ap.add_argument('--mount-species', default='布拉奇多斯')
    ap.add_argument('--roles', default='DKBO,DKBO2,DKBO3,DKBO4,DKBO5')
    ap.add_argument('--count', type=int, default=5)
    ap.add_argument('--stages', default='bait,setup,wait')
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--timeout', type=float, default=rp.CATCH_TIMEOUT_S)
    a = ap.parse_args(argv)
    if a.verify_battle:
        import winenv
        winenv.enable_server()
        return verify_battle(a.roles.split(','))
    if a.lock:
        import winenv
        winenv.enable_server()
        which = tuple(w for w in ('騎寵', '戰寵') if w in a.lock)
        if not which:
            ap.error('--lock 要 騎寵 / 戰寵 / 騎寵,戰寵')
        return relock(a.roles.split(','), a.battle_pet, a.mount_species, which)
    if a.autoswap:
        import winenv
        winenv.enable_server()
        return set_autoswap(a.roles.split(','), a.autoswap == 'on')
    if not a.assign:
        ap.error('要 --assign 或 --autoswap')
    try:
        assign = parse_assign(a.assign)
    except ValueError as e:
        print(e)
        return 2
    import winenv
    winenv.enable_server()
    return run(assign, a.count, tuple(a.stages.split(',')), a.dry_run, timeout=a.timeout)


if __name__ == '__main__':
    sys.exit(main())
