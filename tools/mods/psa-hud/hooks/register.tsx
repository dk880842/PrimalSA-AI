import { atom, read, update } from 'claude-code'
import type { BoxProps, ElementConstructor, EngineInterface, Register, RenderElement, TextProps } from 'claude-code'

import type { Banner, ErrEntry, HudParts, PaneLine, ProgLine, Stat, WatchLine, WatchTone, WinProg, WinView } from '../types'

// 讀 HUD 的腳本：背景截圖 + Windows OCR，印一行 JSON（見 tools/gui/stat.ps1）
// 遊戲畫面由獨立的鏡像視窗顯示（tools/gui/mirror.sh），pane 只放文字
// 路徑由 session cwd 推算（WSL /mnt/c/games/PrimalSA-AI、Windows C:\\games\\PrimalSA-AI、Git Bash /c/games/... 都通），
// 一律換成 Windows 路徑給 powershell.exe；還沒收到 session.start 時用預設值
const PROJECT = 'PrimalSA-AI'
let statPs1 = `C:\\games\\${PROJECT}\\tools\\gui\\stat.ps1`

export function statPathFromCwd(cwd: string): string | undefined {
  const i = cwd.indexOf(PROJECT)
  if (i < 0) return undefined
  let root = cwd.slice(0, i + PROJECT.length)
  const m = /^\/(?:mnt\/|cygdrive\/)?([a-zA-Z])\//.exec(root)
  if (m && !/^[a-zA-Z]:/.test(root)) root = `${m[1]!.toUpperCase()}:/${root.slice(m[0].length)}`
  return `${root}/tools/gui/stat.ps1`.replace(/\//g, '\\')
}
const PERIOD_MS = 15000
// 錯誤 / 改進紀錄（tools/gui/errlog.py 寫入，只留最新 100 筆，一行一筆 JSON）；讀檔很便宜，2 秒一次
// 操作 log（actions.log）照樣由 actlog.py / gui.ps1 在背景寫，只是 pane 不顯示
const LOG_PERIOD_MS = 2000
const STATE_PERIOD_MS = 1000     // 讀 state.json（watch.py 寫的即時狀態）
const LOG_MAX = 100
let logFile = `C:/games/${PROJECT}/tools/.cache/errlog.jsonl`

// 專案根目錄（保留原本的斜線形式，$.fs 接受 /mnt/c/...、C:\... 與 C:/...）
export function logPathFromCwd(cwd: string): string | undefined {
  const i = cwd.indexOf(PROJECT)
  return i < 0 ? undefined : `${cwd.slice(0, i + PROJECT.length)}/tools/.cache/errlog.jsonl`
}

function stamp(ms: number): string {
  const d = new Date(ms)
  const p = (n: number) => String(n).padStart(2, '0')
  return `${p(d.getMonth() + 1)}/${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}`
}

// errlog.jsonl → 最新在上、最多 LOG_MAX 筆；壞行略過
export function errEntries(text: string): ErrEntry[] {
  const out: ErrEntry[] = []
  for (const l of text.split(/\r?\n/)) {
    if (!l.trim()) continue
    try {
      const r = JSON.parse(l) as ErrEntry
      if (typeof r.error === 'string') out.push({ id: r.id, ts: r.ts, error: r.error, fix: r.fix ?? null, source: r.source ?? null, ...(r.client ? { client: String(r.client) } : {}) })
    } catch {
      // 壞行略過
    }
  }
  return out.slice(-LOG_MAX).reverse()
}

// 一筆紀錄的顯示文字：[錯誤] 與 [改進]（沒改進 = 待改進）。now：與 now 同一天只顯示「時:分」；n > 1：合併了幾筆（×N）
export function errLine(e: ErrEntry, now?: number, n = 1): { head: string; fix: string; pending: boolean } {
  const when = now !== undefined && new Date(now).toDateString() === new Date(e.ts).toDateString() ? stamp(e.ts).slice(6) : stamp(e.ts)
  return { head: `${when} #${e.id}${n > 1 ? ` ×${n}` : ''}${e.client ? ` [${e.client}]` : ''}${e.source ? ` [${e.source}]` : ''} ${e.error}`, fix: e.fix ? `→ 改進：${e.fix}` : '→ 待改進', pending: !e.fix }
}

// ───────────────────────── 即時狀態監看（watch.py）：路徑 / 解析 / 顯示 / 監督 ─────────────────────────
// 計畫：notes/plan-watch-state.md §1.3～1.5、§7 第 4 階段。只管「自己 spawn 的」子程序；其他 session / 平台只讀 state.json

// 專案根目錄與其下檔案（保留 cwd 的斜線形式，$.fs 接受 /mnt/c/...、C:\... 與 C:/...）
export function rootFromCwd(cwd: string): string | undefined {
  const i = cwd.indexOf(PROJECT)
  return i < 0 ? undefined : cwd.slice(0, i + PROJECT.length)
}

// ── 多視窗（第 3d 步，2026-10-15 使用者定案 D5：一個 session 顯示全部視窗）──
// 視窗身分 = 遊戲程序名稱（tools/gui/clients.py）。主視窗 PrimalSA 沿用舊路徑；其他視窗的狀態檔在 tools/.cache/clients/<程序名>/、
// 事件 log 在 notes/clients/<程序名>/（與 clients.cache_dir / notes_dir 相同規則；名稱由 clients.py running --rostered 給，已是資料夾名寫法）
export const MAIN_CLIENT = 'PrimalSA'
export const isMainClient = (c?: string | null) => !c || c.toLowerCase() === MAIN_CLIENT.toLowerCase()
export const cacheRel = (c?: string | null) => (isMainClient(c) ? 'tools/.cache' : `tools/.cache/clients/${c}`)
export const notesRel = (c?: string | null) => (isMainClient(c) ? 'notes' : `notes/clients/${c}`)
export const stateFileFromCwd = (cwd: string, client?: string) => { const r = rootFromCwd(cwd); return r ? `${r}/${cacheRel(client)}/state.json` : undefined }
export const hudCfgFromCwd = (cwd: string, client?: string) => { const r = rootFromCwd(cwd); return r ? `${r}/${cacheRel(client)}/psa-hud.json` : undefined }
export const buffTimeFromCwd = (cwd: string, client?: string) => { const r = rootFromCwd(cwd); return r ? `${r}/${cacheRel(client)}/bufftime.json` : undefined }   // bufftime.py 寫的預計到期
export const questLogFromCwd = (cwd: string, client?: string) => { const r = rootFromCwd(cwd); return r ? `${r}/${notesRel(client)}/quest-events.log` : undefined }
export const verifyHaltFromCwd = (cwd: string, client?: string) => { const r = rootFromCwd(cwd); return r ? `${r}/${cacheRel(client)}/verify-halt.json` : undefined }   // 每視窗一份（verifyhalt.path）

// actions.log 是全部視窗共用的一份：非主視窗的行是「HH:MM:SS [程序名] …」（actlog.py / gui.ps1），主視窗沒有標籤。
// 取出某個視窗的行；非主視窗的行去掉標籤（後面的解析照單視窗格式）。undefined（讀不到）原樣回
const ACT_TAG = /^(\d\d:\d\d:\d\d) \[(PrimalSA\d*)\] /i
export function actionsFor(text: string | undefined, client?: string): string | undefined {
  if (text === undefined) return undefined
  const main = isMainClient(client)
  const out: string[] = []
  for (const l of text.split(/\r?\n/)) {
    const m = ACT_TAG.exec(l)
    if (main) { if (!m) out.push(l) }
    else if (m && m[2]!.toLowerCase() === client!.toLowerCase()) out.push(`${m[1]} ${l.slice(m[0].length)}`)
  }
  return out.join('\n')
}

// clients.py running --rostered 的輸出 → 要顯示的視窗（主視窗永遠在第一個，其他照輸出順序、去重）；退出碼非 0 = 查不到 → undefined（維持現狀）
export function parseRunning(exitCode: number, stdout: string): string[] | undefined {
  if (exitCode !== 0) return undefined
  const out = [MAIN_CLIENT]
  for (const l of stdout.split(/\r?\n/)) {
    const n = l.trim()
    if (/^[A-Za-z0-9_.-]{1,64}$/.test(n) && !out.some(x => x.toLowerCase() === n.toLowerCase())) out.push(n)
  }
  return out
}

// 視窗清單變化（純函式）：要新增的、要移除的（連續 MISS_LIMIT 次偵測不到才移除，避免一次查詢失誤就殺掉 watch；主視窗永不移除）
export const MISS_LIMIT = 2
export function diffClients(cur: { name: string; misses: number }[], want: string[]): { add: string[]; drop: string[]; misses: Record<string, number> } {
  const has = (l: string[], n: string) => l.some(x => x.toLowerCase() === n.toLowerCase())
  const add = want.filter(n => !cur.some(c => c.name.toLowerCase() === n.toLowerCase()))
  const drop: string[] = []
  const misses: Record<string, number> = {}
  for (const c of cur) {
    if (isMainClient(c.name) || has(want, c.name)) { misses[c.name] = 0; continue }
    const m = c.misses + 1
    if (m >= MISS_LIMIT) drop.push(c.name)
    else misses[c.name] = m
  }
  return { add, drop, misses }
}

// /psa-hud watch|ack 的對象：不給 / all = 全部偵測到的視窗；程序名（大小寫不分）= 那一個；找不到 → 錯誤訊息字串
export function pickTargets(names: string[], arg: string | undefined): string[] | string {
  if (!arg || arg.toLowerCase() === 'all') return [...names]
  const hit = names.find(n => n.toLowerCase() === arg.toLowerCase())
  return hit ? [hit] : `找不到視窗 ${arg}（目前偵測到：${names.join('、')}；偵測每 30 秒一次，視窗要在 clients.py ROSTERS 登錄）`
}

// spawn 子程序的環境變數：主視窗與改版前逐字相同；其他視窗加 PSA_CLIENT。
// WSL 上用 Windows 直譯器（python.exe）時，WSL → Windows 只傳 WSLENV 列出的變數 → 一併列進 WSLENV（與 winenv.client_env / gui.sh 同規則）。
// 取捨：$.process 的 env 是「蓋在 host 環境上」，讀不到 host 原本的 WSLENV，所以這種情況會蓋掉它（只影響 watch 子程序；Linux 直譯器時 watch 自己的 winenv 會處理）
export function clientEnv(client: string | undefined, base: Record<string, string>, pythonPath: string | undefined, cwd: string): Record<string, string> {
  if (isMainClient(client)) return base
  const env: Record<string, string> = { ...base, PSA_CLIENT: client! }
  if (pythonPath && /^[a-zA-Z]:|\.exe$/i.test(pythonPath) && cwd.startsWith('/mnt/')) env.WSLENV = Object.keys(env).join(':')
  return env
}

// watch.py 的絕對路徑：直譯器是 Windows 的（C:\...\python.exe、.exe）→ Windows 路徑；Linux 直譯器 → /mnt/<磁碟>/ 原生路徑。
// 不給直譯器（uv run 退路）時由 cwd 的形式推斷：/mnt/c/... 當 WSL（Linux 路徑），其他當 Windows
export function watchPathFromCwd(cwd: string, pythonPath?: string, file = 'watch.py'): string | undefined {
  const root = rootFromCwd(cwd)
  if (!root) return undefined
  const m = /^(?:\/(?:mnt\/|cygdrive\/)?([a-zA-Z])\/|([a-zA-Z]):[\\/])(.*)$/.exec(root)
  if (!m) return `${root}/tools/gui/${file}`           // 純 Linux 路徑（不是 /mnt/c 之類）
  const drive = (m[1] ?? m[2])!
  const rest = m[3]!.replace(/\\/g, '/')
  const isWin = pythonPath !== undefined ? /^[a-zA-Z]:|\.exe$/i.test(pythonPath) : !cwd.startsWith('/mnt/')
  return isWin
    ? `${drive.toUpperCase()}:\\${rest.replace(/\//g, '\\')}\\tools\\gui\\${file}`
    : `/mnt/${drive.toLowerCase()}/${rest}/tools/gui/${file}`
}

// state.hud（第 3 階段）：欄位級 {v, ts}；ok = 最近一次讀到資料；stale = 被蓋住 / 太久沒更新（欄位值保留舊的）
type WF<T> = { v?: T; ts?: number }
export type WHud = {
  ok?: boolean; stale?: boolean; age_s?: number | null; ts?: number | null
  level?: WF<string>; hp?: WF<number>; hpPct?: WF<number>; mp?: WF<number>; mpPct?: WF<number>
  name?: WF<string> & { stale?: boolean; conflict?: boolean }
  pet?: { level?: WF<string>; hp?: WF<number>; name?: WF<string> & { stale?: boolean } }
  map?: WF<string> & { id?: number; stale?: boolean }   // stale = 座標太久沒讀到（watch MAP_STALE_S），值是舊的
  pos?: WF<number[]> & { stale?: boolean }
  buffs?: WF<string[]> & { stale?: boolean }   // 頭像下方 buff：'exp'（2倍智慧果）/ 'dragon'（龍王的守護）
}

// state.json（只認 v 主版本 1；不認得的鍵一律忽略）
type WState = {
  v?: number; seq?: number; phase?: string; ts?: number
  watcher?: { token?: string; running?: boolean; interval?: number }
  screen?: { label?: string; age_s?: number; state?: string; full?: boolean; annot?: string[]; enc_on?: boolean | null }
  hud?: WHud
  flags?: { verify_suspect?: boolean; netwatch_halt?: boolean }
  alerts?: { msg?: string; line?: string }[]
}
export function parseState(text: string | undefined): { state: WState | null; badVersion: number | null } {
  if (!text) return { state: null, badVersion: null }
  try {
    const d = JSON.parse(text) as WState
    if (!d || typeof d !== 'object') return { state: null, badVersion: null }
    if (Math.floor(Number(d.v)) !== 1) return { state: null, badVersion: typeof d.v === 'number' ? d.v : -1 }
    return { state: d, badVersion: null }
  } catch {
    return { state: null, badVersion: null }   // 寫到一半 / 壞檔：這輪當沒讀到（下一秒再讀）
  }
}

// 退避：2 → 5 → 15 → 30 → 60 s（上限 60 s），±20% jitter
const BACKOFF_S = [2, 5, 15, 30, 60]
export function backoffMs(idx: number, rnd: number): number {
  return Math.round(BACKOFF_S[Math.min(idx, BACKOFF_S.length - 1)]! * 1000 * (0.8 + 0.4 * rnd))
}
export const SHORT_RUN_MS = 30000     // 跑不到 30 s 算「立刻死」
export const GOOD_RUN_MS = 60000      // 跑滿 60 s 歸零
export const MAX_SHORT_RUNS = 5       // 連續 5 次跑不到 30 s 就停止重開
export const GRACE3_MS = 3000         // 啟動後第一次拿到退出碼 3：可能是熱重載時舊子程序還在收尾，等 3 s 重試一次

export type ExitIn = { code: number | null; ranMs: number; progressed: boolean; consec: number; idx: number; grace: boolean }
export type ExitOut = { action: 'retry' | 'ro3' | 'ro6' | 'stopped' | 'failed'; delayMs: number; consec: number; idx: number; grace: boolean }
// 子程序結束後怎麼辦（純函式）
export function decideExit(i: ExitIn, rnd: number): ExitOut {
  const keep = { consec: i.consec, idx: i.idx, grace: i.grace }
  if (i.code === 5) return { action: 'stopped', delayMs: 0, ...keep }
  if (i.code === 6) return { action: 'ro6', delayMs: 0, ...keep }
  if (i.code === 3) {
    if (i.grace) return { action: 'retry', delayMs: GRACE3_MS, ...keep, grace: false }
    return { action: 'ro3', delayMs: 0, ...keep }
  }
  let { consec, idx } = i
  if (i.ranMs >= GOOD_RUN_MS || i.progressed) { consec = 0; idx = 0 }
  else if (i.ranMs < SHORT_RUN_MS) consec++
  else consec = 0
  if (consec >= MAX_SHORT_RUNS) return { action: 'failed', delayMs: 0, consec, idx, grace: false }
  return { action: 'retry', delayMs: backoffMs(idx, rnd), consec, idx: idx + 1, grace: false }
}

// 卡住門檻：phase=starting 或還沒看到任何進展（剛 spawn）45 s；其他 max(10 s, 3×interval)
export function stallThresholdMs(phase: string | null | undefined, interval: number | null | undefined, progressed: boolean): number {
  if (phase === 'starting' || !progressed) return 45000
  return Math.max(10000, 3 * (interval && interval > 0 ? interval : 0.5) * 1000)
}

type Chunk = { stream: string; text: string }
type Streamer = {
  next: () => Promise<{ done?: boolean; value?: unknown }>
  return?: (v?: unknown) => Promise<unknown>
}
export type SupDeps = {
  spawn: () => Streamer | Promise<Streamer>      // 組 argv + $.process.spawn
  now: () => Promise<number>                     // 本地毫秒
  sleep: (ms: number) => Promise<void>
  rnd: () => number
  stopCli: () => Promise<void>                   // watch.py --stop（寫 psa-hud.json watch=false + watch.stop，等 watch 結束）
  saveCfg: (on: boolean) => Promise<void>        // 寫 psa-hud.json（唯一依據）
}
export type SupStatus = 'idle' | 'running' | 'waiting' | 'ro3' | 'ro6' | 'failed' | 'stopped' | 'off'

// 監督自己 spawn 的 watch 子程序（不依賴 $：測試用假 deps）
export class Supervisor {
  status: SupStatus = 'idle'
  spawns = 0
  lastCode: number | null = null
  stalls = 0
  tail = ''                        // 子程序 stdout / stderr 最後約 20 行
  seenAt = 0                       // (token, seq) 最近一次變化的本地時間（顯示年齡、判斷沒更新用）
  private key: string | null = null
  private epoch = 0
  private spawnAt = 0
  private progressed = false
  private abortRun: (() => void) | null = null
  cfgOn = true
  constructor(private d: SupDeps) {}

  start(): void {
    this.epoch++
    this.cfgOn = true
    this.status = 'idle'
    void this.loop(this.epoch)
  }

  // 每秒呼叫：key = `${token}:${seq}` 或 null
  async observe(key: string | null, phase: string | null, interval: number | null): Promise<void> {
    const now = await this.d.now()
    if (key !== this.key) {
      this.key = key
      this.seenAt = now
      if (key && this.status === 'running') this.progressed = true
    }
    if (this.status === 'running' && this.abortRun) {
      const last = Math.max(this.seenAt, this.spawnAt)
      if (now - last > stallThresholdMs(phase, interval, this.progressed)) {
        this.stalls++
        this.status = 'waiting'          // 先換狀態，避免同一次卡住重複觸發
        this.abortRun()
      }
    }
  }

  private pushTail(text: string): void {
    this.tail = (this.tail + text).split('\n').slice(-20).join('\n').slice(-4000)
  }

  private async sleepSliced(ms: number, epoch: number): Promise<void> {
    for (let left = ms; left > 0 && epoch === this.epoch; left -= 500) await this.d.sleep(Math.min(500, left))
  }

  private async loop(epoch: number): Promise<void> {
    let consec = 0, idx = 0, grace = true
    while (epoch === this.epoch) {
      this.status = 'running'
      const t0 = await this.d.now()
      this.spawnAt = t0
      this.progressed = false
      let code: number | null = -1
      let stream: Streamer | undefined
      try {
        stream = await this.d.spawn()
        this.spawns++
      } catch (err) {
        this.pushTail(`spawn 失敗：${String(err).slice(0, 120)}\n`)
      }
      if (stream) {
        const abort = new Promise<'abort'>(res => { this.abortRun = () => res('abort') })
        try {
          for (;;) {
            // 持續讀 stdout / stderr（避免 1,048,576 字元上限卡住子程序）；被叫停就 return() 結束串流（殺子程序）
            const r = await Promise.race([stream.next(), abort])
            if (r === 'abort') {
              code = -2
              if (stream.return) void stream.return().catch(() => undefined)
              break
            }
            if (r.done) {
              const v = r.value as { code?: number | null } | undefined
              code = v?.code ?? -1
              break
            }
            this.pushTail((r.value as Chunk).text)
          }
        } catch (err) {
          this.pushTail(`串流錯誤：${String(err).slice(0, 120)}\n`)
        }
        this.abortRun = null
      }
      if (epoch !== this.epoch) return             // off / on / 重載：不判斷、不重開
      this.lastCode = code
      const ranMs = (await this.d.now()) - t0
      const o = decideExit({ code, ranMs, progressed: this.progressed, consec, idx, grace }, this.d.rnd())
      ;({ consec, idx, grace } = o)
      if (o.action === 'retry') {
        this.status = 'waiting'
        await this.sleepSliced(o.delayMs, epoch)
        continue
      }
      this.status = o.action
      return
    }
  }

  // /psa-hud watch off：寫設定 → 先 --stop（乾淨退出碼 5）→ 作廢目前迴圈並殺殘留
  async setOff(): Promise<void> {
    this.cfgOn = false
    this.epoch++
    await this.d.saveCfg(false).catch(() => undefined)
    await this.d.stopCli().catch(() => undefined)
    this.abortRun?.()
    this.status = 'off'
  }

  // 視窗關掉了（偵測不到程序）：作廢迴圈、收掉子程序；不寫設定、不送 --stop（遊戲再開時照設定重新 spawn）
  dispose(): void {
    this.epoch++
    this.abortRun?.()
    this.status = 'off'
  }

  // /psa-hud watch on：寫設定、計數歸零、立即啟動（watch.stop 由 stopCli 對面清；on 時 watch.py 自己忽略早於啟動的 stop 檔）
  async setOn(): Promise<void> {
    await this.d.saveCfg(true).catch(() => undefined)
    this.abortRun?.()
    this.stalls = 0
    this.start()
  }
}

// ── 狀態行顯示 ──
export type ViewIn = { state: WState | null; badVersion: number | null; status: SupStatus; lastCode: number | null; now: number; seenAt: number; hasFile: boolean }
// 狀態行最多幾秒沒變就提示「監看沒有更新」（沒有自己的子程序在管時）
export const STALE_HINT_MS = 10000
export function viewModel(i: ViewIn): WatchLine {
  const hints: { text: string; tone: WatchTone }[] = []
  let main: string
  if (i.badVersion != null) {
    main = '（state.json 版本不符）'
    hints.push({ text: `state.json 版本 v${i.badVersion}，這個 HUD 只認 v1`, tone: 'red' })
  } else if (!i.state) {
    main = i.hasFile ? '（state.json 讀取中）' : '（沒有狀態）'
  } else {
    main = i.state.screen?.label || '（無畫面資料）'
    // 「N 秒前」：state 內的 age_s + 本地第一次看到這個 (token, seq) 之後的經過時間；> 3 s 才顯示（不比對跨平台時鐘）
    const age = (i.state.screen?.age_s ?? 0) + Math.max(0, i.now - i.seenAt) / 1000
    if (age > 3) main += ` ｜ ${Math.floor(age)} 秒前`
  }
  const own = i.status === 'running' || i.status === 'waiting' || i.status === 'idle'
  switch (i.status) {
    case 'failed': hints.push({ text: `監看啟動失敗（最後退出碼 ${i.lastCode ?? '?'}）；/psa-hud watch on 重試`, tone: 'red' }); break
    case 'ro3': hints.push({ text: '已有 watch 在跑（不是這個 HUD 啟動的），只讀', tone: 'gray' }); break
    case 'ro6': hints.push({ text: '另一平台的 watch 正在跑，只讀（它結束後要 /psa-hud watch on）', tone: 'gray' }); break
    case 'off': hints.push({ text: '監看已關閉（/psa-hud watch on 開啟）', tone: 'gray' }); break
    case 'stopped': hints.push({ text: '監看已被要求停止（/psa-hud watch on 重開）', tone: 'gray' }); break
    case 'waiting': hints.push({ text: `監看重開中（上次退出碼 ${i.lastCode ?? '?'}）`, tone: 'yellow' }); break
    case 'idle': case 'running': if (!i.state) hints.push({ text: '監看啟動中…', tone: 'yellow' }); break
  }
  // 不是自己管的 watch（只讀 / 關閉 / 停止 / 失敗）：state 久沒更新 = 監看未執行
  if (!own && i.state && i.now - i.seenAt > STALE_HINT_MS) hints.push({ text: '監看未執行（state.json 沒有更新）', tone: 'red' })
  if (!own && !i.state && i.badVersion == null && (i.status === 'off' || i.status === 'failed' || i.status === 'stopped')) hints.push({ text: '監看未執行', tone: 'red' })
  // 黃字：畫面上有提示視窗（annotate 只標出，不代表是驗證視窗；idle + 提示視窗是最該看一眼的組合）
  if (i.state?.screen?.annot?.includes('notice_dialog')) hints.push({ text: '畫面上有提示視窗，請看一眼', tone: 'yellow' })
  if (i.state?.flags?.verify_suspect) hints.push({ text: '疑似答題 / 驗證視窗，請人工處理', tone: 'red' })
  if (i.state?.flags?.netwatch_halt) hints.push({ text: '斷線監看已暫停（netwatch.halt）', tone: 'red' })
  for (const a of (i.state?.alerts ?? []).slice(0, 2)) if (a.msg || a.line) hints.push({ text: String(a.msg || a.line).slice(0, 120), tone: 'red' })
  return { main, hints }
}

const PANE = 'psa-hud'

export const statArgv = () => ['powershell.exe', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', statPs1]

const stat = atom({ plugin: 'psa-hud', key: 'stat' } as const, null)
const acts = atom({ plugin: 'psa-hud', key: 'errs' } as const, [] as ErrEntry[])
const at = atom({ plugin: 'psa-hud', key: 'at' } as const, 0)
const hudAtom = atom({ plugin: 'psa-hud', key: 'hud' } as const, null as string | null)
const encAtom = atom({ plugin: 'psa-hud', key: 'enc' } as const, null as { text: string; warn: boolean } | null)
const prog = atom({ plugin: 'psa-hud', key: 'prog' } as const, [] as ProgLine[])
const line = atom({ plugin: 'psa-hud', key: 'line' } as const, { main: '（沒有狀態）', hints: [] } as WatchLine)
const winsAtom = atom({ plugin: 'psa-hud', key: 'wins' } as const, [] as WinView[])       // 多視窗：每視窗一份（單視窗 = 空）
const progsAtom = atom({ plugin: 'psa-hud', key: 'progs' } as const, [] as WinProg[])
const bannerAtom = atom({ plugin: 'psa-hud', key: 'banner' } as const, [] as Banner[])

// 等級字串沒有任何數字（例：寵物等級 OCR 把數字讀成 'o級'）→ 數字部分換成 ?（'?級'），不顯示怪字
export function levelText(l: string | undefined): string | undefined {
  if (!l || /\d/.test(l)) return l
  return l.endsWith('級') ? '?級' : '?'
}

// 數值拆成幾段（pane 每段一行）：who 名字 / 等級 / HP / MP、pet 寵物、loc 地圖座標
// 寵物名 '?'（沒學過 / 讀不出）不顯示，避免「寵 ? ?」這種雜訊；寵物等級讀不到才是 ?
export function statParts(s: Stat): HudParts {
  if (!s.ok) return { who: `PSA: ${s.error ?? '讀取失敗'}`, err: true }
  const v = (n: number | null | undefined) => (n == null ? '?' : String(n))
  // OCR 讀不到數字時改顯示血條比例（hpPct / mpPct），都沒有才是 ?
  const num = (n: number | null | undefined, pct: number | null | undefined) => (n != null ? String(n) : pct != null ? `${pct}%` : '?')
  if (!s.level && s.hp == null && s.mp == null && s.hpPct == null) return { who: 'PSA: 讀不到 HUD（對話 / 戰鬥 / 其他畫面蓋住，或視窗被遮）', err: true }
  const out: HudParts = { who: `${s.name ? `${s.name}  ` : ''}${levelText(s.level) || '?'}  HP ${num(s.hp, s.hpPct)}  MP ${num(s.mp, s.mpPct)}` }
  if (s.petLevel || s.petHp != null) out.pet = `寵 ${s.petName && s.petName !== '?' ? `${s.petName} ` : ''}${levelText(s.petLevel) || '?'} HP ${v(s.petHp)}`
  if (s.map || s.pos) out.loc = `${s.map ?? ''} ${s.pos ?? ''}`.trim()
  // 表格用的結構化欄位（pane 的人物 / 寵物 / 地圖列）
  out.f = {
    ...(s.name ? { name: s.name } : {}), level: levelText(s.level) || '?', hp: num(s.hp, s.hpPct), mp: num(s.mp, s.mpPct),
    ...(s.petName && s.petName !== '?' ? { petName: s.petName } : {}), ...(s.petLevel || s.petHp != null ? { petLevel: levelText(s.petLevel) || '?', petHp: v(s.petHp) } : {}),
    ...(s.map ? { map: s.map } : {}), ...(s.pos ? { pos: s.pos } : {}),
  }
  return out
}
// 分段 → 一行（/psa-hud 指令回覆、舊測試）
export const joinParts = (p: HudParts) => [p.who, p.pet, p.loc].filter(Boolean).join('  |  ') + (p.note ?? '')
export const format = (s: Stat): string => joinParts(statParts(s))

// watch 活著 = 讀得到 state，且 (token, seq) 在 STALE_HINT_MS 內有變、watcher 沒說自己 stopping（另一 session / 平台的 watch 也算）
export function watchAlive(state: WState | null, now: number, seenAt: number): boolean {
  return !!state && state.watcher?.running !== false && now - seenAt <= STALE_HINT_MS
}

const COVER_TEXT: Record<string, string> = {
  battle: '戰鬥前', dialog: '對話前', reward: '領獎前', select: '選單前', panel: '面板前', unknown: '畫面被蓋住前',
  minimized: '遊戲最小化前', no_game: '遊戲未執行前', error: '讀取失敗前',
}

// state.hud → pane 第二行（和 format 同格式）；沒有任何數值 → null。stale 時加灰字（原因 · N 秒前）
// 名字顯示：沒有欄位 → undefined（不顯示）；'?' = 不確定；舊值（stale）加結尾 ?；旁路與 OCR 不一致（conflict）加 !
export function nameText(f?: (WF<string> & { stale?: boolean; conflict?: boolean }) | null): string | undefined {
  if (!f) return undefined
  const v = f.v || '?'
  if (v === '?') return '?'
  return `${v}${f.stale ? '?' : ''}${f.conflict ? '!' : ''}`
}

// ── buff 剩餘時間（智慧果 / 龍王的守護）──
// watch 是零輸入，不會點 buff 圖示讀時間；時間來自 tools/gui/bufftime.py read 寫的本視窗 bufftime.json（預計到期 epoch 秒），pane 自己倒數。
// 圖示有沒有看 state.hud.buffs（watch 每 12 s 像素判斷）。規則（每種 buff）：
//   到期時間還沒到 → 「智慧果 剩 H:MM」（圖示讀得到且確定沒有 → 結尾加 ? 表示可能已消失）
//   圖示有、但沒讀過時間 / 時間已過 → 「智慧果 ?」並提示指令（黃字）
//   圖示沒有、也沒有有效時間 → 不顯示
const BUFF_LABEL: Record<string, string> = { exp: '智慧果', dragon: '龍王' }
export type BuffTimes = Record<string, { expires_ts?: number; read_ts?: number }>
export function parseBuffTimes(text: string | undefined): BuffTimes {
  if (!text) return {}
  try {
    const d = JSON.parse(text) as { buffs?: unknown }
    return d && typeof d.buffs === 'object' && d.buffs ? (d.buffs as BuffTimes) : {}
  } catch {
    return {}
  }
}
// 秒 → 「H:MM」（滿一天「N天H:MM」）
export function hm(sec: number): string {
  const t = Math.max(0, Math.floor(sec / 60))
  const d = Math.floor(t / 1440), h = Math.floor((t % 1440) / 60), m = t % 60
  return `${d ? `${d}天` : ''}${h}:${String(m).padStart(2, '0')}`
}
export const BUFFTIME_CMD = 'bufftime.py read'
export function buffLine(b: (WF<string[]> & { stale?: boolean }) | null | undefined, times: BuffTimes, now: number): { text: string; warn: boolean } | undefined {
  const icons = Array.isArray(b?.v) ? b!.v : undefined
  const parts: string[] = []
  let unknown = false
  for (const k of ['exp', 'dragon']) {
    const icon = icons?.includes(k) ?? false
    const exp = times[k]?.expires_ts
    const left = typeof exp === 'number' ? exp - now / 1000 : undefined
    const gone = !!icons && !icon && !b?.stale          // 圖示讀得到且確定沒有
    if (left !== undefined && left > 0) parts.push(`${BUFF_LABEL[k]} 剩 ${hm(left)}${gone ? '?' : ''}`)
    else if (icon) { parts.push(`${BUFF_LABEL[k]} ?`); unknown = true }
  }
  if (!parts.length) return undefined
  return { text: parts.join(' · ') + (unknown ? `（${BUFFTIME_CMD}）` : ''), warn: unknown }
}

// 遇敵狀態：screen.enc_on（watch 依右下「取消遇敵」鈕：true 開 / false 主畫面看不到 / null 戰鬥或面板蓋住不判）。
// null / 沒欄位時沿用 last（最後已知值）並加 ?；都沒有 → undefined（不顯示）。
// 龍王的守護只顯示在 Buff 列（buffLine），這裡不加龍王括號說明（2026-10-15 使用者）。warn = 不遇敵（黃字提醒掛機可能停了）
export function encText(state: WState | null, last?: boolean): { text: string; warn: boolean; val?: boolean } | undefined {
  const cur = state?.screen?.enc_on
  const val = typeof cur === 'boolean' ? cur : last
  if (val === undefined) return undefined
  const q = typeof cur === 'boolean' ? '' : ' ?'
  const text = val ? `遇敵中${q}` : `不遇敵${q}`
  return { text, warn: !val, val }
}

// state.hud → 分段（pane 每段一行）；沒有任何數值 → null。stale 時 note =（原因 · N 秒前）
export function hudParts(state: WState | null, now: number, seenAt: number): HudParts | null {
  const h = state?.hud
  if (!h) return null
  const v = <T,>(f?: WF<T>): T | undefined => f?.v
  const pos = v(h.pos)
  const ms = mapStale(h) ? '?' : ''           // 座標太久沒讀到（例：地圖名折兩行）：地名 / 座標是舊值，加 ?
  const s: Stat = {
    ok: true, name: nameText(h.name), petName: nameText(h.pet?.name), level: v(h.level), hp: v(h.hp) ?? null, hpPct: v(h.hpPct) ?? null, mp: v(h.mp) ?? null, mpPct: v(h.mpPct) ?? null,
    petLevel: v(h.pet?.level), petHp: v(h.pet?.hp) ?? null, map: v(h.map) ? `${v(h.map)}${ms}` : undefined,
    pos: pos && h.map?.id != null ? `${h.map.id}:${pos[0]},${pos[1]}${ms}` : pos ? `${pos[0]},${pos[1]}${ms}` : undefined,
  }
  if (!s.level && s.hp == null && s.mp == null && s.hpPct == null && !s.petLevel && !s.map && !s.pos) return null   // 只有名字不算有資料
  const p = statParts(s)
  if (h.stale) {
    const age = Math.round((h.age_s ?? 0) + Math.max(0, now - seenAt) / 1000)
    const why = COVER_TEXT[state?.screen?.state ?? ''] ?? '讀取中'
    p.note = `（${why} · ${age}s 前）`
  }
  return p
}
// 同內容一行（hudAtom / /psa-hud 指令回覆）；buff 改在 pane 的 buff 行顯示，這裡不帶
export function hudText(state: WState | null, now: number, seenAt: number): string | null {
  const p = hudParts(state, now, seenAt)
  return p ? joinParts(p) : null
}

async function poll($: EngineInterface): Promise<Stat> {
  try {
    const { exitCode, stdout, stderr } = await $.process.run(statArgv(), { timeoutMs: 10000 })
    const line = stdout.trim().split('\n').pop()?.trim() ?? ''
    if (exitCode !== 0 || !line.startsWith('{')) return { ok: false, error: `讀取失敗 ${stderr.trim().slice(0, 80)}` }
    return JSON.parse(line) as Stat
  } catch (err) {
    return { ok: false, error: `讀取失敗 ${String(err).slice(0, 80)}` }
  }
}

// 上一次讀取還沒結束就不再開新的（約 1 秒，計時器 15 秒一次）
let busy = false

// watch 活著時（tickState 每秒更新）等級 / HP 改讀 state.hud，不再 spawn 一次性 stat.ps1；watch 不在才退回
let hudAlive = false

async function refresh($: EngineInterface): Promise<Stat | undefined> {
  if (busy || hudAlive) return undefined
  busy = true
  try {
    const s = await poll($)
    const now = await $.clock.now()
    await update($, stat, () => s)
    await update($, at, () => now)
    return s
  } finally {
    busy = false
  }
}

async function refreshLog($: EngineInterface): Promise<void> {
  let lines: ErrEntry[] = []
  try {
    lines = errEntries(await $.fs.read(logFile))
  } catch {
    // 還沒有 log 檔：顯示空的
  }
  const old = await read($, acts)
  if (JSON.stringify(old) === JSON.stringify(lines)) return   // 沒變就不重畫
  await update($, acts, () => lines)
}

function clock(ms: number): string {
  const d = new Date(ms)
  const p = (n: number) => String(n).padStart(2, '0')
  return `${p(d.getHours())}:${p(d.getMinutes())}:${p(d.getSeconds())}`
}

// ── 與引擎接起來 ──
// 每個視窗一份：監督（自己 spawn 的 watch）+ 遇敵最後已知值 + 偵測不到的次數。ctls[0] 永遠是主視窗（sup = ctls[0].sup，舊程式照用）
type Ctl = { name: string; sup: Supervisor; lastEnc?: boolean; misses: number }
let ctls: Ctl[] = []
let sup: Supervisor | undefined
let projCwd = ''
let argvPrefix: string[] | undefined     // [python] 或 ['uv','run','--no-project','python']
let pyPath: string | undefined           // uv python find 找到的直譯器（沒有 = uv run 退路）
let watchScript = ''
let tickBusy = false
export const winCount = () => Math.max(1, ctls.length)

// 取得直譯器：uv python find；失敗退回 uv run（推測 uv 會轉發 SIGTERM，待驗）
async function pyArgv($: EngineInterface, file: string, extra: string[] = []): Promise<string[]> {
  if (!argvPrefix) {
    let py: string | undefined
    try {
      const r = await $.process.run(['uv', 'python', 'find'], { timeoutMs: 15000 })
      const l = r.stdout.trim().split(/\r?\n/).pop()?.trim()
      if (r.exitCode === 0 && l) py = l
    } catch {
      // 找不到 uv python：走退路
    }
    pyPath = py
    watchScript = watchPathFromCwd(projCwd, py) ?? ''
    argvPrefix = py ? [py] : ['uv', 'run', '--no-project', 'python']
  }
  return [...argvPrefix, file === 'watch.py' ? watchScript : (watchPathFromCwd(projCwd, pyPath, file) ?? ''), ...extra]
}
const watchArgv = ($: EngineInterface, extra: string[] = []) => pyArgv($, 'watch.py', extra)

// 主視窗：env 與改版前逐字相同（不帶 PSA_CLIENT）；其他視窗加 PSA_CLIENT（WSL + Windows 直譯器另列 WSLENV）
const runEnv = (client: string, base: Record<string, string> = {}) => clientEnv(client, base, pyPath, projCwd)

function makeSup($: EngineInterface, client: string = MAIN_CLIENT): Supervisor {
  const main = isMainClient(client)
  return new Supervisor({
    spawn: async () => {
      const argv = await watchArgv($)
      return $.process.spawn({
        argv,
        cwd: rootFromCwd(projCwd),
        env: runEnv(client, { PSA_WATCH_OWNER: 'hud', PYTHONIOENCODING: 'utf-8' }),
      }) as unknown as Streamer
    },
    now: () => $.clock.now(),
    sleep: ms => $.clock.sleep(ms),
    rnd: () => Math.random(),
    stopCli: async () => {
      const argv = await watchArgv($, ['--stop'])
      if (main) await $.process.run(argv, { timeoutMs: 15000 })
      else await $.process.run(argv, { timeoutMs: 15000, env: runEnv(client) })
    },
    saveCfg: async on => {
      const f = hudCfgFromCwd(projCwd, client)
      if (!f) return
      let cfg: Record<string, unknown> = {}
      try {
        const d = JSON.parse(await $.fs.read(f)) as unknown
        if (d && typeof d === 'object') cfg = d as Record<string, unknown>
      } catch {
        // 沒有設定檔：新建
      }
      cfg.watch = on
      await $.fs.write(f, JSON.stringify(cfg))
    },
  })
}

// psa-hud.json 的 watch 欄位是 on / off 唯一依據；沒檔 / 壞檔 = on（每個視窗各一份，在自己的狀態資料夾）
async function cfgWatchOn($: EngineInterface, client: string = MAIN_CLIENT): Promise<boolean> {
  const f = hudCfgFromCwd(projCwd, client)
  if (!f) return true
  try {
    const d = JSON.parse(await $.fs.read(f)) as { watch?: unknown }
    return d.watch !== false
  } catch {
    return true
  }
}

async function addClient($: EngineInterface, name: string): Promise<Ctl> {
  const c: Ctl = { name, sup: makeSup($, name), misses: 0 }
  ctls.push(c)
  if (await cfgWatchOn($, name)) c.sup.start()
  else c.sup.status = 'off'
  return c
}

// ── 視窗偵測（第 3d 步）──
// 取捨：不在每次 render / 每秒 tick 跑 powershell。每 DETECT_PERIOD_MS 在背景跑一次 `clients.py running --rostered`
// （同 clients.running() 的程序清單查詢，只讀；ROSTERS 有登錄的才算），結果存在模組變數，繪製只讀 atom。
// 不用「state.json 新鮮」判斷：非主視窗的 state.json 要等我們 spawn watch 之後才會有（雞生蛋）。
// 查詢失敗 = 維持現狀；偵測不到連續 MISS_LIMIT 次才收掉那個視窗的 watch。主視窗永遠顯示（沒開遊戲時照舊顯示「遊戲未執行」）
const DETECT_PERIOD_MS = 30000
let detectBusy = false
async function detectClients($: EngineInterface): Promise<void> {
  if (detectBusy || !projCwd) return
  detectBusy = true
  try {
    let want: string[] | undefined
    try {
      const r = await $.process.run(await pyArgv($, 'clients.py', ['running', '--rostered']), { timeoutMs: 20000, env: { PYTHONIOENCODING: 'utf-8' } })
      want = parseRunning(r.exitCode ?? 1, r.stdout ?? '')
    } catch {
      want = undefined
    }
    if (!want) return
    const d = diffClients(ctls, want)
    for (const n of d.drop) ctls.find(x => x.name === n)?.sup.dispose()
    ctls = ctls.filter(c => !d.drop.includes(c.name))
    for (const c of ctls) c.misses = d.misses[c.name] ?? 0
    for (const n of d.add) await addClient($, n)
    if (d.add.length || d.drop.length) { void tickState($); void tickProg($) }
  } catch {
    // 偵測失敗：維持現狀，下一輪再試
  } finally {
    detectBusy = false
  }
}

// 每視窗驗證停手旗標（verifyhalt.py；2026-10-15 起各自視窗停手）：主視窗 tools/.cache/verify-halt.json、其他 tools/.cache/clients/<程序名>/verify-halt.json。
// 舊格式：改版前全部視窗共用主視窗那一份，非主視窗寫的內含 client 欄 → 歸屬那個視窗（與 verifyhalt.legacy_owner / psawin Get-PsaVerifyHalt 同規則）
type HaltDoc = { ts?: number; client?: string; src?: string; reason?: string }
export type Halt = { text: string; legacy: boolean }
const parseHalt = (s: string): HaltDoc | null => {
  try { const x = JSON.parse(s) as unknown; return x && typeof x === 'object' ? (x as HaltDoc) : null } catch { return null }
}
// 主視窗路徑上那份旗標屬於誰：client 欄是別的視窗 → 那個視窗（舊共用格式）；壞檔 / 沒欄位 / 主視窗 → PrimalSA；沒檔 → undefined
export function haltOwner(mainText: string | undefined): string | undefined {
  if (mainText === undefined) return undefined
  const c = parseHalt(mainText)?.client
  const n = typeof c === 'string' ? c.trim().replace(/\.exe$/i, '') : ''
  return n && !isMainClient(n) ? n : MAIN_CLIENT
}
// 某個視窗的旗標：own = 它自己路徑上的內容（主視窗 = mainText），mainText = 主視窗路徑上的內容（判斷舊共用旗標）
export function haltFor(client: string, own: string | undefined, mainText: string | undefined): Halt | undefined {
  const owner = haltOwner(mainText)
  if (isMainClient(client)) return owner && isMainClient(owner) ? { text: mainText!, legacy: false } : undefined
  if (own !== undefined) return { text: own, legacy: false }
  return owner && owner.toLowerCase() === client.toLowerCase() ? { text: mainText!, legacy: true } : undefined
}
// 一個視窗的停手紅字（純函式）：旗標兩行（清除指令帶程序名）+ 多視窗時 verify_suspect 一行（單視窗的 verify_suspect 已在狀態提示行，不重複）
export function haltLines(client: string, h: Halt | undefined, state: WState | null = null, multi = false): Banner[] {
  const out: Banner[] = []
  if (h) {
    const d = parseHalt(h.text) ?? {}                 // 壞檔也當旗標存在
    const when = typeof d.ts === 'number' ? ` ${stamp(d.ts * 1000)}` : ''
    out.push({ text: `${multi ? '' : `${client} `}停手：驗證旗標${when} ${d.src ?? ''}：${d.reason ?? ''}${h.legacy ? '（舊共用旗標檔）' : ''}`.replace(/\s+/g, ' ').trim(), tone: 'red' })
    out.push({ text: `人處理完驗證視窗後：uv run --no-project python tools/gui/verifyhalt.py clear ${client}`, tone: 'red' })
  }
  if (multi && state?.flags?.verify_suspect) out.push({ text: '疑似答題 / 驗證視窗，請人工處理（只停這個視窗）', tone: 'red' })
  return out
}
// pane 最上面的警示（純函式）：單視窗 = 主視窗的停手紅字；多視窗的紅字放在各視窗段落（WinView.al），這裡只剩
// 「舊共用旗標屬於沒顯示的視窗」的黃字提示（主視窗不受影響，提示怎麼清）
export function bannerLines(mainText: string | undefined, wins: { client: string; state: WState | null }[]): Banner[] {
  const out: Banner[] = wins.length > 1 ? [] : haltLines(MAIN_CLIENT, haltFor(MAIN_CLIENT, mainText, mainText))
  const owner = haltOwner(mainText)
  if (owner && !isMainClient(owner) && !wins.some(w => w.client.toLowerCase() === owner.toLowerCase())) {
    out.push({ text: `舊共用驗證旗標屬 ${owner}（主視窗不受影響）；清：uv run --no-project python tools/gui/verifyhalt.py clear ${owner}`, tone: 'yellow' })
  }
  return out
}

// 每秒：每個視窗讀 state.json → 餵給各自的監督（存活 / 卡住）→ 顯示文字變了才更新 atom。
// 主視窗照舊更新 line / hud / enc（單視窗 pane 只看這三個）；多視窗另組 wins（每視窗一份）
async function tickState($: EngineInterface): Promise<void> {
  if (tickBusy || !sup) return
  tickBusy = true
  try {
    const views: WinView[] = []
    const seen: { client: string; state: WState | null }[] = []
    const readText = async (p: string) => { try { const x = await $.fs.read(p); return typeof x === 'string' ? x : undefined } catch { return undefined } }
    const mainHalt = await readText(verifyHaltFromCwd(projCwd) ?? 'tools/.cache/verify-halt.json')
    const multi = ctls.length > 1
    for (const c of [...ctls]) {
      let text: string | undefined
      let hasFile = true
      try {
        text = await $.fs.read(stateFileFromCwd(projCwd, c.name) ?? `${cacheRel(c.name)}/state.json`)
      } catch {
        hasFile = false
      }
      const { state, badVersion } = parseState(text)
      const key = state ? `${state.watcher?.token ?? '?'}:${state.seq ?? '?'}` : null
      await c.sup.observe(key, state?.phase ?? null, state?.watcher?.interval ?? null)
      const vm = viewModel({ state, badVersion, status: c.sup.status, lastCode: c.sup.lastCode, now: await $.clock.now(), seenAt: c.sup.seenAt, hasFile })
      const now = await $.clock.now()
      const alive = watchAlive(state, now, c.sup.seenAt)
      const hp = alive ? hudParts(state, now, c.sup.seenAt) : null
      const ht = alive ? (hp ? joinParts(hp) : '（等級 / HP 讀取中…）') : null
      const bf = buffLine(alive ? state?.hud?.buffs : undefined, parseBuffTimes(await readText(buffTimeFromCwd(projCwd, c.name) ?? `${cacheRel(c.name)}/bufftime.json`)), now) ?? null
      const et = alive ? encText(state, c.lastEnc) : undefined
      if (typeof et?.val === 'boolean') c.lastEnc = et.val
      const eo = et ? { text: et.text, warn: et.warn } : null
      seen.push({ client: c.name, state })
      const own = isMainClient(c.name) ? mainHalt : await readText(verifyHaltFromCwd(projCwd, c.name) ?? `${cacheRel(c.name)}/verify-halt.json`)
      views.push({ client: c.name, wl: vm, ht, en: eo, al: multi ? haltLines(c.name, haltFor(c.name, own, mainHalt), state, true) : [], hp, bf })
      if (c.sup !== sup) continue
      const wasAlive = hudAlive
      hudAlive = alive
      if ((await read($, hudAtom)) !== ht) await update($, hudAtom, () => ht)
      if (JSON.stringify(await read($, encAtom)) !== JSON.stringify(eo)) await update($, encAtom, () => eo)
      if (wasAlive && !alive) void refresh($)       // watch 剛死：馬上用一次性 stat 補上，不等 15 s
      const old = await read($, line)
      if (JSON.stringify(old) !== JSON.stringify(vm)) await update($, line, () => vm)
    }
    const wv = views
    if (JSON.stringify(await read($, winsAtom)) !== JSON.stringify(wv)) await update($, winsAtom, () => wv)
    const bn = bannerLines(mainHalt, seen)
    if (JSON.stringify(await read($, bannerAtom)) !== JSON.stringify(bn)) await update($, bannerAtom, () => bn)
  } catch {
    // 讀檔 / 寫 atom 失敗（例：模組正在卸載）：這一輪略過，保持上一次的畫面，不留未處理的 rejection
  } finally {
    tickBusy = false
  }
}

const STATUS_TEXT: Record<SupStatus, string> = {
  idle: '準備啟動', running: '執行中', waiting: '等待重開', ro3: '已有 watch 在跑（只讀）', ro6: '另一平台的 watch 在跑（只讀）',
  failed: '啟動失敗', stopped: '已被要求停止', off: '已關閉',
}
const supSummary = (s: Supervisor) => `監看：${STATUS_TEXT[s.status]}｜spawn ${s.spawns} 次｜卡住重開 ${s.stalls} 次｜最後退出碼 ${s.lastCode ?? '無'}`

// ───────────────────────── 自動 session 標題（PSA｜…）─────────────────────────
// 讀 notes/quest-events.log 最後一筆 [questrun] 行組短標題（練功中則改「PSA｜練功中 地點」，見 grindActivity），由 classic.UserPromptSubmit / SessionStart 的 sessionTitle 設定。
// 只覆蓋空標題或「PSA｜」開頭（本 mod 自己設的）；使用者 /rename 的名字不動。讀不到 / 沒紀錄就不輸出
export const TITLE_PREFIX = 'PSA｜'
const TITLE_MAX = 40
const CAVE_IDS = new Set([2000, 2001, 2002, 2003])    // 四大洞窟（questdefs.QCAVE）
const LOG_TAIL_LINES = 400

export const mayRetitle = (cur: string | undefined) => !cur || cur.startsWith(TITLE_PREFIX)
const cleanName = (n: string) => n.replace(/\(1\.82\)\s*$/, '').trim()

// questdefs.py → {id: detail}（只解析 id=…, detail='…'，不執行 Python）
export function questNames(py: string): Map<number, string> {
  const m = new Map<number, string>()
  for (const x of py.matchAll(/id=(\d+),\s*detail='([^']+)'/g)) m.set(Number(x[1]), cleanName(x[2]!))
  return m
}

// 任務驅動器的事件行標籤：questrun（questrun.py）/ rebirth（rebirth.py 轉生任務）；取檔案中最後一筆
const TASK_TAG = /\[(?:questrun|rebirth)\]/

// [rebirth] 最後一筆：任務名取「階段 X 開始（名稱）」或本 run 開始行「轉到第 N 轉（名稱）」；階段取最後一個「階段 X 開始」
// 結束 rc=0 → 已完成；rc≠0 後還有別的事件行 → 接手中（rebirth rc=N），否則失敗 rc=N；其餘進行中（附階段）
function rebirthTitle(lines: string[], last: number): string | undefined {
  let start = -1
  for (let i = last; i >= 0; i--) if (/\[rebirth\].*開始：轉到第/.test(lines[i]!)) { start = i; break }
  let name: string | undefined
  let stage: string | undefined
  for (let i = last; i >= Math.max(start, 0); i--) {
    const m = /\[rebirth\]\s*階段 (\S+) 開始(?:（([^）]+)）)?/.exec(lines[i]!)
    if (m) { stage ??= m[1]; name ??= m[2] }
    if (stage && name) break
  }
  if (!name && start >= 0) name = /轉到第 \d+ 轉（([^）]+)）/.exec(lines[start]!)?.[1]
  if (!name) return undefined
  const line = lines[last]!
  let state = stage ? `${stage} 進行中` : '進行中'
  const end = /\]\s*結束 rc=(\d+)/.exec(line)
  if (end) {
    const later = lines.slice(last + 1).some(l => l.trim() !== '')
    state = end[1] === '0' ? '已完成' : later ? `接手中（rebirth rc=${end[1]}）` : `失敗 rc=${end[1]}`
  }
  const t = `${TITLE_PREFIX}${name} ${state}`
  return t.length > TITLE_MAX ? t.slice(0, TITLE_MAX) : t
}

// 找最後一筆 [questrun] / [rebirth] 行：結束 → 完成 / 失敗（rc≠0 後還有別的事件行 → 接手中），其他 → 進行中；
// 任務名只在本 run（最後一個「開始：任務」行起）內取最後一個「任務 N「名」」，沒有就用開始行第一個 ID 查 questdefs。沒有 questrun 紀錄回 undefined
export function titleFromLog(log: string, names: Map<number, string> = new Map()): string | undefined {
  const lines = log.split(/\r?\n/).slice(-LOG_TAIL_LINES)
  let last = -1
  for (let i = lines.length - 1; i >= 0; i--) if (TASK_TAG.test(lines[i]!)) { last = i; break }
  if (last < 0) return undefined
  const line = lines[last]!
  if (line.includes('[rebirth]')) return rebirthTitle(lines, last)
  // 本次 run 邊界 = 最後一個「開始：任務」行（含）；名字只在邊界之後找，不抓到前一次 run
  let start = -1
  for (let i = last; i >= 0; i--) if (/\[questrun\].*開始：任務/.test(lines[i]!)) { start = i; break }
  let id: number | undefined
  let name: string | undefined
  for (let i = last; i >= Math.max(start, 0) && !name; i--) {
    const m = /\[questrun\].*?任務 (\d+)「([^」]+)」/.exec(lines[i]!)
    if (m) { id = Number(m[1]); name = cleanName(m[2]!) }
  }
  if (!name) {
    const m = /任務 \[?(\d+)/.exec(line) ?? (start >= 0 ? /任務 \[?(\d+)/.exec(lines[start]!) : null)
    if (m) { id = Number(m[1]); name = names.get(id) }
  }
  if (!name) return undefined
  if (id !== undefined && CAVE_IDS.has(id)) name = `四大洞窟：${name}`
  let state = '進行中'
  const end = /結束 rc=(\d+)/.exec(line)
  if (end) {
    // rc≠0 之後還有別的事件行（手動…）→ 任務仍在處理，不是停了
    const later = lines.slice(last + 1).some(l => l.trim() !== '')
    state = end[1] === '0' ? '已完成' : later ? `接手中（questrun rc=${end[1]}）` : `失敗 rc=${end[1]}`
  }
  else if (/已完成（/.test(line)) state = '已完成'
  const t = `${TITLE_PREFIX}${name} ${state}`
  return t.length > TITLE_MAX ? t.slice(0, TITLE_MAX) : t
}

// ───────────────────────── 練功中判斷 ─────────────────────────
// 規則：最後一筆 [questrun] 行之後，actions.log 最新的「原地遇敵：開 / 關」是「開」，
// 且 watch 沒說遇敵是關的（screen.enc_on === false 不算）、地圖沒離開最近抵達的練功點。
// state 太舊（> STATE_FRESH_S）當沒有；沒有 state 時只信遇敵「開」在 GRIND_MAX_S 內（離線上限 2 小時）。
// 之後只要有更新的 questrun 行（新任務開始）就回到任務顯示。純函式，時間比較用「距今秒數」所以跨午夜也對
// 地點（2026-10-15 修：p2 進 31706 地圖名折兩行，watch 讀不到座標、map 停在傳送前 → 顯示「練功中 海主人隧道」）：
//   最近抵達的練功點取三個來源中最新的：actions.log「grind 傳送到 X id:」、follow.json（spot + last_switch，follow 以地圖 ID / 地圖名確認抵達）、
//   grind.json（mode=start 且 rc=0 的 spot + ts）；再跟 state.hud.map 比：map 是新的（不 stale）且比抵達紀錄新 → 以 map 為準（是練功點就顯示該點、
//   不是就當已離開）；map stale（watch 標記，或比 hud 其他欄舊 > MAP_STALE_S）→ 不信 map，只用抵達紀錄；都沒有時舊地名加「?」
const ACT_TAIL_LINES = 600
const STATE_FRESH_S = 60
const GRIND_MAX_S = 7200
export const MAP_STALE_S = 30           // 與 watch.py MAP_STALE_S 相同
export type Grind = { spot: string; quick: boolean }

// tools/gui/spots.py 的 SPOTS 表 → 練功點名 → 抵達地圖 ID（只認 5 欄的那張表；HEAL_SPOTS_1920 只有 3 欄不會比到）
export function spotIds(py: string): Map<string, number> {
  const m = new Map<string, number>()
  for (const x of py.matchAll(/'([^']+)':\s*\(\s*\d+,\s*\d+,\s*(\d+),\s*\d+,\s*'/g)) m.set(x[1]!, Number(x[2]))
  return m
}

// state.hud.map 是不是舊值：watch 標了 stale，或比 hud 最近一次成功讀值（hud.ts）舊超過 MAP_STALE_S（舊版 watch 沒有 stale 欄位時的備援）
export function mapStale(h?: WHud | null): boolean {
  const m = h?.map
  if (!m) return false
  if (m.stale === true) return true
  return typeof m.ts === 'number' && typeof h?.ts === 'number' && h.ts - m.ts > MAP_STALE_S
}

type Arrive = { spot: string; id?: number; age: number }
// 最近抵達的練功點（三個來源取最新；age = 距今秒數）。follow.json / grind.json 讀不到或壞檔 → 略過
function lastArrive(acts: string[], i: ProgIn, ids: Map<string, number>): Arrive | undefined {
  const c: Arrive[] = []
  const nowS = i.now / 1000
  for (let k = acts.length - 1; k >= 0; k--) {
    const m = /grind 傳送到 (\S+) (\d+):/.exec(acts[k]!)
    if (m) { const a = actionAgeS(acts[k]!, i.now); if (a !== undefined) c.push({ spot: m[1]!, id: Number(m[2]), age: a }); break }
  }
  const js = (t?: string): Record<string, unknown> | undefined => { if (!t) return undefined; try { const o = JSON.parse(t); return o && typeof o === 'object' ? o : undefined } catch { return undefined } }
  const f = js(i.follow)
  if (f && typeof f.spot === 'string' && f.spot && typeof f.last_switch === 'number' && !f.dry_run) c.push({ spot: f.spot, id: ids.get(f.spot), age: nowS - f.last_switch })
  const g = js(i.grind)
  if (g && g.mode === 'start' && g.rc === 0 && typeof g.spot === 'string' && g.spot && typeof g.ts === 'number') c.push({ spot: g.spot, id: ids.get(g.spot), age: nowS - g.ts })
  return c.length ? c.reduce((a, b) => (b.age < a.age ? b : a)) : undefined
}

// quest-events.log 行首「YYYY-MM-DD HH:MM:SS」→ 距今秒數
function questLineAgeS(l: string, now: number): number | undefined {
  const m = /^(\d{4})-(\d\d)-(\d\d) (\d\d):(\d\d):(\d\d)/.exec(l)
  if (!m) return undefined
  return Math.round((now - new Date(+m[1]!, +m[2]! - 1, +m[3]!, +m[4]!, +m[5]!, +m[6]!).getTime()) / 1000)
}

export function grindActivity(i: ProgIn): Grind | undefined {
  if (!i.actions) return undefined
  const acts = i.actions.split(/\r?\n/).filter(l => l.trim()).slice(-ACT_TAIL_LINES)
  const age = (l: string) => actionAgeS(l, i.now)
  let enc: string | undefined
  for (let k = acts.length - 1; k >= 0; k--) if (/原地遇敵：[開關]/.test(acts[k]!)) { enc = acts[k]; break }
  if (!enc || !/原地遇敵：開/.test(enc)) return undefined
  const encAge = age(enc)
  if (encAge === undefined || encAge > GRIND_MAX_S) return undefined
  // 最後一筆 questrun 行比遇敵開還新 → 還在任務中
  if (i.quest) {
    const q = i.quest.split(/\r?\n/).slice(-LOG_TAIL_LINES).filter(l => TASK_TAG.test(l))
    const qa = q.length ? questLineAgeS(q[q.length - 1]!, i.now) : undefined
    if (qa !== undefined && qa <= encAge) return undefined
  }
  const st = i.state
  const fresh = !!st && typeof st.ts === 'number' && (i.now / 1000 - st.ts) <= STATE_FRESH_S
  if (fresh && st!.screen?.enc_on === false) return undefined
  const ids = i.spots ?? new Map<string, number>()
  const arr = lastArrive(acts, i, ids)
  const mp = fresh ? st!.hud?.map : undefined
  const stale = mapStale(st?.hud)
  let spot: string | undefined
  if (mp && !stale && mp.id !== undefined) {
    const mapAge = typeof mp.ts === 'number' ? i.now / 1000 - mp.ts : 0       // 沒有 ts（舊格式）當成剛讀到
    if (arr && arr.age < mapAge) spot = arr.spot                              // 抵達紀錄比地圖讀值新（剛傳送完）
    else if (arr && arr.id === mp.id) spot = arr.spot
    else {
      const here = [...ids].find(([, v]) => v === mp.id)?.[0]
      if (here) spot = here
      else if (arr && arr.id !== undefined) return undefined                  // 已離開練功點
      else spot = arr?.spot ?? (mp.v || undefined)
    }
  } else if (arr) spot = arr.spot                                             // map 舊值 / 沒有：只信抵達紀錄
  else if (mp?.v) spot = stale ? `${mp.v}?` : mp.v
  if (!spot) spot = '原地'
  // 快速戰鬥：各角色最後一筆「ass：X 快速戰鬥 → 開/關」（掃整份 actions.log，開快戰常在很久以前），至少一人且全部為開才標
  const quickBy = new Map<string, boolean>()
  for (const l of i.actions.split(/\r?\n/)) { const m = /ass：(\S+) 快速戰鬥 → ([開關])/.exec(l); if (m) quickBy.set(m[1]!, m[2] === '開') }
  const quick = quickBy.size > 0 && [...quickBy.values()].every(Boolean)
  return { spot, quick }
}

export function grindTitle(g: Grind): string {
  return `${TITLE_PREFIX}練功中 ${g.spot}`
}

// ───────────────────────── 即時進度區（任務 / 最近事件 / 最後動作 / 警報）─────────────────────────
// 純函式：假檔內容 → 最多 6 行 {text, tone}；任一來源讀不到（undefined）該行顯示「—」
const PROG_PERIOD_MS = 3000
const PROG_W = 56            // 每行最多字數（超過加 …）
const IDLE_S = 120           // 最後動作超過這麼久沒動 → 標「閒置 N 分」
// follow / grind：該視窗的 follow.json / grind.json 原文（練功點抵達紀錄）；spots：spotIds(tools/gui/spots.py)
export type ProgIn = { quest?: string; actions?: string; state?: WState | null; now: number; follow?: string; grind?: string; spots?: Map<string, number> }
const cut = (t: string) => (t.length > PROG_W ? `${t.slice(0, PROG_W - 1)}…` : t)

// 事件行去掉日期、截圖路徑、[questrun] / [rebirth] 標籤
export function cleanEvent(l: string): string {
  return l.replace(/^\d{4}-\d\d-\d\d\s+/, '').replace(/\s*\S*[\\/]\S*\.(?:png|jpe?g|bmp)\b/gi, '').replace(/\[(?:questrun|rebirth)\]\s*/, '').trim()
}

// actions.log 一行是「HH:MM:SS 描述」（沒有日期）；以今天的 HH:MM:SS 算距今秒數（跨午夜 +86400）
export function actionAgeS(hms: string, now: number): number | undefined {
  const m = /^(\d\d):(\d\d):(\d\d)/.exec(hms)
  if (!m) return undefined
  const d = new Date(now)
  const cur = d.getHours() * 3600 + d.getMinutes() * 60 + d.getSeconds()
  const then = Number(m[1]) * 3600 + Number(m[2]) * 60 + Number(m[3])
  return (cur - then + 86400) % 86400
}

// events：最近事件行數（單視窗 3；多視窗每視窗 1，pane 才不會太長）
export function progressLines(i: ProgIn, names: Map<number, string> = new Map(), events = 3): ProgLine[] {
  const out: ProgLine[] = []
  const g = grindActivity(i)
  const t = i.quest === undefined ? undefined : titleFromLog(i.quest, names)
  // 智慧果 / 龍王改在 buff 行（含剩餘時間），這裡不再重複
  out.push({ text: g ? `練功中：${g.spot}${g.quick ? '（快速戰鬥）' : ''}` : `任務：${t ? t.slice(TITLE_PREFIX.length) : '—'}`, tone: 'plain' })
  const ev = i.quest === undefined ? [] : i.quest.split(/\r?\n/).filter(l => l.trim()).slice(-events).map(cleanEvent)
  if (ev.length === 0) out.push({ text: '事件：—', tone: 'gray' })
  for (const e of ev) out.push({ text: cut(` ${e}`), tone: 'gray' })
  const al = i.actions?.split(/\r?\n/).filter(l => l.trim()).pop()
  if (!al) out.push({ text: '動作：—', tone: 'gray' })
  else {
    const age = actionAgeS(al, i.now)
    const idle = age !== undefined && age > IDLE_S
    const tag = age === undefined ? '' : idle ? `（閒置 ${Math.floor(age / 60)} 分）` : `（${age} 秒前）`
    out.push({ text: cut(`動作 ${al.replace(/\s+/g, ' ').trim()}`.slice(0, PROG_W - tag.length) + tag), tone: idle ? 'yellow' : 'plain' })
  }
  // 警報（verify_suspect / alerts）只在各視窗段落頂端的紅字顯示一次（viewModel 的紅色提示），這裡不重複
  return out.slice(0, 6)
}

// 兩個 hook 共用：回新標題或 undefined（不該改 / 讀檔失敗 / 沒紀錄 / 與現在相同）。
// 一律看主視窗（notes/quest-events.log、actions.log 沒標籤的行、tools/.cache/state.json）；多視窗（nWin > 1）結尾加「（N 視窗）」
export const winSuffix = (n: number) => (n > 1 ? `（${n} 視窗）` : '')
export async function autoTitle($: EngineInterface, cwd: string, cur: string | undefined, nWin: number = winCount()): Promise<string | undefined> {
  try {
    const root = rootFromCwd(cwd)
    if (!root || !mayRetitle(cur)) return undefined
    const log = await $.fs.read(`${root}/notes/quest-events.log`)
    if (typeof log !== 'string') return undefined
    let names = new Map<number, string>()
    try {
      const py = await $.fs.read(`${root}/tools/gui/questdefs.py`)
      if (typeof py === 'string') names = questNames(py)
    } catch { /* 沒有 questdefs 就只靠 log 內的名字 */ }
    const rd = async (f: string) => { try { const x = await $.fs.read(`${root}/${f}`); return typeof x === 'string' ? x : undefined } catch { return undefined } }
    const [actions, stText, follow, grind, spy] = await Promise.all([rd('tools/.cache/actions.log'), rd('tools/.cache/state.json'),
      rd('tools/.cache/follow.json'), rd('tools/.cache/grind.json'), rd('tools/gui/spots.py')])
    const g = grindActivity({ quest: log, actions: actionsFor(actions, MAIN_CLIENT), state: parseState(stText).state, now: await $.clock.now(), follow, grind, spots: spy ? spotIds(spy) : undefined })
    const t0 = g ? grindTitle(g) : titleFromLog(log, names)
    const t = t0 ? t0 + winSuffix(nWin) : undefined
    return t && t !== cur ? t : undefined
  } catch {
    return undefined
  }
}

// 每 3 秒：讀三個檔 → progressLines → 有變才更新 atom（任何錯誤都吞掉）。
// 多視窗：每個視窗讀自己的 quest-events.log / state.json，actions.log 共用一份、依標籤分視窗 → progs（每視窗事件 1 行）
let progBusy = false
let questNameCache: Map<number, string> | undefined
let spotIdCache: Map<string, number> | undefined
async function tickProg($: EngineInterface): Promise<void> {
  if (progBusy || !projCwd) return
  progBusy = true
  try {
    const root = rootFromCwd(projCwd)
    if (!root) return
    const rd = async (f: string) => { try { const x = await $.fs.read(`${root}/${f}`); return typeof x === 'string' ? x : undefined } catch { return undefined } }
    const [quest, actions, stText, follow, grind] = await Promise.all([rd('notes/quest-events.log'), rd('tools/.cache/actions.log'), rd('tools/.cache/state.json'),
      rd('tools/.cache/follow.json'), rd('tools/.cache/grind.json')])
    if (!questNameCache) { const py = await rd('tools/gui/questdefs.py'); if (py) questNameCache = questNames(py) }
    if (!spotIdCache) { const py = await rd('tools/gui/spots.py'); if (py) spotIdCache = spotIds(py) }
    const now = await $.clock.now()
    const spots = spotIdCache
    const main: ProgIn = { quest, actions: actionsFor(actions, MAIN_CLIENT), state: parseState(stText).state, now, follow, grind, spots }
    const lines = progressLines(main, questNameCache)
    if (JSON.stringify(await read($, prog)) !== JSON.stringify(lines)) await update($, prog, () => lines)
    const ps: WinProg[] = []
    {
      // 每視窗一份（單視窗也是；事件：單視窗 2 行、多視窗 1 行）
      const nEv = ctls.length > 1 ? 1 : 2
      for (const c of [...ctls]) {
        if (isMainClient(c.name)) { ps.push({ client: c.name, lines: progressLines(main, questNameCache, nEv) }); continue }
        const cr = cacheRel(c.name)
        const [q, st, fo, gr] = await Promise.all([rd(`${notesRel(c.name)}/quest-events.log`), rd(`${cr}/state.json`), rd(`${cr}/follow.json`), rd(`${cr}/grind.json`)])
        ps.push({ client: c.name, lines: progressLines({ quest: q, actions: actionsFor(actions, c.name), state: parseState(st).state, now, follow: fo, grind: gr, spots }, questNameCache, nEv) })
      }
    }
    if (JSON.stringify(await read($, progsAtom)) !== JSON.stringify(ps)) await update($, progsAtom, () => ps)
  } catch {
    // 讀檔失敗：保持上一次的畫面
  } finally {
    progBusy = false
  }
}

const PSA_HUD_DESC = '打開精靈王石器資訊 pane 並立即更新；/psa-hud off 關 pane；/psa-hud watch on|off [程序名|all] 開關即時監看；/psa-hud ack [程序名|all] 清掉驗證警報'

// 初始化（session.start 呼叫；熱重載後 session.start 沒重發時由 command.run 補呼叫）：
// 設路徑、開 pane（openPane）、起計時器、建監督並視設定啟動 watch。同一份模組只做一次（inited）
let inited = false
async function init($: EngineInterface, cwd: string, o: { openPane: boolean }): Promise<void> {
  if (inited) return
  inited = true
  statPs1 = statPathFromCwd(cwd) ?? statPs1
  logFile = logPathFromCwd(cwd) ?? logFile
  projCwd = cwd
  // 舊版（0.1）放在狀態列，改用 pane 後清掉
  $.ui.status(undefined)
  if (o.openPane) void $.ui.open({ id: PANE, title: '精靈王石器' })
  void refresh($)
  $.clock.every(PERIOD_MS, () => void refresh($))
  void refreshLog($)
  $.clock.every(LOG_PERIOD_MS, () => void refreshLog($))
  // 即時狀態監看：設定 off 就不啟動；否則 spawn 自己的 watch 並開始每秒讀 state.json
  // （熱重載時舊模組 spawn 的 watch 可能還在收尾：新的會拿到退出碼 3，grace 等 3 s 重試一次，見 decideExit）
  ctls = []
  sup = (await addClient($, MAIN_CLIENT)).sup
  void tickState($)
  $.clock.every(STATE_PERIOD_MS, () => void tickState($))
  void tickProg($)
  $.clock.every(PROG_PERIOD_MS, () => void tickProg($))
  // 多視窗：背景偵測其他視窗（30 s 一次；見 detectClients 的取捨說明）
  void detectClients($)
  $.clock.every(DETECT_PERIOD_MS, () => void detectClients($))
}

// ───────────────────────── pane 排版 ─────────────────────────
// 2026-10-15 使用者：「有點亂、智慧果時間沒有、有些行字太長看不到」→ 改成每視窗一段、重點在前、依顯示寬度折行：
//   [視窗] 畫面狀態 ｜ N 秒前                （粗體；單視窗不加 [視窗]）
//     ！停手 / 驗證 / 斷線 / 警報              （紅字粗體，緊接標題）
//     DKBO  4轉126級  HP 51  MP 100（面板前 · 23s 前）
//     寵 0轉105級 HP 1008
//     老爺爺的家 1013:13,16
//     遇敵中 · 智慧果 剩 1:23 · 龍王 ?（bufftime.py read）   （綠；不遇敵 / 時間未知 = 黃）
//     任務：… / 練功中：…                       （一般字）
//     最近事件、最後動作                        （灰；閒置黃）
//     監看只讀 / 提示視窗等次要提示              （灰 / 黃）
// 下面是錯誤 / 改進紀錄：同一錯誤合併成一筆（×N），待改進的黃字、已改進的下一行綠字寫改進內容；每筆最多折 2 行。
// 寬度：中日韓全形字算 2；pane 寬度取 ui.render 的 bodyColumns（拿不到用 PANE_W）
export const PANE_W = 64
const WIDE = /[ᄀ-ᅟ⺀-〾ぁ-㏿㐀-䶿一-鿿ꀀ-꓏가-힣豈-﫿︰-﹏＀-｠￠-￦]/
const charW = (c: string) => (WIDE.test(c) ? 2 : 1)
export function dispW(t: string): number {
  let n = 0
  for (const c of t) n += charW(c)
  return n
}
// 依顯示寬度折行：第一行寬 width、續行前面加 indent；最多 maxLines 行，放不下的最後一行結尾換成 …
export function wrapW(text: string, width: number, maxLines = 2, indent = '  '): string[] {
  const out: string[] = []
  let cur = '', w = 0
  const chars = [...text.replace(/\s+/g, ' ').trim()]
  for (let i = 0; i < chars.length; i++) {
    const c = chars[i]!
    const cw = charW(c)
    if (w + cw > width) {
      if (out.length + 1 >= maxLines) {
        // 最後一行：留 1 格放 …
        let t = cur
        while (dispW(t) + 1 > width && t.length) t = [...t].slice(0, -1).join('')
        out.push(`${t}…`)
        return out
      }
      // 英數字中間不切（指令 / 路徑要能整段複製）：退回這一行最後一個空白，後半段帶到下一行
      let carry = ''
      if (/[!-~]/.test(c) && /[!-~]$/.test(cur)) {
        const sp = cur.lastIndexOf(' ')
        if (sp > indent.length && cur.length - sp <= 40) { carry = cur.slice(sp + 1); cur = cur.slice(0, sp) }
      }
      out.push(cur)
      cur = indent + carry
      w = dispW(cur)
      if (c === ' ') continue
    }
    cur += c
    w += cw
  }
  if (cur.trim()) out.push(cur)
  return out
}

// ── 表格排版（2026-10-15 使用者定案：上方每視窗一張小表上下排、下方錯誤 / 改進紀錄表）──
// 一個畫表的純函式：欄寬（固定 / flex 吃剩餘）、顯示寬度（中文 2）、截短加 …、框線；上下兩種表共用。
// 每格兩側各 1 格空白；框線字元算 1 寬，所以整張表顯示寬度 = width（不會超過 pane）
export type TRow = { cells: string[]; tone: PaneLine['tone']; bold?: boolean; max?: number }
export type TCol = { w: number | 'flex' }
export type TableIn = { width: number; cols: TCol[]; rows: TRow[]; title?: string; header?: string[]; rule?: boolean }
const padW = (t: string, w: number) => t + ' '.repeat(Math.max(0, w - dispW(t)))
// 截短到顯示寬度 w（超過結尾換成 …）
export function truncW(t: string, w: number): string {
  const s = t.replace(/[\r\n\t]+/g, ' ').trim()       // 保留中間連續空白（同列兩個值的對齊用）
  if (dispW(s) <= w) return s
  let o = ''
  for (const c of s) { if (dispW(o) + charW(c) + 1 > w) break; o += c }
  return `${o}…`
}
export function tableLines(i: TableIn): PaneLine[] {
  const n = i.cols.length
  const fixed = i.cols.reduce((a, c) => a + (c.w === 'flex' ? 0 : c.w), 0)
  const flex = Math.max(4, i.width - fixed - (n + 1) - 2 * n)
  const ws = i.cols.map(c => (c.w === 'flex' ? flex : c.w))
  const line = (l: string, m: string, r: string) => `${l}${ws.map(w => '─'.repeat(w + 2)).join(m)}${r}`
  const out: PaneLine[] = []
  const gray = (text: string) => out.push({ text, tone: 'gray' })
  if (i.title) {
    const t = ` ${truncW(i.title, Math.max(1, i.width - 5))} `
    gray(`┌${t}${'─'.repeat(Math.max(0, i.width - 2 - dispW(t)))}┐`)
  } else gray(line('┌', '┬', '┐'))
  const emit = (r: TRow) => {
    const cols = r.cells.map((c, k) => { const t = String(c ?? ''); return dispW(t) <= ws[k]! ? [t] : wrapW(t, ws[k]!, k === n - 1 ? (r.max ?? 1) : 1, '') })
    const h = Math.max(1, ...cols.map(c => c.length))
    for (let y = 0; y < h; y++) {
      const body = ws.map((w, k) => padW(truncW(cols[k]?.[y] ?? '', w), w)).join(' │ ')
      out.push({ text: `│ ${body} │`, tone: r.tone, ...(r.bold ? { bold: true } : {}) })
    }
  }
  if (i.header) { emit({ cells: i.header, tone: 'plain', bold: true }); gray(line('├', '┼', '┤')) }
  i.rows.forEach((r, k) => {
    emit(r)
    if (i.rule && k < i.rows.length - 1) gray(line('├', '┼', '┤'))
  })
  gray(line('└', '┴', '┘'))
  return out
}

// 視窗代號：PrimalSA → p1、PrimalSA2 → p2、PrimalSA3 → p3（依程序名尾數；與 clients.py ROSTERS 的 p1 / p2 一致）
export const pLabel = (client: string) => `p${/(\d+)$/.exec(client)?.[1] ?? '1'}`
// 地圖名縮短（保守：只去掉「五十年前」前綴與括號註記；仍太長由表格截短）
export function shortMap(m: string): string {
  return m.replace(/^五十年前/, '').replace(/[（(][^）)]*[）)]$/, '').trim()
}
// 地圖 + 座標：去掉地圖編號（「1013:13,16」→「13,16」）；沒資料 → undefined
function mapPos(map?: string, pos?: string): string | undefined {
  const p = pos?.replace(/^\d+:/, '')
  const t = [map ? shortMap(map) : '', p ?? ''].filter(Boolean).join(' ')
  return t || undefined
}
const LEFT_W = 22     // 同列兩個值時，左邊那個值佔的顯示寬度
// 同列兩個值：左值補空白對齊到 LEFT_W；放不下（cw = 內容欄寬）就退成單一空白，讓右值盡量不被截
const pair = (a: string, b: string | undefined, cw: number) => {
  if (!b) return a
  const wide = `${dispW(a) < LEFT_W ? padW(a, LEFT_W) : `${a}  `}${b}`
  return dispW(wide) <= cw ? wide : `${a} ${b}`
}
// 事件 / 動作行裡的 HH:MM:SS 縮成 HH:MM
const hhmm = (t: string) => t.replace(/\b(\d\d:\d\d):\d\d\b/, '$1')

// 一個視窗的輸入（tickState 的 WinView + tickProg 的進度行；主視窗 watch 不在時 st = 一次性 stat）
export type SecIn = { w: WinView; prog: ProgLine[]; st?: Stat | null }
// 一個視窗 → 一張小表（純函式）。tag：多視窗時表頭加 p1 / p2 代號；extra：額外的警示列（單視窗的停手旗標 banner）
export function winTable(i: SecIn, width = PANE_W, tag = false, extra: Banner[] = []): PaneLine[] {
  const w = i.w
  const cw = Math.max(4, width - 11)          // 內容欄顯示寬度（見 tableLines：欄 4 + 框線 3 + 內距 4）
  const rows: TRow[] = []
  const add = (label: string, text: string | undefined, tone: PaneLine['tone'], max = 1, bold = false) => { if (text) rows.push({ cells: [label, text], tone, max, ...(bold ? { bold } : {}) }) }
  const hints = Array.isArray(w.wl?.hints) ? w.wl.hints : []
  // ！警示：停手旗標 / verify_suspect（al）+ 狀態提示裡的紅字；同一件事只寫一次；多件事多列
  const al = Array.isArray(w.al) ? w.al : []
  const alerts: { text: string; tone: PaneLine['tone'] }[] = [
    ...extra.map(b => ({ text: String(b.text ?? ''), tone: (b.tone === 'yellow' ? 'yellow' : 'red') as PaneLine['tone'] })),
    ...al.map(b => ({ text: String(b.text ?? ''), tone: 'red' as const })),
    ...hints.filter(x => x.tone === 'red').map(x => ({ text: String(x.text ?? ''), tone: 'red' as const })),
  ]
  const seen: string[] = []
  for (const a of alerts) {
    const key = a.text.replace(/（只停這個視窗）$/, '')
    if (seen.includes(key)) continue
    seen.push(key)
    add('！', a.text, a.tone, 3, true)          // 停手紅字含清除指令，最多折 3 行不截掉
  }
  // HUD：watch 的分段；主視窗 watch 不在時退回一次性 stat；都沒有 = 讀取中
  const hp = w.hp ?? (w.ht == null && i.st ? statParts(i.st) : null)
  const f = hp?.f
  const note = hp?.note ? ` ${hp.note}` : ''
  if (hp && f) {
    const who = [f.name, f.level].filter(Boolean).join(' ')
    add('人物', pair(who || '—', `HP ${f.hp ?? '?'} / MP ${f.mp ?? '?'}${note}`, cw), hp.err ? 'yellow' : 'plain')
    if (f.petLevel || f.petHp != null) add('寵物', pair([f.petName, f.petLevel ?? '?'].filter(Boolean).join(' '), `HP ${f.petHp ?? '?'}`, cw), 'plain')
    else add('寵物', '—', 'gray')
    add('地圖', pair(mapPos(f.map, f.pos) ?? '—', w.en?.text, cw), w.en?.warn ? 'yellow' : 'plain')
  } else if (hp) {
    add('人物', `${hp.who}${note}`, hp.err ? 'yellow' : 'plain')
    if (hp.pet) add('寵物', hp.pet.replace(/^寵 /, ''), 'plain')
    const loc = hp.loc?.replace(/\s\d+:(?=\d+,\d+)/, ' ')
    if (loc || w.en) add('地圖', pair(loc ? loc.replace(/^(\S+)(\s)/, (_m, a: string, s: string) => shortMap(a) + s) : '—', w.en?.text, cw), w.en?.warn ? 'yellow' : 'plain')
  } else {
    add('人物', w.ht ?? '讀取中…', 'gray')
    if (w.en) add('地圖', pair('—', w.en.text, cw), w.en.warn ? 'yellow' : 'plain')
  }
  add('Buff', w.bf?.text, w.bf?.warn ? 'yellow' : 'green', 2)
  // 任務 / 練功（狀態）+ 事件 + 動作；沒資料的事件 / 動作列不顯示
  const prog = Array.isArray(i.prog) ? i.prog : []
  const tone = (p: ProgLine): PaneLine['tone'] => (p.tone === 'red' ? 'red' : p.tone)
  const first = prog[0]
  if (first) add('狀態', String(first.text ?? '').trim().replace(/^任務：—$/, '—') || '—', tone(first), 2)
  else add('狀態', '—', 'gray')
  let evN = 0
  for (const p of prog.slice(1)) {
    const t = String(p.text ?? '').trim()
    if (!t || /^(事件|動作)：—$/.test(t)) continue
    if (t.startsWith('動作')) add('動作', hhmm(t.replace(/^動作\s*/, '')), tone(p))
    else { add(evN++ === 0 ? '事件' : '', hhmm(t.replace(/^事件：?\s*/, '')), tone(p)); }
  }
  // 次要提示（監看只讀 / 重開中 / 提示視窗）：表格下方一行灰字（有黃字提示就整行黃）
  const sec = hints.filter(x => x.tone !== 'red')
  const out = tableLines({
    width, cols: [{ w: 4 }, { w: 'flex' }], rows,
    title: `${tag ? `${pLabel(w.client)} ` : ''}${w.client}${w.wl?.main ? ` · ${w.wl.main}` : ''}`,
  })
  if (sec.length) out.push({ text: truncW(`${sec.map(x => String(x.text ?? '')).join(' · ')}`, width), tone: sec.some(x => x.tone === 'yellow') ? 'yellow' : 'gray' })
  return out
}

// 錯誤紀錄合併：同一視窗 + 來源 + 錯誤文字 + 改進 → 一筆（保留最新那筆，n = 次數），順序照最新在前
export function errGroups(lines: ErrEntry[]): { e: ErrEntry; n: number }[] {
  const out: { e: ErrEntry; n: number; k: string }[] = []
  for (const e of lines) {
    const k = `${e.client ?? ''}|${e.source ?? ''}|${e.error}|${e.fix ?? ''}`
    const hit = out.find(x => x.k === k)
    if (hit) hit.n++
    else out.push({ e, n: 1, k })
  }
  return out.map(({ e, n }) => ({ e, n }))
}

// pane 內容（純函式，測試直接呼叫）。注意：tsconfig 的 jsxFactory 是 h，
// 這裡的箭頭函式參數不可以叫 h（會蓋掉 JSX 工廠 → 每個 <Text> 都變成「h is not a function」→ 整個 pane 空白）
export type PaneData = {
  wl?: WatchLine | null; st?: Stat | null; ht?: string | null; en?: { text: string; warn: boolean } | null
  pg?: ProgLine[] | null; lines?: ErrEntry[] | null
  // 每視窗一張表（wins / progs 依 client 對上；單視窗也走同一條路，表頭不加 p1）；還沒讀過（空）時退回 wl / st / ht / en / pg。
  // banner（單視窗的 verify-halt.json、舊共用旗標提示）併入第一張表的「！」列
  wins?: WinView[] | null; progs?: WinProg[] | null; banner?: Banner[] | null
  width?: number; now?: number             // pane 寬度（bodyColumns）、現在時間（錯誤紀錄當天只顯示時:分）
}
export const LOG_SHOW = 6     // 下方錯誤 / 改進紀錄表最多顯示幾筆（合併後）
const hm2 = (ts: number, now?: number) => {
  const s = stamp(ts)           // MM/DD HH:MM
  return now !== undefined && new Date(now).toDateString() === new Date(ts).toDateString() ? s.slice(6) : s.slice(0, 5)
}
// 錯誤 / 改進紀錄表：時間 / 次數 / 來源 / 內容 / 狀態；每筆之間有橫線；內容欄吃剩餘寬度
export function errTable(lines: ErrEntry[], width: number, now?: number, max = LOG_SHOW): PaneLine[] {
  if (lines.length === 0) return [{ text: '（還沒有錯誤紀錄）', tone: 'gray' }]
  const groups = errGroups(lines).slice(0, max)
  const src = (e: ErrEntry) => `${e.client && !isMainClient(e.client) ? `${pLabel(e.client)} ` : ''}${e.source ?? ''}`.trim() || '—'
  const showSrc = width >= 56
  const sw = Math.min(12, Math.max(4, ...groups.map(g => dispW(src(g.e)))))
  const cols: TCol[] = [{ w: 5 }, { w: 4 }, ...(showSrc ? [{ w: sw }] : []), { w: 'flex' }, { w: 6 }]
  const rows: TRow[] = groups.map(({ e, n }) => ({
    cells: [hm2(e.ts, now), `×${n}`, ...(showSrc ? [src(e)] : []), e.error.replace(/\s+/g, ' '), e.fix ? '已改進' : '待改進'],
    tone: e.fix ? 'green' : 'yellow',
  }))
  return tableLines({ width, cols, header: ['時間', '次數', ...(showSrc ? ['來源'] : []), '內容', '狀態'], rows, rule: true })
}
export function paneLines(d: PaneData): PaneLine[] {
  const width = typeof d.width === 'number' && d.width >= 34 ? d.width : PANE_W
  const out: PaneLine[] = []
  const progs = Array.isArray(d.progs) ? d.progs : []
  const pgOf = (c: string) => progs.find(x => x.client === c)?.lines
  const wins: WinView[] = Array.isArray(d.wins) && d.wins.length
    ? d.wins
    : [{ client: MAIN_CLIENT, wl: d.wl ?? { main: '（沒有狀態）', hints: [] }, ht: d.ht ?? null, en: d.en ?? null }]
  const multi = wins.length > 1
  const banner = Array.isArray(d.banner) ? d.banner : []
  wins.forEach((w, k) => {
    const prog = pgOf(w.client) ?? (isMainClient(w.client) && Array.isArray(d.pg) ? d.pg : [])
    out.push(...winTable({ w, prog: Array.isArray(prog) ? prog : [], st: isMainClient(w.client) ? d.st ?? null : null }, width, multi, k === 0 ? banner : []))
  })
  out.push({ text: '', tone: 'plain' })
  out.push(...errTable(Array.isArray(d.lines) ? d.lines : [], width, d.now))
  return out
}
export type PaneEls = { Box: ElementConstructor<BoxProps>; Text: ElementConstructor<TextProps> }
export function paneTree(els: PaneEls, d: PaneData): RenderElement {
  const { Box, Text } = els
  const ls = paneLines(d)
  return (
    <Box flexDirection="column">
      {ls.map((l, i) => (
        <Text key={`l${i}`} wrap="truncate-end" color={l.tone === 'red' ? 'red' : l.tone === 'yellow' ? 'yellow' : l.tone === 'green' ? 'green' : undefined}
          dimColor={l.tone === 'gray'} bold={!!l.bold}>{l.text}</Text>
      ))}
    </Box>
  )
}

export const register: Register = on => {
  // 標題：UserPromptSubmit / SessionStart 都試；任何錯誤都吞掉，不擋使用者送訊息
  on('classic.UserPromptSubmit', async ($, e, next) => {
    const r = await next(e)
    const t = await autoTitle($, e.cwd, e.session_title)
    return t ? { ...r, sessionTitle: t } : r
  })
  on('classic.SessionStart', async ($, e, next) => {
    const r = await next(e)
    const t = await autoTitle($, e.cwd, e.session_title)
    return t ? { ...r, sessionTitle: t } : r
  })

  on('session.start', async ($, e, next) => {
    // 設定在使用者層級（每個專案都會載入），只在精靈王石器專案裡啟動
    if (!e.cwd.includes('PrimalSA-AI') || !e.isInteractive) return next(e)
    await $.command.register({ name: 'psa-hud', description: PSA_HUD_DESC })
    await init($, e.cwd, { openPane: true })
    return next(e)
  })

  on('command.run', { command: 'psa-hud' }, async ($, e) => {
    const arg = String((e as { args?: string }).args ?? '').trim().split(/\s+/)
    // 熱重載（/reload-plugins、存檔、worker 重生）後模組變數歸零、計時器被丟掉，session.start 不一定重發：
    // 指令進來時發現還沒初始化就補做（路徑、計時器、監督），不重開 pane（下面各分支自己決定）
    if (!inited) {
      let cwd = ''
      try { cwd = await $.session.cwd() } catch { /* 讀不到 cwd：照舊只用預設路徑 */ }
      if (cwd.includes(PROJECT)) await init($, cwd, { openPane: false })
    }
    if (arg[0] === 'off') {
      // 只關 pane；監看（watch）照跑，關監看用 /psa-hud watch off
      await $.ui.close({ id: PANE })
      return { text: 'psa-hud pane 已關閉（監看照跑；/psa-hud 或 /psa-hud on 重開）' }
    }
    if (arg[0] === 'ack') {
      // 人工確認過 quest 轉述的驗證警報：叫 watch 清掉（unknown_long 靠畫面恢復自動清）。多視窗：/psa-hud ack [程序名|all]（不給 = 全部）
      if (!sup) return { text: '監看未啟用（只在精靈王石器專案的互動 session 裡啟動）' }
      const tg = pickTargets(ctls.map(c => c.name), arg[1])
      if (typeof tg === 'string') return { text: tg }
      const out: string[] = []
      for (const n of tg) {
        const tag = ctls.length > 1 ? `[${n}] ` : ''
        try {
          const argv = await watchArgv($, ['--ack'])
          const r = isMainClient(n) ? await $.process.run(argv, { timeoutMs: 15000 }) : await $.process.run(argv, { timeoutMs: 15000, env: runEnv(n) })
          out.push(tag + (r.exitCode === 0 ? '已送出 ack：watch 下一輪清掉 quest 轉述的驗證警報（畫面不認得的警報要等畫面恢復才會清）' : `ack 失敗（退出碼 ${r.exitCode}）`))
        } catch (err) {
          out.push(`${tag}ack 失敗：${String(err).slice(0, 80)}`)
        }
      }
      return { text: out.join('\n') }
    }
    if (arg[0] === 'watch') {
      if (!sup) return { text: '監看未啟用（只在精靈王石器專案的互動 session 裡啟動）' }
      if (arg[1] !== undefined && arg[1] !== 'on' && arg[1] !== 'off' && arg[1] !== 'status') return { text: `用法：/psa-hud watch on|off|status${ctls.length > 1 ? ' [程序名|all]' : ''}` }
      const tg = pickTargets(ctls.map(c => c.name), arg[2])
      if (typeof tg === 'string') return { text: tg }
      const sel = ctls.filter(c => tg.includes(c.name))
      for (const c of sel) {
        if (arg[1] === 'off') await c.sup.setOff()
        else if (arg[1] === 'on') await c.sup.setOn()
      }
      await tickState($)
      const one = (c: Ctl) => `${ctls.length > 1 ? `[${c.name}] ` : ''}${supSummary(c.sup)}${c.sup.tail ? `\n最後輸出：${c.sup.tail.trim().split('\n').slice(-3).join(' / ')}` : ''}`
      return { text: sel.map(one).join('\n') }
    }
    await $.ui.open({ id: PANE, title: '精靈王石器' })
    const s = await refresh($)
    const ht = hudAlive ? await read($, hudAtom) : null
    let extra = ''
    if (ctls.length > 1) {
      // 多視窗：其他視窗各補一行（HUD 行 + 監看狀態）
      const wv = await read($, winsAtom)
      for (const c of ctls.slice(1)) extra += `\n[${c.name}] ${wv.find(w => w.client === c.name)?.ht ?? '（等級 / HP 讀取中…）'}｜${supSummary(c.sup)}`
    }
    return { text: (ctls.length > 1 ? `[${MAIN_CLIENT}] ` : '') + (ht ?? (s ? format(s) : '上一次讀取還在進行中')) + (sup ? `\n${supSummary(sup)}` : '') + extra }
  })

  on('ui.render', { component: 'Pane', requestId: PANE }, async ($, e) => {
    const els = $.ui.resolve(e)
    const { Box, Text } = els
    try {
      return paneTree(els, {
        wl: await read($, line), st: await read($, stat), ht: await read($, hudAtom), en: await read($, encAtom),
        pg: await read($, prog), lines: await read($, acts),
        wins: await read($, winsAtom), progs: await read($, progsAtom), banner: await read($, bannerAtom),
        width: (e as { props?: { bodyColumns?: number } }).props?.bodyColumns, now: await $.clock.now(),
      })
    } catch (err) {
      // 繪製出錯也要畫一行說明，不讓 pane 空白（hook 拋例外時引擎不畫任何東西）
      return (
        <Box flexDirection="column">
          <Text color="red">{`psa-hud 繪製失敗：${String(err).slice(0, 200)}`}</Text>
          <Text dimColor>（/psa-hud 重試；錯誤細節請回報開發）</Text>
        </Box>
      )
    }
  })
}
