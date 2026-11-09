$ErrorActionPreference="Stop"
$ProgressPreference="SilentlyContinue"
$A=Join-Path $env:GITHUB_WORKSPACE "altium-stage11-artifacts"
New-Item -ItemType Directory -Force -Path $A | Out-Null
function L([string]$m){$s="[$(Get-Date -Format o)] $m";Write-Host $s;Add-Content (Join-Path $A "setup.log") $s}
function AltiumSignature([string]$p){
 $sig=Get-AuthenticodeSignature $p
 L "Signature $p : $($sig.Status) : $($sig.SignerCertificate.Subject)"
 if($sig.Status -ne "Valid" -or $sig.SignerCertificate.Subject -notmatch 'Altium'){throw "Refusing non-valid or non-Altium-signed executable: $p"}
}
# Existing signed offline installer basis. No crack, patch, keygen, loader or license modification is executed.
# The official downloads endpoint requires an authenticated Altium Account for the offline package.
$url="https://f1.199server.site/Pro/Altium%20Designer%2026.11.1.5%20x64.rar"
$rar=Join-Path $env:RUNNER_TEMP "Altium_Designer_26.11.1.5_x64.rar"
$media=Join-Path $env:RUNNER_TEMP "altium-media"
& curl.exe -L --fail --max-time 240 -o $rar $url
if($LASTEXITCODE -ne 0){throw "Offline media download failed"}
L "Archive SHA256=$((Get-FileHash $rar -Algorithm SHA256).Hash)"
& "C:\Program Files\7-Zip\7z.exe" x -y "-o$media" $rar *> (Join-Path $A "extract.log")
if($LASTEXITCODE -ne 0){throw "Extract failed"}
$installer=Get-ChildItem $media -Recurse -Filter Installer.exe | Select-Object -First 1
if(-not $installer){throw "Installer absent"}
AltiumSignature $installer.FullName
$p=Start-Process $installer.FullName -ArgumentList @("-Programs:C:\AD26","-Documents:C:\AD26Docs","-UI:None","-AutoInstall","-InstallAll") -PassThru
if(-not $p.WaitForExit(480000)){Stop-Process $p.Id -Force;throw "Installation exceeded 8 minute cap"}
L "Installer exit=$($p.ExitCode)"
$exe="C:\AD26\X2.EXE"
if(-not (Test-Path $exe)){throw "X2.EXE not installed"}
AltiumSignature $exe
L "X2 SHA256=$((Get-FileHash $exe -Algorithm SHA256).Hash)"
$InputDir=Join-Path $env:GITHUB_WORKSPACE "native-input"
New-Item -ItemType Directory -Force $InputDir | Out-Null
$runs=gh run list --repo Damirinho9/New-repository --branch altium-7330744-stage11-fix --status success --limit 3 --json databaseId | ConvertFrom-Json
if(-not $runs -or -not $runs[0].databaseId){throw "No successful Stage11 build artifact available"}
$run=$runs[0].databaseId
L "Input Stage11 run=$run"
gh run download $run --repo Damirinho9/New-repository -D $InputDir
if($LASTEXITCODE -ne 0){throw "Cannot download corrected project"}
python -m pip install --disable-pip-version-check --quiet pywinauto pyautogui pillow
if($LASTEXITCODE -ne 0){throw "GUI dependencies failed"}
python .\altium_stage11\probe_gui.py $exe $InputDir $A
L "GUI exit=$LASTEXITCODE"
Get-Process | Where-Object {$_.ProcessName -match 'Altium|X2|DXP'} | Select ProcessName,Id,MainWindowTitle | ConvertTo-Json | Out-File (Join-Path $A "processes.json")
try{taskkill /IM X2.EXE /T /F | Out-Null}catch{}
