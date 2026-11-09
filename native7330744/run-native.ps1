param([string]$Workspace=$env:GITHUB_WORKSPACE)
$ErrorActionPreference='Stop';$ProgressPreference='SilentlyContinue'
$Out=Join-Path $Workspace 'native7330744-artifacts'
New-Item -ItemType Directory -Force $Out|Out-Null
$installer=Join-Path $env:RUNNER_TEMP 'ni-cds-educational_14.3_online.exe'
Invoke-WebRequest 'https://download.ni.com/support/nipkg/products/ni-c/ni-cds-educational/14.3/online/ni-cds-educational_14.3_online.exe' -OutFile $installer -UseBasicParsing
$sig=Get-AuthenticodeSignature $installer
if($sig.Status -ne 'Valid'){throw 'Invalid official NI installer signature'}
$p=Start-Process $installer -ArgumentList @('--quiet','--accept-eulas','--prevent-reboot') -PassThru
if(-not $p.WaitForExit(480000)){try{Stop-Process -Id $p.Id -Force}catch{}}
$ms=Get-ChildItem 'C:\Program Files (x86)\National Instruments','C:\Program Files\National Instruments' -Filter Multisim.exe -Recurse -ErrorAction SilentlyContinue|Select-Object -First 1
if(-not $ms){throw 'Multisim executable absent after installation'}
python -m pip install --disable-pip-version-check --quiet pywinauto pyautogui pillow
python (Join-Path $Workspace 'native7330744\probe.py') "$($ms.FullName)" "$Out"
$rc=$LASTEXITCODE
try{taskkill /IM Multisim.exe /T /F|Out-Null}catch{}
exit $rc
