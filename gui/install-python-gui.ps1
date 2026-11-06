param([string]$Workspace=$env:GITHUB_WORKSPACE)
$ErrorActionPreference="Continue"
$ProgressPreference="SilentlyContinue"
$A=Join-Path $Workspace "gui-artifacts"
New-Item -ItemType Directory -Force -Path $A | Out-Null
$Log=Join-Path $A "python-workflow.log"
function L([string]$m){$s="[$(Get-Date -Format o)] $m";Write-Host $s;Add-Content $Log $s}

$url="https://download.ni.com/support/nipkg/products/ni-c/ni-cds-educational/14.3/online/ni-cds-educational_14.3_online.exe"
$installer=Join-Path $env:RUNNER_TEMP "ni-cds-educational_14.3_online.exe"
L "Downloading signed NI Education 14.3 bootstrapper"
Invoke-WebRequest -Uri $url -OutFile $installer -UseBasicParsing
L "SHA256=$((Get-FileHash $installer -Algorithm SHA256).Hash)"
$sig=Get-AuthenticodeSignature $installer
L "Signature=$($sig.Status) signer=$($sig.SignerCertificate.Subject)"
if($sig.Status -ne "Valid"){exit 10}

$p=Start-Process -FilePath $installer -ArgumentList @("--quiet","--accept-eulas","--prevent-reboot") -PassThru
$done=$p.WaitForExit(480000)
if($done){L "Installer exit=$($p.ExitCode)"}else{L "Installer wrapper timeout";try{Stop-Process -Id $p.Id -Force}catch{}}

$ms=Get-ChildItem "C:\Program Files (x86)\National Instruments","C:\Program Files\National Instruments" -Filter Multisim.exe -Recurse -ErrorAction SilentlyContinue | Select-Object -First 1
if(-not $ms){L "Multisim.exe not found";exit 11}
L "Multisim=$($ms.FullName)"

L "Installing Python UI automation packages"
python -m pip install --disable-pip-version-check --quiet pywinauto pyautogui pillow
L "pip exit=$LASTEXITCODE"
if($LASTEXITCODE -ne 0){exit 12}

$cir=Join-Path $Workspace "gui\7330744_V6_GUI_import.cir"
$target=Join-Path $A "7330744_V6_PhotoRelay.ms14"
$py=Join-Path $Workspace "gui\gui_automation.py"

python $py "$($ms.FullName)" "$cir" "$target" "$A"
$pyExit=$LASTEXITCODE
L "Python GUI exit=$pyExit"

if(Test-Path $target){
  L "MS14 exists size=$((Get-Item $target).Length) sha256=$((Get-FileHash $target -Algorithm SHA256).Hash)"
  $ps32="$env:WINDIR\SysWOW64\WindowsPowerShell\v1.0\powershell.exe"
  & $ps32 -NoProfile -ExecutionPolicy Bypass -File (Join-Path $Workspace "gui\validate-ms14.ps1") -Workspace $Workspace -Ms14 $target
  L "Validation exit=$LASTEXITCODE"
}else{
  L "MS14 missing after Python UI automation"
}

try{taskkill /IM Multisim.exe /T /F | Out-Null}catch{}
exit $pyExit
