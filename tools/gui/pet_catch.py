#!/usr/bin/env python3
"""多人同時外掛自動抓寵（卡坦的願望 S6 用；包 rebirth_pets.Tools 的誘餌 / 捉寵設置 / 等待）。只用標準函式庫。

用法（專案根目錄；先關原地遇敵、解散隊伍；DKBO 不抓）：
  uv run --no-project python tools/gui/pet_catch.py --assign "DKBO2:鯊魚系:克邦凱斯,DKBO3:鯊魚系:加克拉,DKBO4:鯊魚系:加格,DKBO5:鯊魚系:邦恩吉" --count 5 [--stages bait,setup,wait] [--dry-run]
    --assign 角色:系別:物種,…   每人抓一種（誘餌數 = 隻數）
    --count N                  每人抓幾隻（預設 5）= 背包放 N 個誘餌 = 可抓捕數
    --stages                   bait（公共倉庫取整疊 → 拆 N → 其餘存回）/ setup（外掛捉寵設置 + 勾自動存倉庫 + 勾自動抓寵）/ wait（輪詢到全部抓完）/
                               register（抓完登錄來源：見下）；預設全做
  uv run --no-project python tools/gui/pet_catch.py --assign "..." --stages register     # 只登錄來源（抓完後補做 / 重做）
  register（2026-10-13 卡坦 4 鯊 / 4 雞物種靠縮圖會混、只好人工比腹部顏色）：「誰抓的」是主鍵 —— 每人只抓 --assign 指定的一種，
    所以抓寵者寵物欄裡沒名字、物種登錄檔還不認得的寵物 = 他抓的那種；寫進「成長字串 → 物種」登錄檔（register_growths，撞別種就刪）
    與來源檔 tools/.cache/pet-tpl/catch-src.json（成長字串 → 物種 / 抓寵者 / 時間；倉庫存入後會重排，所以不記格位）。
    交叉驗證：縮圖只在本次 --assign 的物種之間相對比較（petimg_match.rank_among，inlier + 主色都同意才算有把握）：
    有把握且是別的物種 → 矛盾，不登錄這隻、退出碼 15（EXIT_CATCH_SPECIES，印出哪人哪格）；沒把握 → 照來源登錄。
    之後 store-many / take-many 加 `--candidates <同一組物種>`：沒名字的寵物 / 倉庫卡先看登錄檔，認不得再用同一套相對比較，仍沒把握就 72 不取（不亂分）。
    --poll 秒                  wait 輪詢間隔（預設：第一次依隻數 k×20+20 秒〔40～120〕、之後每 60 秒，review 1013b §2.4；給值 = 每次都等這麼久。每次要開外掛面板，開前會先等戰鬥結束）
    --reuse-setup              沿用上一批的捉寵設置（petquest 同一輪第 2 批起）：系別 / 物種欄位 OCR 讀不到字就不重選下拉（讀到別的字才重選），可抓捕數 / 勾選照做，讀回驗證照舊
    --dry-run                  只印計畫
  register 的排除（2026-10-14 恐龍博士：第 1 格騎寵布拉奇多斯 51/9/8/1 被登錄成魯尼帖斯）：第 1 格、騎乘中、騎寵（名字 / 物種 / 縮圖）、
    抓寵前就在寵物欄的寵物一律不登錄。「抓寵前」= 抓寵前寵物欄快照 tools/.cache/pet-tpl/catch-pre.json（setup 階段前寫：petquest 用它抓前讀好的
    pet.py list 直接存〔save_pre〕，沒有 / 超過 PRE_MAX_S 才自己讀一次）；比對用名字框點陣指紋 nh（同一隻固定），再退回成長字串，依張數扣（同字串多隻也對）。
    快照沒有該角色 → 只排除第 1 格 / 騎寵並印警告。非空、不是騎寵、名字和成長字串都讀不出的新寵物 → 不登錄並報錯（退出碼 16，其餘照登錄），不沉默略過。
  setup / wait 失敗（設置選不到、逾時…；驗證視窗 9 / 斷線 10 除外）→ 收尾把這批抓寵者的「自動抓寵」勾掉（catch_off；已設好的人不會繼續抓）。
  uv run --no-project python tools/gui/pet_catch.py --catch-off [--roles DKBO2,DKBO3]     # 改做：外掛捉寵設置「自動抓寵」取消勾選（讀回）
  uv run --no-project python tools/gui/pet_catch.py --lock 騎寵,戰寵 [--battle-pet 朵拉比斯] [--mount-species 布拉奇多斯] [--roles ...]   # 外掛鎖定重勾（下拉讀字選、讀回）
  uv run --no-project python tools/gui/pet_catch.py --autoswap on|off [--roles ...]                 # 自動轉換戰寵
  批次（2026-10-12）：背包（取誘餌）/ 外掛（捉寵設置、輪詢、自動轉換、鎖定）面板都只開一次，逐人切頭像做完再關。
退出碼：0 全部抓完；16 register：有新寵物名字框讀不出（EXIT_CATCH_UNREAD，那隻沒登錄，其他照登錄）；103 取誘餌 / 設定 / 逾時失敗（rebirth_pets.EXIT_CATCH）；14 捉寵設置系別 / 物種選不到或讀回對不上（EXIT_CATCH_PICK，已重試、已收下拉、沒勾自動抓寵）；
  15 register：抓寵者欄裡有寵物縮圖有把握認成別的物種（EXIT_CATCH_SPECIES，那隻沒登錄，其他照登錄）；其餘沿用 uikit（8 佔用 / 9 驗證視窗 / 10 斷線）。
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


EXIT_CATCH_SPECIES = 15
EXIT_CATCH_UNREAD = 16
SRC_FILE = 'catch-src.json'                # 抓寵來源檔（petmatch.TPL_DIR 底下）
PRE_FILE = 'catch-pre.json'                # 抓寵前寵物欄快照（register 排除舊寵物用）
PRE_MAX_S = 30 * 60                        # 快照超過這麼久就不信（自己重讀）
PASS_RC = (9, 10)                          # uikit.EXIT_UNKNOWN_SCREEN / EXIT_HALT：驗證視窗 / 斷線 → 不做任何收尾點擊


def src_path():
    import petmatch
    return petmatch.TPL_DIR / SRC_FILE


def load_src() -> dict:
    import json
    try:
        d = json.loads(src_path().read_text(encoding='utf-8'))
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


def save_src(d: dict) -> None:
    import json
    p = src_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix('.tmp')
    tmp.write_text(json.dumps(d, ensure_ascii=False), encoding='utf-8')
    tmp.replace(p)


def pre_path():
    import petmatch
    return petmatch.TPL_DIR / PRE_FILE


def save_pre(pets: dict, now: float | None = None) -> None:
    """抓寵前寵物欄快照（{角色: pet.py list 的格}）→ catch-pre.json（只留比對要的欄位）"""
    import json
    keep = ('slot', 'empty', 'name', 'unnamed', 'nh', 'state')
    d = {'ts': time.time() if now is None else now,
         'roles': {r: [{k: s.get(k) for k in keep if k in s} for s in slots or []] for r, slots in (pets or {}).items()}}
    p = pre_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix('.tmp')
    tmp.write_text(json.dumps(d, ensure_ascii=False), encoding='utf-8')
    tmp.replace(p)


def load_pre(max_age: float = PRE_MAX_S, now: float | None = None) -> dict:
    """→ {角色: 格}；沒有 / 壞檔 / 超過 max_age → {}"""
    import json
    try:
        d = json.loads(pre_path().read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return {}
    now = time.time() if now is None else now
    if not isinstance(d, dict) or now - (d.get('ts') or 0) > max_age:
        return {}
    return d.get('roles') or {}


def _is_mountish(s: dict) -> bool:
    import uikit as U
    return bool(s.get('mountlike') or s.get('state') == '騎乘' or s.get('species') in U.MOUNTS or s.get('img_species') in U.MOUNTS
                or s.get('name') in U.MOUNTS)


def new_slots(pre: list, cur: list) -> list:
    """純函式：抓寵前快照 pre、現在 cur（pet.py list 的格）→ cur 裡「抓寵前不在」的非空格。
    先比名字框點陣指紋 nh、再比成長字串 / 名字，依張數扣（3 隻同字串的魯尼帖斯抓前有 1 隻 → 新的 2 隻）"""
    from collections import Counter
    nh = Counter(s['nh'] for s in pre or [] if not s.get('empty') and s.get('nh'))
    ids = Counter(s.get('unnamed') or s.get('name') for s in pre or [] if not s.get('empty') and not s.get('nh') and (s.get('unnamed') or s.get('name')))
    out = []
    for s in cur or []:
        if s.get('empty'):
            continue
        k, i = s.get('nh'), s.get('unnamed') or s.get('name')
        if k and nh[k] > 0:
            nh[k] -= 1
        elif i and ids[i] > 0:
            ids[i] -= 1
        else:
            out.append(s)
    return out


def plan_register(assign: list, pets: dict, reg_growth: dict, pre: dict | None = None) -> tuple:
    """純函式：抓寵者寵物欄 → (登錄 {成長字串: (物種, 抓寵者)}, 矛盾 [(角色, 格, 成長字串, 縮圖物種, 應是)], 讀不出 [(角色, 格, OCR 行)])。
    只看「沒名字、成長字串還沒登錄成別的物種」的格（已登錄成別種 = 以前分來的，不是這次抓的）；
    一律不看：第 1 格、騎乘中 / 騎寵、抓寵前快照 pre[角色] 裡就有的（pre 沒有該角色 → 只靠前兩條）；
    縮圖（rank_among 結果放在 img_species / species）有把握且 ≠ 指定物種 → 矛盾（不登錄）；沒把握 / 相同 → 依來源登錄；
    非空、沒名字、成長字串讀不出 → 讀不出清單（不登錄、呼叫端要報錯）"""
    want = {r: sp for r, _, sp in assign}
    todo, bad, unread = {}, [], []
    for role, sp in want.items():
        slots = pets.get(role) or []
        fresh = new_slots(pre[role], slots) if pre and role in pre else [s for s in slots if not s.get('empty')]
        for s in fresh:
            if s.get('slot') == 1 or _is_mountish(s) or s.get('name'):
                continue
            g = s.get('unnamed')
            if s.get('guess') and g == s.get('guess') and s.get('unreadable'):     # 讀不出、靠候選字串認的：已登錄成這種 = 沒事要做；否則不拿來登錄（不確定的字串不進登錄檔）
                if reg_growth.get(g) == sp:
                    continue
                g = None
            if not g:
                unread.append((role, s.get('slot'), s.get('ocr')))
                continue
            known = reg_growth.get(g)
            if known and known != sp:
                continue
            seen = s.get('img_species') or (s.get('species') if s.get('species_src', '').startswith('img') else None)
            if seen and seen != sp:
                bad.append((role, s['slot'], g, seen, sp))
                continue
            if g in todo and todo[g][0] != sp:                  # 同一字串兩個抓寵者（不同物種）→ 不可靠，兩邊都不登錄
                bad.append((role, s['slot'], g, f'字串也在 {todo[g][1]}（{todo[g][0]}）', sp))
                todo[g] = (None, todo[g][1])
                continue
            todo[g] = (sp, role)
    return {g: v for g, v in todo.items() if v[0]}, bad, unread


def register_catches(assign: list, tools=None) -> int:
    """抓完登錄來源（見檔頭 register）：寵物面板只開一次讀抓寵者 → plan_register → register_growths + catch-src.json。→ 0 / 15 / 讀取失敗退出碼"""
    import petmatch
    T = tools or rp.Tools()
    species = list(dict.fromkeys(sp for _, _, sp in assign))
    rc, pets = T.pets_list([r for r, _, _ in assign], img_only=species)
    if rc:
        print(f'pet_catch：register 讀寵物欄失敗 rc {rc}')
        return rc
    reg = petmatch.load_species()
    pre = load_pre()
    miss = [r for r, _, _ in assign if r not in pre]
    if miss:
        print(f'pet_catch：register 沒有 {miss} 的抓寵前快照（{PRE_FILE}）→ 只排除第 1 格 / 騎寵，抓寵前就在的寵物可能被誤登錄，請人看結果')
    todo, bad, unread = plan_register(assign, pets, reg.get('growth') or {}, pre)
    dropped = register_growths({g: sp for g, (sp, _) in todo.items()})
    src = load_src()
    now = time.strftime('%Y-%m-%d %H:%M:%S')
    for g, (sp, role) in todo.items():
        old = src.get(g)
        if old and old.get('species') != sp:
            src[g] = {'species': None, 'catcher': None, 'ts': now, 'note': f'撞號：{old.get("species")} / {sp}'}
        else:
            src[g] = {'species': sp, 'catcher': role, 'ts': now}
    save_src(src)
    for role, _, sp in assign:
        gs = [g for g, (s2, r2) in todo.items() if r2 == role]
        print(f'pet_catch：register {role} 抓的 {sp}：登錄 {len(gs)} 隻 {gs}')
    if dropped:
        print(f'pet_catch：register 有 {dropped} 個成長字串撞到別的物種，已從登錄檔刪掉（這些只能靠縮圖）')
    for role, slot, ocr in unread:
        print(f'pet_catch：register {role} 第 {slot} 格名字框讀不出成長字串（OCR {ocr}）→ 不登錄；用 pet.py list 看，必要時 learn-species --confirm-growth')
    if unread:
        try:
            import errlog
            errlog.add(f'pet_catch register：新寵物名字框讀不出成長字串 {[(r, s) for r, s, _ in unread]}（OCR {[o for _, _, o in unread]}）', source='pet_catch')
        except Exception:                                              # noqa: BLE001
            pass
    if bad:
        for role, slot, g, seen, sp in bad:
            print(f'pet_catch：register {role} 第 {slot} 格 {g}：縮圖認成 {seen}，但他抓的是 {sp} → 不登錄（請人看）')
        return EXIT_CATCH_SPECIES
    return EXIT_CATCH_UNREAD if unread else 0


def catch_off(roles: list, tools=None) -> int:
    """外掛捉寵設置「自動抓寵」取消勾選（抓寵中途失敗的收尾；已是未勾就不點，_toggle 讀回）。外掛面板只開一次逐人。→ 0 / 退出碼"""
    T = tools or rp.Tools()

    def fn(role):
        rc = T._toggle(rp.CATCH_XY['auto'], False, f'{role} 取消自動抓寵')
        return rc, None if rc else False
    rc, _, bad = T.ass_each(list(roles), 'catch', fn)
    print(f'pet_catch：自動抓寵{"已取消" if not rc else f"取消失敗（{bad} rc {rc}）"}：{list(roles)}')
    return rc


def ensure_pre(roles: list, T) -> int:
    """setup 前確保有抓寵前快照（PRE_MAX_S 內、含全部抓寵者）；沒有就讀一次寵物欄存起來。→ 0 / 讀取失敗退出碼"""
    pre = load_pre()
    if all(r in pre for r in roles):
        return 0
    rc, pets = T.pets_list(list(roles))
    if rc:
        print(f'pet_catch：抓寵前讀寵物欄失敗 rc {rc}')
        return rc
    save_pre(pets)
    return 0


NEXT_POLL_S = 60.0                # 第一次輪詢之後的間隔（review 1013b §2.4）


def first_poll_s(count: int) -> float:
    """第一次輪詢等多久：依隻數估（實測自動抓寵約 15 秒 / 隻）k × 20 + 20，夾在 [40, CATCH_POLL_S]（4 隻 100 秒、1 隻 40 秒）"""
    return float(max(40, min(int(rp.CATCH_POLL_S), int(count) * 20 + 20)))


def run(assign: list, count: int = 5, stages=('bait', 'setup', 'wait', 'register'), dry_run: bool = False, tools=None, timeout: float = rp.CATCH_TIMEOUT_S,
        poll: float | None = None, reuse_setup: bool = False) -> int:
    """poll = None（預設）：第一次輪詢 first_poll_s(count)、之後每 NEXT_POLL_S；給值 = 每次都等這麼久（舊行為）。
    reuse_setup = 沿用上一批的捉寵設置（petquest 第 2 批起；見 rebirth_pets.catch_setup_many reuse）"""
    T = tools or rp.Tools()
    print(f'計畫：{[(r, f, s, count) for r, f, s in assign]} 階段 {list(stages)}')
    if dry_run:
        return 0
    if 'bait' in stages:
        import contextlib
        import bag
        with (bag.Session() if tools is None else contextlib.nullcontext()) as bs:   # 背包面板只開一次，逐人切頭像（取 / 拆 / 存回都在同一次；內層 Session 巢狀時不重開 / 不關）
            if bs is not None and bs.rc:
                return bs.rc
            rc = T.bait_take_many([r for r, _, _ in assign], count)
            if rc:
                print(f'pet_catch：{getattr(T, "bait_failed", None) or "?"} 取誘餌失敗 rc {rc}')
                return rc
        if tools is None and uikit.is_open(bag.BAGANY):         # 2026-10-12 實機：拆分 / 存入後背包面板仍開著，外掛打不開
            uikit.close_panel(bag.BAGANY, known_open=True)
    roles = [r for r, _, _ in assign]
    if 'setup' in stages:
        rc = ensure_pre(roles, T)
        if rc:
            return rc
        rc, bad = (T.catch_setup_many(assign, count, reuse=True) if reuse_setup else T.catch_setup_many(assign, count))   # 外掛面板只開一次：逐人捉寵設置 + 勾自動存倉庫 / 自動抓寵
        if rc:
            print(f'pet_catch：{bad} 捉寵設置 / 勾選失敗 rc {rc}')
            if rc not in PASS_RC:                                  # 前面的人可能已勾好自動抓寵、會繼續抓（2026-10-14 DKBO3 物種選不到、DKBO2 照抓）→ 全部勾掉
                catch_off(roles, T)
            return rc
        for role, fam, sp in assign:
            print(f'pet_catch：{role} 開始抓 {count} 隻 {sp}')
    if 'wait' in stages:
        pending = {r for r, _, _ in assign}
        end = uikit.clock() + timeout
        waits = 0
        while pending:
            T.sleep(poll if poll else (first_poll_s(count) if not waits else NEXT_POLL_S))
            waits += 1
            rc, st = T.catch_poll_many(sorted(pending))          # 一次開面板讀所有還沒抓完的人
            if rc:
                if rc not in PASS_RC:
                    catch_off(sorted(pending), T)
                return rc
            for role, (left, auto) in st.items():
                print(f'pet_catch：{role} 可抓捕數 {left} 自動抓寵 {auto}')
                if auto is False and left in (0, None):                # 可抓捕數 OCR 常讀不到（None）；遊戲抓完會自己取消「自動抓寵」勾選 = 抓完（2026-10-12 實機）
                    pending.discard(role)
            if pending and uikit.clock() >= end:
                print(f'pet_catch：逾時，未抓完 {sorted(pending)} → 取消自動抓寵')
                catch_off(sorted(pending), T)
                return rp.EXIT_CATCH
    if 'register' in stages:
        return register_catches(assign, T)
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


def unlock(roles: list, which=('戰寵',), tools=None) -> int:
    """外掛「鎖定戰寵 / 鎖定騎寵」取消勾選（換練功寵前；先確認是勾著才點，_toggle 已處理）。外掛面板只開一次逐人。→ 0 / 退出碼"""
    T = tools or rp.Tools()
    rc, bad = T.lock_set_many([(r, w, False, None) for r in roles for w in which])
    if rc:
        print(f'pet_catch：{bad} 取消鎖定失敗 rc {rc}')
    else:
        print(f'pet_catch：{"、".join(which)} 已取消鎖定：{roles}')
    return rc


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
    ap.add_argument('--unlock', default=None, metavar='騎寵,戰寵', help='改做：外掛取消鎖定（換練功寵前）')
    ap.add_argument('--catch-off', action='store_true', help='改做：外掛捉寵設置「自動抓寵」取消勾選（--roles，預設 DKBO2,DKBO3,DKBO4,DKBO5）')
    ap.add_argument('--battle-pet', default='朵拉比斯')
    ap.add_argument('--mount-species', default='布拉奇多斯')
    ap.add_argument('--roles', default='DKBO,DKBO2,DKBO3,DKBO4,DKBO5')
    ap.add_argument('--count', type=int, default=5)
    ap.add_argument('--stages', default='bait,setup,wait,register')
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--timeout', type=float, default=rp.CATCH_TIMEOUT_S)
    ap.add_argument('--poll', type=float, default=None, help='wait 階段輪詢間隔秒（預設：第一次 k×20+20、之後 60；每次要開外掛面板）')
    ap.add_argument('--reuse-setup', action='store_true', help='沿用上一批的捉寵設置（欄位讀不到字不重選下拉；讀回驗證照舊）')
    a = ap.parse_args(argv)
    if a.catch_off:
        import winenv
        winenv.enable_server()
        roles = a.roles.split(',') if a.roles != ap.get_default('roles') else ['DKBO2', 'DKBO3', 'DKBO4', 'DKBO5']
        return catch_off(roles)
    if a.verify_battle:
        import winenv
        winenv.enable_server()
        return verify_battle(a.roles.split(','))
    if a.unlock:
        import winenv
        winenv.enable_server()
        return unlock(a.roles.split(','), tuple(w for w in ('騎寵', '戰寵') if w in a.unlock))
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
    return run(assign, a.count, tuple(a.stages.split(',')), a.dry_run, timeout=a.timeout, poll=a.poll, reuse_setup=a.reuse_setup)


if __name__ == '__main__':
    sys.exit(main())
