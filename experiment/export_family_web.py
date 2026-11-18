"""Export the product family models the agent made for the web viewer, at many sizes.

The browser cannot run the agent's Python (CadQuery) code, so each family's latest model
(generated_family/<id>_t2.py, built by the agent) is run here over a grid of sizes / options,
checked with the general rule checker at every grid point, and saved as light triangle meshes:

  web/family/index.json                 the families, their slider values and which grid points pass
  web/family/<id>/<key>.json            one model: parts (mesh, material, how it opens)

Mesh coordinates are mm in cabinet coordinates (x right, y depth with the front at y < 0, z up).
How a part opens (for the viewer's open / closed switch):
  door      turns about its hinge edge (found from the hinge cup holes), at its back face
  drawer    the front and its box (drawer_<k>_*) slide out together
  blind panel and everything else stay put.

usage: python experiment/export_family_web.py
"""

import itertools
import json
import os
import re
import shutil
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "experiment"))

from evaluate_one import as_shape, load  # noqa: E402
from rule_check import check_parts, cups_of  # noqa: E402

OUT = os.path.join(ROOT, "web", "family")

# What the viewer lets people change, per family (values the agent's code is run with).
GRID = {
    "f1_tall": {"W": [450, 600, 750, 900], "H": [1800, 2100, 2400]},
    "f2_wall": {"W": [600, 800, 1000, 1200], "H": [600, 750, 900]},
    "f3_open": {"W": [600, 800, 1000, 1200, 1400], "H": [1200, 1500, 1800]},
    "f4_drawer": {"W": [450, 600, 750, 900], "H": [700, 850], "n_drawers": [3, 4]},
    "f5_corner": {"W": [900, 1000, 1100, 1200], "door_side": ["left", "right"]},
}


def material(name):
    if name.startswith("door") or name.startswith("drawer_front") or name.startswith("blind"):
        return "front"
    if name.startswith("leg"):
        return "leg"
    if name.startswith("pin"):
        return "pin"
    return "body"


def mesh(shape, tol=0.5):
    vs, fs = shape.tessellate(tol, 0.5)
    v = []
    for p in vs:
        v += [round(p.x, 1), round(p.y, 1), round(p.z, 1)]
    return v, [k for f in fs for k in f]


def drawer_key(name):
    m = re.match(r"drawer_front_(\d+)", name) or re.match(r"drawer_(\d+)_", name)
    return m.group(1) if m else None


def how_it_opens(parts):
    """name -> opening info for doors and drawers."""
    out = {}
    boxes = {}
    for n, s in parts:
        k = drawer_key(n)
        if k and not n.startswith("drawer_front"):
            b = s.BoundingBox()
            lo, hi = boxes.get(k, (b.ymin, b.ymax))
            boxes[k] = (min(lo, b.ymin), max(hi, b.ymax))
    for n, s in parts:
        b = s.BoundingBox()
        if n.startswith("door"):
            cups = cups_of(s)
            if not cups or b.xlen < b.ylen:  # only front-facing doors with hinge cups
                continue
            left = sum(c[0] for c in cups) / len(cups) < (b.xmin + b.xmax) / 2
            out[n] = {"t": "hinge", "side": "left" if left else "right",
                      "x": round(b.xmin if left else b.xmax, 1), "y": round(b.ymax, 1)}
        elif drawer_key(n):
            k = drawer_key(n)
            lo, hi = boxes.get(k, (0, 400))
            out[n] = {"t": "slide", "d": round(0.75 * (hi - lo), 1)}
    return out


def key_of(values):
    return "_".join(f"{k}-{v}" for k, v in values.items())


def main():
    fams = {f["id"]: f for f in json.load(open(os.path.join(ROOT, "experiment", "families.json"), encoding="utf-8"))}
    shutil.rmtree(OUT, ignore_errors=True)
    os.makedirs(OUT)
    index = []
    for fid, axes in GRID.items():
        src = os.path.join(ROOT, "generated_family", f"{fid}_t2.py")
        if not os.path.exists(src):
            continue
        mod = load(src)
        base = dict(mod.PARAMS)
        os.makedirs(os.path.join(OUT, fid))
        names = list(axes)
        entry = {"family": fid, "name": fams[fid]["family"], "axes": axes, "items": {},
                 "default": {k: base[k] if base.get(k) in axes[k] else axes[k][-1] for k in names},
                 "notes": list(base.get("notes") or [])}
        for combo in itertools.product(*(axes[k] for k in names)):
            values = dict(zip(names, combo))
            params = dict(base, **values)
            key = key_of(values)
            try:
                parts = [(n, as_shape(s)) for n, s in mod.build(params)]
                rc = check_parts(parts)
            except Exception as e:  # noqa: BLE001
                print("fail", fid, key, e)
                entry["items"][key] = {"ok": False, "error": f"{type(e).__name__}"}
                continue
            opens = how_it_opens(parts)
            bbs = [s.BoundingBox() for _, s in parts]
            box = [min(b.xmin for b in bbs), min(b.ymin for b in bbs), min(b.zmin for b in bbs),
                   max(b.xmax for b in bbs), max(b.ymax for b in bbs), max(b.zmax for b in bbs)]
            out = []
            for n, s in parts:
                v, i = mesh(s)
                part = {"n": n, "m": material(n), "v": v, "i": i}
                if n in opens:
                    part["o"] = opens[n]
                out.append(part)
            item = {"family": fid, "values": values, "box": [round(x, 1) for x in box],
                    "pass": bool(rc.get("pass")), "failed": [k for k, v in rc["rules"].items() if not v],
                    "counts": rc.get("counts") or {}, "parts": out}
            with open(os.path.join(OUT, fid, key + ".json"), "w", encoding="utf-8") as fh:
                json.dump(item, fh, ensure_ascii=False, separators=(",", ":"))
            entry["items"][key] = {"ok": True, "pass": item["pass"], "failed": item["failed"]}
            print(fid, key, "pass" if item["pass"] else f"FAIL {item['failed']}",
                  os.path.getsize(os.path.join(OUT, fid, key + ".json")) // 1024, "KB", flush=True)
        index.append(entry)
    with open(os.path.join(OUT, "index.json"), "w", encoding="utf-8") as fh:
        json.dump(index, fh, ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
