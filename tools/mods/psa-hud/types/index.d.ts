// stat.ps1 印出的一行 JSON
export type Stat = {
  ok: boolean
  error?: string
  level?: string
  hp?: number | null
  hpPct?: number | null
  mpPct?: number | null
  mp?: number | null
  petLevel?: string
  petHp?: number | null
  map?: string
  pos?: string
  // watch 的 state.hud 才有（stat.ps1 本身沒有）：人物名 / 寵物名（'?' = 不確定；結尾 ? = 舊值）
  name?: string
  petName?: string
}

// errlog.jsonl 一筆
export type ErrEntry = { id: number; ts: number; error: string; fix: string | null; source: string | null; client?: string }  // client：非主視窗才有（errlog.py 寫的程序名）

// pane 頂端狀態行：主行 + 提示行（tone：red 警示 / yellow 提醒 / gray 資訊）
export type WatchTone = 'red' | 'yellow' | 'gray'
export type WatchLine = { main: string; hints: { text: string; tone: WatchTone }[] }

// 即時進度區一行（tone：plain 一般 / gray 次要 / yellow 提醒 / red 警報）
export type ProgLine = { text: string; tone: 'plain' | 'gray' | 'yellow' | 'red' }

// 多視窗（第 3d 步）：每個視窗一份狀態行 / HUD 行 / 遇敵行
export type WinView = { client: string; wl: WatchLine; ht: string | null; en: { text: string; warn: boolean } | null }
// 多視窗：每個視窗一份即時進度區
export type WinProg = { client: string; lines: ProgLine[] }
// 頂端醒目警示（verify-halt.json、任一視窗 verify_suspect）
export type Banner = { text: string; tone: WatchTone }

declare module 'claude-code' {
  interface PluginState {
    'psa-hud': {
      // 最近一次讀取結果；null = 還沒讀過
      stat: Stat | null
      // 錯誤 / 改進紀錄（errlog.jsonl）最新 100 筆，最新在前
      errs: ErrEntry[]
      // 最近一次讀取的時間（毫秒）
      at: number
      // watch 活著時的等級 / HP 行（state.hud 組成）；null = watch 不在，改用 stat
      hud: string | null
      // 遇敵狀態行（state.screen.enc_on；warn = 不遇敵，黃字）；null = 不顯示
      enc: { text: string; warn: boolean } | null
      // 即時狀態行（讀 tools/.cache/state.json 組成；顯示文字變了才更新）
      line: WatchLine
      // 即時進度區（任務 / 最近事件 / 最後動作 / 警報，最多 6 行）
      prog: ProgLine[]
      // 多視窗時每視窗一份（只有 1 個視窗 = 空陣列，pane 照單視窗畫）
      wins: WinView[]
      progs: WinProg[]
      // 頂端醒目警示（空 = 不顯示）
      banner: Banner[]
    }
  }
}
