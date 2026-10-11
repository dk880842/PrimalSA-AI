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

# ---- P2：截圖端（stat / digitmatch / ocr / titlematch / findmark）共用 ----
# 這些腳本自己 PrintWindow 取「實體客戶區」全解析度圖，區域框一律以「邏輯客戶區像素」（2880×1659 座標系；截圖座標 ×2）給，
# 同比例的實體視窗（例 1728×995）由下面兩個函式換成實體像素框 / 點；OCR 直接裁實體像素（不先縮成 1440 再放大），
# 輸出尺寸仍是「邏輯框寬高 × 放大倍數」（與筆電相同大小，文字等效放大倍數自動依實體 / 邏輯比例調整）。
# 2880×1659（恆等）與不同比例 / PSA_GEOM=off（舊行為）：原樣回傳，與舊版逐位元組相同。

# 依環境變數 PSA_GEOM=off 決定要不要走換算層（gui.ps1 另有 -Scale 覆蓋；截圖端沒有 -Scale）
function Get-PsaGeomAuto([int]$CW, [int]$CH) { Get-PsaGeom $CW $CH 2 ($env:PSA_GEOM -eq 'off') }

# 四捨五入（0.5 進位，不用銀行家捨入；框邊界要單調）
function Round-PsaHalfUp([double]$Val) { [int][Math]::Floor($Val + 0.5) }

# 邏輯客戶區像素框 (x, y, w, h) → 實體客戶區像素框（int[4]）。兩端各自取整再相減，相鄰框不會產生縫；夾在客戶區內且至少 1 px
function Convert-PsaBox($G, $bx, $by, $bw, $bh) {
  if (-not $G.Proportional -or $G.Identity) { return , @([int]$bx, [int]$by, [int]$bw, [int]$bh) }
  $fx = $G.Sx / 2.0; $fy = $G.Sy / 2.0
  $x0 = [Math]::Max(0, [Math]::Min($G.CW - 1, (Round-PsaHalfUp ($bx * $fx)))); $y0 = [Math]::Max(0, [Math]::Min($G.CH - 1, (Round-PsaHalfUp ($by * $fy))))
  $x1 = [Math]::Max($x0 + 1, [Math]::Min($G.CW, (Round-PsaHalfUp (($bx + $bw) * $fx)))); $y1 = [Math]::Max($y0 + 1, [Math]::Min($G.CH, (Round-PsaHalfUp (($by + $bh) * $fy))))
  , @($x0, $y0, ($x1 - $x0), ($y1 - $y0))
}

# 邏輯客戶區像素點 → 實體客戶區像素點（int[2]；血條掃描線用）
function Convert-PsaClientPoint($G, $px, $py) {
  if (-not $G.Proportional -or $G.Identity) { return , @([int]$px, [int]$py) }
  $fx = $G.Sx / 2.0; $fy = $G.Sy / 2.0
  , @([Math]::Max(0, [Math]::Min($G.CW - 1, (Round-PsaHalfUp ($px * $fx)))), [Math]::Max(0, [Math]::Min($G.CH - 1, (Round-PsaHalfUp ($py * $fy)))))
}

# 讀圖檔成 32bpp / 96dpi 的 Bitmap（離線測試用 -Image；DrawImage 不會被檔案內的 dpi 影響）。讀不到回 $null
function Open-PsaImage([string]$Path) {
  try { $src = New-Object System.Drawing.Bitmap $Path } catch { return $null }
  $bm = New-Object System.Drawing.Bitmap $src.Width, $src.Height, ([System.Drawing.Imaging.PixelFormat]::Format32bppArgb)
  $bm.SetResolution(96, 96)
  $gr = [System.Drawing.Graphics]::FromImage($bm); $gr.DrawImage($src, 0, 0, $src.Width, $src.Height); $gr.Dispose(); $src.Dispose()
  $bm
}
