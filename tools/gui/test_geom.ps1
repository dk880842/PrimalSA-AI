# 座標換算層離線測試（不碰遊戲）：psageom.ps1 的換算數學、2880×1659 恆等（與舊版公式 / 舊 DrawImage 路徑逐位元組相同）、
# 往返誤差、PSA_GEOM=off（Off 旗標）、fit 尺寸計算。由 test_geom.py 呼叫；輸出 PASS / FAIL 行，最後 SUMMARY。
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
Add-Type -AssemblyName System.Drawing
. (Join-Path $PSScriptRoot 'psageom.ps1')
$script:fail = 0; $script:total = 0
function Check($name, $ok, $detail = '') {
  $script:total++
  if ($ok) { "PASS $name" } else { $script:fail++; "FAIL $name $detail" }
}

# --- 幾何判斷 ---
$g0 = Get-PsaGeom 2880 1659
Check '2880x1659 = 恆等 / 同比例 / Sx=Sy=2' ($g0.Identity -and $g0.Proportional -and $g0.Sx -eq 2.0 -and $g0.Sy -eq 2.0 -and $g0.ShotW -eq 1440 -and $g0.ShotH -eq 830 -and $g0.Layout -eq '2880x1659')
$g1 = Get-PsaGeom 1728 995
Check '1728x995 同比例、Sx=1.2、Sy=995/829.5、shot 1440x830' ($g1.Proportional -and -not $g1.Identity -and [Math]::Abs($g1.Sx - 1.2) -lt 1e-12 -and [Math]::Abs($g1.Sy - 995/829.5) -lt 1e-12 -and $g1.ShotW -eq 1440 -and $g1.ShotH -eq 830 -and $g1.Layout -eq '2880x1659')
$g2 = Get-PsaGeom 1920 1017
Check '1920x1017 不同比例 → 舊行為 Sx=Sy=2、shot 960x508、Layout=1920x1017' (-not $g2.Proportional -and $g2.Sx -eq 2.0 -and $g2.Sy -eq 2.0 -and $g2.ShotW -eq 960 -and $g2.ShotH -eq 508 -and $g2.Layout -eq '1920x1017')
$g3 = Get-PsaGeom 1920 1009
Check '1920x1009（最大化外接）不同比例' (-not $g3.Proportional -and $g3.Layout -eq '1920x1009')
$g4 = Get-PsaGeom 1728 995 2 $true
Check 'PSA_GEOM=off（Off）：1728x995 退回舊行為 Sx=Sy=2、shot 864x498' (-not $g4.Proportional -and $g4.Sx -eq 2.0 -and $g4.ShotW -eq 864 -and $g4.ShotH -eq 498 -and $g4.Layout -eq '1728x995')
$g5 = Get-PsaGeom 2880 1659 2 $true
Check 'PSA_GEOM=off：2880x1659 結果與預設相同（Sx / shot）' ($g5.Sx -eq 2.0 -and $g5.Sy -eq 2.0 -and $g5.ShotW -eq 1440 -and $g5.ShotH -eq 830 -and -not $g5.Proportional -and $g5.Identity)
$g6 = Get-PsaGeom 1728 996
Check '高度差 1 px 仍算同比例；差 2 px 不算' ($g6.Proportional -and -not (Get-PsaGeom 1728 998).Proportional)
Check '寬 < 1440 不算同比例' (-not (Get-PsaGeom 1152 663).Proportional)
$g7 = Get-PsaGeom 3840 2212
Check '3840x2212（比 2880 大）同比例、Sx 約 2.667' ($g7.Proportional -and [Math]::Abs($g7.Sx - 3840/1440) -lt 1e-12)

# --- 恆等：與舊公式逐點相同（含小數座標，drag 內插會出現） ---
$bad = 0; $cnt = 0
$xs = @(0, 1, 0.5, 1.5, 2.5, 100.25, 462, 763, 763.5, 948, 1439, 1439.9, 1440)
$ys = @(0, 1, 0.5, 2.5, 99.75, 335, 760, 829, 829.5, 830)
foreach ($x in $xs) { foreach ($y in $ys) {
  $q = Convert-PsaPoint $g0 $x $y
  $ox = [int]([double]$x * 2); $oy = [int]([double]$y * 2)
  $cnt++; if ($q[0] -ne $ox -or $q[1] -ne $oy) { $bad++ }
} }
Check "恆等：$cnt 個點（含小數、邊界、超出）與舊 [int](x*Scale) 完全相同（含不夾）" ($bad -eq 0) "bad=$bad"
$bad = 0
foreach ($x in $xs) { foreach ($y in $ys) {
  $q = Convert-PsaPoint $g2 $x $y   # 1920x1017 舊行為也不夾
  if ($q[0] -ne [int]([double]$x * 2) -or $q[1] -ne [int]([double]$y * 2)) { $bad++ }
} }
Check '1920x1017 舊行為：與舊公式相同' ($bad -eq 0)
# ToLParam 用的位元運算（gui.ps1 內同一式）恆等時不變
$q = Convert-PsaPoint $g0 763 760; $lp = [IntPtr](($q[1] -shl 16) -bor ($q[0] -band 0xffff)); $old = [IntPtr]((([int](760.0 * 2)) -shl 16) -bor (([int](763.0 * 2)) -band 0xffff))
Check 'lParam 恆等相同' ($lp -eq $old)

# --- 1728x995：換算表與往返誤差 ---
$maxErr = 0.0; $bad = 0; $cnt = 0
foreach ($x in 0..1439) { if ($x % 37 -ne 0) { continue }
  foreach ($y in 0..829) { if ($y % 41 -ne 0) { continue }
    $q = Convert-PsaPoint $g1 $x $y
    $bx = $q[0] / $g1.Sx; $by = $q[1] / $g1.Sy      # 反算回截圖座標
    $e = [Math]::Max([Math]::Abs($bx - $x), [Math]::Abs($by - $y)); if ($e -gt $maxErr) { $maxErr = $e }
    if ($q[0] -lt 0 -or $q[0] -gt 1727 -or $q[1] -lt 0 -or $q[1] -gt 994) { $bad++ }
    $cnt++
} }
Check "1728x995 往返誤差 ≤ 0.5 / 1.1995（$cnt 點，最大 $([Math]::Round($maxErr, 4)) 截圖 px）且都在客戶區內" ($maxErr -le 0.5 / 1.19952 + 1e-9 -and $bad -eq 0)
$exp = @{ '763,760' = @(916, 912); '605,70' = @(726, 84); '0,0' = @(0, 0) }   # 手算：x*1.2 / y*1.19952 取整（偶數進位）
$bad = 0; foreach ($k in $exp.Keys) { $v = $k -split ','; $q = Convert-PsaPoint $g1 $v[0] $v[1]; if ($q[0] -ne $exp[$k][0] -or $q[1] -ne $exp[$k][1]) { $bad++; "  $k -> $($q -join ',') 預期 $($exp[$k] -join ',')" } }
Check '1728x995 固定輸入表（763,760 → 916,912 等）' ($bad -eq 0)
$q = Convert-PsaPoint $g1 1440 830; $q2 = Convert-PsaPoint $g1 -5 -5
Check '1728x995 超出範圍夾在客戶區內（1440,830 → 1727,994；負值 → 0）' ($q[0] -eq 1727 -and $q[1] -eq 994 -and $q2[0] -eq 0 -and $q2[1] -eq 0)
$q = Convert-PsaPoint $g4 100 100
Check 'PSA_GEOM=off：1728x995 的 (100,100) → 200,200（舊公式）' ($q[0] -eq 200 -and $q[1] -eq 200)

# --- shot：2880×1659 與舊 DrawImage 路徑逐位元組相同；1728×995 / 1920×1017 尺寸 ---
function New-TestBmp($w, $h) {
  $b = New-Object System.Drawing.Bitmap $w, $h
  $rnd = New-Object System.Random 12345
  for ($y = 0; $y -lt $h; $y += 3) { for ($x = 0; $x -lt $w; $x += 3) { $b.SetPixel($x, $y, [System.Drawing.Color]::FromArgb(255, ($x * 7 + $y) % 256, ($y * 5) % 256, $rnd.Next(256))) } }
  $b
}
function Png-Bytes($bmp) { $ms = New-Object IO.MemoryStream; $bmp.Save($ms, [System.Drawing.Imaging.ImageFormat]::Png); $ms.ToArray() }
function Old-Shot($full, [double]$Scale) {   # 舊 gui.ps1 shot 的縮圖段（原樣）
  $w = [int]($full.Width / $Scale); $hh = [int]($full.Height / $Scale)
  $small = New-Object System.Drawing.Bitmap $w, $hh
  $g = [System.Drawing.Graphics]::FromImage($small)
  $g.InterpolationMode = 'HighQualityBicubic'; $g.DrawImage($full, 0, 0, $w, $hh); $g.Dispose()
  $small
}
function Same-Bytes($a, $b) { if ($a.Length -ne $b.Length) { return $false }; for ($i = 0; $i -lt $a.Length; $i++) { if ($a[$i] -ne $b[$i]) { return $false } }; $true }
$full = New-TestBmp 2880 1659
$o = Old-Shot $full 2; $n = Get-PsaShot $full $g0
Check "shot 恆等：2880x1659 → $($n.Width)x$($n.Height)，PNG 位元組與舊路徑相同" ((Same-Bytes (Png-Bytes $o) (Png-Bytes $n)) -and $n.Width -eq 1440 -and $n.Height -eq 830)
$o.Dispose(); $n.Dispose()
$n = Get-PsaShot $full $g5   # PSA_GEOM=off 的 2880x1659
$o = Old-Shot $full 2
Check 'shot PSA_GEOM=off（2880x1659）與舊路徑相同' (Same-Bytes (Png-Bytes $o) (Png-Bytes $n)); $o.Dispose(); $n.Dispose(); $full.Dispose()
$full = New-TestBmp 1728 995
$n = Get-PsaShot $full $g1
Check "shot 1728x995 → 1440x830（實得 $($n.Width)x$($n.Height)）" ($n.Width -eq 1440 -and $n.Height -eq 830); $n.Dispose()
$n = Get-PsaShot $full $g4; $o = Old-Shot $full 2
Check "shot 1728x995 + PSA_GEOM=off → 864x498 且與舊路徑相同" ((Same-Bytes (Png-Bytes $o) (Png-Bytes $n)) -and $n.Width -eq 864 -and $n.Height -eq 498); $n.Dispose(); $o.Dispose(); $full.Dispose()
$full = New-TestBmp 1920 1017
$n = Get-PsaShot $full $g2; $o = Old-Shot $full 2
Check "shot 1920x1017（舊版面）→ $($n.Width)x$($n.Height)，與舊路徑相同" ((Same-Bytes (Png-Bytes $o) (Png-Bytes $n)) -and $n.Width -eq 960 -and $n.Height -eq 508); $n.Dispose(); $o.Dispose(); $full.Dispose()

# --- fit 尺寸計算 ---
$f = Get-PsaFitSize 1920 1032 16 31
Check "fit 1920x1032 工作區 → 1728x995（實得 $($f -join 'x')）" ($f[0] -eq 1728 -and $f[1] -eq 995)
$f = Get-PsaFitSize 1920 1032 16 31 1700
Check 'fit 指定寬 1700 → 1700x979' ($f[0] -eq 1700 -and $f[1] -eq 979)
$f = Get-PsaFitSize 2560 1392 16 31
Check "fit 2560x1392 → 2304x1327（寬量化 144 倍數，實得 $($f -join 'x')）" ($f[0] -eq 2304 -and $f[1] -eq 1327)
$f = Get-PsaFitSize 1366 728 16 31
Check "fit 1366x728（放不下 1440，不量化）→ 實得 $($f -join 'x')，高 ≤ 697" ($f[1] -le 697 -and $f[0] -lt 1440 -and $f[0] -gt 1000)
$f = Get-PsaFitSize 3000 1700 16 31
Check "fit 3000x1700 → 寬 2880 → 恆等 2880x1659（實得 $($f -join 'x')）" ($f[0] -eq 2880 -and $f[1] -eq 1659)
$allProp = $true
foreach ($wa in @(@(1920, 1032), @(1920, 1080), @(2560, 1392), @(2560, 1440), @(3440, 1392), @(1600, 860))) {
  $f = Get-PsaFitSize $wa[0] $wa[1] 16 31
  $gg = Get-PsaGeom $f[0] $f[1]
  if ($f[0] -ge 1440 -and (-not $gg.Proportional -or $f[0] + 16 -gt $wa[0] -or $f[1] + 31 -gt $wa[1])) { $allProp = $false; "  $($wa -join 'x') -> $($f -join 'x')" }
}
Check 'fit 各種工作區：結果同比例（換算層認得）且放得進工作區' $allProp

# --- P2：截圖端的框 / 點換算（邏輯客戶區像素 → 實體像素） ---
$ga = Get-PsaGeomAuto 1728 995
Check 'Get-PsaGeomAuto：未設 PSA_GEOM=off 時 = Get-PsaGeom（1728x995 同比例）' ($ga.Proportional -and $ga.Layout -eq '2880x1659' -and $ga.Sx -eq $g1.Sx)
$bx = Convert-PsaBox $g0 150 186 180 46
Check 'Convert-PsaBox 恆等：框原樣（含不夾範圍）' ($bx[0] -eq 150 -and $bx[1] -eq 186 -and $bx[2] -eq 180 -and $bx[3] -eq 46)
$bx = Convert-PsaBox $g0 3000 1700 50 60
Check 'Convert-PsaBox 恆等：超出客戶區也原樣（舊版不夾）' ($bx[0] -eq 3000 -and $bx[2] -eq 50 -and $bx[3] -eq 60)
$bx = Convert-PsaBox $g2 1530 98 190 30
Check 'Convert-PsaBox 1920x1017 舊版面：框原樣（版面表本來就是客戶區像素）' ($bx[0] -eq 1530 -and $bx[1] -eq 98 -and $bx[2] -eq 190 -and $bx[3] -eq 30)
$bx = Convert-PsaBox $g4 150 186 180 46
Check 'Convert-PsaBox PSA_GEOM=off：1728x995 也原樣（舊行為）' ($bx[0] -eq 150 -and $bx[2] -eq 180)
$bx = Convert-PsaBox $g1 150 186 180 46      # HUD 等級框
Check "Convert-PsaBox 1728x995：等級框 → 90,112,108,27（實得 $($bx -join ','))" ($bx[0] -eq 90 -and $bx[1] -eq 112 -and $bx[2] -eq 108 -and $bx[3] -eq 27)
# 相鄰框無縫（右邊界 = 下一框左邊界）、整張範圍夾在客戶區內、至少 1 px
$a = Convert-PsaBox $g1 100 50 37 20; $b = Convert-PsaBox $g1 137 50 41 20
Check '相鄰邏輯框換成實體後仍相接（無縫、不重疊）' (($a[0] + $a[2]) -eq $b[0])
$bx = Convert-PsaBox $g1 0 0 2880 1659
Check '整個客戶區 → 0,0,1728,995' ($bx[0] -eq 0 -and $bx[1] -eq 0 -and $bx[2] -eq 1728 -and $bx[3] -eq 995)
$bx = Convert-PsaBox $g1 2870 1650 100 100
Check '超出客戶區的框夾進範圍、至少 1 px' (($bx[0] + $bx[2]) -le 1728 -and ($bx[1] + $bx[3]) -le 995 -and $bx[2] -ge 1 -and $bx[3] -ge 1)
$cp = Convert-PsaClientPoint $g0 344 112
Check 'Convert-PsaClientPoint 恆等：點原樣' ($cp[0] -eq 344 -and $cp[1] -eq 112)
$cp = Convert-PsaClientPoint $g1 344 112
Check "Convert-PsaClientPoint 1728x995：HP 血條起點 344,112 → 206,67（實得 $($cp -join ','))" ($cp[0] -eq 206 -and $cp[1] -eq 67)
# 全部 HUD 框（stat / digitmatch 的 2880x1659 版面）換成實體後都在客戶區內、尺寸約為 0.6 倍
$hud = @(@(150,186,180,46), @(340,92,200,44), @(340,166,200,38), @(560,158,160,46), @(750,92,200,44), @(2220,150,360,46), @(2250,178,300,34))
$okHud = $true
foreach ($hb in $hud) { $q = Convert-PsaBox $g1 $hb[0] $hb[1] $hb[2] $hb[3]
  if ($q[0] -lt 0 -or $q[1] -lt 0 -or ($q[0] + $q[2]) -gt 1728 -or ($q[1] + $q[3]) -gt 995 -or [Math]::Abs($q[2] - $hb[2] * 0.6) -gt 1.01 -or [Math]::Abs($q[3] - $hb[3] * 0.6) -gt 1.01) { $okHud = $false; "  box $($hb -join ',') -> $($q -join ',')" } }
Check 'HUD 7 個框換成 1728x995：在客戶區內、寬高為 0.6 倍 ±1' $okHud

"SUMMARY $($script:total - $script:fail)/$($script:total)"
if ($script:fail) { exit 1 }
