# Stage 3 - backend selection and GUI fallback

Date: 2026-11-19
Branch: kompas-7335493-native-work1
Head before record: 43dcd08f99ba548ad2ecc48faa8dcb314aec051d

## Priority 1 - licensed Windows KOMPAS API7

Status: UNAVAILABLE.

Evidence: workflow run 44267589118.
- Linux source/syntax gate passed.
- Job `build-native-work5` required labels `[self-hosted, Windows, X64, kompas]`.
- The job never obtained a runner and had no steps.
- Run remained pending for about 24 hours and was cancelled.

Conclusion: no usable Windows KOMPAS runner is currently available. Do not queue native work on this runner until its availability is independently restored.

## Priority 2 - full Linux GUI kKompas

Official `ascon-kompas-v25 25.0.5.2780` GUI package was downloaded only as the missing GUI component and extracted over the frozen Ubuntu portable runtime. KOMPAS itself was not fully reinstalled.

Full GUI executable:
`/opt/ascon/kompas3d-v25/Bin/kKompas`

Observed successful GUI/API run: 44534936664.
- real `kKompas` process launched under Xvfb
- in-process API7 probe executed on main KOMPAS event loop
- KOMPAS version 25.0.5
- `GetDocuments()` returned a live collection
- `DOCUMENT_COUNT=0`
- result: `PASS_FULL_LINUX_GUI_INPROCESS_API_AND_DOCUMENTS`

License gate run: 44535591846.
- `KOMPAS_VARIANT=0`
- `LICENSE_2D_ACTIVE_BEFORE=0`
- `LICENSE_3D_ACTIVE_BEFORE=0`
- official `SetKompasModuleActive(..., true)` was attempted once
- `LICENSE_2D_ACTIVE_AFTER=0`
- `LICENSE_3D_ACTIVE_AFTER=0`
- result: `FULL_GUI_API_PASS_LICENSE_INACTIVE`

Conclusion: full Linux GUI is technically operational and API7 is reachable in-process, but this hosted GUI session has no active 2D/3D license. Per project rules it is NOT eligible for native modeling. Do not continue experiments on this unlicensed GUI backend.

Final Stage 3 evidence artifact:
- run 44535591846
- artifact 14535756935
- digest sha256:7ad892036b0174fb24c0aa38817a2a4f98a6627655d7778e0304e9094df9f542
- retention until 2027-02-17T13:39:13Z

## Priority 3 - frozen Ubuntu runtime with official external SDK

Selected backend for Stage 4.

Established in Stage 2:
- launch `/tmp/kKompas -> ksinvisible`
- command `/tmp/kKompas -automation`
- `ksapi.GetKompas()` returns live `IApplication`
- application: `КОМПАС-3D Invisible v25`
- `GetDocuments()` returns live `IDocuments`
- result: `PASS_KOMPAS_SDK_CONNECTION_AND_DOCUMENTS`

Do not use `GetKompasInvisible()` in this runtime.
Do not pass TCP ports to `IApplication()`.

## Stage 3 decision

`RESULT=PASS_BACKEND_SELECTION_PRIORITY3_PORTABLE_UBUNTU_EXTERNAL_SDK`

Next stage must test a minimal real native mutation on the selected Priority 3 backend. If it cannot provide editable native documents despite the established SDK connection, stop using it and require a genuinely licensed external workstation/runner. No Debian, no ALT license-inactive modeling, no full KOMPAS reinstall.
