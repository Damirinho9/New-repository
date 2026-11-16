import json, time, pathlib, ctypes
from ctypes import wintypes
import pythoncom
import win32com.client

ROOT = pathlib.Path.cwd()
tests = json.loads((ROOT / "pr13" / "autocorrect_tests.json").read_text(encoding="utf-8"))
log = []

user32 = ctypes.WinDLL("user32", use_last_error=True)
EnumChildProc = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
user32.EnumChildWindows.argtypes = [wintypes.HWND, EnumChildProc, wintypes.LPARAM]
user32.GetClassNameW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
user32.SendMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
user32.SendMessageW.restype = wintypes.LPARAM
WM_CHAR = 0x0102

def child_classes(parent):
    out = []
    @EnumChildProc
    def cb(hwnd, lparam):
        buf = ctypes.create_unicode_buffer(256)
        user32.GetClassNameW(hwnd, buf, 256)
        out.append((int(hwnd), buf.value))
        return True
    user32.EnumChildWindows(parent, cb, 0)
    return out

def find_wwg(parent):
    direct = child_classes(parent)
    for hwnd, cls in direct:
        if cls == "_WwG":
            return hwnd
    for hwnd, cls in direct:
        found = find_wwg(hwnd)
        if found:
            return found
    return None

def send_chars(hwnd, text):
    for ch in text:
        user32.SendMessageW(hwnd, WM_CHAR, ord(ch), 1)
        time.sleep(0.06)

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
top = int(word.ActiveWindow.Hwnd)
wwg = find_wwg(top)
log.append(f"WORD_TOP_HWND={top}")
log.append(f"WORD_EDITOR_HWND={wwg}")
if not wwg:
    (ROOT / "autocorrect-results.txt").write_text("\n".join(log)+"\n", encoding="utf-8")
    raise SystemExit("Word _WwG editor window not found")

failed = False
for t in tests:
    doc.Content.Text = ""
    doc.Range(0,0).Select()
    send_chars(wwg, t["input"])
    send_chars(wwg, " ")
    time.sleep(0.8)
    actual = (doc.Content.Text or "").strip()
    log.append(f'FIRST:{t["input"]} -> {actual}')
    if actual != t["expected"]:
        log.append(f'BUILTIN_MISS:{t["input"]}')
        try:
            ac.Entries.Item(t["input"]).Delete()
        except Exception:
            pass
        ac.Entries.Add(Name=t["input"], Value=t["expected"])
        time.sleep(0.4)
        doc.Content.Text = ""
        doc.Range(0,0).Select()
        send_chars(wwg, t["input"])
        send_chars(wwg, " ")
        time.sleep(0.8)
        actual2 = (doc.Content.Text or "").strip()
        log.append(f'AFTER_MANUAL:{t["input"]} -> {actual2}')
        if actual2 == t["expected"]:
            log.append(f'MANUAL_OK:{t["input"]}')
        else:
            log.append(f'FINAL_FAIL:{t["input"]}')
            failed = True
    else:
        log.append(f'BUILTIN_OK:{t["input"]}')
    (ROOT / "autocorrect-results.txt").write_text("\n".join(log)+"\n", encoding="utf-8")

try:
    doc.Close(0)
except Exception:
    pass
try:
    word.Quit()
except Exception:
    pass

print("\n".join(log))
if failed:
    raise SystemExit(2)
