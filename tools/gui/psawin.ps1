# 多視窗共用（dot-source：. (Join-Path $PSScriptRoot 'psawin.ps1')）：選遊戲程序 + 全域點擊鎖。不碰遊戲，只定義函式。
#
# 選視窗：環境變數 PSA_CLIENT = 遊戲程序名稱（不含 .exe；PrimalSA / PrimalSA2 / PrimalSA3 …），沒設 = PrimalSA（原本的單視窗行為）。
#   同機多開時每個視窗用不同名稱的執行檔（GameClient/PrimalSA2.exe + 目錄連結 PrimalSA2_Data），程序名稱就能精確分辨，不必讀名單。
#   精確比對（GetProcessesByName，不吃萬用字元）；找不到 → 不操作；同名多個 → 不操作（不猜是哪一個）。
#   WSL 的 powershell.exe 要靠 WSLENV 才收得到 PSA_CLIENT（winenv.py / gui.sh / mirror.sh 會加）；常駐 serve.ps1 每個請求自己設。
#
# 點擊鎖：背景點擊要把「真實游標」瞬移到目標（Unity 讀真實游標），兩個視窗同時點會搶游標。
#   用 Windows 具名 Mutex（Local\ = 同一登入工作階段；WSL 與 Windows 原生叫起來的 powershell.exe 都在同一個工作階段，所以跨行程、跨平台都有效），
#   只包「游標離開使用者 → 移回」那一小段（gui.ps1 的 BgBegin…BgEnd、fg 模式的移游標 + 按放）；鍵盤（PostMessage）不鎖。
#   持有者被 kill → AbandonedMutexException，視為取得（呼叫端寫 actions.log）。逾時 → 呼叫端不點、exit 7。

$PsaDefaultClient = 'PrimalSA'
$PsaInputMutexName = 'Local\PrimalSA-AI-Input'
$PsaInputLockTimeoutMs = 5000
$PsaGuiDir = $PSScriptRoot                    # tools/gui（dot-source 當下記住，函式裡用）
$PsaSharedCache = [IO.Path]::GetFullPath((Join-Path $PsaGuiDir '..\.cache'))

# PSA_CLIENT 正規化：去空白、去結尾 .exe；空的 = PrimalSA
function Get-PsaClient {
  $n = ([string]$env:PSA_CLIENT).Trim()
  if ($n -match '(?i)\.exe$') { $n = $n.Substring(0, $n.Length - 4) }
  if (-not $n) { return $PsaDefaultClient }
  return $n
}

# 是不是主視窗（PrimalSA）：log 不加標籤、錯誤訊息維持舊文字
function Test-PsaDefaultClient([string]$Name) { return [string]::Equals($Name, $PsaDefaultClient, [StringComparison]::OrdinalIgnoreCase) }

# 每個視窗自己的狀態資料夾（與 clients.py cache_dir / dir_name 同規則）：主視窗 = tools/.cache（與改版前相同）；
# 其他 = tools/.cache/clients/<程序名>（不合法字元換 _、全是點的名稱前面加 _，不會跳出 clients/）。gui.ps1 的相對截圖 / gui-session.txt 用
function Get-PsaCacheDir([string]$Name = (Get-PsaClient)) {
  if (Test-PsaDefaultClient $Name) { return $PsaSharedCache }
  $d = $Name -replace '[^A-Za-z0-9_.-]', '_'
  if ($d.Length -gt 64) { $d = $d.Substring(0, 64) }
  if ($d -match '^\.*$') { $d = '_' + $d }
  return (Join-Path (Join-Path $PsaSharedCache 'clients') $d)
}

# 每視窗驗證停手旗標（verifyhalt.py 寫；多視窗時這個視窗出現驗證視窗才設，只停這個視窗）：存在 → gui.ps1 不送 click / dclick / drag / key / typeq（exit 9）。
# 路徑與 verifyhalt.path 同規則：Get-PsaCacheDir <程序名> / verify-halt.json（主視窗 = tools/.cache/verify-halt.json）。
# 舊格式（改版前全部視窗共用 tools/.cache/verify-halt.json，非主視窗寫的內含 client 欄）：client 不是主視窗 → 算那個視窗的，主視窗不受影響。
# 回傳本視窗命中的旗標檔路徑；沒有 = $null。常駐 serve.ps1 每請求設 PSA_CLIENT，gui.ps1 傳 $Client 進來
function Get-PsaVerifyHalt([string]$Name = (Get-PsaClient)) {
  $main = Join-Path $PsaSharedCache 'verify-halt.json'
  $owner = $null
  if (Test-Path -LiteralPath $main) {
    $owner = $PsaDefaultClient
    try {
      $c = ([string]((Get-Content -LiteralPath $main -Raw -Encoding UTF8 | ConvertFrom-Json).client)).Trim()
      if ($c -match '(?i)\.exe$') { $c = $c.Substring(0, $c.Length - 4) }
      if ($c) { $owner = $c }
    } catch { }                                    # 壞檔：當作主視窗自己的（與 verifyhalt._read 一致：壞檔也算存在）
  }
  if (Test-PsaDefaultClient $Name) {
    if ($owner -and (Test-PsaDefaultClient $owner)) { return $main }
    return $null
  }
  $own = Join-Path (Get-PsaCacheDir $Name) 'verify-halt.json'
  if (Test-Path -LiteralPath $own) { return $own }
  if ($owner -and [string]::Equals($owner, $Name, [StringComparison]::OrdinalIgnoreCase)) { return $main }
  return $null
}
function Test-PsaVerifyHalt([string]$Name = (Get-PsaClient)) { return ($null -ne (Get-PsaVerifyHalt $Name)) }

# 找 PSA_CLIENT 指定的遊戲程序。回傳 hashtable：
#   ok=$true  → name、proc（唯一一個 Process）
#   ok=$false → name、kind（badname / none / multi）、error（給人看的訊息；none 一律含「<名稱> 沒有在執行」，watch.py 靠它判斷遊戲沒開）
# $Procs 只給離線測試注入假程序清單用（不給 = 真的查）
function Find-PsaProcess($Procs = $null) {
  $n = Get-PsaClient
  if ($n -notmatch '^[A-Za-z0-9_.-]{1,64}$') {
    return @{ ok = $false; name = $n; kind = 'badname'; error = "PSA_CLIENT 名稱不合法：$n（只能是程序名稱，例如 PrimalSA2）" }
  }
  if ($null -eq $Procs) { $Procs = [Diagnostics.Process]::GetProcessesByName($n) }
  $ps = @($Procs)
  if ($ps.Count -eq 0) { return @{ ok = $false; name = $n; kind = 'none'; error = "$n 沒有在執行" } }
  if ($ps.Count -gt 1) {
    $ids = ($ps | ForEach-Object { $_.Id }) -join ','
    return @{ ok = $false; name = $n; kind = 'multi'; error = "同名程序 $n 有 $($ps.Count) 個（PID $ids），不知道要操作哪一個：每個視窗要用不同名稱的執行檔，並設 PSA_CLIENT" }
  }
  return @{ ok = $true; name = $n; proc = $ps[0] }
}

# 讀圖腳本（stat / ocr / findmark / titlematch / 數字樣板）回 JSON 用的錯誤字串：主視窗沒開維持舊文字「遊戲沒有在執行」，
# 其他視窗加「（程序名）」；同名多個 / 名稱不合法用 Find-PsaProcess 的訊息
function Get-PsaFindError($Found) {
  if ($Found.kind -eq 'none') { if (Test-PsaDefaultClient $Found.name) { return '遊戲沒有在執行' } else { return "遊戲沒有在執行（$($Found.name)）" } }
  return $Found.error
}

# 取點擊鎖。回傳 hashtable：ok、mutex（ok 時才有，交給 Exit-PsaInputLock 放）、waitMs、abandoned
# $Name / $TimeoutMs 只給測試換（實際一律用 $PsaInputMutexName）
function Enter-PsaInputLock([int]$TimeoutMs = $PsaInputLockTimeoutMs, [string]$Name = $PsaInputMutexName) {
  $sw = [Diagnostics.Stopwatch]::StartNew()
  $m = New-Object Threading.Mutex($false, $Name)
  $got = $false; $ab = $false
  try { $got = $m.WaitOne($TimeoutMs) }
  catch {
    # 持有者沒放就結束（被 kill）：鎖已轉給我們。PowerShell 會把 .NET 例外包成 MethodInvocationException，內層才是 AbandonedMutexException
    $ex = $_.Exception
    while ($ex -and -not ($ex -is [Threading.AbandonedMutexException])) { $ex = $ex.InnerException }
    if ($ex) { $got = $true; $ab = $true } else { $m.Dispose(); throw }
  }
  if (-not $got) { $m.Dispose(); return @{ ok = $false; waitMs = [int]$sw.ElapsedMilliseconds; abandoned = $false } }
  return @{ ok = $true; mutex = $m; waitMs = [int]$sw.ElapsedMilliseconds; abandoned = $ab }
}

# 放點擊鎖；可重複呼叫、$null 安全
function Exit-PsaInputLock($Lock) {
  if ($Lock -and $Lock.mutex) {
    try { $Lock.mutex.ReleaseMutex() } catch { }
    $Lock.mutex.Dispose(); $Lock.mutex = $null
  }
}
