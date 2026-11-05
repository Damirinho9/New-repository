param([string]$Workspace=$env:GITHUB_WORKSPACE)
$ErrorActionPreference="Continue"
$A=Join-Path $Workspace "stage5-artifacts"
New-Item -ItemType Directory -Force -Path $A | Out-Null
$log=Join-Path $A "transfer-com.log"
function L([string]$m){$s="[$(Get-Date -Format o)] $m";Write-Host $s;Add-Content $log $s}

$app=$null;$c=$null
try{
  $app=New-Object -ComObject "MultisimInterface.MultisimApp"
  $app.Connect()
  L "Connected to $($app.VersionInfo)"
  $c=$app.NewFile()
  $net=Join-Path $Workspace "stage5\7330744_V6_PhotoRelay_transfer_Multisim.cir"
  $cmd=Join-Path $A "transfer-commands.txt"
  $raw=Join-Path $A "7330744_transfer.raw"
  $simlog=Join-Path $A "7330744_transfer_simulation.log"
  $dq=[char]34
  $n=$net.Replace("\","/")
  $r=$raw.Replace("\","/")
  @(
    ("source "+$dq+$n+$dq),
    "dc I_PHOTO 0 12u 0.1u",
    "display",
    ("write "+$dq+$r+$dq+" all")
  ) | Set-Content $cmd -Encoding ASCII
  $c.DoCommandLine($cmd,$simlog)
  for($i=0;$i -lt 30;$i++){
    Start-Sleep -Seconds 2
    if(Test-Path $raw){
      $sz=(Get-Item $raw).Length
      L "RAW size=$sz"
      if($sz -gt 1000){break}
    }
  }
  L "SimulationState=$($c.SimulationState)"
  L "LastErrorMessage=$($c.LastErrorMessage)"
  try{$c.StopSimulation()}catch{}
  try{$app.Disconnect()}catch{}
}catch{
  L "ERROR $($_.Exception.ToString())"
  exit 2
}
if(Test-Path (Join-Path $A "7330744_transfer.raw")){exit 0}else{exit 3}
