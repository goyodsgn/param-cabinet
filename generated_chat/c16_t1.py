import math
import cadquery as cq

PARAMS = {
    # Customer gave inside sizes: inner width 1164, inner depth 516, outer height 850.
    # W = 1164 + 2*18 = 1200 ; Dc = 516 + 10 = 526 ; D = 526 + 22 + 2 = 550
    "W": 1200,
    "H": 850,
    "D": 550,
    "leg_h": 100,
    "back_mode": "onset",
    "top_mode": "inset",
    "t": 18,
    "back_t": 10,
    "divider_t": 18,
    "door_t": 22,
    "shelf_t": 30,
    "door_gap": 2,
    "door_max_w": 600,
    "n_doors": None,
    "door_layout": None,
    "n_shelves": None,
    "shelf_min_gap": 320,
    "bottom_clear_min": None,
    "pin_max_spacing": 500,
    "leg_max_spacing": 600,
    "notes": [
        "Inside sizes converted: W = 1164 + 2*18 = 1200, "
        "Dc = 516 + back_t 10 = 526, D = Dc + door_t 22 + door_gap 2 = 550.",
        "Height 850 is the overall height including the 100 mm legs.",
    ],
}


def _ceil(x):
    return int(math.ceil(round(x, 9)))


def _box(x0, x1, y0, y1, z0, z1):
    return cq.Solid.makeBox(x1 - x0, y1 - y0, z1 - z0, cq.Vector(x0, y0, z0))


def _cut(solid, cutter):
    res = solid.cut(cutter)
    sols = res.Solids()
    return sols[0] if sols else solid


def build(params):
    p = params
    W, H, D = p["W"], p["H"], p["D"]
    leg_h = p["leg_h"]
    t, back_t, div_t = p["t"], p["back_t"], p["divider_t"]
    door_t, shelf_t, gap = p["door_t"], p["shelf_t"], p["door_gap"]
    back_mode, top_mode = p["back_mode"], p["top_mode"]

    Dc = D - door_t - gap
    has_top = top_mode != "none"
    inner_d = Dc - back_t  # depth to the back panel's inner face
    panel_d = inner_d if back_mode == "onset" else Dc

    # ---------- carcass vertical extents ----------
    z_bot = leg_h
    if top_mode == "onset":
        side_top = H - t
    else:
        side_top = H
    clear_lo = leg_h + t
    clear_hi = H - t if has_top else H
    clear_h = clear_hi - clear_lo

    parts = {}  # name -> solid (ordered)
    order = []

    def add(name, solid):
        parts[name] = solid
        order.append(name)

    # ---------- doors / bays ----------
    min_n = max(1, _ceil(W / p["door_max_w"]))
    n = max(min_n, p["n_doors"] or 0)
    layout = p["door_layout"]
    if layout is not None:
        if sum(layout) < min_n:
            layout = None
        else:
            n = sum(layout)
    if layout is None:
        layout = [1] * n
    cw = W / n

    # bay boundaries (in door cells)
    bays = []  # (first_cell, num_cells, kind)
    c = 0
    for kind in layout:
        bays.append((c, kind))
        c += kind
    divider_x = []
    for b in range(1, len(bays)):
        divider_x.append(bays[b][0] * cw)

    # ---------- sides ----------
    side_l = _box(0, t, 0, panel_d, z_bot, side_top)
    side_r = _box(W - t, W, 0, panel_d, z_bot, side_top)
    panels = {"side_left": side_l, "side_right": side_r}

    # ---------- dividers ----------
    for i, dx in enumerate(divider_x, start=1):
        panels["divider_%d" % i] = _box(dx - div_t / 2, dx + div_t / 2, 0, inner_d,
                                        clear_lo, clear_hi)

    # ---------- bays x-ranges ----------
    bay_ranges = []
    nb = len(bays)
    for b in range(nb):
        if b == 0:
            xl, ol = t, "side_left"
        else:
            xl, ol = divider_x[b - 1] + div_t / 2, "divider_%d" % b
        if b == nb - 1:
            xr, orr = W - t, "side_right"
        else:
            xr, orr = divider_x[b] - div_t / 2, "divider_%d" % (b + 1)
        bay_ranges.append((xl, xr, ol, orr))

    # ---------- shelves count & positions ----------
    bcm = p["bottom_clear_min"]
    gmin = p["shelf_min_gap"]
    if p["n_shelves"] is not None:
        k = max(0, int(p["n_shelves"]))
    elif bcm is None:
        k = max(0, int(math.floor((clear_h - gmin) / (gmin + shelf_t))))
    else:
        k = max(0, int(math.floor((clear_h - max(bcm, gmin)) / (gmin + shelf_t))))

    shelf_z = []  # bottom z of each shelf
    if k > 0:
        g = (clear_h - k * shelf_t) / (k + 1)
        if bcm is not None and g < bcm:
            g2 = (clear_h - bcm - k * shelf_t) / k
            for i in range(k):
                shelf_z.append(clear_lo + bcm + i * (g2 + shelf_t))
        else:
            for i in range(1, k + 1):
                shelf_z.append(clear_lo + i * g + (i - 1) * shelf_t)

    # ---------- shelves & pins ----------
    shelves = []
    pins = []
    shelf_depth = inner_d
    span = shelf_depth - 2 * 50
    n_pin = _ceil(span / p["pin_max_spacing"]) + 1
    pin_ys = [50 + i * span / (n_pin - 1) for i in range(n_pin)]
    pr = 2.5
    hole_cutters = {key: [] for key in panels}

    for (xl, xr, ol, orr) in bay_ranges:
        for zb in shelf_z:
            shelves.append(_box(xl + 1, xr - 1, 0, shelf_depth, zb, zb + shelf_t))
            zc = zb - 2.5
            for y in pin_ys:
                # left pin: 8 into left panel, 6 into bay
                pins.append(cq.Solid.makeCylinder(pr, 14, cq.Vector(xl - 8, y, zc),
                                                  cq.Vector(1, 0, 0)))
                hole_cutters[ol].append(cq.Solid.makeCylinder(
                    pr, 8, cq.Vector(xl - 8, y, zc), cq.Vector(1, 0, 0)))
                # right pin
                pins.append(cq.Solid.makeCylinder(pr, 14, cq.Vector(xr - 6, y, zc),
                                                  cq.Vector(1, 0, 0)))
                hole_cutters[orr].append(cq.Solid.makeCylinder(
                    pr, 8, cq.Vector(xr, y, zc), cq.Vector(1, 0, 0)))

    for key in list(panels.keys()):
        s = panels[key]
        for cyl in hole_cutters[key]:
            s = _cut(s, cyl)
        panels[key] = s

    add("side_left", panels["side_left"])
    add("side_right", panels["side_right"])

    # ---------- top / bottom ----------
    add("bottom", _box(t, W - t, 0, panel_d, leg_h, leg_h + t))
    if top_mode == "inset":
        add("top", _box(t, W - t, 0, panel_d, H - t, H))
    elif top_mode == "onset":
        add("top", _box(0, W, 0, panel_d, H - t, H))

    # ---------- back ----------
    if back_mode == "onset":
        add("back", _box(0, W, Dc - back_t, Dc, leg_h, H))
    else:
        add("back", _box(t, W - t, Dc - back_t, Dc, clear_lo, clear_hi))

    # ---------- dividers, shelves, pins ----------
    for i in range(1, len(divider_x) + 1):
        add("divider_%d" % i, panels["divider_%d" % i])
    for i, s in enumerate(shelves, start=1):
        add("shelf_%d" % i, s)
    for i, s in enumerate(pins, start=1):
        add("pin_%d" % i, s)

    # ---------- doors ----------
    door_w = cw - 2 * gap
    door_h = (H - leg_h) - 2 * gap
    if door_h <= 900:
        n_cup = 2
    elif door_h <= 1600:
        n_cup = 3
    else:
        n_cup = 4
    cup_zs = [100 + i * (door_h - 200) / (n_cup - 1) for i in range(n_cup)]

    # hinge sides
    hinges = [None] * n
    all_single = all(v == 1 for v in layout)
    if all_single:
        for i in range(n):
            hinges[i] = "L" if i % 2 == 0 else "R"
        if n % 2 == 1 and n > 1:
            hinges[-1] = "R"
    else:
        for (c0, kind) in bays:
            if kind == 2:
                hinges[c0] = "L"
                hinges[c0 + 1] = "R"
            else:
                center = c0 * cw + cw / 2
                hinges[c0] = "L" if center <= W / 2 else "R"

    for i in range(n):
        x0 = i * cw + gap
        y0 = -(gap + door_t)
        z0 = leg_h + gap
        d = _box(x0, x0 + door_w, y0, -gap, z0, z0 + door_h)
        if hinges[i] == "L":
            cx = x0 + 22.5
        else:
            cx = x0 + door_w - 22.5
        for cz in cup_zs:
            cup = cq.Solid.makeCylinder(17.5, 12, cq.Vector(cx, -gap, z0 + cz),
                                        cq.Vector(0, -1, 0))
            d = _cut(d, cup)
        add("door_%d" % (i + 1), d)

    # ---------- legs ----------
    lr = 20
    off = 30 + lr
    xs_span = (W - off) - off
    ys_span = (Dc - off) - off
    nx = _ceil(xs_span / p["leg_max_spacing"]) + 1
    ny = _ceil(ys_span / p["leg_max_spacing"]) + 1
    lx = [off + i * xs_span / (nx - 1) for i in range(nx)]
    ly = [off + j * ys_span / (ny - 1) for j in range(ny)]
    idx = 1
    for y in ly:
        for x in lx:
            add("leg_%d" % idx, cq.Solid.makeCylinder(lr, leg_h, cq.Vector(x, y, 0),
                                                      cq.Vector(0, 0, 1)))
            idx += 1

    return [(name, parts[name]) for name in order]
