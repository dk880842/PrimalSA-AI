# 座標換算層（P1，計畫 notes/plan-display-scale.md）：純數學，不碰 Win32 / 遊戲，由 gui.ps1 dot-source，也給離線測試 test_geom.ps1 用。
# 邏輯座標系 = 2880×1659 客戶區（截圖座標 1440×830 = 它 ÷2）。實際客戶區與它「同長寬比」（高度差 ≤ 1 px）時，
# 截圖座標 → 實體客戶區像素 = 乘 Sx = W/1440、Sy = H/829.5（P0 實測純等比例，不需每軸校正）。
# 2880×1659 時 Sx = Sy = 2 恰為舊行為（恆等：shot / click / pixel 輸出與舊版逐位元組相同）。
# 其他比例（例 1920×1017）或環境變數 PSA_GEOM=off 或明確給 -Scale：舊行為（Sx = Sy = Scale，shot = 實體 / Scale）。
# 注意：PowerShell 變數不分大小寫（$H 與 $h 是同一個），本檔變數一律用不會與 gui.ps1 的 $h / $r / $p 撞名的名稱。

$script:PsaLogW = 2880
$script:PsaLogH = 1659
$script:PsaShotW = 1440
$script:PsaShotH = 830        # 829.5 取偶數進位，與舊版 [int](1659/2) 相同

# 幾何物件：實體客戶區 (CW, CH) → 換算係數。Off = 強制舊行為
function Get-PsaGeom([int]$CW, [int]$CH, [double]$Scale = 2, [bool]$Off = $false) {
  $prop = (-not $Off) -and $CW -ge 1440 -and [Math]::Abs([long]$CH * $script:PsaLogW - [long]$CW * $script:PsaLogH) -le $script:PsaLogW
  if ($prop) {
    $sx = $CW / 1440.0; $sy = $CH / 829.5
    $shotW = $script:PsaShotW; $shotH = $script:PsaShotH
  } else {
    $sx = $Scale; $sy = $Scale
    $shotW = [int]($CW / $Scale); $shotH = [int]($CH / $Scale)
  }
  [pscustomobject]@{
    CW = $CW; CH = $CH; Sx = $sx; Sy = $sy; Scale = $Scale
    Proportional = $prop                                  # 與 2880×1659 同長寬比（換算可用）
    Identity = ($CW -eq $script:PsaLogW -and $CH -eq $script:PsaLogH)   # 2880×1659 本尊
    Layout = $(if ($prop) { '2880x1659' } else { "${CW}x${CH}" })      # 「套哪套座標常數」的邏輯版面
    ShotW = $shotW; ShotH = $shotH
  }
}

# 截圖座標 (x, y) → 實體客戶區像素（int 陣列）。取整沿用舊版的 [int] 轉型（四捨五入到偶數），恆等時與舊版相同；
# 非恆等時夾在客戶區內（舊版不夾，恆等 / 舊行為也不夾，輸出不變）
function Convert-PsaPoint($G, $x, $y) {
  $cx = [int]([double]$x * $G.Sx); $cy = [int]([double]$y * $G.Sy)
  if ($G.Proportional -and -not $G.Identity) {
    $cx = [Math]::Max(0, [Math]::Min($G.CW - 1, $cx)); $cy = [Math]::Max(0, [Math]::Min($G.CH - 1, $cy))
  }
  , @($cx, $cy)
}

# 全解析度截圖 → 截圖座標系縮圖（Bitmap；呼叫端負責 Dispose）。恆等 / 舊行為 = 舊版 DrawImage 路徑
function Get-PsaShot($Full, $G) {
  $small = New-Object System.Drawing.Bitmap $G.ShotW, $G.ShotH
  $gr = [System.Drawing.Graphics]::FromImage($small)
  $gr.InterpolationMode = 'HighQualityBicubic'; $gr.DrawImage($Full, 0, 0, $G.ShotW, $G.ShotH); $gr.Dispose()
  $small
}

# fit 的目標客戶區尺寸。$WaW/$WaH = 工作區、$ExW/$ExH = 視窗「可見」框架佔的寬 / 高（不含 DWM 隱形邊框）。
# 沒指定寬度：取放得下的最大同比例寬，再往下取 144（= 2880 的 5%）的倍數（螢幕 1920×1032 → 1728×995，倍率剛好 0.6）；
# 放不下 1440 時不量化（盡量大）。指定寬度則照給（高 = round(W×1659/2880)，不檢查放不放得下，由呼叫端決定）
function Get-PsaFitSize([int]$WaW, [int]$WaH, [int]$ExW, [int]$ExH, [int]$ReqW = 0) {
  if ($ReqW -gt 0) { $cw = $ReqW }
  else {
    $availW = $WaW - $ExW; $availH = $WaH - $ExH
    $cw = [Math]::Min($availW, [int][Math]::Floor($availH * $script:PsaLogW / $script:PsaLogH))
    # 修正浮點 / 取整讓 ch 超出：往下收斂
    while ($cw -gt 1 -and [int][Math]::Round($cw * $script:PsaLogH / $script:PsaLogW, [MidpointRounding]::AwayFromZero) -gt $availH) { $cw-- }
    if ($cw -ge 1440) { $cw = [int]([Math]::Floor($cw / 144.0) * 144) }
  }
  $ch = [int][Math]::Round($cw * $script:PsaLogH / $script:PsaLogW, [MidpointRounding]::AwayFromZero)
  , @($cw, $ch)
}
