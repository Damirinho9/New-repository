import os, time, pathlib, ctypes, threading
from PIL import ImageGrab
import pythoncom
import win32com.client
from win32com.client import gencache, constants
import win32gui, win32con
import pyautogui

ROOT=pathlib.Path.cwd()
OUT=ROOT/"screens"
OUT.mkdir(exist_ok=True)
ERRDOC=ROOT/"PR13_1_source.docx"
FINALDOC=ROOT/"final_input"/"PR13_2.doc"

def save_shot(name):
    time.sleep(1.0)
    img=ImageGrab.grab(all_screens=True)
    img.save(OUT/name)
    print("SHOT", name, img.size, flush=True)

def focus_word(word):
    try:
        hwnd=int(word.ActiveWindow.Hwnd)
        win32gui.ShowWindow(hwnd, win32con.SW_MAXIMIZE)
        time.sleep(0.4)
        try: win32gui.SetForegroundWindow(hwnd)
        except Exception: pass
        time.sleep(0.6)
        return hwnd
    except Exception as e:
        print("focus_word error", repr(e), flush=True)
        return 0

def dismiss():
    pyautogui.press("esc")
    time.sleep(0.8)

def dismiss_first_run_privacy():
    time.sleep(1.0)
    # Fixed hosted desktop is 1024x768. This is the native "Закрыть" button
    # in the Office privacy first-run modal.
    pyautogui.click(916, 598)
    time.sleep(1.4)
    pyautogui.press("esc")
    time.sleep(0.8)

def com_retry(fn, attempts=20, pause=0.3):
    last=None
    for _ in range(attempts):
        try: return fn()
        except Exception as e:
            last=e
            time.sleep(pause)
    raise last

def dialog_worker(dialog_id, kwargs):
    pythoncom.CoInitialize()
    try:
        app=win32com.client.GetActiveObject("Word.Application")
        dlg=app.Dialogs(dialog_id)
        for k,v in kwargs.items():
            try: setattr(dlg,k,v)
            except Exception as e: print("DIALOG_SET_FAIL",k,repr(e),flush=True)
        print("DIALOG_SHOW",dialog_id,kwargs,flush=True)
        dlg.Show()
        print("DIALOG_CLOSED",dialog_id,flush=True)
    except Exception as e:
        print("DIALOG_FAIL",dialog_id,repr(e),flush=True)
    finally:
        pythoncom.CoUninitialize()

def capture_dialog(word, dialog_id, filename, kwargs=None):
    kwargs=kwargs or {}
    focus_word(word)
    t=threading.Thread(target=dialog_worker,args=(dialog_id,kwargs),daemon=True)
    t.start()
    time.sleep(2.0)
    save_shot(filename)
    pyautogui.press("esc")
    time.sleep(1.0)
    t.join(timeout=4.0)

def ensure_autocorrect(word):
    ac=word.AutoCorrect
    ac.ReplaceText=True
    for name,value in [("ПРимер","Пример"),("дата16","16.11.2026")]:
        try:
            e=ac.Entries.Item(name)
            if str(e.Value)!=value:
                e.Delete()
                ac.Entries.Add(Name=name,Value=value)
        except Exception:
            ac.Entries.Add(Name=name,Value=value)

def ensure_autotext(word):
    temp=word.Documents.Add()
    try:
        for value in ["16.11.2026","Пятница","Апрель"]:
            found=False
            try:
                word.Templates.LoadBuildingBlocks()
            except Exception:
                pass
            for i in range(1,word.Templates.Count+1):
                try:
                    if word.Templates.Item(i).AutoTextEntries.Item(value):
                        found=True
                        break
                except Exception:
                    pass
            if not found:
                temp.Content.Text=value
                rng=temp.Range(0,len(value))
                word.NormalTemplate.AutoTextEntries.Add(Name=value,Range=rng)
    finally:
        temp.Close(0)

# Minimize runner console so it never covers Word.
try:
    kernel32=ctypes.WinDLL("kernel32")
    user32=ctypes.WinDLL("user32")
    hwnd_console=kernel32.GetConsoleWindow()
    if hwnd_console:
        user32.ShowWindow(hwnd_console,6)
except Exception as e:
    print("console minimize failed",repr(e),flush=True)

pythoncom.CoInitialize()
word=gencache.EnsureDispatch("Word.Application")
word.Visible=True
word.DisplayAlerts=0
word.Options.CheckSpellingAsYouType=True
word.Options.CheckGrammarAsYouType=True
word.Options.CheckGrammarWithSpelling=True

doc=None
try:
    doc=word.Documents.Open(str(ERRDOC),False,True)
    doc.Content.LanguageID=1049
    doc.ShowSpellingErrors=True
    doc.ShowGrammaticalErrors=True
    doc.Activate()
    focus_word(word)
    dismiss_first_run_privacy()
    focus_word(word)
    try:
        word.ActiveWindow.View.Type=3
        word.ActiveWindow.View.Zoom.Percentage=100
    except Exception: pass

    # 1. Red underlines in the actual error document.
    rng=com_retry(lambda: doc.Content.Duplicate)
    find=rng.Find
    find.Text="древнейшых"
    find.Forward=True
    if find.Execute():
        rng.Select()
        word.Selection.Collapse(0)
    time.sleep(4.0)
    save_shot("01_Проверка_правописания_красные_подчеркивания.png")

    # 2. Native context menu with spelling correction suggestions.
    rng=com_retry(lambda: doc.Content.Duplicate)
    find=rng.Find
    find.Text="древнейшых"
    find.Forward=True
    if find.Execute(): rng.Select()
    focus_word(word)
    pyautogui.hotkey("shift","f10")
    time.sleep(1.8)
    save_shot("02_Контекстное_меню_исправления.png")
    dismiss()

    # Prepare settings used in this practical work on this Word instance.
    com_retry(lambda: ensure_autocorrect(word))
    com_retry(lambda: ensure_autotext(word))

    # 3. AutoCorrect dialog with the work's explicit replacement.
    capture_dialog(
        word,
        constants.wdDialogToolsAutoCorrect,
        "03_Настройки_автозамены.png",
        {"Replace":"ПРимер","With":"Пример","ReplaceText":1}
    )

    # 4. Hyphenation dialog, with automatic hyphenation enabled in the document.
    doc.AutoHyphenation=True
    capture_dialog(
        word,
        constants.wdDialogToolsHyphenation,
        "04_Автоматические_переносы.png",
        {"AutoHyphenation":1,"HyphenateCaps":0}
    )

    # 5. AutoText tab of the native AutoCorrect/AutoManager dialog.
    capture_dialog(
        word,
        constants.wdDialogToolsAutoManager,
        "05_Автотекст.png",
        {"Tab":constants.wdDialogToolsAutoManagerTabAutoText}
    )

    doc.Close(0)
    doc=None

    # 6. Final PR13_2.doc with the date inserted via configured AutoCorrect.
    doc=word.Documents.Open(str(FINALDOC),False,True)
    doc.Content.LanguageID=1049
    doc.Activate()
    focus_word(word)
    try:
        word.ActiveWindow.View.Type=3
        word.ActiveWindow.View.Zoom.Percentage=100
    except Exception: pass
    end=doc.Content.End-1
    doc.Range(max(0,end-30),end).Select()
    word.Selection.Collapse(0)
    time.sleep(2.0)
    save_shot("06_ПР13_2_дата_16.11.2026.png")

finally:
    if doc is not None:
        try: doc.Close(0)
        except Exception: pass
    try: word.Quit()
    except Exception: pass
    pythoncom.CoUninitialize()

print("DONE",sorted(p.name for p in OUT.glob("*.png")),flush=True)
