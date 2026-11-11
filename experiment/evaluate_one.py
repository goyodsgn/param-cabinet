"""Evaluate one generated model file against the company rules.

usage: python experiment/evaluate_one.py MODEL.py [OVERRIDES_JSON]

Loads PARAMS and build() from the file, applies optional parameter overrides, builds the parts and
checks the geometry against the reference rules (cabinet_reference.compute_layout). Prints one JSON
object. Exit code is 0 even when checks fail; a crash is reported as runs=false.
"""

import importlib.util
import json
import os
import sys
import traceback

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cabinet_reference import Params, compute_layout  # noqa: E402

TOL = 1.0
CUP_R = 17.5


def load(path):
    spec = importlib.util.spec_from_file_location("generated_model", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def as_shape(obj):
    """Accept a cq.Shape or a cq.Workplane."""
    if hasattr(obj, "findSolid"):
        return obj.findSolid()
    if hasattr(obj, "val") and not hasattr(obj, "isValid"):
        return obj.val()
    return obj


def cup_faces(shape):
    from OCP.BRepAdaptor import BRepAdaptor_Surface

    out = []
    for f in shape.Faces():
        if f.geomType() != "CYLINDER":
            continue
        r = BRepAdaptor_Surface(f.wrapped).Cylinder().Radius()
        if abs(r - CUP_R) < 0.5:
            out.append(f)
    return out


def evaluate(path, overrides=None):
    res = {"runs": False, "error": ""}
    try:
        mod = load(path)
        params = dict(getattr(mod, "PARAMS"))
        res["params_found"] = sorted(k for k in ("W", "H", "D", "leg_h") if k in params)
        res["param_count"] = len(params)
        res["defaults"] = {k: params.get(k) for k in ("W", "H", "D", "leg_h")}
        if overrides:
            params.update(overrides)
        parts = [(n, as_shape(s)) for n, s in mod.build(params)]
        res["runs"] = True
    except Exception as e:  # noqa: BLE001
        res["error"] = f"{type(e).__name__}: {e}".splitlines()[0][:300]
        res["trace"] = traceback.format_exc()[-1500:]
        return res

    checks = {}
    if any(k not in params for k in ("W", "H", "D", "leg_h")):
        checks["params"] = False
        res["checks"] = checks
        res["pass"] = False
        return res
    checks["params"] = True
    p = Params(W=float(params["W"]), H=float(params["H"]), D=float(params["D"]),
               leg_h=float(params["leg_h"]), back_mode=str(params.get("back_mode", "onset")))
    lay = compute_layout(p)
    names = [n for n, _ in parts]

    # Every part is a valid solid with volume
    try:
        checks["solids"] = all(s.isValid() and s.Volume() > 0 for _, s in parts) and len(parts) > 0
    except Exception:  # noqa: BLE001
        checks["solids"] = False

    # Carcass parts present
    checks["carcass_parts"] = all(n in names for n in ("side_left", "side_right", "top", "bottom", "back"))

    doors = sorted([(n, s) for n, s in parts if n.startswith("door_")],
                   key=lambda x: x[1].BoundingBox().xmin)
    legs = [s for n, s in parts if n.startswith("leg_")]
    n_div = sum(n.startswith("divider_") for n in names)
    n_shelf = sum(n.startswith("shelf_") for n in names)
    n_pin = sum(n.startswith("pin_") for n in names)
    bays = len(lay.bays)
    checks["door_count"] = len(doors) == lay.n_doors
    checks["divider_count"] = n_div == len(lay.dividers)
    checks["shelf_count"] = n_shelf == lay.n_shelves * bays
    checks["pin_count"] = n_pin == 4 * lay.n_shelves * bays
    checks["leg_count"] = len(legs) == len(lay.legs)
    res["got"] = {"doors": len(doors), "dividers": n_div, "shelves": n_shelf, "pins": n_pin,
                  "legs": len(legs)}
    res["expected"] = {"doors": lay.n_doors, "hinges": lay.n_hinges, "dividers": len(lay.dividers),
                       "shelves": lay.n_shelves * bays, "pins": 4 * lay.n_shelves * bays,
                       "legs": len(lay.legs), "sides": [d.hinge_side for d in lay.doors]}

    # Door gap: every door matches the reference door rectangle (x, z, w, h) and hangs door_gap
    # in front of the carcass (its back face at y = -door_gap)
    gap_ok = len(doors) == lay.n_doors
    for (_, s), d in zip(doors, lay.doors):
        bb = s.BoundingBox()
        if (abs(bb.xmin - d.x) > TOL or abs(bb.xlen - d.w) > TOL or abs(bb.zmin - d.z) > TOL
                or abs(bb.zlen - d.h) > TOL or abs(bb.ymax + p.door_gap) > TOL):
            gap_ok = False
    checks["door_gap"] = gap_ok

    # Hinge cups per door and hinge side
    hinge_ok, side_ok, sides, counts = True, True, [], []
    for _, s in doors:
        bb = s.BoundingBox()
        cups = cup_faces(s)
        counts.append(len(cups))
        if len(cups) != lay.n_hinges:
            hinge_ok = False
        if cups:
            cx = sum(f.Center().x for f in cups) / len(cups)
            sides.append("left" if cx < (bb.xmin + bb.xmax) / 2 else "right")
        else:
            sides.append("none")
    if sides != [d.hinge_side for d in lay.doors]:
        side_ok = False
    checks["hinge_count"] = hinge_ok and len(doors) > 0
    checks["hinge_sides"] = side_ok and len(doors) > 0
    res["got"]["hinges_per_door"] = counts
    res["got"]["sides"] = sides

    # Overall size
    try:
        import cadquery as cq

        bb = cq.Compound.makeCompound([s for _, s in parts]).BoundingBox()
        res["got"]["bbox"] = [round(v, 1) for v in (bb.xmin, bb.xmax, bb.ymin, bb.ymax, bb.zmin, bb.zmax)]
        checks["overall_size"] = (abs(bb.xlen - p.W) < TOL and abs(bb.ylen - p.D) < TOL
                                  and abs(bb.zlen - p.H) < TOL and abs(bb.zmin) < TOL)
    except Exception:  # noqa: BLE001
        checks["overall_size"] = False

    res["checks"] = checks
    res["pass"] = all(checks.values())
    return res


if __name__ == "__main__":
    overrides = json.loads(sys.argv[2]) if len(sys.argv) > 2 else None
    print(json.dumps(evaluate(sys.argv[1], overrides), ensure_ascii=False))
