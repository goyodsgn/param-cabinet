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
- Side panels are onset on the top and bottom: sides run full height, top/bottom sit between them.
- Back panel is onset (covers the rear of sides, top and bottom) or inset (fits between them).
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
    divider_t: float = 18.0           # inner vertical wall thickness

    # Doors
    door_t: float = 22.0
    door_gap: float = 2.0             # clearance on every side of each door, and door-to-carcass
    door_max_w: float = 600.0         # one more door (and one more wall) when exceeded
    door_min_w: float = 250.0
    n_doors: int | None = None        # customer override; None = minimum count from door_max_w

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
    """Customer may ask for more doors, never fewer than the absolute minimum."""
    return max(p.n_doors or 0, min_door_count(p))


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
    n = door_count(p)
    cell = p.W / n
    door_w = cell - 2 * g
    door_h = p.Hc - 2 * g
    nh = hinge_count(p, door_h)
    doors = []
    for i, side in enumerate(hinge_sides(n)):
        x = i * cell + g
        z = p.z0 + g
        doors.append(Door(x=x, z=z, w=door_w, h=door_h, hinge_side=side,
                          hinge_z=hinge_positions(p, z, door_h, nh)))

    # One inner wall behind every joint between two doors
    dividers = [(j * cell - p.divider_t / 2, j * cell + p.divider_t / 2) for j in range(1, n)]
    edges = [p.t] + [v for d in dividers for v in d] + [p.W - p.t]
    bays = [(edges[2 * i], edges[2 * i + 1]) for i in range(len(edges) // 2)]

    # Shelves, evenly spaced in the clear height
    clear_h = p.Hc - 2 * p.t
    ns = p.n_shelves if p.n_shelves is not None else shelf_count(clear_h, p.shelf_t, p.shelf_min_gap)
    space = (clear_h - ns * p.shelf_t) / (ns + 1)
    shelf_z = [p.z0 + p.t + space * (k + 1) + p.shelf_t * k for k in range(ns)]

    xs, ys = leg_axis(p, p.W), leg_axis(p, p.Dc)
    legs = [(x, y) for x in xs for y in ys]
    return Layout(n_doors=n, door_w=door_w, door_h=door_h, n_hinges=nh, doors=doors,
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
    if [d.hinge_side for d in lay.doors] != hinge_sides(lay.n_doors):
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
    if len(lay.dividers) != lay.n_doors - 1:
        errs.append(f"{len(lay.dividers)} inner walls for {lay.n_doors} doors")
    if any(x1 - x0 <= 2 * (p.shelf_clear + p.pin_out) for x0, x1 in lay.bays):
        errs.append("a bay is too narrow")

    # Shelves
    clear_h = p.Hc - 2 * p.t
    if p.n_shelves is None:
        if lay.n_shelves != shelf_count(clear_h, p.shelf_t, p.shelf_min_gap):
            errs.append("shelf count != rule")
        tops = [p.z0 + p.t] + [z + p.shelf_t for z in lay.shelf_z]
        bots = lay.shelf_z + [p.z0 + p.Hc - p.t]
        if any(b - a < p.shelf_min_gap - 1e-6 for a, b in zip(tops, bots)) and lay.n_shelves > 0:
            errs.append("space between shelves < shelf_min_gap")
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
    left = pin_holes(box(t, body_d, Hc, 0, 0, z0), t, +1)
    right = pin_holes(box(t, body_d, Hc, p.W - t, 0, z0), p.W - t, -1)
    parts += [("side_left", left), ("side_right", right)]
    parts.append(("bottom", box(p.W - 2 * t, body_d, t, t, 0, z0)))
    parts.append(("top", box(p.W - 2 * t, body_d, t, t, 0, z0 + Hc - t)))
    if p.back_mode == "onset":
        parts.append(("back", box(p.W, p.back_t, Hc, 0, Dc - p.back_t, z0)))
    else:
        parts.append(("back", box(p.W - 2 * t, p.back_t, Hc - 2 * t, t, Dc - p.back_t, z0 + t)))

    # Inner walls
    for i, (x0, x1) in enumerate(lay.dividers):
        wall = box(x1 - x0, p.inner_back, Hc - 2 * t, x0, 0, z0 + t)
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
                 f"{lay.n_shelves} shelf/bay  ·  legs {lay.legs_x}x{lay.legs_y}  ·  back {p.back_mode}")
        inside = ([(0, p.z0, p.t, p.Hc), (p.W - p.t, p.z0, p.t, p.Hc),
                   (p.t, p.z0, p.W - 2 * p.t, p.t), (p.t, p.z0 + p.Hc - p.t, p.W - 2 * p.t, p.t)]
                  + [(x0, p.z0 + p.t, x1 - x0, p.Hc - 2 * p.t) for x0, x1 in lay.dividers]
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
    panels = [(0, p.z0, body_d, p.Hc)]                                         # left side panel
    if p.back_mode == "onset":
        panels.append((p.Dc - p.back_t, p.z0, p.back_t, p.Hc))
    else:
        panels.append((p.Dc - p.back_t, p.z0 + p.t, p.back_t, p.Hc - 2 * p.t))
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
    lines = [f"W={p.W:.0f} H={p.H:.0f} D={p.D:.0f} leg_h={p.leg_h:.0f} back={p.back_mode}  ->  "
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

    # usage: python cabinet_reference.py W H D leg_h [back_mode] [out_dir]
    args = sys.argv[1:]
    p = Params()
    for name, v in zip(["W", "H", "D", "leg_h"], args[:4]):
        setattr(p, name, float(v))
    if len(args) >= 5:
        p.back_mode = args[4]
    out = args[5] if len(args) >= 6 else "."
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
    export(parts, f"{out}/cabinet_{int(p.W)}x{int(p.H)}x{int(p.D)}_{p.back_mode}", p, lay)
