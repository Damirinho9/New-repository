# Work 2 - Variant 19 - calculation basis

## 1. Variant input

Variant 19 means scheme 1 and column 9.

| Parameter | Value |
| --- | ---: |
| Material | Steel 60 |
| sigma_b | 680 MPa |
| D1 | 80 mm |
| D2 | 70 mm |
| D3 | 50 mm |
| part l1 | 8 mm |
| part l2 | 22 mm |
| part l3 | 12 mm |
| part l4 | 14 mm |
| L_part | 75 mm |
| R | 21 mm |
| S | 0.04 mm/rev |

The cutter design dimensions below must not be confused with the part-profile dimensions l1...l4 above.

## 2. Cutting geometry

For a round cutter the method allows alpha = 10...12 deg. Adopt the minimum alpha = 10 deg, as in the worked example.

For steel with sigma_b = 680 MPa, table 4 gives gamma = 10 deg.

At S = 0.04 mm/rev, table 5 gives:

- v = 27 m/min;
- p_z = 190 N/mm.

The worked example adds a 5 mm cutoff edge to the part length when defining the cutting-edge projection. Therefore:

l_i' = L_part + 5 = 75 + 5 = 80 mm.

Pz = p_z * l_i' = 190 * 80 = 15200 N.

Since l_i' > 30 mm, the method requires bilateral mounting.

## 3. Mounting hole

For bilateral mounting use formula (5):

d = 1.36 * (l_i')^0.33 * Pz^0.25

d_calc = 64.1238 mm.

Adopt d = 65 mm as the next larger mounting-hole size.

## 4. Profile depth, wall and outside size

Dmax = 80 mm.
Dmin = 50 mm.

t = (Dmax - Dmin) / 2 = 15 mm.

The method requires e >= 0.5d:

e_min = 32.5 mm.

Adopt e = 35 mm.

Adopt a = 8 mm, the upper value from the method range 3...8 mm, matching the method's worked example.

Preliminary outside diameter by formula (6):

d_a ~= 2 * (t + a + e + d/2)
    = 2 * (15 + 8 + 35 + 32.5)
    = 181 mm.

## 5. Cutter-axis position for top-down construction

Horizontal distance between the part and cutter axes:

X_O = Dmax/2 + a + e + d/2
    = 40 + 8 + 35 + 32.5
    = 115.5 mm.

Point A at the minimum workpiece diameter is Dmin/2 = 25 mm from the part axis, hence the horizontal OA projection is:

OA_x = 115.5 - 25 = 90.5 mm.

At alpha = 10 deg:

DeltaY_O = OA_x * tan(alpha) = 15.9576 mm.

Guide-circle radius:

OA = OA_x / cos(alpha) = 91.8961 mm.

Corresponding local guide diameter:

2OA = 183.7922 mm.

This is the geometry to use when building the guide circle in the top-down CAD model.

## 6. Constructive additions

Use the method ranges and the dimensions used in its worked example:

| Element | Adopted value | Method range / basis |
| --- | ---: | --- |
| Cutoff edge axial length | 5 mm | 4...5 mm |
| Cutoff edge angle | 15 deg | 15...20 deg |
| Overlap beyond open workpiece end | 2 mm | 1...2 mm |
| Cylindrical end belt | 2 mm | 1...2 mm |
| Flange width | 5 mm | 3...5 mm |
| Flange diameter allowed | 97.5...110.5 mm | 1.5d...1.7d |
| Flange diameter adopted | 100 mm | inside allowed range |
| Mounting recess diameter | 80 mm | d + 15, allowed d + 10...15 |
| Mounting recess depth | 15 mm | 10...15 mm |
| Technological recess diameter | 67 mm | d + 2 |
| Chamfers | 1 x 45 deg | method section 2.6.7 |
| Chip-space inner fillet | R2 mm | method section 2.6.9 |

Main profiled width l0 is taken as the part length L_part = 75 mm.

Total cutter length by formula (7):

L0 = l0 + 5 + 2 + 2 + 5 = 89 mm.

## 7. Radial rifling

Adopt z = 32, which is inside the required range 32...34 and is the value used in the worked example.

- normal profile angle = 90 deg;
- symmetric side angle = 45 deg;
- beta = atan(pi/z) = 5.607032 deg = approximately 5 deg 36 min 25 sec;
- angular pitch = 360/32 = 11.25 deg;
- circumferential pitch at flange OD 100 mm = pi*100/32 = 9.8175 mm;
- figure 25 profile offsets = 1.5 mm and 0.25 mm.

## 8. Final calculation set for CAD

| Parameter | Final value |
| --- | ---: |
| alpha | 10 deg |
| gamma | 10 deg |
| v | 27 m/min |
| p_z | 190 N/mm |
| l_i' | 80 mm |
| Pz | 15200 N |
| mounting type | bilateral |
| d | 65 mm |
| t | 15 mm |
| a | 8 mm |
| e | 35 mm |
| d_a preliminary | 181 mm |
| part-cutter axis horizontal distance | 115.5 mm |
| cutter-axis vertical offset | 15.9576 mm |
| guide radius OA | 91.8961 mm |
| flange | dia 100 x 5 mm |
| mounting recess | dia 80 x 15 mm |
| technological recess | dia 67 mm |
| total cutter length L0 | 89 mm |
| rifling | 32 teeth, 90 deg profile |
| beta | 5.607032 deg |
| rifling angular pitch | 11.25 deg |

## 9. Important interpretation notes

1. The task-table l1...l4 are dimensions of the machined part profile. The method also uses l1, l2 and l3 for cutter construction. They are intentionally renamed in the calculation files to avoid collisions.
2. The method itself gives ranges for a number of constructive sizes. Values 5, 15, 8, 2, 2 and 5 mm above are explicit selections inside those ranges, following the worked example where possible.
3. Formula (6) gives a preliminary outside size. The actual rear surface is created by the top-down guide-circle geometry, so the CAD model must use the axis position and OA geometry, not replace the generated surface with an arbitrary cylindrical blank.
4. No CAD result is required for the correctness of these calculations. This calculation set is the source of truth for Work 2 modeling.
