$ErrorActionPreference="Stop"
$root=$PSScriptRoot
$out=Join-Path $root "access_direct"
New-Item -ItemType Directory -Force -Path $out | Out-Null
$db=(Get-ChildItem (Join-Path $root "access_out") -Filter *.accdb | Select-Object -First 1).FullName
if(!$db){throw "No accdb"}
$exe=(Get-ChildItem "C:\Program Files\Microsoft Office" -Filter MSACCESS.EXE -Recurse -ErrorAction SilentlyContinue | Select-Object -First 1).FullName
if(!$exe){throw "MSACCESS.EXE not found"}

Add-Type -AssemblyName System.Drawing
Add-Type @"
using System;
using System.Runtime.InteropServices;
public static class W {
 [StructLayout(LayoutKind.Sequential)] public struct RECT { public int Left,Top,Right,Bottom; }
 [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr hWnd, out RECT r);
 [DllImport("user32.dll")] public static extern bool PrintWindow(IntPtr h, IntPtr dc, uint f);
 [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h);
 [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr h, int cmd);
}
"@
function Rect([IntPtr]$h){
 $r=New-Object W+RECT;[W]::GetWindowRect($h,[ref]$r)|Out-Null
 return [pscustomobject]@{W=$r.Right-$r.Left;H=$r.Bottom-$r.Top;L=$r.Left;T=$r.Top}
}
function Shot([IntPtr]$h,[string]$name){
 [W]::ShowWindow($h,9)|Out-Null;Start-Sleep -Milliseconds 500
 [W]::ShowWindow($h,3)|Out-Null;[W]::SetForegroundWindow($h)|Out-Null;Start-Sleep -Seconds 2
 $r=Rect $h;Write-Host "CAPTURE $name RECT=$($r.W)x$($r.H)"
 if($r.W -lt 600 -or $r.H -lt 400){throw "Bad dimensions $($r.W)x$($r.H)"}
 $bmp=New-Object Drawing.Bitmap($r.W,$r.H)
 $g=[Drawing.Graphics]::FromImage($bmp);$dc=$g.GetHdc();[W]::PrintWindow($h,$dc,2)|Out-Null;$g.ReleaseHdc($dc);$g.Dispose()
 $path=Join-Path $out ($name+".png");$bmp.Save($path,[Drawing.Imaging.ImageFormat]::Png);$bmp.Dispose()
 Write-Host "SHOT=$path"
}

$p=Start-Process -FilePath $exe -ArgumentList @($db,"/runtime") -PassThru
Start-Sleep -Seconds 15
$p.Refresh()
$hw=[IntPtr]$p.MainWindowHandle
Write-Host "PID=$($p.Id) SESSION=$($p.SessionId) HWND=$hw BEFORE=$((Rect $hw).W)x$((Rect $hw).H)"
[W]::ShowWindow($hw,9)|Out-Null;Start-Sleep -Seconds 1
[W]::ShowWindow($hw,3)|Out-Null;[W]::SetForegroundWindow($hw)|Out-Null;Start-Sleep -Seconds 3
$r=Rect $hw;Write-Host "AFTER_RESTORE=$($r.W)x$($r.H)"
Shot $hw "00_Access_главное_окно"

$app=$null
try{
  $method=[Runtime.InteropServices.Marshal].GetMethod("GetActiveObject",[Reflection.BindingFlags]"Public,Static")
  if($method){$app=$method.Invoke($null,@("Access.Application"));Write-Host "ATTACH=Marshal.GetActiveObject"}
}catch{Write-Host "MARSHAL_ATTACH_FAIL=$($_.Exception.GetBaseException().Message)"}
if(!$app){
 try{
  Add-Type -AssemblyName Microsoft.VisualBasic
  $app=[Microsoft.VisualBasic.Interaction]::GetObject($null,"Access.Application")
  Write-Host "ATTACH=VB.GetObject"
 }catch{Write-Host "VB_ATTACH_FAIL=$($_.Exception.GetBaseException().Message)"}
}
if(!$app){
 try{$app=New-Object -ComObject Access.Application;Write-Host "ATTACH=New-ComObject"}catch{Write-Host "NEW_COM_FAIL=$($_.Exception.GetBaseException().Message)"}
}
if(!$app){throw "Could not attach/create Access automation object"}

try{
 if(-not $app.CurrentProject.FullName){$app.OpenCurrentDatabase($db)}
}catch{try{$app.OpenCurrentDatabase($db)}catch{}}
$app.Visible=$true
try{$app.DoCmd.Maximize()}catch{}
$hw=[IntPtr]$app.hWndAccessApp
Write-Host "ACCESS_VERSION=$($app.Version) APP_HWND=$hw"
Shot $hw "01_Access_база"

foreach($x in @(
 @("Книги","02_Таблица_Книги"),
 @("Магазины","03_Таблица_Магазины"),
 @("Заказы","04_Таблица_Заказы"),
 @("Описание заказов","05_Таблица_Описание_заказов")
)){
 $app.DoCmd.OpenTable($x[0],0,0);try{$app.DoCmd.Maximize()}catch{};Start-Sleep -Seconds 2;Shot $hw $x[1];$app.DoCmd.Close(0,$x[0],2)
}
foreach($x in @(
 @("Стоимость книг в заказах","10_Запрос_Стоимость_книг"),
 @("Стоимость заказов","11_Запрос_Стоимость_заказов"),
 @("Количество заказов, сделанных каждым магазином","12_Запрос_Количество_заказов"),
 @("Сводная стоимость книг в заказах","13_Запрос_Сводная_стоимость"),
 @("Работа сотрудников","14_Запрос_Работа_сотрудников"),
 @("Учет работы сотрудников по кварталам","15_Запрос_Учет_по_кварталам")
)){
 $app.DoCmd.OpenQuery($x[0],0,0);try{$app.DoCmd.Maximize()}catch{};Start-Sleep -Seconds 2;Shot $hw $x[1];$app.DoCmd.Close(1,$x[0],2)
}
try{$app.DoCmd.RunCommand(133);Start-Sleep -Seconds 3;Shot $hw "20_Схема_данных"}catch{Write-Host "RELATIONSHIPS_FAIL=$($_.Exception.GetBaseException().Message)"}
try{$app.CloseCurrentDatabase()}catch{}
try{$app.Quit(2)}catch{}
Write-Host "NATIVE_ACCESS_GUI_CAPTURE_COMPLETE"
