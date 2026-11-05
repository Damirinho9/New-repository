param([string]$Workspace=$env:GITHUB_WORKSPACE)
$ErrorActionPreference="Continue"
$ProgressPreference="SilentlyContinue"
$A=Join-Path $Workspace "stage5-artifacts"
New-Item -ItemType Directory -Force -Path $A | Out-Null
$log=Join-Path $A "stage5-runner.log"
function L([string]$m){$s="[$(Get-Date -Format o)] $m";Write-Host $s;Add-Content $log $s}

$url="https://download.ni.com/support/nipkg/products/ni-c/ni-cds-professional/14.3/online/ni-cds-professional_14.3_online.exe"
$installer=Join-Path $env:RUNNER_TEMP "ni-cds-professional_14.3_online.exe"
L "Downloading official NI installer"
Invoke-WebRequest -Uri $url -OutFile $installer -UseBasicParsing
L "Installer SHA256=$((Get-FileHash $installer -Algorithm SHA256).Hash)"
$p=Start-Process -FilePath $installer -ArgumentList @("--quiet","--accept-eulas","--prevent-reboot") -Wait -PassThru
L "Installer exit=$($p.ExitCode)"

$ms=Get-ChildItem "C:\Program Files (x86)\National Instruments","C:\Program Files\National Instruments" -Filter "Multisim.exe" -Recurse -ErrorAction SilentlyContinue | Select-Object -First 1
if(-not $ms){L "Multisim.exe not found";exit 2}
L "Multisim=$($ms.FullName)"

Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
Add-Type @"
using System;
using System.Runtime.InteropServices;
public static class Win32 {
  [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr hWnd);
  [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr hWnd, int nCmdShow);
}
"@

function GrabDesktop([string]$path){
  $b=[System.Windows.Forms.Screen]::PrimaryScreen.Bounds
  $bmp=New-Object System.Drawing.Bitmap $b.Width,$b.Height
  $g=[System.Drawing.Graphics]::FromImage($bmp)
  $g.CopyFromScreen($b.Location,[System.Drawing.Point]::Empty,$b.Size)
  $bmp.Save($path,[System.Drawing.Imaging.ImageFormat]::Png)
  $g.Dispose();$bmp.Dispose()
}

# Launch the real Multisim UI and use File > Open to import the .cir graphically.
$proc=Start-Process -FilePath $ms.FullName -PassThru
L "Multisim GUI PID=$($proc.Id)"
for($i=0;$i -lt 20;$i++){
  Start-Sleep -Seconds 2
  $proc.Refresh()
  if($proc.MainWindowHandle -ne 0){break}
}
$proc.Refresh()
L "MainWindowTitle=$($proc.MainWindowTitle) Handle=$($proc.MainWindowHandle)"
if($proc.MainWindowHandle -ne 0){
  [Win32]::ShowWindow($proc.MainWindowHandle,3) | Out-Null
  [Win32]::SetForegroundWindow($proc.MainWindowHandle) | Out-Null
  Start-Sleep -Seconds 2
  $ws=New-Object -ComObject WScript.Shell
  $ws.AppActivate($proc.Id) | Out-Null
  $ws.SendKeys("^o")
  Start-Sleep -Seconds 2
  $cir=Join-Path $Workspace "multisim\7330744_V6_PhotoRelay_3state_Multisim.cir"
  $ws.SendKeys($cir)
  $ws.SendKeys("{ENTER}")
  Start-Sleep -Seconds 12
  # Accept a possible import/status dialog.
  $ws.SendKeys("{ENTER}")
  Start-Sleep -Seconds 8
  $proc.Refresh()
  [Win32]::ShowWindow($proc.MainWindowHandle,3) | Out-Null
  [Win32]::SetForegroundWindow($proc.MainWindowHandle) | Out-Null
  Start-Sleep -Seconds 2
  GrabDesktop (Join-Path $A "00_multisim_imported_circuit_desktop.png")
  L "Captured Multisim imported circuit desktop"
}else{
  L "No GUI window handle"
}

# Actual DC transfer sweep through 32-bit Multisim COM.
$ps32="$env:WINDIR\SysWOW64\WindowsPowerShell\v1.0\powershell.exe"
& $ps32 -NoProfile -ExecutionPolicy Bypass -File (Join-Path $Workspace "stage5\run-transfer-com.ps1") -Workspace $Workspace
L "Transfer worker exit=$LASTEXITCODE"

try{taskkill /IM Multisim.exe /T /F | Out-Null}catch{}
