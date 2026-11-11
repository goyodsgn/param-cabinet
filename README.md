# param-cabinet

AI-generated parametric CAD: a base cabinet whose doors and hinges follow size rules.

Work in progress. Step 1 is the hand-written reference model (`cabinet_reference.py`):
change width and height, and the number of doors and hinges follows the rules.

| Rule | Example value |
| --- | --- |
| Max door width | 600 mm (more doors when exceeded) |
| Gap between doors | 3 mm |
| Hinges per door | 2 up to 900 mm door height, 3 up to 1600 mm, 4 above |
| First hinge from door edge | 100 mm |

Every push runs the tests on GitHub Actions and builds sample cabinets (STEP, STL, SVG)
as a downloadable artifact.

## Preview

![1200 x 850, two doors](previews/cabinet_1200x850.svg)
![2400 x 1700, four doors](previews/cabinet_2400x1700.svg)

Rule check results for each size: [previews/summary.txt](previews/summary.txt)
