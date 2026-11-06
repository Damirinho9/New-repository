param([string]$Workspace=$env:GITHUB_WORKSPACE)
$ErrorActionPreference="Continue"
$ProgressPreference="SilentlyContinue"
$A=Join-Path $Workspace "stage7-artifacts"
New-Item -ItemType Directory -Force -Path $A | Out-Null

function L([string]$m){
  $s="[$(Get-Date -Format o)] $m"
  Write-Host $s
  Add-Content (Join-Path $A "workflow.log") $s
}

$url="https://f1.199server.site/Pro/Altium%20Designer%2026.11.1.5%20x64.rar"
$rar=Join-Path $env:RUNNER_TEMP "altium.rar"
$media=Join-Path $env:RUNNER_TEMP "altium-media"
$seven="C:\Program Files\7-Zip\7z.exe"

L "Download verified offline media"
& curl.exe -L --fail --retry 3 --retry-delay 5 -o $rar $url
if($LASTEXITCODE -ne 0){L "download failed";exit 10}

$rarHash=(Get-FileHash $rar -Algorithm SHA256).Hash
L "RAR SHA256=$rarHash"
if($rarHash -ne "5CF8E6CF7CE18C521B12D3CF9091207756D4697ADF5FF7DD323D340308AFF0A1"){
  L "RAR hash changed"
  exit 11
}

L "Extract offline media"
& $seven x -y "-o$media" $rar *> (Join-Path $A "extract.log")
if($LASTEXITCODE -ne 0){L "extract failed";exit 12}

$root=Get-ChildItem $media -Directory | Select-Object -First 1
$installer=Join-Path $root.FullName "Installer.Exe"
if(-not (Test-Path $installer)){L "Installer missing";exit 13}

$sig=Get-AuthenticodeSignature $installer
L "Installer signature=$($sig.Status) signer=$($sig.SignerCertificate.Subject)"
if($sig.Status -ne "Valid"){exit 14}

$ih=(Get-FileHash $installer -Algorithm SHA256).Hash
L "Installer SHA256=$ih"
if($ih -ne "9D4FB5B69526435192566A2723A3B26A726EF2CCC9F168864EC31C6B02DC552F"){
  L "Installer hash mismatch"
  exit 15
}

$programs="C:\AD26"
$documents="C:\AD26Docs"
L "Install Altium to $programs"
$args=@("-Programs:$programs","-Documents:$documents","-UI:None","-AutoInstall","-InstallAll")
$p=Start-Process -FilePath $installer -ArgumentList $args -Wait -PassThru
L "Installer exit=$($p.ExitCode)"

$x2=Get-ChildItem $programs -Filter "X2.EXE" -Recurse -ErrorAction SilentlyContinue | Select-Object -First 1
if(-not $x2){
  L "X2.EXE not found under C:\AD26"
  Get-ChildItem "C:\" -Filter "X2.EXE" -Recurse -ErrorAction SilentlyContinue |
    Select FullName,Length,LastWriteTime |
    Format-List | Out-File (Join-Path $A "x2-search.txt")
  exit 20
}

L "X2=$($x2.FullName) version=$($x2.VersionInfo.FileVersion)"
$xsig=Get-AuthenticodeSignature $x2.FullName
L "X2 signature=$($xsig.Status) signer=$($xsig.SignerCertificate.Subject)"

$out="C:\7330744_Altium"
if(Test-Path $out){Remove-Item $out -Recurse -Force}
New-Item -ItemType Directory -Force -Path $out | Out-Null

$scriptProject=Join-Path $Workspace "altium-stage7\BuildPhotoRelay.PrjScr"
$proc="BuildPhotoRelay>Run"
$dq=[char]34
$runarg="-RScriptingSystem:RunScript(ProjectName=" + $dq + $scriptProject + $dq + "^|ProcName=" + $dq + $proc + $dq + ")"

L "Launch Altium DelphiScript"
L "RunArg=$runarg"
$ap=Start-Process -FilePath $x2.FullName -ArgumentList $runarg -PassThru
L "Altium PID=$($ap.Id)"

$status=Join-Path $out "stage7-status.txt"
$success=$false
for($i=0;$i -lt 180;$i++){
  Start-Sleep -Seconds 2
  if(Test-Path $status){
    $txt=Get-Content $status -Raw -ErrorAction SilentlyContinue
    if($txt -match "SUCCESS=1"){$success=$true;break}
    if($txt -match "ERROR="){break}
  }
  if($ap.HasExited){break}
}

if(Test-Path $status){
  Copy-Item $status (Join-Path $A "stage7-status.txt") -Force
  L "Status file produced"
}else{
  L "No stage7-status.txt was produced"
}

try{
  Add-Type -AssemblyName System.Windows.Forms
  Add-Type -AssemblyName System.Drawing
  $b=[System.Windows.Forms.Screen]::PrimaryScreen.Bounds
  $bmp=New-Object System.Drawing.Bitmap $b.Width,$b.Height
  $g=[System.Drawing.Graphics]::FromImage($bmp)
  $g.CopyFromScreen($b.Location,[System.Drawing.Point]::Empty,$b.Size)
  $bmp.Save((Join-Path $A "altium-stage7-screen.png"),[System.Drawing.Imaging.ImageFormat]::Png)
  $g.Dispose()
  $bmp.Dispose()
  L "Screenshot saved"
}catch{
  L "Screenshot error=$($_.Exception.Message)"
}

Get-Process | Where-Object {$_.ProcessName -match "X2|Altium"} |
  Select ProcessName,Id,MainWindowTitle,Path |
  Format-List | Out-File (Join-Path $A "processes.txt")

if(Test-Path $out){
  Copy-Item "$out\*" $A -Force -ErrorAction SilentlyContinue
}

Get-ChildItem $A |
  Select Name,Length,LastWriteTime |
  Format-Table -AutoSize | Out-File (Join-Path $A "inventory.txt")

try{taskkill /PID $ap.Id /T /F *> (Join-Path $A "taskkill.txt")}catch{}

if($success){
  L "STAGE7 SUCCESS"
  exit 0
}

L "STAGE7 NOT COMPLETE"
exit 30
