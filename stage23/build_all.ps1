param([ValidateSet('independent','native')][string]$Mode='independent',[string]$Output='run-output',[ValidateSet('1','all')][string]$Work='all',[switch]$Candidate,[string]$Seed)
$ErrorActionPreference='Stop'
$arguments=@((Join-Path $PSScriptRoot 'native_build.py'),'--mode',$Mode,'--out',$Output,'--work',$Work)
if($Candidate){$arguments+='--candidate'}
if($Seed){$arguments+=@('--seed',$Seed)}
python @arguments
exit $LASTEXITCODE
