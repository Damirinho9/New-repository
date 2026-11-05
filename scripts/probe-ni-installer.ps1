param([string]$Workspace=$env:GITHUB_WORKSPACE)
$ErrorActionPreference="Continue"
$A=Join-Path $Workspace "probe-artifacts"
New-Item -ItemType Directory -Force -Path $A | Out-Null
function L([string]$m){$s="[$(Get-Date -Format o)] $m"; Write-Host $s; Add-Content (Join-Path $A "probe.log") $s}

$url="https://download.ni.com/support/nipkg/products/ni-c/ni-cds-professional/14.3/online/ni-cds-professional_14.3_online.exe"
$exe=Join-Path $env:RUNNER_TEMP "ni-cds-professional_14.3_online.exe"
Invoke-WebRequest -Uri $url -OutFile $exe -UseBasicParsing
L "Downloaded installer: $((Get-Item $exe).Length) bytes"
L "SHA256=$((Get-FileHash $exe -Algorithm SHA256).Hash)"

# NI docs recommend passive for older NIPM generations; start detached so diagnostics can proceed.
$p=Start-Process -FilePath $exe -ArgumentList @("--passive","--accept-eulas","--prevent-reboot") -PassThru
L "Started installer PID=$($p.Id)"

for($i=1;$i -le 4;$i++){
  Start-Sleep -Seconds 60
  L "Minute $i"
  Get-Process | Where-Object {$_.ProcessName -match "ni|package|setup|install|multisim"} |
    Select-Object ProcessName,Id,CPU,StartTime,Path |
    Format-Table -AutoSize | Out-String | Add-Content (Join-Path $A "processes.txt")
  $nipkg=@(
    "C:\Program Files\National Instruments\NI Package Manager\nipkg.exe",
    "C:\Program Files (x86)\National Instruments\NI Package Manager\nipkg.exe"
  ) | Where-Object {Test-Path $_} | Select-Object -First 1
  if($nipkg){ L "NIPM found: $nipkg"; try{& $nipkg list *> (Join-Path $A "nipkg-list.txt")}catch{} }
  $ms=Get-ChildItem "C:\Program Files*","C:\ProgramData" -Filter Multisim.exe -Recurse -ErrorAction SilentlyContinue | Select-Object -First 5
  if($ms){ L "Multisim found"; $ms | Select FullName,Length,LastWriteTime | Format-List | Out-File (Join-Path $A "multisim-found.txt") }
}

try{
  Add-Type -AssemblyName System.Windows.Forms
  Add-Type -AssemblyName System.Drawing
  $b=[System.Windows.Forms.Screen]::PrimaryScreen.Bounds
  $bmp=New-Object System.Drawing.Bitmap $b.Width,$b.Height
  $g=[System.Drawing.Graphics]::FromImage($bmp)
  $g.CopyFromScreen($b.Location,[System.Drawing.Point]::Empty,$b.Size)
  $bmp.Save((Join-Path $A "desktop-after-4min.png"),[System.Drawing.Imaging.ImageFormat]::Png)
  $g.Dispose(); $bmp.Dispose()
  L "Screenshot saved"
}catch{L "Screenshot failed: $($_.Exception.Message)"}

if(-not $p.HasExited){
  L "Installer still running after 4 minutes; terminating probe process tree."
  taskkill /PID $p.Id /T /F *> (Join-Path $A "taskkill.txt")
}else{
  L "Installer exited code=$($p.ExitCode)"
}

# Final inventory
Get-ChildItem "C:\Program Files\National Instruments","C:\Program Files (x86)\National Instruments" -ErrorAction SilentlyContinue |
  Select FullName | Out-File (Join-Path $A "ni-roots.txt")
