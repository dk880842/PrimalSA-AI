# psawin.ps1（多視窗選程序 + 全域點擊鎖）離線測試：不碰遊戲視窗、不送任何輸入。
#   1) Get-PsaClient 正規化（沒設 / 空白 / .exe）
#   2) Find-PsaProcess 以注入的假程序清單測 0 / 1 / 3 個、不合法名稱（萬用字元）
#   3) 點擊鎖：取放、另一個行程持有時逾時、持有者沒放就結束（Abandoned → 視為取得）、兩個行程各 15 次取放區間不重疊
#   4) gui.ps1 在 PSA_CLIENT 指向不存在 / 同名多個（svchost）/ 不合法名稱時：不點、exit 1 / 6（這些情況在找視窗那步就結束，碰不到遊戲）
#   5) 改過的 .ps1 都能解析（只 parse 不執行）
#   2c) 每視窗驗證停手旗標 Get-PsaVerifyHalt（暫存資料夾；本視窗 / 別的視窗 / 舊共用旗標歸屬 / 壞檔）
# 鎖測試用自己的 Mutex 名稱，不影響正在跑的 gui.ps1。
# 用法：powershell.exe -NoProfile -ExecutionPolicy Bypass -File tools\gui\test_psawin.ps1
$ErrorActionPreference = 'Continue'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8   # WSL 收到的中文不變亂碼
. (Join-Path $PSScriptRoot 'psawin.ps1')
$fail = 0
function Check($name, $ok) { if ($ok) { "PASS $name" } else { "FAIL $name"; $script:fail++ } }
$saveClient = $env:PSA_CLIENT

# ---- 1) 名稱正規化 ----
Remove-Item Env:PSA_CLIENT -ErrorAction SilentlyContinue
Check '沒設 = PrimalSA' ((Get-PsaClient) -ceq 'PrimalSA')
$env:PSA_CLIENT = '  PrimalSA2.EXE '
Check '去空白 / .exe' ((Get-PsaClient) -ceq 'PrimalSA2')
Check 'PrimalSA2 不是主視窗' (-not (Test-PsaDefaultClient 'PrimalSA2'))
Check 'primalsa（大小寫）是主視窗' (Test-PsaDefaultClient 'primalsa')

# ---- 2) Find-PsaProcess（注入假程序清單）----
$env:PSA_CLIENT = 'PrimalSA2'
$r = Find-PsaProcess -Procs @()
Check "0 個 → none「PrimalSA2 沒有在執行」($($r.error))" ((-not $r.ok) -and $r.kind -eq 'none' -and $r.error -eq 'PrimalSA2 沒有在執行')
Check "讀圖腳本錯誤字串帶程序名 ($(Get-PsaFindError $r))" ((Get-PsaFindError $r) -eq '遊戲沒有在執行（PrimalSA2）')
$one = [pscustomobject]@{ Id = 111; MainWindowHandle = [IntPtr]::Zero }
$r = Find-PsaProcess -Procs @($one)
Check '1 個 → ok' ($r.ok -and $r.proc.Id -eq 111 -and $r.name -eq 'PrimalSA2')
$r = Find-PsaProcess -Procs @($one, [pscustomobject]@{ Id = 222 }, [pscustomobject]@{ Id = 333 })
Check "3 個 → multi 不操作 ($($r.error))" ((-not $r.ok) -and $r.kind -eq 'multi' -and $r.error -match '111,222,333')
Remove-Item Env:PSA_CLIENT
$r = Find-PsaProcess -Procs @()
Check '主視窗 0 個 → 舊訊息「PrimalSA 沒有在執行」/「遊戲沒有在執行」' ($r.error -eq 'PrimalSA 沒有在執行' -and (Get-PsaFindError $r) -eq '遊戲沒有在執行')
$env:PSA_CLIENT = 'Primal*'
$r = Find-PsaProcess -Procs @($one)
Check '萬用字元名稱 → badname（不會比到多個程序）' ((-not $r.ok) -and $r.kind -eq 'badname')

# ---- 2b) 每個視窗的狀態資料夾（與 clients.py cache_dir 同規則；只算路徑，不建資料夾）----
$shared = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\.cache'))
Check "主視窗 = tools\.cache（$(Get-PsaCacheDir 'PrimalSA')）" ((Get-PsaCacheDir 'PrimalSA') -eq $shared -and (Get-PsaCacheDir 'primalsa') -eq $shared)
Check 'PrimalSA2 = tools\.cache\clients\PrimalSA2' ((Get-PsaCacheDir 'PrimalSA2') -eq (Join-Path $shared 'clients\PrimalSA2'))
Check '不合法字元換 _、全是點加 _（不跳出 clients\）' ((Get-PsaCacheDir 'a/b') -eq (Join-Path $shared 'clients\a_b') -and (Get-PsaCacheDir '..') -eq (Join-Path $shared 'clients\_..'))
Remove-Item Env:PSA_CLIENT
Check '不給參數 = 目前 PSA_CLIENT（沒設 = 主視窗）' ((Get-PsaCacheDir) -eq $shared)
Check 'Test-PsaVerifyHalt 回布林' ((Test-PsaVerifyHalt) -is [bool])

# ---- 2c) 每視窗驗證停手旗標（Get-PsaVerifyHalt；$PsaSharedCache 暫時指到暫存資料夾，不碰真的 tools\.cache）----
$saveShared = $PsaSharedCache
$PsaSharedCache = Join-Path $env:TEMP ('psawin-vh-' + [Guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path (Join-Path $PsaSharedCache 'clients\PrimalSA2') -Force | Out-Null
$vMain = Join-Path $PsaSharedCache 'verify-halt.json'; $vP2 = Join-Path $PsaSharedCache 'clients\PrimalSA2\verify-halt.json'
Check '都沒有旗標 → 兩個視窗都不停' ((-not (Test-PsaVerifyHalt 'PrimalSA')) -and (-not (Test-PsaVerifyHalt 'PrimalSA2')))
Set-Content -LiteralPath $vP2 -Value '{"client":"PrimalSA2","src":"watch","reason":"x"}' -Encoding UTF8
Check 'PrimalSA2 自己的旗標 → 只停 PrimalSA2，主視窗照常' ((Test-PsaVerifyHalt 'PrimalSA2') -and (-not (Test-PsaVerifyHalt 'PrimalSA')) -and (Get-PsaVerifyHalt 'PrimalSA2') -eq $vP2)
$env:PSA_CLIENT = 'PrimalSA2'
Check '不給參數 = 目前 PSA_CLIENT（serve.ps1 每請求設）' (Test-PsaVerifyHalt)
Remove-Item Env:PSA_CLIENT
Check '不給參數、沒設 PSA_CLIENT = 主視窗 → 不停' (-not (Test-PsaVerifyHalt))
Remove-Item -LiteralPath $vP2
Set-Content -LiteralPath $vMain -Value '{"client":"PrimalSA","src":"uikit","reason":"y"}' -Encoding UTF8
Check '主視窗自己的旗標 → 只停主視窗' ((Test-PsaVerifyHalt 'PrimalSA') -and (-not (Test-PsaVerifyHalt 'PrimalSA2')))
Set-Content -LiteralPath $vMain -Value '{"client":"PrimalSA2","src":"watch","reason":"舊共用"}' -Encoding UTF8
Check '舊共用旗標（client=PrimalSA2）→ 歸屬 PrimalSA2，主視窗不停' ((Test-PsaVerifyHalt 'PrimalSA2') -and (-not (Test-PsaVerifyHalt 'PrimalSA')) -and (Get-PsaVerifyHalt 'PrimalSA2') -eq $vMain)
Check '舊共用旗標不影響第三個視窗' (-not (Test-PsaVerifyHalt 'PrimalSA3'))
Set-Content -LiteralPath $vMain -Value 'not json' -Encoding UTF8
Check '壞檔 → 算主視窗的（保守停手），其他視窗照常' ((Test-PsaVerifyHalt 'PrimalSA') -and (-not (Test-PsaVerifyHalt 'PrimalSA2')))
Set-Content -LiteralPath $vMain -Value '{"src":"manual","reason":"沒有 client 欄"}' -Encoding UTF8
Check '沒有 client 欄 → 算主視窗的' ((Test-PsaVerifyHalt 'PrimalSA') -and (-not (Test-PsaVerifyHalt 'PrimalSA2')))
Remove-Item -LiteralPath $PsaSharedCache -Recurse -Force
$PsaSharedCache = $saveShared

# ---- 3) 點擊鎖 ----
$mx = 'Local\PrimalSA-AI-Input-test-' + [Guid]::NewGuid().ToString('N')
$lk = Enter-PsaInputLock -TimeoutMs 1000 -Name $mx
Check '無競爭取得' ($lk.ok -and -not $lk.abandoned -and $lk.waitMs -lt 200)
Exit-PsaInputLock $lk; Exit-PsaInputLock $lk
Check '放兩次不出錯' ($null -eq $lk.mutex)

$psexe = Join-Path $PSHOME 'powershell.exe'
$flag = Join-Path $env:TEMP ('psawin-test-' + [Guid]::NewGuid().ToString('N') + '.txt')
# 另一個行程：拿鎖、寫旗標、1.5 秒後「不放鎖」直接結束 → Abandoned
$holder = "`$m = New-Object Threading.Mutex(`$false, '$mx'); [void]`$m.WaitOne(); Set-Content '$flag' x; Start-Sleep -Milliseconds 1500; [Environment]::Exit(0)"
$hp = Start-Process $psexe -ArgumentList '-NoProfile', '-Command', $holder -WindowStyle Hidden -PassThru
$t = [Diagnostics.Stopwatch]::StartNew(); while (-not (Test-Path $flag) -and $t.ElapsedMilliseconds -lt 15000) { Start-Sleep -Milliseconds 50 }
$lk = Enter-PsaInputLock -TimeoutMs 200 -Name $mx
Check "別的行程持有 → 200 ms 逾時 ($($lk.waitMs) ms)" ((-not $lk.ok) -and $lk.waitMs -ge 150 -and $null -eq $lk.mutex)
$lk = Enter-PsaInputLock -TimeoutMs 8000 -Name $mx
Check "持有者沒放就結束 → abandoned 視為取得 ($($lk.waitMs) ms)" ($lk.ok -and $lk.abandoned)
Exit-PsaInputLock $lk
Remove-Item $flag -ErrorAction SilentlyContinue

# 兩個行程各 15 次：取鎖 → 記開始 tick → 等 20 ms → 記結束 tick → 放；所有區間不可重疊
$log1 = Join-Path $env:TEMP ('psawin-a-' + [Guid]::NewGuid().ToString('N') + '.txt'); $log2 = $log1 + '.b'
$worker = {
  param($lib, $name, $out)
  . $lib
  $lines = New-Object Collections.ArrayList
  for ($i = 0; $i -lt 15; $i++) {
    $l = Enter-PsaInputLock -TimeoutMs 10000 -Name $name
    $a = [DateTime]::UtcNow.Ticks; Start-Sleep -Milliseconds 20; $b = [DateTime]::UtcNow.Ticks
    Exit-PsaInputLock $l
    [void]$lines.Add("$a $b $($l.ok)")
    Start-Sleep -Milliseconds 3
  }
  [IO.File]::WriteAllLines($out, [string[]]$lines)
}
$lib = Join-Path $PSScriptRoot 'psawin.ps1'
$p1 = Start-Process $psexe -ArgumentList '-NoProfile', '-EncodedCommand', ([Convert]::ToBase64String([Text.Encoding]::Unicode.GetBytes("& { $worker } '$lib' '$mx' '$log1'"))) -WindowStyle Hidden -PassThru
$p2 = Start-Process $psexe -ArgumentList '-NoProfile', '-EncodedCommand', ([Convert]::ToBase64String([Text.Encoding]::Unicode.GetBytes("& { $worker } '$lib' '$mx' '$log2'"))) -WindowStyle Hidden -PassThru
[void]$p1.WaitForExit(60000); [void]$p2.WaitForExit(60000)
$iv = @()
foreach ($f in @($log1, $log2)) { if (Test-Path $f) { foreach ($ln in [IO.File]::ReadAllLines($f)) { $v = $ln -split ' '; $iv += , @([int64]$v[0], [int64]$v[1], $v[2]) } } }
$iv = $iv | Sort-Object { $_[0] }
$overlap = 0; for ($i = 1; $i -lt $iv.Count; $i++) { if ($iv[$i][0] -lt $iv[$i - 1][1]) { $overlap++ } }
Check "兩個行程 30 次取放：$($iv.Count) 筆、重疊 $overlap 次" ($iv.Count -eq 30 -and $overlap -eq 0 -and -not ($iv | Where-Object { $_[2] -ne 'True' }))
Remove-Item $log1, $log2 -ErrorAction SilentlyContinue

# ---- 4) gui.ps1：目標程序不存在 / 同名多個 / 不合法 → 不點 ----
$gui = Join-Path $PSScriptRoot 'gui.ps1'
foreach ($case in @(@('PsaNoSuchClient9', 1), @('svchost', 6), @('Primal*', 6))) {
  $env:PSA_CLIENT = $case[0]
  $o = & $psexe -NoProfile -ExecutionPolicy Bypass -File $gui click 1 1 2>&1 | Out-String
  $rc = $LASTEXITCODE
  Check "gui.ps1 click，PSA_CLIENT=$($case[0]) → exit $rc（期望 $($case[1])），沒有 click 輸出" ($rc -eq $case[1] -and $o -notmatch 'click 1,1')
}

# ---- 4b) 真的 serve.ps1：每個請求依 client 設 PSA_CLIENT（只用不存在 / 同名多個的程序名，碰不到遊戲）----
Remove-Item Env:PSA_CLIENT -ErrorAction SilentlyContinue
$psi = New-Object Diagnostics.ProcessStartInfo $psexe, ('-NoProfile -NonInteractive -ExecutionPolicy Bypass -File "' + (Join-Path $PSScriptRoot 'serve.ps1') + '" -IdleMin 1')
$psi.UseShellExecute = $false; $psi.RedirectStandardInput = $true; $psi.RedirectStandardOutput = $true; $psi.CreateNoWindow = $true
$psi.StandardOutputEncoding = New-Object Text.UTF8Encoding $false
$sp = [Diagnostics.Process]::Start($psi)
function SrvRead { while ($true) { $l = $sp.StandardOutput.ReadLine(); if ($null -eq $l) { return $null }; $i = $l.IndexOf([string][char]0x1e + 'PSA '); if ($i -ge 0) { return ($l.Substring($i + 5) | ConvertFrom-Json) } } }
$ready = SrvRead
$res = @()
$n = 0
foreach ($cl in @('PsaNoSuchClient9', 'PsaNoSuchClient8', 'svchost')) {
  $n++; $sp.StandardInput.WriteLine((@{ id = $n; script = 'gui'; pos = @('info'); client = $cl } | ConvertTo-Json -Compress)); $sp.StandardInput.Flush()
  $res += , (SrvRead)
}
$sp.StandardInput.WriteLine('{"id":99,"cmd":"quit"}'); $sp.StandardInput.Flush(); [void]$sp.WaitForExit(10000)
Check "serve.ps1 ready" ($ready.ready)
Check "serve.ps1 client=PsaNoSuchClient9 → rc 1、訊息帶該名 ($($res[0].err.Trim()))" ($res[0].rc -eq 1 -and $res[0].err -match 'PsaNoSuchClient9 沒有在執行')
Check "serve.ps1 下一個請求換 client=PsaNoSuchClient8（不沿用上一個）" ($res[1].rc -eq 1 -and $res[1].err -match 'PsaNoSuchClient8 沒有在執行')
Check "serve.ps1 client=svchost（同名多個）→ rc 6" ($res[2].rc -eq 6)

# ---- 5) 解析檢查 ----
foreach ($f in 'psawin', 'gui', 'serve', 'stat', 'ocr', 'findmark', 'titlematch', ('digit' + 'match'), 'mirror') {
  $errs = $null; [void][Management.Automation.Language.Parser]::ParseFile((Join-Path $PSScriptRoot "$f.ps1"), [ref]$null, [ref]$errs)
  Check "$f.ps1 解析無誤" ($errs.Count -eq 0)
}

if ($null -eq $saveClient) { Remove-Item Env:PSA_CLIENT -ErrorAction SilentlyContinue } else { $env:PSA_CLIENT = $saveClient }
"fail=$fail"
exit $fail
