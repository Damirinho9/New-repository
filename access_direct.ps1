$ErrorActionPreference="Stop"
$root=$PSScriptRoot
$out=Join-Path $root "access_direct"
New-Item -ItemType Directory -Force -Path $out | Out-Null
$db=(Get-ChildItem (Join-Path $root "access_out") -Filter *.accdb | Select-Object -First 1).FullName
if(!$db){throw "No accdb"}
$exe=(Get-ChildItem "C:\Program Files\Microsoft Office" -Filter MSACCESS.EXE -Recurse -ErrorAction SilentlyContinue | Select-Object -First 1).FullName
if(!$exe){throw "MSACCESS.EXE not found"}

Add-Type -AssemblyName System.Drawing
Add-Type -AssemblyName System.Windows.Forms
Add-Type @"
using System;
using System.Runtime.InteropServices;
public static class W {
 [StructLayout(LayoutKind.Sequential)] public struct RECT { public int Left,Top,Right,Bottom; }
 [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr hWnd, out RECT r);
 [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h);
 [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr h, int cmd);
}
"@
function GetRect([IntPtr]$h){$r=New-Object W+RECT;[W]::GetWindowRect($h,[ref]$r)|Out-Null;return [pscustomobject]@{W=$r.Right-$r.Left;H=$r.Bottom-$r.Top}}
function DeskShot([string]$name){
  Start-Sleep -Seconds 1
  $b=[Windows.Forms.Screen]::PrimaryScreen.Bounds
  $bmp=New-Object Drawing.Bitmap($b.Width,$b.Height)
  $g=[Drawing.Graphics]::FromImage($bmp)
  $g.CopyFromScreen($b.Location,[Drawing.Point]::Empty,$b.Size)
  $g.Dispose()
  $path=Join-Path $out ($name+".png")
  $bmp.Save($path,[Drawing.Imaging.ImageFormat]::Png);$bmp.Dispose()
  Write-Host "SHOT=$path $($b.Width)x$($b.Height)"
}

$vbs=@'
On Error Resume Next
Set sh = CreateObject("WScript.Shell")
mode = sh.ExpandEnvironmentStrings("%ACCESS_MODE%")
name = sh.ExpandEnvironmentStrings("%ACCESS_NAME%")
Set app = GetObject(, "Access.Application")
If Err.Number <> 0 Then
  WScript.Echo "GETOBJECT_FAIL " & Hex(Err.Number) & " " & Err.Description
  WScript.Quit 20
End If
Err.Clear
If mode = "table" Then
  app.DoCmd.OpenTable name, 0, 2
ElseIf mode = "query" Then
  app.DoCmd.OpenQuery name, 0, 2
ElseIf mode = "closeTable" Then
  app.DoCmd.Close 0, name, 2
ElseIf mode = "closeQuery" Then
  app.DoCmd.Close 1, name, 2
ElseIf mode = "relations" Then
  app.DoCmd.RunCommand 133
ElseIf mode = "quit" Then
  app.CloseCurrentDatabase
  app.Quit 2
End If
If Err.Number <> 0 Then
  WScript.Echo "ACCESS_CMD_FAIL " & mode & " " & name & " " & Hex(Err.Number) & " " & Err.Description
  WScript.Quit 21
End If
If mode <> "quit" Then
  WScript.Sleep 2200
End If
WScript.Echo "OK " & mode & " " & name
'@
$vbsPath=Join-Path $root "access_control.vbs"
Set-Content -Path $vbsPath -Value $vbs -Encoding Unicode

$argLine='"' + $db + '" /runtime'
Write-Host "ACCESS_ARGS=$argLine"
$p=Start-Process -FilePath $exe -ArgumentList $argLine -PassThru
Start-Sleep -Seconds 15
$p.Refresh()
$hw=[IntPtr]$p.MainWindowHandle
Write-Host "PID=$($p.Id) SESSION=$($p.SessionId) HWND=$hw"
$r=GetRect $hw;Write-Host "BEFORE=$($r.W)x$($r.H)"
[W]::ShowWindow($hw,9)|Out-Null;Start-Sleep -Milliseconds 800
[W]::ShowWindow($hw,3)|Out-Null;[W]::SetForegroundWindow($hw)|Out-Null;Start-Sleep -Seconds 3
$r=GetRect $hw;Write-Host "AFTER=$($r.W)x$($r.H)"
DeskShot "00_Access_после_запуска"

# Handle Office first-run dialog "First things first"
$handled=$false
try{
  Add-Type -AssemblyName UIAutomationClient
  Add-Type -AssemblyName UIAutomationTypes
  $rootEl=[Windows.Automation.AutomationElement]::RootElement
  $askCond=New-Object Windows.Automation.PropertyCondition([Windows.Automation.AutomationElement]::NameProperty,"Ask me later")
  $ask=$rootEl.FindFirst([Windows.Automation.TreeScope]::Subtree,$askCond)
  if($ask){
    $sel=$ask.GetCurrentPattern([Windows.Automation.SelectionItemPattern]::Pattern)
    $sel.Select()
    Start-Sleep -Milliseconds 500
    $accCond=New-Object Windows.Automation.PropertyCondition([Windows.Automation.AutomationElement]::NameProperty,"Accept")
    $acc=$rootEl.FindFirst([Windows.Automation.TreeScope]::Subtree,$accCond)
    if($acc){
      $inv=$acc.GetCurrentPattern([Windows.Automation.InvokePattern]::Pattern)
      $inv.Invoke()
      $handled=$true
      Write-Host "FIRST_RUN_HANDLED=UIA"
    }
  }
}catch{Write-Host "UIA_FIRST_RUN_FAIL=$($_.Exception.Message)"}
if(-not $handled){
  Add-Type @"
using System;
using System.Runtime.InteropServices;
public static class MouseX {
 [DllImport("user32.dll")] public static extern bool SetCursorPos(int X,int Y);
 [DllImport("user32.dll")] public static extern void mouse_event(uint f,uint dx,uint dy,uint data,UIntPtr extra);
 public static void Click(int x,int y){SetCursorPos(x,y);mouse_event(2,0,0,0,UIntPtr.Zero);mouse_event(4,0,0,0,UIntPtr.Zero);}
}
"@
  [MouseX]::Click(262,330);Start-Sleep -Milliseconds 600
  [MouseX]::Click(654,486);Start-Sleep -Seconds 2
  Write-Host "FIRST_RUN_HANDLED=MOUSE_FALLBACK"
}
Start-Sleep -Seconds 8
$p.Refresh()
$hw=[IntPtr]$p.MainWindowHandle
if($hw -ne [IntPtr]::Zero){[W]::ShowWindow($hw,9)|Out-Null;[W]::ShowWindow($hw,3)|Out-Null;[W]::SetForegroundWindow($hw)|Out-Null}
DeskShot "01_Access_после_FirstThingsFirst"

# Handle Microsoft Access Security Notice -> Open
$opened=$false
try{
  Add-Type -AssemblyName UIAutomationClient -ErrorAction SilentlyContinue
  Add-Type -AssemblyName UIAutomationTypes -ErrorAction SilentlyContinue
  $rootEl=[Windows.Automation.AutomationElement]::RootElement
  $nameCond=New-Object Windows.Automation.PropertyCondition([Windows.Automation.AutomationElement]::NameProperty,"Open")
  $typeCond=New-Object Windows.Automation.PropertyCondition([Windows.Automation.AutomationElement]::ControlTypeProperty,[Windows.Automation.ControlType]::Button)
  $andCond=New-Object Windows.Automation.AndCondition($nameCond,$typeCond)
  $openBtn=$rootEl.FindFirst([Windows.Automation.TreeScope]::Subtree,$andCond)
  if($openBtn){
    $inv=$openBtn.GetCurrentPattern([Windows.Automation.InvokePattern]::Pattern)
    $inv.Invoke();$opened=$true;Write-Host "SECURITY_NOTICE_OPEN=UIA"
  }
}catch{Write-Host "UIA_SECURITY_OPEN_FAIL=$($_.Exception.Message)"}
if(-not $opened){
  if(-not ("MouseX" -as [type])){
    Add-Type @"
using System;
using System.Runtime.InteropServices;
public static class MouseX {
 [DllImport("user32.dll")] public static extern bool SetCursorPos(int X,int Y);
 [DllImport("user32.dll")] public static extern void mouse_event(uint f,uint dx,uint dy,uint data,UIntPtr extra);
 public static void Click(int x,int y){SetCursorPos(x,y);mouse_event(2,0,0,0,UIntPtr.Zero);mouse_event(4,0,0,0,UIntPtr.Zero);}
}
"@
  }
  [MouseX]::Click(541,485);Write-Host "SECURITY_NOTICE_OPEN=MOUSE_FALLBACK"
}
Start-Sleep -Seconds 10
$p.Refresh();$hw=[IntPtr]$p.MainWindowHandle
if($hw -ne [IntPtr]::Zero){[W]::ShowWindow($hw,9)|Out-Null;[W]::ShowWindow($hw,3)|Out-Null;[W]::SetForegroundWindow($hw)|Out-Null}
DeskShot "02_Access_после_SecurityOpen"

function AccessCmd([string]$mode,[string]$name=""){
  $env:ACCESS_MODE=$mode
  $env:ACCESS_NAME=$name
  $proc=Start-Process -FilePath "cscript.exe" -ArgumentList @("//nologo",$vbsPath) -PassThru
  if(-not $proc.WaitForExit(15000)){
    Write-Host "CSCRIPT_TIMEOUT mode=$mode name=$name"
    DeskShot ("98_TIMEOUT_"+($mode -replace '[^A-Za-z0-9]','_'))
    Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue
    throw "Access VBScript timeout: $mode $name"
  }
  $ec=$proc.ExitCode
  Write-Host "CSCRIPT_EXIT=$ec mode=$mode name=$name"
  if($ec -ne 0){
    DeskShot ("97_ERROR_"+($mode -replace '[^A-Za-z0-9]','_'))
    throw "Access VBScript command failed: $mode $name"
  }
  $p.Refresh();$script:hw=[IntPtr]$p.MainWindowHandle
  if($script:hw -ne [IntPtr]::Zero){[W]::ShowWindow($script:hw,9)|Out-Null;[W]::ShowWindow($script:hw,3)|Out-Null;[W]::SetForegroundWindow($script:hw)|Out-Null}
  Start-Sleep -Seconds 1
}

DeskShot "03_Access_база_загружена"

foreach($x in @(
 @("Книги","10_Таблица_Книги"),
 @("Магазины","11_Таблица_Магазины"),
 @("Сотрудники","12_Таблица_Сотрудники"),
 @("Транспортные компании","13_Таблица_Транспортные_компании"),
 @("Заказы","14_Таблица_Заказы"),
 @("Описание заказов","15_Таблица_Описание_заказов")
)){
 AccessCmd "table" $x[0];DeskShot $x[1];AccessCmd "closeTable" $x[0]
}

foreach($x in @(
 @("Стоимость книг в заказах","20_Запрос_Стоимость_книг_в_заказах"),
 @("Стоимость заказов","21_Запрос_Стоимость_заказов"),
 @("Количество заказов, сделанных каждым магазином","22_Запрос_Количество_заказов"),
 @("Сводная стоимость книг в заказах","23_Запрос_Сводная_стоимость"),
 @("Работа сотрудников","24_Запрос_Работа_сотрудников"),
 @("Учет работы сотрудников по кварталам","25_Запрос_Учет_по_кварталам")
)){
 AccessCmd "query" $x[0];DeskShot $x[1];AccessCmd "closeQuery" $x[0]
}

try{AccessCmd "quit"}catch{Stop-Process -Id $p.Id -Force -ErrorAction SilentlyContinue}
Write-Host "NATIVE_ACCESS_GUI_CAPTURE_COMPLETE"
