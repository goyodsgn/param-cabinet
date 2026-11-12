"""Evaluate one generated model file against the company rules.

usage: python experiment/evaluate_one.py MODEL.py [OVERRIDES_JSON] [REFERENCE_JSON]

Loads PARAMS and build() from the file, applies optional parameter overrides, builds the parts and
checks the geometry against the reference rules (cabinet_reference.compute_layout). By default the
reference uses the model's own PARAMS; REFERENCE_JSON instead gives the spec the customer asked for
(conversation test), so the geometry is checked against what was asked. Prints one JSON object.
Exit code is 0 even when checks fail; a crash is reported as runs=false.
"""

import importlib.util
import json
import os
import sys
import traceback

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cabinet_reference import Params, compute_layout, pin_ys, validate  # noqa: E402

# Keys a customer may change, and absolute rules that must keep the company value
OVERRIDABLE = ["W", "H", "D", "leg_h", "back_mode", "top_mode", "t", "back_t", "divider_t", "door_t",
               "shelf_t", "n_doors", "n_shelves", "shelf_min_gap", "door_layout", "bottom_clear_min"]
STR_KEYS = ("back_mode", "top_mode")
INT_KEYS = ("n_doors", "n_shelves")
ABSOLUTE = {"door_gap": 2.0, "door_max_w": 600.0, "pin_max_spacing": 500.0, "leg_max_spacing": 600.0}

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


def to_params(d):
    kw = {}
    for k in OVERRIDABLE:
        v = d.get(k)
        if v is None:
            continue
        if k in STR_KEYS:
            kw[k] = str(v)
        elif k in INT_KEYS:
            kw[k] = int(v)
        elif k == "door_layout":
            kw[k] = [int(g) for g in v] or None
        else:
            kw[k] = float(v)
    return Params(**kw)


def evaluate(path, overrides=None, mod=None, reference=None):
    res = {"runs": False, "error": ""}
    try:
        mod = mod or load(path)
        params = dict(getattr(mod, "PARAMS"))
        res["params_found"] = sorted(k for k in ("W", "H", "D", "leg_h") if k in params)
        res["param_count"] = len(params)
        res["defaults"] = {k: params.get(k) for k in OVERRIDABLE + list(ABSOLUTE)}
        res["notes"] = list(params.get("notes") or [])
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
    try:
        p = to_params(reference if reference is not None else params)
        lay = compute_layout(p)
    except Exception as e:  # noqa: BLE001  (e.g. door_layout written in a form we cannot read)
        res["error"] = f"params: {type(e).__name__}: {e}"[:300]
        checks["params"] = False
        res["checks"] = checks
        res["pass"] = False
        return res
    # Absolute rules: the model kept the company values and its layout breaks none of them
    abs_vals_ok = all(params.get(k) is None or abs(float(params[k]) - v) < 1e-6 for k, v in ABSOLUTE.items())
    abs_vals_ok = abs_vals_ok and not [e for e in validate(to_params(params), None) if e.startswith("ABSOLUTE")]
    abs_errs = [e for e in validate(p, lay) if e.startswith("ABSOLUTE")]
    checks["absolute_rules"] = abs_vals_ok and not abs_errs
    res["absolute_errors"] = abs_errs
    res["layout"] = {"doors": lay.n_doors, "shelves": lay.n_shelves, "bays": lay.groups}
    names = [n for n, _ in parts]
    by_name = {n: s for n, s in parts}

    # Every part is a valid solid with volume
    try:
        checks["solids"] = all(s.isValid() and s.Volume() > 0 for _, s in parts) and len(parts) > 0
    except Exception:  # noqa: BLE001
        checks["solids"] = False

    # Carcass parts present (no top panel when top_mode is "none")
    need = ["side_left", "side_right", "bottom", "back"] + ([] if p.top_mode == "none" else ["top"])
    checks["carcass_parts"] = all(n in names for n in need)

    # Top panel: inset between the sides, onset over the sides, or none at all
    def bb_of(n):
        return by_name[n].BoundingBox() if n in by_name else None

    try:
        top, sl, back = bb_of("top"), bb_of("side_left"), bb_of("back")
        if p.top_mode == "none":
            top_ok = top is None and sl is not None and abs(sl.zmax - p.H) < TOL
        elif top is None or sl is None:
            top_ok = False
        elif p.top_mode == "onset":
            top_ok = (abs(top.xmin) < TOL and abs(top.xlen - p.W) < TOL and abs(top.zmax - p.H) < TOL
                      and abs(sl.zmax - (p.H - p.t)) < TOL)
        else:
            top_ok = (abs(top.xmin - p.t) < TOL and abs(top.xlen - (p.W - 2 * p.t)) < TOL
                      and abs(top.zmax - p.H) < TOL and abs(sl.zmax - p.H) < TOL)
        checks["top_panel"] = bool(top_ok)
        # Back panel: onset covers the full carcass width and height, inset sits between the panels
        if back is None:
            checks["back_panel"] = False
        elif p.back_mode == "onset":
            checks["back_panel"] = abs(back.xlen - p.W) < TOL and abs(back.zlen - p.Hc) < TOL
        else:
            checks["back_panel"] = (abs(back.xmin - p.t) < TOL and abs(back.xlen - (p.W - 2 * p.t)) < TOL
                                    and abs(back.zlen - p.clear_h) < TOL)
        res["got"] = {"top": [round(v, 1) for v in (top.xmin, top.xmax, top.zmin, top.zmax)] if top else None,
                      "back": [round(v, 1) for v in (back.xmin, back.xmax, back.zmin, back.zmax)] if back else None}
    except Exception:  # noqa: BLE001
        checks["top_panel"] = checks["back_panel"] = False
        res["got"] = {}

    doors = sorted([(n, s) for n, s in parts if n.startswith("door_")],
                   key=lambda x: x[1].BoundingBox().xmin)
    legs = [s for n, s in parts if n.startswith("leg_")]
    n_div = sum(n.startswith("divider_") for n in names)
    n_shelf = sum(n.startswith("shelf_") for n in names)
    n_pin = sum(n.startswith("pin_") for n in names)
    bays = len(lay.bays)
    checks["door_count"] = len(doors) == lay.n_doors
    checks["divider_count"] = n_div == len(lay.dividers)
    # Inner walls stand where the bays meet (door arrangement)
    div_x = sorted((s.BoundingBox().xmin + s.BoundingBox().xmax) / 2 for n, s in parts if n.startswith("divider_"))
    checks["divider_position"] = (len(div_x) == len(lay.dividers)
                                  and all(abs(a - (x0 + x1) / 2) < TOL for a, (x0, x1) in zip(div_x, lay.dividers)))
    # Shelf spaces in the first bay: lowest space >= bottom_clear_min; every space >= shelf_min_gap (automatic)
    x0, x1 = lay.bays[0]
    zs = sorted(s.BoundingBox().zmin for n, s in parts if n.startswith("shelf_")
                and x0 - TOL <= (s.BoundingBox().xmin + s.BoundingBox().xmax) / 2 <= x1 + TOL)
    sp_tops = [p.inner_bottom] + [z + p.shelf_t for z in zs]
    sp_bots = zs + [p.inner_top]
    spaces = [b - a for a, b in zip(sp_tops, sp_bots)]
    ok = len(zs) == lay.n_shelves
    if p.bottom_clear_min is not None and zs:
        ok = ok and spaces[0] >= p.bottom_clear_min - TOL
    if p.n_shelves is None and zs:
        ok = ok and min(spaces) >= p.shelf_min_gap - TOL
    checks["shelf_spaces"] = ok
    checks["shelf_count"] = n_shelf == lay.n_shelves * bays
    pins_expected = 2 * len(pin_ys(p)) * lay.n_shelves * bays
    checks["pin_count"] = n_pin == pins_expected
    checks["leg_count"] = len(legs) == len(lay.legs)
    res["got"].update({"doors": len(doors), "dividers": n_div, "shelves": n_shelf, "pins": n_pin,
                       "legs": len(legs), "spaces_bay1": [round(v) for v in spaces]})
    res["expected"] = {"doors": lay.n_doors, "hinges": lay.n_hinges, "dividers": len(lay.dividers),
                       "shelves": lay.n_shelves * bays, "pins": pins_expected,
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
    overrides = json.loads(sys.argv[2]) if len(sys.argv) > 2 and sys.argv[2] not in ("", "null") else None
    reference = json.loads(sys.argv[3]) if len(sys.argv) > 3 else None
    print(json.dumps(evaluate(sys.argv[1], overrides, reference=reference), ensure_ascii=False))
