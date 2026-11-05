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

$app = $null
$circuit = $null
try {
  $app = New-Object -ComObject "MultisimInterface.MultisimApp"
  ($app | Get-Member | Out-String) | Set-Content (Join-Path $Artifacts "multisim-app-members.txt")
  Log "COM object created."

  $app.Connect()
  Log "Connected."

  $circuit = $app.NewFile()
  ($circuit | Get-Member | Out-String) | Set-Content (Join-Path $Artifacts "multisim-circuit-members.txt")
  Log "NewFile created."

  $netlist = Join-Path $Workspace "multisim\7330744_V6_PhotoRelay_3state_Multisim.cir"
  $commandFile = Join-Path $Artifacts "multisim-commands.txt"
  $simLog = Join-Path $Artifacts "multisim-simulation.log"
  $rawFile = Join-Path $Artifacts "multisim-results.raw"

  $n = $netlist.Replace("\","/")
  $r = $rawFile.Replace("\","/")
  $dq = [char]34
  @(
    ("source " + $dq + $n + $dq),
    "tran 0.0002 12",
    "display",
    ("write " + $dq + $r + $dq + " all"),
    "plot all"
  ) | Set-Content -Path $commandFile -Encoding ASCII

  Get-Content $commandFile | ForEach-Object { Log "CMD: $_" }

  $circuit.DoCommandLine($commandFile, $simLog)
  Log "DoCommandLine submitted."

  # The 12s transient finishes in a few seconds on the runner.
  for($i=1;$i -le 8;$i++){
    Start-Sleep -Seconds 3
    Log "Poll $i SimulationState=$($circuit.SimulationState)"
    if(Test-Path $rawFile){
      Log "RAW exists size=$((Get-Item $rawFile).Length)"
      break
    }
  }

  Log "LastErrorMessage=$($circuit.LastErrorMessage)"

  # Screenshot after the plot command has had time to create a grapher window.
  try {
    Add-Type -AssemblyName System.Windows.Forms
    Add-Type -AssemblyName System.Drawing
    $bounds = [System.Windows.Forms.Screen]::PrimaryScreen.Bounds
    $bmp = New-Object System.Drawing.Bitmap $bounds.Width, $bounds.Height
    $g = [System.Drawing.Graphics]::FromImage($bmp)
    $g.CopyFromScreen($bounds.Location, [System.Drawing.Point]::Empty, $bounds.Size)
    $shot = Join-Path $Artifacts "multisim-after-plot.png"
    $bmp.Save($shot, [System.Drawing.Imaging.ImageFormat]::Png)
    $g.Dispose(); $bmp.Dispose()
    Log "Screenshot saved."
  } catch { Log "Screenshot failed: $($_.Exception.Message)" }

  try { $circuit.StopSimulation() } catch {}
  try { $app.Disconnect() } catch {}
} catch {
  Log "FATAL COM ERROR: $($_.Exception.ToString())"
  exit 2
}

if(Test-Path $rawFile){
  Log "SUCCESS RAW file generated."
  exit 0
}else{
  Log "RAW file still missing."
  exit 3
}
