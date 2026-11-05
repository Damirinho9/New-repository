param(
  [string]$Workspace = $env:GITHUB_WORKSPACE
)

$ErrorActionPreference = "Continue"
$Artifacts = Join-Path $Workspace "artifacts"
New-Item -ItemType Directory -Force -Path $Artifacts | Out-Null
$Diag = Join-Path $Artifacts "multisim-com.log"

function Log([string]$Message) {
  $line = "[$(Get-Date -Format o)] $Message"
  Write-Host $line
  Add-Content -Path $Diag -Value $line
}

Log "COM worker starting."
Log "Is64BitProcess=$([Environment]::Is64BitProcess)"
Log "PowerShell=$($PSVersionTable.PSVersion)"

$app = $null
$circuit = $null
try {
  Log "Creating COM object MultisimInterface.MultisimApp"
  $app = New-Object -ComObject "MultisimInterface.MultisimApp"
  ($app | Get-Member | Out-String) | Set-Content (Join-Path $Artifacts "multisim-app-members.txt")
  Log "COM object created."

  try {
    $connectResult = $app.Connect()
    Log "Connect() returned: $connectResult"
  } catch {
    Log "Connect() exception: $($_.Exception.Message)"
  }

  try {
    $circuit = $app.NewFile()
    Log "NewFile() returned a circuit object."
    ($circuit | Get-Member | Out-String) | Set-Content (Join-Path $Artifacts "multisim-circuit-members.txt")
  } catch {
    Log "NewFile() exception: $($_.Exception.Message)"
  }

  $netlist = Join-Path $Workspace "multisim\7330744_V6_PhotoRelay_3state_Multisim.cir"
  $commandFile = Join-Path $Artifacts "multisim-commands.txt"
  $simLog = Join-Path $Artifacts "multisim-simulation.log"
  $rawFile = Join-Path $Artifacts "multisim-results.raw"

  $n = $netlist.Replace("\","/")
  $r = $rawFile.Replace("\","/")
  $dq = [char]34
  @(
    ("source " + $dq + $n + $dq),
    "tran 0.0001 12",
    ("write " + $dq + $r + $dq + " v(sens) v(gdrv) v(l) v(sw)")
  ) | Set-Content -Path $commandFile -Encoding ASCII

  Log "Command file written: $commandFile"
  Get-Content $commandFile | ForEach-Object { Log "CMD: $_" }

  $started = $false
  if ($circuit) {
    try {
      Log "Trying circuit.DoCommandLine(commandFile, logFile)"
      $circuit.DoCommandLine($commandFile, $simLog)
      $started = $true
      Log "DoCommandLine accepted by MultisimCircuit."
    } catch {
      Log "Circuit DoCommandLine exception: $($_.Exception.Message)"
    }
  }

  if (-not $started -and $app) {
    try {
      Log "Trying app.DoCommandLine(commandFile, logFile)"
      $app.DoCommandLine($commandFile, $simLog)
      $started = $true
      Log "DoCommandLine accepted by MultisimApp."
    } catch {
      Log "App DoCommandLine exception: $($_.Exception.Message)"
    }
  }

  if ($started) {
    Log "Waiting for simulation output."
    $stableCount = 0
    $lastSize = -1
    for ($i=0; $i -lt 60; $i++) {
      Start-Sleep -Seconds 5
      if (Test-Path $rawFile) {
        $size = (Get-Item $rawFile).Length
        Log "RAW exists, size=$size"
        if ($size -eq $lastSize -and $size -gt 0) { $stableCount++ } else { $stableCount = 0 }
        $lastSize = $size
        if ($stableCount -ge 2) { break }
      } else {
        Log "RAW not present yet."
      }
    }
  } else {
    Log "Simulation was not started."
  }

  if (Test-Path $simLog) {
    Log "Simulation log exists, size=$((Get-Item $simLog).Length)"
  }
  if (Test-Path $rawFile) {
    Log "Simulation RAW exists, size=$((Get-Item $rawFile).Length)"
  }

  try {
    if ($circuit) { $circuit.StopSimulation() }
  } catch {}

  try {
    if ($app) { $app.Disconnect() }
    Log "Disconnected from Multisim."
  } catch {
    Log "Disconnect exception: $($_.Exception.Message)"
  }

} catch {
  Log "FATAL COM ERROR: $($_.Exception.ToString())"
  exit 2
}

if (Test-Path (Join-Path $Artifacts "multisim-results.raw")) {
  Log "SUCCESS: Multisim generated a RAW result file."
  exit 0
} else {
  Log "NO RAW RESULT FILE."
  exit 3
}
