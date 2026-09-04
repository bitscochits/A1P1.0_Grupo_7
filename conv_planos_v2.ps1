# Convierte los DWG de C:\planos_v2 a DXF, con accoreconsole de AutoCAD.
#
# La ruta de trabajo NO tiene espacios ni tildes a proposito: el .rar
# viene de "Planos edeificio ingeniería", y accoreconsole se corta con
# esa ruta. Por eso se extrae a C:\planos_v2 antes de convertir.
#
# Uso:
#   powershell -File conv_planos_v2.ps1                 -> todas
#   powershell -File conv_planos_v2.ps1 2017_67-100 ... -> solo esas
param([string[]]$Hojas)

$acc = "C:\Program Files\Autodesk\AutoCAD 2027\accoreconsole.exe"
$dir = "C:\planos_v2"

if (-not (Test-Path -LiteralPath $acc)) {
    Write-Output "No encuentro accoreconsole en: $acc"
    exit 1
}

if (-not $Hojas -or $Hojas.Count -eq 0) {
    $Hojas = Get-ChildItem -LiteralPath $dir -Filter *.dwg |
             ForEach-Object { $_.BaseName }
}

foreach ($h in $Hojas) {
    $dwg = Join-Path $dir "$h.dwg"
    $dxf = Join-Path $dir "$h.dxf"
    if (Test-Path -LiteralPath $dxf) { Write-Output "ya existe: $h"; continue }
    if (-not (Test-Path -LiteralPath $dwg)) { Write-Output "FALTA dwg: $h"; continue }

    $scr = Join-Path $dir "_conv_$h.scr"
    # FILEDIA 0 apaga los cuadros de dialogo; 16 es la precision decimal.
    @"
FILEDIA
0
_.DXFOUT
$dxf
16
_.QUIT
_Y
"@ | Out-File -FilePath $scr -Encoding ascii

    & $acc /i $dwg /s $scr | Out-Null

    if (Test-Path -LiteralPath $dxf) {
        Write-Output ("OK  {0}  {1:N1} MB" -f $h, ((Get-Item -LiteralPath $dxf).Length / 1MB))
    } else {
        Write-Output "FALLO: $h"
    }
    Remove-Item -LiteralPath $scr -ErrorAction SilentlyContinue
}
