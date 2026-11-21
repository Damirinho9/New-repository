$ErrorActionPreference="Stop"
$db=$args[0]
$out=$args[1]
New-Item -ItemType Directory -Force -Path $out | Out-Null

Add-Type -AssemblyName System.Drawing
Add-Type @"
using System;
using System.Runtime.InteropServices;
public static class WinShot {
 [StructLayout(LayoutKind.Sequential)] public struct RECT { public int Left,Top,Right,Bottom; }
 [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr hWnd, out RECT r);
 [DllImport("user32.dll")] public static extern bool PrintWindow(IntPtr hwnd, IntPtr hdcBlt, uint nFlags);
 [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr hWnd);
 [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr hWnd, int cmd);
}
"@

function Shot($app,[string]$name){
  $hw=[IntPtr]$app.hWndAccessApp
  [WinShot]::ShowWindow($hw,3)|Out-Null
  [WinShot]::SetForegroundWindow($hw)|Out-Null
  Start-Sleep -Seconds 2
  $r=New-Object WinShot+RECT
  [WinShot]::GetWindowRect($hw,[ref]$r)|Out-Null
  $w=$r.Right-$r.Left;$h=$r.Bottom-$r.Top
  if($w -lt 600 -or $h -lt 400){throw "Bad Access window $w x $h"}
  $bmp=New-Object Drawing.Bitmap($w,$h)
  $g=[Drawing.Graphics]::FromImage($bmp);$dc=$g.GetHdc()
  [WinShot]::PrintWindow($hw,$dc,2)|Out-Null
  $g.ReleaseHdc($dc);$g.Dispose()
  $p=Join-Path $out ($name+".png")
  $bmp.Save($p,[Drawing.Imaging.ImageFormat]::Png);$bmp.Dispose()
  Write-Host "SHOT=$p"
}

$app=New-Object -ComObject Access.Application
$app.OpenCurrentDatabase($db)
$app.Visible=$true
Start-Sleep -Seconds 4
Write-Host "ACCESS_VERSION=$($app.Version) HWND=$($app.hWndAccessApp)"

# Initial real Access window / navigation context
Shot $app "00_Access_database"

foreach($x in @(
 @("Книги","01_Таблица_Книги"),
 @("Магазины","02_Таблица_Магазины"),
 @("Сотрудники","03_Таблица_Сотрудники"),
 @("Транспортные компании","04_Таблица_Транспортные_компании"),
 @("Заказы","05_Таблица_Заказы"),
 @("Описание заказов","06_Таблица_Описание_заказов")
)){
  $app.DoCmd.OpenTable($x[0],0,0); Start-Sleep -Seconds 2; Shot $app $x[1]; $app.DoCmd.Close(0,$x[0],2)
}

foreach($x in @(
 @("Стоимость книг в заказах","10_Запрос_Стоимость_книг_в_заказах"),
 @("Стоимость заказов","11_Запрос_Стоимость_заказов"),
 @("Количество заказов, сделанных каждым магазином","12_Запрос_Количество_заказов"),
 @("Сводная стоимость книг в заказах","13_Запрос_Сводная_стоимость"),
 @("Работа сотрудников","14_Запрос_Работа_сотрудников"),
 @("Учет работы сотрудников по кварталам","15_Запрос_Учет_по_кварталам")
)){
  $app.DoCmd.OpenQuery($x[0],0,0); Start-Sleep -Seconds 2; Shot $app $x[1]; $app.DoCmd.Close(1,$x[0],2)
}

# Try Relationships window in Access
try{
  $app.DoCmd.RunCommand(133) # acCmdRelationships
  Start-Sleep -Seconds 3
  Shot $app "20_Схема_данных_Access"
}catch{Write-Host "RELATIONSHIPS_UI_FAIL=$($_.Exception.Message)"}

$app.CloseCurrentDatabase();$app.Quit(2)
[Runtime.InteropServices.Marshal]::ReleaseComObject($app)|Out-Null
Write-Host "INTERACTIVE_ACCESS_CAPTURE_COMPLETE"
