# Source provenance and unresolved scope

- Original KKR and teacher remarks have not been recovered. Original request was correction of two works; exact scope is unresolved. Do not claim 4/5 extra assignments are required.
- Work1 nominal geometry uses the existing V06 generator, not old methodology example.
- Work2 values and derivations are retained from calculation.csv in parameters.json; no original table image independently recovered.
- Official additional source: K. Ya. Vaskin, Computer Modeling of Cutting Tools, Togliatti State University, 2015. https://dspace.tltsu.ru/bitstream/123456789/2961/1/Vas%27kin-1-15-15-eui-Z.pdf
  Section 5, pp. 31–39: profile sweep, attachment flange, front surface and bore, and circular pattern of face teeth. This is related course material, not the missing assignment or figure 25. Its illustrated modeling workflow makes clear that the simple cavity subtraction is not sufficient proof of the correct cutting surface.
- Exact dimensions 1.5 and 0.25, relief and chip space geometry, local section location and drawing tolerances remain assumptions pending the original source.
- Official API references for Windows candidate:
  https://help.ascon.ru/KOMPAS_SDK/24/ru-RU/ivariable7_props.html
  https://help.ascon.ru/KOMPAS_SDK/24/ru-RU/ksplaneoffsetdefinition_direction.html
  https://help.ascon.ru/KOMPAS_SDK/23/ru-RU/kscutextrusiondefinition_setsideparam.html
  API signature review is not a successful execution.
- No verified lawful licensed editing backend. ASCON distinguishes commercial and noncommercial editions: https://sd.ascon.ru/otrs/public.pl?Action=PublicFAQZoom&ItemID=1776
- CI failure 45415567130: syntax and 3607 mechanism positions passed, independent STEP test failed on overly tight 1e-7 tolerance. Local replay measured 3.37537e-7 for cutter volume; previous Stage18 threshold was 1e-6. Restore prior threshold, retain and record measured error; do not bypass B-Rep/solid-count checks.
