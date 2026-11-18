"""Export the product family models the agent made (generated_family/*.py) for the web viewer.

Each model becomes web/family/<id>_t<k>.json: triangle meshes per part (mm, cabinet coordinates:
x right, y depth with the front at y < 0, z up), the part's material, the customer's sentence and the
agent's notes. web/family/index.json lists them. The viewer shows these as they are (no recomputation).

usage: python experiment/export_family_web.py
"""

import csv
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "experiment"))

from evaluate_one import as_shape, load  # noqa: E402

OUT = os.path.join(ROOT, "web", "family")


def material(name):
    if name.startswith("door") or name.startswith("drawer_front") or name.startswith("blind"):
        return "front"
    if name.startswith("leg"):
        return "leg"
    if name.startswith("pin"):
        return "pin"
    return "body"


def mesh(shape, tol=0.4):
    vs, fs = shape.tessellate(tol, 0.3)
    v = []
    for p in vs:
        v += [round(p.x, 1), round(p.y, 1), round(p.z, 1)]
    i = [k for f in fs for k in f]
    return v, i


def main():
    fams = {f["id"]: f for f in json.load(open(os.path.join(ROOT, "experiment", "families.json"), encoding="utf-8"))}
    graded = {}
    path = os.path.join(ROOT, "results", "family.csv")
    if os.path.exists(path):
        for r in csv.DictReader(open(path, encoding="utf-8")):
            graded[(r["id"], int(r["turn"]))] = r
    os.makedirs(OUT, exist_ok=True)
    index = []
    for fid, f in fams.items():
        for k, turn in enumerate(f["turns"], start=1):
            src = os.path.join(ROOT, "generated_family", f"{fid}_t{k}.py")
            if not os.path.exists(src):
                continue
            try:
                mod = load(src)
                parts = [(n, as_shape(s)) for n, s in mod.build(dict(mod.PARAMS))]
            except Exception as e:  # noqa: BLE001
                print("skip", fid, k, e)
                continue
            out = []
            for n, s in parts:
                v, i = mesh(s)
                out.append({"n": n, "m": material(n), "v": v, "i": i})
            bbs = [s.BoundingBox() for _, s in parts]
            box = [min(b.xmin for b in bbs), min(b.ymin for b in bbs), min(b.zmin for b in bbs),
                   max(b.xmax for b in bbs), max(b.ymax for b in bbs), max(b.zmax for b in bbs)]
            g = graded.get((fid, k), {})
            counts = json.loads(g["counts"]) if g.get("counts") else {}
            item = {"id": f"{fid}_t{k}", "family": fid, "name": f["family"], "turn": k,
                    "customer": f["turns"][: k], "box": [round(x, 1) for x in box],
                    "pass": g.get("pass") == "True", "counts": counts,
                    "notes": list(mod.PARAMS.get("notes") or []), "parts": out}
            name = f"{fid}_t{k}.json"
            with open(os.path.join(OUT, name), "w", encoding="utf-8") as fh:
                json.dump(item, fh, ensure_ascii=False, separators=(",", ":"))
            index.append({"file": name, "family": fid, "name": f["family"], "turn": k,
                          "size": [round(box[3] - box[0]), round(box[4] - box[1]), round(box[5] - box[2])],
                          "pass": item["pass"]})
            print(name, len(out), "parts", os.path.getsize(os.path.join(OUT, name)) // 1024, "KB")
    with open(os.path.join(OUT, "index.json"), "w", encoding="utf-8") as fh:
        json.dump(index, fh, ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
