$ErrorActionPreference="Stop"
$ProgressPreference="SilentlyContinue"
$A=Join-Path $env:GITHUB_WORKSPACE "altium-verify"
New-Item -ItemType Directory -Force -Path $A | Out-Null
$url="https://f1.199server.site/Pro/Altium%20Designer%2026.11.1.5%20x64.rar"
$rar=Join-Path $env:RUNNER_TEMP "Altium_Designer_26.11.1.5_x64.rar"
$seven="C:\Program Files\7-Zip\7z.exe"
function L([string]$m){$s="[$(Get-Date -Format o)] $m";Write-Host $s;Add-Content (Join-Path $A "verify.log") $s}
L "Downloading"
& curl.exe -L --fail --retry 3 --retry-delay 5 -o $rar $url
if($LASTEXITCODE -ne 0){throw "curl failed"}
L "ArchiveSize=$((Get-Item $rar).Length)"
L "ArchiveSHA256=$((Get-FileHash $rar -Algorithm SHA256).Hash)"
$E=Join-Path $env:RUNNER_TEMP "altium-offline"
New-Item -ItemType Directory -Force -Path $E | Out-Null
& $seven x -y "-o$E" $rar "Altium Designer 26.11.1.5 x64\Installer.Exe" "Altium Designer 26.11.1.5 x64\Metadata\*" "Altium Designer 26.11.1.5 x64\autorun.inf" "Altium Designer 26.11.1.5 x64\Extensions.ini" | Out-File (Join-Path $A "extract.log") -Encoding utf8
$installer=Get-ChildItem $E -Filter "Installer.Exe" -Recurse | Select-Object -First 1
if(-not $installer){throw "Installer.Exe missing"}
L "InstallerPath=$($installer.FullName)"
L "InstallerSize=$($installer.Length)"
L "InstallerSHA256=$((Get-FileHash $installer.FullName -Algorithm SHA256).Hash)"
$sig=Get-AuthenticodeSignature $installer.FullName
L "SignatureStatus=$($sig.Status)"
if($sig.SignerCertificate){
  L "Signer=$($sig.SignerCertificate.Subject)"
  L "Issuer=$($sig.SignerCertificate.Issuer)"
}
$vi=$installer.VersionInfo
L "FileVersion=$($vi.FileVersion)"
L "ProductVersion=$($vi.ProductVersion)"
L "CompanyName=$($vi.CompanyName)"
L "ProductName=$($vi.ProductName)"
Get-ChildItem (Join-Path (Split-Path $installer.FullName) "Metadata") -File | ForEach-Object {
  Copy-Item $_.FullName $A -Force
}
Copy-Item $installer.FullName (Join-Path $A "Installer.Exe") -Force
