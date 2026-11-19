# Zamanlanmış görev "Komixsi Klip Cikar" bunu çalıştırır: günlük klip çıkarma (yalnız üretir; onaylamaz/yüklemez/push yapmaz).
$ErrorActionPreference = 'Stop'
$kok = Split-Path -Parent $PSScriptRoot
$betik = Join-Path $PSScriptRoot 'klip_otomatik.py'
$py = $null
foreach ($ad in 'py', 'python') {
    $k = Get-Command $ad -ErrorAction SilentlyContinue
    if ($k) { $py = $k.Source; break }
}
if (-not $py) { Write-Error 'Python bulunamadi (py/python).'; exit 2 }
$env:PYTHONUTF8 = '1'
Set-Location $kok
if ((Split-Path -Leaf $py) -ieq 'py.exe') { & $py -3 $betik } else { & $py $betik }
exit $LASTEXITCODE
