import pathlib, pythoncom, win32com.client

ROOT = pathlib.Path.cwd()
SRC = ROOT / "input" / "PR13_2.doc"
OUT = ROOT / "ПР13_2.doc"
LOG = ROOT / "metadata-clean.txt"

pythoncom.CoInitialize()
word = win32com.client.DispatchEx("Word.Application")
word.Visible = False
word.DisplayAlerts = 0
lines = [f"WORD_VERSION={word.Version}"]

doc = None
try:
    doc = word.Documents.Open(str(SRC), False, False)
    before = doc.Content.Text
    doc.Repaginate()
    lines.append(f"PAGES_BEFORE={doc.ComputeStatistics(2)}")
    lines.append(f"FORMAT_BEFORE={doc.SaveFormat}")

    # Clear built-in properties that can expose tooling/user traces.
    props = doc.BuiltInDocumentProperties
    for name in ["Author", "Comments", "Last Author", "Title", "Subject", "Keywords", "Company"]:
        try:
            p = props.Item(name)
            old = str(p.Value)
            try:
                p.Value = ""
                lines.append(f"CLEARED:{name}={old}")
            except Exception as e:
                lines.append(f"CLEAR_FAIL:{name}:{e}")
        except Exception:
            pass

    # Native Word privacy cleanup. 99 = wdRDIAll.
    try:
        doc.RemoveDocumentInformation(99)
        lines.append("REMOVE_DOCUMENT_INFORMATION_ALL=True")
    except Exception as e:
        lines.append(f"REMOVE_DOCUMENT_INFORMATION_ALL_FAIL={e}")

    doc.Save()
    lines.append("SAVE_OK=True")
    doc.Close(0)
    doc = None

    # Copy exact Word-saved bytes to artifact path.
    OUT.write_bytes(SRC.read_bytes())

    verify = word.Documents.Open(str(OUT), False, True)
    try:
        verify.Repaginate()
        after = verify.Content.Text
        lines.append(f"PAGES_AFTER={verify.ComputeStatistics(2)}")
        lines.append(f"FORMAT_AFTER={verify.SaveFormat}")
        lines.append(f"TEXT_IDENTICAL={before == after}")
        lines.append(f"ENDS_WITH_DATE={after.rstrip().endswith('16.11.2026')}")
        if before != after:
            raise RuntimeError("Text changed during metadata cleanup")
        if verify.ComputeStatistics(2) != 3:
            raise RuntimeError("Page count changed")
        if verify.SaveFormat != 0:
            raise RuntimeError("Legacy DOC format changed")
        if not after.rstrip().endswith("16.11.2026"):
            raise RuntimeError("Final date missing")
    finally:
        verify.Close(0)

    LOG.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
finally:
    if doc is not None:
        try: doc.Close(0)
        except Exception: pass
    try: word.Quit()
    except Exception: pass
    pythoncom.CoUninitialize()
