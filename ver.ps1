# ================================================================
#  ver.ps1  -  ARMAR EL MODELO LT2 Y ABRIR EL VISOR
# ================================================================
#      .\ver.ps1              exporta el modelo y abre el visor
#      .\ver.ps1 -SoloExportar   solo escribe data/modelo_unity.json
#      .\ver.ps1 -Servidor    ademas levanta el servidor de reanalisis
#
#  Hace, en orden:
#    1. corre el modelo OpenSees del LT2 y resuelve el caso G
#    2. escribe data/modelo_unity.json (contrato de Unity)
#    3. copia el JSON al proyecto Unity Y a la app compilada
#    4. abre el visor
#
#  El paso 3 no es opcional: el visor lee
#  StreamingAssets/modelo_unity.json, y si no se copia muestra el
#  modelo VIEJO sin avisar de nada.
# ================================================================
param(
    [switch]$SoloExportar,
    [switch]$Servidor,
    [switch]$Recompilar
)

$ErrorActionPreference = 'Stop'
$raiz = $PSScriptRoot

# ---- 1. Encontrar un Python con openseespy ---------------------
# Primero el del repo; si no esta, el del laboratorio P1L2, que es
# el mismo entorno. El Python del sistema NO tiene openseespy.
$candidatos = @(
    (Join-Path $raiz '.venv\Scripts\python.exe'),
    (Join-Path (Split-Path $raiz -Parent) 'P1L2_Grupo_7\.venv\Scripts\python.exe')
)
$py = $candidatos | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $py) {
    Write-Host 'No encontre un entorno con openseespy. Crealo con:' -ForegroundColor Yellow
    Write-Host '    python -m venv .venv'
    Write-Host '    .\.venv\Scripts\python.exe -m pip install -r requirements.txt'
    exit 1
}
Write-Host "Python: $py" -ForegroundColor DarkGray

# ---- 2. Modelo -> JSON -----------------------------------------
Set-Location $raiz
& $py 'src\exportar_unity.py'
if ($LASTEXITCODE -ne 0) { Write-Host 'Fallo la exportacion.' -ForegroundColor Red; exit 1 }

if ($SoloExportar) { exit 0 }

# ---- 3. Servidor de reanalisis (opcional) ----------------------
# Tiene que estar arriba ANTES de abrir el visor: el panel de edicion
# se conecta al arrancar.
if ($Servidor) {
    Write-Host 'Levantando el servidor de reanalisis...' -ForegroundColor Cyan
    Start-Process -FilePath $py -ArgumentList 'src\servidor_opensees.py' -WorkingDirectory $raiz
    Start-Sleep -Seconds 2
}

# ---- 4. Sincronizar el JSON y abrir el visor -------------------
# OJO: '--forzar' solo lo entiende el modo 'build'. Antes esto mandaba
# 'app --forzar', que cae en el modo por defecto (abrir el visor) e
# IGNORA la bandera: se editaba un .cs, se corria -Recompilar, y se
# abria la app vieja sin avisar de nada.
if ($Recompilar) {
    Write-Host 'Recompilando la app (varios minutos)...' -ForegroundColor Cyan
    & $py 'src\lanzar_unity.py' 'build' '--forzar'
    if ($LASTEXITCODE -ne 0) { Write-Host 'Fallo la compilacion.' -ForegroundColor Red; exit 1 }
}
& $py 'src\lanzar_unity.py' 'app'
