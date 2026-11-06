param([string]$Workspace=$env:GITHUB_WORKSPACE)
$ErrorActionPreference="Continue"
$ProgressPreference="SilentlyContinue"
$A=Join-Path $Workspace "gui-artifacts"
New-Item -ItemType Directory -Force -Path $A | Out-Null
$Log=Join-Path $A "python-workflow.log"
function L([string]$m){$s="[$(Get-Date -Format o)] $m";Write-Host $s;Add-Content $Log $s}

$url="https://download.ni.com/support/nipkg/products/ni-c/ni-cds-professional/14.3/online/ni-cds-professional_14.3_online.exe"
$installer=Join-Path $env:RUNNER_TEMP "ni-cds-professional_14.3_online.exe"
L "Downloading signed NI Professional 14.3 bootstrapper"
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

# The online NI bootstrapper may exit before all child package operations finish.
# Wait for package/installer processes to settle so the SPICE importer templates are present.
for($i=0;$i -lt 90;$i++){
  $busy=Get-Process -ErrorAction SilentlyContinue | Where-Object {
    $_.ProcessName -match "nipkg|NIPackageManager|ni.*install|setup|msiexec"
  }
  if(-not $busy){break}
  if(($i % 10) -eq 0){L ("Waiting for NI package operations: " + (($busy | Select-Object -ExpandProperty ProcessName -Unique) -join ","))}
  Start-Sleep -Seconds 5
}

$niRoots=@(
  "C:\Program Files (x86)\National Instruments",
  "C:\Program Files\National Instruments",
  "C:\ProgramData\National Instruments"
)
$tpls=@()
foreach($root in $niRoots){
  if(Test-Path $root){
    $tpls += Get-ChildItem $root -Filter "SPICEEWB.TPL" -Recurse -ErrorAction SilentlyContinue
  }
}
$tpls | Select-Object FullName,Length,LastWriteTime | Format-List | Out-File (Join-Path $A "spiceewb-template-search.txt")
$allTpl=@()
foreach($root in $niRoots){
  if(Test-Path $root){
    $allTpl += Get-ChildItem $root -Filter "*.TPL" -Recurse -ErrorAction SilentlyContinue
  }
}
$allTpl | Select-Object FullName,Length,LastWriteTime | Format-Table -AutoSize | Out-File (Join-Path $A "all-tpl-files.txt")

$expectedTpl=Join-Path $ms.DirectoryName "SPICEEWB.TPL"
if(-not (Test-Path $expectedTpl) -and $tpls.Count -gt 0){
  Copy-Item $tpls[0].FullName $expectedTpl -Force
  L "Copied SPICEEWB.TPL from $($tpls[0].FullName) to $expectedTpl"
}
L "Expected SPICEEWB.TPL exists=$(Test-Path $expectedTpl)"

# If the installed tree omitted the legacy SPICE import template, inspect cached
# NI CDS package payloads. NIPM keeps installed package archives under ProgramData.
if(-not (Test-Path $expectedTpl)){
  $nipkg=@(
    "C:\Program Files\National Instruments\NI Package Manager\nipkg.exe",
    "C:\Program Files (x86)\National Instruments\NI Package Manager\nipkg.exe"
  ) | Where-Object {Test-Path $_} | Select-Object -First 1
  if($nipkg){
    & $nipkg help unpack *> (Join-Path $A "nipkg-help-unpack.txt")
    & $nipkg list-installed "ni-cds*" *> (Join-Path $A "nipkg-cds-installed.txt")
    $cacheRoot="C:\ProgramData\National Instruments\NI Package Manager\Packages"
    if(Test-Path $cacheRoot){
      $pkgIndex=Get-ChildItem $cacheRoot -Filter "*.nipkg" -Recurse -File -ErrorAction SilentlyContinue |
        Where-Object {$_.Name -match "ni-cds|multisim"}
      $pkgIndex | Select-Object FullName,Length,LastWriteTime | Format-Table -AutoSize |
        Out-File (Join-Path $A "nipkg-cached-cds-files.txt")
      $unpackRoot=Join-Path $env:RUNNER_TEMP "cds-unpacked"
      New-Item -ItemType Directory -Force -Path $unpackRoot | Out-Null
      foreach($pkg in $pkgIndex){
        $dst=Join-Path $unpackRoot ([IO.Path]::GetFileNameWithoutExtension($pkg.Name))
        New-Item -ItemType Directory -Force -Path $dst | Out-Null
        try{
          & $nipkg unpack "$($pkg.FullName)" "$dst" *> $null
        }catch{}
        $hit=Get-ChildItem $dst -Filter "SPICEEWB.TPL" -Recurse -File -ErrorAction SilentlyContinue | Select-Object -First 1
        if($hit){
          Copy-Item $hit.FullName $expectedTpl -Force
          L "Recovered SPICEEWB.TPL from cached package $($pkg.Name): $($hit.FullName)"
          break
        }
      }
      if(-not (Test-Path $expectedTpl)){
        $textHits=Get-ChildItem $unpackRoot -Recurse -File -ErrorAction SilentlyContinue |
          Where-Object {$_.Length -lt 20MB} |
          Select-String -Pattern "SPICEEWB" -SimpleMatch -List -ErrorAction SilentlyContinue |
          Select-Object -First 30 Path,Line
        $textHits | Format-Table -AutoSize | Out-File (Join-Path $A "spiceewb-text-hits.txt")
      }
    }
  }
}
L "SPICEEWB.TPL after cache recovery exists=$(Test-Path $expectedTpl)"

L "Installing Python UI automation packages"
python -m pip install --disable-pip-version-check --quiet pywinauto pyautogui pillow
L "pip exit=$LASTEXITCODE"
if($LASTEXITCODE -ne 0){exit 12}

$cir=Join-Path $Workspace "gui\7330744_V6_GUI_import.cir"
$target=Join-Path $A "7330744_PhotoRelay_V6.ms14"
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
