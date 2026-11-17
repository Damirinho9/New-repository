from __future__ import annotations

import math

# Work 2, variant 19.
# Source: "kompleksnaya-kontrolnaya-rabota-2.docx", task 2 and method pages 14-18, 23-28.

# Variant input, scheme 1 / column 9.
D1 = 80.0
D2 = 70.0
D3 = 50.0
part_l1 = 8.0
part_l2 = 22.0
part_l3 = 12.0
part_l4 = 14.0
L_part = 75.0
R_part = 21.0
S = 0.04
sigma_b = 680.0

# Method tables.
gamma = 10.0       # deg, steel, sigma_b > 600 and <= 800 MPa
alpha = 10.0       # deg, accepted minimum for a round cutter
v = 27.0           # m/min, table 5 at S=0.04 mm/rev
p_z = 190.0        # N/mm, table 5 at S=0.04 mm/rev

# Constructive values selected inside ranges explicitly given by the method.
cutoff_edge = 5.0       # mm, allowed 4...5
cutoff_angle = 15.0     # deg, allowed 15...20
a = 8.0                 # mm, allowed 3...8
overlap = 2.0           # mm, allowed 1...2
end_belt = 2.0          # mm, allowed 1...2
flange_width = 5.0      # mm, allowed 3...5
recess_extra_d = 15.0   # mm, allowed 10...15
recess_length = 15.0    # mm, allowed 10...15
z = 32                  # allowed 32...34

Dmax = max(D1, D2, D3)
Dmin = min(D1, D2, D3)

# The worked example uses l_i' = L_part + 5 mm for the cutoff groove.
l_i = L_part + cutoff_edge
Pz = p_z * l_i

# l_i > 30 mm -> bilateral support, formula (5).
d_calc = 1.36 * (l_i ** 0.33) * (Pz ** 0.25)
d = 65.0  # nearest larger adopted mounting-hole diameter

t = (Dmax - Dmin) / 2.0
e_min = 0.5 * d
e = 35.0  # adopted >= e_min

d_a_calc = 2.0 * (t + a + e + d / 2.0)
axis_distance_x = Dmax / 2.0 + a + e + d / 2.0

# Point A lies at Dmin/2 from the workpiece axis. Rear angle alpha is provided
# by vertical cutter-axis offset. OA is the guide radius used in top-down geometry.
OA_horizontal = axis_distance_x - Dmin / 2.0
axis_offset_y = OA_horizontal * math.tan(math.radians(alpha))
OA = OA_horizontal / math.cos(math.radians(alpha))
guide_diameter = 2.0 * OA

flange_d_min = 1.5 * d
flange_d_max = 1.7 * d
flange_d = 100.0  # adopted inside the allowed interval

overall_length = L_part + cutoff_edge + overlap + end_belt + flange_width
mount_recess_d = d + recess_extra_d
tech_recess_d = d + 2.0

rifling_profile_angle = 90.0
rifling_side_angle = 45.0
rifling_beta = math.degrees(math.atan(math.pi / z))
rifling_angular_pitch = 360.0 / z
rifling_circ_pitch_at_flange_od = math.pi * flange_d / z

assert abs(l_i - 80.0) < 1e-9
assert abs(Pz - 15200.0) < 1e-9
assert 64.0 < d_calc < 65.0
assert d >= d_calc
assert e >= e_min
assert 1.5 * d <= flange_d <= 1.7 * d
assert z in (32, 33, 34)

rows = [
    ("Dmax", Dmax, "mm"),
    ("Dmin", Dmin, "mm"),
    ("gamma", gamma, "deg"),
    ("alpha", alpha, "deg"),
    ("v", v, "m/min"),
    ("p_z", p_z, "N/mm"),
    ("l_i_prime", l_i, "mm"),
    ("Pz", Pz, "N"),
    ("d_calc", d_calc, "mm"),
    ("d_adopted", d, "mm"),
    ("t", t, "mm"),
    ("e_min", e_min, "mm"),
    ("e_adopted", e, "mm"),
    ("d_a_calc", d_a_calc, "mm"),
    ("axis_distance_x", axis_distance_x, "mm"),
    ("axis_offset_y", axis_offset_y, "mm"),
    ("OA", OA, "mm"),
    ("guide_diameter", guide_diameter, "mm"),
    ("flange_d_range_min", flange_d_min, "mm"),
    ("flange_d_range_max", flange_d_max, "mm"),
    ("flange_d_adopted", flange_d, "mm"),
    ("flange_width", flange_width, "mm"),
    ("mount_recess_d", mount_recess_d, "mm"),
    ("mount_recess_length", recess_length, "mm"),
    ("tech_recess_d", tech_recess_d, "mm"),
    ("overall_length", overall_length, "mm"),
    ("rifling_z", z, "pcs"),
    ("rifling_profile_angle", rifling_profile_angle, "deg"),
    ("rifling_beta", rifling_beta, "deg"),
    ("rifling_angular_pitch", rifling_angular_pitch, "deg"),
    ("rifling_circ_pitch_at_flange_od", rifling_circ_pitch_at_flange_od, "mm"),
]

for name, value, unit in rows:
    if isinstance(value, float):
        print(f"{name}={value:.9f} {unit}")
    else:
        print(f"{name}={value} {unit}")

print("RESULT=PASS_WORK2_VARIANT19_CALC")
