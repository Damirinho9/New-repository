# Work 4 - variant 16 - verified source basis

## Source provenance

Original methodology file from order 7335493:
- file: `Компьютерное моделирование в машиностроении.doc`
- SHA-256: `c8cf9bc3b26df5b86e97d0341a248e176c9296aebe8fa553299ebde24eace612`
- source order archive SHA-256: `0f3ed71ce72ce20df6bdfafdda3601eba66ba38d64642909256e13468ae0a0fe`
- supplied practical-tasks archive SHA-256: `66750405755b111a9e94baf719af83e7105fff675552c795bca7e7510e7186d8`


## Exact assignment

The source methodology "Компьютерное моделирование в машиностроении", checked assignment 4, table 3.1 defines variant 16 as:

"Подшипник роликовый радиально-упорный с коническими роликами двухрядный с двойным внутренним кольцом".

Table 3.2 maps the first surname letter "С" to variant 16.

The source sketch for variant 16 shows:
- two opposed rows of tapered rollers;
- one double inner ring spanning both rows;
- two separate outer cups/rings, one for each row;
- letter dimensions D, d, B, C, T and R.

This topology is mandatory. The previous delivered Work 4 set is not accepted as a source because it contains one outer-ring M3D and two inner-ring M3D files, which is the opposite topology (variant 15 style).

## Methodology requirements retained in this implementation

The methodology requires a real parametric model and describes a bearing example with:
- assembly master/control sketch;
- assembly variables and dependent variables;
- detail variables visible from the assembly;
- parts built from master geometry / linked variables;
- roller and rivet circular arrays;
- a two-half cage connected by rivets;
- rebuild verification after changing a controlling variable.

For the cage the source gives:
- D1 = ROUND((d_vn + d_nar)/2 + 0.6*d_rol) = 102 mm for the adopted nominal set
- D2 = ROUND((d_vn + d_nar)/2 - 0.3*d_rol) = 91 mm for the adopted nominal set
- h = S + b_rol/2
- cell diameter = d_rol + 2*S
- rivet-hole pitch diameter = (D1 + D2)/2
- rivet angular offset = 360/(2*N_rol)
- rivet diameter = ROUND((ROUND(D1)-ROUND(D2))/6)*0.8

## Nominal parameter set

The methodology example itself shows:
- d_nar = 120 mm
- d_vn = 70 mm
- b_rol = 12 mm
- d_rol = 12 mm
- N_rol = 13
- S = 0.6 mm
- z = (d_vn + d_nar)/4 = 47.5 mm

Variant table 3.1 does not provide a separate numerical table for variant 16. Therefore these source-example values are used as the nominal academic parameter set.

For the two-row variant the following selected constructive widths are used:
- T = 40 mm - total double-inner-ring width / controlling rebuild dimension;
- C = T = 40 mm - total outer-cup envelope;
- B = T/2 = 20 mm - one-row axial envelope;
- R = 2 mm - selected ring fillet;
- roller contact-axis angle = 15 deg - selected symmetric opposed-row angle.

Selected values are explicitly marked as selections; they are not represented as values printed in table 3.1.

## Native file contract

Required native models:
- Work4_V16_InnerDoubleRing.m3d
- Work4_V16_OuterCup_L.m3d
- Work4_V16_OuterCup_R.m3d
- Work4_V16_TaperRoller.m3d
- Work4_V16_CageHalf.m3d
- Work4_V16_Rivet.m3d
- Work4_V16_Bearing.a3d

The assembly must contain:
- one double inner ring;
- two external outer cups;
- two opposed rows of tapered rollers, N_rol instances per row;
- two two-half cage sets;
- rivet arrays;
- MASTER_GEOMETRY_V16;
- assembly variables and component external-variable links.

## Strict rebuild acceptance

The test changes only the main assembly variable T:
1. save nominal state;
2. reopen;
3. T = 44 mm;
4. rebuild the assembly without regenerating files from Python geometry;
5. require physical mass and/or bounding-envelope change in T-driven ring components;
6. save, close and reopen the changed state;
7. restore T = 40 mm;
8. rebuild;
9. require nominal masses/envelope to return;
10. save, close and reopen again.

Only after that may the workflow emit PASS_NATIVE_WORK4_VARIANT16.
