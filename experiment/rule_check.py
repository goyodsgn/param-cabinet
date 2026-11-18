"""General rule checker: measures the company rules directly on any cabinet's parts, without a reference
model. Only the part names (door_, shelf_, pin_, leg_, divider_, ...) and the geometry are used, so it works
for product types that have no answer key (tall cabinets, wall cabinets, drawers, ...).
Drawer fronts (drawer_front_*) and a corner cabinet's blind panel (blind_panel) get the door gap check
but no hinge or 600 cell check; other drawer_* parts
are the drawer boxes and do not count as carcass.

usage: python experiment/rule_check.py MODEL.py      -> prints one JSON object
       from rule_check import check_parts; check_parts(parts)

Rules checked (numbers are the company rules; nothing product specific):
  door_cell     ABSOLUTE  door width + 2 * gap <= 600
  door_gap      ABSOLUTE  2 to the carcass outline on every free side, 4 between neighbouring doors,
                          door back face 2 in front of the carcass
  hinge_count   ABSOLUTE  cups per door by door height (<=900: 2, <=1600: 3, above: 4)
  hinge_place             cups 22.5 from one side edge; first/last 100 from the door's top/bottom
  pair_sides              two neighbouring doors with no inner wall behind their joint open as a pair
  shelf_pins    ABSOLUTE  per shelf side: pins 50 from front and back, spacing <= 500, count = minimum
  leg_spacing   ABSOLUTE  neighbouring leg centers <= 600 apart along width and depth
  leg_place               corner legs 30 from the carcass edge, minimum leg count per line
  overlap                 no two parts share volume
  connected               every part touches the cabinet (within the door gap)
  solids                  every part is a valid solid with volume
"""

import json
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

GAP, CELL_MAX, PIN_MAX, LEG_MAX = 2.0, 600.0, 500.0, 600.0
CUP_R, CUP_X, CUP_END = 17.5, 22.5, 100.0
PIN_END, LEG_INSET = 50.0, 30.0
TOL = 1.0


def hinge_rule(h):
    return 2 if h <= 900 else 3 if h <= 1600 else 4


def kind(name):
    # Drawers: the front is checked like a door for gaps (no hinges, no 600 cell); the box is not carcass
    if name.startswith("drawer"):
        return "front" if "front" in name else "drawer"
    if name.startswith("blind"):
        return "front"  # corner cabinet blind panel: a fixed front, gaps like a door, no hinges
    for k in ("door", "shelf", "pin", "leg", "divider"):
        if name.startswith(k):
            return k
    return "panel"


def bb(s):
    b = s.BoundingBox()
    return {"x0": b.xmin, "x1": b.xmax, "y0": b.ymin, "y1": b.ymax, "z0": b.zmin, "z1": b.zmax}


def overlap_1d(a0, a1, b0, b1):
    return min(a1, b1) - max(a0, b0)


def cups_of(solid):
    from OCP.BRepAdaptor import BRepAdaptor_Surface

    out = []
    for f in solid.Faces():
        if f.geomType() != "CYLINDER":
            continue
        if abs(BRepAdaptor_Surface(f.wrapped).Cylinder().Radius() - CUP_R) < 0.5:
            c = f.Center()
            out.append((c.x, c.y, c.z))
    return out


def shelf_edges(shelf, panels):
    """Vertical faces of a shelf that rest against a panel (within 3 mm), as
    (axis_across, coord, axis_along, lo, hi, panel_kind)."""
    out = []
    for f in shelf.Faces():
        if f.geomType() != "PLANE":
            continue
        nv = f.normalAt()
        if abs(nv.z) > 0.1:
            continue
        across, along = ("x", "y") if abs(nv.x) > abs(nv.y) else ("y", "x")
        fb = f.BoundingBox()
        coord = fb.xmin if across == "x" else fb.ymin
        lo, hi = (fb.ymin, fb.ymax) if along == "y" else (fb.xmin, fb.xmax)
        for name, pk, pb in panels:
            near = min(abs(coord - pb[across + "0"]), abs(coord - pb[across + "1"]))
            if near <= 3 + TOL and overlap_1d(lo, hi, pb[along + "0"], pb[along + "1"]) > 10 \
                    and pb[across + "1"] - pb[across + "0"] < 60:
                out.append((across, coord, along, lo, hi, pk if not name.startswith("back") else "back"))
                break
    return out


def check_parts(parts):
    res, msgs = {}, {}

    def fail(rule, msg):
        res[rule] = False
        msgs.setdefault(rule, []).append(msg)

    def ok(rule):
        res.setdefault(rule, True)

    P = [(n, s, kind(n), bb(s)) for n, s in parts]
    # Solids
    ok("solids")
    for n, s, _, _ in P:
        try:
            if not s.isValid() or s.Volume() <= 0:
                fail("solids", f"{n} invalid or empty")
        except Exception:  # noqa: BLE001
            fail("solids", f"{n} unreadable")

    body = [b for n, s, k, b in P if k in ("panel", "divider", "shelf")]
    if not body:
        return {"pass": False, "rules": {"carcass": False}, "messages": {"carcass": ["no carcass parts"]}}
    C = {"x0": min(b["x0"] for b in body), "x1": max(b["x1"] for b in body),
         "y0": min(b["y0"] for b in body), "y1": max(b["y1"] for b in body),
         "z0": min(b["z0"] for b in body), "z1": max(b["z1"] for b in body)}
    doors = sorted([(n, s, b) for n, s, k, b in P if k in ("door", "front")], key=lambda d: (d[2]["z0"], d[2]["x0"]))
    fronts = {n for n, s, k, b in P if k == "front"}
    walls = [b for n, s, k, b in P if k in ("divider", "panel")]

    # Doors: cell width, gaps, hinges
    for rule in ("door_cell", "door_gap", "hinge_count", "hinge_place", "pair_sides"):
        ok(rule)
    sides = {}
    front_only = all(b["y1"] - b["y0"] < b["x1"] - b["x0"] and b["y1"] <= C["y0"] + TOL for _, _, b in doors)
    if not front_only:
        # Every cabinet is a straight box with its doors on the front (corner cabinets included, user rule 11/18)
        for n, s, b in doors:
            if not (b["y1"] - b["y0"] < b["x1"] - b["x0"] and b["y1"] <= C["y0"] + TOL):
                fail("door_gap", f"{n}: not on the front of the carcass")
    doors_old = doors
    for n, s, b in doors_old:
        w, h = b["x1"] - b["x0"], b["z1"] - b["z0"]
        if n not in fronts and w + 2 * GAP > CELL_MAX + TOL:
            fail("door_cell", f"{n}: cell {w + 2 * GAP:.0f} > {CELL_MAX:.0f}")
        if abs(b["y1"] - (C["y0"] - GAP)) > TOL:
            fail("door_gap", f"{n}: back face {C['y0'] - b['y1']:.1f} from carcass, not {GAP:.0f}")
        # four sides: nearest door neighbour in that direction, else the carcass outline
        for side, edge, outline, sign, axis in (("left", b["x0"], C["x0"], -1, "x"), ("right", b["x1"], C["x1"], 1, "x"),
                                                ("bottom", b["z0"], C["z0"], -1, "z"), ("top", b["z1"], C["z1"], 1, "z")):
            other = "z" if axis == "x" else "x"
            best = None
            for m, _, c in doors_old:
                if m == n or overlap_1d(b[other + "0"], b[other + "1"], c[other + "0"], c[other + "1"]) <= TOL:
                    continue
                d = (c[axis + "0"] - edge) if sign > 0 else (edge - c[axis + "1"])
                if d > -TOL and (best is None or d < best):
                    best = d
            if best is not None and best < 50:
                if abs(best - 2 * GAP) > TOL:
                    fail("door_gap", f"{n} {side}: {best:.1f} to the next door, not {2 * GAP:.0f}")
            else:
                d = (outline - edge) * sign
                if abs(d - GAP) > TOL:
                    fail("door_gap", f"{n} {side}: {d:.1f} to the carcass edge, not {GAP:.0f}")
        if n in fronts:
            continue
        cups = cups_of(s)
        need = hinge_rule(h)
        if len(cups) != need:
            fail("hinge_count", f"{n}: {len(cups)} hinges for door height {h:.0f}, rule {need}")
        if cups:
            cx = sum(c[0] for c in cups) / len(cups)
            side = "left" if cx < (b["x0"] + b["x1"]) / 2 else "right"
            sides[n] = side
            want_x = b["x0"] + CUP_X if side == "left" else b["x1"] - CUP_X
            if any(abs(c[0] - want_x) > TOL for c in cups):
                fail("hinge_place", f"{n}: cups not {CUP_X} from the hinge edge")
            zs = sorted(c[2] for c in cups)
            if len(zs) >= 2 and (abs(zs[0] - (b["z0"] + CUP_END)) > TOL or abs(zs[-1] - (b["z1"] - CUP_END)) > TOL):
                fail("hinge_place", f"{n}: end cups not {CUP_END:.0f} from top/bottom")
    # Pairs: two side-by-side doors with no inner wall behind the joint must open left | right
    hinged = [d for d in doors_old if d[0] not in fronts]
    for i, (n, _, b) in enumerate(hinged):
        for m, _, c in hinged[i + 1:]:
            if overlap_1d(b["z0"], b["z1"], c["z0"], c["z1"]) <= TOL or abs(c["x0"] - b["x1"] - 2 * GAP) > TOL:
                continue
            joint = (b["x1"] + c["x0"]) / 2
            wall = any(w["x0"] - TOL <= joint <= w["x1"] + TOL and w["x1"] - w["x0"] < 60 for w in walls)
            if not wall and (sides.get(n), sides.get(m)) != ("left", "right"):
                fail("pair_sides", f"{n}+{m}: no wall behind the joint, hinges {sides.get(n)}/{sides.get(m)}")

    # Shelf pins
    ok("shelf_pins")
    # Cylinder bounding boxes from OCC can be loose, so pins are located by their center of mass
    pins = []
    for n, s, k, b in P:
        if k == "pin":
            c = s.Center()
            pins.append((n, {"cx": c.x, "cy": c.y, "cz": c.z}))
    panels = [(n, k, b) for n, s, k, b in P if k in ("panel", "divider")]
    for n, s, k, b in P:
        if k != "shelf":
            continue
        edges = shelf_edges(s, panels)
        if not any(pk != "back" for *_, pk in edges):
            fail("shelf_pins", f"{n}: no side panel or inner wall next to the shelf")
        for across, coord, along, lo, hi, pk in edges:
            span = hi - lo
            need = math.ceil(max(span - 2 * PIN_END, 0) / PIN_MAX) + 1
            ys = sorted(p["c" + along] for _, p in pins
                        if b["z0"] - 6 < p["cz"] < b["z0"] and abs(p["c" + across] - coord) < 12
                        and lo - TOL <= p["c" + along] <= hi + TOL)
            where = f"{n} at {across}={coord:.0f}"
            if pk == "back" and not ys:
                continue  # pins in the back panel are optional
            if len(ys) != need:
                fail("shelf_pins", f"{where}: {len(ys)} pins for shelf edge {span:.0f}, rule {need}")
                continue
            if abs(ys[0] - (lo + PIN_END)) > TOL or abs(ys[-1] - (hi - PIN_END)) > TOL:
                fail("shelf_pins", f"{where}: end pins not {PIN_END:.0f} from the edges")
            if any(q - p > PIN_MAX + TOL for p, q in zip(ys, ys[1:])):
                fail("shelf_pins", f"{where}: pins more than {PIN_MAX:.0f} apart")

    # Legs
    ok("leg_spacing")
    ok("leg_place")
    legs = []
    for n, s, k, b in P:
        if k == "leg":
            c = s.Center()
            r2 = s.Volume() / (math.pi * max(b["z1"] - b["z0"], 1e-9))
            legs.append({"cx": c.x, "cy": c.y, "d": 2 * math.sqrt(r2)})
    if legs:
        d = legs[0]["d"]
        for axis, lo, hi in (("x", C["x0"], C["x1"]), ("y", C["y0"], C["y1"])):
            cs = sorted({round(l["c" + axis], 1) for l in legs})
            if any(q - p > LEG_MAX + TOL for p, q in zip(cs, cs[1:])):
                fail("leg_spacing", f"legs along {axis}: {max(q - p for p, q in zip(cs, cs[1:])):.0f} apart > {LEG_MAX:.0f}")
            if abs(cs[0] - d / 2 - lo - LEG_INSET) > TOL or abs(hi - cs[-1] - d / 2 - LEG_INSET) > TOL:
                fail("leg_place", f"corner legs along {axis} not {LEG_INSET:.0f} from the carcass edge")
            span = cs[-1] - cs[0]
            if len(cs) != math.ceil(span / LEG_MAX) + 1:
                fail("leg_place", f"{len(cs)} legs along {axis}, minimum is {math.ceil(span / LEG_MAX) + 1}")

    # Overlap (shared volume) and connection, with a bounding-box prefilter
    ok("overlap")
    ok("connected")
    n_parts = len(P)
    adj = {i: set() for i in range(n_parts)}
    for i in range(n_parts):
        a = P[i][3]
        for j in range(i + 1, n_parts):
            c = P[j][3]
            ox = overlap_1d(a["x0"], a["x1"], c["x0"], c["x1"])
            oy = overlap_1d(a["y0"], a["y1"], c["y0"], c["y1"])
            oz = overlap_1d(a["z0"], a["z1"], c["z0"], c["z1"])
            if min(ox, oy, oz) > -2.5:
                adj[i].add(j)
                adj[j].add(i)
            if min(ox, oy, oz) > 0.01:
                try:
                    v = P[i][1].intersect(P[j][1]).Volume()
                except Exception:  # noqa: BLE001
                    v = 0
                if v > 1.0:
                    fail("overlap", f"{P[i][0]} and {P[j][0]} share {v:.0f} mm3")
    seen, stack = {0}, [0]
    while stack:
        for j in adj[stack.pop()]:
            if j not in seen:
                seen.add(j)
                stack.append(j)
    loose = [P[i][0] for i in range(n_parts) if i not in seen]
    if loose:
        fail("connected", f"not touching the cabinet: {', '.join(loose[:6])}")

    absolute = ("door_cell", "door_gap", "hinge_count", "shelf_pins", "leg_spacing")
    return {"pass": all(res.values()), "absolute_pass": all(res.get(r, True) for r in absolute),
            "rules": res, "messages": {k: v[:5] for k, v in msgs.items()},
            "counts": {"doors": len(doors) - len(fronts), "drawers": sum(n.startswith("drawer_front") for n in fronts),
                       "blind": sum(n.startswith("blind") for n in fronts), "shelves": sum(k == "shelf" for _, _, k, _ in P),
                       "pins": len(pins), "legs": len(legs)}}


def check_file(path):
    from evaluate_one import as_shape, load

    try:
        mod = load(path)
        parts = [(n, as_shape(s)) for n, s in mod.build(dict(mod.PARAMS))]
    except Exception as e:  # noqa: BLE001
        return {"pass": False, "runs": False, "error": f"{type(e).__name__}: {e}"[:200]}
    out = check_parts(parts)
    out["runs"] = True
    return out


if __name__ == "__main__":
    print(json.dumps(check_file(sys.argv[1]), ensure_ascii=False))
