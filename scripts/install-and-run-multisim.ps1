param(
  [string]$Workspace = $env:GITHUB_WORKSPACE
)

$ErrorActionPreference = "Continue"
$ProgressPreference = "SilentlyContinue"
$Artifacts = Join-Path $Workspace "artifacts"
New-Item -ItemType Directory -Force -Path $Artifacts | Out-Null

function Write-Log([string]$Message) {
  $line = "[$(Get-Date -Format o)] $Message"
  Write-Host $line
  Add-Content -Path (Join-Path $Artifacts "runner.log") -Value $line
}

function Start-WatchedProcess {
  param(
    [string]$FilePath,
    [string[]]$Arguments,
    [int]$TimeoutSeconds,
    [string]$Label
  )

  Write-Log "Starting $Label"
  Write-Log "Executable: $FilePath"
  Write-Log "Arguments: $($Arguments -join ' ')"

  try {
    $p = Start-Process -FilePath $FilePath -ArgumentList $Arguments -PassThru
    Write-Log "$Label PID=$($p.Id)"
    $finished = $p.WaitForExit($TimeoutSeconds * 1000)

    if ($finished) {
      Write-Log "$Label exited with code $($p.ExitCode)"
      return $p.ExitCode
    }

    Write-Log "$Label exceeded timeout of $TimeoutSeconds seconds."
    try {
      Stop-Process -Id $p.Id -Force -ErrorAction SilentlyContinue
      Write-Log "$Label wrapper process was terminated."
    } catch {}
    return 99998
  } catch {
    Write-Log "$Label start error: $($_.Exception.Message)"
    return 99999
  }
}

function Find-Multisim {
  $roots = @(
    "C:\Program Files (x86)\National Instruments",
    "C:\Program Files\National Instruments"
  )
  $found = @()
  foreach ($root in $roots) {
    if (Test-Path $root) {
      $found += Get-ChildItem $root -Filter "Multisim.exe" -Recurse -ErrorAction SilentlyContinue
    }
  }
  return $found
}

Write-Log "Windows runner: $([Environment]::OSVersion.VersionString)"
Write-Log "PowerShell: $($PSVersionTable.PSVersion)"
Write-Log "Workspace: $Workspace"

$installerUrl = "https://download.ni.com/support/nipkg/products/ni-c/ni-cds-professional/14.3/online/ni-cds-professional_14.3_online.exe"
$installer = Join-Path $env:RUNNER_TEMP "ni-cds-professional_14.3_online.exe"

try {
  Write-Log "Downloading official NI Multisim 14.3 Professional online installer."
  Invoke-WebRequest -Uri $installerUrl -OutFile $installer -UseBasicParsing
  $hash = Get-FileHash $installer -Algorithm SHA256
  Write-Log "Installer SHA256: $($hash.Hash)"
} catch {
  Write-Log "DOWNLOAD ERROR: $($_.Exception.Message)"
  throw
}

# The bootstrapper contains:
# <downloadItem id="ni-cds-professional_14.3"
# uri="nipkg://store/1/install-item/ni-cds-professional_14.3"/>
# Do not use Start-Process -Wait here: NI installers are known to leave
# descendant processes alive and cause PowerShell to wait indefinitely.
$bootstrapCode = Start-WatchedProcess -FilePath $installer -Arguments @(
  "--quiet",
  "--accept-eulas",
  "--prevent-reboot"
) -TimeoutSeconds 480 -Label "NI online bootstrapper"

Write-Log "Bootstrapper stage returned $bootstrapCode"

$nipkgCandidates = @(
  "C:\Program Files\National Instruments\NI Package Manager\nipkg.exe",
  "C:\Program Files (x86)\National Instruments\NI Package Manager\nipkg.exe"
)
$nipmCandidates = @(
  "C:\Program Files\National Instruments\NI Package Manager\NIPackageManager.exe",
  "C:\Program Files (x86)\National Instruments\NI Package Manager\NIPackageManager.exe"
)

# Give the bootstrapper/child process time to finish installing NIPM.
$nipkg = $null
$nipm = $null
for ($i=0; $i -lt 24; $i++) {
  $nipkg = $nipkgCandidates | Where-Object { Test-Path $_ } | Select-Object -First 1
  $nipm = $nipmCandidates | Where-Object { Test-Path $_ } | Select-Object -First 1
  if ($nipkg -or $nipm) { break }
  Write-Log "NI Package Manager not found yet; polling."
  Start-Sleep -Seconds 15
}

if ($nipkg) {
  Write-Log "nipkg found: $nipkg"
  try { & $nipkg list *> (Join-Path $Artifacts "nipkg-list-before.txt") } catch {}
}
if ($nipm) {
  Write-Log "NIPackageManager found: $nipm"
}

$multisim = Find-Multisim
Write-Log "Multisim.exe after bootstrapper: $($multisim.Count)"

# If the bootstrapper did not finish the product install, invoke the exact
# install-item URI embedded in the official NI executable.
if ($multisim.Count -eq 0 -and $nipm) {
  $uri = "nipkg://store/1/install-item/ni-cds-professional_14.3"
  $uriCode = Start-WatchedProcess -FilePath $nipm -Arguments @(
    "--uri=$uri",
    "--quiet",
    "--accept-eulas",
    "--prevent-reboot"
  ) -TimeoutSeconds 900 -Label "NI Package Manager direct Multisim install"
  Write-Log "Direct URI stage returned $uriCode"
}

# Poll installation state rather than waiting forever on an installer process tree.
for ($i=0; $i -lt 40; $i++) {
  $multisim = Find-Multisim
  if ($multisim.Count -gt 0) { break }

  $niProcs = Get-Process -ErrorAction SilentlyContinue |
    Where-Object { $_.ProcessName -match "NI|Package|Install|Multisim" } |
    Select-Object ProcessName,Id,CPU,StartTime
  if ($niProcs) {
    ($niProcs | Format-Table -AutoSize | Out-String) | Add-Content (Join-Path $Artifacts "ni-processes.log")
  }

  Write-Log "Multisim.exe not found yet; polling install state ($i/40)."
  Start-Sleep -Seconds 15
}

if ($nipkg) {
  try { & $nipkg list *> (Join-Path $Artifacts "nipkg-list-after.txt") } catch {}
}

$multisim = Find-Multisim
$multisim | Select-Object FullName,Length,LastWriteTime |
  Format-List | Out-File (Join-Path $Artifacts "multisim-files.txt")
Write-Log "Final Multisim.exe candidates found: $($multisim.Count)"

# Export useful NI install logs.
$logRoots = @(
  "$env:LOCALAPPDATA\National Instruments",
  "$env:PROGRAMDATA\National Instruments",
  "$env:TEMP"
)
foreach ($root in $logRoots) {
  if (Test-Path $root) {
    Get-ChildItem $root -File -Recurse -ErrorAction SilentlyContinue |
      Where-Object {
        $_.Name -match "nipkg|package|install" -and
        $_.LastWriteTime -gt (Get-Date).AddHours(-2) -and
        $_.Length -lt 20MB
      } |
      Select-Object FullName,Length,LastWriteTime |
      Format-Table -AutoSize |
      Out-File -Append (Join-Path $Artifacts "ni-log-file-index.txt")
  }
}

$regOut = Join-Path $Artifacts "com-registration.txt"
"=== HKCR ProgID ===" | Set-Content $regOut
reg query "HKCR\MultisimInterface.MultisimApp" /s >> $regOut 2>&1
"=== CLSID ===" | Add-Content $regOut
reg query "HKCR\CLSID\{D9CBB7A1-6AD6-438B-AD1B-42FB2DB00CAE}" /s >> $regOut 2>&1

$ps32 = "$env:WINDIR\SysWOW64\WindowsPowerShell\v1.0\powershell.exe"
$comScript = Join-Path $Workspace "scripts\run-multisim-com.ps1"
if ($multisim.Count -gt 0 -and (Test-Path $ps32)) {
  Write-Log "Launching 32-bit PowerShell COM test."
  & $ps32 -NoProfile -ExecutionPolicy Bypass -File $comScript -Workspace $Workspace
  Write-Log "32-bit COM test exit code: $LASTEXITCODE"
} else {
  Write-Log "Skipping COM simulation because Multisim.exe or 32-bit PowerShell is missing."
}

try {
  Add-Type -AssemblyName System.Windows.Forms
  Add-Type -AssemblyName System.Drawing
  $bounds = [System.Windows.Forms.Screen]::PrimaryScreen.Bounds
  $bmp = New-Object System.Drawing.Bitmap $bounds.Width, $bounds.Height
  $g = [System.Drawing.Graphics]::FromImage($bmp)
  $g.CopyFromScreen($bounds.Location, [System.Drawing.Point]::Empty, $bounds.Size)
  $shot = Join-Path $Artifacts "runner-desktop.png"
  $bmp.Save($shot, [System.Drawing.Imaging.ImageFormat]::Png)
  $g.Dispose()
  $bmp.Dispose()
  Write-Log "Desktop screenshot saved: $shot"
} catch {
  Write-Log "SCREENSHOT ERROR: $($_.Exception.Message)"
}

Write-Log "Workflow diagnostic stage complete."
