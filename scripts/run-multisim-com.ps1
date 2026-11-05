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

function Capture-Desktop([string]$Path) {
  try {
    Add-Type -AssemblyName System.Windows.Forms
    Add-Type -AssemblyName System.Drawing
    $bounds = [System.Windows.Forms.Screen]::PrimaryScreen.Bounds
    $bmp = New-Object System.Drawing.Bitmap $bounds.Width, $bounds.Height
    $g = [System.Drawing.Graphics]::FromImage($bmp)
    $g.CopyFromScreen($bounds.Location, [System.Drawing.Point]::Empty, $bounds.Size)
    $bmp.Save($Path, [System.Drawing.Imaging.ImageFormat]::Png)
    $g.Dispose()
    $bmp.Dispose()
    Log "Screenshot saved: $Path"
  } catch {
    Log "Screenshot error: $($_.Exception.Message)"
  }
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
    $app.Connect()
    Log "Connect() completed. IsConnected=$($app.IsConnected)"
    Log "VersionInfo=$($app.VersionInfo)"
    Log "MultisimPath=$($app.Path)"
  } catch {
    Log "Connect() exception: $($_.Exception.Message)"
  }

  try {
    $circuit = $app.NewFile()
    Log "NewFile() returned a circuit object."
    ($circuit | Get-Member | Out-String) | Set-Content (Join-Path $Artifacts "multisim-circuit-members.txt")
    Log "Initial SimulationState=$($circuit.SimulationState)"
  } catch {
    Log "NewFile() exception: $($_.Exception.Message)"
  }

  Capture-Desktop (Join-Path $Artifacts "multisim-window-before-sim.png")

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
    ("write " + $dq + $r + $dq)
  ) | Set-Content -Path $commandFile -Encoding ASCII

  Log "Command file written: $commandFile"
  Get-Content $commandFile | ForEach-Object { Log "CMD: $_" }

  $started = $false
  if ($circuit) {
    try {
      Log "Calling circuit.DoCommandLine(commandFile, logFile)"
      $circuit.DoCommandLine($commandFile, $simLog)
      $started = $true
      Log "DoCommandLine accepted. SimulationState=$($circuit.SimulationState)"
    } catch {
      Log "DoCommandLine exception: $($_.Exception.Message)"
    }
  }

  if ($started) {
    $deadline = (Get-Date).AddSeconds(120)
    $lastState = $null
    while ((Get-Date) -lt $deadline) {
      $state = [int]$circuit.SimulationState
      if ($state -ne $lastState) {
        Log "SimulationState=$state"
        $lastState = $state
      }
      if ($state -eq 0) { break }
      Start-Sleep -Milliseconds 500
    }

    if ([int]$circuit.SimulationState -ne 0) {
      Log "Simulation timeout; calling StopSimulation()."
      try { $circuit.StopSimulation() } catch {}
    }
  } else {
    Log "Simulation was not started."
  }

  Start-Sleep -Seconds 2

  if (Test-Path $simLog) {
    Log "Simulation log exists, size=$((Get-Item $simLog).Length)"
  } else {
    Log "Simulation log missing."
  }

  if (Test-Path $rawFile) {
    Log "Simulation RAW exists, size=$((Get-Item $rawFile).Length)"
  } else {
    Log "Simulation RAW missing."
  }

  Capture-Desktop (Join-Path $Artifacts "multisim-window-after-sim.png")

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
