# Native build kit — 7335493
This is an engineering trial, not final delivery. Original methodology and scope not confirmed.
 
## Local run
Use Python 3.12, then python -m pip install -r requirements.txt.
Linux / Windows independent: python native_build.py --mode independent --out independent-run
Validate syntax and fail-closed behavior: python validate_all.py
Native candidate requires interactive Windows with an installed, appropriately licensed KOMPAS (API5/API7), permitted commercial use, installed pywin32 and compatible bitness.
Confirm entitlement externally. In PowerShell: $env:KOMPAS_LICENSE_CONFIRMED='YES'
Run Work 1 first: powershell -ExecutionPolicy RemoteSigned -File .\build_all.ps1 -Mode native -Work 1 -Candidate -Output run-frw
Optional original fragment: pass -Seed 'C:\path\original.frw'. It is copied into a new directory, not overwritten. If the seed is missing named variables, start a new document without -Seed.
Full candidate: powershell -ExecutionPolicy RemoteSigned -File .\build_all.ps1 -Mode native -Work all -Candidate -Output run-all
Use a fresh output directory for each invocation. The runner logs subprocess output and stops on failure, without declaring the order complete.
The Linux wrapper runs the independent path; no complete Linux-native backend was verified. 
Only when entitlement, source method and native behavior are verified should an operator review and release. Do not send candidate output as final work. A2, tolerances, finish, feature assumptions, figure 25, full scope, native export PDF and relocation all require review.
The Windows implementation is untested against actual KOMPAS. Static syntax, independent OCCT, and negative gate can be tested without KOMPAS. 
Existing native sources and official SDK methods are reused but COM signature and plane placement need real testing. Do not retry blindly if a specific API call fails.
 
## Self-hosted runner
Use an already licensed Windows computer with GitHub runner labels self-hosted, Windows, X64, kompas. Start runner in an interactive user session; do not run as an unattended service if GUI interaction is required.
Only execute trusted code from the pinned branch, not external PRs. Do not expose credentials, keys or student files on a public runner. No hosted native run is authorized by a module flag alone.
The native workflow is prepared for manual dispatch; GitHub may require it to be registered on the default branch before dispatch. Do not modify main without authorization; the local command is the primary route.
 
## Release gates
1. Get original assignment and remarks, figure 25, actual scope.
2. Confirm exact groove geometry and cutting profile; resolve all candidate drawing annotations.
3. Native FRW: verify actual geometry and variables after disk reopen.
4. Native M3D/A3D: verify model tree/parameters and change an actual workpiece dimension, not only translation.
5. CDW: verify true local section and update on actual source model change; export native PDF and visual inspect.
6. Copy to a new isolated directory, close original model files, verify links to the copied models and repeat acceptance.
7. Only then prepare final ZIP with real native files, reports, screenshots, and acceptance evidence.
