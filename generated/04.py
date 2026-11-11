import math
import cadquery as cq

PARAMS = {
    # overall size
    "W": 1500.0,
    "H": 850.0,
    "D": 600.0,
    "leg_h": 100.0,
    "back_mode": "onset",
    # panels
    "t": 18.0,
    "back_t": 10.0,
    "divider_t": 18.0,
    "door_t": 22.0,
    "shelf_t": 30.0,
    # doors
    "door_max_w": 600.0,
    "door_gap": 2.0,
    # hinge cups
    "hinge_d": 35.0,
    "hinge_depth": 12.0,
    "hinge_edge": 22.5,
    "hinge_end": 100.0,
    "hinge_h1": 900.0,
    "hinge_h2": 1600.0,
    # shelves
    "shelf_min_gap": 320.0,
    "shelf_clear": 1.0,
    # pins
    "pin_d": 5.0,
    "pin_edge": 50.0,
    "pin_drop": 2.5,
    "pin_hole_depth": 8.0,
    "pin_out": 6.0,
    # legs
    "leg_d": 40.0,
    "leg_corner_gap": 30.0,
    "leg_max_c": 600.0,
}


def _box(x0, x1, y0, y1, z0, z1):
    return cq.Solid.makeBox(x1 - x0, y1 - y0, z1 - z0, cq.Vector(x0, y0, z0))


def _cyl(r, h, pnt, d):
    return cq.Solid.makeCylinder(r, h, cq.Vector(*pnt), cq.Vector(*d))


def _cut(solid, tools):
    for c in tools:
        solid = solid.cut(c)
    sols = solid.Solids()
    return sols[0] if len(sols) == 1 else max(sols, key=lambda s: s.Volume())


def _ceil(v):
    return int(math.ceil(round(v, 9)))


def build(params: dict):
    p = params
    W, H, D = p["W"], p["H"], p["D"]
    leg_h = p["leg_h"]
    t, back_t, div_t = p["t"], p["back_t"], p["divider_t"]
    door_t, shelf_t = p["door_t"], p["shelf_t"]
    gap = p["door_gap"]
    inset = p["back_mode"] == "inset"

    Dc = D - door_t - gap
    Hc = H - leg_h
    z0, z1 = leg_h, H
    Din = Dc - back_t                      # inner depth (back panel inner face)
    carc_d = Dc if inset else Din          # depth of sides/top/bottom

    n = max(1, _ceil(W / p["door_max_w"]))
    cell = W / n

    parts = []

    # ---------------- vertical panels (x ranges) ----------------
    # index 0 = left side, 1..n-1 = dividers, n = right side
    panels = [(0.0, t)]
    for j in range(1, n):
        c = j * cell
        panels.append((c - div_t / 2, c + div_t / 2))
    panels.append((W - t, W))

    # ---------------- shelves ----------------
    clear_h = Hc - 2 * t
    k = max(0, int(math.floor(round((clear_h - p["shelf_min_gap"]) /
                                    (p["shelf_min_gap"] + shelf_t), 9))))
    space = (clear_h - k * shelf_t) / (k + 1)

    pr = p["pin_d"] / 2
    shelves = []
    pins = []
    holes = [[] for _ in panels]   # cutting tools per panel
    for b in range(n):
        bl = panels[b][1]
        br = panels[b + 1][0]
        for j in range(1, k + 1):
            zb = z0 + t + j * space + (j - 1) * shelf_t
            xs0 = bl + p["shelf_clear"]
            xs1 = br - p["shelf_clear"]
            shelves.append(_box(xs0, xs1, 0, Din, zb, zb + shelf_t))
            pz = zb - p["pin_drop"]
            for py in (p["pin_edge"], Din - p["pin_edge"]):
                # left panel of the bay: hole goes into panel (-x), pin sticks out +x
                xa = bl - p["pin_hole_depth"]
                L = p["pin_hole_depth"] + p["pin_out"]
                pins.append(_cyl(pr, L, (xa, py, pz), (1, 0, 0)))
                holes[b].append(_cyl(pr, p["pin_hole_depth"], (xa, py, pz), (1, 0, 0)))
                # right panel of the bay
                xb = br - p["pin_out"]
                pins.append(_cyl(pr, L, (xb, py, pz), (1, 0, 0)))
                holes[b + 1].append(_cyl(pr, p["pin_hole_depth"], (br, py, pz), (1, 0, 0)))

    # ---------------- carcass ----------------
    side_l = _box(panels[0][0], panels[0][1], 0, carc_d, z0, z1)
    side_r = _box(panels[n][0], panels[n][1], 0, carc_d, z0, z1)
    parts.append(("side_left", _cut(side_l, holes[0]) if holes[0] else side_l))
    parts.append(("side_right", _cut(side_r, holes[n]) if holes[n] else side_r))
    parts.append(("top", _box(t, W - t, 0, carc_d, z1 - t, z1)))
    parts.append(("bottom", _box(t, W - t, 0, carc_d, z0, z0 + t)))

    if inset:
        parts.append(("back", _box(t, W - t, Dc - back_t, Dc, z0 + t, z1 - t)))
    else:
        parts.append(("back", _box(0, W, Dc - back_t, Dc, z0, z1)))

    # inner walls
    for j in range(1, n):
        x0, x1 = panels[j]
        d = _box(x0, x1, 0, Din, z0 + t, z1 - t)
        if holes[j]:
            d = _cut(d, holes[j])
        parts.append((f"divider_{j}", d))

    # shelves and pins
    for i, s in enumerate(shelves, 1):
        parts.append((f"shelf_{i}", s))
    for i, s in enumerate(pins, 1):
        parts.append((f"pin_{i}", s))

    # ---------------- doors ----------------
    dw = cell - 2 * gap
    dh = Hc - 2 * gap
    if dh <= p["hinge_h1"]:
        nh = 2
    elif dh <= p["hinge_h2"]:
        nh = 3
    else:
        nh = 4
    for i in range(n):
        xl = i * cell + gap
        xr = xl + dw
        zb = z0 + gap
        zt = zb + dh
        door = _box(xl, xr, -(gap + door_t), -gap, zb, zt)
        # hinge side
        if n > 1 and i == n - 1 and n % 2 == 1:
            right = True
        else:
            right = (i % 2 == 1)
        cx = (xr - p["hinge_edge"]) if right else (xl + p["hinge_edge"])
        zs = zb + p["hinge_end"]
        ze = zt - p["hinge_end"]
        cups = []
        for h in range(nh):
            cz = zs + h * (ze - zs) / (nh - 1)
            cups.append(_cyl(p["hinge_d"] / 2, p["hinge_depth"] + 1,
                             (cx, -gap + 1, cz), (0, -1, 0)))
        parts.append((f"door_{i + 1}", _cut(door, cups)))

    # ---------------- legs ----------------
    off = p["leg_corner_gap"] + p["leg_d"] / 2
    xa, xb = off, W - off
    ya, yb = off, Dc - off
    nx = _ceil((xb - xa) / p["leg_max_c"]) + 1
    ny = _ceil((yb - ya) / p["leg_max_c"]) + 1
    idx = 1
    for iy in range(ny):
        for ix in range(nx):
            x = xa + ix * (xb - xa) / (nx - 1)
            y = ya + iy * (yb - ya) / (ny - 1)
            parts.append((f"leg_{idx}", _cyl(p["leg_d"] / 2, leg_h, (x, y, 0), (0, 0, 1))))
            idx += 1

    return parts
