# Step 4 robustness: 30 sizes per model (seed 0)

Each model is resized to the same sizes (6 extreme cases + random). A size is skipped when
the reference itself is invalid there for that model's own settings.

| model | pass | tested | pass rate | most common failure |
|---|---|---|---|---|
| examples/reference_generated.py (reference) | 30 | 30 | 100% |  |
| generated/01.py | 30 | 30 | 100% |  |
| generated/02.py | 30 | 30 | 100% |  |
| generated/03.py | 30 | 30 | 100% |  |
| generated/04.py | 30 | 30 | 100% |  |
| generated/05.py | 30 | 30 | 100% |  |
| generated/06.py | 30 | 30 | 100% |  |
| generated/07.py | 30 | 30 | 100% |  |
| generated/08.py | 30 | 30 | 100% |  |
| generated/09.py | 30 | 30 | 100% |  |
| generated/10.py | 30 | 30 | 100% |  |
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

**All generated models: 628 / 638 resized samples pass (98%)**

Failures by check (generated models):

- hinge_sides: 10

Example failures:

| model | W | H | D | leg_h | back | failed | error |
|---|---|---|---|---|---|---|---|
| generated_priority/10.py | 1800 | 1704 | 580 | 100 | inset | hinge_sides |  |
| generated_priority/10.py | 1696 | 1832 | 547 | 121 | onset | hinge_sides |  |
| generated_priority/10.py | 1392 | 1741 | 934 | 153 | inset | hinge_sides |  |
| generated_priority/10.py | 1415 | 912 | 470 | 173 | onset | hinge_sides |  |
| generated_priority/10.py | 1464 | 1887 | 415 | 72 | onset | hinge_sides |  |
| generated_priority/08.py | 1800 | 1704 | 580 | 100 | inset | hinge_sides |  |
| generated_priority/08.py | 1696 | 1832 | 547 | 121 | onset | hinge_sides |  |
| generated_priority/08.py | 1392 | 1741 | 934 | 153 | inset | hinge_sides |  |
| generated_priority/08.py | 1415 | 912 | 470 | 173 | onset | hinge_sides |  |
| generated_priority/08.py | 1464 | 1887 | 415 | 72 | onset | hinge_sides |  |
