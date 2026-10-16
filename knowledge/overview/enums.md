# 程式列舉（HotUpdate.dll enums）

> 從熱更新程式抽出的列舉：道具類型、戰鬥指令、方向、角色類型、任務狀態…。名稱是程式原文（英文 / 拼音）。

| 列舉 | 值 |
|---|---|
| ActionEnum | MIN=-1, ATTACK=0, DAMAGE=1, DEAD=2, STAND=3, WALK=4, SIT=5, HAND=6, HAPPY=7, ANGRY=8, SAD=9, DEFENSE=10, NOD=11, THROW=12, RIDE_RIDE=14, RIDE_SIT=15, RIDE_STAND=16, RIDE_RIDE_1=17, RIDE_RIDE_2=18, RIDE_RIDE_3=19, RIDE_RIDE_4=20, MAX=21 |
| AnimationState | None=0, Playing=1, Pause=2, Stop=3 |
| AssetBundleEnum | NONE=0, MAP_TILE_PREFAB=2, MAP_BUILDING_PREFAB=3, ROLE_NORMAL_PREFAB=4, UI_ROLE_NORMAL_PREFAB=5, UI_PREFAB=27, CHAT_MSG_NORMAL=31, ROLE_BATTLE_PREFAB=35, ROLE_BATTLE_BUFF_EFFECT=44, BATTLE_MAGIC_EFFECT=45, ROLE_BATTLE_BUFF_EFFECT2=46, BATTLE_DAMAGE_HEAL=104, EnchantmentEffect=152, ROLE_BATTLE_ARUA_EFFECT=153, NEW_BATTLE_DAMAGE_HEAL=159, PARTICLE_BEGIN=10000 |
| BagItemType | ITEM=0, EMPTY_ITEM=1, LOCK_ITEM=2 |
| BattleAiEventType | NONE=0, ESCAPE=1, CALL_SELF=2, CALL_ENEMY=3, TRANSFIGURATION=4, CHANGE_MODEL=5, DELETE_PASSIVESKILL=6, ADD_PASSIVESKILL=7, CALL_SELF_FRONT=8 |
| BattleBorder | NONE=0, PHYSICAL=1, MAGIC=2 |
| BattleBuffType | BUFF=1, DEBUFF=2, SUPER=3 |
| BattleCmd | NONE=-2, CHANGECMD=-1, STANDBY=0, ATTACK=1, DEFENSE=2, MAGIC=3, ITEM=4, TRICK=5, TRUMP=6, PROTECT=7, CALL=8, ESCAPE=9, CAPTURE=10, EQUIP=11, EVENT=50, DOT_HOT=101, NONOESCAPE=150, TRANS_DEVIL=200, SPURT=201, REFLEX=202, BEATBACK=203, TRIP=204 |
| BattleCmdIcon | ESCAPE=7000, ATTACK=8000, DEFENSE=9000 |
| BattleCmdStatus | WAIT=1, CMD=2, PLAY=3 |
| BattleDamage | NONE=0, PHYSICAL=1, MAGIC=2, HEAL_HP=3, HEAL_MP=4, HEAL_SP=5, MPDAMAGE=6, SPDAMAGE=7, DOT_PHYSICAL=8, DOT_MAGIC=9, REFLEX_DAMAGE=10 |
| BattleDeBuffAssetName | none=0, zhongdu=4, hunluan=6, xuruo=7, shuidi=9, wuyu=10, shuxingzhuanhuan=11, leidian=19, xunyun=20, zhizhuwang=22, judu=24 |
| BattleEffectType | BEHIND=0, FRONT=1, DOWN=2 |
| BattleField | NONE=0, EARTH=1, WATER=2, FIRE=3, WIND=4 |
| BattleFlag | NONE=0, DIE=2, FLY=4, DODGE=8, CRIT=16, AFK=32, RELIVE=64, PROTECT=128, DEFENSE=256, INVINCIBLE=512, BLOCK=1024, SHIELD=2048, PARRY=4096, SOUL_LINK=8192, GEMINI=16384, ELEMENT=32768, SNEER=65536, FINALHIT=131072, ROLE_DIE=262144, ROLE_FLY=524288, ADD_ATTACK=1048576, PHYSICAL_ABSORB=2097152, MISS=4194304, ASSAULT=33554432, FALLHORSE=67108864, NONO=134217728, MAGIC_DODGE=268435456, PHYSICAL_REFLEX=536870912 |
| BattleFlyEffect | FLY_MIN=0, FLY_ONE=1, FLY_TWO=2, FLY_MAX=3 |
| BattleMode | INIT=1, PLAY=2, CMD=3, END=4 |
| BattleNum | MAX=40, SIDE_MAX=20 |
| BattlePos | SIDE_DOWN_BEGIN=0, SIDE_DOWN_END=13, SIDE_UP_BEGIN=20, SIDE_UP_END=33 |
| BattleReady | YES=1, NO=2 |
| BattleSide | SIDE_NONE=-1, SIDE_DOWN=0, SIDE_UP=1, SIDE_DOWN_BEGIN=0, SIDE_DOWN_END=19, SIDE_UP_BEGIN=20, SIDE_UP_END=39 |
| BattleSidePos | SIDE_DOWN=0, SIDE_UP=1, SIDE_DOWN_BEGIN=0, SIDE_DOWN_MID=4, SIDE_DOWN_END=19, SIDE_UP_BEGIN=20, SIDE_UP_MID=24, SIDE_UP_END=39 |
| BattleStatuDeal | ADD=1, DELETE=2, MISS=3 |
| BattleTarget | RANDOM=99999, ANY_ENEMY=101, ANY_ENEMY_LIVE=102, ANY_SELF=201, ONLY_SELF=202, WITHOUT_SELF=203, ANY_SELF_LIVE=204, ANY_SELF_DIE=208, WITHOUT_SELF_LIVE=210, ANY_LIVE=301, ANY_ENEMY_LIVE_PET=503, EMEMY_ONE_ROW=602, ENEMY_BEHIND_BACK=603, ENEMY_LEFT_RIGHT=604, ONLY_SELF_LIVE_PET=606, ONLY_SELF_FOR_PET=607, ANY_ENEMY_DIE_PET=608, ANY_LIVE_NOT_SELF=609, ANY_SELF_DIE_PET=610, ANY_SELF_PET=611, ANY_ENEMY_PET=612, SELF_ONE_ROW=613 |
| BattleTeamType | None=0, Atc=1, Die=2, Select=3 |
| ButtonEnum | NONE=1, OK=2, CANCEL=4, PREV=8, NEXT=16 |
| CameraMode | Login=0, Main=1, Battle=2, MiniMap=3, CG=4 |
| ChannelType | MAP=1, TEAM=2, GUILD=3, WORLD=4, JOB=5, SYSTEM=6, PRIVATE=7, ALL_WORLD=8, WORLD_TEAM=9, Local=10, All=11, TOP_ROLL=100, BOTTOM_TIP=101 |
| ChatMode | System=0, World=1, Family=2, Team=3, Local=4, All=5 |
| ChatShowMsgType | LEFT=1, RIGHT=2 |
| CircularScrollView.e_Direction | Horizontal=0, Vertical=1 |
| ClientSendProtocolMsg+EGMType | GetItem=1, GetPet=2, Transfer=3, SetRole=4, SetCurrency=5, FinishTask=6, PetTurn=7, RoleTurn=8, Family=9, ClanWars=10 |
| ClientSendProtocolMsg+EPointSaveAction | Unlock=1, Import=2, Export=3, Delete=4 |
| ClientSendProtocolMsg+EPublicDepotSafeFlgType | Item=1, Pet=2 |
| ClientSendProtocolMsg+ERoleAction | Auto=1, ChangeRole=2, ChangePet=3 |
| ClientSendProtocolMsg+ERoleMakeupType | UseModel=1, UseBonus=2, NotUseModel=3, NotUseBonus=4 |
| ClientSendProtocolMsg+RoleModifyType | TeamJoinFlag=0, TeamInviteFlag=1, SystemPushFlag=2, PvpInviteFlag=3, GuildInviteFlag=4, EatMeatFlag=5, AutoEncountFlag=6, TaskwaitThing=7, TaskwaitType=8, TradeInviteFlag=9 |
| CmdArgTargetRule | NONE=0, SELF_ROLE=1, SELF_PET=2, RANDOM_ENEMY=3, RANDOM_TEAMER=4 |
| CreateAction | STEP_NAME=0, STEP_ATTR=1, STEP_BASE_ATTR=2 |
| DataManager+ECombinItem | Item=0, Equip=1, Pet=2, PetDna=3 |
| DataManager+EItemBigType | Item=0, Equip=1, Gem=2, Other=3 |
| DataManager+EItemEquipType | NONE=-1, FIST=0, AXE=1, CLUB=2, SPEAR=3, BOW=4, HELM=6, ARMOUR=7, BRACELET=8, INSTRU=9, NECKLACE=10, RING=11, EARRING=13, AMULET=15, BELT=24, SHIELD=25, SHOES=26, GLOVE=27, PETEQUIP=28 |
| DataManager+EItemGemType | NONE=0, QUIP_GEM=1, PET_GEM=2 |
| DataManager+EItemItemType | None=0, Item=1, TASK=2, Currency=3, DRUG=20, MATER=21 |
| Default | RoleImage=100000, BagItemPlace=15 |
| DirEnum | NONE=-1, DOWN=0, LEFT_DOWN=1, LEFT=2, LEFT_UP=3, UP=4, RIGHT_UP=5, RIGHT=6, RIGHT_DOWN=7, MAX=8 |
| DotHot | NONE=0, HP_RECOVER=1101, HP_PHYSICAL_DAMAGE=1102, HP_MAGIC_DAMAGE=1112, MP_RECOVER=1201, MP_DAMAGE=1202, SP_RECOVER=1301, SP_DAMAGE=1302, ON_HP_RECOVER=1401, ON_HP_PHYSICAL_DAMAGE=1402, ON_HP_MAGIC_DAMAGE=1412, ON_HP_RELIVE_RECOVER=1501, GHOST=1601, GHOST_HIGH=1602, REST=2001, SEAL_PM=2002, SEAL_MAGIC=2003, SEAL_ALL=2004, CHAOS=2101, POISON=2102, PARALYSIS=2103, SLEEP=2104, STONE=2105, DRUNK=2106, DIZZINESS=2107, BARRIER=2108, EARTH_ROUND=2109, ASSAULT=2110, FALLRIDE=2112, AMNESIA=2201, STEALTH=3001, PERCEIVE=3002, INVINCIBLE=4001, BLOCK=4002, SHIELD=4003, PARRY=4004, SOUL_LINK=4005, REPEAT_SHOT=5001, FINALHIT_DAMAGE=5002, PASSIVE_SKILL=6001, ADD_ATTACK=7001, PHYSICAL_REFLEX=7101, PHYSICAL_B |
| EAccountLoginMode | Login=0, Regster=1, Change=2 |
| EActionState | Play=0, Pause=1, End=2 |
| EAssetsType | SpriteAtlas=0, GameObject=1, Sprite=2, UI=3, Particle=4, Other=5, HUD=6, LOGIN=7, Lua=8, BattleEffect=9, RoleTile=10, NewUI=11, CharFx=12, TimeLine=13, RandomBadgeData=14, ChatIcon=15, NumberIcon=16, EmojiIcon=17, PetGroupIcon=18, UI_Icon=19, PetStaticPic=20, SkillIcon=21 |
| EAttrProgressType | Earth=0, Water=1, Fire=2, Wind=3 |
| EBagMode | None=0, Editor=1, Delete=2 |
| EBaseAttrType | Vitality=0, Strength=1, Stamina=2, Speed=3 |
| EBattleCmdType | None=0, Attack=1, Skill=2, Capture=3, Bag=4, Defense=5, ChangeRide=6, Escape=7 |
| EBattleEnd | Win=1, Lose=2, Escape=3 |
| EBoxStyle | Yes=0, YesNo=1, DelNo=2 |
| EButtonType | B1=0, B2=1, B3=2, B4=3, B5=4, B6=5, B7=6, B8=7, B9=8, B10=9, B11=10, B12=11, B13=12, B14=13, B15=14, B16=15 |
| EChangeResult | ChangeOK=1, AccountError=2, PassWordError=3, PhoneError=4, PcIdError=5, AccountNoHasError=6, SystemError=7 |
| ECompType | Sprite=0, Image=1 |
| ECurrecyShowMode | None=0, All=1, Noraml=2, Famly=3 |
| ECurrecyType | Diamond=1, OnLine=2, Stone=3, Medal=8, Active=10, Score=11 |
| EFriendType | ATK=0, DEF=1, ADD=2, AUX=3 |
| EGMUIType | Meun=0, Button=1, Input=2, Custom=3, Toggle=4 |
| EHUDGroup | RoleHUD=0, Defalut=1 |
| EImageSizeType | Custom=0, NativeSize=1, MatchWidth=2, MatchHeight=3, MatchWidthAdaptive=4, MatchHeightAdaptive=5 |
| EInputType | Number=0, Boolean=1, String=2 |
| EItemScripts | Discarded=1000, TakeIn=1029, TakeOut=1030, BreadUp=1065, EquipOff=1006, EquipOn=1005, CanUseMuch=1028 |
| EItemType | Item=0, Equip=1, Task=2, Currency=3, PetEquip=4, Material=5, Cook=6, Other=7 |
| ELoginResult | LoginOK=1, AccountError=2, PcIdError=3, ClientVerError=4, LanguageError=5, CodeError=6, GameServerError=7, Lock=8 |
| EPassiveEventType | Injured=0, Dodge=1, Sleep=2, Beat=3, InjuredBeatBack=4 |
| EPetElemType | Earth=0, Wind=1, Fire=2, Water=3 |
| ERTLevel | Hight=0, Mid=1, Low=2 |
| ERegResult | RegOK=1, AccountError=2, PassWordError=3, PhoneError=4, PcIdError=5, AccountRegError=6, SystemError=7, IcodeError=8 |
| EResult | Yes=0, No=1 |
| ERoleInfoMode | newBase=0, Base=1, Skill=2, Ride=3, Change=4 |
| ERoleMoveMode | Local=0, Server=1, Follow=2 |
| ESettingMode | None=0, Other=1, Sound=2, Chat=3, Graphics=4 |
| EShowMode | Game=0, Battle=1, WatchBattle=2 |
| ESillState | None=0, Ready=1, Doing=2, End=3 |
| ESkillPerformMode | Queue=0, Instant=1 |
| EStateConst | Splash=0, Branch=1, Login=2, Gaming=3, LoginGame=4, LoginOut=5, SwitchRole=6, CheckVersion=7, CreateNewRole=8, Battle=9, WatchBattle=10 |
| ETeamInvitaMode | Famly=0, Friend=1 |
| ETeamMode | Team=0, Friend=1, Find=2 |
| ETextColor | C1=16777215, C2=2234389, C3=13764103, C4=6571299, C5=7878172, C6=2883328, C7=9336663, C8=4599312, C9=8084020, C10=9030399, C11=13410417, C12=16711691, C13=6828298, C14=9925958, C15=8683117, C16=16763392, C17=16770763, C18=15648388, C19=15855055, C20=8186547, C21=16755456, C22=16498019, C23=10185551, C24=8196096, C25=14795174, C26=16755712, C27=8146477, C28=14385454, C29=9855039, C30=6110229, C31=0, C32=13485746, C33=16768939, C34=14079702, C35=7200217, C36=49407, C37=16747008, C38=16768512, C39=14923662, C40=16666447, C41=16757276, C42=16580352, C43=7077650, C44=2161913, C45=6926591, C46=16737742, C47=16769731, C48=16770763 |
| ETextOutLine | None=0, Shadow=1, O1=6571299, O2=2234389, O3=2974492, O4=6503196, O5=1852003, O6=16767401, O7=4394240, O8=7602954, O9=1400649, O10=9136716, O11=4144959, O12=2, O13=3, O14=16770048, O15=5458752, O16=9598298 |
| ETextSize | S1=45, S2=35, S3=26, S4=24, S5=20, S6=18, S7=16, S8=13, S9=14, S10=10, S11=22 |
| EUIBagMode | Bag=0, Repository=1, ItemMap=2, OldRepository=3 |
| EUIBagRespotiMode | Private=0, Public=1, Traing=2 |
| EUIBattleMode | Battle=0, Watch=1, OnLineWatch=2 |
| EUIChatInputMode | Emoji=0, Item=1, Pet=2 |
| EUIItemGemMode | Lock=0, UnLock=1, Setup=2 |
| EUIItemMode | Look=0, Useable=1, Used=2, Deposit=3, TakeOut=4, Synthesis=5 |
| EUIPetMode | newPet=0, NewWarehouse=1, NewManual=2 |
| EUIRoleShowAttrPlanMode | Lock=0, Add=1, Used=2, Del=3 |
| EUISameItemSelecterScreenMode | Item=0, Equip=1, Pet=2 |
| EUIType | Login=0, Game=1, Battle=2, Resident=3, System=4 |
| EUnityLayer | None=0, UI=1, UIRole=2, Role=3, Npc=4, TopUI=5, TopUIRole=6, NewUiRole=7, HUD=8 |
| EWorkType | Normal=0, Geming=1, Battle=2, Chat=3, UI=4, Timer=5, Assets=6, AOI=7, Waiter=8 |
| EWorldCurrency | RMB=0, TWD=1, HKD=2, USD=3, KRD=4 |
| Effect | NONE=0, SELECT_TARGET=1, TASK_FINISH_NO=13, TASK_FINISH_YES=14, TASK_ACCEPT_NO=15, TASK_ACCEPT_YES=16, MAP_TRANSFER=150500, NORMAL_ATTACK=160000, DEFENSE_ATTACK=160001, ROAD_SIGN=160002, TARGET_NPC=160003, CRIT_ATTACK=200221, LEVEL_UP=160005, INVINCIBLE=160006, ABSORB=160007, REFLEX=160010, XIANJING=101630, TASK_COMPLETE=200089, TASK_ACCEPT=200090, CALL_EFFECT=200092, SHIELDABSORB=200053 |
| EmailType | SYSTEM=1, NOTIC=2, NORMAL=3 |
| EmojiType | SPRITE=1, ANIMA=2, ITEM=3, PET=4, TEAM=5 |
| EnchantmentType | Spell=0, Physical=1 |
| GemAddType | HP=1, MP=2, SP=3, ATTACK=4, DEFENSE=5, AGILE=6, DODGE=7, HIT=8, CRIT=9, BLOCK=10, POSION=11, CHAOS=12, PARALYSIS=13, SLEEP=14, STONE=15, DRUNK=16, DIZZINESS=17, BARRIER=18, LUCK=19, CHARM=20, ATTACKCOUNT=21 |
| GradientDirection | UPDOWN=0, LEFTRIGHT=1 |
| GuildEventType | ADD_GUILD_EVENT=1, EXIT_GUILD_EVENT=2, KICK_GUILD_EVENT=3, UP_GUILD_JOB=4, DOWN_GUILD_JOB=5 |
| GuildJob | NONE=0, LEADER=1, ELDER=2, NORMAL=3 |
| GuildNotify | GUILD_DISBAND=1, ADD_GUILD=2, INVITE_GUILD=3, REFUSE_INVITE_GUILD=4, EXIT_GUILD=5 |
| GuildSprite | LIGHT=1, DARK=2 |
| GuildUpdateApplyType | ADD=1, DELETE=2 |
| HUDType | HUD=0, UI=1 |
| HandoverType | Base=0, Warehouse=2 |
| HeadType | bag=0, pet=1, role=2, message=3, store=4, pay=5, mail=6 |
| HideScreenMode | None=0, HideScreen=1, HideResident=2, HideAllScreen=3, HideAllScreenAndScreenShot=4, HideUnResident=5 |
| ItemBind | NO=0, YES=1 |
| ItemPos | NONE=-1, BAG=0, EQUIP=1, DEPOT_BAG=10, DEPOT_DEPOT=11, DEPOT_PUBLIC_BAG=12, DEPOT_PUBLIC_DEPOT=13 |
| ItemQuality | GRAY=0, WHITE=1, GREEN=2, BLUE=3, PURPLE=4, ORANGE=5, RED=6 |
| ItemStorge | NONE=-1, BAG=0, ITEM_DEPOT=1, WEAPON=41, SHIELD=42, HEAD=43, ARMOR=44, SHOES=45, BELT=46, GLOVE=47, NECKLACE=48, RING=49, AMULET=50 |
| ItemType | FIST=0, AXE=1, CLUB=2, SPEAR=3, BOW=4, HELM=6, ARMOUR=7, BRACELET=8, INSTRU=9, NECKLACE=10, RING=11, EARRING=13, AMULET=15, OTHER=16, BOOMERANG=17, BREAKTHROW=18, STONETHROW=19, DRUG=20, MATER=21, GEM=22, BAGGAGE=23, BELT=24, SHIELD=25, SHOES=26, GLOVE=27, PET_HEAD=31, PET_TOOTH=32, PET_GLOVE=33, PET_ARMOUR=34, PET_BACK=35, PET_WING=36, PET_SHOES=37, TASK=100, RECHARGEDIS=500, PETEQUIP=600, EQUIP=1000, PETZFDI=601, PETZFSHUI=602, PETZFHUO=603, PETZFFENG=604 |
| JobType | HUNTER=1, MAGIC=2, WARRIOR=3 |
| KickReson | REPLACE=1, HEART_TIMEOUT=2, SERVER_CLOSE=3, LOGIN_MAX=4, OFFLINE=5, JIEKA=6 |
| LanguageType | CHINESE_SIMPLE=40, CHINESE_TRAD=41, ENGLISH=10 |
| LastLoginType | NONE=-999999, VISITOR=1, QQ=2, WX=3, CDKEY=4, PHONE=5 |
| LayourDir | Horizontal=0, Vertical=1 |
| ListItemArrangeType | TopToBottom=0, BottomToTop=1, LeftToRight=2, RightToLeft=3 |
| LogLevel | v=0, d=1, i=2, w=3, e=4 |
| LoginAction | NONE=0, CREATE_ROLE=1, LOGIN_ROLE=2 |
| MapType | SCENE=1, DUNGEO=2, PVP=3, ACTIVITY=4, GUILD=5, GUILD_BATTLE=6 |
| MessageTogType | family=1, PVP=2, friend=3, exchange=4, team=5 |
| MinRoleImage | Min=99999 |
| MirrorImage+MirrorType | Horizontal=0, Vertical=1, Quarter=2 |
| ModuleType | Task=1001, Team=1002, Trading=1003, Famly=1004, Ride=1005, Bag=1006, Activity=1007, Ranking=1008, VIP=1009, Recording=1010, Transfer=1011, Store=1012, Setting=1013 |
| NetDataManager+EItemForm | Bag=0, PublicWarehouse=1, PrivateWarehouse=2 |
| NpcConst | NpcTransmigraPet=999999994, NpcTransferScript=999999995, NpcBattleScript=999999996, NpcTaskAcceptScript=999999997, NpcTaskFinishScript=999999998, NpcDefaultMsgScript=999999999, NpcDefaultTalkMsg=999999999, NpcResetScript=300002, NpcStoreScript=300000, NpcComposeScript=300014, NpcPetSkillScript=300006, NpcSavePointScript=300001, NpcReserveHpMpScript=300002, NpcJoinBusScript=300007, NpcJoinAirPlanScript=300008, NpcAddBeautyBuffScript=300010, NpcAddLuckBuffScript=300015, NpcCallFamilyMemberScript=300011, NpcWarpConditionScript=300017, NpcJoinFamilyBattleScript=300012, NpcWarpToFamilyBattleMapScript=300013, NpcOutFamilyBattleMapScript=300023, NpcPkSystemScript=3142, NpcPickupPetNpcScript=300020, |
| ObjType | TILE=0, BUILDING=1, NPC=2, ROLE=3 |
| OutLineShape | Contour=0, Frame=1 |
| PartnerType | ALL=0, ATTACK=1, DEFENSE=2, HEAL=3, ASSIST=4 |
| PaticleAttackEffect | NONE=0, CRIT_ATTACK=1, PE_BalloonPopExplosion=2, PE_BloodExplosion2D=3 |
| PetStatus | MIN=0, REST=1, BATTLE=2, RIDE=3, MAX=4 |
| PiaoXueType | None=0, UpDown=1, Left=2, Right=3, Rand=4 |
| PlayMode | Repeat=0, Once=1 |
| ProtocolTypeEnum | RAWMSG=0, SPROTOMSG=1 |
| PutInType | Radio=0, MultiSelect=1 |
| RankType | PET_WULI=0, PET_BUYI=1, PET_HULU=2, PET_KEKEER=3, PET_KAIBI=4, PET_BUKE=5, PET_JIAMEI=6, PET_WEIWEI=7, PET_DUWA=8, PET_FEILONG=9, PET_DASHETOU=10, PET_WUGUI=11, PET_SHAYU=12, PET_HAIZHUREN=13, PET_ZHUTOUYU=14, PET_HUBABA=15, PET_RENLONG=16, PET_XINIU=17, PET_LEILONG=18, PET_BAOLONG=19, PET_SHUILONG=20, PET_XINGXING=21, PET_KAKEER=22, PET_LAOHU=23, PET_CHANGMAOXIANG=24, PET_QIBAO=25, PET_SHANYANG=26, PET_CHUANSHANJIA=27, PET_OTHER=100, PET_POWER=101, PET_HP=102, PET_ATTACK=103, PET_DEFENSE=104, PET_AGILE=105, ROLE_LEVEL=200, ROLE_POWER=201, ROLE_STONE=202, ROLE_GOLD=203, ROLE_DENAR=204, EQUIP_POWER=999, EQUIP_FIST=1000, EQUIP_AXE=1001, EQUIP_CLUB=1002, EQUIP_SPEAR=1003, EQUIP_BOW=1004, EQUIP_ |
| RecordMode | Normal=0, Stream=1 |
| RedTipType | EMAIL=1, FRIEND=2, GUILD=3, ROLE=4, AH=5, TEAM=6 |
| RewardType | NONE=0, DENAR=1, GOLD=2, STONE=3, ROLE_EXP=4, PET_EXP=5, PET=6, ITEM=7, LOCK_DENAR=8, GUILD_DEDICATION=9, ACTIVE=10 |
| RidePifuType | ride=0, pifu=1, guanghuan=2, petArua=3 |
| RoleImageType | NORMAL=1, ROLE=2, RIDE=3, BUFF=4, EFFECT=5, ARUA=6, ATTACKEFFECT=7, FRONTARUA=8, BORNARUA=9, BORNFRONTARUA=10, WING=11, REMOTEATTACKEFFECT=12 |
| RoleStatus | NORMAL=0, BATTLE=1, WATCH=2, TRANS=3, WATCHV=98, OFFLINE=99 |
| RoleType | NONE=0, ROLE=1, PET=2, PARTNER=3, MONSTER=4, NPC=5, NPC_PET=6, RIDE_PET=7, GUILD_BUILD=8, UIRole=99, BATTLE=100 |
| SaveWindow | ROLE_TILE=1, ROLE_TRANS=2, ROLE_WINDOW=3, ITEM_WINDOW=4, PET_WINDOW=5, TEAM_WINDOW=6, GUILD_WINDOW=7, TASK_WINDOW=8, AH_WINDOW=9, SHOP_WINDOW=10, RECHARGE_WINDOW=11, SETUP_WINDOW=12, FAST_WINDOW=13, ROLE_ARUA=14, ROLE_FRIEND=15, ROLE_EMAIL=16, ROLE_MAP=17 |
| SceneEnum | SCENE_SPLASH=0, SCENE_NEW_LOGIN=1, SCENE_NEW_MAIN=2, SCENE_EMPTY=3 |
| ScriptButtonType | BATTLE=1, TASK=2, FUNC=3, WARP=4 |
| SelectPetItemType | Pet=0, Item=1 |
| ShieldRoleMask | MainRole=1, TeamRole=2, Npc=4, Family=8, Friend=16, Other=32 |
| ShopBoothFouceType | FOUCE=1, UNFOUCE=2 |
| ShopBoothGoodsType | ITEM=1, PET=2 |
| ShopBoothOperate | NONE=0, UP=1, DOWN=2 |
| ShopBoothRecordType | SELL_RECORD=1, BUY_RECORD=2 |
| ShopMallMainGroup | SALE=1, DENAR=2, GOLD=3, STONE=4, LOCK_DENAR=5 |
| ShowPetType | bag=0, warehouse=1, warehouseBag=2 |
| SkillCostType | NONE=0, HP=101, HP_PERCENT=102, MP=201, MP_PERCENT=202, SP=301, SP_PERCENT=302 |
| SkillQualityType | GRAY=0, WHITE=1, GREEN=2, BLUE=3, PURPLE=4, ORANGE=5, RED=6 |
| SkillResult | SUCCESS=0, HP_NOT_ENOUGH=1, MP_NOT_ENOUGH=2, SP_NOT_ENOUGH=3, SEALED=4, OTHER=5, CAPTURE_NOT_PVE=6, CAPTURE_NOT_ALLOW=7, CAPTURE_FAIL=8, CAPTURE_NOT_MONSTER=9, CAPTURE_PET_FULL=10, NO_TARGET=11, EQUIP_FAIL=12 |
| SkillType | PHYSICAL=1, MAGIC=2 |
| SkillTypeInfo | STUDY=1, SUIT=2 |
| SnapStatus | NoTargetSet=0, TargetHasSet=1, SnapMoving=2, SnapMoveFinish=3 |
| SocketDriver+E_ConnectState | ConnectNone=0, ConnectFail=1, PacketGame=2, DisconnectGame=3, ReConnectGameFail=4, ReConnectAutoFail=5 |
| SoundEnum | BUTTON_CLICK=204, BUTTON_CLICK_1=217, WINDOWS_CLOSE=203, WINDOWS_OPEN=202, BATTLE_BEGIN=215, ERROR=213, ADD_BASEPOINT=100, FLY_ONE=11, FLY_TWO=66, ATTACK=250, HEAL=102 |
| SpriteStoneAddType | STAMINA=1, VITALITY=2, STRENGTH=3, SPEED=4, MAGIC=5 |
| Sproto.SprotoRpc+RpcType | REQUEST=1, RESPONSE=2 |
| StatusType | operability=0, noOperability=1 |
| SystemNotify | HEAL_FULL=1, STONE_PET_GROW=2, RIDE_LEVEL_LESS=3, PET_TRANS_OK=4, FETCH_EMAIL_FULL=5, AIR_BUS_GO=6, AIR_BUS_OVER=7, MANOR_FIGHT_COUNT_DOWN=8, MANOR_CALL=9, MANOR_JOIN_OK=10, MANOR_FIGHT_BEGIN_COUNT_DOWN=11, MANOR_CALL_OK=12, MANOR_EXIT_FIGHT=13, RIDE_NOT_RULE=14, PET_REHEATING_ITEM_NOT_ENOUGH=15, ROLE_TRANS_ASK=16, ROLE_REFUSE_TRANS=17, ROLE_TRANS_PLACE_NOT_ENOUGH_ITEM=18, ROLE_TRANS_PLACE_NOT_ENOUGH_PET=19, ANSWER_ERROR=20, GUILD_BUILD_LEVEL_UP=21, GUILD_TASK_LIMIT_COUNT=22, GUILD_BUILD_ADD_POINT=23, GUILD_ADD_ACTIVEPOINT=24, PET_FULL=25, ITEM_FULL_TO_MAIL=26, PET_FULL_TO_MAIL=27, STUDY_RIDE_NOT_ENOUGH=28, NPC_TALK_IN_TEAM=29, PET_FUSION_ADD_TIME=30, PET_FUSION_CAN_EAT=31, PET_FUSION_GROW_M |
| SystemPara | None=0, ItemName=1, PetName=2, NpcName=3, ManorName=4, CurrencyName=5, TaskName=6, MapName=7, AruaName=8, TileName=9, TrailName=10, SkinName=11, SkillName=12, PetNameByIndex=13, AttackCityMonseterName=14, TaskGroupName=15, DateA=16 |
| TaskGroupType | MIN=1, MAIN_LINE=1, SIDE_LINE=2, GUIDE=3, DAILY=4, DUNGEO=5, ASSAULT=6, JOB=7, NEW=8, GUILD_TASK_1=9, GUILD_TASK_2=10, GUILD_TASK_3=11, MAX=12 |
| TaskStatus | WAIT=-1, NONE=0, ACCEPT=1, FINISH=2, GIVEUP=3, UPDATE=4, ACCEPT_CONDITON=5, NOFINISH=100 |
| TaskType | TALK=1, MONSTER=2, PATROL=3, BATTLE=4, TASK_ITEM=5, ITEM=6, PET=7, USEITEM=8, ANSWER=9, CODE=12 |
| TeamNotify | LEADER_DEAL_RESULT=1, INVITED_DEAL_RESULT=2, MEMBER_KICK=3, MEMBER_LEAVE=4, DISBAND_TEAM=5, LEAVE_NEW_LEADER=6, NEW_LEADER=7, JOIN_TEAM=8, APPLY_JOIN_REFUSE=10, TEAM_FULL=11, APPLY_INVALID=12, APPLY_NOT_LEADER=13, INVITE_JOIN_TEAM=14, TRANSFER_LEADER=15, RECALL_MEMBER_BATTLE=16, RETURN_CALL=17, RECALL_REFUSE=18, OTHER_APPLY_LEADER=19, APPLY_LEADER=20, APPLY_LEADER_NOT_TEAM=21, APPLY_LEADER_REFUSE=22, MEMBER_RETURN=23, LEADER_CAN_NOT_AFK=24, TRANSFER_LEADER_REFUSE=25 |
| TeamStatus | NONE=0, LEADER=1, MEMBER=2, AFK=3, PRE_RETURN=4, PRE_LEAVE=5, LOGOUT=6 |
| UIFamilyPanelType | Affairs=0, ClanWars=1, Manor=2 |
| UIPriority | LowLevel=0, Normal=100, Resident=200, MidLevel=500, HeightLevel=600, Warning=1000, HighestLevel=1500 |
| UISelectItemType | Item=0, Equip=1, All=2, Other=3 |
| UIStonePayShowMode | Pay=0, Power=1, Fund=2, Frist=3, War=4, Day=5, TopUp=6 |
| WuQiType | GJian=0, HXBiao=1, STou=2, FTou=3 |
| XiaLaType | ChangDu1=0, ChangDu2=1, ChangDu3=2, Yanse=3, Yanse2=4, DuoKuang1=5 |
| lotteyType | start=0, lottery=1, Double=2, bigSmall=3, shaizi=4 |
| propertyType | None=0, earth=1, water=2, fire=3, wind=4 |
| tabtoy.FieldType | None=0, Int32=1, Int64=2, UInt32=3, UInt64=4, Float=5, String=6, Bool=7, Enum=8, Struct=9 |
| tabtoy.LogLevel | Debug=0, Info=1, Warnning=2, Error=3 |
| Data.ExchangeItemNewInfocurrencyEnum | none=0, stone=3, gold=2, denar=1, lockdenar=8 |
| Data.ItemBookInfoEnumA | none=0, stone=3, gold=2, denar=1, lockdenar=8 |
| Data.LotterycurrencyEnumA | none=0, stone=3, gold=2, denar=1, lockdenar=8, active=10 |
| Data.MowangFubenSetcurrencyEnumA | none=0, stone=3, gold=2, denar=1, lockdenar=8, active=10 |
| Data.NewItemMaketranscurrencyEnum | none=0, stone=3, gold=2, denar=1, lockdenar=8 |
| Data.PetAttrRandcurrencyEnum | none=0, stone=3, gold=2, denar=1, lockdenar=8 |
| Data.PetDataInfooEnumA | none=0, stone=3, gold=2, denar=1, lockdenar=8 |
| Data.PetRankDataInfooEnumA | none=0, stone=3, gold=2, denar=1, lockdenar=8 |
| Data.activityrequirecurrencyEnumA | none=0, stone=3, gold=2, denar=1, lockdenar=8, active=10 |
| Data.anwsercurrencyEnum | none=0, stone=3, gold=2, denar=1, active=10, lockdenar=8 |
| Data.currencyEnum | none=0, stone=3, gold=2, denar=1, lockdenar=8 |
| Data.currencyType | none=0, stone=3, gold=2, denar=1 |
| Data.dmgElement | dmgElement1=0, dmgElement3=1, dmgElement4=2, dmgElement5=3, dmgElement6=4, dmgElement7=5, dmgElement8=6, dmgElement9=7, dmgElement2=8 |
| Data.effectType | effectType0=0, effectType1=1, effectType2=2 |
| Data.huiluCostcurrencyEnum | none=0, stone=3, gold=2, denar=1, lockdenar=8 |
| Data.mainRankType | mainRankType0=0, mainRankType1=1, mainRankType2=2, mainRankType3=3 |
| Data.npcScriptTypeName | enum0=0, enum1=1, enum2=2, enum3=3, enum4=4 |
| Data.otranscurrencyEnum | none=0, stone=3, gold=2, denar=1, lockdenar=8 |
| Data.petbabytranscurrencyEnum | none=0, stone=3, gold=2, denar=1, lockdenar=8 |
| Data.rewardType | none=0, denar=1, gold=2, stone=3, roleExp=4, petExp=5, pet=6, item=7, lockDenar=8 |
| Data.rideTypeDef | none=0, ride=14, sit=15, ride13=16, ride1=17, ride2=18, ride3=19, ride4=20, ride5=21, ride6=22, ride7=23, ride8=24, ride9=25, ride10=26, ride11=27, ride12=28, ride15=29, ride16=30, ride17=31, ride18=32, ride19=33, ride20=34, ride21=35, ride22=36, ride23=37, ride24=38, ride25=39, ride26=40, ride27=41, ride28=42, ride29=43, ride30=44, ride31=45, ride32=46, ride33=47, ride34=48, ride35=49, ride36=50, |
| Data.roleDef | none=0, role1=1, role2=2, role3=3, role4=4, role5=5, role6=6, role7=7, role8=8, role9=9, role10=10, role11=11, role12=12 |
| Data.skillEffectType | skilleffectType0=0, skilleffectType1=1, skilleffectType2=2 |
| Data.statusEffectType | Type0=0, Type1=1101, Type2=1102, Type3=1112, Type4=1201, Type5=1202, Type6=1301, Type7=1302, Type8=1401, Type9=1402, Type10=1412, Type11=1501, Type12=1601, Type13=1602, Type14=2001, Type15=2002, Type16=2003, Type17=2004, Type18=2101, Type19=2102, Type20=2103, Type21=2104, Type22=2105, Type23=2106, Type24=2107, Type25=2108, Type26=2109, Type27=2110, Type28=2111, Type29=2201, Type30=3001, Type31=300 |
| Data.subRankType | subRankType0=0, subRankType1=1, subRankType2=2, subRankType3=3, subRankType4=4, subRankType5=5, subRankType6=6, subRankType7=7, subRankType8=8, subRankType9=9, subRankType10=10, subRankType11=11, subRankType12=12, subRankType13=13, subRankType14=14, subRankType15=15, subRankType16=16, subRankType17=17, subRankType18=18, subRankType19=19, subRankType20=20, subRankType21=21, subRankType22=22, subRan |
| Data.taskinfoexcurrencyEnum | none=0, stone=3, gold=2, denar=1, lockdenar=8, active=10 |
| Data.transLevelInfoEnum | type0=0, type1=1, type2=2, type3=3, type4=4, type5=5, type6=6, type7=7, type8=8, type9=9, type10=10, type11=11, type12=12, type13=13, type14=14, type15=15, type16=16, type17=17, type18=18, type19=19, type20=20, type21=21, type22=22 |
| Data.transcurrencyEnum | none=0, stone=3, gold=2, denar=1, lockdenar=8 |
| Data.viprequirecurrencyEnumA | none=0, stone=3, gold=2, denar=1, lockdenar=8, active=10 |
