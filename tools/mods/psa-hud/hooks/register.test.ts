import { expect, test } from 'claude-code/testing'

import {
  Supervisor, backoffMs, decideExit, errEntries, errLine, format, logPathFromCwd, parseState, stallThresholdMs, statPathFromCwd,
  viewModel, watchAlive, watchPathFromCwd, hudText, nameText, encText, levelText, paneTree,
} from './register'
import type { PaneEls, SupDeps, ViewIn } from './register'

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
  expect(hudText(unk, 0, 0)).toBe('?  0轉77級  HP 208  MP 45  |  寵 0轉77級 HP 434  |  奇努伊的海底通路 31401:91,29')   // 寵物名 ? 不顯示（雜訊）
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

test('titleFromLog：[rebirth] 行（取最後一筆 questrun / rebirth）', () => {
  const q = '2026-10-12 20:00:00 [questrun] 結束 rc=0，完成 [3003]\n'
  const st = '2026-10-12 21:43:28 [rebirth] 開始：轉到第 2 轉（漆黑洞窟(二轉)），從階段 enter，選項 {}\n2026-10-12 21:43:52 [rebirth] 階段 enter 結束 rc=0\n'
  expect(titleFromLog(q + st, NAMES)).toBe('PSA｜漆黑洞窟(二轉) 進行中')
  const run = st + '2026-10-12 21:49:37 [rebirth] 階段 boss10 開始（漆黑洞窟(二轉)）\n'
  expect(titleFromLog(q + run, NAMES)).toBe('PSA｜漆黑洞窟(二轉) boss10 進行中')
  const fail = run + '2026-10-12 21:49:22 [rebirth] 失敗 rc=84：boss10：x\n2026-10-12 21:49:22 [rebirth] 結束 rc=84；續跑：--from boss10 --trans 2\n'
  expect(titleFromLog(fail, NAMES)).toBe('PSA｜漆黑洞窟(二轉) 失敗 rc=84')
  expect(titleFromLog(fail + '22:00:00 [manual] x\n', NAMES)).toBe('PSA｜漆黑洞窟(二轉) 接手中（rebirth rc=84）')
  expect(titleFromLog(run + '[rebirth] 結束 rc=0\n', NAMES)).toBe('PSA｜漆黑洞窟(二轉) 已完成')
  // 較新的 questrun 蓋過舊 rebirth
  expect(titleFromLog(fail + '[questrun] 開始：任務 [3003]\n', NAMES)).toBe('PSA｜猜謎三兄弟 進行中')
  expect(cleanEvent('2026-10-12 21:49:37 [rebirth] 階段 boss10 開始')).toBe('21:49:37 階段 boss10 開始')
})

test('grindActivity：[rebirth] 比遇敵開新 → 任務中', () => {
  const n = new Date(2026, 9, 12, 22, 0, 0).getTime()
  const acts = '21:50:00 grind 原地遇敵：開\n'
  expect(grindActivity({ quest: '2026-10-12 21:40:00 [rebirth] 結束 rc=0\n', actions: acts, state: null, now: n })).toEqual({ spot: '原地', quick: false })
  expect(grindActivity({ quest: '2026-10-12 21:55:00 [rebirth] 階段 boss10 開始（x）\n', actions: acts, state: null, now: n })).toBeUndefined()
})

test('titleFromLog：不跨 run 抓名字；rc≠0 後有別的事件 → 接手中', () => {
  const prev = '14:00:00 [questrun] 開始：任務 [2002]\n14:01:00 [questrun] 任務 2002「碧青洞窟」詳情結果：ok\n14:02:00 [questrun] 結束 rc=0，完成 [2002]\n'
  const cur = '14:36:09 [questrun] 開始：任務 [3003]，選項 {}\n14:36:30 [questrun] 追蹤 x\n14:37:07 [questrun] 結束 rc=111，完成 []；失敗退出，不恢復掛機\n'
  expect(titleFromLog(prev + cur, NAMES)).toBe('PSA｜猜謎三兄弟 失敗 rc=111')
  expect(titleFromLog(prev + cur + '14:37:59 [manual] 811 → 800\n[petwatch] x\n', NAMES)).toBe('PSA｜猜謎三兄弟 接手中（questrun rc=111）')
  expect(titleFromLog(prev + cur + '\n\n', NAMES)).toBe('PSA｜猜謎三兄弟 失敗 rc=111')
  // 多 ID：取本 run 內最後出現的「任務 N」
  const multi = '1 [questrun] 開始：任務 [2000, 2019]\n2 [questrun] 任務 2000「琉璃洞窟」詳情結果：ok\n3 [questrun] 任務 2019「卡坦的願望(1.82)」詳情結果：ok\n'
  expect(titleFromLog(multi, NAMES)).toBe('PSA｜卡坦的願望 進行中')
  // rc=0 後有別的事件仍是已完成
  expect(titleFromLog(prev + '[manual] x\n', NAMES)).toBe('PSA｜四大洞窟：碧青洞窟 已完成')
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
  expect(idle.length).toBe(5)                     // 警報只在段落頂端紅字（viewModel），進度區不重複
  const v = progressLines({ state: { v: 1, flags: { verify_suspect: true } } as never, now })
  expect(v.map(x => x.text)).toEqual(['任務：—', '事件：—', '動作：—'])
  expect(v.length).toBeLessThanOrEqual(6)
})

// ───────── 練功中判斷 ─────────
import { grindActivity, grindTitle, spotIds, mapStale, MAP_STALE_S } from './register'

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

// 2026-10-15 p2 實況：grind 傳送到海主人隧道後換點到五兄弟洞窟，傳送驗證讀不到座標（31706 地圖名折兩行）→ actions 沒有新的「傳送到」行，
// follow.json 記了抵達（last_switch 13:10:37）；watch 的 map 停在 13:08 的奇努伊的海底通路（等級 13:14 還在更新）
const SPY = `SPOTS = {
    '海主人隧道': (862, 656, 31401, 20, '奇努伊的海底通路'),
    '五兄弟洞窟': (703, 445, 31706, 45, '五兄弟的山寨地下６樓'),
    '地雷區': (1165, 400, 60049, 120, '庫塔伊洞窟地下一樓'),
}
HEAL_SPOTS_1920 = {
    '海主人隧道': (571, 405, 31401),      # 實測
}`
const p2now = new Date(2026, 9, 15, 13, 15, 0).getTime()
const p2s = p2now / 1000
const P2A = '12:55:20 grind 傳送到 海主人隧道 31401:91,29\n12:55:49 grind 原地遇敵：開\n13:08:23 grind 原地遇敵：關\n13:10:42 grind 原地遇敵：關\n13:11:18 grind 原地遇敵：開\n'
const P2F = JSON.stringify({ ts: p2s - 5, state: 'running', spot: '五兄弟洞窟', last_switch: p2s - 263, dry_run: false })
const P2G = JSON.stringify({ mode: 'check', rc: 0, ts: p2s - 200 })
const p2st = (map: object, hudTs = p2s - 1) => ({ v: 1, ts: p2s - 1, screen: { enc_on: true }, hud: { ts: hudTs, level: { v: '0轉51級', ts: hudTs }, map } }) as never
const OLDMAP = { v: '奇努伊的海底通路', id: 31401, ts: p2s - 417 }

test('spotIds：只讀 SPOTS 五欄表', () => {
  expect([...spotIds(SPY)]).toEqual([['海主人隧道', 31401], ['五兄弟洞窟', 31706], ['地雷區', 60049]])
})

test('mapStale：watch 標 stale，或比 hud.ts 舊 > MAP_STALE_S（舊版 watch 沒 stale 欄位）', () => {
  expect(mapStale({ ts: 100, map: { v: 'x', ts: 100 - MAP_STALE_S - 1 } })).toBe(true)
  expect(mapStale({ ts: 100, map: { v: 'x', ts: 90 } })).toBe(false)
  expect(mapStale({ ts: 100, map: { v: 'x', ts: 99, stale: true } })).toBe(true)
  expect(mapStale({ map: { v: 'x' } })).toBe(false)
  expect(mapStale(null)).toBe(false)
})

test('練功中地點：map 停在傳送前的舊值（stale）→ 用 follow.json 抵達紀錄（p2 五兄弟洞窟實況）', () => {
  const sp = spotIds(SPY)
  // 修正前：只看 actions「傳送到」+ state map → 海主人隧道
  expect(grindActivity({ actions: P2A, state: p2st(OLDMAP), now: p2now, spots: sp })!.spot).toBe('海主人隧道')
  expect(grindActivity({ actions: P2A, state: p2st(OLDMAP), now: p2now, follow: P2F, grind: P2G, spots: sp })!.spot).toBe('五兄弟洞窟')
  // 新版 watch 直接標 stale
  expect(grindActivity({ actions: P2A, state: p2st({ ...OLDMAP, stale: true }), now: p2now, follow: P2F, spots: sp })!.spot).toBe('五兄弟洞窟')
  // 不同視窗的 progressLines 走同一條路
  expect(progressLines({ actions: P2A, state: p2st(OLDMAP), now: p2now, follow: P2F, spots: sp }, NAMES, 1)[0]!.text).toBe('練功中：五兄弟洞窟')
  // grind.json start rc=0 也是抵達紀錄（沒有 follow 時）
  const g0 = JSON.stringify({ mode: 'start', rc: 0, spot: '五兄弟洞窟', ts: p2s - 250 })
  expect(grindActivity({ actions: P2A, state: p2st(OLDMAP), now: p2now, grind: g0, spots: sp })!.spot).toBe('五兄弟洞窟')
  // grind.json 傳送失敗（rc≠0）不算抵達
  const g51 = JSON.stringify({ mode: 'start', rc: 51, spot: '五兄弟洞窟', ts: p2s - 250 })
  expect(grindActivity({ actions: P2A, state: p2st(OLDMAP), now: p2now, grind: g51, spots: sp })!.spot).toBe('海主人隧道')
  // 壞檔 / dry-run 的 follow.json 略過
  expect(grindActivity({ actions: P2A, state: p2st(OLDMAP), now: p2now, follow: '{壞', spots: sp })!.spot).toBe('海主人隧道')
  expect(grindActivity({ actions: P2A, state: p2st(OLDMAP), now: p2now, follow: P2F.replace('"dry_run":false', '"dry_run":true'), spots: sp })!.spot).toBe('海主人隧道')
})

test('練功中地點：map 是新的 → 以 map 為準；舊值又沒有抵達紀錄 → 加 ?', () => {
  const sp = spotIds(SPY)
  // watch 讀到五兄弟（新）→ 五兄弟洞窟，即使 actions 最後傳送是海主人隧道
  expect(grindActivity({ actions: P2A, state: p2st({ v: '五兄弟的山寨地下６樓', id: 31706, ts: p2s - 2 }), now: p2now, spots: sp })!.spot).toBe('五兄弟洞窟')
  // 抵達紀錄比 map 新（剛傳送完、watch 還沒讀到新地圖）→ 抵達紀錄
  const fNew = JSON.stringify({ spot: '五兄弟洞窟', last_switch: p2s - 3, dry_run: false })
  expect(grindActivity({ actions: P2A, state: p2st({ ...OLDMAP, ts: p2s - 10 }), now: p2now, follow: fNew, spots: sp })!.spot).toBe('五兄弟洞窟')
  // map 新且不是任何練功點、比抵達紀錄新 → 已離開（不算練功中）
  expect(grindActivity({ actions: P2A, state: p2st({ v: '薩姆吉爾村', id: 1000, ts: p2s - 2 }), now: p2now, follow: P2F, spots: sp })).toBeUndefined()
  // 沒有任何抵達紀錄 + map stale → 舊地名加 ?
  const enc = '13:11:18 grind 原地遇敵：開\n'
  expect(grindActivity({ actions: enc, state: p2st(OLDMAP), now: p2now, spots: sp })!.spot).toBe('奇努伊的海底通路?')
  expect(grindActivity({ actions: enc, state: p2st({ ...OLDMAP, ts: p2s - 5 }), now: p2now, spots: sp })!.spot).toBe('海主人隧道')
})

test('hudText：map stale → 地名 / 座標加 ?', () => {
  const h = { ...HUD, ts: 1000, map: { ...HUD.map, ts: 1000 - MAP_STALE_S - 5 } }
  expect(hudText({ v: 1, hud: h }, 0, 0)).toBe('0轉77級  HP 208  MP 45  |  寵 0轉77級 HP 434  |  奇努伊的海底通路? 31401:91,29?')
  expect(hudText({ v: 1, hud: { ...HUD, map: { ...HUD.map, stale: true } } }, 0, 0)).toBe('0轉77級  HP 208  MP 45  |  寵 0轉77級 HP 434  |  奇努伊的海底通路? 31401:91,29?')
})

test('練功中：快速戰鬥紀錄在 600 行之前也認得；任一人最後是關就不標', () => {
  const filler = Array.from({ length: 700 }, () => '15:00:00 click 1,1\n').join('')
  const a = GA.split('\n').slice(0, 3).join('\n') + '\n' + filler + '15:44:30 depot_use 原地遇敵：開\n'
  expect(grindActivity({ quest: GQ, actions: a, state: gst(), now: gnow })!.quick).toBe(true)
  expect(grindActivity({ quest: GQ, actions: a + '15:44:40 grind ass：DKBO3 快速戰鬥 → 關\n', state: gst(), now: gnow })!.quick).toBe(false)
})

// ───────── buff 剩餘時間（bufftime.json 倒數）─────────
import { buffLine, hm, parseBuffTimes } from './register'

test('buffLine：有到期時間 → 剩 H:MM；圖示有但沒時間 / 已過期 → ? + 指令；都沒有 → 不顯示', () => {
  const now = 1_000_000_000
  const T = (k: string, left: number) => ({ [k]: { expires_ts: now / 1000 + left, read_ts: now / 1000 - 60 } })
  expect(hm(83 * 60 + 59)).toBe('1:23')
  expect(hm(59)).toBe('0:00')
  expect(hm(86400 + 3600 * 2 + 5 * 60)).toBe('1天2:05')
  expect(buffLine({ v: ['exp'] }, T('exp', 83 * 60 + 30), now)).toEqual({ text: '智慧果 剩 1:23', warn: false })
  expect(buffLine({ v: ['exp'] }, {}, now)).toEqual({ text: '智慧果 ?（bufftime.py read）', warn: true })
  expect(buffLine({ v: ['exp'] }, T('exp', -5), now)).toEqual({ text: '智慧果 ?（bufftime.py read）', warn: true })     // 過期 = 沒讀過
  expect(buffLine({ v: [] }, T('exp', -5), now)).toBeUndefined()                                                        // 過期且圖示沒了
  expect(buffLine({ v: [] }, {}, now)).toBeUndefined()
  expect(buffLine({ v: [] }, T('exp', 600), now)?.text).toBe('智慧果 剩 0:10?')                                         // 圖示確定沒有 → 加 ?
  expect(buffLine({ v: [], stale: true }, T('exp', 600), now)?.text).toBe('智慧果 剩 0:10')                              // 圖示是舊值：不下結論
  expect(buffLine(undefined, T('exp', 600), now)?.text).toBe('智慧果 剩 0:10')                                          // watch 不在：只看快取
  expect(buffLine({ v: ['exp', 'dragon'] }, { ...T('exp', 3600), ...T('dragon', 1800) }, now)?.text).toBe('智慧果 剩 1:00 · 龍王 剩 0:30')
  expect(buffLine({ v: ['dragon'] }, T('dragon', 2700), now)?.text).toBe('龍王 剩 0:45')                                // 只有龍王
  expect(buffLine({ v: ['dragon'] }, {}, now)).toEqual({ text: '龍王 ?（bufftime.py read）', warn: true })           // 龍王沒時間
  expect(buffLine({ v: ['exp', 'dragon'] }, T('exp', 3600), now)).toEqual({ text: '智慧果 剩 1:00 · 龍王 ?（bufftime.py read）', warn: true })
  expect(parseBuffTimes(undefined)).toEqual({})
  expect(parseBuffTimes('壞')).toEqual({})
  expect(parseBuffTimes('{"v":1,"buffs":{"exp":{"expires_ts":5}}}')).toEqual({ exp: { expires_ts: 5 } })
})

test('hudText 不再帶 buff（buff 改在 pane 的遇敵 / buff 行）；練功中那行也不重複', () => {
  const st = { v: 1, hud: { ...HUD, buffs: { v: ['exp'], ts: 1 } }, screen: { state: 'idle' } }
  expect(hudText(st, 0, 0)).toBe('0轉77級  HP 208  MP 45  |  寵 0轉77級 HP 434  |  奇努伊的海底通路 31401:91,29')
  const l0 = (b: object) => progressLines({ quest: GQ, actions: GA, state: gst({ hud: { map: { v: '庫塔伊洞窟地下一樓', id: 60049 }, buffs: b } }), now: gnow }, NAMES)[0]!.text
  expect(l0({ v: ['exp'], ts: 1 })).toBe('練功中：地雷區（快速戰鬥）')
})

test('encText：遇敵狀態；null 沿用最後值加 ?；有龍王也不加括號說明', () => {
  const b = (k: string[]) => ({ v: k, ts: 1 })
  expect(encText({ v: 1, screen: { enc_on: true } } as never)).toEqual({ text: '遇敵中', warn: false, val: true })
  expect(encText({ v: 1, screen: { enc_on: false } } as never)).toEqual({ text: '不遇敵', warn: true, val: false })
  expect(encText({ v: 1, screen: { enc_on: null } } as never, false)).toEqual({ text: '不遇敵 ?', warn: true, val: false })
  expect(encText({ v: 1, screen: { enc_on: null } } as never, true)?.text).toBe('遇敵中 ?')
  expect(encText({ v: 1, screen: {} } as never)).toBeUndefined()
  expect(encText({ v: 1, screen: { enc_on: true }, hud: { buffs: b(['dragon']) } } as never)?.text).toBe('遇敵中')
  expect(encText({ v: 1, screen: { enc_on: false }, hud: { buffs: b(['dragon']) } } as never)?.text).toBe('不遇敵')
})

// ───────────── pane 空白（2026-10-13）：jsxFactory h 被 hints.map(h => …) 蓋掉；熱重載後 session.start 沒重發 ─────────────
const ROOT = '/mnt/c/games/PrimalSA-AI'
const PANE_SITE = { component: 'Pane' as const, requestId: 'psa-hud', props: { title: '精靈王石器', isFocused: false, bodyColumns: 60, placement: 'dock' as const, scroll: { offset: 0, bodyRows: 40 }, view: {} } }
const NOW_S = 1791848148
// 實際發生時的 state.json 形狀：verify_suspect + 2 筆 alerts → 狀態行一定有提示行（hints 非空）
const STATE_ALERT = JSON.stringify({
  v: 1, seq: 7, phase: 'run', ts: NOW_S, watcher: { token: 't1', running: true, interval: 0.5 },
  screen: { label: '戰鬥中（完整・演出中）', age_s: 0.5, state: 'battle', annot: [], enc_on: null },
  hud: { stale: true, age_s: 3, level: { v: '2轉125級' }, hp: { v: 475 }, mp: { v: 90 }, pet: { level: { v: 'o級' }, hp: { v: 909 }, name: { v: '?' } }, map: { v: '柯奧的民家', id: 1112 }, pos: { v: [15, 15] }, name: { v: 'DKBO' } },
  flags: { verify_suspect: true }, alerts: [{ msg: '警告：連續 3 次遇到不認得的畫面' }, { msg: '警告：第二筆' }],
})

// 模擬「熱重載後」：測試只接 command.run，不送 session.start
type TestOn = Parameters<Extract<Parameters<typeof test>[1], (...a: never[]) => unknown>>[1]
function fakeHost(on: TestOn, files: Record<string, string>, log: string[]) {
  on('session.cwd', () => ({ value: ROOT }))
  on('clock.now', () => ({ value: NOW_S * 1000 }))
  on('clock.every', () => ({ value: undefined }) as never)
  on('clock.sleep', () => ({ value: undefined }) as never)
  on('ui.status', () => ({ value: undefined }) as never)
  on('ui.open', () => { log.push('open'); return { value: { isPlaced: true } } })
  on('ui.close', () => { log.push('close'); return { value: undefined } as never })
  on('fs.read', (_$, e) => {
    const p = String((e as { path: string }).path).replace(`${ROOT}/`, '')
    if (p in files) return { value: files[p]! }
    throw new Error(`ENOENT ${p}`)
  })
  on('fs.write', () => ({ value: undefined }) as never)
  on('process.run', () => ({ value: { exitCode: 1, stdout: '', stderr: 'x', isStdoutTruncated: false, isStderrTruncated: false } }))
  // watch 子程序：立刻以退出碼 3（已有 watch 在跑）結束 → 只讀
  on('process.spawn', async function* () { return { value: { code: 3 } } as never })
}

for (const surface of ['terminal', 'desktop'] as const) {
  test(`熱重載後沒有 session.start：/psa-hud on 補初始化、pane 畫出提示行不空白（${surface}）`, async ($, on) => {
    const log: string[] = []
    fakeHost(on, { 'tools/.cache/state.json': STATE_ALERT, 'tools/.cache/psa-hud.json': '{"watch":true}' }, log)
    const { text } = await $.command.run({ command: 'psa-hud', args: 'on' } as never)
    expect(log).toContain('open')
    expect(text).toContain('監看：')                        // sup 已由 lazy init 建立
    const ui = await $.ui.mount({ plugin: 'psa-hud', surface, ...PANE_SITE } as never)
    const tree = await ui.drawn()
    expect(tree).toMatchObject({ type: 'Box' })
    expect(await ui.find({ type: 'Text', text: /疑似答題/ })).toBeDefined()
    expect(await ui.find({ type: 'Text', text: /2轉125級/ })).toBeDefined()
    expect(await ui.find({ type: 'Text', text: /寵物 +│ \?級 +HP 909/ })).toBeDefined()   // 'o級' 不顯示怪字、寵物名 ? 不顯示
    await ui.unmount()
  })

  test(`pane 什麼都還沒讀到也照畫（${surface}）`, async ($, on) => {
    on('clock.now', () => ({ value: 0 }))
    const ui = await $.ui.mount({ plugin: 'psa-hud', surface, ...PANE_SITE } as never)
    expect(await ui.find({ type: 'Text', text: /沒有狀態/ })).toBeDefined()
    expect(await ui.find({ type: 'Text', text: /還沒有錯誤紀錄/ })).toBeDefined()
    await ui.unmount()
  })
}

test('paneTree：hints 非空不拋（jsxFactory h 不可被參數蓋掉）；欄位 undefined / 壞形狀也不拋', () => {
  const els = { Box: (p: unknown) => ({ type: 'Box', p }), Text: (p: unknown) => ({ type: 'Text', p }) } as unknown as PaneEls
  expect(() => paneTree(els, { wl: { main: 'x', hints: [{ text: '疑似答題', tone: 'red' }] } })).not.toThrow()
  expect(() => paneTree(els, {})).not.toThrow()
  expect(() => paneTree(els, { wl: { main: 'x', hints: undefined } as never, pg: undefined, lines: null, en: null, st: null, ht: undefined })).not.toThrow()
  expect(() => paneTree(els, { lines: [{ id: 1, ts: 0, error: 'e', fix: null, source: null }], pg: [{ text: 'p', tone: 'red' }] })).not.toThrow()
})

test('/psa-hud off 只關 pane（不碰監看）；on 重開', async ($, on) => {
  const log: string[] = []
  fakeHost(on, { 'tools/.cache/state.json': STATE_ALERT }, log)
  const off = await $.command.run({ command: 'psa-hud', args: 'off' } as never)
  expect(log).toEqual(['close'])
  expect(off.text).toContain('已關閉')
  await $.command.run({ command: 'psa-hud', args: 'on' } as never)
  expect(log).toEqual(['close', 'open'])
})

test('levelText / format：等級沒有數字（OCR 讀成 o級）顯示 ?級', () => {
  expect(levelText('o級')).toBe('?級')
  expect(levelText('2轉125級')).toBe('2轉125級')
  expect(levelText('abc')).toBe('?')
  expect(levelText(undefined)).toBeUndefined()
  expect(format({ ok: true, level: '2轉125級', hp: 475, mp: 90, petLevel: 'o級', petHp: 909, petName: '?' })).toBe('2轉125級  HP 475  MP 90  |  寵 ?級 HP 909')
})

// ───────────── 多視窗（第 3d 步）：共用情境 ─────────────
const p2 = (n: number) => String(n).padStart(2, '0')
const HMS = (ms: number) => { const d = new Date(ms); return `${p2(d.getHours())}:${p2(d.getMinutes())}:${p2(d.getSeconds())}` }
const T0 = NOW_S * 1000
// 單視窗情境的檔案（沒有任何 [程序名] 標籤的行 → 新舊版本畫面必須逐字相同）
const SINGLE_FILES: Record<string, string> = {
  'tools/.cache/state.json': STATE_ALERT,
  'tools/.cache/psa-hud.json': '{"watch":true}',
  'notes/quest-events.log': '2026-10-15 10:00:00 [questrun] 開始：任務 [2000]，選項 {}\n2026-10-15 10:00:05 [questrun] 任務 2000「琉璃洞窟」詳情結果：accepted\n',
  'tools/.cache/actions.log': `${HMS(T0 - 50000)} grind 傳送到 地雷區 60049:30,25\n${HMS(T0 - 5000)} click 120,80\n`,
  'tools/.cache/errlog.jsonl': JSON.stringify({ id: 3, ts: T0 - 60000, error: '主視窗錯誤', fix: null, source: 'quest' }) + '\n',
}
type ScOpts = { running?: string; files?: Record<string, string> }
// 假 host：clients.py running → opts.running（undefined = 查詢失敗）；uv python find → Linux 直譯器；stat.ps1 → 失敗；
// watch 子程序記下 env 後以退出碼 3 結束（只讀）
function scenarioHost(on: TestOn, o: ScOpts) {
  const log = { spawnEnv: [] as Record<string, string>[], runs: [] as { argv: string[]; env?: Record<string, string> }[] }
  const files = o.files ?? SINGLE_FILES
  on('session.cwd', () => ({ value: ROOT }))
  on('clock.now', () => ({ value: T0 }))
  on('clock.every', () => ({ value: undefined }) as never)
  on('clock.sleep', () => ({ value: undefined }) as never)
  on('ui.status', () => ({ value: undefined }) as never)
  on('ui.open', () => ({ value: { isPlaced: true } }))
  on('ui.close', () => ({ value: undefined }) as never)
  on('fs.read', (_$, e) => {
    const p = String((e as { path: string }).path).replace(`${ROOT}/`, '')
    if (p in files) return { value: files[p]! }
    throw new Error(`ENOENT ${p}`)
  })
  on('fs.write', () => ({ value: undefined }) as never)
  on('process.run', (_$, e) => {
    const argv = [...(e as { argv: string[] }).argv]
    log.runs.push({ argv, env: (e as { init?: { env?: Record<string, string> } }).init?.env })
    const r = (code: number, stdout: string) => ({ value: { exitCode: code, stdout, stderr: '', isStdoutTruncated: false, isStderrTruncated: false } })
    if (argv[0] === 'uv' && argv[1] === 'python') return r(0, '/usr/bin/python3\n')
    if (argv.some(a => a.endsWith('clients.py'))) return o.running === undefined ? r(1, '') : r(0, o.running)
    return r(1, '')
  })
  on('process.spawn', async function* (_$, e) {
    log.spawnEnv.push({ ...((e as { env?: Record<string, string> }).env ?? {}) })
    return { value: { code: 3 } } as never
  })
  return log
}
const flush = async () => { for (let i = 0; i < 5000; i++) await Promise.resolve() }
async function paneTexts($: Parameters<Extract<Parameters<typeof test>[1], (...a: never[]) => unknown>>[0]): Promise<string[]> {
  const ui = await $.ui.mount({ plugin: 'psa-hud', surface: 'terminal', ...PANE_SITE } as never)
  const t = (await ui.findAll({ type: 'Text' })).map(x => String(x.text ?? ''))
  await ui.unmount()
  return t
}

import {
  MAIN_CLIENT, actionsFor, bannerLines, haltFor, haltLines, haltOwner, clientEnv, diffClients, hudCfgFromCwd, isMainClient, parseRunning, pickTargets,
  questLogFromCwd, stateFileFromCwd, verifyHaltFromCwd, winSuffix,
} from './register'

const YMD = (ms: number) => { const d = new Date(ms); return `${d.getFullYear()}-${p2(d.getMonth() + 1)}-${p2(d.getDate())}` }
const STAMP = (ms: number) => { const d = new Date(ms); return `${p2(d.getMonth() + 1)}/${p2(d.getDate())} ${p2(d.getHours())}:${p2(d.getMinutes())}` }
// 表格列 / 表頭 helper（寬度 = PANE_SITE.bodyColumns 60；中文算 2）
const PW = 60
const padTo = (t: string, w: number) => t + ' '.repeat(Math.max(0, w - dispW(t)))
const R = (label: string, content: string) => `│ ${padTo(label, 4)} │ ${padTo(content, PW - 11)} │`
const HD = (title: string) => { const t = ` ${title} `; return `┌${t}${'─'.repeat(PW - 2 - dispW(t))}┐` }
const BOT = `└${'─'.repeat(6)}┴${'─'.repeat(PW - 9)}┘`
// 單視窗情境的 pane 文字（2026-10-15 表格 UI：表頭 → ！警示列 → 人物 / 寵物 / 地圖 → 狀態 / 事件 / 動作；次要提示在表格下方灰字）
const SINGLE_TEXTS = () => [
  HD('PrimalSA · 戰鬥中（完整・演出中）'), R('！', '疑似答題 / 驗證視窗，請人工處理'), R('！', '警告：連續 3 次遇到不認得的畫面'), R('！', '警告：第二筆'),
  R('人物', `DKBO 2轉125級 HP 475 / MP 90 （戰鬥前 · 3s 前）`), R('寵物', `${padTo('?級', 22)}HP 909`), R('地圖', '柯奧的民家 15,15'),
  R('狀態', '任務：四大洞窟：琉璃洞窟 進行中'), R('事件', '10:00 開始：任務 [2000]，選項 {}'), R('', '10:00 任務 2000「琉璃洞窟」詳情結果：accepted'),
  R('動作', `${HMS(T0 - 5000).slice(0, 5)} click 120,80（5 秒前）`), BOT,
  '已有 watch 在跑（不是這個 HUD 啟動的），只讀', '',
]
// 下方錯誤紀錄表：表頭 + 一筆（當天只顯示時:分）
const CELL = (x: string) => x.replace(/^│[^│]*│ /, '').replace(/ │$/, '').trim()
const SINGLE_ERR = (t: string[]) => {
  const e = t.slice(SINGLE_TEXTS().length)
  expect(e.length).toBe(5)
  expect(e[0]).toMatch(/^┌─+┬─+┬─+┬─+┬─+┐$/)
  expect(e[1]).toMatch(/^│ 時間 +│ 次數 +│ 來源 +│ 內容 +│ 狀態 +│$/)
  expect(e[3]).toMatch(new RegExp(`^│ ${STAMP(T0 - 60000).slice(6)} +│ ×1 +│ quest +│ 主視窗錯誤 +│ 待改進 │$`))
}
const RO3 = '監看：已有 watch 在跑（只讀）｜spawn 2 次｜卡住重開 0 次｜最後退出碼 3'

// clients.py running --rostered 只列 ROSTERS 有登錄的（PrimalSA3 沒名單 → 不出現，Python 端已濾）；查不到（undefined）= 維持單視窗
for (const running of ['PrimalSA\n', '', 'PrimalSA\r\n', undefined]) {
  test(`單視窗（running=${JSON.stringify(running)}）：pane / 指令 / watch spawn 與改版前逐字相同`, async ($, on) => {
    const log = scenarioHost(on, { running })
    const a = await $.command.run({ command: 'psa-hud', args: 'on' } as never)
    await flush()
    const b = await $.command.run({ command: 'psa-hud', args: 'watch status' } as never)
    await flush()
    const d = await $.command.run({ command: 'psa-hud', args: 'watch bogus' } as never)
    expect(a.text).toBe('上一次讀取還在進行中\n監看：執行中｜spawn 0 次｜卡住重開 0 次｜最後退出碼 無')
    expect(b.text).toBe(RO3)
    expect(d.text).toBe('用法：/psa-hud watch on|off|status')
    const pt = await paneTexts($)
    expect(pt.slice(0, SINGLE_TEXTS().length)).toEqual(SINGLE_TEXTS())
    SINGLE_ERR(pt)
    expect(log.spawnEnv).toEqual([{ PSA_WATCH_OWNER: 'hud', PYTHONIOENCODING: 'utf-8' }, { PSA_WATCH_OWNER: 'hud', PYTHONIOENCODING: 'utf-8' }])
    expect(log.runs.some(r => r.argv.some(x => x.endsWith('clients.py')))).toBe(true)          // 有偵測（背景、不在繪製時）
    expect(log.runs.filter(r => r.argv.includes('--stop')).length).toBe(0)
  })
}

// 多視窗情境：PrimalSA2 有自己的 state / 事件 log；actions.log 共用、帶 [PrimalSA2] 標籤；errlog 有 client 欄
const ST2 = JSON.stringify({
  v: 1, seq: 3, phase: 'run', ts: NOW_S, watcher: { token: 't2', running: true, interval: 0.5 },
  screen: { label: '主畫面', age_s: 0.2, state: 'idle', annot: [], enc_on: true },
  hud: { stale: false, age_s: 0.2, level: { v: '1轉60級' }, hp: { v: 300 }, mp: { v: 50 }, name: { v: 'DKBO6' }, map: { v: '庫塔伊洞窟地下一樓', id: 60049 }, pos: { v: [30, 25] }, buffs: { v: ['exp'] } },
  flags: {}, alerts: [],
})
const MULTI_FILES: Record<string, string> = {
  ...SINGLE_FILES,
  'tools/.cache/clients/PrimalSA2/state.json': ST2,
  'tools/.cache/clients/PrimalSA2/psa-hud.json': '{"watch":true}',
  'notes/clients/PrimalSA2/quest-events.log': `${YMD(T0 - 3600000)} ${HMS(T0 - 3600000)} [questrun] 結束 rc=0，完成 [3003]\n`,
  'tools/.cache/actions.log': SINGLE_FILES['tools/.cache/actions.log']! +
    `${HMS(T0 - 40000)} [PrimalSA2] grind 傳送到 地雷區 60049:30,25\n${HMS(T0 - 30000)} [PrimalSA2] grind ass：DKBO6 快速戰鬥 → 開（已確認）\n${HMS(T0 - 20000)} [PrimalSA2] depot_use 原地遇敵：開\n${HMS(T0 - 2000)} [PrimalSA2] click 9,9\n`,
  'tools/.cache/errlog.jsonl': SINGLE_FILES['tools/.cache/errlog.jsonl']! + JSON.stringify({ id: 4, ts: T0 - 30000, error: '二號錯誤', fix: null, source: 'grind', client: 'PrimalSA2' }) + '\n',
}

test('多視窗：偵測到 PrimalSA2 → 第二支 watch 帶 PSA_CLIENT；pane 每視窗一段、練功中 / 遇敵 / buff 分開、警示醒目、errlog 有 client', async ($, on) => {
  const log = scenarioHost(on, { running: 'PrimalSA\nPrimalSA2\n', files: MULTI_FILES })
  await $.command.run({ command: 'psa-hud', args: 'on' } as never)
  await flush()
  const st = await $.command.run({ command: 'psa-hud', args: 'watch status' } as never)
  await flush()
  expect(log.spawnEnv.filter(e => !e.PSA_CLIENT).length).toBe(2)                  // 主視窗 env 不變（不帶 PSA_CLIENT）
  expect(log.spawnEnv.filter(e => e.PSA_CLIENT === 'PrimalSA2')).toEqual([
    { PSA_WATCH_OWNER: 'hud', PYTHONIOENCODING: 'utf-8', PSA_CLIENT: 'PrimalSA2' }, { PSA_WATCH_OWNER: 'hud', PYTHONIOENCODING: 'utf-8', PSA_CLIENT: 'PrimalSA2' },
  ])
  expect(st.text).toBe(`[PrimalSA] ${RO3}\n[PrimalSA2] ${RO3}`)
  const t = await paneTexts($)
  // 各自視窗停手（2026-10-15）：verify_suspect 紅字放在自己那張表的「！」列，不在最上面、不寫「全部視窗停手」
  expect(t[0]!.startsWith('┌ p1 PrimalSA · 戰鬥中（完整・演出中）')).toBe(true)
  expect(t[1]).toBe(R('！', '疑似答題 / 驗證視窗，請人工處理（只停這個視窗）'))
  expect(t.filter(x => x.includes('疑似答題')).length).toBe(1)                       // 同一件事只寫一次（不再三處重複）
  expect(t.some(x => x.includes('全部視窗停手'))).toBe(false)
  const i2 = t.findIndex(x => x.startsWith('┌ p2 PrimalSA2 · 主畫面'))
  expect(i2).toBeGreaterThan(0)
  const t2 = t.slice(i2)                                                              // PrimalSA2 那張表之後
  expect(t2[1]).toBe(R('人物', `${padTo('DKBO6 1轉60級', 22)}HP 300 / MP 50`))
  expect(t2[2]).toBe(R('寵物', '—'))
  expect(t2[3]).toBe(R('地圖', '庫塔伊洞窟地下一樓 30,25  遇敵中'))   // 去掉地圖編號、遇敵放地圖列右邊
  expect(t2[4]).toBe(R('Buff', '智慧果 ?（bufftime.py read）'))                      // 有 exp 圖示、沒有 bufftime.json
  expect(t2[5]).toBe(R('狀態', '練功中：地雷區（快速戰鬥）'))
  expect(t2.some(x => x.includes('任務：四大洞窟'))).toBe(false)
  expect(t.slice(0, i2).join('\n')).toContain('任務：四大洞窟：琉璃洞窟 進行中')       // 主視窗那張表
  expect(t).toContain(R('動作', `${HMS(T0 - 5000).slice(0, 5)} click 120,80（5 秒前）`))   // 主視窗最後動作 = 沒標籤的行
  expect(t).toContain(R('動作', `${HMS(T0 - 2000).slice(0, 5)} click 9,9（2 秒前）`))      // PrimalSA2 最後動作（標籤去掉）
  expect(t.some(x => /^│ \d\d:\d\d +│ ×1 +│ p2 grind +│ 二號錯誤 +│ 待改進 │$/.test(x))).toBe(true)
  expect(t.some(x => /^│ \d\d:\d\d +│ ×1 +│ quest +│ 主視窗錯誤 +│ 待改進 │$/.test(x))).toBe(true)
  // 指令：只關 PrimalSA2 的監看 → 只有它送 --stop（帶 PSA_CLIENT）
  const off = await $.command.run({ command: 'psa-hud', args: 'watch off PrimalSA2' } as never)
  expect(String(off.text).startsWith('[PrimalSA2] 監看：已關閉')).toBe(true)
  expect(off.text).not.toContain('[PrimalSA] ')
  const stops = log.runs.filter(r => r.argv.includes('--stop'))
  expect(stops.length).toBe(1)
  expect(stops[0]!.env?.PSA_CLIENT).toBe('PrimalSA2')
  expect((await $.command.run({ command: 'psa-hud', args: 'watch on PrimalSA9' } as never)).text).toContain('找不到視窗 PrimalSA9')
  expect((await $.command.run({ command: 'psa-hud', args: 'watch bogus' } as never)).text).toBe('用法：/psa-hud watch on|off|status [程序名|all]')
  // ack（不給 = 全部）：兩個視窗各送一次，PrimalSA2 帶 PSA_CLIENT
  const ack = await $.command.run({ command: 'psa-hud', args: 'ack' } as never)
  expect(String(ack.text).split('\n').length).toBe(2)
  const acks = log.runs.filter(r => r.argv.includes('--ack'))
  expect(acks.map(r => r.env?.PSA_CLIENT ?? '')).toEqual(['', 'PrimalSA2'])
})

test('verify-halt.json 存在：單視窗也在最上面紅字警示（沒有檔案時畫面不變）', async ($, on) => {
  scenarioHost(on, { running: 'PrimalSA\n', files: { ...SINGLE_FILES, 'tools/.cache/verify-halt.json': JSON.stringify({ ts: NOW_S - 60, client: 'PrimalSA', src: 'uikit', reason: '連 3 次不認得' }) } })
  await $.command.run({ command: 'psa-hud', args: 'on' } as never)
  await flush()
  await $.command.run({ command: 'psa-hud', args: 'watch status' } as never)
  const t = await paneTexts($)
  expect(t[0]).toBe(HD('PrimalSA · 戰鬥中（完整・演出中）'))
  const msg = t.slice(1, 5).map(CELL).join(' ').replace(/\s+/g, ' ')                 // 折行但訊息與指令完整
  expect(msg).toBe(`PrimalSA 停手：驗證旗標 ${STAMP((NOW_S - 60) * 1000)} uikit：連 3 次不認得 畫面恢復 5 秒自動清；手動：uv run --no-project python tools/gui/verifyhalt.py clear PrimalSA`)
  expect(t.slice(1, 5).every(x => x.startsWith('│ ！') || x.startsWith('│      │'))).toBe(true)
})

test('舊共用旗標（client=PrimalSA2）+ 只有主視窗：主視窗不紅，只一行黃字提示怎麼清', async ($, on) => {
  scenarioHost(on, { running: 'PrimalSA\n', files: { ...SINGLE_FILES, 'tools/.cache/verify-halt.json': JSON.stringify({ ts: NOW_S - 60, client: 'PrimalSA2', src: 'watch', reason: '舊' }) } })
  await $.command.run({ command: 'psa-hud', args: 'on' } as never)
  await flush()
  await $.command.run({ command: 'psa-hud', args: 'watch status' } as never)
  const t = await paneTexts($)
  expect(t[1]!.startsWith('│ ！   │ 舊共用驗證旗標屬 PrimalSA2')).toBe(true)
  expect(t.slice(1, 5).join(' ').replace(/[│\s]+/g, ' ')).toContain('uv run --no-project python tools/gui/verifyhalt.py clear PrimalSA2')
  expect(t.filter(x => x.includes('停手')).length).toBe(0)                            // 主視窗不紅
})

test('多視窗：PrimalSA2 自己的 verify-halt.json → 只在 PrimalSA2 段落紅字，主視窗段落沒有停手字', async ($, on) => {
  scenarioHost(on, { running: 'PrimalSA\nPrimalSA2\n', files: { ...MULTI_FILES, 'tools/.cache/clients/PrimalSA2/verify-halt.json': JSON.stringify({ ts: NOW_S - 60, client: 'PrimalSA2', src: 'watch', reason: '不認得 10 秒' }) } })
  await $.command.run({ command: 'psa-hud', args: 'on' } as never)
  await flush()
  await $.command.run({ command: 'psa-hud', args: 'watch status' } as never)
  await flush()
  const t = await paneTexts($)
  const i2 = t.findIndex(x => x.startsWith('┌ p2 PrimalSA2'))
  expect(i2).toBeGreaterThan(0)
  expect(t.slice(i2 + 1, i2 + 4).map(CELL).join(' ').replace(/\s+/g, ' ')).toBe(`停手：驗證旗標 ${STAMP((NOW_S - 60) * 1000)} watch：不認得 10 秒 畫面恢復 5 秒自動清；手動：uv run --no-project python tools/gui/verifyhalt.py clear PrimalSA2`)
  expect(t.slice(0, i2).some(x => x.includes('停手：驗證旗標'))).toBe(false)
})

test('路徑函式：主視窗 = 舊路徑；其他視窗在 clients/<程序名>', () => {
  expect(stateFileFromCwd(ROOT)).toBe(`${ROOT}/tools/.cache/state.json`)
  expect(stateFileFromCwd(ROOT, 'PrimalSA')).toBe(`${ROOT}/tools/.cache/state.json`)
  expect(stateFileFromCwd(ROOT, 'PrimalSA2')).toBe(`${ROOT}/tools/.cache/clients/PrimalSA2/state.json`)
  expect(hudCfgFromCwd(ROOT, 'PrimalSA2')).toBe(`${ROOT}/tools/.cache/clients/PrimalSA2/psa-hud.json`)
  expect(hudCfgFromCwd(ROOT)).toBe(`${ROOT}/tools/.cache/psa-hud.json`)
  expect(questLogFromCwd(ROOT)).toBe(`${ROOT}/notes/quest-events.log`)
  expect(questLogFromCwd(ROOT, 'PrimalSA2')).toBe(`${ROOT}/notes/clients/PrimalSA2/quest-events.log`)
  expect(verifyHaltFromCwd('C:\\games\\PrimalSA-AI\\tools')).toBe('C:\\games\\PrimalSA-AI/tools/.cache/verify-halt.json')
  expect(verifyHaltFromCwd(ROOT, 'PrimalSA2')).toBe(`${ROOT}/tools/.cache/clients/PrimalSA2/verify-halt.json`)
  expect([isMainClient(undefined), isMainClient('primalsa'), isMainClient('PrimalSA2')]).toEqual([true, true, false])
  expect(MAIN_CLIENT).toBe('PrimalSA')
})

test('actionsFor：主視窗 = 沒標籤的行；其他視窗只取自己的標籤行並去掉標籤；undefined 原樣', () => {
  const a = '10:00:00 walk a\n10:00:01 [PrimalSA2] walk b\n10:00:02 [PrimalSA3] walk c\n10:00:03 ass：DKBO [x] 快速戰鬥\n'
  expect(actionsFor(a)).toBe('10:00:00 walk a\n10:00:03 ass：DKBO [x] 快速戰鬥\n')
  expect(actionsFor(a, 'PrimalSA2')).toBe('10:00:01 walk b')
  expect(actionsFor(a, 'primalsa3')).toBe('10:00:02 walk c')
  expect(actionsFor(undefined, 'PrimalSA2')).toBeUndefined()
  expect(actionsFor('10:00:00 walk a\n')).toBe('10:00:00 walk a\n')           // 沒有標籤行 = 原文
})

test('parseRunning / diffClients：主視窗永遠第一；查不到維持現狀；連 2 次偵測不到才移除', () => {
  expect(parseRunning(0, 'PrimalSA2\r\nPrimalSA\n\n')).toEqual(['PrimalSA', 'PrimalSA2'])
  expect(parseRunning(0, '')).toEqual(['PrimalSA'])
  expect(parseRunning(1, 'PrimalSA2')).toBeUndefined()
  expect(parseRunning(0, 'bad name!\nPrimalSA2')).toEqual(['PrimalSA', 'PrimalSA2'])
  const cur = [{ name: 'PrimalSA', misses: 0 }, { name: 'PrimalSA2', misses: 0 }]
  expect(diffClients(cur, ['PrimalSA', 'PrimalSA2', 'PrimalSA3'])).toEqual({ add: ['PrimalSA3'], drop: [], misses: { PrimalSA: 0, PrimalSA2: 0 } })
  expect(diffClients(cur, ['PrimalSA'])).toEqual({ add: [], drop: [], misses: { PrimalSA: 0, PrimalSA2: 1 } })
  expect(diffClients([cur[0]!, { name: 'PrimalSA2', misses: 1 }], ['PrimalSA']).drop).toEqual(['PrimalSA2'])
  expect(diffClients([cur[0]!, { name: 'PrimalSA2', misses: 1 }], ['PrimalSA', 'PrimalSA2']).misses.PrimalSA2).toBe(0)
  expect(diffClients([{ name: 'PrimalSA', misses: 5 }], []).drop).toEqual([])        // 主視窗永不移除
})

test('pickTargets / clientEnv / winSuffix / bannerLines', () => {
  expect(pickTargets(['PrimalSA', 'PrimalSA2'], undefined)).toEqual(['PrimalSA', 'PrimalSA2'])
  expect(pickTargets(['PrimalSA', 'PrimalSA2'], 'ALL')).toEqual(['PrimalSA', 'PrimalSA2'])
  expect(pickTargets(['PrimalSA', 'PrimalSA2'], 'primalsa2')).toEqual(['PrimalSA2'])
  expect(typeof pickTargets(['PrimalSA'], 'PrimalSA2')).toBe('string')
  const base = { PSA_WATCH_OWNER: 'hud' }
  expect(clientEnv('PrimalSA', base, '/usr/bin/python3', ROOT)).toBe(base)
  expect(clientEnv('PrimalSA2', base, '/usr/bin/python3', ROOT)).toEqual({ PSA_WATCH_OWNER: 'hud', PSA_CLIENT: 'PrimalSA2' })
  expect(clientEnv('PrimalSA2', base, 'C:\\py\\python.exe', ROOT)).toEqual({ PSA_WATCH_OWNER: 'hud', PSA_CLIENT: 'PrimalSA2', WSLENV: 'PSA_WATCH_OWNER:PSA_CLIENT' })
  expect(clientEnv('PrimalSA2', base, 'C:\\py\\python.exe', 'C:\\games\\PrimalSA-AI')).toEqual({ PSA_WATCH_OWNER: 'hud', PSA_CLIENT: 'PrimalSA2' })   // Windows 原生直接繼承
  expect([winSuffix(1), winSuffix(2), winSuffix(3)]).toEqual(['', '（2 視窗）', '（3 視窗）'])
  const vs = { v: 1, flags: { verify_suspect: true } } as never
  expect(bannerLines(undefined, [{ client: 'PrimalSA', state: vs }])).toEqual([])          // 單視窗：verify_suspect 已在提示行，不重複
  expect(bannerLines(undefined, [{ client: 'PrimalSA', state: null }, { client: 'PrimalSA2', state: vs }])).toEqual([])   // 多視窗：紅字在各視窗段落
  expect(haltLines('PrimalSA2', undefined, vs, true)).toEqual([{ text: '疑似答題 / 驗證視窗，請人工處理（只停這個視窗）', tone: 'red' }])
  expect(haltLines('PrimalSA2', undefined, vs, false)).toEqual([])
  expect(bannerLines('not json', [])[0]?.text).toBe('PrimalSA 停手：驗證旗標 ：')                // 壞檔 = 主視窗的（保守）
  // 歸屬：主視窗自己的 / 舊共用（client 欄是別的視窗）/ 每視窗自己的檔
  const m1 = JSON.stringify({ client: 'PrimalSA', reason: 'a' }), m2 = JSON.stringify({ client: 'PrimalSA2.exe', reason: 'b' })
  expect([haltOwner(undefined), haltOwner(m1), haltOwner(m2), haltOwner('bad'), haltOwner('{}')]).toEqual([undefined, 'PrimalSA', 'PrimalSA2', 'PrimalSA', 'PrimalSA'])
  expect(haltFor('PrimalSA', m1, m1)).toEqual({ text: m1, legacy: false })
  expect(haltFor('PrimalSA2', undefined, m1)).toBeUndefined()
  expect(haltFor('PrimalSA', m2, m2)).toBeUndefined()
  expect(haltFor('primalsa2', undefined, m2)).toEqual({ text: m2, legacy: true })
  expect(haltFor('PrimalSA3', undefined, m2)).toBeUndefined()
  expect(haltFor('PrimalSA2', 'own', undefined)).toEqual({ text: 'own', legacy: false })
  expect(haltLines('PrimalSA2', { text: m2, legacy: true }, null, true)[0]?.text).toBe('停手：驗證旗標 ：b（舊共用旗標檔）')
})

test('autoTitle：多視窗加「（N 視窗）」；練功判斷只看主視窗沒標籤的行', async () => {
  const log = '[questrun] 任務 2000「琉璃洞窟」詳情結果：accepted\n'
  const root = '/mnt/c/games/PrimalSA-AI'
  const rd = (acts: string) => async (p: string) => {
    if (p.endsWith('quest-events.log')) return log
    if (p.endsWith('actions.log')) return acts
    if (p.endsWith('questdefs.py')) return "dict(id=2000, detail='琉璃洞窟')"
    throw new Error('ENOENT')
  }
  const mk = (acts: string) => ({ clock: { now: async () => gnow }, fs: { read: rd(acts) } }) as never
  expect(await autoTitle(mk(''), root, undefined, 1)).toBe('PSA｜四大洞窟：琉璃洞窟 進行中')
  expect(await autoTitle(mk(''), root, undefined, 2)).toBe('PSA｜四大洞窟：琉璃洞窟 進行中（2 視窗）')
  expect(await autoTitle(mk(''), root, 'PSA｜四大洞窟：琉璃洞窟 進行中（2 視窗）', 2)).toBeUndefined()
  // PrimalSA2 在練功（帶標籤）→ 主視窗標題不受影響
  const tagged = GA.split('\n').filter(Boolean).map(l => `${l.slice(0, 8)} [PrimalSA2] ${l.slice(9)}`).join('\n') + '\n'
  expect(await autoTitle(mk(tagged), root, undefined, 2)).toBe('PSA｜四大洞窟：琉璃洞窟 進行中（2 視窗）')
  expect(await autoTitle(mk(GA), root, undefined, 3)).toBe('PSA｜練功中 地雷區（3 視窗）')
})

test('Supervisor.dispose：收掉子程序、不寫設定、不送 --stop、不重開', async () => {
  const h = harness([{ hang: true }, { hang: true }])
  h.sup.start(); await settle()
  h.sup.dispose(); await settle()
  expect([h.log.returned, h.log.stops, h.log.cfg, h.sup.status, h.log.spawns]).toEqual([1, 0, [], 'off', 1])
})

// ───────────── pane 排版（2026-10-15 改版：每視窗一段、重點在前、依顯示寬度折行、智慧果剩餘時間）─────────────
import { dispW, errGroups, errTable, paneLines, tableLines, truncW, winTable, wrapW, PANE_W } from './register'

test('dispW / wrapW：全形算 2；依寬度折行、續行縮排、超過行數加 …；英數字不從中間切', () => {
  expect(dispW('ab中文')).toBe(6)
  expect(wrapW('短', 10)).toEqual(['短'])
  expect(wrapW('一二三四五六七八', 10, 2)).toEqual(['一二三四五', '  六七八'])
  expect(wrapW('一二三四五六七八九十一二三四五六七八', 10, 2)).toEqual(['一二三四五', '  六七八…'])
  for (const l of wrapW('長'.repeat(200), 30, 3)) expect(dispW(l)).toBeLessThanOrEqual(30)
  expect(wrapW('清：uv run --no-project python tools/gui/verifyhalt.py clear', 30, 3)).toEqual(['清：uv run --no-project python', '  tools/gui/verifyhalt.py', '  clear'])
})

test('errGroups：同一視窗 + 來源 + 錯誤 + 改進合併成一筆（保留最新），順序不變', () => {
  const e = (id: number, error: string, source = 'q') => ({ id, ts: id, error, fix: null, source })
  const g = errGroups([e(9, 'A'), e(8, 'B'), e(7, 'A'), e(6, 'A', 'x'), e(5, 'A')])
  expect(g.map(x => [x.e.id, x.n])).toEqual([[9, 3], [8, 1], [6, 1]])
})

const WV = (o: object = {}) => ({ client: 'PrimalSA2', wl: { main: '主畫面', hints: [] }, ht: 'x', en: { text: '遇敵中', warn: false }, al: [], ...o }) as never
const HP = (o: object = {}) => ({
  who: 'DKBO6  0轉105級  HP 482  MP 100', pet: '寵 0轉105級 HP 1008', loc: '五十年前波拉島 500:210,344',
  f: { name: 'DKBO6', level: '0轉105級', hp: '482', mp: '100', petLevel: '0轉105級', petHp: '1008', map: '五十年前波拉島', pos: '500:210,344' }, ...o,
})
const wOf = (ls: { text: string }[]) => ls.map(x => dispW(x.text))

test('winTable：表頭 → ！警示列（去重）→ 人物 / 寵物 / 地圖 → Buff → 狀態 / 事件 / 動作；列與列之間沒有橫線', () => {
  const w = WV({
    wl: { main: '主畫面', hints: [{ text: '已有 watch 在跑（不是這個 HUD 啟動的），只讀', tone: 'gray' }, { text: '疑似答題 / 驗證視窗，請人工處理', tone: 'red' }] },
    al: [{ text: '疑似答題 / 驗證視窗，請人工處理（只停這個視窗）', tone: 'red' }],
    hp: HP(), bf: { text: '智慧果 剩 1:23', warn: false },
  })
  const l = winTable({ w, prog: [
    { text: '練功中：波拉島', tone: 'plain' }, { text: ' 15:25:12 follow：升級', tone: 'gray' }, { text: '動作 15:22:01 關外掛面板（閒置 6 分）', tone: 'yellow' },
  ] }, 64, true)
  const t = l.map(x => x.text)
  expect(t[0]!.startsWith('┌ p2 PrimalSA2 · 主畫面 ─')).toBe(true)
  expect(t[0]!.endsWith('┐')).toBe(true)
  expect(t[1]!.startsWith('│ ！   │ 疑似答題')).toBe(true)
  expect(t.filter(x => x.includes('疑似答題')).length).toBe(1)                       // 同一件事只寫一次
  expect(l[1]).toMatchObject({ tone: 'red', bold: true })
  expect(t[2]!.startsWith('│ 人物 │ DKBO6 0轉105級')).toBe(true)
  expect(t[2]).toMatch(/HP 482 \/ MP 100 +│$/)
  expect(t[3]).toMatch(/^│ 寵物 │ 0轉105級 +HP 1008 +│$/)
  expect(t[4]).toMatch(/^│ 地圖 │ 波拉島 210,344 +遇敵中 +│$/)               // 去掉地圖編號、「五十年前」
  expect(t[5]).toMatch(/^│ Buff │ 智慧果 剩 1:23 +│$/)
  expect(l[5]!.tone).toBe('green')
  expect(t[6]).toMatch(/^│ 狀態 │ 練功中：波拉島 +│$/)
  expect(t[7]).toMatch(/^│ 事件 │ 15:25 follow：升級 +│$/)
  expect(t[8]).toMatch(/^│ 動作 │ 15:22 關外掛面板（閒置 6 分） +│$/)
  expect(l[8]!.tone).toBe('yellow')
  expect(t[9]!.startsWith('└──────┴')).toBe(true)
  expect(t.slice(1, 9).some(x => x.includes('├'))).toBe(false)                        // 上方表格列與列之間不加橫線
  expect(t[10]).toBe('已有 watch 在跑（不是這個 HUD 啟動的），只讀')                    // 次要提示：表格下方灰字一行
  expect(l[10]!.tone).toBe('gray')
  expect(wOf(l.slice(0, 10)).every(n => n === 64)).toBe(true)                          // 表格寬度固定
  // 單視窗：表頭只寫程序名
  expect(winTable({ w: WV(), prog: [] }, 64, false)[0]!.text.startsWith('┌ PrimalSA2')).toBe(true)
})

test('winTable：龍王在 Buff 列、地圖列不帶龍王字樣', () => {
  const rows = winTable({ w: WV({ hp: HP(), en: { text: '遇敵中', warn: false }, bf: { text: '智慧果 剩 1:23 · 龍王 剩 0:45', warn: false } }), prog: [] }).map(x => x.text)
  expect(rows.find(x => x.includes('Buff'))).toContain('龍王 剩 0:45')
  expect(rows.find(x => x.includes('遇敵中'))).not.toContain('龍王')
})

test('winTable：沒有 buff 不顯示 Buff 列；不遇敵 / buff 時間未知 → 黃字；沒資料的事件 / 動作列不顯示；無警示不顯示 ！', () => {
  const t0 = winTable({ w: WV({ hp: HP() }), prog: [{ text: '任務：—', tone: 'plain' }, { text: '事件：—', tone: 'gray' }, { text: '動作：—', tone: 'gray' }] }, 64, true).map(x => x.text)
  expect(t0.some(x => x.includes('Buff') || x.includes('！') || x.includes('事件') || x.includes('動作'))).toBe(false)
  expect(winTable({ w: WV({ hp: HP(), en: { text: '不遇敵', warn: true } }), prog: [] }).find(x => x.text.includes('不遇敵'))!.tone).toBe('yellow')
  expect(winTable({ w: WV({ hp: HP(), bf: { text: '智慧果 ?（bufftime.py read）', warn: true } }), prog: [] }).find(x => x.text.includes('智慧果'))!.tone).toBe('yellow')
  // 多件警示 = 多列；停手指令長 → 折行不截掉
  const halt = winTable({ w: WV({ hp: HP(), al: [
    { text: '停手：驗證旗標 uikit：連 3 次不認得', tone: 'red' }, { text: '畫面恢復 5 秒自動清；手動：uv run --no-project python tools/gui/verifyhalt.py clear PrimalSA2', tone: 'red' },
  ] }), prog: [] }, 64, true).map(x => x.text)
  expect(halt.filter(x => x.startsWith('│ ！   │')).length).toBe(2)
  expect(halt.join('').replace(/[│\s]/g, '')).toContain('verifyhalt.pyclearPrimalSA2')
  // 主視窗 watch 不在：退回一次性 stat；讀不到 → 讀取中
  expect(winTable({ w: WV({ client: 'PrimalSA', ht: null, hp: null }), prog: [], st: { ok: true, level: '0轉1級', hp: 3, mp: 4 } }).map(x => x.text).join('\n')).toContain('0轉1級')
  expect(winTable({ w: WV({ ht: null, hp: null }), prog: [] }).map(x => x.text).join('\n')).toContain('讀取中…')
  // 單視窗的 banner 併入「！」列（黃字提示 = 黃）
  const b = winTable({ w: WV({ hp: HP() }), prog: [] }, 64, false, [{ text: '舊共用驗證旗標屬 PrimalSA2', tone: 'yellow' }])
  expect(b[1]).toMatchObject({ tone: 'yellow' })
  expect(b[1]!.text.startsWith('│ ！   │ 舊共用')).toBe(true)
})

test('tableLines / truncW：中文算 2、截短加 …、框線；內容過長不撐破', () => {
  expect(truncW('一二三四五六', 8)).toBe('一二三…')
  expect(truncW('abc', 8)).toBe('abc')
  const l = tableLines({ width: 30, cols: [{ w: 4 }, { w: 'flex' }], title: 't', rows: [{ cells: ['人物', '長'.repeat(50)], tone: 'plain' }] })
  expect(l.map(x => dispW(x.text))).toEqual([30, 30, 30])
  expect(l[1]!.text.endsWith('… │')).toBe(true)
  expect(l[0]!.text.startsWith('┌ t ─')).toBe(true)
})

test('errTable：5 欄、每筆之間橫線、預設 6 筆新的在上、同句合併 ×N、待改進黃 / 已改進綠、當天只顯示時:分', () => {
  const now = new Date(2026, 9, 15, 15, 30).getTime()
  const e = (id: number, error: string, o: object = {}) => ({ id, ts: now - id * 60000, error, fix: null, source: 'questrun', ...o })
  const lines = [e(1, 'A'), e(2, 'A'), e(3, 'B', { source: 'bag', client: 'PrimalSA2' }), e(4, 'C', { fix: '已修' }),
    e(5, 'D'), e(6, 'E'), e(7, 'F'), e(8, 'G', { ts: new Date(2026, 9, 10, 8, 5).getTime() })]
  const l = errTable(lines, 64, now)
  const t = l.map(x => x.text)
  expect(t[0]).toMatch(/^┌─+┬─+┬─+┬─+┬─+┐$/)
  expect(t[1]).toMatch(/^│ 時間 +│ 次數 +│ 來源 +│ 內容 +│ 狀態 +│$/)
  expect(t[3]).toMatch(/^│ 15:29 +│ ×2 +│ questrun +│ A +│ 待改進 │$/)         // 同句合併 ×2
  expect(t[5]).toMatch(/^│ 15:27 +│ ×1 +│ p2 bag +│ B +│ 待改進 │$/)
  expect(l[3]!.tone).toBe('yellow')
  expect(t.filter(x => x.startsWith('│ 15:') || x.startsWith('│ 10/')).length).toBe(6)  // 6 筆上限（A×2 合併 → 6 組）
  expect(t.filter(x => x.startsWith('├')).length).toBe(6)                              // 表頭下 1 + 筆與筆之間 5
  expect(t[7]).toMatch(/已改進 │$/)
  expect(l.find(x => x.text.includes('已改進'))!.tone).toBe('green')
  expect(t.every(x => dispW(x) === 64)).toBe(true)
  expect(t.join('\n')).not.toContain('G')                                            // 第 7 組以後不顯示
  // 非當天顯示 月/日
  expect(errTable([e(8, 'G', { ts: new Date(2026, 9, 10, 8, 5).getTime() })], 64, now).map(x => x.text).join('\n')).toContain('│ 10/10 │')
  expect(errTable([], 64, now)).toEqual([{ text: '（還沒有錯誤紀錄）', tone: 'gray' }])
})

test('paneLines：每行顯示寬度不超過 pane 寬度（長錯誤 / 長事件 / 3 個視窗堆疊）', () => {
  const long = '任務 2031「英雄島前傳（必做）」要有龍王的守護 buff 才組隊跑：背包與公共倉庫都沒有龍王的守護 → 改走單人逃跑（同一行指令加 --solo）'
  for (const width of [40, 60, PANE_W, 80, 120]) {
    const ls = paneLines({
      wins: [WV({ client: 'PrimalSA', hp: HP() }), WV({ bf: { text: '智慧果 剩 1:23 · 龍王 ?（bufftime.py read）', warn: true } }), WV({ client: 'PrimalSA3', hp: HP() })],
      progs: [{ client: 'PrimalSA', lines: [{ text: `任務：${long}`, tone: 'plain' }, { text: ` 15:28:34 ${long}`, tone: 'gray' }] }],
      lines: [{ id: 1, ts: 0, error: long, fix: long, source: 'questrun' }, { id: 2, ts: 0, error: long, fix: null, source: 'bag' }],
      width, now: 0,
    })
    for (const l of ls) expect(dispW(l.text)).toBeLessThanOrEqual(width)
    const heads = ls.map(l => l.text).filter(x => x.startsWith('┌ p'))
    expect(heads.map(x => x.slice(2, 4))).toEqual(['p1', 'p2', 'p3'])               // 3 張小表上下堆疊（p1 在前）
  }
})

test('多視窗：PrimalSA2 有 bufftime.json → pane 顯示「智慧果 剩 H:MM」倒數', async ($, on) => {
  const bt = JSON.stringify({ v: 1, ts: NOW_S - 600, buffs: { exp: { expires_ts: NOW_S + 83 * 60 + 30, read_ts: NOW_S - 600, remaining_s: 5580 } } })
  scenarioHost(on, { running: 'PrimalSA\nPrimalSA2\n', files: { ...MULTI_FILES, 'tools/.cache/clients/PrimalSA2/bufftime.json': bt } })
  await $.command.run({ command: 'psa-hud', args: 'on' } as never)
  await flush()
  await $.command.run({ command: 'psa-hud', args: 'watch status' } as never)
  await flush()
  const t = await paneTexts($)
  expect(t).toContain(R('Buff', '智慧果 剩 1:23'))
})
