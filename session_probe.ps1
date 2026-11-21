$ErrorActionPreference="Continue"
Write-Host "CURRENT SESSION"
whoami
(Get-Process -Id $PID).SessionId
Write-Host "QWINSTA"
qwinsta
Write-Host "QUERY SESSION"
query session
Write-Host "PROCESSES"
Get-Process explorer,dwm,LogonUI,winlogon -ErrorAction SilentlyContinue | Format-Table Name,Id,SessionId,MainWindowHandle

# trigger session probe
