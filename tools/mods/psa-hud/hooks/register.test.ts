import { expect, test } from 'claude-code/testing'

import {
  Supervisor, backoffMs, decideExit, errEntries, errLine, format, logPathFromCwd, parseState, stallThresholdMs, statPathFromCwd,
  viewModel, watchAlive, watchPathFromCwd, hudText, nameText,
} from './register'
import type { SupDeps, ViewIn } from './register'

const OK = '{"ok":true,"level":"0轉38級","hp":208,"mp":45,"petLevel":"0轉38級","petHp":434,"map":"奇努伊的海底通路","pos":"31401:91,29"}'

test('format：一行顯示等級 / HP / MP / 寵物 / 地圖', () => {
  expect(format(JSON.parse(OK))).toBe('0轉38級  HP 208  MP 45  |  寵 0轉38級 HP 434  |  奇努伊的海底通路 31401:91,29')
  expect(format({ ok: false, error: '遊戲沒有在執行' })).toBe('PSA: 遊戲沒有在執行')
  expect(format({ ok: true, level: '0轉1級', hp: null, mp: 3 })).toBe('0轉1級  HP ?  MP 3')
})

test('/psa-hud 開 pane、只跑 stat.ps1（不截圖、不產生色塊）並回報數值', async ($, on) => {
  const seen: string[][] = []
  on('process.run', (_$, e) => {
    seen.push([...e.argv])
    return { value: { exitCode: 0, stdout: `${OK}\r\n`, stderr: '', isStdoutTruncated: false, isStderrTruncated: false } }
  })
  on('ui.open', () => ({ value: { isPlaced: true } }))
  on('clock.now', () => ({ value: 0 }))
  const { text } = await $.command.run({ command: 'psa-hud', args: '' } as never)
  expect(text).toBe('0轉38級  HP 208  MP 45  |  寵 0轉38級 HP 434  |  奇努伊的海底通路 31401:91,29')
  expect(seen[0]?.[0]).toBe('powershell.exe')
  expect(seen[0]).not.toContain('-Shot')
  expect(seen[0]).not.toContain('-Blocks')
})

test('stat.ps1 失敗時回報讀取失敗', async ($, on) => {
  on('process.run', () => ({ value: { exitCode: 1, stdout: '', stderr: 'boom', isStdoutTruncated: false, isStderrTruncated: false } }))
  on('ui.open', () => ({ value: { isPlaced: true } }))
  on('clock.now', () => ({ value: 0 }))
  const { text } = await $.command.run({ command: 'psa-hud', args: '' } as never)
  expect(text).toBe('PSA: 讀取失敗 boom')
})

test('statPathFromCwd：WSL / Windows / Git Bash / 子目錄都換成 Windows 路徑', () => {
  const want = 'C:\\games\\PrimalSA-AI\\tools\\gui\\stat.ps1'
  expect(statPathFromCwd('/mnt/c/games/PrimalSA-AI')).toBe(want)
  expect(statPathFromCwd('C:\\games\\PrimalSA-AI')).toBe(want)
  expect(statPathFromCwd('C:/games/PrimalSA-AI/tools')).toBe(want)
  expect(statPathFromCwd('/c/games/PrimalSA-AI')).toBe(want)
  expect(statPathFromCwd('/home/x/other')).toBeUndefined()
})

test('errEntries：只取最新 100 筆、最新在前、略過空行與壞行', () => {
  const text = Array.from({ length: 120 }, (_, i) => JSON.stringify({ id: i + 1, ts: 0, error: `e${i + 1}`, fix: null, source: null })).join('\n') + '\n\nnot json\n'
  const l = errEntries(text)
  expect(l.length).toBe(100)
  expect(l[0]?.id).toBe(120)
  expect(l[99]?.id).toBe(21)
})

test('errLine：有改進顯示 → 改進，沒有標待改進', () => {
  const ts = new Date(2026, 9, 9, 23, 18).getTime()
  const a = errLine({ id: 9, ts, error: '空等', fix: '閒置結束', source: 'quest' })
  expect(a.head).toBe('10/09 23:18 #9 [quest] 空等')
  expect(a.fix).toBe('→ 改進：閒置結束')
  expect(a.pending).toBe(false)
  const b = errLine({ id: 10, ts, error: 'x', fix: null, source: null })
  expect(b.fix).toBe('→ 待改進')
  expect(b.pending).toBe(true)
})

test('format：OCR 讀不到數字時改用血條比例', () => {
  expect(format({ ok: true, level: '0轉5級', hp: null, mp: null, hpPct: 80, mpPct: 100 })).toBe('0轉5級  HP 80%  MP 100%')
  expect(format({ ok: true, hp: null, mp: null })).toContain('讀不到 HUD')
})

test('logPathFromCwd：WSL / Windows / Git Bash 都接到 tools/.cache/errlog.jsonl', () => {
  expect(logPathFromCwd('/mnt/c/games/PrimalSA-AI/tools')).toBe('/mnt/c/games/PrimalSA-AI/tools/.cache/errlog.jsonl')
  expect(logPathFromCwd('C:\\games\\PrimalSA-AI')).toBe('C:\\games\\PrimalSA-AI/tools/.cache/errlog.jsonl')
  expect(logPathFromCwd('/home/x')).toBeUndefined()
})


// ───────────── 即時狀態監看（第 4 階段）─────────────
const ST = (o: Record<string, unknown> = {}) => ({ v: 1, seq: 5, phase: 'running', watcher: { token: 'aa', running: true, interval: 0.5 }, screen: { label: '主畫面', age_s: 0.1 }, ...o })
const VIN = (o: Partial<ViewIn> = {}): ViewIn => ({ state: ST() as never, badVersion: null, status: 'running', lastCode: null, now: 1000, seenAt: 1000, hasFile: true, ...o })

test('狀態行：label 原樣顯示，N 秒前只在 > 3 s 才出現（age_s + 本地經過時間）', () => {
  expect(viewModel(VIN()).main).toBe('主畫面')
  expect(viewModel(VIN({ now: 1000 + 2800 })).main).toBe('主畫面')            // 0.1 + 2.8 < 3
  expect(viewModel(VIN({ now: 1000 + 3000 })).main).toBe('主畫面 ｜ 3 秒前')     // 0.1 + 3.0 > 3
  expect(viewModel(VIN({ now: 1000 + 12000 })).main).toBe('主畫面 ｜ 12 秒前')
  expect(viewModel(VIN({ state: ST({ screen: { label: '戰鬥中（完整・下指令）', age_s: 5 } }) as never })).main).toBe('戰鬥中（完整・下指令） ｜ 5 秒前')
  for (const l of [viewModel(VIN()).main, viewModel(VIN({ state: null })).main]) expect(l.includes('安全')).toBe(false)
})

test('狀態行提示：失敗 / 只讀 / 關閉 / 未執行 / 啟動中 / 版本', () => {
  const h = (o: Partial<ViewIn>) => viewModel(VIN(o)).hints
  expect(h({ status: 'failed', lastCode: 1 })[0]).toEqual({ text: '監看啟動失敗（最後退出碼 1）；/psa-hud watch on 重試', tone: 'red' })
  expect(h({ status: 'ro3' })[0]?.tone).toBe('gray')
  expect(h({ status: 'ro6' })[0]?.text).toContain('另一平台')
  expect(h({ status: 'off' })[0]?.text).toContain('已關閉')
  expect(h({ status: 'ro3', now: 1000 + 11000 }).map(x => x.text)).toContain('監看未執行（state.json 沒有更新）')
  expect(h({ status: 'running', now: 1000 + 20000 })).toEqual([])                       // 自己管的由卡住機制處理，不另外提示
  expect(h({ status: 'running', state: null, hasFile: false })[0]?.text).toBe('監看啟動中…')
  expect(h({ status: 'waiting', lastCode: 7 })[0]).toEqual({ text: '監看重開中（上次退出碼 7）', tone: 'yellow' })
  const bad = viewModel(VIN({ state: null, badVersion: 2 }))
  expect(bad.main).toContain('版本不符')
  expect(h({ state: ST({ flags: { verify_suspect: true, netwatch_halt: true } }) as never }).map(x => x.tone)).toEqual(['red', 'red'])
})

test('parseState：v 主版本 1 才收、忽略不認得的鍵、壞檔回 null', () => {
  expect(parseState(JSON.stringify({ v: 1, seq: 3, 未知: 1 })).state?.seq).toBe(3)
  expect(parseState(JSON.stringify({ v: 1.2, seq: 3 })).state?.seq).toBe(3)
  expect(parseState(JSON.stringify({ v: 2 }))).toEqual({ state: null, badVersion: 2 })
  expect(parseState('{"v":1,')).toEqual({ state: null, badVersion: null })
  expect(parseState(undefined).state).toBeNull()
})

test('watchPathFromCwd：WSL / Windows / Git Bash，依直譯器形式決定路徑', () => {
  expect(watchPathFromCwd('/mnt/c/games/PrimalSA-AI/tools', '/usr/bin/python3')).toBe('/mnt/c/games/PrimalSA-AI/tools/gui/watch.py')
  expect(watchPathFromCwd('/mnt/c/games/PrimalSA-AI', '/home/bal/.local/bin/python3.12')).toBe('/mnt/c/games/PrimalSA-AI/tools/gui/watch.py')
  expect(watchPathFromCwd('C:\\games\\PrimalSA-AI', 'C:\\Python312\\python.exe')).toBe('C:\\games\\PrimalSA-AI\\tools\\gui\\watch.py')
  expect(watchPathFromCwd('/c/games/PrimalSA-AI', 'C:\\x\\python.exe')).toBe('C:\\games\\PrimalSA-AI\\tools\\gui\\watch.py')
  expect(watchPathFromCwd('/mnt/c/games/PrimalSA-AI', 'C:\\x\\python.exe')).toBe('C:\\games\\PrimalSA-AI\\tools\\gui\\watch.py')   // WSL 呼叫 Windows 直譯器
  expect(watchPathFromCwd('C:\\games\\PrimalSA-AI', '/usr/bin/python3')).toBe('/mnt/c/games/PrimalSA-AI/tools/gui/watch.py')
  expect(watchPathFromCwd('/mnt/c/games/PrimalSA-AI')).toBe('/mnt/c/games/PrimalSA-AI/tools/gui/watch.py')                          // uv run 退路：由 cwd 推斷
  expect(watchPathFromCwd('C:/games/PrimalSA-AI/tools')).toBe('C:\\games\\PrimalSA-AI\\tools\\gui\\watch.py')
  expect(watchPathFromCwd('/home/x')).toBeUndefined()
})

test('decideExit：退出碼 3 / 5 / 6 不重試；3 在啟動寬限內等 3 s 重試一次', () => {
  const base = { ranMs: 1000, progressed: false, consec: 0, idx: 0, grace: false }
  expect(decideExit({ ...base, code: 5 }, 0.5).action).toBe('stopped')
  expect(decideExit({ ...base, code: 6 }, 0.5).action).toBe('ro6')
  expect(decideExit({ ...base, code: 3 }, 0.5).action).toBe('ro3')
  const g = decideExit({ ...base, code: 3, grace: true }, 0.5)
  expect([g.action, g.delayMs, g.grace]).toEqual(['retry', 3000, false])
  expect(decideExit({ ...base, code: 1 }, 0.5).action).toBe('retry')
})

test('退避序列 2/5/15/30/60 s 各 ±20%，超過上限固定 60 s', () => {
  expect([0, 1, 2, 3, 4, 9].map(i => backoffMs(i, 0.5))).toEqual([2000, 5000, 15000, 30000, 60000, 60000])
  expect(backoffMs(0, 0)).toBe(1600)
  expect(backoffMs(4, 1)).toBe(72000)
})

test('decideExit：連續 5 次跑不到 30 s 停；跑滿 60 s 或 seq 前進歸零；30~60 s 不算短也不歸零 idx', () => {
  let st = { consec: 0, idx: 0, grace: false }
  const acts: string[] = []
  for (let n = 0; n < 5; n++) {
    const o = decideExit({ code: 1, ranMs: 2000, progressed: false, ...st }, 0.5)
    acts.push(o.action); st = { consec: o.consec, idx: o.idx, grace: o.grace }
  }
  expect(acts).toEqual(['retry', 'retry', 'retry', 'retry', 'failed'])
  const a = decideExit({ code: 1, ranMs: 61000, progressed: false, consec: 4, idx: 4, grace: false }, 0.5)
  expect([a.action, a.consec, a.idx, a.delayMs]).toEqual(['retry', 0, 1, 2000])
  const b = decideExit({ code: 1, ranMs: 3000, progressed: true, consec: 4, idx: 4, grace: false }, 0.5)
  expect([b.action, b.consec, b.idx]).toEqual(['retry', 0, 1])
  const c = decideExit({ code: 1, ranMs: 40000, progressed: false, consec: 4, idx: 2, grace: false }, 0.5)
  expect([c.action, c.consec, c.idx]).toEqual(['retry', 0, 3])
})

test('卡住門檻：starting / 還沒進展 45 s；其他 max(10 s, 3×interval)', () => {
  expect(stallThresholdMs('starting', 0.5, true)).toBe(45000)
  expect(stallThresholdMs('running', 0.5, false)).toBe(45000)
  expect(stallThresholdMs('running', 0.5, true)).toBe(10000)
  expect(stallThresholdMs('running', 4, true)).toBe(12000)
  expect(stallThresholdMs(undefined, undefined, true)).toBe(10000)
})

// ── Supervisor：假子程序 / 假時鐘，驗 spawn 次數與狀態 ──
type Run = { chunks?: string[]; code?: number; runMs?: number; hang?: boolean }
function harness(runs: Run[]) {
  const t = { now: 100000 }
  const log = { spawns: 0, stops: 0, cfg: [] as boolean[], returned: 0, pulled: 0 }
  const deps: SupDeps = {
    spawn: () => {
      const r = runs[log.spawns] ?? runs[runs.length - 1]!
      log.spawns++
      const chunks = [...(r.chunks ?? [])]
      let release: (() => void) | undefined
      return {
        next: () => {
          log.pulled++
          const c = chunks.shift()
          if (c !== undefined) return Promise.resolve({ done: false, value: { stream: 'stdout', text: c } })
          if (r.hang) return new Promise<never>(res => { release = () => res(undefined as never) })
          t.now += r.runMs ?? 1000
          return Promise.resolve({ done: true, value: { code: r.code ?? 1, signal: null } })
        },
        return: () => { log.returned++; release?.(); return Promise.resolve(undefined) },
      }
    },
    now: () => Promise.resolve(t.now),
    sleep: ms => { t.now += ms; return Promise.resolve() },
    rnd: () => 0.5,
    stopCli: () => { log.stops++; return Promise.resolve() },
    saveCfg: on => { log.cfg.push(on); return Promise.resolve() },
  }
  return { t, log, sup: new Supervisor(deps) }
}
const settle = async () => { for (let i = 0; i < 3000; i++) await Promise.resolve() }

test('Supervisor：退出碼 3 / 6 / 5 不重試（3 在寬限內先重試一次）', async () => {
  const a = harness([{ code: 6 }]); a.sup.start(); await settle()
  expect([a.log.spawns, a.sup.status]).toEqual([1, 'ro6'])
  const b = harness([{ code: 5 }]); b.sup.start(); await settle()
  expect([b.log.spawns, b.sup.status]).toEqual([1, 'stopped'])
  const c = harness([{ code: 3 }, { code: 3 }]); c.sup.start(); await settle()
  expect([c.log.spawns, c.sup.status, c.sup.lastCode]).toEqual([2, 'ro3', 3])
  const d = harness([{ code: 3 }, { code: 0, chunks: ['x'], hang: true }]); d.sup.start(); await settle()
  expect([d.log.spawns, d.sup.status]).toEqual([2, 'running'])                // 舊子程序收尾完 → 第二次接手成功
})

test('Supervisor：連續 5 次跑不到 30 s → 共 spawn 5 次後停止（監看啟動失敗）', async () => {
  const h = harness([{ code: 1, runMs: 500 }]); h.sup.start(); await settle()
  expect([h.log.spawns, h.sup.status, h.sup.lastCode]).toEqual([5, 'failed', 1])
  expect(viewModel(VIN({ status: h.sup.status, lastCode: h.sup.lastCode })).hints[0]?.tone).toBe('red')
  await settle()
  expect(h.log.spawns).toBe(5)
})

test('Supervisor：卡住 → return() 結束舊串流 → 重開 1 次；門檻內不動', async () => {
  const h = harness([{ hang: true, chunks: ['hi'] }, { hang: true }])
  h.sup.start(); await settle()
  expect(h.log.spawns).toBe(1)
  await h.sup.observe('t:1', 'running', 0.5)                  // 第一次看到 key：進展
  h.t.now += 9000; await h.sup.observe('t:1', 'running', 0.5); await settle()
  expect([h.log.spawns, h.log.returned]).toEqual([1, 0])      // 9 s < 10 s
  h.t.now += 2000; await h.sup.observe('t:1', 'running', 0.5); await settle()
  expect(h.log.returned).toBe(1)
  expect(h.log.spawns).toBe(2)
  expect(h.sup.stalls).toBe(1)
})

test('Supervisor：phase=starting / 沒進展 45 s 內不重開', async () => {
  const h = harness([{ hang: true }])
  h.sup.start(); await settle()
  h.t.now += 40000; await h.sup.observe(null, 'starting', null); await settle()
  expect(h.log.spawns).toBe(1)
  h.t.now += 6000; await h.sup.observe(null, 'starting', null); await settle()
  expect(h.log.returned).toBe(1)
})

test('Supervisor：stdout 灌 2 MB 會被持續讀完（不卡子程序）', async () => {
  const big = Array.from({ length: 200 }, () => 'x'.repeat(10000) + '\n')
  const h = harness([{ chunks: big, code: 6 }]); h.sup.start(); await settle()
  expect(h.log.pulled).toBe(201)
  expect(h.sup.status).toBe('ro6')
  expect(h.sup.tail.length).toBeLessThan(5000)
})

test('Supervisor：off 呼叫 --stop 並寫設定、不再重開；on 重新啟動並歸零', async () => {
  const h = harness([{ hang: true }, { hang: true }])
  h.sup.start(); await settle()
  await h.sup.setOff(); await settle()
  expect([h.log.stops, h.log.cfg, h.sup.status, h.log.spawns]).toEqual([1, [false], 'off', 1])
  expect(h.log.returned).toBe(1)                                  // 殘留的串流被收掉
  await settle()
  expect(h.log.spawns).toBe(1)                                    // off 之後不重開
  await h.sup.setOn(); await settle()
  expect([h.log.cfg, h.log.spawns, h.sup.status]).toEqual([[false, true], 2, 'running'])
})

// ── 第 3 階段：state.hud → HUD 行；watch 活著時不再需要一次性 stat ──
const HUD = {
  ok: true, stale: false, age_s: 0.5,
  level: { v: '0轉77級', ts: 1 }, hp: { v: 208, ts: 1 }, hpPct: { v: 80, ts: 1 }, mp: { v: 45, ts: 1 }, mpPct: { v: 100, ts: 1 },
  pet: { level: { v: '0轉77級', ts: 1 }, hp: { v: 434, ts: 1 } }, map: { v: '奇努伊的海底通路', id: 31401, ts: 1 }, pos: { v: [91, 29], ts: 1 },
}

test('hudText：state.hud 組成與 format 同格式的一行；stale 加（原因 · N 秒前）', () => {
  const st = { v: 1, hud: HUD, screen: { state: 'idle' } }
  expect(hudText(st, 0, 0)).toBe('0轉77級  HP 208  MP 45  |  寵 0轉77級 HP 434  |  奇努伊的海底通路 31401:91,29')
  const stale = { v: 1, hud: { ...HUD, stale: true, ok: false, age_s: 20 }, screen: { state: 'battle', full: true } }
  expect(hudText(stale, 5000, 0)).toBe('0轉77級  HP 208  MP 45  |  寵 0轉77級 HP 434  |  奇努伊的海底通路 31401:91,29（戰鬥前 · 25s 前）')
  expect(hudText({ v: 1, hud: { ok: false, stale: true } }, 0, 0)).toBeNull()      // 一個值都沒有
  expect(hudText({ v: 1 }, 0, 0)).toBeNull()
  expect(hudText(null, 0, 0)).toBeNull()
  // 只有血條比例（OCR 讀不到數字）時顯示百分比
  expect(hudText({ v: 1, hud: { ok: true, level: { v: '0轉1級' }, hpPct: { v: 30 } } }, 0, 0)).toBe('0轉1級  HP 30%  MP ?')
})

test('watchAlive：(token, seq) 10 s 內有變才算活著；watcher.running=false 不算；沒有 state 不算', () => {
  const st = { v: 1, watcher: { running: true } }
  expect(watchAlive(st, 5000, 0)).toBe(true)
  expect(watchAlive(st, 10001, 0)).toBe(false)
  expect(watchAlive({ v: 1, watcher: { running: false } }, 100, 0)).toBe(false)
  expect(watchAlive(null, 0, 0)).toBe(false)
})

// ── 第 5 階段：警示顯示 ──
test('警示：提示視窗 = 黃字；verify_suspect / alerts = 紅字（verify_suspect 與 alerts 各一行，最多 2 筆 alerts）；標籤不出現「安全」', () => {
  const h = (o: Record<string, unknown>) => viewModel(VIN({ state: ST(o) as never })).hints
  expect(h({ screen: { label: '主畫面（提示視窗）', age_s: 0, annot: ['notice_dialog'] } })).toEqual([{ text: '畫面上有提示視窗，請看一眼', tone: 'yellow' }])
  expect(h({ screen: { label: '登入畫面', age_s: 0, annot: ['login'] } })).toEqual([])      // 登入 / 選角只改標籤，不是警示
  const a = h({ flags: { verify_suspect: true }, alerts: [{ kind: 'unknown_long', msg: '不認得的畫面超過 10 秒（可能是驗證視窗，請人工確認）' }, { kind: 'verify', line: 'L2' }, { kind: 'verify', line: 'L3' }] })
  expect(a.map(x => x.tone)).toEqual(['red', 'red', 'red'])
  expect(a[0]?.text).toContain('疑似答題')
  expect(a.some(x => x.text.includes('L3'))).toBe(false)
})

// ── 第 7 階段：人物名 / 寵物名顯示 ──
test('nameText：沒有 → 不顯示；? 照舊；stale 加結尾 ?；conflict 加 !', () => {
  expect(nameText(undefined)).toBeUndefined()
  expect(nameText({ v: 'DKB0', ts: 1 })).toBe('DKB0')
  expect(nameText({ v: 'DKB0', ts: 1, stale: true })).toBe('DKB0?')
  expect(nameText({ v: 'DKB05', ts: 1, conflict: true })).toBe('DKB05!')
  expect(nameText({ v: '?', ts: undefined })).toBe('?')
})

test('hudText：帶人物名 / 寵物名；沒學過的寵物顯示 ?；只有名字不算有資料', () => {
  const st = { v: 1, hud: { ...HUD, name: { v: 'DKB0', ts: 1 }, pet: { ...HUD.pet, name: { v: '迪基格斯', ts: 1 } } }, screen: { state: 'idle' } }
  expect(hudText(st, 0, 0)).toBe('DKB0  0轉77級  HP 208  MP 45  |  寵 迪基格斯 0轉77級 HP 434  |  奇努伊的海底通路 31401:91,29')
  const unk = { v: 1, hud: { ...HUD, name: { v: '?' }, pet: { ...HUD.pet, name: { v: '?' } } }, screen: { state: 'idle' } }
  expect(hudText(unk, 0, 0)).toBe('?  0轉77級  HP 208  MP 45  |  寵 ? 0轉77級 HP 434  |  奇努伊的海底通路 31401:91,29')
  expect(hudText({ v: 1, hud: { ok: false, stale: true, name: { v: 'DKB0' } } }, 0, 0)).toBeNull()
})

// ───────── 自動 session 標題 ─────────
import { autoTitle, mayRetitle, questNames, titleFromLog } from './register'

const NAMES = questNames("dict(id=3003, detail='猜謎三兄弟'),\n dict(id=2000, detail='琉璃洞窟', track='x'),\n dict(id=2019, detail='卡坦的願望(1.82)', track='y')")

test('titleFromLog：進行中 / 已完成 / 失敗 / 四大洞窟前綴 / 長度', () => {
  const run = '2026-10-12 10:56:32 [questrun] 開始：任務 [2000]，選項 {}\n2026-10-12 10:57:11 [questrun] 任務 2000「琉璃洞窟」詳情結果：accepted\n追蹤 x\n'
  expect(titleFromLog(run, NAMES)).toBe('PSA｜四大洞窟：琉璃洞窟 進行中')
  expect(titleFromLog(run + '2026-10-12 11:00:00 [questrun] 結束 rc=112，完成 []；失敗退出\n', NAMES)).toBe('PSA｜四大洞窟：琉璃洞窟 失敗 rc=112')
  const done = '[questrun] 任務 2019「卡坦的願望(1.82)」已完成（quest.py 任務完成；219 秒、1 片）\n'
  expect(titleFromLog(done, NAMES)).toBe('PSA｜卡坦的願望 已完成')
  expect(titleFromLog('x [questrun] 開始：任務 [2000]，選項 {}\n', NAMES)).toBe('PSA｜四大洞窟：琉璃洞窟 進行中')
  expect(titleFromLog('x [questrun] 結束 rc=0，完成 [2019]\n[questrun] 開始：任務 [2019]\n', NAMES)).toBe('PSA｜卡坦的願望 進行中')
  expect(titleFromLog('沒有紀錄\n', NAMES)).toBeUndefined()
  expect(titleFromLog('', NAMES)).toBeUndefined()
  expect((titleFromLog('[questrun] 任務 1「' + '很長'.repeat(30) + '」詳情結果：ok\n') ?? '').length).toBeLessThanOrEqual(40)
})

test('titleFromLog：不跨 run 抓名字；rc≠0 後有別的事件 → 接手中', () => {
  const prev = '14:00:00 [questrun] 開始：任務 [2002]\n14:01:00 [questrun] 任務 2002「碧青洞窟」詳情結果：ok\n14:02:00 [questrun] 結束 rc=0，完成 [2002]\n'
  const cur = '14:36:09 [questrun] 開始：任務 [3003]，選項 {}\n14:36:30 [questrun] 追蹤 x\n14:37:07 [questrun] 結束 rc=111，完成 []；失敗退出，不恢復掛機\n'
  expect(titleFromLog(prev + cur, NAMES)).toBe('PSA｜猜謎三兄弟 失敗 rc=111')
  expect(titleFromLog(prev + cur + '14:37:59 [quiztower] 811 → 800\n[petwatch] x\n', NAMES)).toBe('PSA｜猜謎三兄弟 接手中（questrun rc=111）')
  expect(titleFromLog(prev + cur + '\n\n', NAMES)).toBe('PSA｜猜謎三兄弟 失敗 rc=111')
  // 多 ID：取本 run 內最後出現的「任務 N」
  const multi = '1 [questrun] 開始：任務 [2000, 2019]\n2 [questrun] 任務 2000「琉璃洞窟」詳情結果：ok\n3 [questrun] 任務 2019「卡坦的願望(1.82)」詳情結果：ok\n'
  expect(titleFromLog(multi, NAMES)).toBe('PSA｜卡坦的願望 進行中')
  // rc=0 後有別的事件仍是已完成
  expect(titleFromLog(prev + '[quiztower] x\n', NAMES)).toBe('PSA｜四大洞窟：碧青洞窟 已完成')
})

test('mayRetitle：空與 PSA｜ 開頭才可改，使用者自取的不動', () => {
  expect(mayRetitle(undefined)).toBe(true)
  expect(mayRetitle('')).toBe(true)
  expect(mayRetitle('PSA｜舊標題')).toBe(true)
  expect(mayRetitle('我的名字')).toBe(false)
})

test('autoTitle：輸出標題；已是同標題 / 使用者自取名 / 非本專案 / 讀檔失敗都不輸出也不拋錯', async () => {
  const log = '[questrun] 任務 2000「琉璃洞窟」詳情結果：accepted\n'
  const mk = (fail = false) => ({ clock: { now: async () => Date.now() }, fs: { read: async (p: string) => { if (fail) throw new Error('boom'); return p.endsWith('quest-events.log') ? log : "dict(id=2000, detail='琉璃洞窟')" } } }) as never
  const root = '/mnt/c/games/PrimalSA-AI'
  expect(await autoTitle(mk(), root, undefined)).toBe('PSA｜四大洞窟：琉璃洞窟 進行中')
  expect(await autoTitle(mk(), 'C:\\games\\PrimalSA-AI\\tools', '')).toBe('PSA｜四大洞窟：琉璃洞窟 進行中')
  expect(await autoTitle(mk(), root, 'PSA｜四大洞窟：琉璃洞窟 進行中')).toBeUndefined()
  expect(await autoTitle(mk(), root, '使用者的名字')).toBeUndefined()
  expect(await autoTitle(mk(), '/home/x/other', undefined)).toBeUndefined()
  expect(await autoTitle(mk(true), root, undefined)).toBeUndefined()
})

// ───────── 即時進度區 ─────────
import { actionAgeS, cleanEvent, progressLines } from './register'

test('cleanEvent：去日期 / 截圖路徑 / [questrun]', () => {
  expect(cleanEvent('2026-10-12 11:34:20 自動巡路中 C:\\games\\PrimalSA-AI\\tools\\.cache\\shot1.png')).toBe('11:34:20 自動巡路中')
  expect(cleanEvent('2026-10-12 11:42:02 [questrun] 結束 rc=9')).toBe('11:42:02 結束 rc=9')
})

test('actionAgeS：同日 / 跨午夜 / 壞格式', () => {
  const now = new Date(2026, 9, 12, 11, 42, 30).getTime()
  expect(actionAgeS('11:42:02 x', now)).toBe(28)
  expect(actionAgeS('23:59:50 x', new Date(2026, 9, 12, 0, 0, 10).getTime())).toBe(20)
  expect(actionAgeS('壞', now)).toBeUndefined()
})

test('progressLines：任務 / 3 行事件 / 動作 / 警報，≤6 行；壞檔顯示 —', () => {
  const now = new Date(2026, 9, 12, 11, 42, 30).getTime()
  const quest = '2026-10-12 11:00:00 [questrun] 任務 2000「琉璃洞窟」詳情結果：accepted\n2026-10-12 11:34:06 追蹤沒反應 → 刷新角色重點\n2026-10-12 11:34:20 自動巡路中\n\n2026-10-12 11:34:30 ' + '長'.repeat(80) + '\n'
  const r = progressLines({ quest, actions: '11:42:20 click 120,80\n', state: null, now }, NAMES)
  expect(r.map(x => x.text).slice(0, 4)).toEqual(['任務：四大洞窟：琉璃洞窟 進行中', ' 11:34:06 追蹤沒反應 → 刷新角色重點', ' 11:34:20 自動巡路中', r[3]!.text])
  expect(r[3]!.text.length).toBeLessThanOrEqual(56)
  expect(r[4]).toEqual({ text: '動作 11:42:20 click 120,80（10 秒前）', tone: 'plain' })
  expect(r.length).toBe(5)
  const idle = progressLines({ quest, actions: '11:30:00 click', state: { v: 1, alerts: [{ msg: '驗證' }] } as never, now }, NAMES)
  expect(idle[4]).toEqual({ text: '動作 11:30:00 click（閒置 12 分）', tone: 'yellow' })
  expect(idle[5]).toEqual({ text: '警報：驗證', tone: 'red' })
  const v = progressLines({ state: { v: 1, flags: { verify_suspect: true } } as never, now })
  expect(v.map(x => x.text)).toEqual(['任務：—', '事件：—', '動作：—', '警報：疑似答題 / 驗證視窗，請人工處理'])
  expect(v.length).toBeLessThanOrEqual(6)
})

// ───────── 練功中判斷 ─────────
import { grindActivity, grindTitle } from './register'

const GQ = '2026-10-12 15:00:58 [questrun] 結束 rc=0，完成 [3003]\n'
const GA = '14:43:25 grind 傳送到 地雷區 60049:30,25\n14:43:33 grind ass：DKBO2 快速戰鬥 → 開（已確認）\n14:43:44 grind ass：DKBO 快速戰鬥 → 開（已確認）\n15:44:30 depot_use 原地遇敵：開\n15:44:57 click 1318,90 ass.py 關外掛面板\n'
const gnow = new Date(2026, 9, 12, 15, 45, 30).getTime()
const gst = (o: object = {}) => ({ v: 1, ts: gnow / 1000 - 1, screen: { enc_on: true }, hud: { map: { v: '庫塔伊洞窟地下一樓', id: 60049 } }, ...o }) as never

test('練功中：questrun 完成後 grind → 顯示練功中（快速戰鬥）；標題同步', () => {
  const g = grindActivity({ quest: GQ, actions: GA, state: gst(), now: gnow })
  expect(g).toEqual({ spot: '地雷區', quick: true })
  expect(grindTitle(g!)).toBe('PSA｜練功中 地雷區')
  expect(progressLines({ quest: GQ, actions: GA, state: gst(), now: gnow }, NAMES)[0]).toEqual({ text: '練功中：地雷區（快速戰鬥）', tone: 'plain' })
})

test('練功中：grind 後又開新 questrun → 回任務顯示；沒有快速戰鬥紀錄不加；無 state 仍判斷', () => {
  const q2 = GQ + '2026-10-12 15:45:00 [questrun] 開始：任務 [2000]，選項 {}\n'
  expect(grindActivity({ quest: q2, actions: GA, state: gst(), now: gnow })).toBeUndefined()
  expect(progressLines({ quest: q2, actions: GA, state: gst(), now: gnow }, NAMES)[0]!.text).toBe('任務：四大洞窟：琉璃洞窟 進行中')
  expect(grindActivity({ quest: GQ, actions: '14:43:25 grind 傳送到 地雷區 60049:30,25\n15:44:30 drv 原地遇敵：開\n', state: null, now: gnow })).toEqual({ spot: '地雷區', quick: false })
})

test('練功中：遇敵關掉 / enc_on=false / 離開練功點 / 太久 都不算', () => {
  expect(grindActivity({ quest: GQ, actions: GA + '15:45:10 drv 原地遇敵：關\n', state: gst(), now: gnow })).toBeUndefined()
  expect(grindActivity({ quest: GQ, actions: GA, state: gst({ screen: { enc_on: false } }), now: gnow })).toBeUndefined()
  expect(grindActivity({ quest: GQ, actions: GA, state: gst({ hud: { map: { v: '薩姆吉爾村', id: 1000 } } }), now: gnow })).toBeUndefined()
  expect(grindActivity({ quest: GQ, actions: GA, state: null, now: new Date(2026, 9, 12, 18, 0, 0).getTime() })).toBeUndefined()
  // state 太舊 → 當沒有，不因地圖 / enc_on 判掉
  expect(grindActivity({ quest: GQ, actions: GA, state: gst({ ts: gnow / 1000 - 600, screen: { enc_on: false } }), now: gnow })).toBeDefined()
  expect(grindActivity({ quest: GQ, actions: undefined, state: gst(), now: gnow })).toBeUndefined()
})

test('練功中：actions 跨午夜（遇敵 23:50 開、現在 00:10）仍算；questrun 昨天結束不影響', () => {
  const n = new Date(2026, 9, 13, 0, 10, 0).getTime()
  expect(grindActivity({ quest: '2026-10-12 23:00:00 [questrun] 結束 rc=0，完成 [3003]\n', actions: '23:50:00 grind 原地遇敵：開\n', state: null, now: n })).toEqual({ spot: '原地', quick: false })
  // questrun 00:05（今天）比 23:50 遇敵開新 → 任務
  expect(grindActivity({ quest: '2026-10-13 00:05:00 [questrun] 開始：任務 [2000]\n', actions: '23:50:00 grind 原地遇敵：開\n', state: null, now: n })).toBeUndefined()
})

test('autoTitle：練功中 → PSA｜練功中 地雷區；使用者自取名不動', async () => {
  const mk = () => ({ clock: { now: async () => gnow }, fs: { read: async (p: string) => p.endsWith('quest-events.log') ? GQ + '2026-10-12 15:00:58 [questrun] 任務 3003「猜謎三兄弟」已完成（x）\n' : p.endsWith('actions.log') ? GA : p.endsWith('state.json') ? JSON.stringify(gst()) : '' } }) as never
  const root = '/mnt/c/games/PrimalSA-AI'
  expect(await autoTitle(mk(), root, 'PSA｜猜謎三兄弟 已完成')).toBe('PSA｜練功中 地雷區')
  expect(await autoTitle(mk(), root, 'PSA｜練功中 地雷區')).toBeUndefined()
  expect(await autoTitle(mk(), root, '我的名字')).toBeUndefined()
})

test('練功中：快速戰鬥紀錄在 600 行之前也認得；任一人最後是關就不標', () => {
  const filler = Array.from({ length: 700 }, () => '15:00:00 click 1,1\n').join('')
  const a = GA.split('\n').slice(0, 3).join('\n') + '\n' + filler + '15:44:30 depot_use 原地遇敵：開\n'
  expect(grindActivity({ quest: GQ, actions: a, state: gst(), now: gnow })!.quick).toBe(true)
  expect(grindActivity({ quest: GQ, actions: a + '15:44:40 grind ass：DKBO3 快速戰鬥 → 關\n', state: gst(), now: gnow })!.quick).toBe(false)
})

// ───────── buff 顯示 ─────────
import { buffText } from './register'

test('buffText / hudText：EXP×2、龍王；stale 加 ?；沒有就不顯示', () => {
  expect(buffText(undefined)).toBeUndefined()
  expect(buffText({ v: [] })).toBeUndefined()
  expect(buffText({ v: ['exp', 'dragon'] })).toBe('EXP×2 龍王')
  expect(buffText({ v: ['exp'], stale: true })).toBe('EXP×2?')
  const st = { v: 1, hud: { ...HUD, buffs: { v: ['exp'], ts: 1 } }, screen: { state: 'idle' } }
  expect(hudText(st, 0, 0)).toBe('0轉77級  HP 208  MP 45  |  寵 0轉77級 HP 434  |  奇努伊的海底通路 31401:91,29  |  EXP×2')
  expect(hudText({ v: 1, hud: { ...HUD, buffs: { v: [], ts: 1 } } }, 0, 0)).toBe('0轉77級  HP 208  MP 45  |  寵 0轉77級 HP 434  |  奇努伊的海底通路 31401:91,29')
})

test('練功中那行：有 exp buff 加「＋EXP×2」（stale 加 ?）', () => {
  const l0 = (b: object) => progressLines({ quest: GQ, actions: GA, state: gst({ hud: { map: { v: '庫塔伊洞窟地下一樓', id: 60049 }, buffs: b } }), now: gnow }, NAMES)[0]!.text
  expect(l0({ v: ['exp'], ts: 1 })).toBe('練功中：地雷區（快速戰鬥）＋EXP×2')
  expect(l0({ v: ['exp'], ts: 1, stale: true })).toBe('練功中：地雷區（快速戰鬥）＋EXP×2?')
  expect(l0({ v: ['dragon'], ts: 1 })).toBe('練功中：地雷區（快速戰鬥）')
})
