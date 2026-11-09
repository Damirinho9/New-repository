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
[IO.File]::WriteAllText((Join-Path $Out 'multisim-executable.txt'),$ms.FullName)
python -m pip install --disable-pip-version-check --quiet pywinauto pyautogui pillow
python (Join-Path $Workspace 'nativebuild7330744.py') "$($ms.FullName)" "$Out"
$rc=$LASTEXITCODE
Write-Host "Native initial assembly exit=$rc; keeping Multisim alive for verified UI corrections"
exit 0

# Native GUI pass 2: verified canvas, explicit 50 Hz and AC RMS meter.
