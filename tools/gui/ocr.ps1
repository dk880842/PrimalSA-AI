# 通用區域 OCR（背景截圖 PrintWindow + Windows 內建 OCR；不搶焦點）。座標 = 截圖座標（客戶區 ×1/2）。
# 用法：ocr.ps1 X Y W H [-Zoom 3] [-Dark 150]   → 輸出一行 JSON：{"ok":true,"lines":[{"text":"伐木證書","y":310,"x":205},...]}
#   -Dark N：深色字二值化門檻（max(R,G,B) < N 視為字；0 = 不二值化直接放大）。任務追蹤標題是深棕字 → 預設 150。
#   -Light N：亮字二值化門檻（min(R,G,B) > N 視為字；白色數字用，例 200；優先於 -Dark）。
#   -Zooms "2,3,4,5,6"：同一張截圖用多個放大倍數各 OCR 一次，結果合併（Windows OCR 對同一圖換倍數結果差很多，任務追蹤標題用 2～6 倍才讀得全）。
#   -Green N：綠字二值化（G > N 且 G - max(R,B) > 60 視為字；優先於 -Light / -Dark）。背包刪除管理提示窗的綠字清單 (40,240,0) 用，
#     米黃底、白色「是否批量刪除道具?」都變白 → 只剩清單（2026-10-14：不二值化時 Windows OCR 常整行漏讀）。
#   -Image 路徑：改讀截圖檔（gui shot 存的 1440 寬或原始 2880 寬都可，依寬度換算），不碰遊戲；離線核對 OCR 參數 / 做 fixtures 用。
#   -Small 1：先把整張客戶區縮成跟 gui shot 同一張 1440 縮圖（psawin.ps1 ConvertTo-PsaSmall，HighQualityBicubic）再裁框放大，
#     讓實機讀到的像素跟截圖 / -Image 離線讀完全相同。預設 0 = 舊行為（直接從客戶區原生 2880 裁框縮放，其他呼叫者不受影響）。
#     2026-10-17 每日任務快速合成彈窗大字（黃字黑邊 16px）：-Image 讀 1440 截圖讀得出「合成弓箭8」，實機從原生 2880 取像 4 倍率全空（229）；
#     把截圖放大 2 倍模擬原生 → 3/4/5 倍全掉、只剩 2 倍。根因同 2e224bc（numglyph px vs spixel）。-Image 給 2880 原圖時 -Small 1 也會先縮。
#   每行的 x / y = 該行文字在截圖座標的中心。
param([int]$X, [int]$Y, [int]$Wd, [int]$Ht, [int]$Zoom = 3, [int]$Dark = 150, [string]$Zooms = "", [int]$Light = 0, [int]$Green = 0, [string]$Image = "", [int]$Small = 0)
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
Add-Type -AssemblyName System.Drawing, System.Runtime.WindowsRuntime
Add-Type @"
using System; using System.Runtime.InteropServices;
public class WO {
  [DllImport("user32.dll")] public static extern bool SetProcessDPIAware();
  [DllImport("user32.dll")] public static extern bool GetClientRect(IntPtr h, out RECT r);
  [DllImport("user32.dll")] public static extern bool IsIconic(IntPtr h);
  [DllImport("user32.dll")] public static extern bool PrintWindow(IntPtr h, IntPtr hdc, uint f);
  public struct RECT { public int L,T,R,B; }
  // 亮字二值化：min(R,G,B) > light 視為字（白色數字加深色描邊，例如寵物格等級）→ 轉成黑字白底
  // 2026-10-10 改 LockBits 逐列處理（GetPixel/SetPixel 一塊 780×540 約 215 ms → 約 28 ms）；
  // 只處理 Format32bppArgb（crop 新建的 Bitmap 預設就是），其他格式走舊的 GetPixel 版當保底。輸出每像素 B,G,R,A=255 與舊版逐位元組相同。
  public static void BinarizeLight(System.Drawing.Bitmap b, int light) { Bin(b, true, light); }
  public static void Binarize(System.Drawing.Bitmap b, int dark) { Bin(b, false, dark); }
  // light=true：min(R,G,B) > th 為字；false：max(R,G,B) < th 為字。字 → 黑、其他 → 白
  static void Bin(System.Drawing.Bitmap b, bool light, int th) {
    if (b.PixelFormat != System.Drawing.Imaging.PixelFormat.Format32bppArgb) { BinSlow(b, light, th); return; }
    int w = b.Width, h = b.Height;
    System.Drawing.Imaging.BitmapData d = b.LockBits(new System.Drawing.Rectangle(0, 0, w, h),
      System.Drawing.Imaging.ImageLockMode.ReadWrite, System.Drawing.Imaging.PixelFormat.Format32bppArgb);
    try {
      byte[] row = new byte[w * 4];
      for (int y = 0; y < h; y++) {
        IntPtr p = IntPtr.Add(d.Scan0, y * d.Stride);      // stride 為負時也正確
        Marshal.Copy(p, row, 0, row.Length);
        for (int x = 0; x < w; x++) {
          int i = x * 4; int bl = row[i], g = row[i + 1], r = row[i + 2];
          bool ink = light ? (Math.Min(r, Math.Min(g, bl)) > th) : (Math.Max(r, Math.Max(g, bl)) < th);
          byte v = ink ? (byte)0 : (byte)255;
          row[i] = v; row[i + 1] = v; row[i + 2] = v; row[i + 3] = 255;
        }
        Marshal.Copy(row, 0, p, row.Length);
      }
    } finally { b.UnlockBits(d); }
  }
  static void BinSlow(System.Drawing.Bitmap b, bool light, int th) {
    for (int y = 0; y < b.Height; y++) for (int x = 0; x < b.Width; x++) {
      var c = b.GetPixel(x, y);
      bool ink = light ? (Math.Min(c.R, Math.Min(c.G, c.B)) > th) : (Math.Max(c.R, Math.Max(c.G, c.B)) < th);
      b.SetPixel(x, y, ink ? System.Drawing.Color.Black : System.Drawing.Color.White);
    }
  }
}
"@ -ReferencedAssemblies System.Drawing
function Out-Json($o) { $o | ConvertTo-Json -Compress -Depth 4; exit 0 }
# 綠字二值化放獨立的型別 WOG、只在 -Green 時才編譯：常駐 server（serve.ps1）同一個 session 已載入舊版 WO，
# 改 WO 的原始碼會讓 Add-Type 報「型別已存在」→ 跑到一半的程序 OCR 全壞，所以 WO 區塊不動
if ($Green -gt 0) {
Add-Type @"
using System; using System.Runtime.InteropServices;
public class WOG {
  // G > th 且 G - max(R,B) > 60 → 黑字，其他 → 白（只處理 Format32bppArgb；crop 新建的 Bitmap 預設就是）
  public static void Green(System.Drawing.Bitmap b, int th) {
    int w = b.Width, h = b.Height;
    System.Drawing.Imaging.BitmapData d = b.LockBits(new System.Drawing.Rectangle(0, 0, w, h),
      System.Drawing.Imaging.ImageLockMode.ReadWrite, System.Drawing.Imaging.PixelFormat.Format32bppArgb);
    try {
      byte[] row = new byte[w * 4];
      for (int y = 0; y < h; y++) {
        IntPtr p = IntPtr.Add(d.Scan0, y * d.Stride);
        Marshal.Copy(p, row, 0, row.Length);
        for (int x = 0; x < w; x++) {
          int i = x * 4; int bl = row[i], g = row[i + 1], r = row[i + 2];
          byte v = (g > th && g - Math.Max(r, bl) > 60) ? (byte)0 : (byte)255;
          row[i] = v; row[i + 1] = v; row[i + 2] = v; row[i + 3] = 255;
        }
        Marshal.Copy(row, 0, p, row.Length);
      }
    } finally { b.UnlockBits(d); }
  }
}
"@ -ReferencedAssemblies System.Drawing
}
[WO]::SetProcessDPIAware() | Out-Null
$k = 2
if ($Image) {
  try { $full = New-Object System.Drawing.Bitmap $Image } catch { Out-Json @{ ok = $false; error = "讀不到截圖檔 $Image" } }
  $k = $full.Width / 1440.0
} else {
if (-not (Test-Path Function:\Find-PsaProcess)) { . (Join-Path $PSScriptRoot 'psawin.ps1') }   # 依 PSA_CLIENT 選遊戲程序（沒設 = PrimalSA；同名多個不操作）
$fp = Find-PsaProcess
if (-not $fp.ok) { Out-Json @{ ok = $false; error = (Get-PsaFindError $fp) } }
$h = $fp.proc.MainWindowHandle
if ([WO]::IsIconic($h)) { Out-Json @{ ok = $false; error = '遊戲視窗最小化' } }
$r = New-Object WO+RECT; [WO]::GetClientRect($h, [ref]$r) | Out-Null
$full = New-Object System.Drawing.Bitmap $r.R, $r.B
$g = [System.Drawing.Graphics]::FromImage($full); $dc = $g.GetHdc()
$ok = [WO]::PrintWindow($h, $dc, 3); $g.ReleaseHdc($dc); $g.Dispose()
if (-not $ok) { Out-Json @{ ok = $false; error = 'PrintWindow 失敗' } }
}
# -Small 1：縮成 gui shot 那張 1440 縮圖再裁（舊 server 已載入的 psawin 沒有 ConvertTo-PsaSmall 就重載）
if ($Small -gt 0 -and $k -gt 1.01) {
  if (-not (Test-Path Function:\ConvertTo-PsaSmall)) { . (Join-Path $PSScriptRoot 'psawin.ps1') }
  $sm = ConvertTo-PsaSmall $full $k; $full.Dispose(); $full = $sm; $k = 1
}
$null = [Windows.Media.Ocr.OcrEngine, Windows.Foundation, ContentType = WindowsRuntime]
$null = [Windows.Graphics.Imaging.SoftwareBitmap, Windows.Foundation, ContentType = WindowsRuntime]
$null = [Windows.Storage.Streams.InMemoryRandomAccessStream, Windows.Storage.Streams, ContentType = WindowsRuntime]
$asTask = [System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object {
  $_.Name -eq 'AsTask' -and $_.GetParameters().Count -eq 1 -and $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1' } | Select-Object -First 1
function Await($op, [Type]$t) { $task = $asTask.MakeGenericMethod($t).Invoke($null, @($op)); $task.Wait() | Out-Null; $task.Result }
$null = [Windows.Globalization.Language, Windows.Globalization, ContentType = WindowsRuntime]
$engine = [Windows.Media.Ocr.OcrEngine]::TryCreateFromLanguage((New-Object Windows.Globalization.Language 'zh-Hant-TW'))
if (-not $engine) { $engine = [Windows.Media.Ocr.OcrEngine]::TryCreateFromUserProfileLanguages() }
$px = $X * $k; $py = $Y * $k; $pw = $Wd * $k; $ph = $Ht * $k
function OcrZoom([int]$z) {
  $crop = New-Object System.Drawing.Bitmap ([int]($Wd * $z)), ([int]($Ht * $z))
  $g = [System.Drawing.Graphics]::FromImage($crop); $g.InterpolationMode = 'HighQualityBicubic'
  $g.DrawImage($full, (New-Object System.Drawing.Rectangle 0, 0, $crop.Width, $crop.Height), $px, $py, $pw, $ph, 'Pixel'); $g.Dispose()
  if ($Green -gt 0) { [WOG]::Green($crop, $Green) } elseif ($Light -gt 0) { [WO]::BinarizeLight($crop, $Light) } elseif ($Dark -gt 0) { [WO]::Binarize($crop, $Dark) }
  $pad = New-Object System.Drawing.Bitmap ($crop.Width + 80), ($crop.Height + 80)
  $g = [System.Drawing.Graphics]::FromImage($pad); $g.Clear([System.Drawing.Color]::White); $g.DrawImage($crop, 40, 40); $g.Dispose()
  $crop.Dispose(); $crop = $pad
  if ($env:OCR_DEBUG) { $crop.Save($env:OCR_DEBUG) }
  $ms = New-Object IO.MemoryStream; $crop.Save($ms, [System.Drawing.Imaging.ImageFormat]::Bmp); $crop.Dispose()
  $ras = New-Object Windows.Storage.Streams.InMemoryRandomAccessStream
  $out = $ras.GetOutputStreamAt(0)
  $wr = New-Object Windows.Storage.Streams.DataWriter $out
  $wr.WriteBytes($ms.ToArray()); $null = Await ($wr.StoreAsync()) ([uint32]); $null = Await ($wr.FlushAsync()) ([bool])
  $dec = Await ([Windows.Graphics.Imaging.BitmapDecoder]::CreateAsync($ras)) ([Windows.Graphics.Imaging.BitmapDecoder])
  $sb = Await ($dec.GetSoftwareBitmapAsync()) ([Windows.Graphics.Imaging.SoftwareBitmap])
  $res = Await ($engine.RecognizeAsync($sb)) ([Windows.Media.Ocr.OcrResult])
  $r2 = @()
  foreach ($ln in $res.Lines) {
    $x0 = 1e9; $x1 = 0; $y0 = 1e9; $y1 = 0
    foreach ($wo in $ln.Words) { $b = $wo.BoundingRect; if ($b.X -lt $x0) { $x0 = $b.X }; if ($b.X + $b.Width -gt $x1) { $x1 = $b.X + $b.Width }; if ($b.Y -lt $y0) { $y0 = $b.Y }; if ($b.Y + $b.Height -gt $y1) { $y1 = $b.Y + $b.Height } }
    $r2 += [ordered]@{ text = ($ln.Text -replace '\s', ''); x = [int]($X + (($x0 + $x1) / 2 - 40) / $z); y = [int]($Y + (($y0 + $y1) / 2 - 40) / $z); zoom = $z }
  }
  $r2
}
$zl = if ($Zooms) { $Zooms.Split(',') | ForEach-Object { [int]$_ } } else { @($Zoom) }
$lines = @()
foreach ($z in $zl) { $lines += OcrZoom $z }
$full.Dispose()
Out-Json ([ordered]@{ ok = $true; lines = $lines })
