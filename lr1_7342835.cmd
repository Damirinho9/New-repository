@echo off
setlocal EnableExtensions EnableDelayedExpansion
set "WORK=C:\LR1_7342835"
set "OUT=%GITHUB_WORKSPACE%\artifacts"
set "LOG=%OUT%\LR1_CMD_TRANSCRIPT.txt"
set "NET=%OUT%\LR1_NETWORK_TRANSCRIPT.txt"
set "FAM=FAMILIYA_NE_UKAZANA"
set "NAME=IMYA_NE_UKAZANO"
set "OTCH=OTCHESTVO_NE_UKAZANO"

if exist "%WORK%" rd /s /q "%WORK%"
md "%WORK%"
if not exist "%OUT%" md "%OUT%"

> "%LOG%" echo LAB 1 PART 1 - NATIVE WINDOWS CMD
>>"%LOG%" echo Runner: %COMPUTERNAME%
>>"%LOG%" echo Date/time:
>>"%LOG%" echo %DATE% %TIME%
>>"%LOG%" echo.
>>"%LOG%" echo NOTE: Student full name was not provided. Literal placeholders are used; no personal data was invented.
>>"%LOG%" echo.

>>"%LOG%" echo ===== TASK 1 =====
>>"%LOG%" echo GUI Properties dialog is unavailable on headless GitHub Actions. Native console size is changed with MODE CON instead.
mode con cols=120 lines=40 >>"%LOG%" 2>&1

>>"%LOG%" echo ===== TASK 2 HELP =====
help >>"%LOG%" 2>&1

>>"%LOG%" echo ===== TASK 3 COLOR HELP =====
color /? >>"%LOG%" 2>&1

>>"%LOG%" echo ===== TASK 4 COLOR CHANGE =====
color 1E
>>"%LOG%" echo Executed: COLOR 1E

>>"%LOG%" echo ===== TASK 5 DIR HELP =====
dir /? >>"%LOG%" 2>&1

>>"%LOG%" echo ===== TASK 6 ROOT DIRECTORY =====
dir C:\ >>"%LOG%" 2>&1

>>"%LOG%" echo ===== TASK 7 HIDDEN FILES C:\Windows =====
dir C:\Windows /A:H >>"%LOG%" 2>&1

>>"%LOG%" echo ===== TASK 8 TREE HELP =====
tree /? >>"%LOG%" 2>&1

>>"%LOG%" echo ===== TASK 9 TREE C: =====
tree C:\ /A | "C:\Program Files\Git\usr\bin\head.exe" -n 120 > "%OUT%\TASK09_TREE_C_HEAD.txt" 2>&1
>>"%LOG%" echo Executed native TREE C:\ /A; first 120 output lines saved to TASK09_TREE_C_HEAD.txt for report evidence.
type "%OUT%\TASK09_TREE_C_HEAD.txt" >>"%LOG%" 2>&1

>>"%LOG%" echo ===== TASK 10 ROOT SORTED BY SIZE =====
dir C:\ /O:S >>"%LOG%" 2>&1

>>"%LOG%" echo ===== TASK 11 WINDOWS SORTED BY DATE/TIME =====
dir C:\Windows /O:D >>"%LOG%" 2>&1

>>"%LOG%" echo ===== TASK 12 MD HELP =====
md /? >>"%LOG%" 2>&1

>>"%LOG%" echo ===== TASK 13 CREATE SURNAME DIRECTORY =====
md "%WORK%\%FAM%"
dir "%WORK%" >>"%LOG%" 2>&1

>>"%LOG%" echo ===== TASK 14 CD HELP =====
cd /? >>"%LOG%" 2>&1

>>"%LOG%" echo ===== TASK 15 ENTER NEW DIRECTORY =====
cd /d "%WORK%\%FAM%"
>>"%LOG%" echo Current directory: %CD%

>>"%LOG%" echo ===== TASK 16 CREATE NAME\PATRONYMIC WITH ONE COMMAND =====
md "%NAME%\%OTCH%"
tree "%WORK%\%FAM%" /A >>"%LOG%" 2>&1

>>"%LOG%" echo ===== TASK 17 CREATE fam.txt name.txt otchestvo.txt =====
>fam.txt echo %FAM%
>name.txt echo %NAME%
>otchestvo.txt echo %OTCH%
dir >>"%LOG%" 2>&1

>>"%LOG%" echo ===== TASK 18 CREATE fio.docx =====
>fio.docx echo %FAM%
dir fio.docx >>"%LOG%" 2>&1
type fio.docx >>"%LOG%" 2>&1

>>"%LOG%" echo ===== TASK 19 COPY HELP =====
copy /? >>"%LOG%" 2>&1

>>"%LOG%" echo ===== TASK 20 COMBINE TXT FILES =====
copy /b fam.txt+name.txt+otchestvo.txt fio.txt >>"%LOG%" 2>&1
dir fio.txt >>"%LOG%" 2>&1

>>"%LOG%" echo ===== TASK 21 TYPE HELP =====
type /? >>"%LOG%" 2>&1

>>"%LOG%" echo ===== TASK 22 TYPE fio.txt =====
type fio.txt >>"%LOG%" 2>&1

>>"%LOG%" echo ===== TASK 23 CREATE C:\LR1_7342835\FIO =====
md "%WORK%\FIO"
dir "%WORK%" >>"%LOG%" 2>&1

>>"%LOG%" echo ===== TASK 24 COPY name.txt and otchestvo.txt TO FIO =====
copy name.txt "%WORK%\FIO\" >>"%LOG%" 2>&1
copy otchestvo.txt "%WORK%\FIO\" >>"%LOG%" 2>&1
dir "%WORK%\FIO" >>"%LOG%" 2>&1

>>"%LOG%" echo ===== TASK 25 MOVE HELP =====
move /? >>"%LOG%" 2>&1

>>"%LOG%" echo ===== TASK 26 MOVE fio.txt TO FIO =====
move fio.txt "%WORK%\FIO\" >>"%LOG%" 2>&1
dir "%WORK%\FIO" >>"%LOG%" 2>&1

>>"%LOG%" echo ===== TASK 27 ATTRIB HELP =====
attrib /? >>"%LOG%" 2>&1

>>"%LOG%" echo ===== TASK 28 SET READ-ONLY ON fio.txt =====
attrib +R "%WORK%\FIO\fio.txt"
attrib "%WORK%\FIO\fio.txt" >>"%LOG%" 2>&1

>>"%LOG%" echo ===== TASK 29 REN HELP =====
ren /? >>"%LOG%" 2>&1

>>"%LOG%" echo ===== TASK 30 RENAME fio.txt TO myfio.txt =====
ren "%WORK%\FIO\fio.txt" myfio.txt
dir "%WORK%\FIO" >>"%LOG%" 2>&1

>>"%LOG%" echo ===== TASK 31 REMOVE READ-ONLY =====
>>"%LOG%" echo Methodical text says fio.txt, but it was renamed in task 30; applying to myfio.txt.
attrib -R "%WORK%\FIO\myfio.txt"
attrib "%WORK%\FIO\myfio.txt" >>"%LOG%" 2>&1

>>"%LOG%" echo ===== TASK 32 ERASE HELP =====
erase /? >>"%LOG%" 2>&1

>>"%LOG%" echo ===== TASK 33 DELETE name.txt otchestvo.txt FROM NAME\PATRONYMIC =====
copy name.txt "%NAME%\%OTCH%\name.txt" >nul
copy otchestvo.txt "%NAME%\%OTCH%\otchestvo.txt" >nul
erase "%NAME%\%OTCH%\name.txt" "%NAME%\%OTCH%\otchestvo.txt" >>"%LOG%" 2>&1
dir "%NAME%\%OTCH%" >>"%LOG%" 2>&1

>>"%LOG%" echo ===== TASK 34 RD HELP =====
rd /? >>"%LOG%" 2>&1

>>"%LOG%" echo ===== TASK 35 DELETE PATRONYMIC DIRECTORY =====
rd "%NAME%\%OTCH%" >>"%LOG%" 2>&1
tree "%WORK%\%FAM%" /A >>"%LOG%" 2>&1

>>"%LOG%" echo ===== TASK 36 FIND HELP =====
find /? >>"%LOG%" 2>&1

>>"%LOG%" echo ===== TASK 37 FIND FILES CONTAINING SURNAME PLACEHOLDER =====
find /I "%FAM%" fam.txt fio.docx "%WORK%\FIO\myfio.txt" >>"%LOG%" 2>&1

>>"%LOG%" echo ===== TASK 38 SYSTEMINFO HELP =====
systeminfo /? >>"%LOG%" 2>&1

>>"%LOG%" echo ===== TASK 39 SYSTEMINFO =====
systeminfo > "%OUT%\TASK39_SYSTEMINFO.txt" 2>&1
type "%OUT%\TASK39_SYSTEMINFO.txt" >>"%LOG%"

>>"%LOG%" echo ===== TASK 40 VER HELP / COMMAND =====
help ver >>"%LOG%" 2>&1

>>"%LOG%" echo ===== TASK 41 WINDOWS VERSION =====
ver >>"%LOG%" 2>&1

>>"%LOG%" echo ===== TASK 42 SYSTEM CONFIGURATION AGAIN =====
systeminfo >>"%LOG%" 2>&1

>>"%LOG%" echo ===== TASK 43 DATE AND TIME =====
date /t >>"%LOG%" 2>&1
time /t >>"%LOG%" 2>&1

>>"%LOG%" echo ===== TASK 44 PROMPT HELP =====
prompt /? >>"%LOG%" 2>&1

>>"%LOG%" echo ===== TASK 45 CHANGE PROMPT =====
prompt Hello. Enter command$G
>>"%LOG%" echo Prompt changed natively. Non-ASCII prompt is avoided because student data/language encoding is not supplied in headless runner.

>>"%LOG%" echo ===== TASK 46 CURRENT DIRECTORY CONTENTS =====
dir >>"%LOG%" 2>&1

>>"%LOG%" echo ===== TASK 47 RESTORE PROMPT =====
prompt $P$G
>>"%LOG%" echo Prompt restored to $P$G

>>"%LOG%" echo ===== TASK 48 EXIT =====
cmd /c exit
>>"%LOG%" echo Child CMD exited successfully.

> "%NET%" echo LAB 1 PART 2 - NATIVE WINDOWS NETWORK UTILITIES
>>"%NET%" echo Runner: %COMPUTERNAME%
>>"%NET%" echo Date/time: %DATE% %TIME%
>>"%NET%" echo.

>>"%NET%" echo ===== TASK 1 HELP IPCONFIG =====
ipconfig /? >>"%NET%" 2>&1
>>"%NET%" echo ===== TASK 1 HELP ARP =====
arp /? >>"%NET%" 2>&1
>>"%NET%" echo ===== TASK 1 HELP GETMAC =====
getmac /? >>"%NET%" 2>&1
>>"%NET%" echo ===== TASK 1 HELP NETSTAT =====
netstat /? >>"%NET%" 2>&1
>>"%NET%" echo ===== TASK 1 HELP NSLOOKUP =====
nslookup /? >>"%NET%" 2>&1
>>"%NET%" echo ===== TASK 1 HELP PING =====
ping /? >>"%NET%" 2>&1

>>"%NET%" echo ===== TASK 2 IPCONFIG SHORT =====
ipconfig >>"%NET%" 2>&1
>>"%NET%" echo ===== TASK 2 IPCONFIG FULL =====
ipconfig /all >>"%NET%" 2>&1

>>"%NET%" echo ===== TASK 3 ARP TABLE =====
arp -a >>"%NET%" 2>&1

>>"%NET%" echo ===== TASK 4 GETMAC =====
getmac /v >>"%NET%" 2>&1

>>"%NET%" echo ===== TASK 5 NETSTAT TCP/UDP AND LISTENING =====
netstat -ano >>"%NET%" 2>&1

>>"%NET%" echo ===== EXTRA NSLOOKUP mcesii.ru =====
nslookup mcesii.ru >>"%NET%" 2>&1

>>"%NET%" echo ===== TASK 6 PING mcesii.ru =====
ping -n 4 mcesii.ru >>"%NET%" 2>&1

> "%OUT%\FINAL_TREE.txt" tree "%WORK%" /F /A
> "%OUT%\FINAL_DIR_FIO.txt" dir "%WORK%\FIO"
> "%OUT%\FINAL_DIR_SURNAME.txt" dir "%WORK%\%FAM%"

echo Native CMD lab execution completed.
endlocal

rem trigger dedicated tree workflow

rem final trigger
