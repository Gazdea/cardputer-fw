# Flash a launcher image over USB (esptool).
#
#   .\tools\usb-flash.ps1 -Port COM6 -File .\dist\Launcher-m5stack-cardputer-2.9.1-cfw14.bin
#
# By default only the app part is written (offset 0x10000), so the partition table,
# NVS and the SD card are left untouched. Use -Full to write the whole merged image
# at 0x0 — needed only when the layout itself changes (it wipes NVS and app partitions).

param(
    [string]$Port = "COM6",
    [Parameter(Mandatory = $true)][string]$File,
    [switch]$Full,
    [switch]$Verify
)

$ErrorActionPreference = "Stop"
if (-not (Test-Path $File)) { throw "file not found: $File" }

$bytes = [System.IO.File]::ReadAllBytes($File)
$isMerged = ($bytes.Length -gt 0x10100) -and ($bytes[0] -eq 0xE9) -and
            ($bytes[0x8000] -eq 0xAA) -and ($bytes[0x8001] -eq 0x50)

if ($Full) {
    if (-not $isMerged) { throw "not a merged image (no partition table at 0x8000)" }
    "full flash: $File -> 0x0 (wipes NVS and app partitions)"
    python -m esptool --port $Port --baud 460800 write-flash 0x0 $File
}
else {
    $app = $bytes
    $offset = 0x10000
    if ($isMerged) {
        $len = $bytes.Length - 0x10000
        $app = New-Object byte[] $len
        [Array]::Copy($bytes, 0x10000, $app, 0, $len)
        "merged image: flashing app part"
    }
    else {
        $offset = 0x10000
        "bare app image: flashing at 0x10000"
    }
    $tmp = [System.IO.Path]::GetTempFileName()
    [System.IO.File]::WriteAllBytes($tmp, $app)
    try {
        "app part: {0:N0} bytes -> 0x{1:X}" -f $app.Length, $offset
        python -m esptool --port $Port --baud 460800 write-flash ("0x{0:X}" -f $offset) $tmp
    }
    finally { Remove-Item $tmp -ErrorAction SilentlyContinue }
}

if ($LASTEXITCODE -ne 0) { throw "esptool failed" }
"done"
