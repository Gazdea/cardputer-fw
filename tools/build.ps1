# Build the custom Launcher for Cardputer ADV and drop a versioned copy into dist/.
#
#   .\tools\build.ps1 -Version 2.9.1-cfw2
#
# Requires: PlatformIO (python -m platformio) and the launcher source checkout.

param(
    [string]$Version = "2.9.1-cfw1",
    [string]$Src = "C:\Users\mikha\projects\firmware\launcher"
)

$ErrorActionPreference = "Stop"
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$dist = Join-Path (Split-Path -Parent $here) "dist"
New-Item -ItemType Directory -Force -Path $dist | Out-Null

$ini = Join-Path $Src "boards\m5stack-cardputer\platformio.ini"
$text = [System.IO.File]::ReadAllText($ini)
$updated = [regex]::Replace($text, '-DLAUNCHER=''"[^"]*"''', "-DLAUNCHER='""$Version""'")
if ($updated -notmatch [regex]::Escape($Version)) {
    throw "could not set LAUNCHER=$Version in $ini"
}
[System.IO.File]::WriteAllText($ini, $updated, (New-Object System.Text.UTF8Encoding($false)))
"building version $Version"

Push-Location $Src
try {
    python -m platformio run -e m5stack-cardputer
    if ($LASTEXITCODE -ne 0) { throw "platformio failed" }
}
finally { Pop-Location }

$built = Join-Path $Src "Launcher-m5stack-cardputer.bin"
if (-not (Test-Path $built)) { throw "no image produced at $built" }

$target = Join-Path $dist ("Launcher-m5stack-cardputer-{0}.bin" -f $Version)
Copy-Item $built $target -Force
$sha = (Get-FileHash $target -Algorithm SHA256).Hash.ToLower()
$size = (Get-Item $target).Length

"`nimage : $target"
"size  : $size bytes"
"sha256: $sha"
"`nnext  : .\tools\publish.ps1 -Version $Version -File `"$target`""
