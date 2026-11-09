param([int]$Sequence,[string]$Workspace=$env:GITHUB_WORKSPACE)
$ErrorActionPreference='Stop';$ProgressPreference='SilentlyContinue'
$Out=Join-Path $Workspace 'native7330744-artifacts'
$Ms=(Get-Content (Join-Path $Out 'multisim-executable.txt') -Raw).Trim()
$commands=Join-Path $Out "actions-$Sequence.json"
$apipath='repos/Damirinho9/New-repository/contents/native_control_7330744.json?ref=multisim-7330744-native-gui-v2'
$ready=$false
for($i=0;$i -lt 48;$i++){
 try{
  $reply=gh api $apipath | ConvertFrom-Json
  $json=[System.Text.Encoding]::UTF8.GetString([System.Convert]::FromBase64String($reply.content))
  $control=$json | ConvertFrom-Json
  if($control.complete -eq $true){Add-Content $env:GITHUB_ENV 'GUI_DONE=true';exit 0}
  if([int]$control.sequence -eq $Sequence){
   [IO.File]::WriteAllText($commands,$json,[Text.UTF8Encoding]::new($false))
   $ready=$true;break
  }
 }catch{Write-Host "Control sequence $Sequence not available yet"}
 Start-Sleep 10
}
if(-not $ready){Write-Host "Bounded wait for sequence $Sequence elapsed";exit 0}
python (Join-Path $Workspace 'nativeui7330744.py') $Ms $Out $commands
Write-Host "Native UI correction sequence $Sequence exit=$LASTEXITCODE"
exit 0
