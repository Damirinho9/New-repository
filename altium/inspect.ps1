$ErrorActionPreference="Stop"
$ProgressPreference="SilentlyContinue"
$A=Join-Path $env:GITHUB_WORKSPACE "altium-inspect"
New-Item -ItemType Directory -Force -Path $A | Out-Null
$url="https://f1.199server.site/Pro/Altium%20Designer%2026.11.1.5%20x64.rar"
$rar=Join-Path $env:RUNNER_TEMP "Altium_Designer_26.11.1.5_x64.rar"

function L([string]$m){$s="[$(Get-Date -Format o)] $m";Write-Host $s;Add-Content (Join-Path $A "inspect.log") $s}

L "Downloading archive"
& curl.exe -L --fail --retry 3 --retry-delay 5 -o $rar $url
if($LASTEXITCODE -ne 0){throw "curl failed $LASTEXITCODE"}
$fi=Get-Item $rar
L "SizeBytes=$($fi.Length)"
L "SHA256=$((Get-FileHash $rar -Algorithm SHA256).Hash)"

$seven="C:\Program Files\7-Zip\7z.exe"
if(-not (Test-Path $seven)){throw "7z not found"}
& $seven l -slt $rar | Out-File (Join-Path $A "archive-list-slt.txt") -Encoding utf8
& $seven l $rar | Out-File (Join-Path $A "archive-list.txt") -Encoding utf8

$names=& $seven l -ba $rar
$names | Out-File (Join-Path $A "archive-list-ba.txt") -Encoding utf8

$bad=$names | Select-String -Pattern "crack|medicine|keygen|patch|loader|activat|license.*fix|readme.*破解|注册机" -CaseSensitive:$false
$bad | Out-File (Join-Path $A "suspicious-names.txt") -Encoding utf8
L ("SuspiciousNameMatches=" + @($bad).Count)

# Extract only executables and text metadata for signature inspection.
$E=Join-Path $env:RUNNER_TEMP "altium-exe"
New-Item -ItemType Directory -Force -Path $E | Out-Null
& $seven x -y "-o$E" $rar "*.exe" "*.msi" "*.txt" "*.nfo" "*.url" | Out-File (Join-Path $A "extract-log.txt") -Encoding utf8

$execs=Get-ChildItem $E -Recurse -File | Where-Object {$_.Extension -in ".exe",".msi"}
$rows=@()
foreach($f in $execs){
  $sig=Get-AuthenticodeSignature $f.FullName
  $rows += [pscustomobject]@{
    RelativePath=$f.FullName.Substring($E.Length).TrimStart("\")
    Size=$f.Length
    SHA256=(Get-FileHash $f.FullName -Algorithm SHA256).Hash
    SignatureStatus=$sig.Status
    Signer=if($sig.SignerCertificate){$sig.SignerCertificate.Subject}else{""}
  }
}
$rows | Export-Csv (Join-Path $A "executables-signatures.csv") -NoTypeInformation -Encoding utf8
$rows | Format-Table -AutoSize | Out-File (Join-Path $A "executables-signatures.txt") -Encoding utf8
L ("ExecutableCount=" + $rows.Count)
L ("ValidSigned=" + @($rows | Where-Object {$_.SignatureStatus -eq "Valid"}).Count)
L ("AltiumSigned=" + @($rows | Where-Object {$_.Signer -match "Altium"}).Count)

# Save likely installer paths only.
$likely=$rows | Where-Object {$_.RelativePath -match "setup|install|altium"} | Select-Object -First 100
$likely | Export-Csv (Join-Path $A "likely-installers.csv") -NoTypeInformation -Encoding utf8

# Extract top-level text files for human inspection, capped.
Get-ChildItem $E -Recurse -File | Where-Object {$_.Extension -in ".txt",".nfo",".url"} | ForEach-Object {
  $dest=Join-Path $A ("text_" + ($_.Name -replace '[^A-Za-z0-9._-]','_'))
  try { Get-Content $_.FullName -TotalCount 300 | Set-Content $dest -Encoding utf8 } catch {}
}
