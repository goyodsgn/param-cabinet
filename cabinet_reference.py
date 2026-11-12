"""
Parametric base cabinet - reference model (written by hand, used as the answer key).

Structure
  1. Params          : values a person changes (dimensions + rule values)
  2. compute_layout  : rule calculation (doors, hinges, dividers, shelves, pins, legs) - no CAD needed
  3. validate        : breakage checks (reused by the robustness test)
  4. build           : 3D geometry with CadQuery
  5. __main__        : print the layout and export STEP / STL / PNG

Size convention: W, D, H are the overall bounding box of the whole cabinet, doors and legs included.

Coordinates (mm): x = width (0 .. W), z = height (floor at 0, top at H).
y = depth: the carcass front face is at y = 0 and its back at y = Dc. The doors hang in front of it,
door_gap away from the carcass, so the cabinet spans y = -(door_gap + door_t) .. Dc, which is D long.

Rule priority
- Absolute rules (customers cannot change them): door width per door <= door_max_w (600), hinge count
  by door height, shelf pin count by shelf depth, door_gap (2), leg spacing <= leg_max_spacing (600).
- Everything else is a company default that a customer request may override, e.g. n_doors (more doors
  than the minimum), n_shelves, back_mode, thicknesses, leg_h.

Joinery
- Doors are onset (overlay) on the whole carcass front.
- Bottom panel sits between the side panels.
- Top panel: top_mode "inset" (default, between the sides), "onset" (covers the top of the sides, W wide)
  or "none" (no top panel at all, e.g. a sink cabinet; the worktop goes on later).
- Back panel is onset (covers the rear of sides, top and bottom) or inset (fits between them).

Door arrangement
- door_layout lists the doors in each bay from left to right, e.g. [1, 2] = a single door on the left and
  a double door (pair) on the right. All door cells are W / n wide; an inner wall stands only between
  bays. None = every door is its own bay (a wall behind every door joint).

Inner space
- bottom_clear_min: the lowest space (bottom panel to first shelf) stays at least this high, e.g. for
  albums or encyclopedias. Other spaces still keep shelf_min_gap.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field


# ---------------------------------------------------------------
# 1. Parameters
# ---------------------------------------------------------------
@dataclass
class Params:
    # Overall size (bounding box, mm)
    W: float = 1200.0
    H: float = 850.0
    D: float = 580.0

    # Panels
    t: float = 18.0                   # side / top / bottom panel thickness
    back_t: float = 10.0              # back panel thickness
    back_mode: str = "onset"          # "onset" or "inset"
    top_mode: str = "inset"           # "inset" (between sides), "onset" (covers sides) or "none" (sink)
    divider_t: float = 18.0           # inner vertical wall thickness

    # Doors
    door_t: float = 22.0
    door_gap: float = 2.0             # clearance on every side of each door, and door-to-carcass
    door_max_w: float = 600.0         # one more door (and one more wall) when exceeded
    door_min_w: float = 250.0
    n_doors: int | None = None        # customer override; None = minimum count from door_max_w
    door_layout: list | None = None   # doors per bay, left to right, each 1 or 2; e.g. [1, 2]
    single_door_hinge: str | None = None  # all single doors hinged on one side ("left"/"right"); None = facing pairs

    # Hinges: (door height upper bound, hinge count), first matching band wins
    hinge_rule: list = field(default_factory=lambda: [
        (900.0, 2),
        (1600.0, 3),
        (float("inf"), 4),
    ])
    hinge_edge_offset: float = 100.0  # door top/bottom edge to first/last cup center
    hinge_cup_d: float = 35.0
    hinge_cup_depth: float = 12.0
    hinge_x_offset: float = 22.5      # hinge-side door edge to cup center

    # Shelves
    shelf_t: float = 30.0
    shelf_min_gap: float = 320.0      # every clear space between shelves stays at least this high
    n_shelves: int | None = None      # customer override; None = most shelves that keep shelf_min_gap
    bottom_clear_min: float | None = None  # lowest space at least this high (None = no extra demand)
    shelf_clear: float = 1.0          # side clearance between shelf and vertical panels
    pin_d: float = 5.0                # shelf pin diameter
    pin_hole_depth: float = 8.0       # pin hole depth into the vertical panel
    pin_out: float = 6.0              # pin length sticking out of the panel
    pin_offset: float = 50.0          # first/last pin center from the shelf's front and back edges
    pin_max_spacing: float = 500.0    # max distance between pins along the depth -> more pins

    # Legs
    leg_h: float = 100.0
    leg_d: float = 40.0
    leg_inset: float = 30.0           # carcass edge to leg edge
    leg_max_spacing: float = 600.0    # max center distance between neighbouring legs

    # Derived sizes
    @property
    def Dc(self) -> float:            # carcass depth
        return self.D - self.door_t - self.door_gap

    @property
    def Hc(self) -> float:            # carcass height
        return self.H - self.leg_h

    @property
    def z0(self) -> float:            # carcass bottom
        return self.leg_h

    @property
    def inner_back(self) -> float:    # y of the inner face of the back panel
        return self.Dc - self.back_t

    @property
    def inner_bottom(self) -> float:  # z of the top face of the bottom panel
        return self.z0 + self.t

    @property
    def inner_top(self) -> float:     # z of the underside of the top panel (carcass top with no top)
        return self.z0 + self.Hc - (0 if self.top_mode == "none" else self.t)

    @property
    def clear_h(self) -> float:       # clear inner height
        return self.inner_top - self.inner_bottom


# ---------------------------------------------------------------
# 2. Rule calculation (pure Python)
# ---------------------------------------------------------------
@dataclass
class Door:
    x: float            # left edge
    z: float            # bottom edge
    w: float
    h: float
    hinge_side: str     # "left" or "right"
    hinge_z: list       # cup center heights (absolute z)


@dataclass
class Layout:
    n_doors: int
    groups: list        # doors per bay, left to right
    door_w: float
    door_h: float
    n_hinges: int
    doors: list
    dividers: list      # (x0, x1) of each inner wall
    bays: list          # (x0, x1) clear width between vertical panels
    n_shelves: int      # shelves per bay
    shelf_z: list       # bottom z of each shelf
    legs: list          # (x, y) leg centers
    legs_x: int
    legs_y: int

    def hinge_centers(self, p: Params):
        out = []
        for d in self.doors:
            cx = d.x + p.hinge_x_offset if d.hinge_side == "left" else d.x + d.w - p.hinge_x_offset
            out.append([(cx, z) for z in d.hinge_z])
        return out

    def pins(self, p: Params):
        """Shelf pins as (x_panel_face, direction, y, z): direction +1 means the pin sticks out to +x."""
        out = []
        ys = pin_ys(p)
        for (x0, x1) in self.bays:
            for zb in self.shelf_z:
                zc = zb - p.pin_d / 2
                for y in ys:
                    out.append((x0, +1, y, zc))   # left panel of the bay, pin points right
                    out.append((x1, -1, y, zc))   # right panel of the bay, pin points left
        return out


def min_door_count(p: Params) -> int:
    return max(1, math.ceil(p.W / p.door_max_w))


def door_count(p: Params) -> int:
    """Customer may ask for more doors, never fewer than the absolute minimum.
    With an explicit door_layout the count is what the layout says (validate flags a too-wide door)."""
    if p.door_layout:
        return sum(int(g) for g in p.door_layout)
    return max(p.n_doors or 0, min_door_count(p))


def door_groups(p: Params) -> list:
    if p.door_layout:
        return [int(g) for g in p.door_layout]
    return [1] * door_count(p)


def door_sides(p: Params, groups: list) -> list:
    """All single doors: facing pairs (hinge_sides). With a double door in the layout: each pair opens
    left-right, and a single door hinges on the side of the cabinet it is nearer (middle -> left)."""
    n = sum(groups)
    if all(g == 1 for g in groups):
        if p.single_door_hinge in ("left", "right"):
            return [p.single_door_hinge] * n
        return hinge_sides(n)
    cell = p.W / n
    out, i = [], 0
    for g in groups:
        if g == 2:
            out += ["left", "right"]
        else:
            out.append("left" if (i + 0.5) * cell <= p.W / 2 + 1e-9 else "right")
        i += g
    return out


def shelf_rule_count(p: Params) -> int:
    """Most shelves keeping every space >= shelf_min_gap and the lowest >= bottom_clear_min."""
    low = max(p.bottom_clear_min or 0, p.shelf_min_gap)
    return max(0, math.floor((p.clear_h - low) / (p.shelf_min_gap + p.shelf_t)))


def shelf_positions(p: Params, k: int) -> list:
    """Bottom z of each shelf: spread evenly; if that leaves the lowest space under bottom_clear_min,
    keep the lowest space at bottom_clear_min and spread the rest evenly above it."""
    if k <= 0:
        return []
    base, ch = p.inner_bottom, p.clear_h
    space = (ch - k * p.shelf_t) / (k + 1)
    if p.bottom_clear_min is None or space >= p.bottom_clear_min:
        return [base + space * (i + 1) + p.shelf_t * i for i in range(k)]
    b = p.bottom_clear_min
    rest = (ch - b - k * p.shelf_t) / k
    return [base + b + i * (p.shelf_t + rest) for i in range(k)]


def pin_ys(p: Params) -> list:
    """Pin positions along the depth on each side of a shelf: front and back pins at pin_offset,
    plus middle pins so neighbouring pins are at most pin_max_spacing apart."""
    lo, hi = p.pin_offset, p.inner_back - p.pin_offset
    n = leg_count(hi - lo, p.pin_max_spacing)
    if n == 1:
        return [(lo + hi) / 2]
    return [lo + i * (hi - lo) / (n - 1) for i in range(n)]


def hinge_count(p: Params, door_h: float) -> int:
    for upper, n in p.hinge_rule:
        if door_h <= upper:
            return n
    return p.hinge_rule[-1][1]


def hinge_sides(n: int) -> list:
    """Facing pairs: L R, L R, ... An odd last door (n > 1) hinges right."""
    sides = ["left" if i % 2 == 0 else "right" for i in range(n)]
    if n % 2 == 1 and n > 1:
        sides[-1] = "right"
    return sides


def hinge_positions(p: Params, door_z: float, door_h: float, n: int) -> list:
    if n == 1:
        return [door_z + door_h / 2]
    lo = door_z + p.hinge_edge_offset
    hi = door_z + door_h - p.hinge_edge_offset
    step = (hi - lo) / (n - 1)
    return [lo + i * step for i in range(n)]


def shelf_count(clear_h: float, shelf_t: float, min_gap: float) -> int:
    """Most shelves that keep every space at least min_gap high."""
    return max(0, math.floor((clear_h - min_gap) / (min_gap + shelf_t)))


def leg_count(span: float, max_spacing: float) -> int:
    if span <= 0:
        return 1
    return math.ceil(span / max_spacing) + 1


def leg_axis(p: Params, length: float):
    lo = p.leg_inset + p.leg_d / 2
    hi = length - lo
    n = leg_count(hi - lo, p.leg_max_spacing)
    if n == 1:
        return [length / 2]
    step = (hi - lo) / (n - 1)
    return [lo + i * step for i in range(n)]


def compute_layout(p: Params) -> Layout:
    g = p.door_gap
    groups = door_groups(p)
    n = sum(groups)
    cell = p.W / n
    door_w = cell - 2 * g
    door_h = p.Hc - 2 * g
    nh = hinge_count(p, door_h)
    doors = []
    for i, side in enumerate(door_sides(p, groups)):
        x = i * cell + g
        z = p.z0 + g
        doors.append(Door(x=x, z=z, w=door_w, h=door_h, hinge_side=side,
                          hinge_z=hinge_positions(p, z, door_h, nh)))

    # One inner wall between neighbouring bays (behind every door joint unless two doors form a pair)
    joints, acc = [], 0
    for gcount in groups[:-1]:
        acc += gcount
        joints.append(acc)
    dividers = [(j * cell - p.divider_t / 2, j * cell + p.divider_t / 2) for j in joints]
    edges = [p.t] + [v for d in dividers for v in d] + [p.W - p.t]
    bays = [(edges[2 * i], edges[2 * i + 1]) for i in range(len(edges) // 2)]

    # Shelves in the clear height
    ns = p.n_shelves if p.n_shelves is not None else shelf_rule_count(p)
    shelf_z = shelf_positions(p, ns)

    xs, ys = leg_axis(p, p.W), leg_axis(p, p.Dc)
    legs = [(x, y) for x in xs for y in ys]
    return Layout(n_doors=n, groups=groups, door_w=door_w, door_h=door_h, n_hinges=nh, doors=doors,
                  dividers=dividers, bays=bays, n_shelves=ns, shelf_z=shelf_z,
                  legs=legs, legs_x=len(xs), legs_y=len(ys))


# ---------------------------------------------------------------
# 3. Validation (returns a list of problems; empty list = OK)
# ---------------------------------------------------------------
def validate(p: Params, lay: Layout | None = None) -> list:
    errs = []
    if min(p.W, p.H, p.D, p.t, p.back_t, p.door_t, p.leg_h, p.leg_d, p.divider_t, p.shelf_t) <= 0:
        return ["dimension <= 0"]
    if p.back_mode not in ("onset", "inset"):
        errs.append(f"back_mode must be onset or inset, got {p.back_mode}")
    if p.top_mode not in ("onset", "inset", "none"):
        errs.append(f"top_mode must be onset, inset or none, got {p.top_mode}")
    if p.single_door_hinge not in (None, "left", "right"):
        errs.append(f"single_door_hinge must be left, right or None, got {p.single_door_hinge}")
    if p.door_layout is not None and (not p.door_layout or any(int(g) not in (1, 2) for g in p.door_layout)):
        errs.append(f"door_layout entries must be 1 or 2, got {p.door_layout}")
        return errs
    if p.door_gap < 0:
        errs.append("door gap < 0")
    if p.Dc <= p.back_t + 2 * p.pin_offset:
        errs.append("depth too small for carcass")
    if p.Hc <= 2 * p.t:
        errs.append("height too small for top and bottom panels")
    if p.W <= 2 * p.t:
        errs.append("width too small for two side panels")

    lay = lay or compute_layout(p)

    # Doors
    if lay.n_doors != door_count(p):
        errs.append(f"door count {lay.n_doors} != rule {door_count(p)}")
    if lay.n_doors < min_door_count(p):
        errs.append(f"ABSOLUTE: door wider than {p.door_max_w} ({lay.n_doors} doors for W {p.W:.0f})")
    if lay.door_w < p.door_min_w - 1e-6:
        errs.append(f"door width {lay.door_w:.1f} < min {p.door_min_w}")
    for i, d in enumerate(lay.doors):
        cell_x0 = i * p.W / lay.n_doors
        if abs(d.x - (cell_x0 + p.door_gap)) > 1e-6:
            errs.append(f"door {i}: gap on the left is not {p.door_gap}")
    if abs(lay.door_h - (p.Hc - 2 * p.door_gap)) > 1e-6:
        errs.append("door height does not leave the gap top and bottom")
    if [d.hinge_side for d in lay.doors] != door_sides(p, lay.groups):
        errs.append("hinge sides are not facing pairs")

    # Hinges
    if lay.n_hinges != hinge_count(p, lay.door_h):
        errs.append("ABSOLUTE: hinge count != rule")
    r = p.hinge_cup_d / 2
    for di, (d, cups) in enumerate(zip(lay.doors, lay.hinge_centers(p))):
        for cx, cz in cups:
            if cx - r < d.x - 1e-6 or cx + r > d.x + d.w + 1e-6 or cz - r < d.z - 1e-6 or cz + r > d.z + d.h + 1e-6:
                errs.append(f"door {di}: hinge cup outside the door")
        zs = sorted(z for _, z in cups)
        if any(b - a < p.hinge_cup_d for a, b in zip(zs, zs[1:])):
            errs.append(f"door {di}: hinge cups overlap")
    if p.hinge_cup_depth >= p.door_t:
        errs.append("hinge cup goes through the door")

    # Inner walls: one per extra door, every bay wide enough
    if len(lay.dividers) != len(lay.groups) - 1:
        errs.append(f"{len(lay.dividers)} inner walls for {len(lay.groups)} bays")
    if any(x1 - x0 <= 2 * (p.shelf_clear + p.pin_out) for x0, x1 in lay.bays):
        errs.append("a bay is too narrow")

    # Shelves
    clear_h = p.clear_h
    tops = [p.inner_bottom] + [z + p.shelf_t for z in lay.shelf_z]
    bots = lay.shelf_z + [p.inner_top]
    if p.n_shelves is None:
        if lay.n_shelves != shelf_rule_count(p):
            errs.append("shelf count != rule")
        if any(b - a < p.shelf_min_gap - 1e-6 for a, b in zip(tops, bots)) and lay.n_shelves > 0:
            errs.append("space between shelves < shelf_min_gap")
    if p.bottom_clear_min is not None and bots[0] - tops[0] < p.bottom_clear_min - 1e-6:
        errs.append(f"lowest space {bots[0] - tops[0]:.0f} < bottom_clear_min {p.bottom_clear_min:.0f}")
    elif lay.n_shelves * p.shelf_t >= clear_h:
        errs.append("shelves do not fit")
    ys = pin_ys(p)
    if any(b - a > p.pin_max_spacing + 1e-6 for a, b in zip(ys, ys[1:])):
        errs.append("ABSOLUTE: shelf pins too far apart")
    if p.pin_hole_depth >= p.t or 2 * p.pin_hole_depth >= p.divider_t:
        errs.append("shelf pin holes go through a panel")
    if p.pin_out <= p.shelf_clear:
        errs.append("shelf pins do not reach under the shelf")

    # Legs
    span_x = p.W - 2 * (p.leg_inset + p.leg_d / 2)
    span_y = p.Dc - 2 * (p.leg_inset + p.leg_d / 2)
    if span_x <= 0 or span_y <= 0:
        errs.append("cabinet too small for corner legs")
    else:
        if lay.legs_x != leg_count(span_x, p.leg_max_spacing):
            errs.append("ABSOLUTE: legs along width != rule")
        if lay.legs_y != leg_count(span_y, p.leg_max_spacing):
            errs.append("ABSOLUTE: legs along depth != rule")
    return errs


# ---------------------------------------------------------------
# 4. 3D geometry (CadQuery)
# ---------------------------------------------------------------
def build(p: Params, lay: Layout | None = None):
    """Return a list of (name, cq.Solid)."""
    import cadquery as cq

    lay = lay or compute_layout(p)
    V = cq.Vector
    parts = []
    z0, Hc, Dc, t = p.z0, p.Hc, p.Dc, p.t
    body_d = Dc - p.back_t if p.back_mode == "onset" else Dc

    def box(dx, dy, dz, x, y, z):
        return cq.Solid.makeBox(dx, dy, dz, pnt=V(x, y, z))

    def pin_holes(solid, x_face, direction):
        """Drill shelf pin holes into a vertical panel from its face at x_face."""
        for (xf, d, y, z) in lay.pins(p):
            if abs(xf - x_face) < 1e-6:
                hole = cq.Solid.makeCylinder(p.pin_d / 2, p.pin_hole_depth,
                                             pnt=V(xf, y, z), dir=V(-d, 0, 0))
                solid = solid.cut(hole)
        return solid

    # Carcass
    side_h = Hc - t if p.top_mode == "onset" else Hc
    left = pin_holes(box(t, body_d, side_h, 0, 0, z0), t, +1)
    right = pin_holes(box(t, body_d, side_h, p.W - t, 0, z0), p.W - t, -1)
    parts += [("side_left", left), ("side_right", right)]
    parts.append(("bottom", box(p.W - 2 * t, body_d, t, t, 0, z0)))
    if p.top_mode == "inset":
        parts.append(("top", box(p.W - 2 * t, body_d, t, t, 0, z0 + Hc - t)))
    elif p.top_mode == "onset":
        parts.append(("top", box(p.W, body_d, t, 0, 0, z0 + Hc - t)))
    if p.back_mode == "onset":
        parts.append(("back", box(p.W, p.back_t, Hc, 0, Dc - p.back_t, z0)))
    else:
        parts.append(("back", box(p.W - 2 * t, p.back_t, p.clear_h, t, Dc - p.back_t, p.inner_bottom)))

    # Inner walls
    for i, (x0, x1) in enumerate(lay.dividers):
        wall = box(x1 - x0, p.inner_back, p.clear_h, x0, 0, p.inner_bottom)
        wall = pin_holes(wall, x0, -1)
        wall = pin_holes(wall, x1, +1)
        parts.append((f"divider_{i + 1}", wall))

    # Shelves and pins
    k = 0
    for bi, (x0, x1) in enumerate(lay.bays):
        for zb in lay.shelf_z:
            k += 1
            parts.append((f"shelf_{k}", box(x1 - x0 - 2 * p.shelf_clear, p.inner_back, p.shelf_t,
                                            x0 + p.shelf_clear, 0, zb)))
    for j, (xf, d, y, z) in enumerate(lay.pins(p)):
        start = xf - d * p.pin_hole_depth
        parts.append((f"pin_{j + 1}", cq.Solid.makeCylinder(
            p.pin_d / 2, p.pin_hole_depth + p.pin_out, pnt=V(start, y, z), dir=V(d, 0, 0))))

    # Doors, hung door_gap in front of the carcass, hinge cups drilled from the back face
    y_back = -p.door_gap
    for i, (d, cups) in enumerate(zip(lay.doors, lay.hinge_centers(p))):
        door = box(d.w, p.door_t, d.h, d.x, y_back - p.door_t, d.z)
        for cx, cz in cups:
            door = door.cut(cq.Solid.makeCylinder(p.hinge_cup_d / 2, p.hinge_cup_depth,
                                                  pnt=V(cx, y_back, cz), dir=V(0, -1, 0)))
        parts.append((f"door_{i + 1}", door))

    # Legs
    for i, (x, y) in enumerate(lay.legs):
        parts.append((f"leg_{i + 1}", cq.Solid.makeCylinder(p.leg_d / 2, p.leg_h,
                                                            pnt=V(x, y, 0), dir=V(0, 0, 1))))
    return parts


def check_solids(parts) -> list:
    errs = []
    for name, s in parts:
        if not s.isValid():
            errs.append(f"{name}: invalid solid")
        if s.Volume() <= 0:
            errs.append(f"{name}: zero volume")
    return errs


def bbox_size(parts):
    import cadquery as cq

    bb = cq.Compound.makeCompound([s for _, s in parts]).BoundingBox()
    return bb.xlen, bb.ylen, bb.zlen


def export(parts, stem: str, p: Params | None = None, lay: Layout | None = None):
    import cadquery as cq

    comp = cq.Compound.makeCompound([s for _, s in parts])
    cq.exporters.export(comp, f"{stem}.step")
    cq.exporters.export(comp, f"{stem}.stl")
    if p is not None:
        from render import mesh_of, render

        lay = lay or compute_layout(p)
        cups = [c for door_cups in lay.hinge_centers(p) for c in door_cups]
        title = (f"W {p.W:.0f} x H {p.H:.0f} x D {p.D:.0f} (overall)  ·  {lay.n_doors} door(s), "
                 f"{lay.n_hinges} hinges each  ·  {len(lay.dividers)} wall(s)  ·  "
                 f"{lay.n_shelves} shelf/bay  ·  legs {lay.legs_x}x{lay.legs_y}  ·  back {p.back_mode}  ·  "
                 f"top {p.top_mode}  ·  bays {lay.groups}")
        side_h = p.Hc - p.t if p.top_mode == "onset" else p.Hc
        top = {"inset": [(p.t, p.z0 + p.Hc - p.t, p.W - 2 * p.t, p.t)],
               "onset": [(0, p.z0 + p.Hc - p.t, p.W, p.t)], "none": []}[p.top_mode]
        inside = ([(0, p.z0, p.t, side_h), (p.W - p.t, p.z0, p.t, side_h),
                   (p.t, p.z0, p.W - 2 * p.t, p.t)] + top
                  + [(x0, p.inner_bottom, x1 - x0, p.clear_h) for x0, x1 in lay.dividers]
                  + [(x0 + p.shelf_clear, z, x1 - x0 - 2 * p.shelf_clear, p.shelf_t)
                     for x0, x1 in lay.bays for z in lay.shelf_z])
        render([(n, mesh_of(s)) for n, s in parts if not n.startswith("pin_")],
               (p.W, p.D, p.H), f"{stem}.png", title,
               doors=[(d.x, d.z, d.w, d.h) for d in lay.doors], cups=cups, cup_d=p.hinge_cup_d,
               legs=[(x - p.leg_d / 2, p.leg_d, p.leg_h) for x in sorted({x for x, _ in lay.legs})],
               inside=inside, y_front=-(p.door_gap + p.door_t), side=side_view(p, lay))


def side_view(p: Params, lay: Layout) -> dict:
    """Rectangles (y, z, dy, dz) and pin dots for a side elevation seen from the right,
    looking at the inner face of the left side panel. Front (doors) on the left."""
    body_d = p.Dc - p.back_t if p.back_mode == "onset" else p.Dc
    side_h = p.Hc - p.t if p.top_mode == "onset" else p.Hc
    panels = [(0, p.z0, body_d, side_h)]                                       # left side panel
    if p.top_mode == "onset":
        panels.append((0, p.z0 + p.Hc - p.t, body_d, p.t))
    if p.back_mode == "onset":
        panels.append((p.Dc - p.back_t, p.z0, p.back_t, p.Hc))
    else:
        panels.append((p.Dc - p.back_t, p.inner_bottom, p.back_t, p.clear_h))
    shelves = [(0, z, p.inner_back, p.shelf_t) for z in lay.shelf_z]
    door = (-(p.door_gap + p.door_t), lay.doors[0].z, p.door_t, lay.door_h)
    pins = [(y, z) for (xf, d, y, z) in lay.pins(p) if abs(xf - p.t) < 1e-6]
    legs = [(y - p.leg_d / 2, p.leg_d, p.leg_h) for y in sorted({y for _, y in lay.legs})]
    return {"panels": panels, "shelves": shelves, "door": door, "pins": pins, "legs": legs,
            "pin_d": p.pin_d, "y0": -(p.door_gap + p.door_t), "D": p.D, "H": p.H}


# ---------------------------------------------------------------
# 5. Run
# ---------------------------------------------------------------
def describe(p: Params, lay: Layout) -> str:
    lines = [f"W={p.W:.0f} H={p.H:.0f} D={p.D:.0f} leg_h={p.leg_h:.0f} back={p.back_mode} top={p.top_mode} "
             f"bays={lay.groups}  ->  "
             f"doors {lay.n_doors} x {lay.door_w:.1f} x {lay.door_h:.1f} mm, hinges {lay.n_hinges} per door, "
             f"walls {len(lay.dividers)}, shelves {lay.n_shelves} per bay, pins {len(lay.pins(p))} "
             f"({len(pin_ys(p))} per side), "
             f"legs {lay.legs_x} x {lay.legs_y} = {len(lay.legs)}"]
    for i, d in enumerate(lay.doors):
        zs = ", ".join(f"{z:.0f}" for z in d.hinge_z)
        lines.append(f"  door {i + 1}: x={d.x:.1f}  hinge side={d.hinge_side}  hinge z=[{zs}]")
    return "\n".join(lines)


if __name__ == "__main__":
    import sys

    # usage: python cabinet_reference.py W H D leg_h [back_mode] [out_dir] [top_mode] [door_layout e.g. 1,2]
    #        [bottom_clear_min]
    args = sys.argv[1:]
    p = Params()
    for name, v in zip(["W", "H", "D", "leg_h"], args[:4]):
        setattr(p, name, float(v))
    if len(args) >= 5:
        p.back_mode = args[4]
    out = args[5] if len(args) >= 6 else "."
    if len(args) >= 7:
        p.top_mode = args[6]
    if len(args) >= 8 and args[7] != "-":
        p.door_layout = [int(g) for g in args[7].split(",")]
    if len(args) >= 9:
        p.bottom_clear_min = float(args[8])
    lay = compute_layout(p)
    print(describe(p, lay))
    errs = validate(p, lay)
    print("rules:", "OK" if not errs else errs)
    parts = build(p, lay)
    gerrs = check_solids(parts)
    size = bbox_size(parts)
    if any(abs(a - b) > 1e-3 for a, b in zip(size, (p.W, p.D, p.H))):
        gerrs.append(f"bounding box {size} != (W, D, H)")
    print("geometry:", "OK" if not gerrs else gerrs)
    extra = (f"_top-{p.top_mode}" if p.top_mode != "inset" else "") + \
        (f"_bays-{'-'.join(map(str, lay.groups))}" if p.door_layout else "")
    export(parts, f"{out}/cabinet_{int(p.W)}x{int(p.H)}x{int(p.D)}_{p.back_mode}{extra}", p, lay)
