$ErrorActionPreference="Stop"
$root=$PSScriptRoot
$dbPath=(Get-ChildItem (Join-Path $root "access_out") -Filter *.accdb | Select-Object -First 1).FullName
$log=Join-Path $root "ACCESS_ENGINE_FINAL.txt"
$dao=New-Object -ComObject DAO.DBEngine.120
$db=$dao.OpenDatabase($dbPath)
function Count-Rs($rs){$c=0;if(-not $rs.EOF){$rs.MoveLast();$c=$rs.RecordCount};$rs.Close();return $c}
function Assert([bool]$ok,[string]$msg){if(!$ok){throw "FAIL: $msg"};Add-Content $log ("PASS "+$msg)}
"ACCESS ENGINE FINAL ACCEPTANCE" | Set-Content $log -Encoding UTF8
Add-Content $log ("DB="+$dbPath)
$expected=@{"Сотрудники"=5;"Магазины"=11;"Транспортные компании"=7;"Книги"=29;"Заказы"=41;"Описание заказов"=173}
foreach($t in $expected.Keys){
  $rs=$db.OpenRecordset($t);$c=Count-Rs $rs;Assert ($c -eq $expected[$t]) ("TABLE "+$t+" rows="+$c)
}
$queries=@(
"Цена книг","Цена книг до 500 р","Цена книг Макаровой","Книги ценой от 200 до 500 р за 2012 год","Заказы с задержкой выполнения",
"Список книг по сериям","Книги серии Учебное пособие","Книги двух учебных серий","Книги с диском","Список заказов по датам",
"Заказы за 2012 год","Сотрудники без заказов","Заказчики книг по информатике","Книги в магазинах Саратова за 2012 год","Магазины книги по налогам",
"Поиск транспортной компании","Поиск заказов по фамилии сотрудника","Поиск заказов по фамилии сотрудника за период","Поиск книг по году","Заказы определенного магазина",
"Стоимость книг в заказах","Общая стоимость проданных книг","Стоимость заказов","Стоимость заказов по годам","Количество заказов, сделанных каждым магазином",
"Количество проданных книг каждого названия","Количество заказов по сотрудникам","Сводная стоимость книг в заказах","Работа сотрудников","Учет работы сотрудников по кварталам",
"Количество заказов по магазинам и годам")
foreach($qname in $queries){
  $qd=$db.QueryDefs.Item($qname)
  foreach($p in $qd.Parameters){
    switch($p.Name){
      "Введите город" {$p.Value="Москва"}
      "Введите фамилию:" {$p.Value="Юрьева"}
      "Введите начало интервала" {$p.Value=[datetime]"2009-01-01"}
      "Введите конец интервала" {$p.Value=[datetime]"2012-12-31"}
      "Введите год издания" {$p.Value=2012}
      "Введите название магазина" {$p.Value="Амиталь"}
      default {throw "Unexpected parameter in $qname : $($p.Name)"}
    }
  }
  $rs=$qd.OpenRecordset();$c=Count-Rs $rs
  Add-Content $log ("PASS QUERY "+$qname+" rows="+$c+" parameters="+$qd.Parameters.Count)
}
$checks=@(
 @("Заказы-Магазины","SELECT Count(*) AS C FROM [Заказы] AS z LEFT JOIN [Магазины] AS m ON z.[Код магазина]=m.[Код магазина] WHERE m.[Код магазина] Is Null"),
 @("Заказы-Сотрудники","SELECT Count(*) AS C FROM [Заказы] AS z LEFT JOIN [Сотрудники] AS s ON z.[Код сотрудника]=s.[Код сотрудника] WHERE s.[Код сотрудника] Is Null"),
 @("Заказы-Транспорт","SELECT Count(*) AS C FROM [Заказы] AS z LEFT JOIN [Транспортные компании] AS t ON z.[Доставка]=t.[Название компании] WHERE t.[Название компании] Is Null"),
 @("Описание-Заказы","SELECT Count(*) AS C FROM [Описание заказов] AS d LEFT JOIN [Заказы] AS z ON d.[Код заказа]=z.[Код заказа] WHERE z.[Код заказа] Is Null"),
 @("Описание-Книги","SELECT Count(*) AS C FROM [Описание заказов] AS d LEFT JOIN [Книги] AS k ON d.[Код книги]=k.[Код книги] WHERE k.[Код книги] Is Null")
)
foreach($x in $checks){$rs=$db.OpenRecordset($x[1]);$c=$rs.Fields.Item("C").Value;$rs.Close();Assert ($c -eq 0) ("RELATION "+$x[0]+" orphan_rows=0")}
$rs=$db.OpenRecordset("SELECT Count(*) AS C FROM [Стоимость книг в заказах] WHERE Abs([Стоимость]-([Цена]*[Количество]-[Цена]*[Количество]*[Скидка]*0.01))>0.0001")
$bad=$rs.Fields.Item("C").Value;$rs.Close();Assert ($bad -eq 0) "FORMULA mismatches=0"
$rs=$db.OpenRecordset("SELECT TOP 1 [Код заказа],[Цена],[Количество],[Скидка],[Стоимость] FROM [Стоимость книг в заказах] ORDER BY [Код заказа],[Код книги]")
Add-Content $log ("SAMPLE order="+$rs.Fields.Item("Код заказа").Value+" price="+$rs.Fields.Item("Цена").Value+" qty="+$rs.Fields.Item("Количество").Value+" discount="+$rs.Fields.Item("Скидка").Value+" cost="+$rs.Fields.Item("Стоимость").Value);$rs.Close()
Add-Content $log "RESULT=PASS"
$db.Close()
Get-Content $log
