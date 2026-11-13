<#
.SYNOPSIS
    Build the packaged Trading Companion: dist\Trading Companion\Trading Companion.exe

.DESCRIPTION
    A PyInstaller one-folder, windowed build of companion.desktop. The folder holds the
    Python code, the built web UI (-Ui), the data files the companion opens at run time
    (the list is companion.paths.RUNTIME_DATA_FILES) and the window icon. A missing UI or
    data file fails the build.

    The saved minute history (data\databento\bars, hundreds of MB) is not bundled. The
    packaged app looks for <symbol>_minute.csv files in a "history" folder next to
    Trading Companion.exe, or in the folder named by "history_dir" in
    %USERPROFILE%\.trading_companion\desktop.json. Without one it runs live only.

    Needs: .venv with companion\requirements.txt and companion\requirements-build.txt.

.PARAMETER Ui
    The built web UI folder (with index.html). Default: companion\web\dist

.PARAMETER Python
    The Python that has the requirements. Default: .venv\Scripts\python.exe

.PARAMETER Dist
    Where the app folder is written. Default: dist (dist\Trading Companion)

.EXAMPLE
    .\Build-Companion.ps1
    .\Build-Companion.ps1 -Ui C:\path\to\web\dist
#>
[CmdletBinding()]
param(
    [string]$Ui = "",
    [string]$Python = "",
    [string]$Dist = ""
)

$ErrorActionPreference = "Stop"
$Repo = $PSScriptRoot
$Name = "Trading Companion"

function Fail([string]$Message) {
    Write-Host ""
    Write-Host "BUILD FAILED: $Message" -ForegroundColor Red
    exit 1
}

function Resolve-From([string]$Path, [string]$Default) {
    if ([string]::IsNullOrWhiteSpace($Path)) { $Path = $Default }
    if (-not [System.IO.Path]::IsPathRooted($Path)) { $Path = Join-Path $Repo $Path }
    return [System.IO.Path]::GetFullPath($Path)
}

$Ui = Resolve-From $Ui "companion\web\dist"
$Python = Resolve-From $Python ".venv\Scripts\python.exe"
$Dist = Resolve-From $Dist "dist"
$Work = Join-Path $Repo "build\pyinstaller"
$Entry = Join-Path $Repo "companion\desktop\__main__.py"
$Icon = Join-Path $Repo "companion\desktop\icon.ico"
$App = Join-Path $Dist $Name

# --- what goes in ------------------------------------------------------------------

if (-not (Test-Path $Python -PathType Leaf)) { Fail "Python not found at $Python (create .venv and install companion\requirements.txt and companion\requirements-build.txt)." }
& $Python -c "import PyInstaller, webview, aiohttp, pandas" 2>$null
if ($LASTEXITCODE -ne 0) { Fail "Missing packages in $Python. Run: uv pip install --python `"$Python`" -r companion\requirements.txt -r companion\requirements-build.txt" }
if (-not (Test-Path (Join-Path $Ui "index.html") -PathType Leaf)) { Fail "No built UI at $Ui (index.html missing). Build it in companion\web (npm run build) or pass -Ui." }
if (-not (Test-Path $Icon -PathType Leaf)) { Fail "Icon missing: $Icon (python -m companion.desktop.make_icon writes it)." }

# The data files, from the one list the code uses (companion.paths), relative to the package.
Push-Location $Repo
try {
    $listed = & $Python -c "from companion import paths; print('\n'.join('/'.join(p) for p in paths.RUNTIME_DATA_FILES + paths.REFERENCE_FILES))"
    if ($LASTEXITCODE -ne 0) { Fail "Could not read companion.paths.RUNTIME_DATA_FILES." }
} finally { Pop-Location }
$DataFiles = @($listed | Where-Object { $_.Trim() } | ForEach-Object { $_.Trim() })
if ($DataFiles.Count -eq 0) { Fail "companion.paths lists no data files." }

$AddData = @()
foreach ($relative in $DataFiles) {
    $source = Join-Path $Repo ("companion/" + $relative)
    if (-not (Test-Path $source -PathType Leaf)) { Fail "Data file missing: $source" }
    $folder = Split-Path ("companion/" + $relative) -Parent
    $AddData += @("--add-data", "$source;$folder")
}
$AddData += @("--add-data", "$Icon;companion/desktop")
$AddData += @("--add-data", "$Ui;companion/web/dist")

# --- build -------------------------------------------------------------------------

Write-Host "Building $Name"
Write-Host "  UI:     $Ui"
Write-Host "  Python: $Python"
Write-Host "  Data:   $($DataFiles -join ', ')"
Write-Host "  Output: $App"

$Arguments = @(
    "-m", "PyInstaller", $Entry,
    "--noconfirm", "--clean", "--log-level", "WARN",
    "--onedir", "--windowed",
    "--name", $Name,
    "--icon", $Icon,
    "--paths", $Repo,
    "--distpath", $Dist,
    "--workpath", $Work,
    "--specpath", $Work,
    # styles are found by listing their folder and imported by name; the live feed is imported on first use
    "--collect-submodules", "companion.styles",
    "--collect-submodules", "companion.tradingview",
    "--collect-submodules", "companion.core",
    # not used by the desktop app: the Tk window, the research tools and the big optional stacks
    "--exclude-module", "companion.app",
    "--exclude-module", "companion.tools",
    "--exclude-module", "tkinter",
    "--exclude-module", "matplotlib",
    "--exclude-module", "scipy",
    "--exclude-module", "torch",
    "--exclude-module", "IPython",
    "--exclude-module", "pytest"
) + $AddData

Push-Location $Repo
try {
    & $Python @Arguments
    $code = $LASTEXITCODE
} finally { Pop-Location }
if ($code -ne 0) { Fail "PyInstaller exited with $code." }

# --- check what came out -----------------------------------------------------------

$Exe = Join-Path $App "$Name.exe"
$Bundle = Join-Path $App "_internal"
if (-not (Test-Path $Exe -PathType Leaf)) { Fail "No exe at $Exe" }
foreach ($relative in $DataFiles) {
    $packed = Join-Path $Bundle ("companion/" + $relative)
    if (-not (Test-Path $packed -PathType Leaf)) { Fail "Data file not in the package: $packed" }
}
if (-not (Test-Path (Join-Path $Bundle "companion\web\dist\index.html") -PathType Leaf)) { Fail "UI not in the package." }
$csv = @(Get-ChildItem $App -Recurse -Filter "*_minute.csv" -ErrorAction SilentlyContinue)
if ($csv.Count -gt 0) { Fail "Minute history was bundled ($($csv[0].FullName)); it must not be." }

@"
Trading Companion
=================

Start: double-click "Trading Companion.exe". A second double-click brings the open
window to the front.

Needs the Microsoft Edge WebView2 Runtime (part of Windows 11; for Windows 10 see
https://developer.microsoft.com/microsoft-edge/webview2/).

Live mode reads TradingView Desktop through its debug port (see the port in
_internal\companion\config\symbols.json).

Saved history (optional): put nq_minute.csv, es_minute.csv and/or gc_minute.csv in a
folder named "history" next to this file, or name another folder in
%USERPROFILE%\.trading_companion\desktop.json:

    { "history_dir": "D:\\data\\bars" }

Without it the app runs live only and says that saved history is unavailable.

Settings, the window's size and place, and desktop.log (what happened, and any error)
are in %USERPROFILE%\.trading_companion (or the folder in TRADING_COMPANION_HOME).
"@ | Set-Content -Path (Join-Path $App "README.txt") -Encoding UTF8

$bytes = (Get-ChildItem $App -Recurse -File | Measure-Object -Property Length -Sum).Sum
$files = (Get-ChildItem $App -Recurse -File).Count
Write-Host ""
Write-Host ("Built: {0}" -f $Exe) -ForegroundColor Green
Write-Host ("Size:  {0:N1} MB in {1} files" -f ($bytes / 1MB), $files)
