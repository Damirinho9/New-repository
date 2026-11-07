param([string]$Workspace=$env:GITHUB_WORKSPACE)
$ErrorActionPreference="Continue"
$ProgressPreference="SilentlyContinue"

$Root=Join-Path $Workspace "final7330669"
$Out=Join-Path $Workspace "final7330669-artifacts"
New-Item -ItemType Directory -Force -Path $Out | Out-Null
$Log=Join-Path $Out "finalize-all.log"

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
}
else{L "Installer wrapper exit=$($p.ExitCode)"}

$ms=$null
for($i=0;$i -lt 36;$i++){
  $ms=Get-ChildItem "C:\Program Files (x86)\National Instruments","C:\Program Files\National Instruments" -Filter Multisim.exe -Recurse -ErrorAction SilentlyContinue | Select-Object -First 1
  if($ms){break}
  Start-Sleep -Seconds 10
}
if(-not $ms){L "Multisim.exe not found";exit 11}
L "Multisim=$($ms.FullName)"
python -m pip install --disable-pip-version-check --quiet pywinauto pyautogui pillow

$results=@()
foreach($lab in @("lab2_final.py","lab3_final.py","lab4_final.py")){
  $name=[IO.Path]::GetFileNameWithoutExtension($lab)
  $labOut=Join-Path $Out $name
  New-Item -ItemType Directory -Force -Path $labOut | Out-Null
  L "START $lab"
  python (Join-Path $Root $lab) "$($ms.FullName)" "$labOut"
  $code=$LASTEXITCODE
  L "END $lab exit=$code"
  $results += [pscustomobject]@{Lab=$lab;Exit=$code}
  try{taskkill /IM Multisim.exe /T /F | Out-Null}catch{}
  Start-Sleep -Seconds 2
}

$results | Format-Table -AutoSize | Out-File (Join-Path $Out "results.txt")
$bad=$results | Where-Object {$_.Exit -ne 0}
if($bad){
  L ("Failures: "+(($bad | ForEach-Object {"$($_.Lab)=$($_.Exit)"}) -join ", "))
  exit 20
}
L "ALL_THREE_NATIVE_LABS_OK"
exit 0
