import os, sys, pathlib, hashlib, json
sys.path.append('/opt/ascon/kompas3d-v25/Bin')
from constants import constants as c
import ksapi

OUT = pathlib.Path('native_drawing')
OUT.mkdir(exist_ok=True)
TARGET = (OUT / 'Hexlet_KOMPAS3D_Privet_Hexlet.cdw').resolve()
REOPENED = (OUT / 'Hexlet_KOMPAS3D_Privet_Hexlet_REOPENED.cdw').resolve()

print('OPEN_INVISIBLE_1')
app = ksapi.OpenKompasInvisible()
print('APP1=', app)
if app is None:
    raise SystemExit('OpenKompasInvisible #1 returned None')
print('APP1_NAME=', app.GetApplicationName(True))
print('APP1_BUILD=', app.GetBuildNumber())

lm = app.GetApplicationLicenseManager()
print('LICENSE_MANAGER=', lm)
if lm is not None:
    try:
        print('KOMPAS_VARIANT=', lm.GetKompasVariant())
    except Exception as exc:
        print('KOMPAS_VARIANT_ERROR=', type(exc).__name__, str(exc))
    try:
        before2d = lm.IsKompasModuleActive(c.ksKompasModule2D)
        print('LICENSE_2D_BEFORE=', int(bool(before2d)))
        lm.SetKompasModuleActive(c.ksKompasModule2D, True)
        after2d = lm.IsKompasModuleActive(c.ksKompasModule2D)
        print('LICENSE_2D_AFTER=', int(bool(after2d)))
    except Exception as exc:
        print('LICENSE_2D_ERROR=', type(exc).__name__, str(exc))

docs = app.GetDocuments()
print('DOCS1=', docs)
if docs is None:
    raise SystemExit('GetDocuments #1 returned None')

try:
    print('LOCK_TEMPLATES_BEFORE=', int(bool(docs.IsLockTemplatesSettings())))
    docs.SetLockTemplatesSettings(True)
    print('LOCK_TEMPLATES_AFTER=', int(bool(docs.IsLockTemplatesSettings())))
except Exception as exc:
    print('LOCK_TEMPLATES_ERROR=', type(exc).__name__, str(exc))

doc = docs.AddWithDefaultSettings(c.ksDocumentDrawing, True)
print('DOC_ADD_DEFAULT=', doc)

if doc is None:
    try:
        doc = docs.Add(c.ksDocumentDrawing, True)
        print('DOC_ADD_PLAIN=', doc)
    except Exception as exc:
        print('DOC_ADD_PLAIN_ERROR=', type(exc).__name__, str(exc))

if doc is None:
    import glob
    templates = sorted(
        glob.glob('/opt/ascon/kompas3d-v25/Templates/**/*.cdt', recursive=True)
        + glob.glob('/etc/ascon/KOMPAS-3D/25/Templates/**/*.cdt', recursive=True)
    )
    print('CDT_TEMPLATES=', templates[:20])
    for template in templates:
        try:
            cand = docs.AddNewDocumentFromTemplate(template, True)
            print('DOC_ADD_TEMPLATE=', template, cand)
            if cand is not None:
                doc = cand
                break
        except Exception as exc:
            print('DOC_ADD_TEMPLATE_ERROR=', template, type(exc).__name__, str(exc))

print('DOC1=', doc)
if doc is None:
    try:
        print('KOMPAS_ERROR=', app.GetKompasError())
    except Exception as exc:
        print('KOMPAS_ERROR_QUERY_FAIL=', type(exc).__name__, str(exc))
    raise SystemExit('All native drawing creation routes returned None')

print('DOC1_TYPE=', doc.GetDocumentType())
if doc.GetDocumentType() != c.ksDocumentDrawing:
    raise SystemExit(f'Wrong document type: {doc.GetDocumentType()}')

d2 = ksapi.IKompasDocument2D(doc)
mgr = d2.GetViewsAndLayersManager()
views = mgr.GetViews()
view = views.GetActiveView()
dc = ksapi.IDrawingContainer(view)
texts = dc.GetDrawingTexts()
before = texts.GetCount()
print('TEXT_COUNT_BEFORE=', before)

t = texts.Add()
if t is None:
    raise SystemExit('DrawingTexts.Add returned None')
t.SetX(60.0)
t.SetY(120.0)
it = ksapi.IText(t)
line = it.Add()
item = line.Add()
item.SetStr('Привет, Хекслет!')
try:
    ksapi.ITextFont(item).SetHeight(10.0)
except Exception as exc:
    print('FONT_WARN=', type(exc).__name__, str(exc))
if not t.Update():
    raise SystemExit('DrawingText.Update failed')

after = texts.GetCount()
print('TEXT_COUNT_AFTER=', after)
if after < before + 1:
    raise SystemExit('Text count did not increase')

save_ok = doc.SaveAs(str(TARGET))
print('SAVE_OK=', save_ok)
if not TARGET.exists() or TARGET.stat().st_size == 0:
    raise SystemExit('CDW was not saved')
print('TARGET_SIZE=', TARGET.stat().st_size)
print('TARGET_SHA256=', hashlib.sha256(TARGET.read_bytes()).hexdigest())
print('TARGET_HEAD=', TARGET.read_bytes()[:4].hex())

doc.Close(c.kdDoNotSaveChanges)
app.Quit()
print('CLOSED_FIRST_INSTANCE')

print('OPEN_INVISIBLE_2')
app2 = ksapi.OpenKompasInvisible()
print('APP2=', app2)
if app2 is None:
    raise SystemExit('OpenKompasInvisible #2 returned None')
docs2 = app2.GetDocuments()
doc2 = docs2.Open(str(TARGET), False, False)
print('REOPEN_DOC=', doc2)
if doc2 is None:
    raise SystemExit('Reopen returned None')
print('REOPEN_TYPE=', doc2.GetDocumentType())
if doc2.GetDocumentType() != c.ksDocumentDrawing:
    raise SystemExit('Reopened document is not drawing')

rd2 = ksapi.IKompasDocument2D(doc2)
rview = rd2.GetViewsAndLayersManager().GetViews().GetActiveView()
rdc = ksapi.IDrawingContainer(rview)
rtexts = rdc.GetDrawingTexts()
recount = rtexts.GetCount()
print('REOPEN_TEXT_COUNT=', recount)
if recount < 1:
    raise SystemExit('No text objects after reopen')

resave_ok = doc2.SaveAs(str(REOPENED))
print('RESAVE_OK=', resave_ok)
if not REOPENED.exists() or REOPENED.stat().st_size == 0:
    raise SystemExit('Reopened CDW resave failed')

result = {
    'result':'PASS_NATIVE_DRAWING_SAVE_CLOSE_REOPEN',
    'application':app2.GetApplicationName(True),
    'build':app2.GetBuildNumber(),
    'document_type':doc2.GetDocumentType(),
    'text_count':recount,
    'file':TARGET.name,
    'size':TARGET.stat().st_size,
    'sha256':hashlib.sha256(TARGET.read_bytes()).hexdigest(),
    'reopened_file':REOPENED.name,
    'reopened_size':REOPENED.stat().st_size,
    'reopened_sha256':hashlib.sha256(REOPENED.read_bytes()).hexdigest(),
}
(OUT/'validation.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
print('RESULT=PASS_NATIVE_DRAWING_SAVE_CLOSE_REOPEN')

doc2.Close(c.kdDoNotSaveChanges)
app2.Quit()
