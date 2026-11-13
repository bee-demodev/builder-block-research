param(
    [string]$TitlePattern = "NQU2026",
    [string]$OutputDir = "results\live_tradingview_desktop",
    [string]$Symbol = "CME_MINI:NQU2026",
    [string]$Timeframe = "unknown",
    [int]$ResizeWidth = 1600,
    [int]$ResizeHeight = 1000,
    [int]$CropX = 54,
    [int]$CropY = 80,
    [int]$CropWidth = 1498,
    [int]$CropHeight = 883,
    [switch]$NoResize,
    [switch]$NoCrop
)

$ErrorActionPreference = "Stop"

Add-Type @"
using System;
using System.Runtime.InteropServices;

public class TradingViewDesktopCaptureWin32 {
  [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr hWnd, int nCmdShow);
  [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr hWnd);
  [DllImport("user32.dll")] public static extern bool MoveWindow(IntPtr hWnd, int X, int Y, int nWidth, int nHeight, bool bRepaint);
  [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr hWnd, out RECT lpRect);
}

public struct RECT {
  public int Left;
  public int Top;
  public int Right;
  public int Bottom;
}
"@

Add-Type -AssemblyName System.Drawing
Add-Type -AssemblyName System.Windows.Forms

$process = Get-Process TradingView |
    Where-Object { $_.MainWindowHandle -ne 0 -and $_.MainWindowTitle -match $TitlePattern } |
    Select-Object -First 1

if (-not $process) {
    throw "No TradingView Desktop window matched title pattern '$TitlePattern'."
}

[TradingViewDesktopCaptureWin32]::ShowWindow($process.MainWindowHandle, 9) | Out-Null
if (-not $NoResize) {
    [TradingViewDesktopCaptureWin32]::MoveWindow($process.MainWindowHandle, 0, 0, $ResizeWidth, $ResizeHeight, $true) | Out-Null
}
Start-Sleep -Milliseconds 800
[TradingViewDesktopCaptureWin32]::SetForegroundWindow($process.MainWindowHandle) | Out-Null
Start-Sleep -Milliseconds 800

$rect = New-Object RECT
[TradingViewDesktopCaptureWin32]::GetWindowRect($process.MainWindowHandle, [ref]$rect) | Out-Null

$windowWidth = $rect.Right - $rect.Left
$windowHeight = $rect.Bottom - $rect.Top
if ($windowWidth -le 0 -or $windowHeight -le 0) {
    throw "TradingView Desktop window has invalid bounds: $windowWidth x $windowHeight."
}

New-Item -ItemType Directory -Force -Path $OutputDir | Out-Null
$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$safeSymbol = ($Symbol -replace "[^A-Za-z0-9_-]+", "_").Trim("_")
if (-not $safeSymbol) {
    $safeSymbol = "chart"
}

$rawPath = Join-Path $OutputDir "tradingview_desktop_${safeSymbol}_${stamp}.png"
$cropPath = Join-Path $OutputDir "tradingview_desktop_${safeSymbol}_${stamp}.chart_crop.png"
$metadataPath = Join-Path $OutputDir "tradingview_desktop_${safeSymbol}_${stamp}.metadata.json"

$bitmap = New-Object System.Drawing.Bitmap $windowWidth, $windowHeight
$graphics = [System.Drawing.Graphics]::FromImage($bitmap)
$graphics.CopyFromScreen($rect.Left, $rect.Top, 0, 0, $bitmap.Size)
$bitmap.Save($rawPath, [System.Drawing.Imaging.ImageFormat]::Png)
$graphics.Dispose()

$cropWritten = $false
if (-not $NoCrop) {
    if ($CropX -lt 0 -or $CropY -lt 0 -or $CropWidth -le 0 -or $CropHeight -le 0) {
        throw "Crop bounds must be positive. Received x=$CropX y=$CropY width=$CropWidth height=$CropHeight."
    }
    if (($CropX + $CropWidth) -gt $windowWidth -or ($CropY + $CropHeight) -gt $windowHeight) {
        throw "Crop bounds exceed capture size ${windowWidth}x${windowHeight}: x=$CropX y=$CropY width=$CropWidth height=$CropHeight."
    }
    $cropRect = New-Object System.Drawing.Rectangle $CropX, $CropY, $CropWidth, $CropHeight
    $cropBitmap = New-Object System.Drawing.Bitmap $CropWidth, $CropHeight
    $cropGraphics = [System.Drawing.Graphics]::FromImage($cropBitmap)
    $targetRect = New-Object System.Drawing.Rectangle 0, 0, $CropWidth, $CropHeight
    $cropGraphics.DrawImage($bitmap, $targetRect, $cropRect, [System.Drawing.GraphicsUnit]::Pixel)
    $cropBitmap.Save($cropPath, [System.Drawing.Imaging.ImageFormat]::Png)
    $cropGraphics.Dispose()
    $cropBitmap.Dispose()
    $cropWritten = $true
}

$bitmap.Dispose()

$metadata = [ordered]@{
    generated_at_local = (Get-Date).ToString("s")
    source = "TradingView Desktop"
    process_id = $process.Id
    title = $process.MainWindowTitle
    title_pattern = $TitlePattern
    symbol = $Symbol
    timeframe = $Timeframe
    resized = (-not $NoResize)
    window = [ordered]@{
        left = $rect.Left
        top = $rect.Top
        width = $windowWidth
        height = $windowHeight
    }
    raw_screenshot = (Resolve-Path -LiteralPath $rawPath).Path
    chart_crop = if ($cropWritten) { (Resolve-Path -LiteralPath $cropPath).Path } else { $null }
    crop = if ($cropWritten) {
        [ordered]@{
            x = $CropX
            y = $CropY
            width = $CropWidth
            height = $CropHeight
        }
    } else {
        $null
    }
}

$metadata | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $metadataPath -Encoding UTF8
$metadata | ConvertTo-Json -Depth 6
