# 找畫面上的黃色色塊（NPC 頭上的任務標記「?」「!」候選；背景截圖 PrintWindow，不搶焦點）。座標 = 截圖座標（1440×830，= 邏輯客戶區 ×1/2）。
#   客戶區與 2880×1659 同長寬比（例 1728×995）時，每個截圖座標點取「最近的實體像素」做連通元件（psageom.ps1 換算；色塊大小 / n 仍是截圖座標，與筆電可比）；
#   -Crop 的裁圖也直接裁實體像素（輸出尺寸 = 框寬高 × Zoom，與筆電相同）。恆等（2880×1659）/ 其他比例 / PSA_GEOM=off = 舊行為（取每 2×2 的左上點）。-Image 檔.png：離線讀圖（測試用）。
# 用法：findmark.ps1 [-Crop x,y,w,h -Out file.png [-Zoom 4]]（另存放大裁圖，看標記細節用）  → 一行 JSON：{"ok":true,"blobs":[{"x":720,"y":285,"w":13,"h":24,"n":180,"mode":"..."}...]}
#   x,y = 色塊中心；w,h = 外框；n = 符合顏色的像素數（截圖座標 1/2 縮小後）。形狀 / 位置過濾交給呼叫端（quest.py）。
#   黃色判定：R>225 且 160<G<235 且 B<70（飽和金黃，NPC 名字白黃字 B 較高 / G 較亮，由 quest.py 以形狀排除）。
param([string]$Crop, [string]$Out, [int]$Zoom = 4, [string]$Image)
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
Add-Type -AssemblyName System.Drawing
Add-Type -TypeDefinition @"
using System; using System.Collections.Generic; using System.Runtime.InteropServices; using System.Drawing; using System.Drawing.Imaging;
public class FM {
  [DllImport("user32.dll")] public static extern bool SetProcessDPIAware();
  [DllImport("user32.dll")] public static extern bool GetClientRect(IntPtr h, out RECT r);
  [DllImport("user32.dll")] public static extern bool IsIconic(IntPtr h);
  [DllImport("user32.dll")] public static extern bool PrintWindow(IntPtr h, IntPtr hdc, uint f);
  public struct RECT { public int L,T,R,B; }
  // 縮成 1/2（取每 2×2 的左上點）後做連通元件；回傳 "cx,cy,w,h,n" 字串清單
  public static List<string> Blobs(Bitmap bmp) { return BlobsS(bmp, bmp.Width / 2, bmp.Height / 2, 2.0, 2.0); }
  // 截圖座標 (x, y) 取實體 (round(x·sx), round(y·sy))（夾在圖內）；W×H = 截圖座標大小。sx = sy = 2 時 = 舊版 Blobs（(x*2, y*2)）
  public static List<string> BlobsS(Bitmap bmp, int W, int H, double sx, double sy) {
    BitmapData d = bmp.LockBits(new Rectangle(0, 0, bmp.Width, bmp.Height), ImageLockMode.ReadOnly, PixelFormat.Format32bppArgb);
    byte[] buf = new byte[d.Stride * bmp.Height]; Marshal.Copy(d.Scan0, buf, 0, buf.Length); bmp.UnlockBits(d);
    bool[] m = new bool[W * H];
    for (int y = 0; y < H; y++) for (int x = 0; x < W; x++) {
      int qx = Math.Min(bmp.Width - 1, (int)Math.Floor(x * sx + 0.5)), qy = Math.Min(bmp.Height - 1, (int)Math.Floor(y * sy + 0.5));
      int i = qy * d.Stride + qx * 4; int b = buf[i], g = buf[i + 1], r = buf[i + 2];
      m[y * W + x] = r > 225 && g > 160 && g < 235 && b < 70;
    }
    List<string> res = new List<string>(); bool[] seen = new bool[W * H]; Stack<int> st = new Stack<int>();
    for (int s = 0; s < m.Length; s++) {
      if (!m[s] || seen[s]) continue;
      int x0 = W, x1 = 0, y0 = H, y1 = 0, n = 0; st.Push(s); seen[s] = true;
      while (st.Count > 0) {
        int p = st.Pop(); int px = p % W, py = p / W; n++;
        if (px < x0) x0 = px; if (px > x1) x1 = px; if (py < y0) y0 = py; if (py > y1) y1 = py;
        for (int dy = -1; dy <= 1; dy++) for (int dx = -1; dx <= 1; dx++) {
          int nx = px + dx, ny = py + dy; if (nx < 0 || ny < 0 || nx >= W || ny >= H) continue;
          int q = ny * W + nx; if (m[q] && !seen[q]) { seen[q] = true; st.Push(q); }
        }
      }
      if (n >= 6) res.Add(string.Format("{0},{1},{2},{3},{4}", (x0 + x1) / 2, (y0 + y1) / 2, x1 - x0 + 1, y1 - y0 + 1, n));
    }
    return res;
  }
}
"@ -ReferencedAssemblies System.Drawing
function Out-Json($o) { $o | ConvertTo-Json -Compress -Depth 4; exit 0 }
[FM]::SetProcessDPIAware() | Out-Null
. (Join-Path $PSScriptRoot 'psageom.ps1')
if ($Image) {
  $full = Open-PsaImage $Image
  if (-not $full) { Out-Json @{ ok = $false; error = "讀不到圖：$Image" } }
} else {
$proc = Get-Process PrimalSA -ErrorAction SilentlyContinue
if (-not $proc) { Out-Json @{ ok = $false; error = '遊戲沒有在執行' } }
$h = $proc.MainWindowHandle
if ([FM]::IsIconic($h)) { Out-Json @{ ok = $false; error = '遊戲視窗最小化' } }
$r = New-Object FM+RECT; [FM]::GetClientRect($h, [ref]$r) | Out-Null
$full = New-Object System.Drawing.Bitmap $r.R, $r.B
$g = [System.Drawing.Graphics]::FromImage($full); $dc = $g.GetHdc()
$ok = [FM]::PrintWindow($h, $dc, 3); $g.ReleaseHdc($dc); $g.Dispose()
if (-not $ok) { Out-Json @{ ok = $false; error = 'PrintWindow 失敗' } }
}
$Gm = Get-PsaGeomAuto $full.Width $full.Height
$scaled = $Gm.Proportional -and -not $Gm.Identity
if ($Crop -and $Out) {
  $c = $Crop.Split(',') | ForEach-Object { [int]$_ }
  $pb = Convert-PsaBox $Gm ($c[0] * 2) ($c[1] * 2) ($c[2] * 2) ($c[3] * 2)     # 截圖框 ×2 = 邏輯客戶區框 → 實體像素框
  $bm = New-Object System.Drawing.Bitmap ($c[2] * $Zoom), ($c[3] * $Zoom)
  $gg = [System.Drawing.Graphics]::FromImage($bm); $gg.InterpolationMode = 'NearestNeighbor'
  $gg.DrawImage($full, (New-Object System.Drawing.Rectangle 0, 0, $bm.Width, $bm.Height), $pb[0], $pb[1], $pb[2], $pb[3], 'Pixel'); $gg.Dispose()
  $bm.Save($Out, [System.Drawing.Imaging.ImageFormat]::Png); $bm.Dispose()
}
$blobs = @()
$bl = if ($scaled) { [FM]::BlobsS($full, $Gm.ShotW, [int]($full.Height / $Gm.Sy), $Gm.Sx, $Gm.Sy) } else { [FM]::Blobs($full) }
foreach ($s in $bl) { $p = $s.Split(','); $blobs += [ordered]@{ x = [int]$p[0]; y = [int]$p[1]; w = [int]$p[2]; h = [int]$p[3]; n = [int]$p[4] } }
$full.Dispose()
Out-Json ([ordered]@{ ok = $true; blobs = $blobs })
