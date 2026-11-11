import math
import cadquery as cq

PARAMS = {
    "W": 1200,
    "H": 850,
    "D": 580,
    "leg_h": 100,
    "back_mode": "onset",
    "t": 18,
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
    # extra parameters
    "pin_d": 5,
    "pin_hole_depth": 8,
    "pin_out": 6,
    "pin_edge": 50,
    "shelf_clear": 1,
    "hinge_d": 35,
    "hinge_depth": 12,
    "hinge_edge": 22.5,
    "hinge_end": 100,
    "leg_d": 40,
    "leg_corner_gap": 30,
    "notes": [],
}


def _box(x0, x1, y0, y1, z0, z1):
    return (cq.Workplane("XY")
            .box(x1 - x0, y1 - y0, z1 - z0, centered=False)
            .translate((x0, y0, z0)).val())


def _cyl(r, h, p, d):
    return cq.Solid.makeCylinder(r, h, cq.Vector(*p), cq.Vector(*d))


def _solid(shape):
    if isinstance(shape, cq.Solid):
        return shape
    sols = shape.Solids()
    return sols[0] if len(sols) == 1 else cq.Compound.makeCompound(sols)


def _cut_all(base, cutters):
    s = base
    for c in cutters:
        s = s.cut(c)
    return _solid(s)


def build(params):
    p = params
    W, H, D = p["W"], p["H"], p["D"]
    leg_h = p["leg_h"]
    t, back_t, div_t = p["t"], p["back_t"], p["divider_t"]
    door_t, shelf_t, gap = p["door_t"], p["shelf_t"], p["door_gap"]
    inset = p["back_mode"] == "inset"

    Dc = D - door_t - gap
    inner_d = Dc - back_t                      # depth up to back panel inner face
    panel_d = Dc if inset else inner_d         # depth of sides/top/bottom
    z0, z1 = leg_h, H
    carc_h = H - leg_h
    clear_h = carc_h - 2 * t

    # ---- door count (never fewer than automatic, never cell wider than max)
    n_auto = max(1, math.ceil(W / p["door_max_w"]))
    n = n_auto
    if p["n_doors"] is not None:
        n = max(n_auto, int(p["n_doors"]))
    cell = W / n

    parts = []
    cutters = {}  # panel name -> list of hole solids

    # ---- bays
    centers = [j * cell for j in range(1, n)]
    bays = []
    for b in range(n):
        xl = t if b == 0 else centers[b - 1] + div_t / 2
        xr = (W - t) if b == n - 1 else centers[b] - div_t / 2
        lname = "side_left" if b == 0 else "divider_%d" % b
        rname = "side_right" if b == n - 1 else "divider_%d" % (b + 1)
        bays.append((xl, xr, lname, rname))

    # ---- shelf count
    if p["n_shelves"] is None:
        k = max(0, math.floor((clear_h - p["shelf_min_gap"]) / (p["shelf_min_gap"] + shelf_t)))
    else:
        k = max(0, int(p["n_shelves"]))
    space = (clear_h - k * shelf_t) / (k + 1) if k >= 0 else clear_h

    # ---- shelves and pins
    pin_r = p["pin_d"] / 2
    hd, po = p["pin_hole_depth"], p["pin_out"]
    shelf_d = inner_d
    span = shelf_d - 2 * p["pin_edge"]
    n_pins = math.ceil(span / p["pin_max_spacing"]) + 1
    pin_ys = [p["pin_edge"] + i * span / (n_pins - 1) for i in range(n_pins)]

    shelves = []
    pins = []
    for (xl, xr, lname, rname) in bays:
        for i in range(1, k + 1):
            zb = z0 + t + i * space + (i - 1) * shelf_t
            sc = p["shelf_clear"]
            shelves.append(_box(xl + sc, xr - sc, 0, shelf_d, zb, zb + shelf_t))
            zc = zb - pin_r
            for y in pin_ys:
                # left panel: hole hd deep into the panel, sticks po out
                pins.append(_cyl(pin_r, hd + po, (xl - hd, y, zc), (1, 0, 0)))
                cutters.setdefault(lname, []).append(
                    _cyl(pin_r, hd, (xl - hd, y, zc), (1, 0, 0)))
                # right panel
                pins.append(_cyl(pin_r, hd + po, (xr - po, y, zc), (1, 0, 0)))
                cutters.setdefault(rname, []).append(
                    _cyl(pin_r, hd, (xr, y, zc), (1, 0, 0)))

    # ---- carcass panels
    parts.append(("side_left", _cut_all(_box(0, t, 0, panel_d, z0, z1),
                                         cutters.get("side_left", []))))
    parts.append(("side_right", _cut_all(_box(W - t, W, 0, panel_d, z0, z1),
                                          cutters.get("side_right", []))))
    parts.append(("top", _box(t, W - t, 0, panel_d, z1 - t, z1)))
    parts.append(("bottom", _box(t, W - t, 0, panel_d, z0, z0 + t)))
    if inset:
        parts.append(("back", _box(t, W - t, Dc - back_t, Dc, z0 + t, z1 - t)))
    else:
        parts.append(("back", _box(0, W, Dc - back_t, Dc, z0, z1)))

    # ---- dividers
    for j, cx in enumerate(centers, start=1):
        name = "divider_%d" % j
        d = _box(cx - div_t / 2, cx + div_t / 2, 0, inner_d, z0 + t, z1 - t)
        parts.append((name, _cut_all(d, cutters.get(name, []))))

    # ---- shelves and pins
    for i, s in enumerate(shelves, start=1):
        parts.append(("shelf_%d" % i, _solid(s)))
    for i, s in enumerate(pins, start=1):
        parts.append(("pin_%d" % i, _solid(s)))

    # ---- doors
    dw = cell - 2 * gap
    dh = carc_h - 2 * gap
    zb = z0 + gap
    n_h = 2 if dh <= 900 else (3 if dh <= 1600 else 4)
    cup_r = p["hinge_d"] / 2
    for i in range(n):
        x0 = i * cell + gap
        left = (i % 2 == 0)
        if n > 1 and n % 2 == 1 and i == n - 1:
            left = False
        door = _box(x0, x0 + dw, -(gap + door_t), -gap, zb, zb + dh)
        cx = x0 + p["hinge_edge"] if left else x0 + dw - p["hinge_edge"]
        cs = []
        first = zb + p["hinge_end"]
        last = zb + dh - p["hinge_end"]
        for m in range(n_h):
            cz = first + m * (last - first) / (n_h - 1)
            cs.append(_cyl(cup_r, p["hinge_depth"], (cx, -gap, cz), (0, -1, 0)))
        parts.append(("door_%d" % (i + 1), _cut_all(door, cs)))

    # ---- legs
    lr = p["leg_d"] / 2
    off = p["leg_corner_gap"] + lr
    sx = W - 2 * off
    sy = Dc - 2 * off
    nx = math.ceil(sx / p["leg_max_spacing"]) + 1
    ny = math.ceil(sy / p["leg_max_spacing"]) + 1
    idx = 1
    for a in range(nx):
        x = off + a * sx / (nx - 1)
        for b in range(ny):
            y = off + b * sy / (ny - 1)
            parts.append(("leg_%d" % idx, _cyl(lr, leg_h, (x, y, 0), (0, 0, 1))))
            idx += 1

    return parts
