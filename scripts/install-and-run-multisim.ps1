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

Write-Log "Windows runner: $([Environment]::OSVersion.VersionString)"
Write-Log "PowerShell: $($PSVersionTable.PSVersion)"
Write-Log "Workspace: $Workspace"

$installerUrl = "https://download.ni.com/support/nipkg/products/ni-c/ni-cds-professional/14.3/online/ni-cds-professional_14.3_online.exe"
$installer = Join-Path $env:RUNNER_TEMP "ni-cds-professional_14.3_online.exe"

try {
  Write-Log "Downloading official NI Multisim 14.3 Professional online installer..."
  Invoke-WebRequest -Uri $installerUrl -OutFile $installer -UseBasicParsing
  $hash = Get-FileHash $installer -Algorithm SHA256
  Write-Log "Installer downloaded: $installer"
  Write-Log "Installer SHA256: $($hash.Hash)"
} catch {
  Write-Log "DOWNLOAD ERROR: $($_.Exception.Message)"
  throw
}

try {
  Write-Log "Starting silent NI installation."
  $stdout = Join-Path $Artifacts "installer-stdout.log"
  $stderr = Join-Path $Artifacts "installer-stderr.log"
  $proc = Start-Process -FilePath $installer -ArgumentList @("--quiet","--accept-eulas","--prevent-reboot") -Wait -PassThru -RedirectStandardOutput $stdout -RedirectStandardError $stderr
  Write-Log "Installer exit code: $($proc.ExitCode)"
} catch {
  Write-Log "INSTALL ERROR: $($_.Exception.Message)"
}

$nipkgCandidates = @(
  "C:\Program Files\National Instruments\NI Package Manager\nipkg.exe",
  "C:\Program Files (x86)\National Instruments\NI Package Manager\nipkg.exe"
)
$nipkg = $nipkgCandidates | Where-Object { Test-Path $_ } | Select-Object -First 1
if ($nipkg) {
  Write-Log "NI Package Manager found: $nipkg"
  try { & $nipkg list *> (Join-Path $Artifacts "nipkg-list.txt") } catch {}
  try { & $nipkg help install *> (Join-Path $Artifacts "nipkg-help-install.txt") } catch {}
} else {
  Write-Log "NI Package Manager CLI not found."
}

$roots = @(
  "C:\Program Files (x86)\National Instruments",
  "C:\Program Files\National Instruments"
)
$multisim = @()
foreach ($root in $roots) {
  if (Test-Path $root) {
    $multisim += Get-ChildItem $root -Filter "Multisim.exe" -Recurse -ErrorAction SilentlyContinue
  }
}
$multisim | Select-Object FullName,Length,LastWriteTime | Format-List | Out-File (Join-Path $Artifacts "multisim-files.txt")
Write-Log "Multisim.exe candidates found: $($multisim.Count)"

$regOut = Join-Path $Artifacts "com-registration.txt"
"=== HKCR ProgID ===" | Set-Content $regOut
reg query "HKCR\MultisimInterface.MultisimApp" /s >> $regOut 2>&1
"=== CLSID known from Multisim COM interface ===" | Add-Content $regOut
reg query "HKCR\CLSID\{D9CBB7A1-6AD6-438B-AD1B-42FB2DB00CAE}" /s >> $regOut 2>&1

$ps32 = "$env:WINDIR\SysWOW64\WindowsPowerShell\v1.0\powershell.exe"
$comScript = Join-Path $Workspace "scripts\run-multisim-com.ps1"
if (Test-Path $ps32) {
  Write-Log "Launching 32-bit PowerShell COM test."
  & $ps32 -NoProfile -ExecutionPolicy Bypass -File $comScript -Workspace $Workspace
  Write-Log "32-bit COM test exit code: $LASTEXITCODE"
} else {
  Write-Log "32-bit PowerShell not found at $ps32"
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
  $g.Dispose(); $bmp.Dispose()
  Write-Log "Desktop screenshot saved: $shot"
} catch {
  Write-Log "SCREENSHOT ERROR: $($_.Exception.Message)"
}

Write-Log "Workflow diagnostic stage complete."
