import math
import cadquery as cq

PARAMS = {
    "W": 2400,
    "H": 900,
    "D": 600,
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
    # extra values
    "pin_edge": 50,
    "pin_d": 5,
    "pin_len": 14,
    "pin_hole_depth": 8,
    "shelf_side_clear": 1,
    "cup_d": 35,
    "cup_depth": 12,
    "cup_edge": 22.5,
    "cup_end_dist": 100,
    "leg_d": 40,
    "leg_corner_gap": 30,
    "notes": [
        "W2400 / max door width 600 -> 4 doors (cells of 600), 3 inner walls.",
        "Door height 796 -> 2 hinge cups per door.",
        "Defaults used: legs 100, inset top, onset back, no bottom_clear_min.",
    ],
}


def _ceil(x):
    return int(math.ceil(round(x, 9)))


def _box(x0, x1, y0, y1, z0, z1):
    return cq.Solid.makeBox(x1 - x0, y1 - y0, z1 - z0, cq.Vector(x0, y0, z0))


def _cut(solid, tool):
    r = solid.cut(tool)
    sols = r.Solids()
    return sols[0] if sols else solid


def build(params):
    p = params
    W, H, D = p["W"], p["H"], p["D"]
    leg_h = p["leg_h"]
    t, back_t, dt = p["t"], p["back_t"], p["divider_t"]
    door_t, shelf_t, gap = p["door_t"], p["shelf_t"], p["door_gap"]
    door_max_w = p["door_max_w"]
    top_mode, back_mode = p["top_mode"], p["back_mode"]

    Dc = D - door_t - gap
    inner_d = Dc - back_t  # depth of dividers / shelves
    Dp = inner_d if back_mode == "onset" else Dc  # side/top/bottom depth

    has_top = top_mode != "none"
    z_floor = leg_h + t                      # top of bottom panel
    z_ceil = H - t if has_top else H         # underside of top / carcass top
    clear_h = z_ceil - z_floor

    # ---------- doors / bays ----------
    layout = p.get("door_layout")
    n_min = max(1, _ceil(W / door_max_w))
    if layout:
        layout = list(layout)
        n = sum(layout)
        if n < n_min:  # would break the 600 limit -> fall back to automatic
            layout = None
    if not layout:
        n = n_min
        if p.get("n_doors"):
            n = max(n, int(p["n_doors"]))
        layout = [1] * n
        all_single = True
    else:
        all_single = all(b == 1 for b in layout)
    cell = W / n

    # hinge sides
    hinges = []
    if all_single:
        for i in range(n):
            hinges.append("L" if i % 2 == 0 else "R")
        if n > 1 and n % 2 == 1:
            hinges[-1] = "R"
    else:
        idx = 0
        for b in layout:
            if b == 2:
                hinges += ["L", "R"]
            else:
                cx = (idx + 0.5) * cell
                hinges.append("L" if cx <= W / 2 else "R")
            idx += b

    # bay boundaries (x centers of dividers)
    div_x = []
    acc = 0
    for b in layout[:-1]:
        acc += b
        div_x.append(acc * cell)

    # ---------- panels ----------
    panels = {}
    side_z1 = H - t if top_mode == "onset" else H
    panels["side_left"] = _box(0, t, 0, Dp, leg_h, side_z1)
    panels["side_right"] = _box(W - t, W, 0, Dp, leg_h, side_z1)
    panels["bottom"] = _box(t, W - t, 0, Dp, leg_h, leg_h + t)
    if top_mode == "inset":
        panels["top"] = _box(t, W - t, 0, Dp, H - t, H)
    elif top_mode == "onset":
        panels["top"] = _box(0, W, 0, Dp, H - t, H)
    if back_mode == "onset":
        panels["back"] = _box(0, W, Dc - back_t, Dc, leg_h, H)
    else:
        panels["back"] = _box(t, W - t, Dc - back_t, Dc, z_floor, z_ceil)
    for j, xc in enumerate(div_x):
        panels["divider_%d" % (j + 1)] = _box(xc - dt / 2, xc + dt / 2, 0, inner_d, z_floor, z_ceil)

    # ---------- bays ----------
    faces = [(t, "side_left")]
    bays = []
    left_face, left_name = t, "side_left"
    for j, xc in enumerate(div_x):
        bays.append((left_face, left_name, xc - dt / 2, "divider_%d" % (j + 1)))
        left_face, left_name = xc + dt / 2, "divider_%d" % (j + 1)
    bays.append((left_face, left_name, W - t, "side_right"))

    # ---------- shelf count and heights ----------
    bcm = p.get("bottom_clear_min")
    min_gap = p["shelf_min_gap"]
    if p.get("n_shelves") is not None:
        k = max(0, int(p["n_shelves"]))
    else:
        base = max(bcm, min_gap) if bcm else min_gap
        k = max(0, int(math.floor(round((clear_h - base) / (min_gap + shelf_t), 9))))
    shelf_bottoms = []
    if k > 0:
        g = (clear_h - k * shelf_t) / (k + 1)
        if bcm and g < bcm and p.get("n_shelves") is None:
            g2 = (clear_h - bcm - k * shelf_t) / k
            for i in range(k):
                shelf_bottoms.append(z_floor + bcm + i * (g2 + shelf_t))
        else:
            for i in range(k):
                shelf_bottoms.append(z_floor + g + i * (g + shelf_t))

    # ---------- shelves and pins ----------
    shelves = []
    pins = []
    cuts = {}  # panel name -> list of tool solids
    sc = p["shelf_side_clear"]
    pe = p["pin_edge"]
    pr = p["pin_d"] / 2.0
    plen = p["pin_len"]
    hd = p["pin_hole_depth"]
    out = plen - hd
    span = inner_d - 2 * pe
    m = _ceil(span / p["pin_max_spacing"]) + 1 if span > 0 else 1
    ypins = [pe + i * span / (m - 1) for i in range(m)] if m > 1 else [inner_d / 2.0]

    for (xl, nl, xr, nr) in bays:
        for zb in shelf_bottoms:
            shelves.append(_box(xl + sc, xr - sc, 0, inner_d, zb, zb + shelf_t))
            zp = zb - p["pin_d"] / 2.0
            for y in ypins:
                # left pin
                pins.append(cq.Solid.makeCylinder(pr, plen, cq.Vector(xl - hd, y, zp), cq.Vector(1, 0, 0)))
                cuts.setdefault(nl, []).append(
                    cq.Solid.makeCylinder(pr, hd, cq.Vector(xl - hd, y, zp), cq.Vector(1, 0, 0)))
                # right pin
                pins.append(cq.Solid.makeCylinder(pr, plen, cq.Vector(xr - out, y, zp), cq.Vector(1, 0, 0)))
                cuts.setdefault(nr, []).append(
                    cq.Solid.makeCylinder(pr, hd, cq.Vector(xr, y, zp), cq.Vector(1, 0, 0)))

    for name, tools in cuts.items():
        s = panels[name]
        for tool in tools:
            s = _cut(s, tool)
        panels[name] = s

    # ---------- doors ----------
    doors = []
    dw = cell - 2 * gap
    dh = (H - leg_h) - 2 * gap
    nh = 2 if dh <= 900 else (3 if dh <= 1600 else 4)
    zb0 = leg_h + gap
    zc = [zb0 + p["cup_end_dist"] + i * (dh - 2 * p["cup_end_dist"]) / (nh - 1) for i in range(nh)]
    for i in range(n):
        x0 = i * cell + gap
        d = _box(x0, x0 + dw, -(gap + door_t), -gap, zb0, zb0 + dh)
        cx = x0 + p["cup_edge"] if hinges[i] == "L" else x0 + dw - p["cup_edge"]
        for z in zc:
            cup = cq.Solid.makeCylinder(p["cup_d"] / 2.0, p["cup_depth"],
                                        cq.Vector(cx, -gap - p["cup_depth"], z), cq.Vector(0, 1, 0))
            d = _cut(d, cup)
        doors.append(d)

    # ---------- legs ----------
    legs = []
    lr = p["leg_d"] / 2.0
    off = p["leg_corner_gap"] + lr
    xs0, xs1 = off, W - off
    ys0, ys1 = off, Dc - off
    nx = _ceil((xs1 - xs0) / p["leg_max_spacing"]) + 1
    ny = _ceil((ys1 - ys0) / p["leg_max_spacing"]) + 1
    xl_ = [xs0 + i * (xs1 - xs0) / (nx - 1) for i in range(nx)]
    yl_ = [ys0 + i * (ys1 - ys0) / (ny - 1) for i in range(ny)]
    for y in yl_:
        for x in xl_:
            legs.append(cq.Solid.makeCylinder(lr, leg_h, cq.Vector(x, y, 0), cq.Vector(0, 0, 1)))

    # ---------- assemble ----------
    parts = []
    for nm in ("side_left", "side_right", "top", "bottom", "back"):
        if nm in panels:
            parts.append((nm, panels[nm]))
    for j in range(len(div_x)):
        parts.append(("divider_%d" % (j + 1), panels["divider_%d" % (j + 1)]))
    for i, s in enumerate(shelves):
        parts.append(("shelf_%d" % (i + 1), s))
    for i, s in enumerate(pins):
        parts.append(("pin_%d" % (i + 1), s))
    for i, s in enumerate(doors):
        parts.append(("door_%d" % (i + 1), s))
    for i, s in enumerate(legs):
        parts.append(("leg_%d" % (i + 1), s))
    return parts
