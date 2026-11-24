# Stage 7 - fresh official SDK audit, no native acceptance

Run 45400758324 (job 138468404827), success of static audit only.
Commit d93aea131b781cbaa35730427c4cf114eef8cd37.
Artifact 14922862309, SHA256 0da41751831a8179cee55f550f8a0e6c172e2ff36794f3bab8b54ad4da36c329.
Downloaded archive CRC and SHA256 checked.

- Official fresh SDK package 25.0.5.2780, 173 MB, extracted without running CAD or activating any license.
- Simulated full install: 204 packages; base: 164; 40 additional packages. APT simulation is not installation.
- A/B: SetLockTemplatesSettings, IsLockTemplatesSettings, GetOpenDocumentParam, OpenDocument declarations exist in KsAPI and KsAPICLink C++ headers.
- C/D: no ksCreateDocument, CreateDocumentW, or DocumentParam declarations in directly scanned SDK headers. CreateDocument references exist in KsAPI.h and KsAPICLink headers, not proof of a callable legacy export.
- Fresh SDK-only exact export index is empty; not proof about full runtime.
- Earlier Stage 4 had already inspected the legacy API5 and exact exports across the frozen Linux binaries: run 44724144842, job 136247160034, EXACT_LEGACY_EXPORT_FOUND=0, RESULT=LEGACY_API5_NOT_EXPOSED_BY_LINUX_V25_RUNTIME. Export probe run 44693532386 also exists. The research premise that C/D had never been investigated was incomplete.
- A/B candidate script stage7/factory_ab_candidate.py prepared. It is not native smoke acceptance; it checks only factory/save/reopen. It must not be run until independently verified lawful entitlement exists. It does not activate license or implement geometry mutation.
- No proof of existing Invisible entitlement for paid work or hosted runner. No production execution, no native file, no acceptance. Do not treat a module flag or environment flag as license evidence.
- No new expenses. No repeat of STEP gates.

RESULT=SDK_STATIC_AUDIT_ONLY_NO_NATIVE_PASS
