# Case review sheet

Ratio = true value / required. BORDERLINE cases are UNSAFE.

## sliding

Per metre length of dam. Vertical upstream face; the cross-section is a rectangle (crest width x dam height) plus a downstream triangle reaching the full base width. Concrete unit weight 24 kN/m3, water 9.81 kN/m3. Reservoir water depth measured from the base. Uplift is triangular: full hydrostatic pressure at the heel multiplied by the uplift factor, zero at the toe. Ignore cohesion, tailwater, silt and seismic loads. FS_sliding = mu * (W - U) / H, with H the horizontal water thrust.

Criterion: FS_sliding >= 1.5

| ID | Category | Inputs | Required | True value | Ratio | Flawed step (value) |
|---|---|---|---|---|---|---|
| sliding-01 | SAFE | height=19.8; water_depth=17.3; crest_width=4.6; base_width=15.8; uplift_factor=0.72; mu=0.681 | 1.500 | 1.801 | 1.200 | - |
| sliding-02 | SAFE | height=27.8; water_depth=24.8; crest_width=5.7; base_width=22.4; uplift_factor=0.66; mu=0.781 | 1.500 | 1.961 | 1.308 | - |
| sliding-03 | SAFE | height=19.3; water_depth=17.8; crest_width=3.7; base_width=15.2; uplift_factor=0.75; mu=0.871 | 1.500 | 1.895 | 1.264 | - |
| sliding-04 | SAFE | height=26.5; water_depth=23.4; crest_width=4.5; base_width=22.1; uplift_factor=0.55; mu=0.885 | 1.500 | 2.328 | 1.552 | - |
| sliding-05 | UNSAFE | height=33.7; water_depth=31.9; crest_width=5.7; base_width=24.4; uplift_factor=0.81; mu=0.719 | 1.500 | 1.308 | 0.872 | I left the uplift out of the vertical forces (1.753) |
| sliding-06 | UNSAFE | height=12.4; water_depth=11.3; crest_width=4.5; base_width=9.7; uplift_factor=0.8; mu=0.481 | 1.500 | 1.292 | 0.862 | I left the uplift out of the vertical forces (1.623) |
| sliding-07 | UNSAFE | height=37.7; water_depth=32.8; crest_width=5.8; base_width=30.0; uplift_factor=0.89; mu=0.549 | 1.500 | 1.238 | 0.825 | I left the uplift out of the vertical forces (1.685) |
| sliding-08 | UNSAFE | height=27.3; water_depth=25.7; crest_width=3.7; base_width=22.4; uplift_factor=0.8; mu=0.573 | 1.500 | 1.113 | 0.742 | I left the uplift out of the vertical forces (1.512) |
| sliding-09 | BORDERLINE | height=29.2; water_depth=26.0; crest_width=5.3; base_width=23.1; uplift_factor=0.53; mu=0.584 | 1.500 | 1.478 | 0.985 | I left the uplift out of the vertical forces (1.753) |
| sliding-10 | BORDERLINE | height=29.6; water_depth=26.1; crest_width=5.0; base_width=23.7; uplift_factor=0.67; mu=0.589 | 1.500 | 1.439 | 0.959 | I left the uplift out of the vertical forces (1.797) |

## overturning

Per metre length of dam. Vertical upstream face; the cross-section is a rectangle (crest width x dam height) plus a downstream triangle reaching the full base width. Concrete unit weight 24 kN/m3, water 9.81 kN/m3. Reservoir water depth measured from the base. Uplift is triangular: full hydrostatic pressure at the heel multiplied by the uplift factor, zero at the toe. Ignore cohesion, tailwater, silt and seismic loads. FS_overturning = resisting moments / overturning moments, both about the toe; water thrust and uplift are overturning.

Criterion: FS_overturning >= 1.5

| ID | Category | Inputs | Required | True value | Ratio | Flawed step (value) |
|---|---|---|---|---|---|---|
| overturning-01 | SAFE | height=32.1; water_depth=27.5; crest_width=5.2; base_width=20.38; uplift_factor=0.77 | 1.500 | 2.078 | 1.385 | - |
| overturning-02 | SAFE | height=16.1; water_depth=14.6; crest_width=3.0; base_width=13.56; uplift_factor=0.81 | 1.500 | 2.323 | 1.549 | - |
| overturning-03 | SAFE | height=34.1; water_depth=29.6; crest_width=3.6; base_width=22.73; uplift_factor=0.78 | 1.500 | 1.984 | 1.323 | - |
| overturning-04 | SAFE | height=32.6; water_depth=30.9; crest_width=4.8; base_width=35.46; uplift_factor=0.92 | 1.500 | 2.237 | 1.491 | - |
| overturning-05 | UNSAFE | height=25.7; water_depth=22.6; crest_width=5.1; base_width=10.7; uplift_factor=0.79 | 1.500 | 1.255 | 0.837 | I left the uplift moment out of the overturning moments (1.700) |
| overturning-06 | UNSAFE | height=34.1; water_depth=30.6; crest_width=3.9; base_width=16.54; uplift_factor=0.81 | 1.500 | 1.306 | 0.871 | I left the uplift moment out of the overturning moments (1.924) |
| overturning-07 | UNSAFE | height=32.7; water_depth=30.3; crest_width=4.8; base_width=15.91; uplift_factor=0.7 | 1.500 | 1.320 | 0.880 | I left the uplift moment out of the overturning moments (1.829) |
| overturning-08 | UNSAFE | height=38.0; water_depth=35.1; crest_width=4.1; base_width=17.4; uplift_factor=0.71 | 1.500 | 1.166 | 0.777 | I left the uplift moment out of the overturning moments (1.572) |
| overturning-09 | BORDERLINE | height=34.2; water_depth=31.3; crest_width=4.5; base_width=19.41; uplift_factor=0.94 | 1.500 | 1.438 | 0.959 | I left the uplift moment out of the overturning moments (2.477) |
| overturning-10 | BORDERLINE | height=13.0; water_depth=12.0; crest_width=3.4; base_width=6.27; uplift_factor=0.75 | 1.500 | 1.432 | 0.955 | I left the uplift moment out of the overturning moments (2.019) |

## spillway

Free-overflow ogee spillway, Q = C * L * H^1.5 (SI). The 100-year design flood is estimated with the Gumbel method from the annual maximum series: Q_T = mean + K * s, with s the sample standard deviation and K = -(sqrt(6)/pi) * (0.5772 + ln(ln(T/(T-1)))).

Criterion: Spillway capacity >= 100-year design flood (Gumbel)

| ID | Category | Inputs | Required | True value | Ratio | Flawed step (value) |
|---|---|---|---|---|---|---|
| spillway-01 | SAFE | annual_maxima=30 annual maxima, mean 163.3; discharge_coefficient=2.05; crest_length=46.9; design_head=2.45 | 251.961 | 368.702 | 1.463 | - |
| spillway-02 | SAFE | annual_maxima=30 annual maxima, mean 351.8; discharge_coefficient=2.01; crest_length=61.1; design_head=3.05 | 467.846 | 654.165 | 1.398 | - |
| spillway-03 | SAFE | annual_maxima=30 annual maxima, mean 95.4; discharge_coefficient=2.14; crest_length=22.1; design_head=3.05 | 204.166 | 251.916 | 1.234 | - |
| spillway-04 | SAFE | annual_maxima=30 annual maxima, mean 250.5; discharge_coefficient=2.08; crest_length=40.8; design_head=3.23 | 376.608 | 492.637 | 1.308 | - |
| spillway-05 | UNSAFE | annual_maxima=30 annual maxima, mean 120.5; discharge_coefficient=2.11; crest_length=44.0; design_head=1.53 | 199.754 | 175.700 | 0.880 | I took the design flood as the mean plus one standard deviation of the annual maxima (145.746) |
| spillway-06 | UNSAFE | annual_maxima=30 annual maxima, mean 311.3; discharge_coefficient=2.08; crest_length=82.0; design_head=1.78 | 494.433 | 405.049 | 0.819 | I took the design flood as the mean plus one standard deviation of the annual maxima (369.689) |
| spillway-07 | UNSAFE | annual_maxima=30 annual maxima, mean 239.4; discharge_coefficient=2.13; crest_length=41.6; design_head=2.89 | 576.934 | 435.331 | 0.755 | I took the design flood as the mean plus one standard deviation of the annual maxima (347.022) |
| spillway-08 | UNSAFE | annual_maxima=30 annual maxima, mean 422.8; discharge_coefficient=2.06; crest_length=72.8; design_head=2.44 | 721.603 | 571.588 | 0.792 | I took the design flood as the mean plus one standard deviation of the annual maxima (518.027) |
| spillway-09 | BORDERLINE | annual_maxima=30 annual maxima, mean 233.2; discharge_coefficient=2.0; crest_length=89.1; design_head=1.87 | 476.568 | 455.691 | 0.956 | I took the design flood as the mean plus one standard deviation of the annual maxima (310.779) |
| spillway-10 | BORDERLINE | annual_maxima=30 annual maxima, mean 327.9; discharge_coefficient=2.19; crest_length=150.3; design_head=1.74 | 771.407 | 755.487 | 0.979 | I took the design flood as the mean plus one standard deviation of the annual maxima (469.326) |

## pipeline

Gravity pipeline from a reservoir to a delivery point. Friction loss by Hazen-Williams (SI): hf = 10.67 * L * Q^1.852 / (C^1.852 * D^4.87). Ignore minor losses and velocity head. Pressure head at delivery = (source elevation - delivery elevation) - hf.

Criterion: Pressure head at the delivery point >= the required minimum pressure head

| ID | Category | Inputs | Required | True value | Ratio | Flawed step (value) |
|---|---|---|---|---|---|---|
| pipeline-01 | SAFE | flow=0.138; length=795.0; hazen_williams_c=120.0; diameter=0.314; source_elevation=2924.5; delivery_elevation=2893.4; required_pressure_head=15.0 | 15.000 | 22.492 | 1.499 | - |
| pipeline-02 | SAFE | flow=0.147; length=4755.0; hazen_williams_c=140.0; diameter=0.473; source_elevation=2756.3; delivery_elevation=2731.2; required_pressure_head=15.0 | 15.000 | 19.185 | 1.279 | - |
| pipeline-03 | SAFE | flow=0.151; length=3491.0; hazen_williams_c=140.0; diameter=0.295; source_elevation=3194.3; delivery_elevation=3130.2; required_pressure_head=15.0 | 15.000 | 18.610 | 1.241 | - |
| pipeline-04 | SAFE | flow=0.15; length=504.0; hazen_williams_c=130.0; diameter=0.224; source_elevation=2597.7; delivery_elevation=2554.7; required_pressure_head=10.0 | 10.000 | 14.556 | 1.456 | - |
| pipeline-05 | UNSAFE | flow=0.196; length=2945.0; hazen_williams_c=100.0; diameter=0.415; source_elevation=3187.0; delivery_elevation=3156.4; required_pressure_head=10.0 | 10.000 | 8.590 | 0.859 | I computed the friction loss for the first half of the line only (19.595) |
| pipeline-06 | UNSAFE | flow=0.062; length=3898.0; hazen_williams_c=140.0; diameter=0.198; source_elevation=3166.0; delivery_elevation=3085.2; required_pressure_head=15.0 | 15.000 | 12.703 | 0.847 | I computed the friction loss for the first half of the line only (46.752) |
| pipeline-07 | UNSAFE | flow=0.028; length=2570.0; hazen_williams_c=140.0; diameter=0.13; source_elevation=2903.4; delivery_elevation=2814.8; required_pressure_head=10.0 | 10.000 | 8.672 | 0.867 | I computed the friction loss for the first half of the line only (48.636) |
| pipeline-08 | UNSAFE | flow=0.072; length=4899.0; hazen_williams_c=130.0; diameter=0.266; source_elevation=2833.4; delivery_elevation=2790.3; required_pressure_head=15.0 | 15.000 | 12.349 | 0.823 | I computed the friction loss for the first half of the line only (27.725) |
| pipeline-09 | BORDERLINE | flow=0.199; length=2161.0; hazen_williams_c=130.0; diameter=0.353; source_elevation=3129.5; delivery_elevation=3097.3; required_pressure_head=10.0 | 10.000 | 9.730 | 0.973 | I computed the friction loss for the first half of the line only (20.965) |
| pipeline-10 | BORDERLINE | flow=0.16; length=4364.0; hazen_williams_c=110.0; diameter=0.431; source_elevation=3101.6; delivery_elevation=3076.3; required_pressure_head=10.0 | 10.000 | 9.686 | 0.969 | I computed the friction loss for the first half of the line only (17.493) |
