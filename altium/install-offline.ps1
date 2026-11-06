$ErrorActionPreference="Continue"
$ProgressPreference="SilentlyContinue"
$A=Join-Path $env:GITHUB_WORKSPACE "altium-install-artifacts"
New-Item -ItemType Directory -Force -Path $A | Out-Null
function L([string]$m){$s="[$(Get-Date -Format o)] $m";Write-Host $s;Add-Content (Join-Path $A "install.log") $s}

$url="https://f1.199server.site/Pro/Altium%20Designer%2026.11.1.5%20x64.rar"
$rar=Join-Path $env:RUNNER_TEMP "Altium_Designer_26.11.1.5_x64.rar"
$seven="C:\Program Files\7-Zip\7z.exe"
$media=Join-Path $env:RUNNER_TEMP "altium-media"

L "Download offline media"
& curl.exe -L --fail --retry 3 --retry-delay 5 -o $rar $url
if($LASTEXITCODE -ne 0){L "curl failed";exit 10}
L "RAR size=$((Get-Item $rar).Length)"
L "RAR SHA256=$((Get-FileHash $rar -Algorithm SHA256).Hash)"

L "Extract offline media"
& $seven x -y "-o$media" $rar *> (Join-Path $A "7z-extract.log")
if($LASTEXITCODE -ne 0){L "7z failed";exit 11}

$root=Get-ChildItem $media -Directory | Select-Object -First 1
$installer=Join-Path $root.FullName "Installer.Exe"
if(-not (Test-Path $installer)){L "Installer missing";exit 12}
$sig=Get-AuthenticodeSignature $installer
L "Installer signature=$($sig.Status)"
if($sig.SignerCertificate){L "Installer signer=$($sig.SignerCertificate.Subject)"}
L "Installer SHA256=$((Get-FileHash $installer -Algorithm SHA256).Hash)"
$vi=(Get-Item $installer).VersionInfo
L "Installer file version=$($vi.FileVersion)"
L "Installer product=$($vi.ProductName)"
if($sig.Status -ne "Valid"){L "Refuse unsigned installer";exit 13}

$programs="C:\Program Files\Altium\AD26"
$documents="C:\Users\Public\Documents\Altium\AD26"
L "Start offline silent install"
$args=@(
  "-Programs:$programs",
  "-Documents:$documents",
  "-UI:None",
  "-AutoInstall",
  "-InstallAll"
)
$p=Start-Process -FilePath $installer -ArgumentList $args -Wait -PassThru -RedirectStandardOutput (Join-Path $A "installer-stdout.log") -RedirectStandardError (Join-Path $A "installer-stderr.log")
L "Installer exit=$($p.ExitCode)"

L "Inventory installed Altium executables"
$roots=@("C:\Program Files\Altium","C:\Program Files (x86)\Altium")
$execs=@()
foreach($r in $roots){
  if(Test-Path $r){
    $execs += Get-ChildItem $r -Recurse -File -ErrorAction SilentlyContinue | Where-Object {$_.Name -match '^(X2|AltiumDesigner|DXP).*\.exe$|Altium.*\.exe$'}
  }
}
$execs | Select FullName,Length,LastWriteTime,@{N="FileVersion";E={$_.VersionInfo.FileVersion}} | Format-List | Out-File (Join-Path $A "installed-executables.txt")
L "Installed candidate executables=$($execs.Count)"

$main=$execs | Where-Object {$_.Name -ieq "X2.EXE"} | Select-Object -First 1
if(-not $main){$main=$execs | Where-Object {$_.Name -match "AltiumDesigner"} | Select-Object -First 1}
if($main){
  L "Main EXE=$($main.FullName)"
  $msig=Get-AuthenticodeSignature $main.FullName
  L "Main signature=$($msig.Status)"
  if($msig.SignerCertificate){L "Main signer=$($msig.SignerCertificate.Subject)"}
  L "Main SHA256=$((Get-FileHash $main.FullName -Algorithm SHA256).Hash)"

  # Best-effort GUI launch and screenshot, no credential entry.
  try{
    Add-Type -AssemblyName System.Windows.Forms
    Add-Type -AssemblyName System.Drawing
    $proc=Start-Process $main.FullName -PassThru
    L "GUI PID=$($proc.Id)"
    Start-Sleep -Seconds 20
    $b=[System.Windows.Forms.Screen]::PrimaryScreen.Bounds
    $bmp=New-Object System.Drawing.Bitmap $b.Width,$b.Height
    $g=[System.Drawing.Graphics]::FromImage($bmp)
    $g.CopyFromScreen($b.Location,[System.Drawing.Point]::Empty,$b.Size)
    $shot=Join-Path $A "altium-first-launch.png"
    $bmp.Save($shot,[System.Drawing.Imaging.ImageFormat]::Png)
    $g.Dispose();$bmp.Dispose()
    L "Screenshot saved"
    Get-Process | Where-Object {$_.ProcessName -match "Altium|X2|DXP"} | Select ProcessName,Id,MainWindowTitle,Path | Format-List | Out-File (Join-Path $A "altium-processes.txt")
  }catch{L "GUI launch/screenshot error=$($_.Exception.Message)"}
}else{
  L "Main Altium executable not found"
  exit 20
}
exit 0
