param([string]$Workspace=$env:GITHUB_WORKSPACE)

$ErrorActionPreference="Continue"
$ProgressPreference="SilentlyContinue"

$Out=Join-Path $Workspace "lab7330669-lab4-artifacts"
New-Item -ItemType Directory -Force -Path $Out | Out-Null
$Log=Join-Path $Out "install-native-gui.log"

function L([string]$m){
  $s="[$(Get-Date -Format o)] $m"
  Write-Host $s
  Add-Content -Path $Log -Value $s
}

$url="https://download.ni.com/support/nipkg/products/ni-c/ni-cds-educational/14.3/online/ni-cds-educational_14.3_online.exe"
$installer=Join-Path $env:RUNNER_TEMP "ni-cds-educational_14.3_online.exe"

L "Downloading official signed NI Multisim 14.3 Education installer"
Invoke-WebRequest -Uri $url -OutFile $installer -UseBasicParsing
L "Installer SHA256=$((Get-FileHash $installer -Algorithm SHA256).Hash)"

$sig=Get-AuthenticodeSignature $installer
L "Signature=$($sig.Status) signer=$($sig.SignerCertificate.Subject)"
if($sig.Status -ne "Valid"){ exit 10 }

$p=Start-Process -FilePath $installer -ArgumentList @("--quiet","--accept-eulas","--prevent-reboot") -PassThru
$finished=$p.WaitForExit(480000)
if($finished){
  L "Installer wrapper exit=$($p.ExitCode)"
}else{
  L "Installer wrapper timeout after 480 sec"
  try{Stop-Process -Id $p.Id -Force}catch{}
}

$ms=$null
for($i=0;$i -lt 36;$i++){
  $ms=Get-ChildItem "C:\Program Files (x86)\National Instruments","C:\Program Files\National Instruments" -Filter Multisim.exe -Recurse -ErrorAction SilentlyContinue | Select-Object -First 1
  if($ms){break}
  Start-Sleep -Seconds 10
}

if(-not $ms){
  L "Multisim.exe not found"
  exit 11
}

L "Multisim=$($ms.FullName)"
L "Multisim SHA256=$((Get-FileHash $ms.FullName -Algorithm SHA256).Hash)"

python -m pip install --disable-pip-version-check --quiet pywinauto pyautogui pillow
if($LASTEXITCODE -ne 0){
  L "pip install failed"
  exit 12
}

$py=Join-Path $Workspace "lab7330669\lab4_native.py"
python $py "$($ms.FullName)" "$Out"
$code=$LASTEXITCODE
L "lab4_native.py exit=$code"

if(Test-Path (Join-Path $Out "Lab4_Diodes.ms14")){
  $f=Get-Item (Join-Path $Out "Lab4_Diodes.ms14")
  L "Lab4 MS14 exists size=$($f.Length) sha256=$((Get-FileHash $f.FullName -Algorithm SHA256).Hash)"
}

try{taskkill /IM Multisim.exe /T /F | Out-Null}catch{}
exit $code
