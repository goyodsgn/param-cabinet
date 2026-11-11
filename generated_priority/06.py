import math
import cadquery as cq

PARAMS = {
    "W": 1800,
    "H": 1000,
    "D": 650,
    "leg_h": 150,
    "back_mode": "onset",
    "t": 15,
    "back_t": 10,
    "divider_t": 18,
    "door_t": 22,
    "shelf_t": 30,
    "door_gap": 2,
    "door_max_w": 600,
    "n_doors": None,
    "n_shelves": None,
    "shelf_min_gap": 320,
    "pin_max_spacing": 500,
    "leg_max_spacing": 600,
    # extra rule values
    "shelf_clearance": 1,
    "pin_edge": 50,
    "pin_d": 5,
    "pin_len": 14,
    "pin_hole_depth": 8,
    "hinge_d": 35,
    "hinge_depth": 12,
    "hinge_edge": 22.5,
    "hinge_end": 100,
    "leg_d": 40,
    "leg_inset": 30,
    "notes": [
        "'판 두께 15' was read as t = 15 (sides, top, bottom). Back, dividers, doors and shelves keep their defaults.",
        "W = 1800 needs 3 doors (ceil(1800/600)), so 2 inner walls and 3 bays with shelves are generated automatically.",
    ],
}


def _solid(shape):
    sols = shape.Solids()
    return sols[0] if sols else shape


def _box(x0, x1, y0, y1, z0, z1):
    return cq.Solid.makeBox(x1 - x0, y1 - y0, z1 - z0, cq.Vector(x0, y0, z0))


def _cyl_x(x0, length, y, z, d):
    return cq.Solid.makeCylinder(d / 2.0, length, cq.Vector(x0, y, z), cq.Vector(1, 0, 0))


def _cyl_y(x, y0, length, z, d):
    return cq.Solid.makeCylinder(d / 2.0, length, cq.Vector(x, y0, z), cq.Vector(0, 1, 0))


def _hinge_count(h):
    if h <= 900:
        return 2
    if h <= 1600:
        return 3
    return 4


def build(params):
    p = params
    W, H, D = p["W"], p["H"], p["D"]
    leg_h = p["leg_h"]
    t, back_t, div_t = p["t"], p["back_t"], p["divider_t"]
    door_t, shelf_t, gap = p["door_t"], p["shelf_t"], p["door_gap"]
    mode = p["back_mode"]

    Dc = D - door_t - gap
    zb, zt = leg_h, H
    ch = H - leg_h
    inner_depth = Dc - back_t  # sides/top/bottom depth in onset, shelf/divider depth always
    panel_depth = inner_depth if mode == "onset" else Dc

    # door count
    n_auto = max(1, math.ceil(W / p["door_max_w"]))
    n = n_auto if p["n_doors"] is None else max(n_auto, int(p["n_doors"]))
    cell = W / n

    parts = []
    holes = {}  # panel name -> list of tools

    # ---- dividers (centers)
    div_names = []
    div_x = []
    for j in range(1, n):
        div_names.append("divider_%d" % j)
        div_x.append(j * cell)

    # ---- bays
    edges = [(None, t)]  # placeholder for readability
    bays = []  # (x0, x1, left_panel_name, right_panel_name)
    for i in range(n):
        if i == 0:
            x0, ln = t, "side_left"
        else:
            x0, ln = div_x[i - 1] + div_t / 2.0, div_names[i - 1]
        if i == n - 1:
            x1, rn = W - t, "side_right"
        else:
            x1, rn = div_x[i] - div_t / 2.0, div_names[i]
        bays.append((x0, x1, ln, rn))

    # ---- shelves + pins
    clear_h = ch - 2 * t
    if p["n_shelves"] is None:
        k = max(0, math.floor((clear_h - p["shelf_min_gap"]) / (p["shelf_min_gap"] + shelf_t)))
    else:
        k = max(0, int(p["n_shelves"]))

    shelves = []
    pins = []
    if k > 0:
        space = (clear_h - k * shelf_t) / (k + 1)
        sc = p["shelf_clearance"]
        pe = p["pin_edge"]
        span = inner_depth - 2 * pe
        npin = math.ceil(span / p["pin_max_spacing"]) + 1
        pys = [pe + i * span / (npin - 1) for i in range(npin)] if npin > 1 else [pe]
        pd, plen, hd = p["pin_d"], p["pin_len"], p["pin_hole_depth"]
        out = plen - hd
        for (x0, x1, ln, rn) in bays:
            for s in range(k):
                zs = zb + t + space * (s + 1) + shelf_t * s
                shelves.append(_box(x0 + sc, x1 - sc, 0, inner_depth, zs, zs + shelf_t))
                zc = zs - pd / 2.0
                for y in pys:
                    # left pin
                    pins.append(_cyl_x(x0 - hd, plen, y, zc, pd))
                    holes.setdefault(ln, []).append(_cyl_x(x0 - hd, hd, y, zc, pd))
                    # right pin
                    pins.append(_cyl_x(x1 - out, plen, y, zc, pd))
                    holes.setdefault(rn, []).append(_cyl_x(x1, hd, y, zc, pd))

    def with_holes(name, solid):
        for tool in holes.get(name, []):
            solid = _solid(solid.cut(tool))
        return solid

    # ---- carcass panels
    parts.append(("side_left", with_holes("side_left", _box(0, t, 0, panel_depth, zb, zt))))
    parts.append(("side_right", with_holes("side_right", _box(W - t, W, 0, panel_depth, zb, zt))))
    parts.append(("top", _box(t, W - t, 0, panel_depth, zt - t, zt)))
    parts.append(("bottom", _box(t, W - t, 0, panel_depth, zb, zb + t)))
    if mode == "onset":
        parts.append(("back", _box(0, W, Dc - back_t, Dc, zb, zt)))
    else:
        parts.append(("back", _box(t, W - t, Dc - back_t, Dc, zb + t, zt - t)))

    # ---- dividers
    for name, cx in zip(div_names, div_x):
        d = _box(cx - div_t / 2.0, cx + div_t / 2.0, 0, inner_depth, zb + t, zt - t)
        parts.append((name, with_holes(name, d)))

    # ---- shelves
    for i, s in enumerate(shelves):
        parts.append(("shelf_%d" % (i + 1), s))

    # ---- pins
    for i, s in enumerate(pins):
        parts.append(("pin_%d" % (i + 1), s))

    # ---- doors
    dw = cell - 2 * gap
    dh = ch - 2 * gap
    m = _hinge_count(dh)
    he = p["hinge_end"]
    for i in range(n):
        dx = i * cell + gap
        dz = zb + gap
        door = _box(dx, dx + dw, -(gap + door_t), -gap, dz, dz + dh)
        if i % 2 == 0:
            hinge_left = True
        else:
            hinge_left = False
        if n > 1 and n % 2 == 1 and i == n - 1:
            hinge_left = False
        cx = dx + p["hinge_edge"] if hinge_left else dx + dw - p["hinge_edge"]
        for c in range(m):
            lz = he + c * (dh - 2 * he) / (m - 1) if m > 1 else dh / 2.0
            cup = _cyl_y(cx, -gap - p["hinge_depth"], p["hinge_depth"], dz + lz, p["hinge_d"])
            door = _solid(door.cut(cup))
        parts.append(("door_%d" % (i + 1), door))

    # ---- legs
    ld = p["leg_d"]
    li = p["leg_inset"] + ld / 2.0
    xs0, xs1 = li, W - li
    ys0, ys1 = li, Dc - li
    spx = xs1 - xs0
    spy = ys1 - ys0
    nx = math.ceil(spx / p["leg_max_spacing"]) + 1
    ny = math.ceil(spy / p["leg_max_spacing"]) + 1
    xl = [xs0 + i * spx / (nx - 1) for i in range(nx)] if nx > 1 else [xs0]
    yl = [ys0 + j * spy / (ny - 1) for j in range(ny)] if ny > 1 else [ys0]
    idx = 1
    for y in yl:
        for x in xl:
            leg = cq.Solid.makeCylinder(ld / 2.0, leg_h, cq.Vector(x, y, 0), cq.Vector(0, 0, 1))
            parts.append(("leg_%d" % idx, leg))
            idx += 1

    return parts
