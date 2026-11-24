# Stage 5: built-in STEP import result

Run: 45391183088; job: 138435004959; artifact: 14918498023.
Artifact SHA256: fcc14f3612de18dbbe64307d75cde5d6977f9135588a3957b973af73d6fc1721.

Actual gate.log:
```
APP КОМПАС-3D Invisible v25
3D_MODULE_ACTIVE
TRY_DOCUMENTS_OPEN_STEP
OPEN_ROUTE_FAIL RuntimeError('NO_DOCUMENT')
PUBLIC_CONVERTER_API ['GetConverter', 'GetConverterByPath']
STEP_CONVERTER_ID -3
BUILTIN_STEP_CONVERTER_CONNECTED
IMPORT_FILTER ('', 0)
IMPORT_COMMAND 0
IMPORT_RC 0 DOCS_BEFORE_AFTER 0 0
```
The SDK connection works; the 3D active flag is true. The native document factory/open route and this particular converter invocation fail. No M3D is produced. The empty filter leaves the import command unconfirmed. This result does not prove that all converter routes are impossible. Do not repeat this identical invocation. API5 LoadFromAdditionFormat is documented but the Linux API5 creation surface was not found in stage4. A future experiment needs a distinct, verified API/edition/backend or confirmed converter configuration. STEP remains intermediate, not accepted native CAD. No commercial license entitlement inferred merely from module flag.
