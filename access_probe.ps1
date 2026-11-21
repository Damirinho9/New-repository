
$ErrorActionPreference = "Stop"
Write-Host "OS:" (Get-CimInstance Win32_OperatingSystem).Caption
Write-Host "OLEDB providers:"
try {
  $e = New-Object System.Data.OleDb.OleDbEnumerator
  $t = $e.GetElements()
  $t | Where-Object { $_.SOURCES_NAME -like "*ACE*" -or $_.SOURCES_NAME -like "*Jet*" } | Format-Table SOURCES_NAME,SOURCES_DESCRIPTION
} catch { Write-Host $_ }
$providers = @("Microsoft.ACE.OLEDB.16.0","Microsoft.ACE.OLEDB.12.0")
foreach($p in $providers){
  try{
    $cat = New-Object -ComObject ADOX.Catalog
    $tmp = Join-Path $env:RUNNER_TEMP ("probe_"+($p -replace '\.','_')+".accdb")
    if(Test-Path $tmp){Remove-Item $tmp -Force}
    $cat.Create("Provider=$p;Data Source=$tmp;")
    Write-Host "CREATE_OK $p $tmp" (Get-Item $tmp).Length
    [Runtime.InteropServices.Marshal]::ReleaseComObject($cat) | Out-Null
  } catch { Write-Host "CREATE_FAIL $p $($_.Exception.Message)" }
}
try {
  $dao = New-Object -ComObject DAO.DBEngine.120
  Write-Host "DAO_OK" $dao.Version
} catch { Write-Host "DAO_FAIL" $_.Exception.Message }
