$ErrorActionPreference="Stop"
$root=$PSScriptRoot
$out=Join-Path $root "lr1_leonov_prompt_shot"
New-Item -ItemType Directory -Force -Path $out | Out-Null
$work="C:\LR1_7342835\Леонов"
New-Item -ItemType Directory -Force -Path $work | Out-Null
"Леонов" | Set-Content -Path (Join-Path $work "fam.txt") -Encoding utf8
"Леонов" | Set-Content -Path (Join-Path $work "fio.docx") -Encoding utf8
"IMYA_NE_UKAZANO" | Set-Content -Path (Join-Path $work "name.txt") -Encoding utf8
"OTCHESTVO_NE_UKAZANO" | Set-Content -Path (Join-Path $work "otchestvo.txt") -Encoding utf8
New-Item -ItemType Directory -Force -Path (Join-Path $work "IMYA_NE_UKAZANO") | Out-Null

Add-Type -AssemblyName System.Drawing
Add-Type -AssemblyName System.Windows.Forms

$arg='chcp 65001>nul & cd /d C:\LR1_7342835\Леонов & prompt Привет. Введите команду$G'
$p=Start-Process -FilePath "cmd.exe" -ArgumentList @("/k",$arg) -WindowStyle Maximized -PassThru
Start-Sleep -Seconds 4
$ws=New-Object -ComObject WScript.Shell
$ws.AppActivate($p.Id) | Out-Null
Start-Sleep -Milliseconds 500
$ws.SendKeys("dir{ENTER}")
Start-Sleep -Seconds 2

$b=[Windows.Forms.Screen]::PrimaryScreen.Bounds
$bmp=New-Object Drawing.Bitmap($b.Width,$b.Height)
$g=[Drawing.Graphics]::FromImage($bmp)
$g.CopyFromScreen($b.Location,[Drawing.Point]::Empty,$b.Size)
$g.Dispose()
$path=Join-Path $out "LR1_44_48_Leonov.png"
$bmp.Save($path,[Drawing.Imaging.ImageFormat]::Png);$bmp.Dispose()
Write-Host "SHOT=$path"

$ws.AppActivate($p.Id) | Out-Null
$ws.SendKeys('prompt $P$G{ENTER}')
Start-Sleep -Milliseconds 500
$ws.SendKeys("exit{ENTER}")
$p.WaitForExit(10000) | Out-Null
Write-Host "DONE"

# trigger prompt capture
