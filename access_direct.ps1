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
using System.Text;
using System.Runtime.InteropServices;
public static class W {
 public delegate bool EnumWindowsProc(IntPtr hWnd, IntPtr lParam);
 [StructLayout(LayoutKind.Sequential)] public struct RECT { public int Left,Top,Right,Bottom; }
 [DllImport("user32.dll")] public static extern bool EnumWindows(EnumWindowsProc cb, IntPtr lParam);
 [DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr hWnd, out uint pid);
 [DllImport("user32.dll")] public static extern bool IsWindowVisible(IntPtr hWnd);
 [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr hWnd, out RECT r);
 [DllImport("user32.dll", CharSet=CharSet.Unicode)] public static extern int GetWindowText(IntPtr hWnd, StringBuilder sb, int n);
 [DllImport("user32.dll")] public static extern bool PrintWindow(IntPtr h, IntPtr dc, uint f);
 [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h);
 [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr h, int cmd);
}
"@

function WindowInfo([int]$procId){
  $list=New-Object System.Collections.Generic.List[object]
  $cb=[W+EnumWindowsProc]{
    param($h,$l)
    [uint32]$wpid=0;[W]::GetWindowThreadProcessId($h,[ref]$wpid)|Out-Null
    if($wpid -eq $procId){
      $r=New-Object W+RECT;[W]::GetWindowRect($h,[ref]$r)|Out-Null
      $sb=New-Object Text.StringBuilder 512;[W]::GetWindowText($h,$sb,$sb.Capacity)|Out-Null
      $script:list.Add([pscustomobject]@{Handle=$h.ToInt64();Visible=[W]::IsWindowVisible($h);W=$r.Right-$r.Left;H=$r.Bottom-$r.Top;Title=$sb.ToString()})
    }
    return $true
  }
  [W]::EnumWindows($cb,[IntPtr]::Zero)|Out-Null
  return $list
}
function ShotHandle([IntPtr]$h,[string]$name){
  [W]::ShowWindow($h,3)|Out-Null
  [W]::SetForegroundWindow($h)|Out-Null
  Start-Sleep -Seconds 2
  $r=New-Object W+RECT;[W]::GetWindowRect($h,[ref]$r)|Out-Null
  $w=$r.Right-$r.Left;$hh=$r.Bottom-$r.Top
  Write-Host "CAPTURE $name HANDLE=$h RECT=$w x $hh"
  if($w -lt 600 -or $hh -lt 400){throw "Bad dimensions $w x $hh"}
  $bmp=New-Object Drawing.Bitmap($w,$hh)
  $g=[Drawing.Graphics]::FromImage($bmp);$dc=$g.GetHdc();[W]::PrintWindow($h,$dc,2)|Out-Null;$g.ReleaseHdc($dc);$g.Dispose()
  $path=Join-Path $out ($name+".png");$bmp.Save($path,[Drawing.Imaging.ImageFormat]::Png);$bmp.Dispose()
  Write-Host "SHOT=$path"
}

Write-Host "EXE=$exe"
$p=Start-Process -FilePath $exe -ArgumentList @($db,"/runtime") -PassThru
Start-Sleep -Seconds 15
$p.Refresh()
Write-Host "PID=$($p.Id) SESSION=$($p.SessionId) HWND=$($p.MainWindowHandle)"
WindowInfo $p.Id | Format-Table -AutoSize

# Restore every top-level Access window owned by this process
foreach($wi in (WindowInfo $p.Id)){[W]::ShowWindow([IntPtr]$wi.Handle,3)|Out-Null}
Start-Sleep -Seconds 3
Write-Host "WINDOWS_AFTER_RESTORE"
WindowInfo $p.Id | Format-Table -AutoSize

$app=$null
try{
  $m=[Runtime.InteropServices.Marshal].GetMethod("GetActiveObject",[Reflection.BindingFlags]"Public,Static")
  if($m){$app=$m.Invoke($null,@("Access.Application"));Write-Host "ATTACH=Marshal.GetActiveObject"}
}catch{Write-Host "MARSHAL_ATTACH_FAIL=$($_.Exception.Message)"}
if(!$app){
  try{
    Add-Type -AssemblyName Microsoft.VisualBasic
    $app=[Microsoft.VisualBasic.Interaction]::GetObject($null,"Access.Application")
    Write-Host "ATTACH=VB.GetObject"
  }catch{Write-Host "VB_ATTACH_FAIL=$($_.Exception.Message)"}
}
if(!$app){throw "Could not attach to running Access"}
Write-Host "ACCESS_VERSION=$($app.Version) APP_HWND=$($app.hWndAccessApp)"
$app.Visible=$true
try{$app.DoCmd.Maximize()}catch{Write-Host "MAXIMIZE_FAIL=$($_.Exception.Message)"}
Start-Sleep -Seconds 3

$hw=[IntPtr]$app.hWndAccessApp
ShotHandle $hw "00_Access_главное_окно"

foreach($x in @(
 @("Книги","01_Книги"),
 @("Магазины","02_Магазины"),
 @("Сотрудники","03_Сотрудники"),
 @("Заказы","04_Заказы")
)){
  $app.DoCmd.OpenTable($x[0],0,0);$app.DoCmd.Maximize();Start-Sleep -Seconds 2;ShotHandle $hw $x[1];$app.DoCmd.Close(0,$x[0],2)
}

foreach($x in @(
 @("Стоимость книг в заказах","10_Стоимость_книг_в_заказах"),
 @("Стоимость заказов","11_Стоимость_заказов"),
 @("Количество заказов, сделанных каждым магазином","12_Количество_заказов"),
 @("Сводная стоимость книг в заказах","13_Сводная_стоимость"),
 @("Работа сотрудников","14_Работа_сотрудников"),
 @("Учет работы сотрудников по кварталам","15_Учет_по_кварталам")
)){
  $app.DoCmd.OpenQuery($x[0],0,0);$app.DoCmd.Maximize();Start-Sleep -Seconds 2;ShotHandle $hw $x[1];$app.DoCmd.Close(1,$x[0],2)
}

try{
 $app.DoCmd.RunCommand(133);Start-Sleep -Seconds 3;ShotHandle $hw "20_Схема_данных"
}catch{Write-Host "RELATIONSHIPS_FAIL=$($_.Exception.Message)"}

try{$app.CloseCurrentDatabase()}catch{}
try{$app.Quit(2)}catch{}
Write-Host "NATIVE_ACCESS_GUI_CAPTURE_COMPLETE"
