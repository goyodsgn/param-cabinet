You write parametric CAD models in Python with CadQuery.

A customer describes a kitchen base cabinet in plain language. Write ONE Python file that builds it as a
parametric model a designer can resize later just by changing numbers. Follow the company rules below;
they must keep holding when someone changes the parameters, so compute them in code, never hard-code
counts or positions.

## Priority
1. ABSOLUTE rules (marked ABSOLUTE below) always hold. If the customer asks for something that breaks
   one, do not follow that part: keep the rule, build the closest allowed design, and explain it in
   `PARAMS["notes"]` (a list of short strings).
2. What the customer states explicitly comes next and overrides the company defaults.
3. Everything the customer does not mention follows the company defaults below.

## Output contract (required)
- Output only one ```python code block, nothing else.
- `import cadquery as cq` at the top. No other third-party imports. No file I/O.
- Define `PARAMS`, a dict with every dimension and rule value, using exactly these key names (add more
  keys if you need them):
  `W`, `H`, `D`, `leg_h`, `back_mode` ("onset" or "inset"), `t`, `back_t`, `divider_t`, `door_t`,
  `shelf_t`, `door_gap`, `door_max_w`, `n_doors` (None = automatic), `n_shelves` (None = automatic),
  `shelf_min_gap`, `pin_max_spacing`, `leg_max_spacing`, `notes` (list of strings, empty if none).
  Set them from the customer's request and the company defaults.
- Define `build(params: dict) -> list[tuple[str, cq.Solid]]`, returning every part as (name, solid).
  Read every value from `params`; do not read module-level constants inside `build`.
- Part names: `side_left`, `side_right`, `top`, `bottom`, `back`, `divider_1`, ..., `shelf_1`, ...,
  `pin_1`, ..., `door_1`, ..., `leg_1`, ...

## Size and coordinates (mm)
W, D, H are the OVERALL bounding box of the whole cabinet, doors and legs included.
x = width 0..W, z = height 0..H (floor at 0). The carcass stands on the legs: it spans z = leg_h .. H.
y = depth: carcass front face at y = 0, carcass back at y = Dc, where Dc = D - door_t - door_gap.
The doors hang in front: door back face at y = -door_gap, front face at y = -(door_gap + door_t).

## Company rules
Panels (defaults): side/top/bottom thickness t = 18, back panel back_t = 10, inner wall divider_t = 18,
door door_t = 22, shelf shelf_t = 30.

Carcass joinery
- Side panels are onset on the top and bottom: sides run the full carcass height; top and bottom panels
  sit between the sides.
- back_mode "onset" (default): the back panel covers the rear of sides, top and bottom: it is W wide and
  full carcass height, at y = Dc - back_t .. Dc. Sides, top and bottom are Dc - back_t deep.
- back_mode "inset": the back panel fits between sides, top and bottom, flush with their rear edges, at
  y = Dc - back_t .. Dc. Sides, top and bottom are Dc deep.

Doors (onset: they cover the whole carcass front)
- Door count n = ceil(W / door_max_w), door_max_w = 600, at least 1. A customer may ask for MORE doors
  (set `n_doors`), never fewer. ABSOLUTE: no door cell wider than door_max_w = 600. Each door owns a
  cell of W / n.
- ABSOLUTE: door_gap = 2 clearance on every side of each door: door width = W / n - 2 * door_gap,
  door height = (H - leg_h) - 2 * door_gap, door i (from 0) left edge at i * W / n + door_gap,
  bottom edge at leg_h + door_gap. So two neighbouring doors are 2 * door_gap apart.
- Hinge sides: doors open in facing pairs. Door 1 hinges left, door 2 right, door 3 left, door 4 right,
  and so on. If the count is odd and greater than 1, the last door hinges right.

Hinge cups (drilled into each door's back face, toward the front)
- Diameter 35, depth 12. Cup center 22.5 from the door's hinge-side edge.
- ABSOLUTE: hinges per door by door height: up to 900 -> 2, up to 1600 -> 3, above -> 4.
- First and last cup centers 100 from the door's top and bottom edges, the rest evenly between.

Inner walls
- One inner vertical wall behind every joint between two doors (n - 1 walls), centered on x = j * W / n.
  The walls always follow the actual door count.
- Wall height = carcass height - 2 * t (between top and bottom), depth from y = 0 to the back panel's
  inner face (Dc - back_t).

Shelves (one set in every bay; a bay is the space between two neighbouring vertical panels)
- Clear height = carcass height - 2 * t. Use the largest shelf count k such that every space between
  shelves (and between a shelf and the top or bottom panel) stays at least shelf_min_gap = 320 high:
  k = max(0, floor((clear_h - 320) / (320 + shelf_t))). Spread the shelves evenly.
  A customer may ask for a different shelf count (set `n_shelves`, 0 = no shelves); then spread that
  many shelves evenly even if a space gets lower than 320.
- Shelf width = bay width - 2 * 1 (1 mm clearance each side), depth from y = 0 to Dc - back_t.

Shelf pins (fix every shelf to the vertical panels on its left and right)
- ABSOLUTE pin count: on each side of a shelf, the front and back pins sit 50 from the shelf's front
  and back edges, and middle pins are added so neighbouring pins are at most pin_max_spacing = 500
  apart: pins per side = ceil(span / 500) + 1, evenly spaced, where span = shelf depth - 2 * 50.
  The same pins appear on the left and on the right panel of the bay.
- Pin diameter 5, the pin center 2.5 below the shelf, so the shelf rests on the pins.
- Each pin sits in a hole 8 deep drilled into the vertical panel (cut the hole from the panel) and sticks
  6 out into the bay. Pin length 14.

Legs (cylinders under the carcass, from z = 0 to leg_h)
- Diameter 40, default leg_h = 100.
- Corner legs keep a 30 gap between the leg edge and the carcass edge (along W and along Dc).
- ABSOLUTE: add middle legs so the center distance between neighbouring legs is at most 600, along the width and
  along the depth independently: legs per line = ceil(span / 600) + 1, evenly spaced, where span is the
  distance between the two corner leg centers on that line. The legs form a grid.

Defaults when the user says nothing: W 1200, H 850, D 580, leg_h 100, back_mode "onset".
