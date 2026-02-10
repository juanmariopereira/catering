# Build release APK for Courier app
# Requisito: Flutter en PATH (ej. C:\flutter\bin o donde lo tengas instalado)
# Ejecutar desde la carpeta courier_app: .\build_apk.ps1

Set-Location $PSScriptRoot

if (-not (Get-Command flutter -ErrorAction SilentlyContinue)) {
    Write-Host "Flutter no esta en el PATH. Anade la carpeta bin de Flutter al PATH o ejecuta:" -ForegroundColor Yellow
    Write-Host '  $env:Path += ";C:\ruta\a\flutter\bin"'
    Write-Host "  flutter build apk --release"
    exit 1
}

Write-Host "Instalando dependencias..." -ForegroundColor Cyan
flutter pub get
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "Construyendo APK release..." -ForegroundColor Cyan
flutter build apk --release
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

$apkPath = "build\app\outputs\flutter-apk\app-release.apk"
if (Test-Path $apkPath) {
    $fullPath = (Resolve-Path $apkPath).Path
    Write-Host ""
    Write-Host "APK generado correctamente:" -ForegroundColor Green
    Write-Host "  $fullPath"
    Write-Host ""
    Write-Host "Para desplegar: copia este archivo a tu servidor o subelo a la URL que uses para que los repartidores descarguen el APK."
} else {
    Write-Host "No se encontro el APK en $apkPath" -ForegroundColor Red
    exit 1
}
