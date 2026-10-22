# Publish a built image as a GitHub release (binary distribution only).
#
#   .\tools\publish.ps1 -Version 2.9.1-cfw14 -File .\dist\Launcher-m5stack-cardputer-2.9.1-cfw14.bin -Notes "what changed"
#
# Requires: gh CLI, logged in with repo scope.

param(
    [Parameter(Mandatory = $true)][string]$Version,
    [Parameter(Mandatory = $true)][string]$File,
    [string]$Notes = "",
    [string]$Repo = "Gazdea/cardputer-fw"
)

$ErrorActionPreference = "Stop"
if (-not (Test-Path $File)) { throw "file not found: $File" }

$sha = (Get-FileHash $File -Algorithm SHA256).Hash.ToLower()
$size = (Get-Item $File).Length

# Probing for an existing release must not abort the script, so keep gh's stderr
# non-terminating for this call only.
$ErrorActionPreference = "Continue"
$null = gh release view $Version --repo $Repo --json tagName 2>&1
$releaseExists = ($LASTEXITCODE -eq 0)
$ErrorActionPreference = "Stop"

if ($releaseExists) {
    gh release upload $Version $File --repo $Repo --clobber
    if ($LASTEXITCODE -ne 0) { throw "gh release upload failed" }
}
else {
    gh release create $Version $File --repo $Repo --title "Cardputer firmware $Version" --notes $Notes
    if ($LASTEXITCODE -ne 0) { throw "gh release create failed" }
}

"release : https://github.com/$Repo/releases/tag/$Version"
"size    : $size bytes"
"sha256  : $sha"
