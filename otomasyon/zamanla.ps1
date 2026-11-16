param([switch]$Kaydet)

# Bu dosyayı çalıştırmak tek başına görev kurmaz. Yönetici incelemesinden
# sonra açıkça -Kaydet verilmelidir. Çıktı betiğin kendisiyle aynı UTF-8'dedir.
$ErrorActionPreference = 'Stop'
$projeKoku = Split-Path -Parent $PSScriptRoot
$pythonYolu = (Get-Command py.exe -ErrorAction Stop).Source
$conhostYolu = Join-Path $env:SystemRoot 'System32\conhost.exe'
$gorevAdi = 'ctrl-agame saatlik haber'
$argumanlar = '--headless "{0}" "{1}"' -f $pythonYolu, (Join-Path $projeKoku 'tools\haber_hatti.py')
$eylem = New-ScheduledTaskAction -Execute $conhostYolu -Argument $argumanlar -WorkingDirectory $projeKoku
$baslangic = (Get-Date).Date.AddHours((Get-Date).Hour + 1)
$tetik = New-ScheduledTaskTrigger -Once -At $baslangic -RepetitionInterval (New-TimeSpan -Hours 1)
$ayarlar = New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Minutes 44) -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
$kullanici = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
$kimlik = New-ScheduledTaskPrincipal -UserId $kullanici -LogonType Interactive -RunLevel Limited
$gorev = New-ScheduledTask -Action $eylem -Trigger $tetik -Settings $ayarlar -Principal $kimlik -Description 'Python haber hatti: yerel eleme, kucuk yazar, zorunlu Sonnet/Opus denetimi.'
if ($Kaydet) {
    Register-ScheduledTask -TaskName $gorevAdi -InputObject $gorev -Force | Out-Null
    Write-Output "Kaydedildi: $gorevAdi"
} else {
    Write-Output (Export-ScheduledTask -InputObject $gorev)
    Write-Output 'Yalniz onizleme; gorev kaydedilmedi. Yonetici incelemesi sonrasi: .\otomasyon\zamanla.ps1 -Kaydet'
}
