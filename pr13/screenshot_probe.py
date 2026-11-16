import os, time, pathlib
from PIL import ImageGrab
import pythoncom, win32com.client

ROOT=pathlib.Path.cwd()
OUT=ROOT/"screens"
OUT.mkdir(exist_ok=True)
doc_path=ROOT/"PR13_1_source.docx"

pythoncom.CoInitialize()
word=win32com.client.DispatchEx("Word.Application")
word.Visible=True
word.DisplayAlerts=0
try:
    doc=word.Documents.Open(str(doc_path),False,True)
    doc.Content.LanguageID=1049
    word.Options.CheckSpellingAsYouType=True
    word.Options.CheckGrammarAsYouType=True
    try:
        word.ActiveWindow.WindowState=1
    except Exception:
        pass
    time.sleep(4)
    img=ImageGrab.grab(all_screens=True)
    img.save(OUT/"test-word.png")
    print("SHOT", img.size)
    print("SPELL", doc.SpellingErrors.Count, "GRAM", doc.GrammaticalErrors.Count)
finally:
    try: doc.Close(0)
    except Exception: pass
    try: word.Quit()
    except Exception: pass
