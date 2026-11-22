$ErrorActionPreference="Stop"
$root=$PSScriptRoot
$out=Join-Path $root "lr1_leonov_shots"
New-Item -ItemType Directory -Force -Path $out | Out-Null
$work="C:\LR1_7342835"
if(Test-Path $work){Remove-Item $work -Recurse -Force}
New-Item -ItemType Directory -Path $work | Out-Null

$bat=Join-Path $root "lr1_leonov.cmd"
$lines=@(
'@echo off',
'chcp 65001 >nul',
'mode con cols=120 lines=42',
'cd /d C:\',
'cls',
'echo Задания 12-18',
'echo C:\^> md C:\LR1_7342835\Леонов',
'md C:\LR1_7342835\Леонов',
'echo C:\^> cd /d C:\LR1_7342835\Леонов',
'cd /d C:\LR1_7342835\Леонов',
'echo C:\LR1_7342835\Леонов^> md IMYA_NE_UKAZANO\OTCHESTVO_NE_UKAZANO',
'md IMYA_NE_UKAZANO\OTCHESTVO_NE_UKAZANO',
'echo C:\LR1_7342835\Леонов^> echo Леонов ^> fam.txt',
'echo Леонов > fam.txt',
'echo C:\LR1_7342835\Леонов^> echo IMYA_NE_UKAZANO ^> name.txt',
'echo IMYA_NE_UKAZANO > name.txt',
'echo C:\LR1_7342835\Леонов^> echo OTCHESTVO_NE_UKAZANO ^> otchestvo.txt',
'echo OTCHESTVO_NE_UKAZANO > otchestvo.txt',
'echo C:\LR1_7342835\Леонов^> echo Леонов ^> fio.docx',
'echo Леонов > fio.docx',
'dir',
'echo 1> "%TEMP%\lr1shot1.ready"',
'timeout /t 7 /nobreak >nul',
'cls',
'echo Задания 19-24',
'cd /d C:\LR1_7342835\Леонов',
'echo C:\LR1_7342835\Леонов^> copy /b fam.txt+name.txt+otchestvo.txt fio.txt',
'copy /b fam.txt+name.txt+otchestvo.txt fio.txt',
'echo C:\LR1_7342835\Леонов^> type fio.txt',
'type fio.txt',
'echo C:\LR1_7342835\Леонов^> md C:\LR1_7342835\FIO',
'md C:\LR1_7342835\FIO',
'echo C:\LR1_7342835\Леонов^> copy name.txt C:\LR1_7342835\FIO\',
'copy name.txt C:\LR1_7342835\FIO\',
'echo C:\LR1_7342835\Леонов^> copy otchestvo.txt C:\LR1_7342835\FIO\',
'copy otchestvo.txt C:\LR1_7342835\FIO\',
'dir C:\LR1_7342835\FIO',
'echo 1> "%TEMP%\lr1shot2.ready"',
'timeout /t 7 /nobreak >nul',
'cls',
'echo Задания 25-31',
'cd /d C:\LR1_7342835\Леонов',
'echo C:\LR1_7342835\Леонов^> move fio.txt C:\LR1_7342835\FIO\',
'move fio.txt C:\LR1_7342835\FIO\',
'echo C:\LR1_7342835\Леонов^> attrib +R C:\LR1_7342835\FIO\fio.txt',
'attrib +R C:\LR1_7342835\FIO\fio.txt',
'attrib C:\LR1_7342835\FIO\fio.txt',
'echo C:\LR1_7342835\Леонов^> ren C:\LR1_7342835\FIO\fio.txt myfio.txt',
'ren C:\LR1_7342835\FIO\fio.txt myfio.txt',
'echo C:\LR1_7342835\Леонов^> attrib -R C:\LR1_7342835\FIO\myfio.txt',
'attrib -R C:\LR1_7342835\FIO\myfio.txt',
'attrib C:\LR1_7342835\FIO\myfio.txt',
'dir C:\LR1_7342835\FIO',
'echo 1> "%TEMP%\lr1shot3.ready"',
'timeout /t 7 /nobreak >nul',
'cls',
'echo Задания 32-37',
'cd /d C:\LR1_7342835\Леонов',
'copy name.txt IMYA_NE_UKAZANO\OTCHESTVO_NE_UKAZANO\name.txt >nul',
'copy otchestvo.txt IMYA_NE_UKAZANO\OTCHESTVO_NE_UKAZANO\otchestvo.txt >nul',
'echo C:\LR1_7342835\Леонов^> erase IMYA_NE_UKAZANO\OTCHESTVO_NE_UKAZANO\name.txt IMYA_NE_UKAZANO\OTCHESTVO_NE_UKAZANO\otchestvo.txt',
'erase IMYA_NE_UKAZANO\OTCHESTVO_NE_UKAZANO\name.txt IMYA_NE_UKAZANO\OTCHESTVO_NE_UKAZANO\otchestvo.txt',
'echo C:\LR1_7342835\Леонов^> rd IMYA_NE_UKAZANO\OTCHESTVO_NE_UKAZANO',
'rd IMYA_NE_UKAZANO\OTCHESTVO_NE_UKAZANO',
'echo C:\LR1_7342835\Леонов^> find /I "Леонов" fam.txt fio.docx C:\LR1_7342835\FIO\myfio.txt',
'find /I "Леонов" fam.txt fio.docx C:\LR1_7342835\FIO\myfio.txt',
'echo 1> "%TEMP%\lr1shot4.ready"',
'timeout /t 7 /nobreak >nul',
'cls',
'echo Итоговая структура каталогов и файлов',
'echo C:\LR1_7342835\Леонов^> tree C:\LR1_7342835 /F /A',
'tree C:\LR1_7342835 /F /A',
'echo 1> "%TEMP%\lr1shot5.ready"',
'timeout /t 7 /nobreak >nul',
'exit'
)
[IO.File]::WriteAllLines($bat,$lines,(New-Object Text.UTF8Encoding($false)))

Add-Type -AssemblyName System.Drawing
Add-Type -AssemblyName System.Windows.Forms
function Shot([string]$name){
  $b=[Windows.Forms.Screen]::PrimaryScreen.Bounds
  $bmp=New-Object Drawing.Bitmap($b.Width,$b.Height)
  $g=[Drawing.Graphics]::FromImage($bmp)
  $g.CopyFromScreen($b.Location,[Drawing.Point]::Empty,$b.Size)
  $g.Dispose()
  $path=Join-Path $out ($name+".png")
  $bmp.Save($path,[Drawing.Imaging.ImageFormat]::Png);$bmp.Dispose()
  Write-Host "SHOT=$path"
}

$p=Start-Process -FilePath "cmd.exe" -ArgumentList @("/c",('"' + $bat + '"')) -WindowStyle Maximized -PassThru
for($i=1;$i -le 5;$i++){
  $m=Join-Path $env:TEMP ("lr1shot"+$i+".ready")
  $limit=(Get-Date).AddSeconds(60)
  while(!(Test-Path $m)){
    Start-Sleep -Milliseconds 300
    if((Get-Date) -gt $limit){throw "Marker timeout $i"}
  }
  Start-Sleep -Seconds 1
  Shot ("0"+$i+"_LR1_Leonov")
  Remove-Item $m -Force
}
$p.WaitForExit()
Write-Host "EXIT=$($p.ExitCode)"
if($p.ExitCode -ne 0){throw "CMD failed"}

# trigger Leonov capture
