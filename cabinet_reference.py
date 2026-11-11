"""
Parametric base cabinet - reference model (written by hand, used as the answer key).

Structure
  1. Params          : values a person changes (dimensions + rule thresholds)
  2. compute_layout  : rule calculation (door count, door width, hinge count/positions) - no CAD needed
  3. validate        : breakage checks (reused later by the robustness test)
  4. build           : 3D geometry with CadQuery
  5. __main__        : print the layout and export STEP / STL / SVG

Coordinates (mm): x = width (left to right), y = depth (front face of the carcass at y=0,
back at y=D, doors sit in front at negative y), z = height (floor at z=0).
The carcass stands on legs, so it spans z = leg_h .. leg_h + H.

The rule numbers (max door width, hinge height bands, ...) are example values.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field


# ---------------------------------------------------------------
# 1. Parameters
# ---------------------------------------------------------------
@dataclass
class Params:
    # Dimensions (mm)
    W: float = 1200.0          # width (front length)
    H: float = 850.0           # carcass height (without legs)
    D: float = 580.0           # depth
    t: float = 18.0            # panel thickness (sides, top, bottom)
    back_t: float = 6.0        # back panel thickness

    # Door rules
    door_max_w: float = 600.0  # max width of one door -> add a door when exceeded
    door_min_w: float = 250.0  # min width of one door (checked by validate)
    door_gap: float = 3.0      # gap between doors and at the outer edges
    door_t: float = 18.0       # door thickness

    # Hinge rule: (door height upper bound, hinge count). First matching band wins.
    hinge_rule: list = field(default_factory=lambda: [
        (900.0, 2),
        (1600.0, 3),
        (float("inf"), 4),
    ])
    hinge_edge_offset: float = 100.0  # distance from door top/bottom to the first hinge
    hinge_cup_d: float = 35.0         # hinge cup diameter
    hinge_cup_depth: float = 12.0     # hinge cup depth
    hinge_x_offset: float = 22.5      # door side edge to cup center

    # Legs
    leg_h: float = 100.0              # leg height (floor to underside of the carcass)
    leg_d: float = 40.0               # leg diameter
    leg_inset: float = 30.0           # gap from the carcass edge to the leg edge
    leg_max_spacing: float = 600.0    # max center distance between legs -> add middle legs


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
    hinge_z: list       # hinge cup center heights (absolute z)


@dataclass
class Layout:
    n_doors: int
    door_w: float
    door_h: float
    n_hinges: int
    doors: list
    legs: list          # (x, y) leg centers
    legs_x: int         # legs along the width
    legs_y: int         # legs along the depth

    def hinge_centers(self, p: Params):
        """(x, z) of every hinge cup, door by door."""
        out = []
        for d in self.doors:
            cx = d.x + p.hinge_x_offset if d.hinge_side == "left" else d.x + d.w - p.hinge_x_offset
            out.append([(cx, z) for z in d.hinge_z])
        return out


def door_count(p: Params) -> int:
    return max(1, math.ceil(p.W / p.door_max_w))


def hinge_count(p: Params, door_h: float) -> int:
    for upper, n in p.hinge_rule:
        if door_h <= upper:
            return n
    return p.hinge_rule[-1][1]


def leg_count(span: float, max_spacing: float) -> int:
    """Legs on one line: corners plus enough middle legs to keep spacing <= max_spacing."""
    if span <= 0:
        return 1
    return math.ceil(span / max_spacing) + 1


def leg_axis(p: Params, length: float):
    """Leg center coordinates along one axis (width or depth)."""
    lo = p.leg_inset + p.leg_d / 2
    hi = length - lo
    n = leg_count(hi - lo, p.leg_max_spacing)
    if n == 1:
        return [length / 2]
    step = (hi - lo) / (n - 1)
    return [lo + i * step for i in range(n)]


def hinge_sides(n: int) -> list:
    """Doors open in facing pairs: L R, L R, ... An odd last door is hinged on the outer right."""
    sides = ["left" if i % 2 == 0 else "right" for i in range(n)]
    if n % 2 == 1:
        sides[-1] = "right" if n > 1 else "left"
    return sides


def hinge_positions(p: Params, door_z: float, door_h: float, n: int) -> list:
    if n == 1:
        return [door_z + door_h / 2]
    lo = door_z + p.hinge_edge_offset
    hi = door_z + door_h - p.hinge_edge_offset
    step = (hi - lo) / (n - 1)
    return [lo + i * step for i in range(n)]


def compute_layout(p: Params) -> Layout:
    n = door_count(p)
    door_w = (p.W - (n + 1) * p.door_gap) / n
    door_h = p.H - 2 * p.door_gap
    nh = hinge_count(p, door_h)
    doors = []
    for i, side in enumerate(hinge_sides(n)):
        x = p.door_gap + i * (door_w + p.door_gap)
        z = p.leg_h + p.door_gap
        doors.append(Door(x=x, z=z, w=door_w, h=door_h, hinge_side=side,
                          hinge_z=hinge_positions(p, z, door_h, nh)))
    xs, ys = leg_axis(p, p.W), leg_axis(p, p.D)
    legs = [(x, y) for x in xs for y in ys]
    return Layout(n_doors=n, door_w=door_w, door_h=door_h, n_hinges=nh, doors=doors,
                  legs=legs, legs_x=len(xs), legs_y=len(ys))


# ---------------------------------------------------------------
# 3. Validation (returns a list of problems; empty list = OK)
# ---------------------------------------------------------------
def validate(p: Params, lay: Layout | None = None) -> list:
    errs = []
    # Basic dimensions
    if min(p.W, p.H, p.D, p.t, p.back_t, p.door_t, p.leg_h, p.leg_d) <= 0:
        errs.append("dimension <= 0")
        return errs
    if p.W <= 2 * p.t:
        errs.append("width too small for two side panels")
    if p.D <= p.back_t:
        errs.append("depth too small for back panel")
    if p.H <= 2 * p.t:
        errs.append("height too small for top and bottom panels")

    lay = lay or compute_layout(p)

    # Door count follows the rule
    if lay.n_doors != door_count(p):
        errs.append(f"door count {lay.n_doors} != rule {door_count(p)}")
    # Door width limits
    if lay.door_w < p.door_min_w - 1e-6:
        errs.append(f"door width {lay.door_w:.1f} < min {p.door_min_w}")
    if lay.door_w > p.door_max_w + 1e-6:
        errs.append(f"door width {lay.door_w:.1f} > max {p.door_max_w}")
    # Doors + gaps fill the width exactly
    total = sum(d.w for d in lay.doors) + (lay.n_doors + 1) * p.door_gap
    if abs(total - p.W) > 1e-6:
        errs.append(f"doors + gaps = {total:.3f} != W {p.W}")
    # Hinge count follows the rule
    if lay.n_hinges != hinge_count(p, lay.door_h):
        errs.append(f"hinge count {lay.n_hinges} != rule {hinge_count(p, lay.door_h)}")

    r = p.hinge_cup_d / 2
    for di, (d, cups) in enumerate(zip(lay.doors, lay.hinge_centers(p))):
        if len(d.hinge_z) != lay.n_hinges:
            errs.append(f"door {di}: {len(d.hinge_z)} hinges")
        for cx, cz in cups:
            # Cup stays inside the door outline
            if cx - r < d.x - 1e-6 or cx + r > d.x + d.w + 1e-6:
                errs.append(f"door {di}: hinge cup outside door in x")
            if cz - r < d.z - 1e-6 or cz + r > d.z + d.h + 1e-6:
                errs.append(f"door {di}: hinge cup outside door in z")
        # Cups do not overlap each other
        zs = sorted(z for _, z in cups)
        for a, b in zip(zs, zs[1:]):
            if b - a < p.hinge_cup_d:
                errs.append(f"door {di}: hinge cups overlap")
                break
    # Facing pairs: even count alternates L R L R
    sides = [d.hinge_side for d in lay.doors]
    if sides != hinge_sides(lay.n_doors):
        errs.append(f"hinge sides {sides} != facing pairs {hinge_sides(lay.n_doors)}")

    # Legs: count follows the spacing rule, all inside the footprint with the margin, no overlap
    span_x = p.W - 2 * (p.leg_inset + p.leg_d / 2)
    span_y = p.D - 2 * (p.leg_inset + p.leg_d / 2)
    if span_x <= 0 or span_y <= 0:
        errs.append("cabinet too small for corner legs")
    else:
        if lay.legs_x != leg_count(span_x, p.leg_max_spacing):
            errs.append(f"legs along width {lay.legs_x} != rule")
        if lay.legs_y != leg_count(span_y, p.leg_max_spacing):
            errs.append(f"legs along depth {lay.legs_y} != rule")
        lr = p.leg_d / 2
        for (x, y) in lay.legs:
            if (x - lr < p.leg_inset - 1e-6 or x + lr > p.W - p.leg_inset + 1e-6
                    or y - lr < p.leg_inset - 1e-6 or y + lr > p.D - p.leg_inset + 1e-6):
                errs.append(f"leg at ({x:.0f}, {y:.0f}) outside the margin")
        xs = sorted({x for x, _ in lay.legs})
        ys = sorted({y for _, y in lay.legs})
        for a, b in list(zip(xs, xs[1:])) + list(zip(ys, ys[1:])):
            if b - a > p.leg_max_spacing + 1e-6:
                errs.append("legs too far apart")
            if b - a < p.leg_d:
                errs.append("legs overlap")

    if p.hinge_cup_depth >= p.door_t:
        errs.append("hinge cup goes through the door")
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

    def box(name, dx, dy, dz, x, y, z):
        parts.append((name, cq.Solid.makeBox(dx, dy, dz, pnt=V(x, y, z))))

    z0 = p.leg_h
    # Carcass
    box("side_left", p.t, p.D, p.H, 0, 0, z0)
    box("side_right", p.t, p.D, p.H, p.W - p.t, 0, z0)
    box("bottom", p.W - 2 * p.t, p.D - p.back_t, p.t, p.t, 0, z0)
    box("top", p.W - 2 * p.t, p.D - p.back_t, p.t, p.t, 0, z0 + p.H - p.t)
    box("back", p.W - 2 * p.t, p.back_t, p.H, p.t, p.D - p.back_t, z0)

    # Legs under the carcass
    for i, (x, y) in enumerate(lay.legs):
        parts.append((f"leg_{i + 1}", cq.Solid.makeCylinder(p.leg_d / 2, p.leg_h,
                                                            pnt=V(x, y, 0), dir=V(0, 0, 1))))

    # Doors with hinge cups drilled from the inner face (y = 0) toward the front
    for i, (d, cups) in enumerate(zip(lay.doors, lay.hinge_centers(p))):
        door = cq.Solid.makeBox(d.w, p.door_t, d.h, pnt=V(d.x, -p.door_t, d.z))
        for cx, cz in cups:
            cup = cq.Solid.makeCylinder(p.hinge_cup_d / 2, p.hinge_cup_depth,
                                        pnt=V(cx, 0, cz), dir=V(0, -1, 0))
            door = door.cut(cup)
        parts.append((f"door_{i + 1}", door))
    return parts


def check_solids(parts) -> list:
    """Geometry-level checks: every part is a valid solid with volume."""
    errs = []
    for name, s in parts:
        if not s.isValid():
            errs.append(f"{name}: invalid solid")
        if s.Volume() <= 0:
            errs.append(f"{name}: zero volume")
    return errs


def export(parts, stem: str, p: Params | None = None, lay: Layout | None = None):
    import cadquery as cq

    comp = cq.Compound.makeCompound([s for _, s in parts])
    cq.exporters.export(comp, f"{stem}.step")
    cq.exporters.export(comp, f"{stem}.stl")
    cq.exporters.export(comp, f"{stem}.svg", opt={
        "width": 900, "height": 600,
        "projectionDir": (-1.2, -2.0, 0.9),
        "showAxes": False, "showHidden": False,
    })
    if p is not None:
        from render import mesh_of, render

        lay = lay or compute_layout(p)
        cups = [c for door_cups in lay.hinge_centers(p) for c in door_cups]
        title = (f"{p.W:.0f} x {p.H:.0f} mm  ·  {lay.n_doors} door(s)  ·  "
                 f"{lay.n_hinges} hinges each")
        title += f"  ·  D {p.D:.0f}  ·  legs {lay.legs_x} x {lay.legs_y}, {p.leg_h:.0f} mm"
        render([(n, mesh_of(s)) for n, s in parts], (p.W, p.D, p.H + p.leg_h), f"{stem}.png", title,
               doors=[(d.x, d.z, d.w, d.h) for d in lay.doors], cups=cups, cup_d=p.hinge_cup_d,
               legs=[(x - p.leg_d / 2, p.leg_d, p.leg_h) for x in sorted({x for x, _ in lay.legs})],
               carcass=(p.leg_h, p.H))


# ---------------------------------------------------------------
# 5. Run
# ---------------------------------------------------------------
def describe(p: Params, lay: Layout) -> str:
    lines = [f"W={p.W:.0f} H={p.H:.0f} D={p.D:.0f} leg_h={p.leg_h:.0f}  ->  doors {lay.n_doors} x "
             f"{lay.door_w:.1f} mm, door height {lay.door_h:.1f} mm, hinges {lay.n_hinges} per door, "
             f"legs {lay.legs_x} x {lay.legs_y} = {len(lay.legs)}"]
    for i, d in enumerate(lay.doors):
        zs = ", ".join(f"{z:.0f}" for z in d.hinge_z)
        lines.append(f"  door {i + 1}: x={d.x:.1f}  hinge side={d.hinge_side}  hinge z=[{zs}]")
    return "\n".join(lines)


if __name__ == "__main__":
    import sys

    p = Params()
    # usage: python cabinet_reference.py W H [D] [leg_h] [out_dir]
    args = sys.argv[1:]
    for name, v in zip(["W", "H", "D", "leg_h"], args[:4]):
        setattr(p, name, float(v))
    lay = compute_layout(p)
    print(describe(p, lay))
    errs = validate(p, lay)
    print("rules:", "OK" if not errs else errs)
    parts = build(p, lay)
    gerrs = check_solids(parts)
    print("geometry:", "OK" if not gerrs else gerrs)
    out = args[4] if len(args) >= 5 else "."
    export(parts, f"{out}/cabinet_{int(p.W)}x{int(p.H)}x{int(p.D)}", p, lay)
