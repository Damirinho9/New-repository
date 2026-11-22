$ErrorActionPreference="Stop"
$root=$PSScriptRoot
$dbPath=(Get-ChildItem (Join-Path $root "access_out") -Filter *.accdb | Select-Object -First 1).FullName
if(!$dbPath){throw "ACCDB not found"}
$exe=(Get-ChildItem "C:\Program Files\Microsoft Office" -Filter MSACCESS.EXE -Recurse -ErrorAction SilentlyContinue | Select-Object -First 1).FullName
if(!$exe){throw "MSACCESS.EXE not found"}
$log=Join-Path $root "ACCESS_FINAL_ACCEPTANCE.txt"

$queries=@(
"Цена книг",
"Цена книг до 500 р",
"Цена книг Макаровой",
"Книги ценой от 200 до 500 р за 2012 год",
"Заказы с задержкой выполнения",
"Список книг по сериям",
"Книги серии Учебное пособие",
"Книги двух учебных серий",
"Книги с диском",
"Список заказов по датам",
"Заказы за 2012 год",
"Сотрудники без заказов",
"Заказчики книг по информатике",
"Книги в магазинах Саратова за 2012 год",
"Магазины книги по налогам",
"Поиск транспортной компании",
"Поиск заказов по фамилии сотрудника",
"Поиск заказов по фамилии сотрудника за период",
"Поиск книг по году",
"Заказы определенного магазина",
"Стоимость книг в заказах",
"Общая стоимость проданных книг",
"Стоимость заказов",
"Стоимость заказов по годам",
"Количество заказов, сделанных каждым магазином",
"Количество проданных книг каждого названия",
"Количество заказов по сотрудникам",
"Сводная стоимость книг в заказах",
"Работа сотрудников",
"Учет работы сотрудников по кварталам",
"Количество заказов по магазинам и годам"
)
$tables=@("Сотрудники","Магазины","Транспортные компании","Книги","Заказы","Описание заказов")

$vbs=@'
Option Explicit
On Error Resume Next
Dim sh, app, db, fso, logPath, out, tables, queries, i, name, rs, qd, p, pn, cnt, sql
Set sh=CreateObject("WScript.Shell")
logPath=sh.ExpandEnvironmentStrings("%ACCEPT_LOG%")
Set fso=CreateObject("Scripting.FileSystemObject")
Set out=fso.CreateTextFile(logPath, True, True)
Set app=GetObject(, "Access.Application")
If Err.Number<>0 Then
  out.WriteLine "FAIL GETOBJECT " & Hex(Err.Number) & " " & Err.Description
  out.Close
  WScript.Quit 20
End If
Set db=app.CurrentDb
out.WriteLine "ACCESS_VERSION=" & app.Version
out.WriteLine "DATABASE=" & db.Name
out.WriteLine ""

tables=Split(sh.ExpandEnvironmentStrings("%ACCEPT_TABLES%"), "|")
out.WriteLine "[TABLES]"
For i=0 To UBound(tables)
  name=tables(i)
  Err.Clear
  app.DoCmd.OpenTable name, 0, 2
  If Err.Number<>0 Then
    out.WriteLine "FAIL TABLE GUI " & name & " " & Hex(Err.Number) & " " & Err.Description
    out.Close
    WScript.Quit 21
  End If
  Set rs=db.OpenRecordset(name)
  If Err.Number<>0 Then
    out.WriteLine "FAIL TABLE DATA " & name & " " & Hex(Err.Number) & " " & Err.Description
    out.Close
    WScript.Quit 22
  End If
  cnt=0
  If Not rs.EOF Then rs.MoveLast: cnt=rs.RecordCount
  rs.Close
  app.DoCmd.Close 0, name, 2
  out.WriteLine "PASS TABLE " & name & " rows=" & cnt
Next
out.WriteLine ""

queries=Split(sh.ExpandEnvironmentStrings("%ACCEPT_QUERIES%"), "|")
out.WriteLine "[QUERIES]"
For i=0 To UBound(queries)
  name=queries(i)
  Err.Clear
  Set qd=db.QueryDefs(name)
  If Err.Number<>0 Then
    out.WriteLine "FAIL QUERY MISSING " & name & " " & Hex(Err.Number) & " " & Err.Description
    out.Close
    WScript.Quit 30
  End If

  If qd.Parameters.Count=0 Then
    Err.Clear
    app.DoCmd.OpenQuery name, 0, 2
    If Err.Number<>0 Then
      out.WriteLine "FAIL QUERY GUI " & name & " " & Hex(Err.Number) & " " & Err.Description
      out.Close
      WScript.Quit 31
    End If
    app.DoCmd.Close 1, name, 2
  Else
    For Each p In qd.Parameters
      pn=p.Name
      If Left(pn,1)="[" And Right(pn,1)="]" Then pn=Mid(pn,2,Len(pn)-2)
      Select Case pn
        Case "Введите город": p.Value="Москва"
        Case "Введите фамилию:": p.Value="Юрьева"
        Case "Введите начало интервала": p.Value=CDate("01/01/2009")
        Case "Введите конец интервала": p.Value=CDate("12/31/2012")
        Case "Введите год издания": p.Value=2012
        Case "Введите название магазина": p.Value="Амиталь"
        Case Else
          out.WriteLine "FAIL UNEXPECTED PARAMETER query=" & name & " parameter=" & p.Name
          out.Close
          WScript.Quit 32
      End Select
    Next
  End If

  Err.Clear
  Set rs=qd.OpenRecordset()
  If Err.Number<>0 Then
    out.WriteLine "FAIL QUERY EXEC " & name & " " & Hex(Err.Number) & " " & Err.Description
    out.Close
    WScript.Quit 33
  End If
  cnt=0
  If Not rs.EOF Then rs.MoveLast: cnt=rs.RecordCount
  rs.Close
  out.WriteLine "PASS QUERY " & name & " rows=" & cnt & " parameters=" & qd.Parameters.Count
Next
out.WriteLine ""

out.WriteLine "[RELATION_INTEGRITY]"
Dim checks, labels
checks=Array( _
 "SELECT Count(*) AS C FROM [Заказы] z LEFT JOIN [Магазины] m ON z.[Код магазина]=m.[Код магазина] WHERE m.[Код магазина] Is Null", _
 "SELECT Count(*) AS C FROM [Заказы] z LEFT JOIN [Сотрудники] s ON z.[Код сотрудника]=s.[Код сотрудника] WHERE s.[Код сотрудника] Is Null", _
 "SELECT Count(*) AS C FROM [Заказы] z LEFT JOIN [Транспортные компании] t ON z.[Доставка]=t.[Название компании] WHERE t.[Название компании] Is Null", _
 "SELECT Count(*) AS C FROM [Описание заказов] d LEFT JOIN [Заказы] z ON d.[Код заказа]=z.[Код заказа] WHERE z.[Код заказа] Is Null", _
 "SELECT Count(*) AS C FROM [Описание заказов] d LEFT JOIN [Книги] k ON d.[Код книги]=k.[Код книги] WHERE k.[Код книги] Is Null" _
)
labels=Array("Заказы-Магазины","Заказы-Сотрудники","Заказы-Транспорт","Описание-Заказы","Описание-Книги")
For i=0 To UBound(checks)
  Set rs=db.OpenRecordset(checks(i))
  cnt=rs.Fields("C").Value
  rs.Close
  out.WriteLine labels(i) & " orphan_rows=" & cnt
  If cnt<>0 Then out.Close: WScript.Quit 40+i
Next

out.WriteLine ""
out.WriteLine "[FORMULA]"
sql="SELECT Count(*) AS C FROM [Стоимость книг в заказах] WHERE Abs([Стоимость]-([Цена]*[Количество]-[Цена]*[Количество]*[Скидка]*0.01))>0.0001"
Set rs=db.OpenRecordset(sql)
cnt=rs.Fields("C").Value
rs.Close
out.WriteLine "formula_mismatches=" & cnt
If cnt<>0 Then out.Close: WScript.Quit 50

sql="SELECT TOP 1 [Код заказа],[Цена],[Количество],[Скидка],[Стоимость] FROM [Стоимость книг в заказах] ORDER BY [Код заказа],[Код книги]"
Set rs=db.OpenRecordset(sql)
out.WriteLine "sample_order=" & rs.Fields("Код заказа").Value & "; price=" & rs.Fields("Цена").Value & "; qty=" & rs.Fields("Количество").Value & "; discount=" & rs.Fields("Скидка").Value & "; cost=" & rs.Fields("Стоимость").Value
rs.Close

out.WriteLine ""
out.WriteLine "RESULT=PASS"
out.Close
app.CloseCurrentDatabase
app.Quit 2
WScript.Quit 0
'@
$vbsPath=Join-Path $root "access_final_acceptance.vbs"
Set-Content -Path $vbsPath -Value $vbs -Encoding Unicode

$env:ACCEPT_LOG=$log
$env:ACCEPT_TABLES=($tables -join "|")
$env:ACCEPT_QUERIES=($queries -join "|")

$p=Start-Process -FilePath $exe -ArgumentList ('"'+$dbPath+'" /runtime') -PassThru
Start-Sleep -Seconds 12
$p.Refresh()
Write-Host "MSACCESS PID=$($p.Id) SESSION=$($p.SessionId) HWND=$($p.MainWindowHandle)"

# Initialize Access UI if a security notice remains.
Add-Type -AssemblyName UIAutomationClient
Add-Type -AssemblyName UIAutomationTypes
try{
  $rootEl=[Windows.Automation.AutomationElement]::RootElement
  $openCond=New-Object Windows.Automation.PropertyCondition([Windows.Automation.AutomationElement]::NameProperty,"Open")
  $openBtn=$rootEl.FindFirst([Windows.Automation.TreeScope]::Subtree,$openCond)
  if($openBtn){$inv=$openBtn.GetCurrentPattern([Windows.Automation.InvokePattern]::Pattern);$inv.Invoke();Start-Sleep -Seconds 5}
}catch{}

$proc=Start-Process -FilePath "cscript.exe" -ArgumentList @("//nologo",$vbsPath) -PassThru -Wait
Write-Host "VALIDATOR_EXIT=$($proc.ExitCode)"
if(Test-Path $log){Get-Content $log}
if($proc.ExitCode -ne 0){throw "Access final acceptance failed with code $($proc.ExitCode)"}
