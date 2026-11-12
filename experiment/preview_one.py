"""Render a preview PNG of a generated model at its own PARAMS (3D view, front elevation of the doors,
front section of the carcass).

usage: python experiment/preview_one.py MODEL.py OUT.png "title"
"""

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "experiment"))

from evaluate_one import as_shape, load  # noqa: E402
from render import mesh_of, render  # noqa: E402


def main(path, out, title=""):
    mod = load(path)
    params = dict(mod.PARAMS)
    parts = [(n, as_shape(s)) for n, s in mod.build(params)]
    W, H, D = float(params["W"]), float(params["H"]), float(params["D"])
    bbs = {n: s.BoundingBox() for n, s in parts}
    doors = [(b.xmin, b.zmin, b.xlen, b.zlen) for n, b in bbs.items() if n.startswith("door_")]
    inside = [(b.xmin, b.zmin, b.xlen, b.zlen) for n, b in bbs.items()
              if n.split("_")[0] in ("side", "top", "bottom", "divider", "shelf") or n == "top"]
    y_front = min(b.ymin for b in bbs.values())
    render([(n, mesh_of(s)) for n, s in parts if not n.startswith("pin_")], (W, D, H), out, title,
           doors=doors, inside=inside, y_front=y_front)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else "")
