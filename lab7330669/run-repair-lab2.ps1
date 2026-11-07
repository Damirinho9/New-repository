param([string]$Workspace=$env:GITHUB_WORKSPACE)
$ErrorActionPreference="Continue"
$ProgressPreference="SilentlyContinue"
$Out=Join-Path $Workspace "lab7330669-repair-artifacts"
New-Item -ItemType Directory -Force -Path $Out | Out-Null
function L([string]$m){$s="[$(Get-Date -Format o)] $m";Write-Host $s;Add-Content (Join-Path $Out "repair-install.log") $s}

$url="https://download.ni.com/support/nipkg/products/ni-c/ni-cds-educational/14.3/online/ni-cds-educational_14.3_online.exe"
$installer=Join-Path $env:RUNNER_TEMP "ni-cds-educational_14.3_online.exe"
Invoke-WebRequest -Uri $url -OutFile $installer -UseBasicParsing
$sig=Get-AuthenticodeSignature $installer
L "installer sig=$($sig.Status)"
if($sig.Status -ne "Valid"){exit 10}
$p=Start-Process -FilePath $installer -ArgumentList @("--quiet","--accept-eulas","--prevent-reboot") -PassThru
$null=$p.WaitForExit(480000)

$ms=$null
for($i=0;$i -lt 30;$i++){
  $ms=Get-ChildItem "C:\Program Files (x86)\National Instruments","C:\Program Files\National Instruments" -Filter Multisim.exe -Recurse -ErrorAction SilentlyContinue | Select-Object -First 1
  if($ms){break}
  Start-Sleep 10
}
if(-not $ms){L "Multisim not found";exit 11}
L "Multisim=$($ms.FullName)"

python -m pip install --disable-pip-version-check --quiet pywinauto pyautogui pillow

$env:GH_TOKEN=$env:GITHUB_TOKEN
$prev=Join-Path $Workspace "previous-lab2"
New-Item -ItemType Directory -Force -Path $prev | Out-Null
gh run download 42394411650 -n multisim-7330669-lab2-native -D $prev
if($LASTEXITCODE -ne 0){L "gh download failed";exit 12}

$src=Get-ChildItem $prev -Filter "Lab2_DC_Circuit.ms14" -Recurse | Where-Object {$_.Name -notmatch "Security"} | Select-Object -First 1
if(-not $src){L "previous ms14 not found";exit 13}
L "source=$($src.FullName) size=$($src.Length)"

python (Join-Path $Workspace "lab7330669\repair_lab2_existing.py") "$($ms.FullName)" "$($src.FullName)" "$Out"
$code=$LASTEXITCODE
L "repair exit=$code"
try{taskkill /IM Multisim.exe /T /F | Out-Null}catch{}
exit $code
