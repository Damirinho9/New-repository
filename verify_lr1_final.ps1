$ErrorActionPreference="Stop"
$work="C:\LR1_7342835_FINAL_CHECK"
$fam="FAMILIYA_NE_UKAZANA"
$name="IMYA_NE_UKAZANO"
$otch="OTCHESTVO_NE_UKAZANO"
$log=Join-Path $env:GITHUB_WORKSPACE "LR1_FINAL_ACCEPTANCE.txt"
if(Test-Path $work){Remove-Item $work -Recurse -Force}
New-Item -ItemType Directory -Path $work | Out-Null

function RunCmd([string]$cmd){
  Write-Host ("CMD> "+$cmd)
  $out = & cmd.exe /d /s /c $cmd 2>&1
  $out | ForEach-Object { Write-Host $_ }
  return @($out)
}
function Check([bool]$cond,[string]$msg){
  if(!$cond){ throw ("FAIL: "+$msg) }
  Add-Content $log ("PASS: "+$msg)
}
"LR1 FINAL ACCEPTANCE" | Set-Content $log -Encoding UTF8
Add-Content $log ("UTC="+[DateTime]::UtcNow.ToString("s"))
Add-Content $log ""

RunCmd ('md "{0}\{1}\{2}\{3}"' -f $work,$fam,$name,$otch)
RunCmd ('cd /d "{0}\{1}" && (echo {1}>fam.txt) && (echo {2}>name.txt) && (echo {3}>otchestvo.txt) && (echo {1}>fio.docx)' -f $work,$fam,$name,$otch)
RunCmd ('cd /d "{0}\{1}" && copy /b fam.txt+name.txt+otchestvo.txt fio.txt' -f $work,$fam)
RunCmd ('md "{0}\FIO"' -f $work)
RunCmd ('copy "{0}\{1}\name.txt" "{0}\FIO\"' -f $work,$fam)
RunCmd ('copy "{0}\{1}\otchestvo.txt" "{0}\FIO\"' -f $work,$fam)
RunCmd ('move "{0}\{1}\fio.txt" "{0}\FIO\"' -f $work,$fam)
RunCmd ('attrib +R "{0}\FIO\fio.txt"' -f $work)
RunCmd ('ren "{0}\FIO\fio.txt" myfio.txt' -f $work)
RunCmd ('attrib -R "{0}\FIO\myfio.txt"' -f $work)
RunCmd ('copy "{0}\{1}\name.txt" "{0}\{1}\{2}\{3}\name.txt" >nul && copy "{0}\{1}\otchestvo.txt" "{0}\{1}\{2}\{3}\otchestvo.txt" >nul' -f $work,$fam,$name,$otch)
RunCmd ('erase "{0}\{1}\{2}\{3}\name.txt" "{0}\{1}\{2}\{3}\otchestvo.txt"' -f $work,$fam,$name,$otch)
RunCmd ('rd "{0}\{1}\{2}\{3}"' -f $work,$fam,$name,$otch)

Check (Test-Path "$work\$fam\fam.txt") "fam.txt exists in surname directory"
Check (Test-Path "$work\$fam\name.txt") "name.txt exists in surname directory"
Check (Test-Path "$work\$fam\otchestvo.txt") "otchestvo.txt exists in surname directory"
Check (Test-Path "$work\$fam\fio.docx") "fio.docx exists in surname directory"
Check (Test-Path "$work\FIO\name.txt") "name.txt copied to FIO"
Check (Test-Path "$work\FIO\otchestvo.txt") "otchestvo.txt copied to FIO"
Check (!(Test-Path "$work\$fam\fio.txt")) "fio.txt removed from source by MOVE"
Check (!(Test-Path "$work\FIO\fio.txt")) "fio.txt removed after REN"
Check (Test-Path "$work\FIO\myfio.txt") "myfio.txt exists after REN"
Check (!(Test-Path "$work\$fam\$name\$otch")) "patronymic directory removed after ERASE and RD"
Check (Test-Path "$work\$fam\$name") "name directory remains"

$lines=Get-Content "$work\FIO\myfio.txt"
Check ($lines.Count -eq 3) "myfio.txt has exactly three combined lines"
Check ($lines[0].Trim() -eq $fam) "myfio.txt line 1 matches surname placeholder"
Check ($lines[1].Trim() -eq $name) "myfio.txt line 2 matches name placeholder"
Check ($lines[2].Trim() -eq $otch) "myfio.txt line 3 matches patronymic placeholder"

$attr=(Get-Item "$work\FIO\myfio.txt").Attributes
Check (($attr -band [IO.FileAttributes]::ReadOnly) -eq 0) "read-only attribute removed from myfio.txt"

$find=RunCmd ('find /I "{0}" "{1}\{0}\fam.txt" "{1}\{0}\fio.docx" "{1}\FIO\myfio.txt"' -f $fam,$work)
Check (($find -join [Environment]::NewLine) -match [regex]::Escape($fam)) "FIND locates expected text"

$promptCheck=& cmd.exe /d /u /c 'chcp 65001>nul & prompt Привет. Введите команду$G & echo %PROMPT%' 2>&1
Add-Content $log ("PROMPT_CHECK="+($promptCheck -join " "))
Check (($promptCheck -join " ") -match "Привет") "exact Russian prompt can be set natively"

$ver=RunCmd "ver"
Check (($ver -join " ") -match "Windows") "VER returns Windows version"
$ip=RunCmd "ipconfig"
Check (($ip -join " ") -match "IPv4|Windows IP Configuration") "IPCONFIG returns network configuration"
$ns=RunCmd "nslookup mcesii.ru"
Check (($ns -join " ") -match "mcesii.ru|31\.31\.198\.145|2a00:") "NSLOOKUP resolves mcesii.ru"
$ping=RunCmd "ping -n 2 mcesii.ru"
Add-Content $log ("PING_RESULT="+($ping -join " | "))
Add-Content $log "NOTE: ICMP reachability is environment-dependent; DNS resolution is checked separately."

Add-Content $log ""
Add-Content $log "FINAL_TREE:"
(tree $work /F /A) | Add-Content $log
Add-Content $log ""
Add-Content $log "RESULT=PASS"
Get-Content $log
