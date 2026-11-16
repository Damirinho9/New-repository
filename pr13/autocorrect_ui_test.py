import json, pathlib
import pythoncom
import win32com.client

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
ac.CorrectCapsLock = True

log.append(f"WORD_VERSION={word.Version}")
log.append(f"REPLACE_TEXT={ac.ReplaceText}")
log.append(f"REPLACE_FROM_SPELLING={ac.ReplaceTextFromSpellingChecker}")
log.append(f"CORRECT_CAPS_LOCK={ac.CorrectCapsLock}")

doc = word.Documents.Add()
doc.Content.LanguageID = 1049

for t in tests:
    builtin = False
    builtin_value = None
    try:
        e = ac.Entries.Item(t["input"])
        builtin = True
        builtin_value = str(e.Value)
    except Exception:
        pass
    log.append(f'ENTRY_BEFORE:{t["input"]} exists={builtin} value={builtin_value}')

    needs_manual = (not builtin) or (builtin_value != t["expected"])
    if needs_manual:
        try:
            ac.Entries.Item(t["input"]).Delete()
        except Exception:
            pass
        ac.Entries.Add(Name=t["input"], Value=t["expected"])
        log.append(f'MANUAL_ADDED:{t["input"]} -> {t["expected"]}')
    else:
        log.append(f'BUILTIN_ENTRY_OK:{t["input"]} -> {builtin_value}')

    entry = ac.Entries.Item(t["input"])
    final_value = str(entry.Value)
    log.append(f'ENTRY_AFTER:{t["input"]} -> {final_value}')

    doc.Content.Text = t["input"]
    rng = doc.Range(0, len(t["input"]))
    entry.Apply(Range=rng)
    applied = (doc.Content.Text or "").strip()
    log.append(f'APPLY_RESULT:{t["input"]} -> {applied}')
    if applied != t["expected"]:
        raise RuntimeError(f'Apply mismatch for {t["input"]}: {applied!r}')

(ROOT / "autocorrect-results.txt").write_text("\n".join(log) + "\n", encoding="utf-8")
print("\n".join(log))

doc.Close(0)
word.Quit()
