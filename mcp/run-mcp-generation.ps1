param([string]$Workspace=$env:GITHUB_WORKSPACE)
$ErrorActionPreference="Stop"
$ProgressPreference="SilentlyContinue"
$A=Join-Path $Workspace "mcp-artifacts"
New-Item -ItemType Directory -Force -Path $A | Out-Null
$Log=Join-Path $A "mcp-workflow.log"
function L([string]$m){$s="[$(Get-Date -Format o)] $m";Write-Host $s;Add-Content $Log $s}

$url="https://download.ni.com/support/nipkg/products/ni-c/ni-cds-educational/14.3/online/ni-cds-educational_14.3_online.exe"
$installer=Join-Path $env:RUNNER_TEMP "ni-cds-educational_14.3_online.exe"
L "Download signed NI Education 14.3"
Invoke-WebRequest -Uri $url -OutFile $installer -UseBasicParsing
$sig=Get-AuthenticodeSignature $installer
L "NI installer signature=$($sig.Status) signer=$($sig.SignerCertificate.Subject)"
if($sig.Status -ne "Valid"){throw "Invalid NI installer signature"}

$p=Start-Process $installer -ArgumentList @("--quiet","--accept-eulas","--prevent-reboot") -PassThru
$done=$p.WaitForExit(480000)
if($done){L "NI bootstrap exit=$($p.ExitCode)"}else{L "NI bootstrap wrapper timeout";try{Stop-Process -Id $p.Id -Force}catch{}}

$ms=$null
for($i=0;$i -lt 30;$i++){
  $ms=Get-ChildItem "C:\Program Files (x86)\National Instruments","C:\Program Files\National Instruments" -Filter Multisim.exe -Recurse -ErrorAction SilentlyContinue | Select-Object -First 1
  if($ms){break}
  Start-Sleep 10
}
if(-not $ms){throw "Multisim.exe not found"}
L "Multisim=$($ms.FullName)"

L "Install trial-click dependencies on runner Python"
python -m pip install --disable-pip-version-check --quiet pywinauto pyautogui pillow
python (Join-Path $Workspace "mcp\activate_trial.py") "$($ms.FullName)"
if($LASTEXITCODE -ne 0){throw "Trial activation failed exit=$LASTEXITCODE"}
L "Trial activation complete"

$pyInstaller=Join-Path $env:RUNNER_TEMP "python-3.12.10-x86.exe"
$pyUrl="https://www.python.org/ftp/python/3.12.10/python-3.12.10.exe"
L "Download 32-bit Python 3.12.10"
Invoke-WebRequest -Uri $pyUrl -OutFile $pyInstaller -UseBasicParsing
$py32="C:\Python312-32\python.exe"
Start-Process $pyInstaller -ArgumentList @("/quiet","InstallAllUsers=0","TargetDir=C:\Python312-32","Include_launcher=0","PrependPath=0","Include_test=0","Include_doc=0") -Wait
if(-not (Test-Path $py32)){throw "32-bit Python missing"}
$bits=& $py32 -c "import struct; print(struct.calcsize('P')*8)"
L "Python32 bitness=$bits"
if(($bits | Out-String).Trim() -ne "32"){throw "Python is not 32-bit"}

L "Clone multisim-mcp"
$src="C:\multisim-mcp-src"
if(Test-Path $src){Remove-Item $src -Recurse -Force}
git clone --depth 1 https://github.com/yxy050208/multisim-mcp.git $src
if($LASTEXITCODE -ne 0){throw "git clone failed"}

L "Install multisim-mcp into 32-bit Python"
& $py32 -m pip install --disable-pip-version-check --upgrade pip
& $py32 -m pip install --disable-pip-version-check -e "$src\mcp_server"
if($LASTEXITCODE -ne 0){throw "pip install multisim-mcp failed"}

L "Install pinned MS14 codec"
npm install --global electronics-workbench-decoder@0.2.0
if($LASTEXITCODE -ne 0){throw "npm install codec failed"}
$npmRoot=(npm root -g).Trim()
$ewd=Join-Path $npmRoot "electronics-workbench-decoder\dist\ewd.js"
$ewe=Join-Path $npmRoot "electronics-workbench-decoder\dist\ewe.js"
if(-not (Test-Path $ewd) -or -not (Test-Path $ewe)){throw "codec JS files missing"}
$node=(Get-Command node.exe).Source
L "node=$node"
L "ewd=$ewd"
L "ewe=$ewe"

$env:MULTISIM_MCP_EWD=$ewd
$env:MULTISIM_MCP_EWE=$ewe
$env:MULTISIM_MCP_WORKDIR="C:\msre_exp"
$env:MULTISIM_MCP_WORKER_PYTHON=$py32

$samples="C:\Users\Public\Documents\National Instruments\Circuit Design Suite 14.3\samples"
if(-not (Test-Path $samples)){
  L "Default samples path missing, searching"
  $cand=Get-ChildItem "C:\Users\Public\Documents" -Directory -Recurse -ErrorAction SilentlyContinue | Where-Object {$_.Name -eq "samples" -and $_.FullName -match "Circuit Design Suite 14.3"} | Select-Object -First 1
  if($cand){$samples=$cand.FullName}
}
L "samples=$samples"
if(-not (Test-Path $samples)){throw "Multisim samples not found"}

$pack="C:\MultisimMcp\component-pack"
New-Item -ItemType Directory -Force -Path (Split-Path $pack) | Out-Null
$env:PYTHONPATH="$src\mcp_server"
L "Build local template pack from installed licensed samples"
& $py32 "$src\tools\bootstrap_local_component_pack.py" --samples-root "$samples" --output "$pack" --force *> (Join-Path $A "template-pack.log")
if($LASTEXITCODE -ne 0){throw "template pack generation failed"}
$env:MULTISIM_MCP_TEMPLATE_DIR=$pack
L "Template pack built"

L "Run doctor"
& $py32 -m multisim_mcp.cli doctor --json *> (Join-Path $A "doctor.json")

$net=Join-Path $Workspace "mcp\7330744_V6_Schematic_MCP.cir"
$out=Join-Path $A "7330744_V6_PhotoRelay.ms14"
$img=Join-Path $A "7330744_V6_PhotoRelay_schematic.png"
$res=Join-Path $A "create_schematic_result.json"
L "Generate native editable MS14"
& $py32 (Join-Path $Workspace "mcp\build_ms14.py") "$net" "$out" "$img" "$res"
$buildExit=$LASTEXITCODE
L "build exit=$buildExit"

Get-ChildItem $A -Recurse | Select FullName,Length,LastWriteTime | Format-Table -AutoSize | Out-String | Add-Content $Log
if(Test-Path $out){
  L "SUCCESS MS14 size=$((Get-Item $out).Length) SHA256=$((Get-FileHash $out -Algorithm SHA256).Hash)"
}else{
  L "MS14 missing"
}
if(Test-Path $img){
  L "Schematic image size=$((Get-Item $img).Length)"
}
try{taskkill /IM Multisim.exe /T /F | Out-Null}catch{}
exit $buildExit
