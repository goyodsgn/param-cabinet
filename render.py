"""Shaded preview image (PNG) of the cabinet parts, viewed from the front-left and slightly above."""

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d.art3d import Poly3DCollection

COLORS = {"door": (0.85, 0.76, 0.62), "carcass": (0.88, 0.88, 0.88)}
LIGHT = (-0.45, -0.75, 0.5)  # from front-left-above


def shaded(tris, base):
    """Flat shading per triangle; abs() so face winding does not matter."""
    lx, ly, lz = LIGHT
    ln = (lx * lx + ly * ly + lz * lz) ** 0.5
    out = []
    for (a, b, c) in tris:
        u = [b[i] - a[i] for i in range(3)]
        v = [c[i] - a[i] for i in range(3)]
        n = (u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2], u[0] * v[1] - u[1] * v[0])
        nn = (n[0] ** 2 + n[1] ** 2 + n[2] ** 2) ** 0.5 or 1.0
        k = abs(n[0] * lx + n[1] * ly + n[2] * lz) / (nn * ln)
        f = 0.62 + 0.38 * k
        out.append(tuple(min(1.0, ch * f) for ch in base))
    return out


def mesh_of(solid, tol=1.0):
    """Triangles of a CadQuery solid as a list of 3x3 coordinate lists."""
    verts, tris = solid.tessellate(tol)
    pts = [(v.x, v.y, v.z) for v in verts]
    return [[pts[a], pts[b], pts[c]] for a, b, c in tris]


import math

ELEV, AZIM = 18, -118


def front_facing(tris):
    """Drop triangles facing away from the camera. Normals are oriented outward
    from the part's center, which holds for the box-shaped parts used here."""
    if not tris:
        return tris
    e, a = math.radians(ELEV), math.radians(AZIM)
    cam = (math.cos(e) * math.cos(a), math.cos(e) * math.sin(a), math.sin(e))
    pts = [v for t in tris for v in t]
    ctr = [sum(v[i] for v in pts) / len(pts) for i in range(3)]
    keep = []
    for (a_, b, c) in tris:
        u = [b[i] - a_[i] for i in range(3)]
        w = [c[i] - a_[i] for i in range(3)]
        n = (u[1] * w[2] - u[2] * w[1], u[2] * w[0] - u[0] * w[2], u[0] * w[1] - u[1] * w[0])
        g = [(a_[i] + b[i] + c[i]) / 3 - ctr[i] for i in range(3)]
        if sum(n[i] * g[i] for i in range(3)) < 0:
            n = tuple(-x for x in n)
        if sum(n[i] * cam[i] for i in range(3)) > 1e-9:
            keep.append([a_, b, c])
    return keep


def subdivide(tris, max_edge):
    """Split big triangles so the painter's sort in mplot3d does not mis-order faces."""
    out, stack = [], list(tris)
    while stack:
        a, b, c = stack.pop()
        e = max(sum((a[i] - b[i]) ** 2 for i in range(3)), sum((b[i] - c[i]) ** 2 for i in range(3)),
                sum((c[i] - a[i]) ** 2 for i in range(3))) ** 0.5
        if e <= max_edge:
            out.append([a, b, c])
            continue
        ab = tuple((a[i] + b[i]) / 2 for i in range(3))
        bc = tuple((b[i] + c[i]) / 2 for i in range(3))
        ca = tuple((c[i] + a[i]) / 2 for i in range(3))
        stack += [(a, ab, ca), (ab, b, bc), (ca, bc, c), (ab, bc, ca)]
    return out


def render(meshes, size, path, title="", doors=None, cups=None, cup_d=35.0):
    """meshes: list of (name, triangles). size: (W, D, H) for equal scaling.
    doors: list of (x, z, w, h) and cups: list of (x, z) for the front elevation panel."""
    W, D, H = size
    fig = plt.figure(figsize=(11, 5), dpi=130)
    ax = fig.add_subplot(1, 2, 1, projection="3d")
    # One collection for everything so triangles are depth-sorted together.
    all_tris, all_fc = [], []
    for name, tris in meshes:
        color = COLORS["door"] if name.startswith("door") else COLORS["carcass"]
        tris = subdivide(front_facing(tris), max(W, H) / 40)
        all_tris += tris
        all_fc += shaded(tris, color)
    ax.add_collection3d(Poly3DCollection(all_tris, facecolors=all_fc, edgecolors=all_fc, linewidth=0.3))
    ax.set_xlim(0, W)
    ax.set_ylim(-40, D)
    ax.set_zlim(0, H)
    ax.set_box_aspect((W, D + 40, H))
    ax.view_init(elev=ELEV, azim=AZIM)
    ax.set_axis_off()
    if doors:
        ax2 = fig.add_subplot(1, 2, 2)
        ax2.add_patch(plt.Rectangle((0, 0), W, H, fill=False, ec="#999999", lw=0.8))
        for (x, z, w, h) in doors:
            ax2.add_patch(plt.Rectangle((x, z), w, h, fc=COLORS["door"], ec="#8a7454", lw=0.8))
        for (x, z) in cups or []:
            ax2.add_patch(plt.Circle((x, z), cup_d / 2, fc="white", ec="#5b4a32", lw=0.8))
        ax2.set_xlim(-40, W + 40)
        ax2.set_ylim(-40, H + 40)
        ax2.set_aspect("equal")
        ax2.axis("off")
        ax2.set_title("Front, hinge cups seen through the doors", fontsize=9, color="#555555")
    if title:
        fig.text(0.5, 0.04, title, ha="center", fontsize=11, color="#333333")
    fig.savefig(path, bbox_inches="tight", pad_inches=0.1, facecolor="white")
    plt.close(fig)
