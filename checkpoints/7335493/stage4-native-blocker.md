# Stage 4 - strict native smoke acceptance

Date: 2026-11-20
Branch: kompas-7335493-native-work1
Head before record: 23e36fc007a2b905a7a6c7eaf5b08ee62933d94e

## Required gates

2D:
- create native FRW
- line + driving dimension
- variable mutation with coordinate change
- Save -> Close -> Reopen -> Rebuild

3D:
- open existing native M3D
- GetTopPart
- sketch edit
- extrusion
- native mass and volume
- Save -> Close -> Reopen -> Rebuild

No PASS may be reported without the complete chain.

## Licensed invisible backend - 2D

Run 44689823918
Artifact 14607733495
Digest sha256:69e5a888413348405d7d4e9f1f2db426cdb0e27e34706c81cf44dffc0d56d410

Confirmed:
- KOMPAS process and in-process API7 operate
- LICENSE_2D_ACTIVE=1

Creation routes tested from KOMPAS main loop without CLI-open document:
- AddNewDocumentFromTemplate(template, visible) -> null
- AddNewDocumentFromTemplate(template, invisible) -> null
- Open(native Fragment.frw template, visible) -> null
- Open(native Fragment.frw template, invisible) -> null
- AddWithDefaultSettings(ksDocumentFragment, visible) -> null
- AddWithDefaultSettings(ksDocumentFragment, invisible) -> null
- Add(ksDocumentFragment, visible) -> null
- Add(ksDocumentFragment, invisible) -> null

Terminal log:
`FAIL no editable fragment route`

No native 2D mutation occurred. No 2D PASS.

## Licensed invisible backend - 3D

Run 44689925172
Artifact 14608825325
Digest sha256:8ecdb317ddeb735c8cbf5637495bfe0e8f11a4e98186083563ac9494b07bf45e

Confirmed:
- LICENSE_3D_ACTIVE=1
- official vendor SDK part template extracted and verified

Creation routes tested from KOMPAS main loop:
- AddNewDocumentFromTemplate(vendor part.m3d, visible) -> null
- AddWithDefaultSettings(ksDocumentPart, visible) -> null
- Add(ksDocumentPart, visible) -> null

Terminal log:
`RESULT=FAIL_NO_3D_CREATION_ROUTE`

No TopPart was created. No native 3D mutation occurred. No 3D PASS.

## Full GUI backend

Direct official packages were installed on Ubuntu 24.04:
- ascon-kompas-v25 25.0.5.2780
- ascon-kompas-graphic-v25 25.0.5.2780
- ascon-kompas3d-v25 25.0.5.2780
- ascon-kompas-sdk-v25 25.0.5.2780

QtResources.bin was restored to the GUI user config and the official `kompas-v25` launcher was used. The full GUI loads.

External API server route:
- full GUI starts
- `-APIServer=10500` does not expose a listener on the hosted runner
- therefore external `ksapi.GetKompas()` cannot attach to full GUI

In-process API7 route:
Run 44689450966
Artifact 14608540297
Digest sha256:ae708dc20a61706f7492405d2faf5e06709d127c586eb6400bfc298221cdd836

Confirmed:
- KOMPAS_VERSION=25.0.5
- GetKompasApplication works inside full kKompas main event loop

License gate:
- LICENSE_2D_BEFORE=0
- LICENSE_3D_BEFORE=0
- official SetKompasModuleActive(..., true) attempted
- LICENSE_2D_AFTER=0
- LICENSE_3D_AFTER=0
- RESULT=FAIL_FULL_GUI_LICENSE

Per project rules an unlicensed GUI session is not eligible for native modeling.

## Windows backend

The repository contains no Windows KOMPAS installer or portable Windows runtime.
The previously configured self-hosted Windows workflow requiring labels
`[self-hosted, Windows, X64, kompas]` did not obtain a runner and executed no native steps.

## Stage 4 decision

There is currently no backend available through this GitHub environment that is simultaneously:
1. officially licensed for the needed module, and
2. capable of creating/initializing editable 2D/3D native documents.

Therefore:

`RESULT=BLOCKED_NATIVE_ENV_NO_EDITABLE_LICENSED_BACKEND`

This is NOT a native PASS.

Do not repeat the same hosted Linux combinations:
- CLI-open FRW in ksinvisible -> ActiveView null
- CLI-open M3D in ksinvisible -> TopPart null
- Add / AddWithDefaultSettings / native templates in licensed ksinvisible -> null document
- full GUI hosted session -> API7 available in-process but 2D/3D license inactive

To continue native completion, attach a genuinely licensed KOMPAS workstation/runner (prefer Windows API7 or a licensed full Linux GUI session). Once such a runner is available, resume directly from Stage 4 smoke tests; do not redo runtime recovery or builder calculations.
