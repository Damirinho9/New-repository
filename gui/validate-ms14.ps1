param(
  [string]$Workspace,
  [string]$Ms14
)
$ErrorActionPreference="Continue"
$A=Join-Path $Workspace "gui-artifacts"
$Log=Join-Path $A "ms14-validation.log"
function L([string]$m){$s="[$(Get-Date -Format o)] $m";Write-Host $s;Add-Content $Log $s}

L "32-bit validation worker starting"
L "Is64BitProcess=$([Environment]::Is64BitProcess)"
if(-not (Test-Path $Ms14)){L "MS14 not found: $Ms14";exit 4}

$app=$null;$c=$null
try{
  $app=New-Object -ComObject "MultisimInterface.MultisimApp"
  $app.Connect()
  L "Connected: $($app.VersionInfo)"
  $c=$app.OpenFile($Ms14)
  L "OpenFile succeeded"
  L "CircuitName=$($c.CircuitName)"
  L "FileName=$($c.FileName)"
  L "LastError=$($c.LastErrorMessage)"
  ($c | Get-Member | Out-String) | Set-Content (Join-Path $A "ms14-circuit-members.txt")

  try{
    $r=$c.Save()
    L "Save() result=$r"
  }catch{L "Save() error: $($_.Exception.Message)"}

  $snippet=Join-Path $A "7330744_V6_PhotoRelay_design_snippet.png"
  try{
    $r=$c.SaveDesignAsSnippet($snippet,1.0)
    L "SaveDesignAsSnippet result=$r exists=$(Test-Path $snippet)"
  }catch{L "SaveDesignAsSnippet error: $($_.Exception.ToString())"}

  foreach($fmt in 0..7){
    foreach($ext in @("png","bmp","jpg","emf")){
      $p=Join-Path $A ("circuit-image-f{0}.{1}" -f $fmt,$ext)
      try{
        $r=$c.GetCircuitImage($fmt,$p)
        L "GetCircuitImage fmt=$fmt ext=$ext result=$r exists=$(Test-Path $p)"
        if(Test-Path $p){
          L "Circuit image generated: $p size=$((Get-Item $p).Length)"
          break
        }
      }catch{
        L "GetCircuitImage fmt=$fmt ext=$ext error=$($_.Exception.Message)"
      }
    }
  }

  try{$app.Disconnect();L "Disconnected"}catch{}
}catch{
  L "FATAL: $($_.Exception.ToString())"
  exit 5
}
exit 0
