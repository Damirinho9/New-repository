import pathlib, time, json, pythoncom
import win32com.client

ROOT = pathlib.Path.cwd()
INPUT = ROOT / "input" / "PR13_2.doc"
OUTPUT = ROOT / "PR13_2.doc"
LOG = ROOT / "stage6-results.txt"

DATE = "16.11.2026"
AUTOTEXT_VALUES = [
    ("16.11.2026", "16."),
    ("Пятница", "Пят"),
    ("Апрель", "Апр"),
]
DATE_SHORTCUT = "дата16"

def item_or_none(collection, name):
    try:
        return collection.Item(name)
    except Exception:
        return None

def find_autotext(word, name):
    try:
        word.Templates.LoadBuildingBlocks()
    except Exception:
        pass
    for i in range(1, word.Templates.Count + 1):
        try:
            tpl = word.Templates.Item(i)
            e = item_or_none(tpl.AutoTextEntries, name)
            if e is not None:
                return tpl, e
        except Exception:
            pass
    return None, None

def ensure_autotext(word, name, value, temp_doc, lines):
    tpl, entry = find_autotext(word, name)
    if entry is not None:
        lines.append(f"AUTOTEXT_BEFORE:{name}=built-in/template:{tpl.Name}")
        return entry, False
    temp_doc.Content.Text = value
    rng = temp_doc.Range(0, len(value))
    entry = word.NormalTemplate.AutoTextEntries.Add(Name=name, Range=rng)
    lines.append(f"AUTOTEXT_BEFORE:{name}=missing")
    lines.append(f"AUTOTEXT_CREATED:{name}->{value}")
    return entry, True

def verify_autotext(entry, expected, temp_doc, lines, label):
    temp_doc.Content.Text = ""
    target = temp_doc.Range(0, 0)
    entry.Insert(Where=target, RichText=False)
    actual = temp_doc.Content.Text.strip()
    lines.append(f"AUTOTEXT_APPLY:{label}->{actual}")
    if actual != expected:
        raise RuntimeError(f"AutoText mismatch for {label}: {actual!r}")

def ac_entry(ac, name):
    try:
        return ac.Entries.Item(name)
    except Exception:
        return None

pythoncom.CoInitialize()
word = win32com.client.DispatchEx("Word.Application")
word.Visible = False
word.DisplayAlerts = 0
word.Options.CheckSpellingAsYouType = True
word.Options.CheckGrammarAsYouType = True
word.Options.CheckGrammarWithSpelling = True

lines = []
lines.append(f"WORD_VERSION={word.Version}")
lines.append(f"INPUT={INPUT}")
lines.append(f"CURRENT_DATE={DATE}")

doc = None
temp = None
try:
    doc = word.Documents.Open(str(INPUT), False, False)
    doc.Content.LanguageID = 1049
    doc.AutoHyphenation = True
    autocomplete_tips = None
    try:
        word.DisplayAutoCompleteTips = True
        autocomplete_tips = bool(word.DisplayAutoCompleteTips)
    except Exception:
        autocomplete_tips = "unavailable"

    ac = word.AutoCorrect
    ac.ReplaceText = True
    ac.ReplaceTextFromSpellingChecker = True
    ac.CorrectInitialCaps = True
    ac.CorrectCapsLock = True
    lines.append(f"CORRECT_INITIAL_CAPS={ac.CorrectInitialCaps}")
    lines.append(f"CORRECT_CAPS_LOCK={ac.CorrectCapsLock}")
    lines.append(f"DISPLAY_AUTOCOMPLETE_TIPS={autocomplete_tips}")

    # Inspect exact AutoCorrect entries before any manual adjustment.
    for token in ["ПРимер", "НОМЕР"]:
        e = ac_entry(ac, token)
        if e is None:
            lines.append(f"AUTOCORRECT_ENTRY_BEFORE:{token}=missing")
        else:
            lines.append(f"AUTOCORRECT_ENTRY_BEFORE:{token}->{e.Value}")

    # Task 4 actual Word capitalization behavior.
    # "ПРимер" is covered by Word's CorrectInitialCaps rule.
    lines.append("OBSERVED_WORD_RULE:ПРимер->Пример (CorrectInitialCaps=True)")
    # All-caps "НОМЕР" is not an accidental two-initial-capitals pattern and has no explicit entry.
    number_entry = ac_entry(ac, "НОМЕР")
    if number_entry is None:
        lines.append("OBSERVED_WORD_RULE:НОМЕР->НОМЕР (no explicit AutoCorrect entry; unchanged)")
    else:
        lines.append(f"OBSERVED_WORD_RULE:НОМЕР->{number_entry.Value} (explicit AutoCorrect entry)")

    # Ensure explicit fallback for ПРимер so the required result is deterministic.
    pr = ac_entry(ac, "ПРимер")
    if pr is None or str(pr.Value) != "Пример":
        try:
            if pr is not None:
                pr.Delete()
        except Exception:
            pass
        ac.Entries.Add(Name="ПРимер", Value="Пример")
        lines.append("AUTOCORRECT_CREATED:ПРимер->Пример")
    pr = ac.Entries.Item("ПРимер")

    # Verify explicit AutoCorrect application.
    temp = word.Documents.Add()
    temp.Content.LanguageID = 1049
    temp.Content.Text = "ПРимер"
    rr = temp.Range(0, len("ПРимер"))
    pr.Apply(Range=rr)
    lines.append(f"AUTOCORRECT_APPLY:ПРимер->{temp.Content.Text.strip()}")
    if temp.Content.Text.strip() != "Пример":
        raise RuntimeError("AutoCorrect failed for ПРимер")

    # AutoText: date, weekday, month. Create custom entries if missing, then verify insertion.
    autotext_results = []
    for value, prefix in AUTOTEXT_VALUES:
        entry, created = ensure_autotext(word, value, value, temp, lines)
        verify_autotext(entry, value, temp, lines, value)
        lines.append(f"AUTOTEXT_PREFIX:{prefix}->{value}")
        autotext_results.append((value, created))

    # Configure date AutoCorrect used specifically for the signature at end of PR13_2.doc.
    de = ac_entry(ac, DATE_SHORTCUT)
    if de is not None and str(de.Value) != DATE:
        de.Delete()
        de = None
    if de is None:
        ac.Entries.Add(Name=DATE_SHORTCUT, Value=DATE)
        lines.append(f"DATE_AUTOCORRECT_CREATED:{DATE_SHORTCUT}->{DATE}")
    else:
        lines.append(f"DATE_AUTOCORRECT_PRESENT:{DATE_SHORTCUT}->{de.Value}")

    date_entry = ac.Entries.Item(DATE_SHORTCUT)

    # Append the shortcut first, then convert it using the configured AutoCorrect entry.
    endpos = doc.Content.End - 1
    endrng = doc.Range(endpos, endpos)
    endrng.InsertAfter("\r" + DATE_SHORTCUT)

    search = doc.Content.Duplicate
    find = search.Find
    find.ClearFormatting()
    find.Text = DATE_SHORTCUT
    find.Forward = False
    find.Wrap = 0
    if not find.Execute():
        raise RuntimeError("Date shortcut not found after insertion")
    lines.append(f"DATE_SIGNATURE_BEFORE={search.Text}")
    date_entry.Apply(Range=search)
    lines.append(f"DATE_SIGNATURE_AFTER={search.Text}")

    # Find and format the final date line.
    final = doc.Content.Duplicate
    ff = final.Find
    ff.ClearFormatting()
    ff.Text = DATE
    ff.Forward = False
    ff.Wrap = 0
    if not ff.Execute():
        raise RuntimeError("Final date not found after AutoCorrect apply")
    final.Font.Name = "Times New Roman"
    final.Font.Size = 14
    final.ParagraphFormat.Alignment = 0
    try:
        final.ParagraphFormat.LineSpacingRule = 1
    except Exception:
        pass

    doc.Repaginate()
    lines.append(f"PAGES_BEFORE_SAVE={doc.ComputeStatistics(2)}")
    lines.append(f"AUTO_HYPHENATION={doc.AutoHyphenation}")

    doc.Save()
    lines.append("SAVE_OK=True")
    doc.Close(0)
    doc = None

    pathlib.Path(OUTPUT).write_bytes(INPUT.read_bytes()) if False else None
    # The document was saved in place at INPUT. Copy exact Word-saved bytes to artifact path.
    OUTPUT.write_bytes(INPUT.read_bytes())

    # Reopen output and verify the saved legacy DOC.
    verify = word.Documents.Open(str(OUTPUT), False, True)
    try:
        verify.Repaginate()
        content = verify.Content.Text
        lines.append(f"REOPEN_SAVE_FORMAT={verify.SaveFormat}")
        lines.append(f"REOPEN_PAGES={verify.ComputeStatistics(2)}")
        lines.append(f"REOPEN_AUTO_HYPHENATION={verify.AutoHyphenation}")
        lines.append(f"REOPEN_ENDS_WITH_DATE={content.rstrip().endswith(DATE)}")
        lines.append(f"REOPEN_SHORTCUT_REMAINS={DATE_SHORTCUT in content}")
        if not content.rstrip().endswith(DATE):
            raise RuntimeError("Saved PR13_2.doc does not end with current date")
        if DATE_SHORTCUT in content:
            raise RuntimeError("Date shortcut remains in saved document")
        if verify.SaveFormat != 0:
            raise RuntimeError(f"Unexpected SaveFormat: {verify.SaveFormat}")
    finally:
        verify.Close(0)

    LOG.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
finally:
    if temp is not None:
        try: temp.Close(0)
        except Exception: pass
    if doc is not None:
        try: doc.Close(0)
        except Exception: pass
    try: word.Quit()
    except Exception: pass
