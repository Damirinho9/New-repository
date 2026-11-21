$ErrorActionPreference="Stop"
$root=$PSScriptRoot
$out=Join-Path $root "access_direct"
New-Item -ItemType Directory -Force -Path $out | Out-Null
$db=(Get-ChildItem (Join-Path $root "access_out") -Filter *.accdb | Select-Object -First 1).FullName
if(!$db){throw "No accdb"}

$exe=(Get-ChildItem "C:\Program Files\Microsoft Office" -Filter MSACCESS.EXE -Recurse -ErrorAction SilentlyContinue | Select-Object -First 1).FullName
if(!$exe){$exe=(Get-ChildItem "C:\Program Files (x86)\Microsoft Office" -Filter MSACCESS.EXE -Recurse -ErrorAction SilentlyContinue | Select-Object -First 1).FullName}
if(!$exe){throw "MSACCESS.EXE not found"}
Write-Host "EXE=$exe"
Write-Host "DB=$db"
$p=Start-Process -FilePath $exe -ArgumentList ('"'+$db+'" /runtime') -PassThru
Start-Sleep -Seconds 20
$p.Refresh()
Write-Host "PID=$($p.Id) EXITED=$($p.HasExited) HWND=$($p.MainWindowHandle) TITLE=$($p.MainWindowTitle)"
Get-Process MSACCESS -ErrorAction SilentlyContinue | Format-List Id,SessionId,MainWindowHandle,MainWindowTitle,Responding

Add-Type -AssemblyName System.Drawing
Add-Type -AssemblyName System.Windows.Forms
Add-Type @"
using System;
using System.Runtime.InteropServices;
public static class W {
 [StructLayout(LayoutKind.Sequential)] public struct RECT { public int Left,Top,Right,Bottom; }
 [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr h, out RECT r);
 [DllImport("user32.dll")] public static extern bool PrintWindow(IntPtr h, IntPtr dc, uint f);
 [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h);
}
"@
$gp=Get-Process MSACCESS -ErrorAction SilentlyContinue | Where-Object {$_.MainWindowHandle -ne 0} | Select-Object -First 1
if($gp){
 $h=[IntPtr]$gp.MainWindowHandle
 [W]::SetForegroundWindow($h)|Out-Null
 Start-Sleep -Seconds 2
 $r=New-Object W+RECT; [W]::GetWindowRect($h,[ref]$r)|Out-Null
 $w=$r.Right-$r.Left;$hh=$r.Bottom-$r.Top
 Write-Host "RECT=$w x $hh"
 if($w -gt 300 -and $hh -gt 200){
   $bmp=New-Object Drawing.Bitmap($w,$hh)
   $g=[Drawing.Graphics]::FromImage($bmp);$dc=$g.GetHdc();[W]::PrintWindow($h,$dc,2)|Out-Null;$g.ReleaseHdc($dc);$g.Dispose()
   $path=Join-Path $out "access_window.png";$bmp.Save($path,[Drawing.Imaging.ImageFormat]::Png);$bmp.Dispose()
   Write-Host "SCREEN=$path"
 }
}
tasklist /v /fi "imagename eq msaccess.exe"

# trigger direct gui
