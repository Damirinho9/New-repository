import os, time, pathlib, ctypes, json
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
    time.sleep(1.2)
    img=ImageGrab.grab(all_screens=True)
    img.save(OUT/name)
    print("SHOT", name, img.size, flush=True)

def focus_word(word):
    try:
        hwnd=int(word.ActiveWindow.Hwnd)
        win32gui.ShowWindow(hwnd, win32con.SW_MAXIMIZE)
        time.sleep(0.5)
        try:
            win32gui.SetForegroundWindow(hwnd)
        except Exception:
            pass
        time.sleep(0.8)
        return hwnd
    except Exception as e:
        print("focus_word error", repr(e), flush=True)
        return 0

def dismiss():
    pyautogui.press("esc")
    time.sleep(0.8)

def execute_candidates(word, candidates):
    for cid in candidates:
        try:
            enabled = word.CommandBars.GetEnabledMso(cid)
            print("MSO", cid, "enabled", enabled, flush=True)
            if enabled:
                word.CommandBars.ExecuteMso(cid)
                time.sleep(1.5)
                return cid
        except Exception as e:
            print("MSO_FAIL", cid, repr(e), flush=True)
    return None

# Minimize the runner console window so it cannot cover Word.
try:
    kernel32=ctypes.WinDLL("kernel32")
    user32=ctypes.WinDLL("user32")
    hwnd_console=kernel32.GetConsoleWindow()
    if hwnd_console:
        user32.ShowWindow(hwnd_console, 6)  # SW_MINIMIZE
except Exception as e:
    print("console minimize failed", repr(e), flush=True)

pythoncom.CoInitialize()
word=gencache.EnsureDispatch("Word.Application")
word.Visible=True
word.DisplayAlerts=0
word.Options.CheckSpellingAsYouType=True
word.Options.CheckGrammarAsYouType=True
word.Options.CheckGrammarWithSpelling=True

doc=None
try:
    # 1. Source document with visible spelling errors.
    doc=word.Documents.Open(str(ERRDOC),False,True)
    doc.Content.LanguageID=1049
    doc.ShowSpellingErrors=True
    doc.ShowGrammaticalErrors=True
    doc.Activate()
    focus_word(word)
    try:
        word.ActiveWindow.View.Type=3  # Print layout
        word.ActiveWindow.View.Zoom.Percentage=100
    except Exception:
        pass
    # Go to a controlled misspelling near the beginning.
    rng=doc.Content.Duplicate
    find=rng.Find
    find.Text="древнейшых"
    find.Forward=True
    if find.Execute():
        rng.Select()
        word.Selection.Collapse(0)
    time.sleep(4)
    save_shot("01_Проверка_правописания_красные_подчеркивания.png")

    # 2. Context menu for a misspelled word.
    rng=doc.Content.Duplicate
    find=rng.Find
    find.Text="древнейшых"
    find.Forward=True
    if find.Execute():
        rng.Select()
    focus_word(word)
    pyautogui.hotkey("shift","f10")
    time.sleep(1.7)
    save_shot("02_Контекстное_меню_исправления.png")
    dismiss()

    # 3. Native AutoCorrect options dialog.
    focus_word(word)
    used=execute_candidates(word,[
        "AutoCorrectOptions",
        "AutoCorrectOptionsDialog",
        "FileOptionsProofing"
    ])
    print("AUTOCORRECT_USED", used, flush=True)
    save_shot("03_Настройки_автозамены.png")
    dismiss()

    # 4. Native hyphenation dialog/menu.
    focus_word(word)
    used=execute_candidates(word,[
        "HyphenationOptions",
        "HyphenationDialog",
        "HyphenationMenu",
        "Hyphenation"
    ])
    print("HYPHEN_USED", used, flush=True)
    save_shot("04_Автоматические_переносы.png")
    dismiss()

    # 5. AutoText / Quick Parts gallery.
    focus_word(word)
    used=execute_candidates(word,[
        "AutoTextGallery",
        "QuickPartsInsertGallery",
        "BuildingBlocksGallery",
        "QuickPartsGallery"
    ])
    print("AUTOTEXT_USED", used, flush=True)
    save_shot("05_Автотекст.png")
    dismiss()

    doc.Close(0)
    doc=None

    # 6. Final PR13_2.doc with date inserted by AutoCorrect.
    doc=word.Documents.Open(str(FINALDOC),False,True)
    doc.Content.LanguageID=1049
    doc.Activate()
    focus_word(word)
    try:
        word.ActiveWindow.View.Type=3
        word.ActiveWindow.View.Zoom.Percentage=100
    except Exception:
        pass
    end=doc.Content.End-1
    doc.Range(max(0,end-15),end).Select()
    word.Selection.Collapse(0)
    time.sleep(2)
    save_shot("06_ПР13_2_дата_16.11.2026.png")

finally:
    if doc is not None:
        try: doc.Close(0)
        except Exception: pass
    try: word.Quit()
    except Exception: pass

print("DONE", sorted(p.name for p in OUT.glob("*.png")), flush=True)
