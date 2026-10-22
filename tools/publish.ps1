# Publish a built image as a GitHub release and refresh manifest.json.
#
#   .\tools\publish.ps1 -Version 2.9.1-cfw1 -File .\dist\Launcher-m5stack-cardputer-2.9.1-cfw1.bin -Notes "what changed"
#
# Requires: gh CLI, logged in with repo scope.

param(
    [Parameter(Mandatory = $true)][string]$Version,
    [Parameter(Mandatory = $true)][string]$File,
    [string]$Notes = "",
    [string]$Repo = "Gazdea/cardputer-fw"
)

$ErrorActionPreference = "Stop"
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$root = Split-Path -Parent $here
if (-not (Test-Path $File)) { throw "file not found: $File" }

$name = Split-Path $File -Leaf
$sha = (Get-FileHash $File -Algorithm SHA256).Hash.ToLower()
$size = (Get-Item $File).Length
$url = "https://github.com/$Repo/releases/download/$Version/$name"

# Create (or re-use) the release and attach the image.
$existing = gh release view $Version --repo $Repo --json tagName 2>$null
if ($LASTEXITCODE -eq 0) {
    gh release upload $Version $File --repo $Repo --clobber
}
else {
    gh release create $Version $File --repo $Repo --title "Cardputer firmware $Version" --notes $Notes
}

$manifest = [ordered]@{
    product   = "cardputer-adv"
    channel   = "stable"
    generated = (Get-Date -Format "yyyy-MM-dd")
    latest    = [ordered]@{
        version = $Version
        tag     = $Version
        file    = $name
        url     = $url
        sha256  = $sha
        size    = $size
        notes   = $Notes
    }
}

$manifestPath = Join-Path $root "manifest.json"
$manifest | ConvertTo-Json -Depth 6 | Set-Content -Path $manifestPath -Encoding utf8

"manifest updated: $manifestPath"
"sha256: $sha"
"url   : $url"
