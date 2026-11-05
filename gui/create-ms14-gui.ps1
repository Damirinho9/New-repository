param([string]$Workspace=$env:GITHUB_WORKSPACE)
$ErrorActionPreference="Continue"
$ProgressPreference="SilentlyContinue"
$A=Join-Path $Workspace "gui-artifacts"
New-Item -ItemType Directory -Force -Path $A | Out-Null
$Log=Join-Path $A "gui-runner.log"
function L([string]$m){$s="[$(Get-Date -Format o)] $m";Write-Host $s;Add-Content $Log $s}

function Start-WatchedProcess {
  param(
    [string]$FilePath,
    [string[]]$Arguments,
    [int]$TimeoutSeconds,
    [string]$Label
  )
  L ("Starting " + $Label)
  try{
    $p=Start-Process -FilePath $FilePath -ArgumentList $Arguments -PassThru
    L ($Label + " PID=" + $p.Id)
    $finished=$p.WaitForExit($TimeoutSeconds*1000)
    if($finished){L ($Label + " exited code=" + $p.ExitCode);return $p.ExitCode}
    L ($Label + " wrapper timeout after " + $TimeoutSeconds + " sec")
    try{Stop-Process -Id $p.Id -Force -ErrorAction SilentlyContinue}catch{}
    return 99998
  }catch{
    L ($Label + " start error=" + $_.Exception.Message)
    return 99999
  }
}

Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
Add-Type @"
using System;
using System.Runtime.InteropServices;
public static class NativeWin {
  [StructLayout(LayoutKind.Sequential)]
  public struct RECT { public int Left, Top, Right, Bottom; }
  [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr hWnd);
  [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr hWnd, int cmd);
  [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr hWnd, out RECT rect);
}
"@

function GrabDesktop([string]$name){
  try{
    $b=[System.Windows.Forms.Screen]::PrimaryScreen.Bounds
    $bmp=New-Object System.Drawing.Bitmap $b.Width,$b.Height
    $g=[System.Drawing.Graphics]::FromImage($bmp)
    $g.CopyFromScreen($b.Location,[System.Drawing.Point]::Empty,$b.Size)
    $p=Join-Path $A $name
    $bmp.Save($p,[System.Drawing.Imaging.ImageFormat]::Png)
    $g.Dispose();$bmp.Dispose()
    L "Desktop screenshot: $p"
  }catch{L "Desktop screenshot error: $($_.Exception.Message)"}
}

function GrabWindow([IntPtr]$h,[string]$name){
  try{
    $r=New-Object NativeWin+RECT
    if([NativeWin]::GetWindowRect($h,[ref]$r)){
      $w=[Math]::Max(1,$r.Right-$r.Left);$hh=[Math]::Max(1,$r.Bottom-$r.Top)
      $bmp=New-Object System.Drawing.Bitmap $w,$hh
      $g=[System.Drawing.Graphics]::FromImage($bmp)
      $g.CopyFromScreen((New-Object System.Drawing.Point($r.Left,$r.Top)),[System.Drawing.Point]::Empty,(New-Object System.Drawing.Size($w,$hh)))
      $p=Join-Path $A $name
      $bmp.Save($p,[System.Drawing.Imaging.ImageFormat]::Png)
      $g.Dispose();$bmp.Dispose()
      L ("Window screenshot: " + $p + " " + $w + "x" + $hh)
    }
  }catch{L "Window screenshot error: $($_.Exception.Message)"}
}

$installerUrl="https://download.ni.com/support/nipkg/products/ni-c/ni-cds-professional/14.3/online/ni-cds-professional_14.3_online.exe"
$installer=Join-Path $env:RUNNER_TEMP "ni-cds-professional_14.3_online.exe"
L "Downloading official NI Professional 14.3 bootstrapper"
try{
  Invoke-WebRequest -Uri $installerUrl -OutFile $installer -UseBasicParsing
}catch{
  L "Download failed: $($_.Exception.ToString())"
  exit 10
}
$hash=(Get-FileHash $installer -Algorithm SHA256).Hash.ToLower()
L "Installer size=$((Get-Item $installer).Length) SHA256=$hash"
L "Known Professional bootstrapper SHA256=2cae359f70209dde2b3c1a6737a107a32a0847fdaacd2d31530788c247dcd9f2"
$sig=Get-AuthenticodeSignature $installer
L "Signature status=$($sig.Status) signer=$($sig.SignerCertificate.Subject)"
if($sig.Status -ne "Valid"){L "Installer signature invalid";exit 11}

L "Installing NI Circuit Design Suite Professional 14.3 with bounded bootstrapper wait"
$boot=Start-WatchedProcess -FilePath $installer -Arguments @("--quiet","--accept-eulas","--prevent-reboot") -TimeoutSeconds 480 -Label "NI bootstrapper"
L ("Bootstrapper stage returned " + $boot)

function Find-Multisim {
  Get-ChildItem "C:\Program Files (x86)\National Instruments","C:\Program Files\National Instruments" -Filter "Multisim.exe" -Recurse -ErrorAction SilentlyContinue | Select-Object -First 1
}

$ms=$null
for($i=0;$i -lt 12;$i++){
  $ms=Find-Multisim
  if($ms){break}
  Start-Sleep -Seconds 10
}

# If wrapper ended but product is not present, use NI Package Manager URI embedded in the signed bootstrapper.
if(-not $ms){
  $nipm=@(
    "C:\Program Files\National Instruments\NI Package Manager\NIPackageManager.exe",
    "C:\Program Files (x86)\National Instruments\NI Package Manager\NIPackageManager.exe"
  ) | Where-Object {Test-Path $_} | Select-Object -First 1
  if($nipm){
    L "Multisim not found after bootstrapper; trying direct NI install-item URI"
    $uri="nipkg://store/1/install-item/ni-cds-professional_14.3"
    $dc=Start-WatchedProcess -FilePath $nipm -Arguments @("--uri=$uri","--quiet","--accept-eulas","--prevent-reboot") -TimeoutSeconds 900 -Label "NI Package Manager direct install"
    L ("Direct URI stage returned " + $dc)
  }
  for($i=0;$i -lt 30;$i++){
    $ms=Find-Multisim
    if($ms){break}
    Start-Sleep -Seconds 10
  }
}

if(-not $ms){L "Multisim.exe not found";GrabDesktop "00_install_failed.png";exit 12}
L "Multisim.exe=$($ms.FullName)"
L "Multisim SHA256=$((Get-FileHash $ms.FullName -Algorithm SHA256).Hash)"

$cir=Join-Path $Workspace "gui\7330744_V6_GUI_import.cir"
$target=Join-Path $A "7330744_V6_PhotoRelay.ms14"
L "GUI import source=$cir"
L "Target design=$target"

$launched=Start-Process -FilePath $ms.FullName -PassThru
L "Started Multisim PID=$($launched.Id)"
Start-Sleep -Seconds 4

$mp=$null
for($i=0;$i -lt 30;$i++){
  $candidates=Get-Process -Name "Multisim" -ErrorAction SilentlyContinue | Where-Object {$_.MainWindowHandle -ne 0}
  if($candidates){$mp=$candidates | Select-Object -First 1;break}
  Start-Sleep -Seconds 2
}
if(-not $mp){L "No Multisim window";GrabDesktop "01_no_window.png";exit 13}
$mp.Refresh()
L "Window title=$($mp.MainWindowTitle) handle=$($mp.MainWindowHandle)"
[NativeWin]::ShowWindow($mp.MainWindowHandle,3)|Out-Null
[NativeWin]::SetForegroundWindow($mp.MainWindowHandle)|Out-Null

$ws=New-Object -ComObject WScript.Shell
$ws.AppActivate($mp.Id)|Out-Null
Start-Sleep -Seconds 2
GrabWindow $mp.MainWindowHandle "01_blank_multisim.png"

$ws.SendKeys("^o")
Start-Sleep -Seconds 2
$ws.SendKeys($cir)
$ws.SendKeys("{ENTER}")
L "Sent File/Open for .cir"
Start-Sleep -Seconds 18
GrabDesktop "02_after_cir_open_desktop.png"

$ws.SendKeys("{ENTER}")
Start-Sleep -Seconds 6
$mp=(Get-Process -Name "Multisim" -ErrorAction SilentlyContinue | Where-Object {$_.MainWindowHandle -ne 0} | Select-Object -First 1)
if($mp){
  [NativeWin]::ShowWindow($mp.MainWindowHandle,3)|Out-Null
  [NativeWin]::SetForegroundWindow($mp.MainWindowHandle)|Out-Null
  $ws.AppActivate($mp.Id)|Out-Null
  GrabWindow $mp.MainWindowHandle "03_imported_schematic.png"
}
GrabDesktop "03_imported_schematic_desktop.png"

$ws.AppActivate($mp.Id)|Out-Null
$ws.SendKeys("%f")
Start-Sleep -Milliseconds 700
$ws.SendKeys("a")
Start-Sleep -Seconds 2
$ws.SendKeys($target)
$ws.SendKeys("{ENTER}")
L "Sent File/Save As path"
Start-Sleep -Seconds 7
$ws.SendKeys("{ENTER}")
Start-Sleep -Seconds 4
GrabDesktop "04_after_save_desktop.png"

if(-not (Test-Path $target)){
  L "First Save As route did not create target; trying Ctrl+Shift+S"
  $ws.AppActivate($mp.Id)|Out-Null
  $ws.SendKeys("^+s")
  Start-Sleep -Seconds 2
  $ws.SendKeys($target)
  $ws.SendKeys("{ENTER}")
  Start-Sleep -Seconds 6
  $ws.SendKeys("{ENTER}")
  Start-Sleep -Seconds 3
}

$found=@()
if(Test-Path $target){$found=@(Get-Item $target)}
if(-not $found){
  $found=Get-ChildItem $A,$Workspace,$env:USERPROFILE -Filter "*.ms14" -Recurse -ErrorAction SilentlyContinue | Sort-Object LastWriteTime -Descending | Select-Object -First 5
  $found | Select FullName,Length,LastWriteTime | Format-List | Out-File (Join-Path $A "found-ms14.txt")
  if($found){
    Copy-Item $found[0].FullName $target -Force
    L "Normalized found ms14 from $($found[0].FullName)"
  }
}

if(Test-Path $target){
  L "MS14 created size=$((Get-Item $target).Length) SHA256=$((Get-FileHash $target -Algorithm SHA256).Hash)"
}else{
  L "MS14 was not created"
  GrabDesktop "05_save_failed.png"
}

if(Test-Path $target){
  $ps32="$env:WINDIR\SysWOW64\WindowsPowerShell\v1.0\powershell.exe"
  & $ps32 -NoProfile -ExecutionPolicy Bypass -File (Join-Path $Workspace "gui\validate-ms14.ps1") -Workspace $Workspace -Ms14 $target
  L "Validation worker exit=$LASTEXITCODE"
}

$mp=(Get-Process -Name "Multisim" -ErrorAction SilentlyContinue | Where-Object {$_.MainWindowHandle -ne 0} | Select-Object -First 1)
if($mp){
  [NativeWin]::ShowWindow($mp.MainWindowHandle,3)|Out-Null
  [NativeWin]::SetForegroundWindow($mp.MainWindowHandle)|Out-Null
  Start-Sleep -Seconds 2
  GrabWindow $mp.MainWindowHandle "06_final_multisim_workspace.png"
}
GrabDesktop "06_final_desktop.png"

try{taskkill /IM Multisim.exe /T /F | Out-Null}catch{}
if(Test-Path $target){exit 0}else{exit 20}
