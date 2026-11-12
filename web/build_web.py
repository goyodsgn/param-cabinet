"""Build the customer-facing 3D viewer: one GLB (with materials) per option combination + manifest.json.

Options shown to the customer (all combinations are computed ahead of time, so the page needs no server):
  width 900 / 1200 / 1500 / 1800, top panel (between sides / covering / none for a sink),
  door arrangement (default / with a double door), doors closed / open.
usage: python web/build_web.py  -> web/models/*.glb, web/models/manifest.json
"""

import io
import json
import math
import os
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from cabinet_reference import Params, build, compute_layout  # noqa: E402

OUT = os.path.join(ROOT, "web", "models")
H, D = 850.0, 600.0
WIDTHS = [900, 1200, 1500, 1800]
TOPS = ["inset", "onset", "none"]
LAYOUTS = {"default": None, "pair": {900: [2], 1200: [2], 1500: [1, 2], 1800: [2, 2]}}


def oak_texture(size=512, seed=7):
    """Procedural light oak grain (made here, no outside image)."""
    from PIL import Image

    rng = np.random.default_rng(seed)
    y, x = np.mgrid[0:size, 0:size].astype(float) / size
    # smooth noise from a few random sine waves
    warp = sum(rng.uniform(0.01, 0.04) * np.sin(2 * math.pi * (rng.uniform(1, 4) * x + rng.uniform(0, 1)))
               for _ in range(5))
    rings = np.sin(2 * math.pi * (y + warp) * 38 + 3 * np.sin(2 * math.pi * x * 2.0))
    fine = rng.normal(0, 1, (size, size))
    fine = np.cumsum(fine, axis=1)
    fine = (fine - fine.mean()) / (fine.std() + 1e-9)
    t = 0.5 + 0.22 * rings + 0.06 * np.clip(fine, -2, 2)
    base = np.array([196, 160, 112], float)
    dark = np.array([150, 112, 70], float)
    img = base * t[..., None] + dark * (1 - t[..., None])
    img = np.clip(img, 0, 255).astype(np.uint8)
    return Image.fromarray(img, "RGB")


def material_of(name):
    if name.startswith("door"):
        return "oak"
    if name.startswith("leg"):
        return "leg"
    return "white"


def tess(solid, tol=0.4):
    vs, fs = solid.tessellate(tol, 0.3)
    return np.array([(v.x, v.y, v.z) for v in vs], float), np.array(fs, int)


def swing(verts, door, opened_deg, gap):
    """Open a door around its hinge-side vertical edge (at the door's back face)."""
    if not opened_deg:
        return verts
    left = door.hinge_side == "left"
    px = door.x if left else door.x + door.w
    py = -gap
    a = math.radians(-opened_deg if left else opened_deg)
    c, s = math.cos(a), math.sin(a)
    out = verts.copy()
    dx, dy = verts[:, 0] - px, verts[:, 1] - py
    out[:, 0] = px + c * dx - s * dy
    out[:, 1] = py + s * dx + c * dy
    return out


def box_uv(verts, faces, scale=600.0):
    """Unshare vertices and give each triangle planar UVs along its main axis (wood grain runs vertically
    on doors: v follows z)."""
    tri = verts[faces]                                   # (n, 3, 3)
    n = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0])
    axis = np.argmax(np.abs(n), axis=1)
    uv = np.zeros((len(faces), 3, 2))
    for i, ax in enumerate(axis):
        u, v = [(1, 2), (0, 2), (0, 1)][ax]
        uv[i, :, 0] = tri[i, :, u] / scale
        uv[i, :, 1] = tri[i, :, v] / scale
    return tri.reshape(-1, 3), np.arange(len(faces) * 3).reshape(-1, 3), uv.reshape(-1, 2)


def to_gltf_axes(v):
    """mm, z up -> m, y up (x right, z toward the viewer)."""
    return np.column_stack([v[:, 0], v[:, 2], -v[:, 1]]) / 1000.0


def make_glb(p, opened, tex_img):
    import trimesh
    from trimesh.visual.material import PBRMaterial
    from trimesh.visual.texture import TextureVisuals

    lay = compute_layout(p)
    doors = {f"door_{i + 1}": d for i, d in enumerate(lay.doors)}
    groups = {"oak": [], "white": [], "leg": []}
    for name, solid in build(p, lay):
        if name.startswith("pin_"):
            continue
        v, f = tess(solid)
        if name in doors:
            v = swing(v, doors[name], 95 if opened else 0, p.door_gap)
        groups[material_of(name)].append((v, f))

    scene = trimesh.Scene()
    mats = {
        "white": PBRMaterial(name="white_melamine", baseColorFactor=[236, 234, 228, 255],
                             metallicFactor=0.0, roughnessFactor=0.55),
        "leg": PBRMaterial(name="black_metal", baseColorFactor=[30, 30, 32, 255],
                           metallicFactor=0.6, roughnessFactor=0.4),
        "oak": PBRMaterial(name="oak_veneer", baseColorTexture=tex_img, metallicFactor=0.0,
                           roughnessFactor=0.6),
    }
    for key, parts in groups.items():
        if not parts:
            continue
        vs, fs, off = [], [], 0
        for v, f in parts:
            vs.append(v)
            fs.append(f + off)
            off += len(v)
        v, f = np.vstack(vs), np.vstack(fs)
        if key == "oak":
            v2, f2, uv = box_uv(v, f)
            mesh = trimesh.Trimesh(to_gltf_axes(v2), f2, process=False)
            mesh.visual = TextureVisuals(uv=uv, material=mats[key])
        else:
            mesh = trimesh.Trimesh(to_gltf_axes(v), f, process=False)
            mesh.visual = TextureVisuals(material=mats[key])
        scene.add_geometry(mesh, node_name=key, geom_name=key)
    return scene.export(file_type="glb"), lay


def main():
    os.makedirs(OUT, exist_ok=True)
    tex = oak_texture()
    manifest = {"H": H, "D": D, "widths": WIDTHS, "tops": TOPS, "layouts": list(LAYOUTS), "models": {}}
    for W in WIDTHS:
        for top in TOPS:
            for lk, lmap in LAYOUTS.items():
                layout = lmap[W] if lmap else None
                p = Params(W=float(W), H=H, D=D, top_mode=top, door_layout=layout)
                for opened in (False, True):
                    key = f"w{W}_{top}_{lk}_{'open' if opened else 'closed'}"
                    glb, lay = make_glb(p, opened, tex)
                    open(os.path.join(OUT, key + ".glb"), "wb").write(glb)
                    manifest["models"][key] = {
                        "file": f"models/{key}.glb", "doors": lay.n_doors, "hinges": lay.n_hinges,
                        "walls": len(lay.dividers), "shelves": lay.n_shelves * len(lay.bays),
                        "legs": len(lay.legs), "bays": lay.groups,
                        "sides": [d.hinge_side for d in lay.doors], "kb": round(len(glb) / 1024)}
                    print(key, f"{len(glb) / 1024:.0f} KB")
    json.dump(manifest, open(os.path.join(OUT, "manifest.json"), "w"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
