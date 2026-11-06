param([string]$Workspace=$env:GITHUB_WORKSPACE)
$ErrorActionPreference="Stop";$ProgressPreference="SilentlyContinue"
$A=Join-Path $Workspace "final-gui-artifacts";New-Item -ItemType Directory -Force -Path $A|Out-Null
function L([string]$m){$s="[$(Get-Date -Format o)] $m";Write-Host $s;Add-Content (Join-Path $A "workflow.log") $s}

$src=Join-Path $Workspace "native-input"
New-Item -ItemType Directory -Force -Path $src|Out-Null
L "Download native MS14 artifact from verified build"
gh run download 42182317096 --repo Damirinho9/New-repository -n multisim-7330744-mcp-native-ms14 -D "$src"
if($LASTEXITCODE -ne 0){throw "gh artifact download failed"}
$ms14=Get-ChildItem $src -Filter "7330744_V6_PhotoRelay.ms14" -Recurse|Select-Object -First 1
if(-not $ms14){throw "MS14 missing in downloaded artifact"}
Copy-Item $ms14.FullName (Join-Path $A "7330744_V6_PhotoRelay.ms14") -Force
$td=Get-ChildItem $src -Filter "*.topology-diff.json" -Recurse|Select-Object -First 1
if($td){Copy-Item $td.FullName $A -Force}
L "MS14 size=$($ms14.Length) SHA256=$((Get-FileHash $ms14.FullName -Algorithm SHA256).Hash)"

$url="https://download.ni.com/support/nipkg/products/ni-c/ni-cds-educational/14.3/online/ni-cds-educational_14.3_online.exe"
$installer=Join-Path $env:RUNNER_TEMP "ni-cds-educational_14.3_online.exe"
Invoke-WebRequest $url -OutFile $installer -UseBasicParsing
$sig=Get-AuthenticodeSignature $installer
L "installer signature=$($sig.Status)"
if($sig.Status -ne "Valid"){throw "invalid NI signature"}
$p=Start-Process $installer -ArgumentList @("--quiet","--accept-eulas","--prevent-reboot") -PassThru
$done=$p.WaitForExit(480000)
if($done){L "installer exit=$($p.ExitCode)"}else{try{Stop-Process -Id $p.Id -Force}catch{};L "installer wrapper timeout"}

$ms=$null
for($i=0;$i -lt 30;$i++){
 $ms=Get-ChildItem "C:\Program Files (x86)\National Instruments","C:\Program Files\National Instruments" -Filter Multisim.exe -Recurse -ErrorAction SilentlyContinue|Select-Object -First 1
 if($ms){break};Start-Sleep 10
}
if(-not $ms){throw "Multisim not found"}
python -m pip install --disable-pip-version-check --quiet pywinauto pyautogui pillow
python (Join-Path $Workspace "mcp\activate_trial.py") "$($ms.FullName)"
if($LASTEXITCODE -ne 0){throw "trial activation failed"}
L "Open verified MS14 directly in Multisim"
python (Join-Path $Workspace "mcp\open_final_ms14.py") "$($ms.FullName)" "$($ms14.FullName)" "$A"
L "GUI script exit=$LASTEXITCODE"
try{taskkill /IM Multisim.exe /T /F|Out-Null}catch{}
