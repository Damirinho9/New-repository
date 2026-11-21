$ErrorActionPreference="Stop"
$root=$PSScriptRoot
$out=Join-Path $root "access_screens"
New-Item -ItemType Directory -Force -Path $out | Out-Null
$db=Join-Path $root "access_out\LR2-3_P поставки книг.accdb"
if(!(Test-Path $db)){throw "Database not found: $db"}

Write-Host "Trying Access.Application..."
$app=New-Object -ComObject Access.Application
$app.OpenCurrentDatabase($db)
$app.Visible=$true
Start-Sleep -Seconds 3
Write-Host ("ACCESS_VERSION="+$app.Version+" HWND="+$app.hWndAccessApp)

Add-Type -AssemblyName System.Drawing
Add-Type @"
using System;
using System.Runtime.InteropServices;
public static class WinCap {
 [StructLayout(LayoutKind.Sequential)] public struct RECT { public int Left,Top,Right,Bottom; }
 [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr hWnd, out RECT lpRect);
 [DllImport("user32.dll")] public static extern bool PrintWindow(IntPtr hwnd, IntPtr hdcBlt, uint nFlags);
 [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr hWnd);
}
"@

function Capture([string]$name){
  $hw=[IntPtr]$app.hWndAccessApp
  [WinCap]::SetForegroundWindow($hw) | Out-Null
  Start-Sleep -Milliseconds 800
  $r=New-Object WinCap+RECT
  [WinCap]::GetWindowRect($hw,[ref]$r) | Out-Null
  $w=$r.Right-$r.Left; $h=$r.Bottom-$r.Top
  Write-Host ("Capture "+$name+" "+$w+"x"+$h)
  if($w -lt 400 -or $h -lt 300){throw "Bad Access window dimensions"}
  $bmp=New-Object System.Drawing.Bitmap($w,$h)
  $g=[System.Drawing.Graphics]::FromImage($bmp)
  $hdc=$g.GetHdc()
  [WinCap]::PrintWindow($hw,$hdc,2) | Out-Null
  $g.ReleaseHdc($hdc); $g.Dispose()
  $path=Join-Path $out ($name+".png")
  $bmp.Save($path,[System.Drawing.Imaging.ImageFormat]::Png); $bmp.Dispose()
  Write-Host ("SAVED="+$path)
}

$app.DoCmd.OpenTable("Книги",0,0); Start-Sleep -Seconds 2; Capture "01_Книги"
$app.DoCmd.Close(0,"Книги",2)
$app.DoCmd.OpenTable("Магазины",0,0); Start-Sleep -Seconds 2; Capture "02_Магазины"
$app.DoCmd.Close(0,"Магазины",2)
$app.DoCmd.OpenTable("Заказы",0,0); Start-Sleep -Seconds 2; Capture "03_Заказы"
$app.DoCmd.Close(0,"Заказы",2)

foreach($pair in @(
  @("Стоимость книг в заказах","04_Стоимость_книг"),
  @("Стоимость заказов","05_Стоимость_заказов"),
  @("Количество заказов, сделанных каждым магазином","06_Количество_заказов"),
  @("Сводная стоимость книг в заказах","07_Сводная_стоимость"),
  @("Учет работы сотрудников по кварталам","08_Учет_по_кварталам")
)){
  $app.DoCmd.OpenQuery($pair[0],0,0); Start-Sleep -Seconds 2; Capture $pair[1]; $app.DoCmd.Close(1,$pair[0],2)
}

$app.CloseCurrentDatabase()
$app.Quit(2)
[Runtime.InteropServices.Marshal]::ReleaseComObject($app) | Out-Null
Write-Host "ACCESS_SCREENSHOTS_COMPLETE"
