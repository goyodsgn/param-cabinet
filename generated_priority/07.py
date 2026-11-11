import math
import cadquery as cq

PARAMS = {
    "W": 1800,
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
    "notes": [
        "Customer asked for 2 doors, but W = 1800 with a maximum door cell width of 600 "
        "needs at least ceil(1800/600) = 3 doors (ABSOLUTE rule).",
        "Built with 3 doors (n_doors = automatic), each cell 600 wide, and 2 inner walls "
        "behind the door joints.",
    ],
}


def _ceil(x):
    return int(math.ceil(round(x, 9)))


def _box(x0, x1, y0, y1, z0, z1):
    return cq.Solid.makeBox(x1 - x0, y1 - y0, z1 - z0, cq.Vector(x0, y0, z0))


def _cyl(r, h, pnt, d):
    return cq.Solid.makeCylinder(r, h, cq.Vector(*pnt), cq.Vector(*d))


def _solid(shape):
    if isinstance(shape, cq.Solid):
        return shape
    sols = shape.Solids()
    return sols[0] if len(sols) == 1 else shape


def build(params):
    p = params
    W, H, D = p["W"], p["H"], p["D"]
    leg_h = p["leg_h"]
    t, back_t, dt = p["t"], p["back_t"], p["divider_t"]
    door_t, shelf_t, gap = p["door_t"], p["shelf_t"], p["door_gap"]
    door_max_w = p["door_max_w"]

    Dc = D - door_t - gap
    ch = H - leg_h
    z_bot = leg_h
    z_top = H
    inner_depth = Dc - back_t  # y-extent of shelves / dividers

    # ---- door count
    n_min = max(1, _ceil(W / door_max_w))
    n = n_min
    if p.get("n_doors") is not None:
        n = max(n_min, int(p["n_doors"]))
    cell = W / n

    parts = []
    cuts = {}  # panel name -> list of cutting solids

    # ---- carcass
    if p["back_mode"] == "inset":
        panel_d = Dc
        back = _box(t, W - t, Dc - back_t, Dc, z_bot + t, z_top - t)
    else:
        panel_d = Dc - back_t
        back = _box(0, W, Dc - back_t, Dc, z_bot, z_top)

    sides = {
        "side_left": _box(0, t, 0, panel_d, z_bot, z_top),
        "side_right": _box(W - t, W, 0, panel_d, z_bot, z_top),
    }
    top = _box(t, W - t, 0, panel_d, z_top - t, z_top)
    bottom = _box(t, W - t, 0, panel_d, z_bot, z_bot + t)

    panels = {}  # name -> solid (for hole cutting)
    panels["side_left"] = sides["side_left"]
    panels["side_right"] = sides["side_right"]

    # ---- dividers
    for j in range(1, n):
        c = j * cell
        panels["divider_%d" % j] = _box(c - dt / 2, c + dt / 2, 0, inner_depth,
                                        z_bot + t, z_top - t)

    # ---- bays: (x0, x1, left panel name, right panel name)
    bays = []
    for i in range(n):
        if i == 0:
            x0, ln = t, "side_left"
        else:
            x0, ln = i * cell + dt / 2, "divider_%d" % i
        if i == n - 1:
            x1, rn = W - t, "side_right"
        else:
            x1, rn = (i + 1) * cell - dt / 2, "divider_%d" % (i + 1)
        bays.append((x0, x1, ln, rn))

    # ---- shelves and pins
    clear_h = ch - 2 * t
    if p.get("n_shelves") is None:
        k = max(0, int(math.floor((clear_h - p["shelf_min_gap"]) / (p["shelf_min_gap"] + shelf_t))))
    else:
        k = max(0, int(p["n_shelves"]))
    space = (clear_h - k * shelf_t) / (k + 1)

    pin_d = 5.0
    pin_r = pin_d / 2
    pin_edge = 50.0
    span = inner_depth - 2 * pin_edge
    n_pins = _ceil(span / p["pin_max_spacing"]) + 1
    pin_ys = [pin_edge + s * span / (n_pins - 1) for s in range(n_pins)]

    shelves = []
    pins = []
    for (x0, x1, ln, rn) in bays:
        for s in range(1, k + 1):
            zb = z_bot + t + s * space + (s - 1) * shelf_t
            shelves.append(_box(x0 + 1, x1 - 1, 0, inner_depth, zb, zb + shelf_t))
            zc = zb - 2.5
            for y in pin_ys:
                # left panel: hole 8 deep into panel, pin sticks 6 into bay
                cuts.setdefault(ln, []).append(_cyl(pin_r, 8, (x0 - 8, y, zc), (1, 0, 0)))
                pins.append(_cyl(pin_r, 14, (x0 - 8, y, zc), (1, 0, 0)))
                # right panel
                cuts.setdefault(rn, []).append(_cyl(pin_r, 8, (x1, y, zc), (1, 0, 0)))
                pins.append(_cyl(pin_r, 14, (x1 - 6, y, zc), (1, 0, 0)))

    # ---- assemble panels with holes
    def finish(name, solid):
        for c in cuts.get(name, []):
            solid = _solid(solid.cut(c))
        return solid

    parts.append(("side_left", finish("side_left", panels["side_left"])))
    parts.append(("side_right", finish("side_right", panels["side_right"])))
    parts.append(("top", top))
    parts.append(("bottom", bottom))
    parts.append(("back", back))
    for j in range(1, n):
        nm = "divider_%d" % j
        parts.append((nm, finish(nm, panels[nm])))
    for i, s in enumerate(shelves):
        parts.append(("shelf_%d" % (i + 1), s))
    for i, pn in enumerate(pins):
        parts.append(("pin_%d" % (i + 1), pn))

    # ---- doors with hinge cups
    dw = cell - 2 * gap
    dh = ch - 2 * gap
    if dh <= 900:
        n_h = 2
    elif dh <= 1600:
        n_h = 3
    else:
        n_h = 4
    z_cups = [100 + m * (dh - 200) / (n_h - 1) for m in range(n_h)]
    for i in range(n):
        xd = i * cell + gap
        zd = leg_h + gap
        door = _box(xd, xd + dw, -(gap + door_t), -gap, zd, zd + dh)
        hinge_left = (i % 2 == 0)
        if n % 2 == 1 and n > 1 and i == n - 1:
            hinge_left = False
        cx = xd + 22.5 if hinge_left else xd + dw - 22.5
        for zc in z_cups:
            cup = _cyl(17.5, 12, (cx, -gap, zd + zc), (0, -1, 0))
            door = _solid(door.cut(cup))
        parts.append(("door_%d" % (i + 1), door))

    # ---- legs
    leg_r = 20.0
    off = 30.0 + leg_r
    sx = W - 2 * off
    sy = Dc - 2 * off
    nx = _ceil(sx / p["leg_max_spacing"]) + 1
    ny = _ceil(sy / p["leg_max_spacing"]) + 1
    xs = [off + a * sx / (nx - 1) for a in range(nx)]
    ys = [off + b * sy / (ny - 1) for b in range(ny)]
    li = 1
    for y in ys:
        for x in xs:
            parts.append(("leg_%d" % li, _cyl(leg_r, leg_h, (x, y, 0), (0, 0, 1))))
            li += 1

    return parts
