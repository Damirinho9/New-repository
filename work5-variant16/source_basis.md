# Work 5 - variant 16 - verified source basis

## Exact assignment

Source: original methodology `Компьютерное моделирование в машиностроении.doc`, figure 59r.

Variant 16 is:

**Универсальное зажимное устройство конструкции института "Оргстанкинпром".**

Purpose: clamping workpieces on machine-tool tables.

## Mandatory source construction, positions 1-10

1. **Гайка 1** - lower nut working with the T-slot bolt and fixing the device to the machine table.
2. **Гайка 2** - adjustment nut; also the spring stop.
3. **Прихват 3** - clamping lever. One arm bears on support 10, the other on the workpiece.
4. **Болт 4** - T-slot bolt securing the device to the machine table.
5. **Гидроцилиндр 5** - moving cylinder body.
6. **Шток-поршень 6** - piston rod inside cylinder 5.
7. **Гайка 7** - upper adjustment/stop nut against which the piston rod reacts.
8. **Шайбы 8** - paired spherical and conical washers transmitting force from cylinder 5 to clamp 3 while accommodating angular misalignment.
9. **Пружина 9** - return/preload spring; nut 2 is its support.
10. **Подставка 10** - stepped support under one arm of clamp 3.

A demo workpiece and a machine-table/base representation may be present in the educational assembly, but they are not substitutes for any of positions 1-10.

## Verified operating principle

When working medium is supplied to the lower chamber of hydraulic cylinder 5, piston rod 6 remains stationary because it reacts against nut 7. The **cylinder body moves downward**. Its downward motion transfers the clamping force through the spherical/conical washer pair 8 to clamp 3. One arm of clamp 3 bears on support 10 and the other presses the workpiece.

Clamp height setup is performed by rotating nut 7 and nut 2; nut 2 is also the spring 9 stop.

Therefore the construction check must prove:
- rod/piston 6, nuts 7 and 2, spring 9 and T-slot bolt 4 share the central working axis;
- cylinder 5 surrounds rod/piston 6 and can move axially relative to it;
- washer pair 8 lies between cylinder 5 and clamp 3;
- clamp 3 crosses the central axis, has one end on support 10 and the other over the workpiece;
- support 10 is offset from the working axis;
- T-slot bolt 4 and nut 1 anchor the device to the base/table;
- the assembly is not accepted if the cylinder is fixed while the rod moves as the primary clamping action.

## Source-package cross-check

The previously supplied native Work 5 package contains these matching source files:
- `05_Bolt_T_paza.m3d`
- `05_Gaika_Nizhnyaya.m3d`
- `05_Gaika_Regulirovochnaya.m3d`
- `05_Gaika_Verhnyaya.m3d`
- `05_Gidrocilindr.m3d`
- `05_Opora.m3d`
- `05_Prizhim.m3d`
- `05_Pruzhina.m3d`
- `05_Shaiba_Konicheskaya.m3d`
- `05_Shaiba_Sfericheskaya.m3d`
- `05_Shtok_Porshen.m3d`
- `05_Osnovanie.m3d`
- `05_Zagotovka_Primer.m3d`
- `05_Zazhim_Orgstankinprom_Variant_16.a3d`

The legacy A3D `Sources` table contains relative references to all 13 M3D files above. This proves the old package was at least intended for this exact variant, but it is **not accepted solely on that basis**. Native reopen/rebuild, component enumeration, mate-constraint inspection and construction checks remain mandatory.

## Acceptance

PASS only if:
1. every required M3D opens and rebuilds in KOMPAS;
2. the A3D reopens with all relative dependencies resolved;
3. component composition matches positions 1-10;
4. KOMPAS reports real 3D mate constraints, not only arbitrary placements;
5. the central-axis chain and clamp/support/workpiece arrangement match figure 59r;
6. save -> close -> reopen -> rebuild succeeds;
7. no missing-file dialog / unresolved component remains.

Final marker: `RESULT=PASS_NATIVE_WORK5_VARIANT16_ORGSTANKINPROM`.
