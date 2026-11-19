# Stage 2 - KOMPAS SDK connection proof

Date: 2026-11-19
Branch: kompas-7335493-native-work1
Head before record: 10635711147f3e016a71de33e041bb0c7fe3ff03
Workflow run: 44530683146
Workflow result: SUCCESS
Evidence artifact: 14534365210 (7335493-stage2-sdk-connection)
Evidence artifact digest: sha256:f8ab3a7155b79196f9d083a14c040124752db21f157392821cf91bd7dd0e244d
Evidence retention: 2027-02-17T13:09:34Z

## Historical launch reproduced

Symlink:
`/tmp/kKompas -> /opt/ascon/kompas3d-v25/Bin/ksinvisible`

Actual executable:
`/home/runner/work/_temp/kompas-runtime/opt/ascon/kompas3d-v25/Bin/ksinvisible`

Command line:
`/tmp/kKompas -automation`

KOMPAS PID: 2837
Wrapper PID: 2818
Confirmed TCP listener owned by the process: 127.0.0.1:10674

## SDK comparison

`ksapi.GetKompas()`:
- returned live `ksapi.IApplication`
- application name: `КОМПАС-3D Invisible v25`
- `GetDocuments()` returned live `ksapi.IDocuments`
- `GetCount() = 0`
- PASS

`ksapi.GetKompasInvisible()`:
- returned `None`
- FAIL for this launch mode

`ksapi.IApplication(port)`:
- NOT executed. Inspection of the shipped `ksapi.py` proves that `IApplication(int)` accepts an already acquired native `kompasApp` reference. It is not a TCP-port connection API. Passing the listener port would reinterpret the port as an object reference and is invalid.

## Result

`RESULT=PASS_KOMPAS_SDK_CONNECTION_AND_DOCUMENTS`

Stage 2 acceptance criterion is met: a working application object and document collection are available through the official SDK.

Use `/tmp/kKompas -automation` plus `ksapi.GetKompas()` as the established connection backend for the next stage. Do not use `GetKompasInvisible()` for this runtime and do not pass TCP ports to `IApplication()`.
