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
    H: float = 850.0           # carcass height
    D: float = 580.0           # depth
    t: float = 18.0            # panel thickness (sides, bottom)
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
    for i in range(n):
        x = p.door_gap + i * (door_w + p.door_gap)
        z = p.door_gap
        # Pairs open outward: left half hinged left, right half hinged right.
        side = "left" if i < n / 2 else "right"
        doors.append(Door(x=x, z=z, w=door_w, h=door_h, hinge_side=side,
                          hinge_z=hinge_positions(p, z, door_h, nh)))
    return Layout(n_doors=n, door_w=door_w, door_h=door_h, n_hinges=nh, doors=doors)


# ---------------------------------------------------------------
# 3. Validation (returns a list of problems; empty list = OK)
# ---------------------------------------------------------------
def validate(p: Params, lay: Layout | None = None) -> list:
    errs = []
    # Basic dimensions
    if min(p.W, p.H, p.D, p.t, p.back_t, p.door_t) <= 0:
        errs.append("dimension <= 0")
        return errs
    if p.W <= 2 * p.t:
        errs.append("width too small for two side panels")
    if p.D <= p.back_t:
        errs.append("depth too small for back panel")
    if p.H <= p.t:
        errs.append("height too small for bottom panel")

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

    # Carcass
    box("side_left", p.t, p.D, p.H, 0, 0, 0)
    box("side_right", p.t, p.D, p.H, p.W - p.t, 0, 0)
    box("bottom", p.W - 2 * p.t, p.D - p.back_t, p.t, p.t, 0, 0)
    box("back", p.W - 2 * p.t, p.back_t, p.H, p.t, p.D - p.back_t, 0)

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
        render([(n, mesh_of(s)) for n, s in parts], (p.W, p.D, p.H), f"{stem}.png", title,
               doors=[(d.x, d.z, d.w, d.h) for d in lay.doors], cups=cups, cup_d=p.hinge_cup_d)


# ---------------------------------------------------------------
# 5. Run
# ---------------------------------------------------------------
def describe(p: Params, lay: Layout) -> str:
    lines = [f"W={p.W:.0f} H={p.H:.0f} D={p.D:.0f}  ->  doors {lay.n_doors} x {lay.door_w:.1f} mm, "
             f"door height {lay.door_h:.1f} mm, hinges {lay.n_hinges} per door"]
    for i, d in enumerate(lay.doors):
        zs = ", ".join(f"{z:.0f}" for z in d.hinge_z)
        lines.append(f"  door {i + 1}: x={d.x:.1f}  hinge side={d.hinge_side}  hinge z=[{zs}]")
    return "\n".join(lines)


if __name__ == "__main__":
    import sys

    p = Params()
    if len(sys.argv) >= 3:
        p.W, p.H = float(sys.argv[1]), float(sys.argv[2])
    lay = compute_layout(p)
    print(describe(p, lay))
    errs = validate(p, lay)
    print("rules:", "OK" if not errs else errs)
    parts = build(p, lay)
    gerrs = check_solids(parts)
    print("geometry:", "OK" if not gerrs else gerrs)
    out = sys.argv[3] if len(sys.argv) >= 4 else "."
    export(parts, f"{out}/cabinet_{int(p.W)}x{int(p.H)}", p, lay)
