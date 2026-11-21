$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"
$root = $PSScriptRoot
$out = Join-Path $root "access_out"
New-Item -ItemType Directory -Force -Path $out | Out-Null
$dbPath = Join-Path $out "LR2-3_P поставки книг.accdb"
$xlsxPath = Join-Path $out "Таблицы.xlsx"
if(Test-Path $dbPath){Remove-Item $dbPath -Force}
if(Test-Path $xlsxPath){Remove-Item $xlsxPath -Force}

Set-PSRepository -Name PSGallery -InstallationPolicy Trusted
if(-not (Get-Module -ListAvailable -Name ImportExcel)){Install-Module ImportExcel -Scope CurrentUser -Force -AllowClobber}
Import-Module ImportExcel

function ReadCsv([string]$name){Import-Csv -Path (Join-Path $root ("access_src\"+$name+".csv")) -Encoding UTF8}

$books=ReadCsv "Книги"
foreach($r in $books){
  $r."Код книги"=[int]$r."Код книги"; $r."Год издания"=[int]$r."Год издания"; $r."Количество страниц"=[int]$r."Количество страниц"; $r."Цена"=[decimal]$r."Цена"; $r."Диск"=($r."Диск" -eq "Да")
}
$stores=ReadCsv "Магазины"; foreach($r in $stores){$r."Код магазина"=[int]$r."Код магазина"}
$emps=ReadCsv "Сотрудники"
foreach($r in $emps){
  $r."Код сотрудника"=[int]$r."Код сотрудника"
  $r."Дата рождения"=[datetime]::ParseExact($r."Дата рождения","yyyy-MM-dd",$null)
  $r."Дата найма"=[datetime]::ParseExact($r."Дата найма","yyyy-MM-dd",$null)
}
$trans=ReadCsv "Транспортные компании"
$orders=ReadCsv "Заказы"
foreach($r in $orders){
  $r."Код заказа"=[int]$r."Код заказа"; $r."Код магазина"=[int]$r."Код магазина"; $r."Код сотрудника"=[int]$r."Код сотрудника"
  $r."Дата заказа"=[datetime]::ParseExact($r."Дата заказа","yyyy-MM-dd",$null)
  $r."Требуемая дата выполнения"=[datetime]::ParseExact($r."Требуемая дата выполнения","yyyy-MM-dd",$null)
  $r."Фактическая дата выполнения"=[datetime]::ParseExact($r."Фактическая дата выполнения","yyyy-MM-dd",$null)
}
$details=ReadCsv "Описание заказов"
foreach($r in $details){$r."Код заказа"=[int]$r."Код заказа";$r."Код книги"=[int]$r."Код книги";$r."Количество"=[int]$r."Количество";$r."Скидка"=[int]$r."Скидка"}

$books | Export-Excel -Path $xlsxPath -WorksheetName "Книги" -AutoSize -ClearSheet
$stores | Export-Excel -Path $xlsxPath -WorksheetName "Магазины" -AutoSize -Append
$emps | Export-Excel -Path $xlsxPath -WorksheetName "Сотрудники" -AutoSize -Append
$trans | Export-Excel -Path $xlsxPath -WorksheetName "Транспортные компании" -AutoSize -Append
$orders | Export-Excel -Path $xlsxPath -WorksheetName "Заказы" -AutoSize -Append
$details | Export-Excel -Path $xlsxPath -WorksheetName "Описание заказов" -AutoSize -Append
Write-Host "XLSX_CREATED" (Get-Item $xlsxPath).Length

$provider=$null
foreach($p in @("Microsoft.ACE.OLEDB.16.0","Microsoft.ACE.OLEDB.12.0")){
  try{$c=New-Object System.Data.OleDb.OleDbConnection(("Provider="+$p+";Data Source="+$xlsxPath+";Extended Properties='Excel 12.0 Xml;HDR=YES';"));$c.Open();$c.Close();$provider=$p;break}catch{}
}
if(-not $provider){throw "ACE provider unavailable"}
Write-Host "ACE_PROVIDER=$provider"

$cat=New-Object -ComObject ADOX.Catalog
$cat.Create("Provider="+$provider+";Data Source="+$dbPath+";")
[Runtime.InteropServices.Marshal]::ReleaseComObject($cat) | Out-Null

$conn=New-Object System.Data.OleDb.OleDbConnection("Provider="+$provider+";Data Source="+$dbPath+";")
$conn.Open()
function Exec([string]$sql){$cmd=$conn.CreateCommand();$cmd.CommandText=$sql;[void]$cmd.ExecuteNonQuery()}

Exec "CREATE TABLE [Сотрудники] ([Код сотрудника] COUNTER, [Фамилия] VARCHAR(20) NOT NULL, [Имя] VARCHAR(20) NOT NULL, [Отчество] VARCHAR(20) NOT NULL, [Должность] VARCHAR(25) NOT NULL, [Телефон] VARCHAR(14), [Дата рождения] DATETIME NOT NULL, [Дата найма] DATETIME NOT NULL)"
Exec "ALTER TABLE [Сотрудники] ADD CONSTRAINT [PK_Сотрудники] PRIMARY KEY ([Код сотрудника])"
Exec "CREATE INDEX [IX_Сотрудники_Фамилия] ON [Сотрудники] ([Фамилия])"
Exec "CREATE TABLE [Магазины] ([Код магазина] COUNTER, [Название магазина] VARCHAR(30) NOT NULL, [ФИО контактного лица] VARCHAR(50) NOT NULL, [Город] VARCHAR(25) NOT NULL, [Адрес] VARCHAR(70) NOT NULL, [Телефон] VARCHAR(14))"
Exec "ALTER TABLE [Магазины] ADD CONSTRAINT [PK_Магазины] PRIMARY KEY ([Код магазина])"
Exec "CREATE INDEX [IX_Магазины_Название] ON [Магазины] ([Название магазина])"
Exec "CREATE INDEX [IX_Магазины_Город] ON [Магазины] ([Город])"
Exec "CREATE TABLE [Транспортные компании] ([Название компании] VARCHAR(5) NOT NULL, [ФИО контактного лица] VARCHAR(50) NOT NULL, [Город] VARCHAR(25) NOT NULL, [Телефон] VARCHAR(14))"
Exec "ALTER TABLE [Транспортные компании] ADD CONSTRAINT [PK_Транспортные] PRIMARY KEY ([Название компании])"
Exec "CREATE INDEX [IX_Транспортные_Город] ON [Транспортные компании] ([Город])"
Exec "CREATE TABLE [Книги] ([Код книги] COUNTER, [Авторы] VARCHAR(70) NOT NULL, [Название] VARCHAR(100) NOT NULL, [Серия] VARCHAR(30), [Год издания] SHORT, [Количество страниц] SHORT, [Цена] CURRENCY NOT NULL, [Диск] YESNO)"
Exec "ALTER TABLE [Книги] ADD CONSTRAINT [PK_Книги] PRIMARY KEY ([Код книги])"
Exec "CREATE INDEX [IX_Книги_Авторы] ON [Книги] ([Авторы])"
Exec "CREATE TABLE [Заказы] ([Код заказа] COUNTER, [Код магазина] LONG NOT NULL, [Код сотрудника] LONG NOT NULL, [Дата заказа] DATETIME NOT NULL, [Требуемая дата выполнения] DATETIME NOT NULL, [Фактическая дата выполнения] DATETIME, [Доставка] VARCHAR(5) NOT NULL)"
Exec "ALTER TABLE [Заказы] ADD CONSTRAINT [PK_Заказы] PRIMARY KEY ([Код заказа])"
Exec "CREATE TABLE [Описание заказов] ([Код заказа] LONG NOT NULL, [Код книги] LONG NOT NULL, [Количество] SHORT NOT NULL, [Скидка] SHORT)"

$xl=$xlsxPath.Replace("'","''")
Exec ("INSERT INTO [Сотрудники] ([Фамилия],[Имя],[Отчество],[Должность],[Телефон],[Дата рождения],[Дата найма]) SELECT [Фамилия],[Имя],[Отчество],[Должность],[Телефон],[Дата рождения],[Дата найма] FROM [Сотрудники$] IN '"+$xl+"' 'Excel 12.0 Xml;HDR=YES;'")
Exec ("INSERT INTO [Магазины] ([Название магазина],[ФИО контактного лица],[Город],[Адрес],[Телефон]) SELECT [Название магазина],[ФИО контактного лица],[Город],[Адрес],[Телефон] FROM [Магазины$] IN '"+$xl+"' 'Excel 12.0 Xml;HDR=YES;'")
Exec ("INSERT INTO [Транспортные компании] ([Название компании],[ФИО контактного лица],[Город],[Телефон]) SELECT [Название компании],[ФИО контактного лица],[Город],[Телефон] FROM [Транспортные компании$] IN '"+$xl+"' 'Excel 12.0 Xml;HDR=YES;'")
Exec ("INSERT INTO [Книги] ([Авторы],[Название],[Серия],[Год издания],[Количество страниц],[Цена],[Диск]) SELECT [Авторы],[Название],[Серия],[Год издания],[Количество страниц],[Цена],[Диск] FROM [Книги$] IN '"+$xl+"' 'Excel 12.0 Xml;HDR=YES;'")
Exec ("INSERT INTO [Заказы] ([Код магазина],[Код сотрудника],[Дата заказа],[Требуемая дата выполнения],[Фактическая дата выполнения],[Доставка]) SELECT [Код магазина],[Код сотрудника],[Дата заказа],[Требуемая дата выполнения],[Фактическая дата выполнения],[Доставка] FROM [Заказы$] IN '"+$xl+"' 'Excel 12.0 Xml;HDR=YES;'")
Exec ("INSERT INTO [Описание заказов] ([Код заказа],[Код книги],[Количество],[Скидка]) SELECT [Код заказа],[Код книги],[Количество],[Скидка] FROM [Описание заказов$] IN '"+$xl+"' 'Excel 12.0 Xml;HDR=YES;'")
$conn.Close()

$dao=$null
foreach($prog in @("DAO.DBEngine.160","DAO.DBEngine.120")){try{$dao=New-Object -ComObject $prog;Write-Host "DAO=$prog";break}catch{}}
if(-not $dao){throw "DAO unavailable"}
$db=$dao.OpenDatabase($dbPath)

function SetProp($obj,[string]$name,[int]$type,$value){try{$obj.Properties.Item($name).Value=$value}catch{$p=$db.CreateProperty($name,$type,$value);$obj.Properties.Append($p)}}
function Field([string]$t,[string]$f){$db.TableDefs.Item($t).Fields.Item($f)}
function TextReq([string]$t,[string]$f){$x=Field $t $f;$x.Required=$true;$x.AllowZeroLength=$false}
foreach($a in @(
 @("Сотрудники","Фамилия"),@("Сотрудники","Имя"),@("Сотрудники","Отчество"),@("Сотрудники","Должность"),
 @("Магазины","Название магазина"),@("Магазины","ФИО контактного лица"),@("Магазины","Город"),@("Магазины","Адрес"),
 @("Транспортные компании","Название компании"),@("Транспортные компании","ФИО контактного лица"),@("Транспортные компании","Город"),
 @("Книги","Авторы"),@("Книги","Название"),@("Заказы","Доставка")
)){TextReq $a[0] $a[1]}
foreach($a in @(@("Сотрудники","Телефон"),@("Магазины","Телефон"),@("Транспортные компании","Телефон"))){$x=Field $a[0] $a[1];$x.AllowZeroLength=$true;SetProp $x "InputMask" 10 "(999)000-00-00;0;-"}
foreach($a in @(@("Сотрудники","Дата рождения"),@("Сотрудники","Дата найма"),@("Заказы","Дата заказа"),@("Заказы","Требуемая дата выполнения"),@("Заказы","Фактическая дата выполнения"))){SetProp (Field $a[0] $a[1]) "Format" 10 "Short Date"}
SetProp (Field "Книги" "Диск") "DefaultValue" 10 "0"
SetProp (Field "Описание заказов" "Скидка") "DefaultValue" 10 "0"

function LookupValues([string]$t,[string]$f,[string]$vals){$x=Field $t $f;SetProp $x "DisplayControl" 3 111;SetProp $x "RowSourceType" 10 "Value List";SetProp $x "RowSource" 10 $vals;SetProp $x "BoundColumn" 3 1;SetProp $x "ColumnCount" 3 1;SetProp $x "LimitToList" 1 $true}
LookupValues "Сотрудники" "Должность" "Начальник отдела сбыта;Координатор продаж;Менеджер по продажам"
LookupValues "Магазины" "Город" "Воронеж;Москва;Самара;Санкт-Петербург;Саратов"
LookupValues "Транспортные компании" "Город" "Воронеж;Москва;Самара;Санкт-Петербург;Саратов"
LookupValues "Книги" "Серия" "Бухгалтеру и аудитору;Самоучитель;Учебник для вузов;Учебное пособие;Учебно-практическое пособие"
$x=Field "Заказы" "Доставка";SetProp $x "DisplayControl" 3 111;SetProp $x "RowSourceType" 10 "Table/Query";SetProp $x "RowSource" 10 "SELECT [Название компании],[Город] FROM [Транспортные компании] ORDER BY [Город];";SetProp $x "BoundColumn" 3 1;SetProp $x "ColumnCount" 3 2;SetProp $x "LimitToList" 1 $true

function Rel([string]$n,[string]$p,[string]$c,[string]$pf,[string]$cf){$r=$db.CreateRelation($n,$p,$c,0);$rf=$r.CreateField($pf);$rf.ForeignName=$cf;$r.Fields.Append($rf);$db.Relations.Append($r)}
Rel "Транспортные компанииЗаказы" "Транспортные компании" "Заказы" "Название компании" "Доставка"
Rel "МагазиныЗаказы" "Магазины" "Заказы" "Код магазина" "Код магазина"
Rel "СотрудникиЗаказы" "Сотрудники" "Заказы" "Код сотрудника" "Код сотрудника"
Rel "КнигиОписание заказов" "Книги" "Описание заказов" "Код книги" "Код книги"
Rel "ЗаказыОписание заказов" "Заказы" "Описание заказов" "Код заказа" "Код заказа"

function Sub([string]$t,[string]$s,[string]$m,[string]$c){$td=$db.TableDefs.Item($t);SetProp $td "SubdatasheetName" 10 ("Table."+$s);SetProp $td "LinkMasterFields" 10 $m;SetProp $td "LinkChildFields" 10 $c}
Sub "Магазины" "Заказы" "Код магазина" "Код магазина";Sub "Сотрудники" "Заказы" "Код сотрудника" "Код сотрудника";Sub "Транспортные компании" "Заказы" "Название компании" "Доставка";Sub "Книги" "Описание заказов" "Код книги" "Код книги";Sub "Заказы" "Описание заказов" "Код заказа" "Код заказа"

function Q([string]$n,[string]$s){[void]$db.CreateQueryDef($n,$s)}
Q "Цена книг" "SELECT [Авторы],[Название],[Год издания],[Цена],[Диск] FROM [Книги] ORDER BY [Авторы],[Название],[Год издания];"
Q "Цена книг до 500 р" "SELECT [Авторы],[Название],[Год издания],[Цена],[Диск] FROM [Книги] WHERE [Цена]<=500 ORDER BY [Цена];"
Q "Цена книг Макаровой" 'SELECT [Авторы],[Название],[Год издания],[Цена],[Диск] FROM [Книги] WHERE [Авторы] Like "*Макарова*";'
Q "Книги ценой от 200 до 500 р за 2012 год" "SELECT [Авторы],[Название],[Год издания],[Цена],[Диск] FROM [Книги] WHERE [Год издания]=2012 AND [Цена]>=200 AND [Цена]<=500 ORDER BY [Цена];"
Q "Заказы с задержкой выполнения" "SELECT [Код заказа],[Дата заказа],[Требуемая дата выполнения],[Фактическая дата выполнения] FROM [Заказы] WHERE [Требуемая дата выполнения] < [Фактическая дата выполнения];"
Q "Список книг по сериям" "SELECT [Авторы],[Название],[Серия],[Год издания] FROM [Книги] ORDER BY [Серия],[Авторы],[Название];"
Q "Книги серии Учебное пособие" 'SELECT [Авторы],[Название],[Серия],[Год издания] FROM [Книги] WHERE [Серия]="Учебное пособие";'
Q "Книги двух учебных серий" 'SELECT [Авторы],[Название],[Серия],[Год издания] FROM [Книги] WHERE [Серия] In ("Учебное пособие","Учебник для вузов");'
Q "Книги с диском" "SELECT [Авторы],[Название],[Серия],[Год издания],[Диск] FROM [Книги] WHERE [Диск]=True;"
Q "Список заказов по датам" "SELECT z.[Код заказа],z.[Дата заказа],s.[Фамилия],s.[Имя],s.[Отчество],m.[Название магазина],m.[Город] FROM ([Заказы] AS z INNER JOIN [Сотрудники] AS s ON z.[Код сотрудника]=s.[Код сотрудника]) INNER JOIN [Магазины] AS m ON z.[Код магазина]=m.[Код магазина] ORDER BY z.[Дата заказа];"
Q "Заказы за 2012 год" "SELECT * FROM [Список заказов по датам] WHERE [Дата заказа] Between #01/01/2012# And #12/31/2012#;"
Q "Сотрудники без заказов" "SELECT s.[Должность],s.[Фамилия],s.[Имя],s.[Отчество] FROM [Сотрудники] AS s LEFT JOIN [Заказы] AS z ON s.[Код сотрудника]=z.[Код сотрудника] WHERE z.[Код заказа] Is Null;"
Q "Заказчики книг по информатике" 'SELECT k.[Авторы],k.[Название],k.[Год издания],z.[Дата заказа],m.[Название магазина],m.[Город],d.[Количество] FROM (([Книги] AS k INNER JOIN [Описание заказов] AS d ON k.[Код книги]=d.[Код книги]) INNER JOIN [Заказы] AS z ON d.[Код заказа]=z.[Код заказа]) INNER JOIN [Магазины] AS m ON z.[Код магазина]=m.[Код магазина] WHERE k.[Название] Like "*информатика*";'
Q "Книги в магазинах Саратова за 2012 год" "SELECT k.[Авторы],k.[Название],k.[Год издания],z.[Дата заказа],m.[Название магазина],m.[Город],d.[Количество] FROM (([Книги] AS k INNER JOIN [Описание заказов] AS d ON k.[Код книги]=d.[Код книги]) INNER JOIN [Заказы] AS z ON d.[Код заказа]=z.[Код заказа]) INNER JOIN [Магазины] AS m ON z.[Код магазина]=m.[Код магазина] WHERE m.[Город]='Саратов' AND z.[Дата заказа] Between #01/01/2012# And #12/31/2012#;"
Q "Магазины книги по налогам" 'SELECT DISTINCT m.[Название магазина],m.[Город] FROM (([Книги] AS k INNER JOIN [Описание заказов] AS d ON k.[Код книги]=d.[Код книги]) INNER JOIN [Заказы] AS z ON d.[Код заказа]=z.[Код заказа]) INNER JOIN [Магазины] AS m ON z.[Код магазина]=m.[Код магазина] WHERE k.[Название] Like "*налог*";'
Q "Поиск транспортной компании" "PARAMETERS [Введите город] Text (255); SELECT [Название компании],[Город] FROM [Транспортные компании] WHERE [Город]=[Введите город];"
Q "Поиск заказов по фамилии сотрудника" "PARAMETERS [Введите фамилию:] Text (255); SELECT * FROM [Список заказов по датам] WHERE [Фамилия]=[Введите фамилию:];"
Q "Поиск заказов по фамилии сотрудника за период" "PARAMETERS [Введите фамилию:] Text (255), [Введите начало интервала] DateTime, [Введите конец интервала] DateTime; SELECT [Фамилия],[Код заказа],[Дата заказа],[Название магазина],[Город] FROM [Список заказов по датам] WHERE [Фамилия]=[Введите фамилию:] AND [Дата заказа] Between [Введите начало интервала] And [Введите конец интервала];"
Q "Поиск книг по году" "PARAMETERS [Введите год издания] Short; SELECT [Авторы],[Название],[Серия],[Год издания],[Цена] FROM [Книги] WHERE [Год издания]=[Введите год издания];"
Q "Заказы определенного магазина" "PARAMETERS [Введите название магазина] Text (255); SELECT * FROM [Список заказов по датам] WHERE [Название магазина]=[Введите название магазина];"
Q "Стоимость книг в заказах" "SELECT z.[Код заказа],z.[Код магазина],m.[Название магазина],k.[Код книги],k.[Авторы],k.[Название],k.[Год издания],k.[Цена],d.[Количество],d.[Скидка],([Цена]*[Количество]-[Цена]*[Количество]*[Скидка]*0.01) AS [Стоимость] FROM (([Заказы] AS z INNER JOIN [Магазины] AS m ON z.[Код магазина]=m.[Код магазина]) INNER JOIN [Описание заказов] AS d ON z.[Код заказа]=d.[Код заказа]) INNER JOIN [Книги] AS k ON d.[Код книги]=k.[Код книги];"
Q "Общая стоимость проданных книг" "SELECT Sum([Стоимость]) AS [Общая стоимость] FROM [Стоимость книг в заказах];"
Q "Стоимость заказов" "SELECT z.[Код заказа],z.[Дата заказа],m.[Название магазина],Sum(q.[Стоимость]) AS [Стоимость заказа] FROM ([Заказы] AS z INNER JOIN [Магазины] AS m ON z.[Код магазина]=m.[Код магазина]) INNER JOIN [Стоимость книг в заказах] AS q ON z.[Код заказа]=q.[Код заказа] GROUP BY z.[Код заказа],z.[Дата заказа],m.[Название магазина] ORDER BY z.[Дата заказа];"
Q "Стоимость заказов по годам" "SELECT Year(z.[Дата заказа]) AS [Год],m.[Название магазина],Sum(q.[Стоимость]) AS [Стоимость] FROM ([Заказы] AS z INNER JOIN [Магазины] AS m ON z.[Код магазина]=m.[Код магазина]) INNER JOIN [Стоимость книг в заказах] AS q ON z.[Код заказа]=q.[Код заказа] GROUP BY Year(z.[Дата заказа]),m.[Название магазина];"
Q "Количество заказов, сделанных каждым магазином" "SELECT m.[Код магазина],m.[Название магазина],Count(z.[Код заказа]) AS [Количество заказов] FROM [Магазины] AS m LEFT JOIN [Заказы] AS z ON m.[Код магазина]=z.[Код магазина] GROUP BY m.[Код магазина],m.[Название магазина] ORDER BY m.[Код магазина];"
Q "Количество проданных книг каждого названия" "SELECT k.[Название],Sum(d.[Количество]) AS [Количество проданных книг] FROM [Книги] AS k INNER JOIN [Описание заказов] AS d ON k.[Код книги]=d.[Код книги] GROUP BY k.[Название] ORDER BY k.[Название];"
Q "Количество заказов по сотрудникам" "SELECT s.[Фамилия],s.[Имя],s.[Отчество],Count(z.[Код заказа]) AS [Количество заказов] FROM [Сотрудники] AS s LEFT JOIN [Заказы] AS z ON s.[Код сотрудника]=z.[Код сотрудника] GROUP BY s.[Фамилия],s.[Имя],s.[Отчество] ORDER BY s.[Фамилия];"
Q "Сводная стоимость книг в заказах" "TRANSFORM Sum(q.[Стоимость]) AS [Сумма стоимости] SELECT q.[Код книги],q.[Авторы],q.[Название],Sum(q.[Стоимость]) AS [Итого] FROM [Стоимость книг в заказах] AS q GROUP BY q.[Код книги],q.[Авторы],q.[Название] PIVOT q.[Название магазина];"
Q "Работа сотрудников" 'SELECT s.[Фамилия],(Format(z.[Дата заказа],"yyyy") & " Q" & DatePart("q",z.[Дата заказа])) AS [Дата заказа по кварталам],q.[Стоимость] FROM ([Сотрудники] AS s INNER JOIN [Заказы] AS z ON s.[Код сотрудника]=z.[Код сотрудника]) INNER JOIN [Стоимость книг в заказах] AS q ON z.[Код заказа]=q.[Код заказа];'
Q "Учет работы сотрудников по кварталам" 'TRANSFORM Sum(r.[Стоимость]) AS [Сумма стоимости] SELECT r.[Дата заказа по кварталам] FROM [Работа сотрудников] AS r WHERE r.[Дата заказа по кварталам] Like "*2011*" GROUP BY r.[Дата заказа по кварталам] PIVOT r.[Фамилия];'
Q "Количество заказов по магазинам и годам" "TRANSFORM Count(z.[Код заказа]) AS [Количество заказов] SELECT m.[Название магазина] FROM [Магазины] AS m INNER JOIN [Заказы] AS z ON m.[Код магазина]=z.[Код магазина] GROUP BY m.[Название магазина] PIVOT Year(z.[Дата заказа]);"

$db.TableDefs.Refresh();$db.QueryDefs.Refresh();$db.Relations.Refresh()
$log=New-Object System.Collections.Generic.List[string]
$log.Add("DATABASE="+$dbPath);$log.Add("SOURCE_XLSX="+$xlsxPath);$log.Add("DAO_VERSION="+$dao.Version);$log.Add("")
$log.Add("[TABLE_COUNTS]")
foreach($t in @("Сотрудники","Магазины","Транспортные компании","Книги","Заказы","Описание заказов")){$rs=$db.OpenRecordset("SELECT Count(*) AS C FROM [$t]");$c=$rs.Fields.Item("C").Value;$rs.Close();$log.Add($t+"="+$c);Write-Host $t $c}
$log.Add("");$log.Add("[RELATIONS]")
foreach($rn in @("Транспортные компанииЗаказы","МагазиныЗаказы","СотрудникиЗаказы","КнигиОписание заказов","ЗаказыОписание заказов")){$r=$db.Relations.Item($rn);$log.Add($rn+" : "+$r.Table+" -> "+$r.ForeignTable+" Attributes="+$r.Attributes)}
$log.Add("");$log.Add("[LOOKUPS]")
foreach($a in @(@("Сотрудники","Должность"),@("Магазины","Город"),@("Транспортные компании","Город"),@("Книги","Серия"),@("Заказы","Доставка"))){$f=Field $a[0] $a[1];$log.Add($a[0]+"."+$a[1]+" RowSourceType="+$f.Properties.Item("RowSourceType").Value+" RowSource="+$f.Properties.Item("RowSource").Value)}
$log.Add("");$log.Add("[KEY_QUERIES]")
foreach($qn in @("Стоимость книг в заказах","Стоимость заказов","Количество заказов, сделанных каждым магазином","Сводная стоимость книг в заказах","Работа сотрудников","Учет работы сотрудников по кварталам","Количество заказов по магазинам и годам")){$rs=$db.OpenRecordset("[$qn]");$cnt=0;if(-not $rs.EOF){$rs.MoveLast();$cnt=$rs.RecordCount};$rs.Close();$log.Add($qn+" rows="+$cnt);Write-Host $qn $cnt}
$db.BeginTrans()
try{$db.Execute("INSERT INTO [Описание заказов] ([Код заказа],[Код книги],[Количество],[Скидка]) VALUES (999999,999999,1,0)");$log.Add("REFERENTIAL_INTEGRITY=FAIL_INSERT_ALLOWED")}catch{$log.Add("REFERENTIAL_INTEGRITY=PASS_ORPHAN_REJECTED")}
$db.Rollback()
$log | Set-Content -Path (Join-Path $out "VALIDATION.txt") -Encoding UTF8

$sample=New-Object System.Collections.Generic.List[string]
foreach($qn in @("Стоимость книг в заказах","Стоимость заказов","Количество заказов, сделанных каждым магазином","Сводная стоимость книг в заказах","Работа сотрудников","Учет работы сотрудников по кварталам")){
 $sample.Add("===== "+$qn+" =====");$rs=$db.OpenRecordset("[$qn]");$heads=@();for($i=0;$i -lt $rs.Fields.Count;$i++){$heads += $rs.Fields.Item($i).Name};$sample.Add(($heads -join " | "));$n=0
 while(-not $rs.EOF -and $n -lt 8){$vals=@();for($i=0;$i -lt $rs.Fields.Count;$i++){$vals += [string]$rs.Fields.Item($i).Value};$sample.Add(($vals -join " | "));$rs.MoveNext();$n++};$rs.Close();$sample.Add("")
}
$sample | Set-Content -Path (Join-Path $out "QUERY_SAMPLES.txt") -Encoding UTF8
$db.Close()
Write-Host "ACCDB_CREATED" (Get-Item $dbPath).Length
Write-Host "BUILD_COMPLETE"

# final native build trigger
