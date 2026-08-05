$ErrorActionPreference = "Stop"
$root = Split-Path $PSScriptRoot -Parent
Set-Location $root
& cmd.exe /d /c "`"$root\BUILD_WINDOWS_EXE.bat`" $($args -join ' ')"
if ($LASTEXITCODE -ne 0) {
    throw "BounceBeat Studio Windows build failed with exit code $LASTEXITCODE."
}
