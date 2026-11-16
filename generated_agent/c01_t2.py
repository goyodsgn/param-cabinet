import math
import cadquery as cq

PARAMS = {
    "W": 1500, "H": 850, "D": 600, "leg_h": 100,
    "back_mode": "onset", "top_mode": "onset",
    "t": 18, "back_t": 10, "divider_t": 18, "door_t": 22, "shelf_t": 30,
    "door_gap": 2, "door_max_w": 600, "n_doors": None,
    "door_layout": [1, 2], "single_door_hinge": None,
    "n_shelves": None, "shelf_min_gap": 320, "bottom_clear_min": None,
    "pin_max_spacing": 500, "leg_max_spacing": 600,
    "notes": [],
}


def _box(x0, x1, y0, y1, z0, z1):
    return cq.Solid.makeBox(x1 - x0, y1 - y0, z1 - z0, cq.Vector(x0, y0, z0))


def _cyl(r, h, x, y, z, d):
    return cq.Solid.makeCylinder(r, h, cq.Vector(x, y, z), cq.Vector(*d))


def _lin(a, b, n):
    if n == 1:
        return [(a + b) / 2]
    return [a + (b - a) * i / (n - 1) for i in range(n)]


def build(params):
    p = params
    W, H, D = p["W"], p["H"], p["D"]
    leg_h, t, back_t = p["leg_h"], p["t"], p["back_t"]
    dt, door_t, st, gap = p["divider_t"], p["door_t"], p["shelf_t"], p["door_gap"]
    top_mode, back_mode = p["top_mode"], p["back_mode"]
    Dc = D - door_t - gap
    inner_d = Dc - back_t

    # ---- door cells / bays
    layout = p["door_layout"]
    if layout:
        n = sum(layout)
    else:
        n = p["n_doors"] or 1
        n = max(n, math.ceil(W / p["door_max_w"]), 1)
        layout = [1] * n
    if p["single_door_hinge"]:
        layout = [1] * n
    cw = W / n
    bays = []  # (first cell, count)
    c = 0
    for cnt in layout:
        bays.append((c, cnt))
        c += cnt

    # ---- carcass extents
    has_top = top_mode != "none"
    z0 = leg_h + t
    z1 = H - t if has_top else H
    side_top = H - t if top_mode == "onset" else H
    depth = inner_d if back_mode == "onset" else Dc

    # ---- vertical panels (dividers)
    div_x = [bays[b][0] * cw for b in range(1, len(bays))]

    # ---- shelves
    clear_h = z1 - z0
    bcm = p["bottom_clear_min"]
    if p["n_shelves"] is not None:
        k = p["n_shelves"]
    else:
        base = max(bcm, p["shelf_min_gap"]) if bcm else p["shelf_min_gap"]
        k = max(0, math.floor((clear_h - base) / (p["shelf_min_gap"] + st)))
    shelf_z = []
    if k > 0:
        g = (clear_h - k * st) / (k + 1)
        if bcm and g < bcm:
            low = z0 + bcm
            shelf_z.append(low)
            g2 = (z1 - (low + st) - (k - 1) * st) / k
            for i in range(1, k):
                shelf_z.append(low + st + g2 * i + (i - 1) * st)
        else:
            for i in range(1, k + 1):
                shelf_z.append(z0 + g * i + (i - 1) * st)

    # ---- panels with pin holes
    panels = {}
    panels["side_left"] = _box(0, t, 0, depth, leg_h, side_top)
    panels["side_right"] = _box(W - t, W, 0, depth, leg_h, side_top)
    for j, cx in enumerate(div_x):
        panels["divider_%d" % (j + 1)] = _box(cx - dt / 2, cx + dt / 2, 0, inner_d, z0, z1)
    holes = {name: [] for name in panels}
    shelves, pins = [], []

    span = inner_d - 100
    n_pins = math.ceil(span / p["pin_max_spacing"]) + 1
    pin_y = _lin(50, inner_d - 50, n_pins)

    for b in range(len(bays)):
        if b == 0:
            xl, lname = t, "side_left"
        else:
            xl, lname = div_x[b - 1] + dt / 2, "divider_%d" % b
        if b == len(bays) - 1:
            xr, rname = W - t, "side_right"
        else:
            xr, rname = div_x[b] - dt / 2, "divider_%d" % (b + 1)
        for zb in shelf_z:
            shelves.append(_box(xl + 1, xr - 1, 0, inner_d, zb, zb + st))
            for y in pin_y:
                zc = zb - 2.5
                holes[lname].append(_cyl(2.5, 8, xl - 8, y, zc, (1, 0, 0)))
                holes[rname].append(_cyl(2.5, 8, xr, y, zc, (1, 0, 0)))
                pins.append(_cyl(2.5, 14, xl - 8, y, zc, (1, 0, 0)))
                pins.append(_cyl(2.5, 14, xr - 6, y, zc, (1, 0, 0)))

    parts = []
    for name, s in panels.items():
        for h in holes[name]:
            s = s.cut(h)
        sol = s.Solids()
        parts.append((name, sol[0] if sol else s))

    if has_top:
        if top_mode == "onset":
            parts.append(("top", _box(0, W, 0, depth, H - t, H)))
        else:
            parts.append(("top", _box(t, W - t, 0, depth, H - t, H)))
    parts.append(("bottom", _box(t, W - t, 0, depth, leg_h, leg_h + t)))
    if back_mode == "onset":
        parts.append(("back", _box(0, W, Dc - back_t, Dc, leg_h, H)))
    else:
        parts.append(("back", _box(t, W - t, Dc - back_t, Dc, z0, z1)))
    for i, s in enumerate(shelves):
        parts.append(("shelf_%d" % (i + 1), s))
    for i, s in enumerate(pins):
        parts.append(("pin_%d" % (i + 1), s))

    # ---- doors
    door_h = (H - leg_h) - 2 * gap
    n_h = 2 if door_h <= 900 else (3 if door_h <= 1600 else 4)
    hinge = []
    if p["single_door_hinge"]:
        hinge = [p["single_door_hinge"]] * n
    else:
        for (c0, cnt) in bays:
            if cnt == 2:
                hinge += ["left", "right"]
            elif len(layout) == 1 or any(x == 2 for x in layout):
                center = (c0 + 0.5) * cw
                hinge.append("left" if center <= W / 2 else "right")
            else:
                hinge.append(None)
        if None in hinge:
            hinge = ["left" if i % 2 == 0 else "right" for i in range(n)]
            if n > 1 and n % 2 == 1:
                hinge[-1] = "right"
    for i in range(n):
        x0 = i * cw + gap
        x1 = (i + 1) * cw - gap
        zb = leg_h + gap
        zt = zb + door_h
        d = _box(x0, x1, -(gap + door_t), -gap, zb, zt)
        cx = x0 + 22.5 if hinge[i] == "left" else x1 - 22.5
        for zc in _lin(zb + 100, zt - 100, n_h):
            d = d.cut(_cyl(17.5, 12, cx, -gap - 12, zc, (0, 1, 0)))
        parts.append(("door_%d" % (i + 1), d.Solids()[0]))

    # ---- legs
    nx = math.ceil((W - 100) / p["leg_max_spacing"]) + 1
    ny = math.ceil((Dc - 100) / p["leg_max_spacing"]) + 1
    li = 1
    for x in _lin(50, W - 50, nx):
        for y in _lin(50, Dc - 50, ny):
            parts.append(("leg_%d" % li, _cyl(20, leg_h, x, y, 0, (0, 0, 1))))
            li += 1
    return parts
