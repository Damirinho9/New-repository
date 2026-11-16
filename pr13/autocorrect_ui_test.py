import json, time, pathlib
import pythoncom
import win32com.client
from pywinauto import Desktop
from pywinauto.keyboard import send_keys

ROOT = pathlib.Path.cwd()
tests = json.loads((ROOT / "pr13" / "autocorrect_tests.json").read_text(encoding="utf-8"))
log = []

pythoncom.CoInitialize()
word = win32com.client.DispatchEx("Word.Application")
word.Visible = False
word.DisplayAlerts = 0
ac = word.AutoCorrect
ac.ReplaceText = True
ac.ReplaceTextFromSpellingChecker = True
ac.CorrectSentenceCaps = True
ac.CorrectCapsLock = True

log.append(f"WORD_VERSION={word.Version}")
log.append(f"AUTOCORRECT_REPLACE_TEXT={ac.ReplaceText}")
log.append(f"AUTOCORRECT_SPELLING_SUGGESTIONS={ac.ReplaceTextFromSpellingChecker}")

doc = word.Documents.Add()
doc.Content.LanguageID = 1049
doc.Activate()
word.Visible = True
time.sleep(3.0)
hwnd = int(word.ActiveWindow.Hwnd)
win = Desktop(backend="uia").window(handle=hwnd)
win.wait("visible", timeout=10)
win.set_focus()
time.sleep(0.7)
log.append(f"WORD_HWND={hwnd}")
log.append(f"WINDOW_TITLE={win.window_text()}")

failed = False

def save_log():
    (ROOT / "autocorrect-results.txt").write_text("\n".join(log) + "\n", encoding="utf-8")

def com_retry(fn, attempts=15, pause=0.4):
    last = None
    for _ in range(attempts):
        try:
            return fn()
        except Exception as exc:
            last = exc
            time.sleep(pause)
    raise last

def clear_doc():
    win.set_focus()
    time.sleep(0.4)
    send_keys("^a{BACKSPACE}", pause=0.08)
    time.sleep(0.7)

def read_text():
    return com_retry(lambda: (doc.Content.Text or "").strip())

def real_type(value):
    win.set_focus()
    time.sleep(0.4)
    send_keys(value, with_spaces=True, pause=0.10, vk_packet=True)
    send_keys("{SPACE}", pause=0.1)
    time.sleep(1.5)
    return read_text()

for t in tests:
    clear_doc()
    actual = real_type(t["input"])
    log.append(f'FIRST:{t["input"]} -> {actual}')
    if actual != t["expected"]:
        log.append(f'BUILTIN_MISS:{t["input"]}')
        try:
            com_retry(lambda: ac.Entries.Item(t["input"]).Delete())
        except Exception:
            pass
        com_retry(lambda: ac.Entries.Add(Name=t["input"], Value=t["expected"]))
        time.sleep(0.8)
        clear_doc()
        actual2 = real_type(t["input"])
        log.append(f'AFTER_MANUAL:{t["input"]} -> {actual2}')
        if actual2 == t["expected"]:
            log.append(f'MANUAL_OK:{t["input"]}')
        else:
            log.append(f'FINAL_FAIL:{t["input"]}')
            failed = True
    else:
        log.append(f'BUILTIN_OK:{t["input"]}')
    save_log()

save_log()
try:
    doc.Close(0)
except Exception:
    pass
try:
    word.Quit()
except Exception:
    pass

if failed:
    raise SystemExit(2)
print("\n".join(log))
