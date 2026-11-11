# Step 4 robustness: 30 sizes per model (seed 0)

Each model is resized to the same sizes (6 extreme cases + random). A size is skipped when
the reference itself is invalid there for that model's own settings.

| model | pass | tested | pass rate | most common failure |
|---|---|---|---|---|
| examples/reference_generated.py (reference) | 30 | 30 | 100% |  |
| generated/01.py | 12 | 30 | 40% | pin_count (18) |
| generated/02.py | 12 | 30 | 40% | pin_count (18) |
| generated/03.py | 12 | 30 | 40% | pin_count (18) |
| generated/04.py | 12 | 30 | 40% | pin_count (18) |
| generated/05.py | 12 | 30 | 40% | pin_count (18) |
| generated/06.py | 12 | 30 | 40% | pin_count (18) |
| generated/07.py | 12 | 30 | 40% | pin_count (18) |
| generated/08.py | 12 | 30 | 40% | pin_count (18) |
| generated/09.py | 12 | 30 | 40% | pin_count (18) |
| generated/10.py | 12 | 30 | 40% | pin_count (18) |
| generated_priority/01.py | 22 | 22 | 100% |  |
| generated_priority/02.py | 30 | 30 | 100% |  |
| generated_priority/03.py | 30 | 30 | 100% |  |
| generated_priority/04.py | 30 | 30 | 100% |  |
| generated_priority/05.py | 30 | 30 | 100% |  |
| generated_priority/06.py | 30 | 30 | 100% |  |
| generated_priority/07.py | 30 | 30 | 100% |  |
| generated_priority/08.py | 25 | 30 | 83% | hinge_sides (5) |
| generated_priority/09.py | 30 | 30 | 100% |  |
| generated_priority/10.py | 25 | 30 | 83% | hinge_sides (5) |
| generated_priority/11.py | 30 | 30 | 100% |  |
| generated_priority/12.py | 16 | 16 | 100% |  |

**All generated models: 448 / 638 resized samples pass (70%)**

Failures by check (generated models):

- pin_count: 180
- hinge_sides: 10

Example failures:

| model | W | H | D | leg_h | back | failed | error |
|---|---|---|---|---|---|---|---|
| generated/01.py | 3600 | 2200 | 1000 | 200 | inset | pin_count |  |
| generated/01.py | 2400 | 850 | 700 | 100 | inset | pin_count |  |
| generated/01.py | 2015 | 979 | 841 | 143 | inset | pin_count |  |
| generated/01.py | 3559 | 1405 | 808 | 140 | onset | pin_count |  |
| generated/01.py | 1392 | 1741 | 934 | 153 | inset | pin_count |  |
| generated/01.py | 3493 | 1311 | 912 | 89 | onset | pin_count |  |
| generated/01.py | 698 | 1928 | 812 | 168 | onset | pin_count |  |
| generated/01.py | 692 | 2188 | 919 | 200 | inset | pin_count |  |
| generated/01.py | 749 | 1437 | 809 | 132 | onset | pin_count |  |
| generated/01.py | 3484 | 1525 | 732 | 117 | inset | pin_count |  |
| generated/01.py | 2361 | 1616 | 660 | 63 | onset | pin_count |  |
| generated/01.py | 3206 | 2070 | 898 | 185 | inset | pin_count |  |
| generated/01.py | 3081 | 1392 | 689 | 85 | onset | pin_count |  |
| generated/01.py | 3264 | 1503 | 967 | 137 | inset | pin_count |  |
| generated/01.py | 1976 | 1590 | 805 | 197 | inset | pin_count |  |
