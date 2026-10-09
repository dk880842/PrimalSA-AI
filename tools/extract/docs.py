# -*- coding: utf-8 -*-
"""由 knowledge/data（tables/*.jsonl、enums.tsv、mapinfo.json、bundles.tsv）產生分類 Markdown 知識庫。
可單獨執行：python tools/extract/docs.py [knowledge 路徑]"""
import os, sys, json, re, glob, collections, datetime

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))

# ---------------- 常數 / 對照 ----------------
ITEM_TYPE = {0: '拳套', 1: '斧', 2: '棍', 3: '槍', 4: '弓', 6: '頭盔', 7: '鎧甲', 8: '手環', 9: '樂器', 10: '項鍊', 11: '戒指',
             13: '耳環', 15: '護身符', 16: '其他道具', 17: '迴旋鏢', 18: '投擲斧', 19: '投擲石', 20: '藥品料理', 21: '材料', 22: '寶石',
             23: '行李', 24: '腰帶', 25: '盾', 26: '鞋', 27: '手套', 29: '特殊29', 30: '特殊30', 31: '寵物頭飾', 32: '寵物牙', 33: '寵物爪',
             34: '寵物鎧', 35: '寵物背飾', 36: '寵物翼', 37: '寵物鞋', 100: '任務道具', 500: '儲值', 600: '寵物裝備',
             601: '寵物陣法(地)', 602: '寵物陣法(水)', 603: '寵物陣法(火)', 604: '寵物陣法(風)', 606: '寵物銘文'}
# 道具分類檔（類型 → 檔名, 標題）
ITEM_GROUPS = [
    ('weapons', '武器', [0, 1, 2, 3, 4, 17, 18, 19]),
    ('armor', '防具（頭盔 / 鎧甲 / 盾 / 鞋 / 手套 / 腰帶）', [6, 7, 24, 25, 26, 27]),
    ('accessories', '飾品（手環 / 樂器 / 項鍊 / 戒指 / 耳環 / 護身符）', [8, 9, 10, 11, 13, 15]),
    ('consumables', '藥品 / 料理', [20]),
    ('materials', '材料 / 寶石 / 行李', [21, 22, 23]),
    ('pet-equipment', '寵物裝備 / 陣法', [31, 32, 33, 34, 35, 36, 37, 600, 601, 602, 603, 604, 606]),
    ('quest-items', '任務道具', [100]),
    ('misc', '其他道具（卷軸、蛋、禮包、經驗果、活動道具…）', None),   # 其餘全部
]
QUALITY = ['灰', '白', '綠', '藍', '紫', '橙', '紅']
CURRENCY = {0: '', 1: '鑽石', 2: '金幣', 3: '石幣', 8: '綁定鑽石', 10: '活躍度', 11: '積分'}
TASK_TYPE = {1: '主線', 2: '支線', 3: '引導', 4: '每日', 5: '副本', 6: '突襲', 7: '職業/轉生', 8: '新手', 9: '家族任務1', 10: '家族任務2', 11: '家族任務3'}
MAP_TYPE = {1: '一般場景', 2: '副本/迷宮', 3: 'PVP', 4: '活動', 5: '家族', 6: '家族戰'}
STAT = [('physicalAttack', '攻'), ('physicalDefense', '防'), ('agile', '敏'), ('hp', 'HP'), ('mp', 'MP'), ('sp', 'SP'), ('luck', '運'),
        ('charm', '魅'), ('physicalDodge', '閃避'), ('physicalCrit', '爆擊'), ('attackCount', '攻擊次數'),
        ('poisonResist', '抗毒'), ('paralysisResist', '抗麻'), ('sleepResist', '抗睡'), ('stoneResist', '抗石'), ('drunkResist', '抗醉'),
        ('chaosResist', '抗亂'), ('dizzinessResist', '抗暈'), ('barrierResist', '抗結界')]
FIX = [('physicalHitFix', '命中'), ('blockFix', '格擋'), ('enemyRateUpFix', '遇敵率')]
ELEM = ['地', '水', '火', '風']
PET_TYPE_LANG = 200000019
NPC_FUNC = {'fightBattle': '戰鬥', 'taskFinish': '任務完成', 'taskBattle': '任務戰鬥', 'transferRole': '傳送', 'taskAccept': '接任務',
            'itemPetCompose': '道具/寵物合成', 'killPet': '寵物獻祭', 'NpcAnwser': '問答', 'npcFightTimesGet': '限次戰鬥',
            'farJoinTeam': '遠端組隊', 'transmigraPet': '寵物轉生', 'enterDungeo': '進入副本', 'joinAirPlan': '搭乘飛行/交通',
            'petRecycle': '寵物回收', 'newItemMake': '道具製作', 'npcTimesGet': '限次領取', 'itemShopSell': '道具收購',
            'savePoint': '記錄點', 'reserveHpMp': '補血補氣', 'swapSpiritStone': '交換精靈石', 'openItemDepot': '道具倉庫',
            'openPetDepot': '寵物倉庫', 'studyPetSkill': '學寵物技能', 'studyRideLevel': '學騎乘', 'petFusion': '寵物融合',
            'itemUp': '道具強化', 'watchVideos': '看錄影', 'pkSystem': 'PK 系統', 'kangxingCheck': '抗性檢查',
            'petTransBeforeInfo': '寵物轉生資訊', 'addLuckBuff': '加運氣 Buff', 'addBeautyBuff': '加魅力 Buff', 'pickupPetNpc': '領寵'}

BUNDLE_DESC = {
    'mapdata': ('地圖資料（LS2MAP：寬高、地面層、物件層）', '地圖'), 'mapbg': ('地圖背景大圖', '地圖'), 'mapbuild': ('地圖建築 / 物件圖素', '地圖'),
    'maptile': ('地圖地面圖素', '地圖'), 'mapbuilding': ('地圖建築預製物', '地圖'), 'tx': ('地圖特效', '地圖'), 'warp': ('傳送點特效', '地圖'),
    'warppoint': ('傳送點', '地圖'), 'warppointpub': ('傳送點(公用)', '地圖'), 'weathersystem': ('天氣系統', '地圖'),
    'char': ('角色 / 寵物 / 怪物 / NPC 影格圖（char{圖號}）', '角色'), 'chardata': ('48 種基本人物的動畫表 / 位移表', '角色'),
    'roletile': ('角色動畫影格', '角色'), 'rolenormal': ('地圖上的角色預製物', '角色'), 'rolebattle': ('戰鬥中的角色預製物', '角色'),
    'chname': ('稱號 / 名稱特效', '角色'), 'twname': ('稱號特效', '角色'), 'newarua': ('光環特效', '角色'), 'newtail': ('拖尾特效', '角色'),
    'headicon': ('寵物 / 角色頭像（Sprite 名 = Monster.imageId）', '圖示'), 'itemalt': ('道具圖示（Sprite 名 = Item.imageId）', '圖示'),
    'itemaltlist': ('imageId 範圍 → itemalt bundle 對照', '圖示'), 'skillicon': ('技能圖示', '圖示'), 'petstaticpic': ('寵物立繪', '圖示'),
    'npcstaticpic': ('NPC 立繪', '圖示'), 'petgroupicon': ('寵物系別圖示', '圖示'), 'itemtypeicon': ('道具類型圖示', '圖示'),
    'emojiicon': ('聊天表情', '圖示'), 'chaticon': ('聊天圖示', '圖示'), 'numbericon': ('數字圖', '圖示'), 'ui': ('UI 圖示', '圖示'),
    'uispr': ('UI 圖集', '介面'), 'gsound': ('音效', '音效'), 'bgm': ('背景音樂', '音效'), 'synsound': ('合成音效', '音效'), 'lotterysound': ('抽獎音效', '音效'),
    'pe': ('粒子特效', '特效'), 'particle': ('粒子特效', '特效'), 'particlefx': ('粒子特效', '特效'), 'battlemagiceffect': ('戰鬥魔法特效', '特效'),
    'configs': ('**全部設定表**（Tabtoy 二進位，TextAsset `Configs`）', '程式/資料'),
    'hotupdate.dll': ('熱更新程式 HotUpdate.dll（遊戲邏輯，HybridCLR）', '程式/資料'), 'hofix': ('熱更新依賴的 .NET 組件', '程式/資料'),
    'randombadgedata': ('隨機徽章像素資料', '程式/資料'), 'fontskorean': ('韓文字型', '介面'), 'MD5': ('bundle 校驗清單', '程式/資料'),
}

UI_MEANING = {
    'bagpanel': '背包', 'battlehome': '戰鬥主介面（指令列）', 'battleselectskill': '戰鬥選技能', 'battleselectitem': '戰鬥選道具',
    'battleselectride': '戰鬥選騎寵', 'battlecmdselectprompt': '戰鬥指令提示', 'battleteam': '戰鬥隊伍', 'battleroleinfo': '戰鬥角色資訊',
    'petpanel': '寵物面板', 'petinfo': '寵物資訊', 'petselect': '選寵物', 'petskillstore': '寵物技能店', 'petgrow': '寵物成長',
    'newpetgrow': '寵物成長(新)', 'petgem': '寵物寶石', 'petzhufu': '寵物祝福', 'petguanhuaninfo': '寵物光環資訊', 'petzootime': '寵物園時間',
    'roleinfo': '角色資訊', 'newrole': '角色(新)', 'setproperty': '配點', 'zidongjiadian': '自動加點', 'roleattrimport': '屬性方案',
    'propertyconvert': '屬性轉換', 'resetelement': '重置屬性', 'home': '主畫面', 'navigate': '導航', 'newmaptransfer': '地圖傳送',
    'taskinfo': '任務資訊', 'meirirenwu': '每日任務', 'npcdialog': 'NPC 對話', 'npcanswer': 'NPC 問答（含防腳本驗證）',
    'npccommonstore': 'NPC 商店', 'newstore': '商城', 'commonshop': '通用商店', 'trading': '交易', 'tradingwarehouse': '交易倉庫',
    'tradinginput': '交易輸入', 'bourse': '交易所', 'negotiate': '交涉', 'hecheng': '合成', 'hechengbeibao': '合成背包',
    'cailiaohecheng': '材料合成', 'cailiaotujian': '材料圖鑑', 'cailiaofangru': '放入材料', 'duihuan': '兌換', 'duihuanfangru': '兌換放入',
    'itemqianghua': '道具強化', 'selectqianghua': '選擇強化', 'itemgem': '道具寶石', 'itemequip': '裝備', 'itemdetails': '道具詳情',
    'installinscription': '安裝銘文', 'ronghe': '融合', 'ronghemoni': '融合模擬', 'huishoupet': '回收寵物', 'sacrificepet': '獻祭寵物',
    'huilu': '回爐', 'huilutips': '回爐提示', 'learningskills': '學習技能', 'delskill': '刪除技能', 'extractskills': '抽取技能',
    'commonskill': '通用技能', 'lottery': '抽獎', 'lotterybag': '抽獎背包', 'lotterybuy': '抽獎購買', 'lotteryresult': '抽獎結果',
    'family': '家族', 'familypanel': '家族面板', 'familymanorpanel': '莊園', 'clanwars': '族戰', 'createfamily': '建立家族',
    'newteam': '隊伍', 'fastteam': '快速組隊', 'teaminvita': '組隊邀請', 'teammenu': '隊伍選單', 'chatpanel': '聊天', 'chateasy': '簡易聊天',
    'newmail': '郵件', 'message': '訊息', 'goodfriendblacklist': '好友 / 黑名單', 'friendinfo': '好友資訊', 'setting': '設定',
    'newlogin': '登入', 'logininput': '登入輸入', 'newcreaterole': '建立角色', 'roleselector': '選角色', 'switchrole': '切換角色（多角色同時登入）',
    'loading': '載入', 'maploading': '地圖載入', 'netloading': '網路載入', 'netmsg': '網路訊息', 'confirmmsgbox': '確認框',
    'tipmsgbox': '提示框', 'inputmsgbox': '輸入框', 'inputnumberpopup': '數量輸入', 'getitem': '獲得道具', 'getmultitem': '獲得多個道具',
    'newmeiriqiandao': '每日簽到', 'growth': '成長', 'newgrowth': '成長(新)', 'billboard': '排行榜', 'record': '錄影', 'pkwars': 'PK 戰',
    'pkdasai': 'PK 大賽', 'newluandou': '亂鬥', 'meleetime': '亂鬥時間', 'riding': '騎乘', 'selectriding': '選騎寵', 'rideinfo': '騎寵資訊',
    'newzhuangban': '裝扮', 'appearancepreview': '外觀預覽', 'buff': 'Buff', 'buffinfo': 'Buff 資訊', 'kangxinxianshi': '抗性顯示',
    'modifier': '修改器（外掛相關？）', 'wukai': '無卡', 'jisuanqi': '計算機', 'zhihuidou': '智慧豆', 'newspaper': '報紙/公告',
    'bulletin': '公告', 'hongbao': '紅包', 'statement': '聲明', 'useragreement': '用戶協議', 'versionupdater': '版本更新',
    'newstonepay': '儲值', 'paychoosenew': '選擇儲值', 'cdkey': '序號兌換', 'fanyi': '翻譯', 'functions': '功能選單', 'lock': '鎖定',
    'sameitemselecter': '選擇同類道具', 'selectpet': '選寵物', 'selectitemmsgbox': '選道具', 'putinpet': '放入寵物', 'feedmm': '餵養 MM',
    'nourish': '培養', 'swapspiritstone': '交換精靈石', 'selectweiyang': '選擇餵養', 'currency': '貨幣', 'svrpanel': '伺服器列表',
    'topcenter': '頂部中央提示', 'xiala': '下拉選單', 'lianchonghuodong': '連儲活動', 'levelingactivity': '練等活動', 'activelog': '活躍度',
    'activepopup': '活動彈窗', 'getactivitypet': '活動寵物', 'onekeylogin': '一鍵登入', 'newaccountlogininfo': '帳號登入資訊',
}

# ---------------- 讀資料 ----------------
class DB:
    def __init__(self, kdir):
        self.kdir = kdir
        self.data = os.path.join(kdir, 'data')
        self.T = {}
        for f in glob.glob(os.path.join(self.data, 'tables', '*.jsonl')):
            name = os.path.splitext(os.path.basename(f))[0]
            self.T[name] = [json.loads(l) for l in open(f, encoding='utf-8') if l.strip()]
        self.lang = {}
        for r in self.t('NewLanguage'):
            self.lang[r['ID']] = (j(r.get('tcn') or r.get('scn')), j(r.get('krn')))
        for r in self.t('NewLanguagePublic'):
            self.lang[r['ID']] = (r.get('StrTn') or r.get('StrCn') or '', r.get('StrKrn') or '')
        self.items = {r['ID']: r for r in self.t('Item')}
        self.mons = {r['ID']: r for r in self.t('Monster')}
        self.npcs = {r['ID']: r for r in self.t('Npc')}
        self.maps = {r['ID']: r for r in self.t('MapName')}
        self.sb = {r['ID']: r for r in self.t('SkillBattle')}
        self.skill = {r['ID']: r for r in self.t('Skill')}
        self.scripts = {r['ID']: r for r in self.t('NpcScript')}
        self.status = {r['ID']: r for r in self.t('SkillStatus')}
        try: self.mapinfo = {int(k): v for k, v in json.load(open(os.path.join(self.data, 'mapinfo.json'), encoding='utf-8')).items()}
        except Exception: self.mapinfo = {}
        self.enums = {}
        try:
            for line in open(os.path.join(self.data, 'enums.tsv'), encoding='utf-8-sig'):
                if '\t' in line:
                    k, v = line.rstrip('\r\n').split('\t', 1); self.enums[k] = v
        except Exception: pass

    def t(self, name): return self.T.get(name, [])
    def L(self, i, kr=False):
        if not isinstance(i, int): return ''
        v = self.lang.get(i)
        return (v[1] if kr else v[0]) if v else ''
    def item_name(self, i):
        r = self.items.get(i); return name(r) if r else '#%s' % i
    def mon_name(self, i):
        r = self.mons.get(i); return name(r) if r else '#%s' % i
    def map_name(self, i):
        r = self.maps.get(i)
        n = name(r, 'name', 'Krn') if r else ''
        if not n and i in self.mapinfo: n = self.mapinfo[i].get('headerName', '') + '*'
        return n or '地圖%s' % i
    def npc_name(self, i):
        r = self.npcs.get(i); return name(r) if r else '#%s' % i
    def skill_name(self, sid, lv=1):
        r = self.sb.get(sid * 1000 + (lv or 1)) or self.sb.get(sid)
        return name(r) if r else '技能%s' % sid
    def pos(self, m, x, y):
        return '%s(%s) %s,%s' % (self.map_name(m), m, x, y)

def j(v):
    if v is None: return ''
    if isinstance(v, list): return ''.join(str(x) for x in v)
    return str(v)

def name(r, base='name', krsuf='Kr'):
    if not r: return ''
    return clean(r.get(base + 'Tn') or r.get(base + 'Cn') or '')

def kname(r, base='name'):
    if not r: return ''
    return clean(r.get(base + 'Kr') or r.get(base + 'Krn') or '')

def clean(s):
    if s is None: return ''
    if isinstance(s, list): s = ''.join(str(x) for x in s)
    s = str(s).replace('\\n', ' ').replace('\r', ' ').replace('\n', ' ')
    s = re.sub(r'</?(color|size|b|i)[^>]*>', '', s)
    return s.strip()

def cell(s):
    return clean(s).replace('|', '｜') if s not in (None, '') else ''

def table(head, rows):
    out = ['| ' + ' | '.join(head) + ' |', '|' + '---|' * len(head)]
    for r in rows:
        out.append('| ' + ' | '.join(cell(x) if not isinstance(x, (int, float)) else str(x) for x in r) + ' |')
    return '\n'.join(out) + '\n'

class Writer:
    def __init__(self, kdir):
        self.kdir = kdir; self.files = []
    def write(self, rel, title, body, desc=''):
        p = os.path.join(self.kdir, rel.replace('/', os.sep))
        os.makedirs(os.path.dirname(p), exist_ok=True)
        head = '# %s\n\n' % title
        if desc: head += '> %s\n\n' % desc
        with open(p, 'w', encoding='utf-8', newline='\n') as f:
            f.write(head + body)
        self.files.append((rel, title, desc))

def chunks(lst, n):
    for i in range(0, len(lst), n): yield i // n, lst[i:i + n]

def cur(t, v):
    return '%s %s' % (v, CURRENCY.get(t, '貨幣%s' % t)) if t else str(v)

def reward_text(db, lst):
    out = []
    for x in lst or []:
        if not isinstance(x, dict): continue
        if x.get('itemId'): out.append('%s×%d' % (db.item_name(x['itemId']), x.get('itemNum', 1)))
        if x.get('petId'): out.append('寵物 %s' % db.mon_name(x['petId']))
        if x.get('currencyType'): out.append(cur(x['currencyType'], x.get('currencyValue', 0)))
        for k, lab in (('exp', '經驗'), ('stone', '石幣'), ('lockDenar', '綁定鑽石'), ('transAdd', '轉生+'), ('skinStr', '外觀'), ('aruaStr', '光環')):
            if x.get(k): out.append('%s %s' % (lab, x[k]))
        if x.get('partnerId'): out.append('夥伴')
    return '、'.join(out)

def req_text(db, lst):
    out = []
    for x in lst or []:
        if not isinstance(x, dict): continue
        if x.get('itemId'): out.append('%s(%d)×%d' % (db.item_name(x['itemId']), x['itemId'], x.get('itemNum', 1)))
        if x.get('petId'): out.append('寵物 %s(%d)×%d' % (db.mon_name(x['petId']), x['petId'], x.get('petNum', 1)))
        if x.get('currencyType'): out.append(cur(x['currencyType'], x.get('currencyValue', 0)))
    return '、'.join(out)

# ---------------- 道具 ----------------
def item_stats(r):
    st = []
    for k, lab in STAT:
        a, b = r.get(k + 'Min', 0), r.get(k + 'Max', 0)
        if a or b: st.append('%s%s' % (lab, ('%+d' % a) if a == b else '%+d~%+d' % (a, b)))
    for k, lab in FIX:
        if r.get(k): st.append('%s%+d' % (lab, r[k]))
    return ' '.join(st)

def elem_text(d):
    v = [d.get('earth', 0), d.get('water', 0), d.get('fire', 0), d.get('wind', 0)]
    return ' '.join('%s%s' % (ELEM[i], v[i]) for i in range(4) if v[i])

def build_items(db, w):
    # 交叉索引：販售 NPC、合成來源
    sellers = collections.defaultdict(list)
    for n in db.t('Npc'):
        for a in n.get('npcArgs', []) or []:
            if a.get('itemId'): sellers[a['itemId']].append(n)
    made = collections.defaultdict(list)
    for r in db.t('ExchangeItem'):
        if r.get('targetId'): made[r['targetId']].append('合成#%d' % r['ID'])
    for r in db.t('ItemBook'):
        if r.get('itemId') and r.get('needItem'): made[r['itemId']].append('圖鑑#%d' % r['ID'])
    rows_by = collections.defaultdict(list)
    used = set(t for _, _, ts in ITEM_GROUPS if ts for t in ts)
    for r in db.t('Item'):
        ty = r.get('type', 0)
        g = next((slug for slug, _, ts in ITEM_GROUPS if ts and ty in ts), 'misc')
        rows_by[g].append(r)
    idx = []
    for slug, title, ts in ITEM_GROUPS:
        rows = sorted(rows_by[slug], key=lambda r: (r.get('type', 0), r['ID']))
        parts = []
        bytype = collections.OrderedDict()
        for r in rows: bytype.setdefault(r.get('type', 0), []).append(r)
        for ty, rs in bytype.items():
            tr = []
            for r in rs:
                lim = []
                if r.get('level'): lim.append('Lv%d' % r['level'])
                if r.get('transLimit'): lim.append('%d轉' % r['transLimit'])
                if r.get('levelLimit'): lim.append('Lv' + '/'.join(map(str, r['levelLimit'])))
                sk = '、'.join(db.skill_name(s['skillId'], s.get('skillLevel', 1)) for s in r.get('skill', []) or [] if s.get('skillId'))
                src = []
                if r['ID'] in sellers: src.append('NPC販售:' + '、'.join(sorted({name(n) for n in sellers[r['ID']]}))[:60])
                if r['ID'] in made: src.append('/'.join(made[r['ID']][:3]))
                tr.append([r['ID'], name(r), kname(r), QUALITY[r['quality']] if isinstance(r.get('quality'), int) and r['quality'] < 7 else '',
                           ' '.join(lim), item_stats(r), elem_text(r), sk, clean(r.get('descriptionTn') or r.get('descriptionCn'))[:160],
                           ' '.join(src)])
            parts.append('## %s（type=%d，%d 件）\n\n' % (ITEM_TYPE.get(ty, '類型%d' % ty), ty, len(rs)) +
                         table(['ID', '名稱', '韓文', '品質', '需求', '能力', '屬性', '附帶技能', '說明', '取得'], tr))
        w.write('items/%s.md' % slug, '道具：%s' % title, '\n'.join(parts),
                '共 %d 件。能力欄：攻/防/敏/HP/MP/運/魅/閃避/爆擊/抗性；「取得」= NPC 販售或合成/圖鑑配方（細節見 crafting/、economy/npc-shops.md）。' % len(rows))
        idx.append((slug, title, len(rows), sorted({ITEM_TYPE.get(r.get('type', 0), str(r.get('type'))) for r in rows})))
    # 套裝
    tr = []
    for r in db.t('Suit'):
        items = [db.item_name(x) for x in r.get('allSuit', []) or []]
        ef = '；'.join('%d件:%s' % (e.get('suitCount', 0), db.L(e.get('suitDes')) or db.skill_name(e.get('skillId', 0)))
                      for e in r.get('effect', []) or [])
        tr.append([r['ID'], db.L(r.get('name')) or os.path.commonprefix(items), '、'.join(items), ef])
    w.write('items/suits.md', '道具：套裝', table(['ID', '套裝名', '成員', '套裝效果'], tr), '套裝表 Suit，%d 組。' % len(tr))
    body = table(['檔案', '分類', '件數', '包含類型'], [['[%s.md](%s.md)' % (s, s), t, n, '、'.join(ts)] for s, t, n, ts in idx])
    body += '\n- [suits.md](suits.md) 套裝\n\n道具類型代碼（Item.type）：\n\n' + table(['type', '名稱'], sorted(ITEM_TYPE.items()))
    body += '\n品質（Item.quality）：' + '、'.join('%d=%s' % (i, q) for i, q in enumerate(QUALITY)) + '\n'
    w.write('items/README.md', '道具總覽', body, 'Item 表共 %d 件道具，依類型分檔。' % len(db.t('Item')))

# ---------------- 寵物 / 怪物 ----------------
def build_pets(db, w):
    src = {}
    for r in db.t('PetData'):
        for x in r.get('TxtTn', []) or r.get('TxtCn', []) or []:
            if x.get('petId'): src[x['petId']] = clean(x.get('aruaStr'))
    baby = {r['petId']: r for r in db.t('PetBaby') if r.get('petId')}
    ride = collections.defaultdict(list)
    for r in db.t('Ride'):
        if r.get('petId'): ride[r['petId']].append(r)
    def ptn(ty):
        if ty == 100: return 'NPC / 敵方（不可當寵物）'
        return db.L(PET_TYPE_LANG + ty) if 0 <= ty < 30 else ''
    def row(r):
        g = r.get('growArg', {}) or {}
        tot = sum(g.get(k, 0) for k in ('vitArg', 'atkArg', 'defArg', 'dexArg'))
        sk = '、'.join('%s(%d)' % (db.skill_name(s['skillId'], s.get('skillLevel', 1)), s['skillId']) for s in r.get('skills', []) or [] if s.get('skillId'))
        get = []
        if r['ID'] in src: get.append(src[r['ID']])
        if r['ID'] in baby:
            p = baby[r['ID']].get('point', {}) or {}
            get.append('領取:%s' % db.pos(p.get('map'), p.get('x'), p.get('y')))
        return [r['ID'], name(r), kname(r), r.get('quality', 0), '%s/%s' % (g.get('initArg', 0), g.get('levelUpArg', 0)),
                '%s/%s/%s/%s=%d' % (g.get('vitArg', 0), g.get('atkArg', 0), g.get('defArg', 0), g.get('dexArg', 0), tot),
                elem_text(r.get('property', {}) or {}), '可騎' if r['ID'] in ride else '', sk, ' '.join(get), r.get('imageId', '')]
    head = ['ID', '名稱', '韓文', '品質', '初始/每級', '體/腕/耐/速=總檔', '屬性', '騎乘', '天生技能', '取得', '圖號']
    by = collections.defaultdict(list)
    for r in db.t('Monster'): by[r.get('petType', -1)].append(r)
    idx = []
    for ty in sorted(by):
        rs = sorted(by[ty], key=lambda r: r['ID'])
        nm = ptn(ty) or ('未分類' if ty == -1 else '類型%d' % ty)
        if ty == 100:
            for k, part in chunks(rs, 600):
                rel = 'pets/enemies-%d.md' % (k + 1)
                w.write(rel, '怪物 / NPC 戰鬥單位（%d）' % (k + 1), table(head, [row(r) for r in part]),
                        'Monster 表 petType=100：戰鬥中出現的敵人、BOSS、NPC 單位，ID %d ~ %d。' % (part[0]['ID'], part[-1]['ID']))
                idx.append((rel, nm + ' 第%d段' % (k + 1), len(part)))
            continue
        rel = 'pets/type-%s.md' % ('%02d' % ty if ty >= 0 else 'other')
        w.write(rel, '寵物：%s（petType=%d）' % (nm, ty), table(head, [row(r) for r in rs]),
                '同一系別的寵物 / 怪物。成長參數 growArg：初始值 initArg、每級基數 levelUpArg、體腕耐速檔數（總檔越高越強）。')
        idx.append((rel, nm, len(rs)))
    body = table(['檔案', '系別', '數量'], [['[%s](%s)' % (os.path.basename(a), os.path.basename(a)), b, c] for a, b, c in idx])
    body += '''
## 欄位說明
- **體/腕/耐/速**：成長檔（vit/atk/def/dex Arg），加總為「總檔」。四圍公式（來自石器時代社群，未在本遊戲驗證）：
  HP=4體+腕+耐+速、攻=0.1(體+耐)+腕+0.05速、防=0.1(體+腕)+耐+0.05速、敏=速。
- **屬性**：地水火風，合計 100（例：水40 火60）。屬性相剋：地剋水、水剋火、火剋風、風剋地。
- **品質**：0~6（灰白綠藍紫橙紅）。
- 寵物最高等級：Config.petMaxLevel = 140；寵物最多技能數 petSkillMax = 7。
- 其他：[pet-sources.md](pet-sources.md) 取得方式、[ride.md](ride.md) 騎乘、[levels.md](levels.md) 經驗表。
'''
    w.write('pets/README.md', '寵物 / 怪物總覽', body, 'Monster 表 %d 筆（含可捕捉寵物與敵方怪物）。' % len(db.t('Monster')))
    # 取得方式
    out = '## 寵物圖鑑分組（PetData）\n\n'
    tr = []
    for r in db.t('PetData'):
        tr.append([r['ID'], db.L(r.get('GroupName')), '、'.join('%s(%d):%s' % (db.mon_name(x['petId']), x['petId'], clean(x.get('aruaStr')))
                                                          for x in r.get('TxtTn', []) or [] if x.get('petId')), clean(r.get('collectTipTn'))])
    out += table(['ID', '分組', '寵物：取得方式', '收集提示'], tr)
    out += '\n## 寵物領取點（PetBaby）\n\n'
    out += table(['ID', '寵物', '地點', '費用'], [[r['ID'], '%s(%d)' % (db.mon_name(r.get('petId')), r.get('petId', 0)),
        db.pos((r.get('point') or {}).get('map'), (r.get('point') or {}).get('x'), (r.get('point') or {}).get('y')),
        req_text(db, r.get('condtion'))] for r in db.t('PetBaby')])
    out += '\n## 寵物獻祭 / 擊殺（KillPet）\n\n' + table(['ID', '內容'], [[r['ID'], json.dumps({k: v for k, v in r.items() if k != 'ID'}, ensure_ascii=False)] for r in db.t('KillPet')])
    out += '\n## 寵物強化（PetUpList）\n\n' + table(['ID', '吃的道具', '效果'], [[r['ID'], db.item_name(r.get('eatItemId')), json.dumps(r.get('petUpInfo'), ensure_ascii=False)] for r in db.t('PetUpList')])
    out += '\n## 寵物排行加成（PetRankData）\n\n' + table(['寵物', '排名加成'], [['%s(%d)' % (db.mon_name(r['ID']), r['ID']), clean(r.get('lanTn'))] for r in db.t('PetRankData')])
    w.write('pets/pet-sources.md', '寵物取得方式 / 強化', out, '寵物從哪裡來：圖鑑分組來源說明、固定領取點、獻祭與強化。抽獎蛋見 economy/lottery.md。')
    # 騎乘
    tr = []
    for r in db.t('Ride'):
        rt = (r.get('rideType') or {}).get('f8_0', '')
        tr.append([r['ID'], '%s(%s)' % (db.mon_name(r.get('petId')), r.get('petId')), r.get('needlearn', 0), r.get('rule', ''), rt,
                   json.dumps(r.get('rideAttrList'), ensure_ascii=False) if r.get('rideAttrList') else ''])
    w.write('pets/ride.md', '騎乘（Ride）', table(['ID(坐騎圖號)', '寵物', '需學習', '規則', '騎乘動作號', '騎乘屬性'], tr),
            '可騎乘寵物清單。needlearn=1 代表要先在 NPC 學騎乘（NpcScript func=studyRideLevel）。')
    # 經驗
    me = {r['ID']: r.get('exp') for r in db.t('MonsterExp')}
    tr = [[r['ID'], r.get('exp', ''), me.get(r['ID'], '')] for r in db.t('Exp')]
    w.write('pets/levels.md', '等級經驗表', table(['等級', '角色升級經驗(Exp)', '怪物經驗(MonsterExp)'], tr),
            'Exp：角色升到下一級所需經驗；MonsterExp：該等級怪物給的經驗基數。')

# ---------------- 技能 ----------------
def build_skills(db, w):
    tr = []
    for r in sorted(db.t('SkillBattle'), key=lambda r: r['ID']):
        sid, lv = divmod(r['ID'], 1000)
        sk = db.skill.get(sid, {})
        c = r.get('costNum') or {}
        cost = '%s~%s' % (c.get('min', 0), c.get('max', 0)) if c.get('max') else ''
        kind = []
        if sk.get('skillType') == 1: kind.append('物理')
        if sk.get('skillType') == 2: kind.append('魔法')
        if sk.get('isPassive'): kind.append('被動')
        if sk.get('groupMagic') or sk.get('groupPhysical'): kind.append('群體')
        tr.append([r['ID'], sid, lv, name(r), kname(r), ' '.join(kind), cost, clean(r.get('desInfoTn') or r.get('desInfoCn'))[:200]])
    w.write('skills/battle-skills.md', '戰鬥技能（SkillBattle）', table(['ID', 'skillId', '等級', '名稱', '韓文', '類型', 'MP消耗', '說明'], tr),
            'SkillBattle ID = skillId×1000 + 等級；Skill 表（ID = skillId）存類型、是否被動、目標。普通攻擊 / 防禦 / 逃跑等也在此表。')
    tr = []
    for r in sorted(db.t('SkillStatus'), key=lambda r: r['ID']):
        tr.append([r['ID'], name(r), kname(r), {1: 'Buff', 2: 'Debuff', 3: '特殊'}.get(r.get('buffType'), r.get('buffType', '')),
                   clean(r.get('descTn') or r.get('descCn'))[:200]])
    w.write('skills/status-effects.md', '戰鬥狀態 / Buff（SkillStatus）', table(['ID', '名稱', '韓文', '類型', '說明'], tr),
            '戰鬥中身上狀態。錄影 / 記憶體中的 buff 以 type×1000+level 對應本表 ID。異常狀態：毒、麻痺、睡眠、石化、酒醉、混亂、暈眩。')
    tr = [[r['ID'], name(r), kname(r), clean(r.get('desTn') or r.get('desCn')), json.dumps(r.get('buffInfo') or r.get('expBuffInfo') or r.get('attrInfo') or {}, ensure_ascii=False)]
          for r in db.t('RoleBuff')]
    w.write('skills/role-buffs.md', '角色 Buff（RoleBuff，地圖上的增益）', table(['ID', '名稱', '韓文', '說明', '數值'], tr),
            '例如月神守護（降低遇敵率）、經驗加成等，透過道具或 NPC 取得。')
    # NPC 教的技能
    tr = []
    for n in db.t('Npc'):
        for a in n.get('npcArgs', []) or []:
            if a.get('skillId'):
                tr.append([db.skill_name(a['skillId'], a.get('skillLevel', 1)), a['skillId'], a.get('skillLevel', 1), name(n), n['ID'],
                           db.pos(n.get('map'), n.get('x'), n.get('y')), cur(a.get('skillCostType', 3), a.get('skillCost', 0)), a.get('skillRequire', '')])
    tr.sort(key=lambda x: (x[1], x[2]))
    w.write('skills/skill-teachers.md', '技能學習 NPC', table(['技能', 'skillId', '等級', 'NPC', 'NPC ID', '位置', '費用', '需求'], tr),
            '從 Npc.npcArgs 的 skillId 整理：哪個 NPC 教哪個技能（多半是寵物技能店）。')
    tr = [[r['ID'], r.get('group'), r.get('level'), ' '.join('%s=%s' % (k, v) for k, v in r.items() if k.endswith('Fix') and v)] for r in db.t('SkillAttr')]
    w.write('skills/skill-attr.md', '技能屬性加成（SkillAttr）', table(['ID', 'group', '等級', '加成'], tr), '被動技能 / 光環等提供的屬性加成。')
    body = '''- [battle-skills.md](battle-skills.md) 全部戰鬥技能（含寵物技能、精靈魔法、普攻/防禦/逃跑）
- [status-effects.md](status-effects.md) 戰鬥狀態 / Buff / Debuff
- [role-buffs.md](role-buffs.md) 角色地圖 Buff（遇敵率、經驗…）
- [skill-teachers.md](skill-teachers.md) 哪個 NPC 教什麼技能
- [skill-attr.md](skill-attr.md) 技能屬性加成

戰鬥指令（EBattleCmdType）：1 攻擊、2 技能、3 捕捉、4 道具、5 防禦、6 換騎寵、7 逃跑。
戰場屬性（BattleField）：0 無、1 地、2 水、3 火、4 風；結界（BattleBorder）：1 物理、2 魔法。
技能消耗類型（SkillCostType）：101 HP、102 HP%、201 MP、202 MP%、301 SP、302 SP%。
'''
    w.write('skills/README.md', '技能總覽', body)

# ---------------- 世界：地圖 / NPC / 傳送 ----------------
def build_world(db, w):
    npc_by_map = collections.defaultdict(list)
    for n in db.t('Npc'): npc_by_map[n.get('map')].append(n)
    warps_from = collections.defaultdict(list)
    for r in db.t('MapWarp'):
        if not r.get('isNotUse'): warps_from[r.get('fMap')].append(r)
    ids = sorted(set(db.maps) | set(db.mapinfo))
    tr = []
    for m in ids:
        r = db.maps.get(m, {}); mi = db.mapinfo.get(m, {})
        tr.append([m, db.map_name(m), kname(r), MAP_TYPE.get(r.get('type'), r.get('type', '')), '%sx%s' % (mi.get('w', '?'), mi.get('h', '?')) if mi else '',
                   len(npc_by_map.get(m, [])), len(warps_from.get(m, [])), '有' if r.get('banSkillList') else ''])
    w.write('world/maps.md', '地圖一覽', table(['ID', '名稱', '韓文', '類型', '大小(寬x高)', 'NPC數', '出口數', '禁技能'], tr),
            'MapName + mapdata 合併。名稱後有 * 表示設定表沒有名稱、用地圖檔頭的範本名（可能不準）。通行格在 data/maps.bin（用 tools/query/psa.py grid/route 查）。')
    # 出口
    out = []
    for m in sorted(warps_from):
        lines = ['- (%s,%s) → %s' % (r.get('fX'), r.get('fY'), db.pos(r.get('tMap'), r.get('tX'), r.get('tY')))
                 for r in sorted(warps_from[m], key=lambda r: (r.get('tMap', 0), r.get('fX', 0), r.get('fY', 0)))]
        out.append('## %s (%s)\n' % (db.map_name(m), m) + '\n'.join(lines) + '\n')
    w.write('world/warps.md', '地圖出口 / 傳送點（MapWarp）', '\n'.join(out),
            '依出發地圖分組：站在 (x,y) 會被傳送到目的地圖座標。共 %d 個。跨地圖路線可用 tools/query/psa.py route。' % sum(map(len, warps_from.values())))
    # NPC（依地圖分檔）
    maps_sorted = sorted(npc_by_map, key=lambda m: (m is None, m or 0))
    groups = []; cur_g = []; cnt = 0
    for m in maps_sorted:
        cur_g.append(m); cnt += len(npc_by_map[m])
        if cnt >= 500: groups.append(cur_g); cur_g = []; cnt = 0
    if cur_g: groups.append(cur_g)
    idx = []
    for gi, ms in enumerate(groups):
        out = []
        for m in ms:
            lines = []
            for n in sorted(npc_by_map[m], key=lambda n: n['ID']):
                info = []
                sells = [a for a in n.get('npcArgs', []) or [] if a.get('itemId') and a.get('price') is not None]
                if sells: info.append('販售: ' + '、'.join('%s(%d) %s' % (db.item_name(a['itemId']), a['itemId'], cur(a.get('currency', 3), a.get('price', 0))) for a in sells[:40]) + (' …共%d項' % len(sells) if len(sells) > 40 else ''))
                sks = [a for a in n.get('npcArgs', []) or [] if a.get('skillId')]
                if sks: info.append('教技能: ' + '、'.join('%s Lv%d %s' % (db.skill_name(a['skillId'], a.get('skillLevel', 1)), a.get('skillLevel', 1), cur(a.get('skillCostType', 3), a.get('skillCost', 0))) for a in sks))
                scs = [db.scripts[s] for s in n.get('script', []) or [] if s in db.scripts]
                if scs: info.append('功能: ' + '、'.join('%s[%s](腳本%d)' % (name(s), NPC_FUNC.get((s.get('script') or {}).get('func'), (s.get('script') or {}).get('func', '')), s['ID']) for s in scs))
                if n.get('airBusWay'): info.append('交通路線: ' + ' → '.join(db.pos(p.get('map'), p.get('x'), p.get('y')) for p in n['airBusWay'][:6]))
                if n.get('openUIName'): info.append('開啟介面: ' + n['openUIName'])
                if n.get('beginTask'): info.append('起始任務: ' + '、'.join(str(t.get('taskId')) for t in n['beginTask']))
                msg = clean(n.get('defaultMsgTw') or n.get('defaultMsg'))
                if msg: info.append('對話: 「%s」' % msg[:120])
                vis = '' if n.get('visable', 1) else '（隱藏）'
                lines.append('- **%s**%s (ID %d, %s / %s) @ (%s,%s)%s' % (name(n) or '(無名)', vis, n['ID'], kname(n), n.get('imageId', ''), n.get('x'), n.get('y'),
                             ''.join('\n  - ' + x for x in info)))
            out.append('## %s (%s)\n\n' % (db.map_name(m), m) + '\n'.join(lines) + '\n')
        rel = 'world/npcs-%02d.md' % (gi + 1)
        w.write(rel, 'NPC（地圖 %s ~ %s）' % (ms[0], ms[-1]), '\n'.join(out), '依地圖分組列出 NPC：位置、販售、教技能、功能腳本、交通路線、預設對話。')
        idx.append([('[%s](%s)' % (os.path.basename(rel), os.path.basename(rel))), '%s ~ %s' % (ms[0], ms[-1]),
                    '、'.join(db.map_name(m) for m in ms[:8]) + ('…' if len(ms) > 8 else '')])
    # 傳送服務
    out = '## 城鎮傳送（Transfer）\n\n' + table(['ID', '分組', '名稱', '目的地', '條件'], [[r['ID'], r.get('group'), db.L(r.get('nameId')),
        db.pos((r.get('point') or {}).get('map'), (r.get('point') or {}).get('x'), (r.get('point') or {}).get('y')),
        json.dumps(r.get('condtion'), ensure_ascii=False) if r.get('condtion') else ''] for r in db.t('Transfer')])
    out += '\n## 付費傳送（OtherTransfer）\n\n' + table(['ID', '名稱', '目的地', '費用'], [[r['ID'], db.L(r.get('name')),
        db.pos((r.get('point') or {}).get('map'), (r.get('point') or {}).get('x'), (r.get('point') or {}).get('y')), req_text(db, r.get('condtion'))] for r in db.t('OtherTransfer')])
    tr = []
    for n in db.t('Npc'):
        if n.get('airBusWay'):
            arg = n.get('airBusArg') or {}
            tr.append([n['ID'], name(n), db.pos(n.get('map'), n.get('x'), n.get('y')), ' → '.join(db.pos(p.get('map'), p.get('x'), p.get('y')) for p in n['airBusWay'][:8]),
                       '%s石幣 等待%s秒' % (arg.get('needstone', ''), arg.get('waittime', '')) if arg else ''])
    out += '\n## 交通 NPC（airBusWay：船 / 飛行）\n\n' + table(['NPC ID', 'NPC', '位置', '路線', '費用'], tr)
    out += '\n## 莊園（ManorSet）\n\n' + table(['ID', '名稱', '傳送點'], [[r['ID'], db.L(r.get('manorName')), db.pos((r.get('warpPoint') or {}).get('map'), (r.get('warpPoint') or {}).get('x'), (r.get('warpPoint') or {}).get('y'))] for r in db.t('ManorSet')])
    out += '\n## 挖寶點（DigTreasure）\n\n' + table(['ID', '名稱', '位置', '類型'], [[r['ID'], db.L(r.get('name')), db.pos((r.get('pos') or {}).get('map'), (r.get('pos') or {}).get('x'), (r.get('pos') or {}).get('y')), r.get('type', '')] for r in db.t('DigTreasure')])
    out += '\n## 地圖限制（TeamCountLimit）\n\n' + table(['地圖', '限制'], [['%s(%s)' % (db.map_name(r['ID']), r['ID']), ' '.join(k for k, v in r.items() if k != 'ID' and v)] for r in db.t('TeamCountLimit')])
    w.write('world/transport.md', '交通 / 傳送服務 / 莊園 / 挖寶', out, '除了地圖出口以外的移動方式。')
    body = '''- [maps.md](maps.md) 全部地圖（ID、名稱、韓文、類型、大小、NPC 數、出口數）
- [warps.md](warps.md) 每張地圖的出口座標與目的地
- [transport.md](transport.md) 城鎮傳送、付費傳送、船 / 飛行交通、莊園、挖寶點、地圖限制
- NPC（依地圖 ID 分檔）：

''' + table(['檔案', '地圖 ID 範圍', '包含地圖（前幾個）'], idx) + '''
## 座標系
- 地圖格子座標 (x, y)，原點左上；畫面是斜角（x 往右上、y 往右下）。
- 通行格：data/maps.bin，格子值 0=無地面 1=可通行 2=不可通行地面(水/懸崖) 3=物件阻擋。
- 方向（DirEnum）：0 下、1 左下、2 左、3 左上、4 上、5 右上、6 右、7 右下。
- NPC 常站在櫃檯後方，走到 NPC 3 格內即可對話。
'''
    w.write('world/README.md', '世界：地圖 / NPC / 傳送總覽', body, '地圖 %d 張、NPC %d 個、出口 %d 個。' % (len(ids), len(db.t('Npc')), len(db.t('MapWarp'))))

# ---------------- 任務 ----------------
def build_quests(db, w):
    tr = [[r['ID'], name(r), kname(r), clean(r.get('explanTn') or r.get('explanCn')), reward_text(db, r.get('reward'))] for r in db.t('TaskExplan')]
    w.write('quests/guides.md', '任務攻略說明（TaskExplan）', table(['ID', '名稱', '韓文', '說明', '獎勵'], tr), '主要任務鏈的攻略說明（成人儀式、轉生等）。')
    by = collections.defaultdict(list)
    for r in db.t('Task'): by[r.get('group', 0)].append(r)
    out = []
    for g in sorted(by):
        rs = sorted(by[g], key=lambda r: (r.get('step', 0), r['ID']))
        out.append('## 任務組 %s：%s（%s）\n' % (g, name(rs[0]), TASK_TYPE.get(rs[0].get('type'), rs[0].get('type'))))
        for r in rs:
            cond = []
            for c in r.get('condition', []) or []:
                if c.get('level'): cond.append('等級≥%d' % c['level'])
                if c.get('trans'): cond.append('轉生≥%d' % c['trans'])
                if c.get('itemId'): cond.append('%s(%d)×%d' % (db.item_name(c['itemId']), c['itemId'], c.get('itemNum', 1)))
                if c.get('petId'): cond.append('寵物%s(%d) Lv%d+' % (db.mon_name(c['petId']), c['petId'], c.get('petLevel', 1)))
                if c.get('monsterId'): cond.append('打倒%s(%d)×%d' % (db.mon_name(c['monsterId']), c['monsterId'], c.get('monsterNum', 1)))
                if c.get('stone'): cond.append('石幣%d' % c['stone'])
                if c.get('fightCount'): cond.append('戰鬥%d次' % c['fightCount'])
            fc = (r.get('conditionEx') or {}).get('fightCount')
            if fc: cond.append('戰鬥%d次' % fc)
            nav = r.get('taskNavigate') or []
            sn = db.npcs.get(r.get('startNpc')); en = db.npcs.get(r.get('endNpc'))
            lines = ['### %d. %s (ID %d)%s' % (r.get('step', 0), name(r), r['ID'], ' ★重要' if r.get('isImportant') else '')]
            ex = clean(r.get('explandTn') or r.get('explandCn'))
            if ex: lines.append('- 說明：%s' % ex)
            if sn: lines.append('- 接取：%s(NPC %d) @ %s' % (name(sn), sn['ID'], db.pos(sn.get('map'), sn.get('x'), sn.get('y'))))
            if en: lines.append('- 回報：%s(NPC %d) @ %s' % (name(en), en['ID'], db.pos(en.get('map'), en.get('x'), en.get('y'))))
            if nav: lines.append('- 導航終點：%s（導航路徑 %d 點）' % (db.pos(nav[-1].get('map'), nav[-1].get('x'), nav[-1].get('y')), len(nav)))
            if cond: lines.append('- 條件：' + '、'.join(cond))
            if r.get('waitItem'): lines.append('- 需要道具：' + req_text(db, r['waitItem']))
            rw = reward_text(db, r.get('reward'))
            if rw: lines.append('- 獎勵：' + rw)
            if r.get('randomItemReward'): lines.append('- 隨機獎勵：' + reward_text(db, r['randomItemReward']))
            if r.get('finishTasks'): lines.append('- 前置任務：' + '、'.join(map(str, r['finishTasks'])))
            if r.get('loop'): lines.append('- 可重複')
            out.append('\n'.join(lines) + '\n')
    w.write('quests/tasks.md', '任務鏈（Task）', '\n'.join(out), 'Task 表 %d 步，依任務組(group)與步驟排列。類型：%s。' % (len(db.t('Task')), '、'.join('%d=%s' % kv for kv in TASK_TYPE.items())))
    # NPC 腳本
    npc_of = collections.defaultdict(list)
    for n in db.t('Npc'):
        for s in n.get('script', []) or []: npc_of[s].append(n)
    rs = sorted(db.t('NpcScript'), key=lambda r: r['ID'])
    idx = []
    for k, part in chunks(rs, 350):
        out = []
        for r in part:
            sc = r.get('script') or {}
            func = sc.get('func', '')
            lines = ['### 腳本 %d：%s（%s）' % (r['ID'], name(r), NPC_FUNC.get(func, func))]
            ns = npc_of.get(r['ID'])
            if ns: lines.append('- NPC：' + '、'.join('%s(%d) @ %s' % (name(n), n['ID'], db.pos(n.get('map'), n.get('x'), n.get('y'))) for n in ns[:5]))
            extra = {kk: v for kk, v in sc.items() if kk not in ('func',)}
            if extra.get('map'): lines.append('- 目的地 / 地點：%s' % db.pos(extra.get('map'), extra.get('x'), extra.get('y')))
            other = {kk: v for kk, v in extra.items() if kk not in ('map', 'x', 'y')}
            if other: lines.append('- 參數：' + json.dumps(other, ensure_ascii=False))
            if r.get('needList'): lines.append('- 需求：' + json.dumps(r['needList'], ensure_ascii=False))
            if r.get('anwserinfo'): lines.append('- 選項參數：' + json.dumps(r['anwserinfo'], ensure_ascii=False)[:400])
            for m in r.get('msgTn') or r.get('msgCn') or []:
                lines.append('  > ' + clean(m))
            out.append('\n'.join(lines) + '\n')
        rel = 'quests/npc-scripts-%d.md' % (k + 1)
        w.write(rel, 'NPC 腳本 / 對話（%d ~ %d）' % (part[0]['ID'], part[-1]['ID']), '\n'.join(out),
                'NpcScript：NPC 點下去的功能（接任務、戰鬥、傳送、合成…）與對話內容。func 對照見 quests/README.md。')
        idx.append(['[%s](%s)' % (os.path.basename(rel), os.path.basename(rel)), '%d ~ %d' % (part[0]['ID'], part[-1]['ID'])])
    tr = [[r['ID'], db.L(r.get('title'))] for r in db.t('Answer')]
    w.write('quests/answers.md', '答題題庫（Answer）', table(['ID', '題目'], tr),
            '伺服器觸發的答題（含「防腳本驗證」）。選項是圖片（answerInfo.img），客戶端看不到正解。出現答題視窗時須由人類處理或謹慎作答。')
    body = '''- [guides.md](guides.md) 主要任務攻略說明
- [tasks.md](tasks.md) 全部任務鏈：接取 / 回報 NPC 位置、條件、獎勵、導航終點
- [answers.md](answers.md) 答題題庫（防腳本驗證）
- NPC 腳本 / 對話：

''' + table(['檔案', '腳本 ID'], idx) + '\n## 腳本功能（NpcScript.script.func）\n\n' + table(['func', '意義'], sorted(NPC_FUNC.items()))
    body += '\n任務狀態（TaskStatus）：-1 等待、0 無、1 已接、2 完成、3 放棄。任務類型（TaskType）：1 對話、2 打怪、3 巡邏、4 戰鬥、5 任務道具、6 道具、7 寵物、8 使用道具、9 答題、12 代碼。\n'
    w.write('quests/README.md', '任務總覽', body)

# ---------------- 合成 / 製作 ----------------
def build_crafting(db, w):
    tr = []
    for r in db.t('ExchangeItem'):
        tgt = db.item_name(r.get('targetId')) if r.get('targetType', 1) == 1 else '寵物 ' + db.mon_name(r.get('targetId'))
        tr.append([r['ID'], '%s(%s)' % (tgt, r.get('targetId')), req_text(db, r.get('requireInfos')), '%.1f%%' % (r.get('rate', 1000) / 10.0),
                   req_text(db, r.get('requireInfosVip'))])
    w.write('crafting/exchange.md', '合成 / 兌換配方（ExchangeItem）', table(['ID', '產物', '材料', '成功率', 'VIP 材料'], tr),
            '合成介面（UIHeCheng）用的配方。isSeletItemIndex 的材料是「多選一」。共 %d 筆。' % len(tr))
    tr = []
    for r in db.t('ItemBook'):
        tr.append([r['ID'], db.L(r.get('name')), '%s(%s)' % (db.item_name(r.get('itemId')), r.get('itemId')) if r.get('itemId') else '',
                   req_text(db, r.get('needItem')), r.get('okprice', ''), '、'.join(map(str, r.get('itemList', []) or []))[:80]])
    w.write('crafting/item-book.md', '材料圖鑑製作（ItemBook）', table(['ID', '名稱', '產物', '材料', '費用', '子項'], tr), '材料圖鑑（UICaiLiaoTuJian）。')
    out = '## ItemMakeForNew\n\n' + table(['ID(產物)', '成功率', 'A 組', 'B 組', 'C 組', '額外需求'], [[
        '%s(%d)' % (db.item_name(r['ID']), r['ID']), r.get('okRate', ''),
        '、'.join(db.item_name(x.get('itemId')) for x in r.get('aList', []) or [])[:200],
        '、'.join(db.item_name(x.get('itemId')) for x in r.get('bList', []) or [])[:200],
        '、'.join(db.item_name(x.get('itemId')) for x in r.get('cList', []) or [])[:200],
        json.dumps(r.get('extraNeed'), ensure_ascii=False) if r.get('extraNeed') else ''] for r in db.t('ItemMakeForNew')])
    out += '\n## NewItemMake\n\n' + table(['ID(產物)', 'A 組', 'B 組', '機率', '需求', '說明'], [[
        '%s(%d)' % (db.item_name(r['ID']), r['ID']), '、'.join(db.item_name(x) for x in r.get('aList', []) or []),
        '、'.join(db.item_name(x) if isinstance(x, int) else str(x) for x in r.get('bList', []) or []), r.get('getRate', ''),
        req_text(db, r.get('needInfo')), clean(r.get('smTn') or r.get('smCn'))] for r in db.t('NewItemMake')])
    w.write('crafting/item-make.md', '道具製作', out)
    out = '## 道具強化（ItemUp）\n\n'
    for r in db.t('ItemUp'):
        out += '### %s(%d)\n\n' % (db.item_name(r['ID']), r['ID']) + table(['等級', '材料', '數量', '成功率', '金幣', '鑽石', '效果'], [[
            u.get('upLevel'), db.item_name(u.get('needItemId')), u.get('needItemNum'), u.get('rate'), u.get('gold'), u.get('denar'),
            ' '.join('%s=%s' % (k, v) for k, v in u.items() if k not in ('upLevel', 'needItemId', 'needItemNum', 'rate', 'gold', 'denar'))] for u in r.get('upNeedInfo', []) or []]) + '\n'
    out += '## 道具升級（ItemUpNew）\n\n' + table(['道具', '最高等級', '內容'], [['%s(%d)' % (db.item_name(r['ID']), r['ID']), r.get('maxLevel'),
        json.dumps({k: v for k, v in r.items() if k not in ('ID', 'maxLevel')}, ensure_ascii=False)[:600]] for r in db.t('ItemUpNew')])
    w.write('crafting/enhance.md', '道具強化 / 升級', out)
    tr = [[r['ID'], req_text(db, r.get('cost'))] for r in db.t('Huilu')]
    w.write('crafting/huilu.md', '回爐（Huilu）', table(['ID', '花費'], tr), '寵物 / 道具回爐的花費表。')
    body = '''- [exchange.md](exchange.md) 合成 / 兌換配方（最主要）
- [item-book.md](item-book.md) 材料圖鑑製作
- [item-make.md](item-make.md) 其他製作
- [enhance.md](enhance.md) 道具強化 / 升級
- [huilu.md](huilu.md) 回爐

要查「某道具怎麼做 / 拿來做什麼」：`python tools/query/psa.py item <名稱或ID>`。
'''
    w.write('crafting/README.md', '合成 / 製作總覽', body)

# ---------------- 經濟 / 活動 ----------------
def build_economy(db, w):
    out = []
    for n in sorted(db.t('Npc'), key=lambda n: (n.get('map', 0), n['ID'])):
        sells = [a for a in n.get('npcArgs', []) or [] if a.get('itemId') and a.get('price') is not None]
        if not sells: continue
        out.append('## %s (NPC %d) @ %s\n\n' % (name(n), n['ID'], db.pos(n.get('map'), n.get('x'), n.get('y'))) +
                   table(['道具', 'ID', '價格'], [[db.item_name(a['itemId']), a['itemId'], cur(a.get('currency', 3), a.get('price', 0))] for a in sells]))
    w.write('economy/npc-shops.md', 'NPC 商店', '\n'.join(out), '每個販售 NPC 的商品與價格（Npc.npcArgs）。貨幣：%s。' % '、'.join('%d=%s' % kv for kv in CURRENCY.items() if kv[0]))
    out = '## 商城（ShopMall）\n\n' + table(['ID', '分組', '商品', '價格'], [[r['ID'], r.get('group'), '%s(%s)' % (db.item_name(r.get('goodsId')), r.get('goodsId')), r.get('priceDefaultInit')] for r in db.t('ShopMall')])
    out += '\n## 商城分頁（ShopMallName）\n\n' + table(['ID', '名稱', '子分頁'], [[r['ID'], db.L(r.get('name')), '、'.join(db.L(s.get('name')) for s in r.get('subGroup', []) or [])] for r in db.t('ShopMallName')])
    out += '\n## 一鍵購買（OneKeyBuy）\n\n' + table(['道具', '價格'], [[db.item_name(r['ID']), json.dumps(r.get('Info'), ensure_ascii=False)] for r in db.t('OneKeyBuy')])
    w.write('economy/mall.md', '商城', out)
    out = ''
    for r in db.t('Lottery'):
        out += '## %s (ID %d)\n\n%s\n\n' % (name(r) or '抽獎%d' % r['ID'], r['ID'], clean(r.get('descriptionTn') or r.get('descriptionCn')))
        if r.get('Item'): out += table(['道具', 'ID', '權重', '數量'], [[db.item_name(x.get('itemId')), x.get('itemId'), x.get('rate'), x.get('itemNumStr', '1')] for x in r['Item']]) + '\n'
    w.write('economy/lottery.md', '抽獎（Lottery）', out, '抽獎 / 扭蛋內容與權重。')
    out = '## 活動（Activity）\n\n' + table(['ID', '名稱', '類型', '獎勵'], [[r['ID'], db.L(r.get('name')), r.get('type'), reward_text(db, r.get('reward'))[:300]] for r in db.t('Activity')])
    out += '\n## 每日活動（DateActivity）\n\n' + table(['ID', '名稱', '說明', '活躍度'], [[r['ID'], name(r), clean(r.get('InfoTn') or r.get('InfoCn')), r.get('active')] for r in db.t('DateActivity')])
    out += '\n## 副本說明（MowangFuben）\n\n' + '\n'.join('### 副本 %d\n%s\n' % (r['ID'], clean(r.get('ShuoMingTn') or r.get('ShuoMingCn')).replace(' ', '\n')) for r in db.t('MowangFuben'))
    out += '\n## 副本獎勵（MowangFubenSet）\n\n' + table(['ID', '名稱', '說明'], [[r['ID'], name(r), clean(r.get('descriptionTn') or r.get('descriptionCn'))] for r in db.t('MowangFubenSet')])
    out += '\n## VIP（Vip）\n\n' + table(['等級', '名稱', '需求', '獎勵', '特權'], [[r['ID'], db.L(r.get('name')), json.dumps(r.get('need'), ensure_ascii=False), reward_text(db, r.get('reward')), json.dumps(r.get('vipPower'), ensure_ascii=False)] for r in db.t('Vip')])
    out += '\n## MM 觀光（MMWatch）\n\n' + table(['ID', '地點', 'MM 對話'], [[r['ID'], db.pos((r.get('WatchInfo') or {}).get('map'), (r.get('WatchInfo') or {}).get('x'), (r.get('WatchInfo') or {}).get('y')), clean(r.get('MMChatTn'))] for r in db.t('MMWatch')])
    w.write('economy/activities.md', '活動 / 副本 / VIP', out)
    out = ''
    for r in db.t('Notice'):
        out += '## %s\n\n%s\n\n' % (clean(r.get('NameTN') or r.get('NameCN')) or '公告%d' % r['ID'], re.sub(r'</?(color|size)[^>]*>', '', (r.get('msgTCN') or r.get('msgCN') or '').replace('\\n', '\n')))
    w.write('economy/notices.md', '遊戲公告（Notice）', out, '開服公告：基礎設定（經驗倍率、離線時間、月卡 / 季卡效果等）。')
    out = '## 儲值方案（NewReChargeNomal）\n\n' + table(['ID', '價格', '說明', '得鑽'], [[r['ID'], r.get('price'), clean(r.get('explanTn') or r.get('explanCn')), r.get('getDenar')] for r in db.t('NewReChargeNomal')])
    out += '\n## 累儲獎勵（ReCharge）\n\n' + table(['ID', '累儲鑽石', '獎勵'], [[r['ID'], r.get('needRechargeDenar'), '、'.join('%s×%s' % (db.item_name(x.get('itemId')), x.get('num')) for x in r.get('items', []) or [])] for r in db.t('ReCharge')])
    w.write('economy/recharge.md', '儲值（僅供參考，AI 不得進行任何付費操作）', out)
    body = '''- [npc-shops.md](npc-shops.md) NPC 商店：誰賣什麼、價格
- [mall.md](mall.md) 商城
- [lottery.md](lottery.md) 抽獎 / 扭蛋
- [activities.md](activities.md) 活動、每日活動、副本、VIP
- [notices.md](notices.md) 開服公告（伺服器基礎設定）
- [recharge.md](recharge.md) 儲值方案（參考用，禁止操作）

## 貨幣
''' + table(['代碼', '名稱', '說明'], [[1, '鑽石 (denar)', '儲值貨幣'], [2, '金幣 (gold)', ''], [3, '石幣 (stone)', '主要遊戲貨幣，打怪 / 賣道具取得'],
                                    [8, '綁定鑽石 (lockDenar)', '不可交易'], [10, '活躍度 (active)', '每日活動累積'], [11, '積分', '']])
    w.write('economy/README.md', '經濟 / 商店 / 活動總覽', body)

# ---------------- 總覽 ----------------
def build_overview(db, w):
    cfg = (db.t('Config') or [{}])[0]
    CFG_DESC = {'battleSpeed': '戰鬥速度倍率', 'normalSpeed': '一般移動速度倍率', 'maxRole': '最多角色數', 'initRoleNum': '初始角色欄',
                'petSkillMax': '寵物技能欄上限', 'maxItemPlace': '背包頁數上限', 'initItemPlace': '初始背包格', 'petMaxLevel': '寵物等級上限',
                'guildCreateNeed': '建立家族費用', 'maxItemDepotPlace': '道具倉庫頁上限', 'perItemDepotNum': '每頁倉庫格數', 'maxPetDepotPlace': '寵物倉庫頁上限',
                'initWeight': '初始負重', 'eggEatCount': '吃蛋次數上限', 'catchPetItem': '捕捉寵物道具費用', 'changeName': '改名費用',
                'familyMaxMemberCount': '家族人數上限', 'mustOutBattleMap': '必須脫離戰鬥的地圖', 'randomPkMap': '隨機 PK 地圖', 'baseExp': '基礎經驗倍率',
                'autoEatExpItemList': '自動吃的經驗道具', 'MD5Version': '資料版本', 'rolePointSaveCost': '保存配點方案費用'}
    tr = []
    for k, v in cfg.items():
        s = json.dumps(v, ensure_ascii=False)
        tr.append([k, CFG_DESC.get(k, ''), s if len(s) < 300 else s[:300] + '…'])
    w.write('overview/game-config.md', '遊戲常數（Config 表）', table(['欄位', '說明', '值'], tr), 'Config 表唯一一列：伺服器 / 客戶端共用的遊戲常數。')
    # 列舉
    keep = [k for k in sorted(db.enums) if not k.startswith(('Data.', 'Coffee', 'DG.', 'Spine', 'TMPro', 'UnityEngine', 'BestHTTP', 'SRF', 'SRDebugger'))]
    tr = [[k, db.enums[k][:700]] for k in keep]
    tr += [[k, db.enums[k][:400]] for k in sorted(db.enums) if k.startswith('Data.')]
    w.write('overview/enums.md', '程式列舉（HotUpdate.dll enums）', table(['列舉', '值'], tr),
            '從熱更新程式抽出的列舉：道具類型、戰鬥指令、方向、角色類型、任務狀態…。名稱是程式原文（英文 / 拼音）。')
    # bundle 分類
    rows = []
    try:
        for line in open(os.path.join(db.data, 'bundles.tsv'), encoding='utf-8'):
            f, sz = line.rstrip('\n').split('\t'); rows.append((f, int(sz)))
    except Exception: pass
    groups = collections.OrderedDict()
    for f, sz in rows:
        base = re.sub(r'\.assetbundle1?$', '', f)
        if base.startswith('ui') or base.endswith('_yhkrn'):
            key = 'ui*'
        else:
            key = re.sub(r'[_\d]+.*$', '', base) or base
        g = groups.setdefault(key, [0, 0, []]); g[0] += 1; g[1] += sz; g[2].append(f)
    tr = []
    for k, (n, sz, fs) in sorted(groups.items(), key=lambda kv: (-kv[1][0], kv[0])):
        d, cat = BUNDLE_DESC.get(k, ('', ''))
        if k == 'ui*': d, cat = 'UI 介面預製物（*_yhkrn = 韓版 UI），見 ui-screens.md', '介面'
        tr.append([k, cat, n, '%.1f MB' % (sz / 1048576), d, '、'.join(fs[:3]) + ('…' if n > 3 else '')])
    w.write('overview/client-files.md', '遊戲客戶端檔案分類', '''## 資料夾結構（GameClient，唯讀）
- `PrimalSA.exe`：遊戲主程式（Unity 2022.3.62f3，IL2CPP）
- `GameAssembly.dll`：IL2CPP 編譯的原生程式碼；`PrimalSA_Data/il2cpp_data/Metadata/global-metadata.dat`：IL2CPP 中繼資料
- `PrimalSA_Data/StreamingAssets/AssetBundles/`：**所有遊戲資源與設定表**（2,700+ 個 bundle）
- `PrimalSA_Data/*.assets`、`level0~2`：開機場景與內建資源
- 遊戲邏輯在熱更新組件 `HotUpdate.dll`（HybridCLR），放在 hotupdate.dll.assetbundle 裡，會隨熱更新替換。

## AssetBundle 分類
''' + table(['前綴', '類別', '數量', '大小', '內容', '範例'], tr) + '''
## 檔案格式（逆向結果）
- **Bundle 混淆**：檔頭前塞了約 330 bytes 假資料（含多個 `UnityFS` 簽章）；真正 bundle = 前 1024 bytes 內**最後一個** `UnityFS` 起算。資料區塊 LZMA、block info LZ4。
- **configs.assetbundle** → TextAsset `Configs`，Tabtoy v3 二進位（`TABTOY` 檔頭；tag=(型別<<16)|欄位索引；型別 1 int32、2 int64、5 float、6 string、7 bool、8 enum、9 struct、10 表列）。
  表名 / 欄位名來自 HotUpdate.dll 的 `Data.*Define.Deserialize()`，由 tools/schemadump 產生 `data/schema.tsv`。
- **mapdata_{地圖ID}** → TextAsset `LS2MAP`（大端序：名稱 GBK、寬、高、地面層 uint16[]、物件層 uint16[]）；圖素編號對 MapOffset 表的 walkable。地圖 ID 以檔名為準。
- **itemalt_\\*** Sprite 名 = Item.imageId；**headicon\\*** Sprite 名 = Monster.imageId；**char{圖號}** 角色影格。
- 文字有三語：`*Cn` 簡中、`*Tn` 繁中、`*Kr/*Krn` 韓文。本知識庫以繁中為主、附韓文（韓版客戶端畫面可能顯示韓文）。
''', 'GameClient 內容分類與格式說明（供維護與進一步分析用）。')
    # UI
    ui = sorted({re.sub(r'^(uiui|ui)', '', re.sub(r'(_yhkrn)?\.assetbundle1?$', '', f)) for f, _ in rows
                 if f.startswith('ui') and f not in ('ui_icon.assetbundle', 'uistonebutton.assetbundle', 'uinpcname.assetbundle')})
    tr = [[u, 'UI%sScreen' % u, UI_MEANING.get(u, '')] for u in ui]
    w.write('overview/ui-screens.md', '遊戲介面（UI 畫面）', table(['bundle 名', '推測類別名', '用途'], tr),
            '由 ui*_yhkrn.assetbundle 檔名整理的介面清單；用途是依拼音 / 英文推測。NPC 的 openUIName 會直接開這些畫面。')

def build_text(db, w):
    rows = []
    for r in db.t('NewLanguage'): rows.append([r['ID'], j(r.get('tcn') or r.get('scn')), j(r.get('krn'))])
    for r in db.t('NewLanguagePublic'): rows.append([r['ID'], r.get('StrTn') or r.get('StrCn') or '', r.get('StrKrn') or ''])
    rows.sort(key=lambda r: r[0])
    idx = []
    for k, part in chunks(rows, 1500):
        rel = 'text/strings-%d.md' % (k + 1)
        w.write(rel, '遊戲文字（%d ~ %d）' % (part[0][0], part[-1][0]), table(['ID', '繁中', '韓文'], [[a, cell(b)[:300], cell(c)[:300]] for a, b, c in part]),
                '語言表 NewLanguage / NewLanguagePublic：介面文字、系統訊息、提示。用來對照畫面上的韓文 / 中文訊息。')
        idx.append(['[%s](%s)' % (os.path.basename(rel), os.path.basename(rel)), '%d ~ %d' % (part[0][0], part[-1][0])])
    w.write('text/README.md', '遊戲文字總覽', table(['檔案', 'ID 範圍'], idx) +
            '\n常見：40000000105「登錄上限已達到」、200000019+N 寵物系別名稱。看到畫面訊息時用 grep 搜尋本資料夾即可找到 ID 與中韓對照。\n')

def build_readme(db, w):
    c = lambda n: len(db.t(n))
    now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M')
    ver = (db.t('Config') or [{}])[0].get('MD5Version', '')
    try: appver = open(os.path.join(db.data, 'app.ver'), encoding='utf-8').read().strip()
    except Exception: appver = ''
    if appver: ver = '%s；客戶端版本（app.ver）：%s' % (ver, appver)
    body = '''本資料夾由 `tools/extract/extract.py` 從 `GameClient/` 自動產生（**請勿手動修改**，重新匯出會覆蓋）。
產生時間：%s；遊戲資料版本（Config.MD5Version）：%s。

## 分類目錄
| 資料夾 | 內容 | 主要來源表 |
|---|---|---|
| [overview/](overview/) | 遊戲常數、程式列舉、客戶端檔案分類 / 格式、UI 畫面清單 | Config、HotUpdate.dll |
| [items/](items/README.md) | 道具 %d 件（武器、防具、飾品、藥品、材料、寵物裝備、任務、其他）、套裝 | Item、Suit |
| [pets/](pets/README.md) | 寵物 / 怪物 %d 種（依系別分檔）、取得方式、騎乘、經驗表 | Monster、PetData、PetBaby、Ride、Exp |
| [skills/](skills/README.md) | 戰鬥技能 %d、狀態 %d、角色 Buff、技能學習 NPC | SkillBattle、Skill、SkillStatus、RoleBuff |
| [world/](world/README.md) | 地圖 %d 張、出口 %d 個、NPC %d 個（依地圖分組）、交通 / 傳送 | MapName、MapWarp、Npc、Transfer |
| [quests/](quests/README.md) | 任務 %d 步、攻略說明、NPC 腳本 / 對話 %d 個、答題題庫 | Task、TaskExplan、NpcScript、Answer |
| [crafting/](crafting/README.md) | 合成配方 %d、材料圖鑑、製作、強化、回爐 | ExchangeItem、ItemBook、ItemUp |
| [economy/](economy/README.md) | NPC 商店、商城、抽獎、活動 / 副本、公告、儲值 | Npc.npcArgs、ShopMall、Lottery、Activity |
| [text/](text/README.md) | 遊戲文字 %d 條（繁中 / 韓文對照） | NewLanguage、NewLanguagePublic |
| [data/](data/) | 機器可讀原始資料（見下） | — |

## 原始資料（data/）
- `tables/<表名>.jsonl`：全部設定表，一行一筆 JSON（含 Cn/Tn/Kr 三語全部欄位）。**要精確查欄位用這個**，例如 `grep '"ID":1610,' knowledge/data/tables/Monster.jsonl`。
- `schema.tsv`：Tabtoy 欄位對照（類別、tag、欄位名|型別）；`enums.tsv`：程式列舉。
- `maps.bin`：每張地圖通行格（格式見 tools/query/psa.py）；`mapinfo.json`：地圖寬高。
- `ItemAltList.csv`、`bundles.tsv`：圖示 bundle 對照、bundle 清單。

## 怎麼查（給 AI）
1. **先 grep 名稱**：`grep -rn "烏力" knowledge/ --include=*.md`（繁中名或韓文名都可以）。
2. **用查詢工具**（交叉關聯 + 路線）：
   - `uv run --no-project python tools/query/psa.py find 關鍵字`
   - `... psa.py item <名稱|ID>`：能力、誰賣、怎麼合成、拿去合成什麼、哪個抽獎有
   - `... psa.py pet <名稱|ID>`、`npc <名稱|ID>`、`map <名稱|ID>`、`skill <名稱|ID>`、`task <名稱|ID>`
   - `... psa.py route <起點地圖> <x> <y> <終點地圖> [x y]`：跨地圖路線（經過哪些出口）
   - `... psa.py grid <地圖> <x> <y> [半徑]`：印出座標附近的通行格
3. ID 慣例：SkillBattle ID = skillId×1000+等級；Buff ID = type×1000+level；Monster.petType 0~28 系別、100 敵方；地圖 ID 以 mapdata 檔名為準。
''' % (now, ver, c('Item'), c('Monster'), c('SkillBattle'), c('SkillStatus'), len(set(db.maps) | set(db.mapinfo)), c('MapWarp'), c('Npc'),
       c('Task'), c('NpcScript'), c('ExchangeItem'), c('NewLanguage') + c('NewLanguagePublic'))
    body += '\n## 全部文件\n\n' + '\n'.join('- [%s](%s) — %s%s' % (rel, rel, t, ('：' + d) if d else '') for rel, t, d in sorted(w.files)) + '\n'
    w.write('README.md', '精靈王石器（PrimalSA）遊戲知識庫', body)

def build(kdir=None):
    kdir = kdir or os.path.join(ROOT, 'knowledge')
    db = DB(kdir)
    # 清掉舊的產生檔（data/ 保留）
    for sub in ('overview', 'items', 'pets', 'skills', 'world', 'quests', 'crafting', 'economy', 'text'):
        for f in glob.glob(os.path.join(kdir, sub, '*.md')): os.remove(f)
    w = Writer(kdir)
    for fn in (build_overview, build_items, build_pets, build_skills, build_world, build_quests, build_crafting, build_economy, build_text):
        fn(db, w)
        print('  %s 完成' % fn.__name__, flush=True)
    build_readme(db, w)
    print('  共 %d 個文件' % len(w.files))

if __name__ == '__main__':
    build(sys.argv[1] if len(sys.argv) > 1 else None)
