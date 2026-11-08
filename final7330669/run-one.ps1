param(
  [string]$Workspace=$env:GITHUB_WORKSPACE,
  [ValidateSet("lab2","lab3","lab4")][string]$Lab
)
$ErrorActionPreference="Continue"
$ProgressPreference="SilentlyContinue"

$Root=Join-Path $Workspace "final7330669"
$Out=Join-Path $Workspace ("final7330669-" + $Lab + "-artifacts")
New-Item -ItemType Directory -Force -Path $Out | Out-Null
$Log=Join-Path $Out "runner.log"

function L([string]$m){
  $s="[$(Get-Date -Format o)] $m"
  Write-Host $s
  Add-Content -Path $Log -Value $s
}

$url="https://download.ni.com/support/nipkg/products/ni-c/ni-cds-educational/14.3/online/ni-cds-educational_14.3_online.exe"
$installer=Join-Path $env:RUNNER_TEMP "ni-cds-educational_14.3_online.exe"
L "Downloading official signed NI Multisim 14.3 Education installer"
Invoke-WebRequest -Uri $url -OutFile $installer -UseBasicParsing
$sig=Get-AuthenticodeSignature $installer
L "Installer signature=$($sig.Status) signer=$($sig.SignerCertificate.Subject)"
if($sig.Status -ne "Valid"){ exit 10 }

$p=Start-Process -FilePath $installer -ArgumentList @("--quiet","--accept-eulas","--prevent-reboot") -PassThru
$finished=$p.WaitForExit(480000)
if(-not $finished){
  L "Installer wrapper timeout after 480 sec"
  try{Stop-Process -Id $p.Id -Force}catch{}
}else{
  L "Installer wrapper exit=$($p.ExitCode)"
}

$ms=$null
for($i=0;$i -lt 36;$i++){
  $ms=Get-ChildItem "C:\Program Files (x86)\National Instruments","C:\Program Files\National Instruments" -Filter Multisim.exe -Recurse -ErrorAction SilentlyContinue | Select-Object -First 1
  if($ms){break}
  Start-Sleep -Seconds 10
}
if(-not $ms){L "Multisim.exe not found";exit 11}
L "Multisim=$($ms.FullName)"

python -m pip install --disable-pip-version-check --quiet pywinauto pyautogui pillow

$script=Join-Path $Root ($Lab + "_final.py")
L "START $script"
python $script "$($ms.FullName)" "$Out"
$code=$LASTEXITCODE
L "END $Lab exit=$code"
try{taskkill /IM Multisim.exe /T /F | Out-Null}catch{}

if($code -ne 0){ exit $code }
L "NATIVE_${Lab}_OK"
exit 0
