import math
import cadquery as cq

PARAMS = {
    "W": 1200,
    "H": 850,
    "D": 600,
    "leg_h": 100,
    "back_mode": "inset",
    "top_mode": "none",
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
    "pin_d": 5,
    "pin_hole_depth": 8,
    "pin_out": 6,
    "pin_edge": 50,
    "shelf_clear": 1,
    "cup_d": 35,
    "cup_depth": 12,
    "cup_edge_x": 22.5,
    "cup_edge_z": 100,
    "leg_d": 40,
    "leg_corner_gap": 30,
    "notes": [
        "Sink base cabinet: no top panel (top_mode none). Sides, back and inner wall run up to the carcass top.",
        "Back panel is inset (between the sides, down to the bottom panel, flush with the rear edges).",
        "Width 1200 gives 2 doors (max 600 per door cell) with 1 inner wall at the joint.",
    ],
}


def _solid(shape):
    if isinstance(shape, cq.Solid):
        return shape
    sols = shape.Solids()
    return sols[0] if sols else shape


def _box(x0, x1, y0, y1, z0, z1):
    return cq.Solid.makeBox(x1 - x0, y1 - y0, z1 - z0, cq.Vector(x0, y0, z0))


def _cyl(r, h, p, d):
    return cq.Solid.makeCylinder(r, h, cq.Vector(*p), cq.Vector(*d))


def build(params):
    p = params
    W, H, D = p["W"], p["H"], p["D"]
    leg_h = p["leg_h"]
    t, back_t, dt = p["t"], p["back_t"], p["divider_t"]
    door_t, st, gap = p["door_t"], p["shelf_t"], p["door_gap"]
    dmax = p["door_max_w"]
    top_mode, back_mode = p["top_mode"], p["back_mode"]
    Dc = D - door_t - gap

    # ---------- door count / layout ----------
    n_min = max(1, math.ceil(W / dmax))
    layout = p["door_layout"]
    if layout and sum(layout) >= n_min:
        n = sum(layout)
    else:
        layout = None
        n = n_min
        if p["n_doors"]:
            n = max(n, int(p["n_doors"]))
        layout = [1] * n
    cell = W / n

    # ---------- carcass extents ----------
    has_top = top_mode in ("inset", "onset")
    side_z1 = H - t if top_mode == "onset" else H
    clear_z0 = leg_h + t
    clear_z1 = H - t if has_top else H
    clear_h = clear_z1 - clear_z0
    panel_depth = Dc - back_t if back_mode == "onset" else Dc
    inner_depth = Dc - back_t

    # ---------- bays / walls ----------
    wall_x = []
    cum = 0
    for b in layout[:-1]:
        cum += b
        wall_x.append(cum * cell)
    bay_l = [t] + [c + dt / 2 for c in wall_x]
    bay_r = [c - dt / 2 for c in wall_x] + [W - t]
    n_bays = len(bay_l)

    panels = {}
    panels["side_left"] = _box(0, t, 0, panel_depth, leg_h, side_z1)
    panels["side_right"] = _box(W - t, W, 0, panel_depth, leg_h, side_z1)
    for i, c in enumerate(wall_x):
        panels["divider_%d" % (i + 1)] = _box(c - dt / 2, c + dt / 2, 0, inner_depth, clear_z0, clear_z1)
    left_name = ["side_left"] + ["divider_%d" % (i + 1) for i in range(len(wall_x))]
    right_name = ["divider_%d" % (i + 1) for i in range(len(wall_x))] + ["side_right"]

    parts = {}
    parts["bottom"] = _box(t, W - t, 0, panel_depth, leg_h, leg_h + t)
    if top_mode == "inset":
        parts["top"] = _box(t, W - t, 0, panel_depth, H - t, H)
    elif top_mode == "onset":
        parts["top"] = _box(0, W, 0, panel_depth, H - t, H)
    if back_mode == "onset":
        parts["back"] = _box(0, W, Dc - back_t, Dc, leg_h, H)
    else:
        parts["back"] = _box(t, W - t, Dc - back_t, Dc, clear_z0, clear_z1)

    # ---------- shelf count and heights ----------
    bcm = p["bottom_clear_min"]
    if p["n_shelves"] is not None:
        k = max(0, int(p["n_shelves"]))
    elif bcm:
        k = max(0, math.floor((clear_h - max(bcm, p["shelf_min_gap"])) / (p["shelf_min_gap"] + st)))
    else:
        k = max(0, math.floor((clear_h - p["shelf_min_gap"]) / (p["shelf_min_gap"] + st)))
    shelf_z = []
    if k > 0:
        g = (clear_h - k * st) / (k + 1)
        if bcm and g < bcm:
            g2 = (clear_h - k * st - bcm) / k
            shelf_z = [clear_z0 + bcm + j * (st + g2) for j in range(k)]
        else:
            shelf_z = [clear_z0 + g * (j + 1) + st * j for j in range(k)]

    # ---------- shelves and pins ----------
    sc = p["shelf_clear"]
    pe = p["pin_edge"]
    pr = p["pin_d"] / 2.0
    hd = p["pin_hole_depth"]
    po = p["pin_out"]
    span = inner_depth - 2 * pe
    n_pin = math.ceil(span / p["pin_max_spacing"]) + 1
    pin_ys = [pe + span * i / (n_pin - 1) for i in range(n_pin)]

    shelves = []
    pins = []
    cuts = {}
    for b in range(n_bays):
        xl, xr = bay_l[b], bay_r[b]
        for zb in shelf_z:
            shelves.append(_box(xl + sc, xr - sc, 0, inner_depth, zb, zb + st))
            zc = zb - p["pin_d"] / 2.0
            for y in pin_ys:
                # left panel of bay
                pins.append(_cyl(pr, hd + po, (xl - hd, y, zc), (1, 0, 0)))
                cuts.setdefault(left_name[b], []).append(_cyl(pr, hd, (xl - hd, y, zc), (1, 0, 0)))
                # right panel of bay
                pins.append(_cyl(pr, hd + po, (xr - po, y, zc), (1, 0, 0)))
                cuts.setdefault(right_name[b], []).append(_cyl(pr, hd, (xr, y, zc), (1, 0, 0)))

    for name, cl in cuts.items():
        s = panels[name]
        for c in cl:
            s = _solid(s.cut(c))
        panels[name] = s

    # ---------- doors ----------
    door_w = cell - 2 * gap
    door_h = (H - leg_h) - 2 * gap
    z_bot = leg_h + gap
    if door_h <= 900:
        nh = 2
    elif door_h <= 1600:
        nh = 3
    else:
        nh = 4

    # hinge sides
    hinge = []
    if all(b == 1 for b in layout):
        for i in range(n):
            side = "L" if i % 2 == 0 else "R"
            if n % 2 == 1 and n > 1 and i == n - 1:
                side = "R"
            hinge.append(side)
    else:
        idx = 0
        for b in layout:
            if b == 2:
                hinge += ["L", "R"]
                idx += 2
            else:
                cx = (idx + 0.5) * cell
                hinge.append("L" if cx <= W / 2 else "R")
                idx += 1

    doors = []
    for i in range(n):
        x0 = i * cell + gap
        d = _box(x0, x0 + door_w, -(gap + door_t), -gap, z_bot, z_bot + door_h)
        cx = x0 + p["cup_edge_x"] if hinge[i] == "L" else x0 + door_w - p["cup_edge_x"]
        za = z_bot + p["cup_edge_z"]
        zb_ = z_bot + door_h - p["cup_edge_z"]
        for j in range(nh):
            zc = za + (zb_ - za) * j / (nh - 1)
            d = _solid(d.cut(_cyl(p["cup_d"] / 2.0, p["cup_depth"], (cx, -gap, zc), (0, -1, 0))))
        doors.append(d)

    # ---------- legs ----------
    lr = p["leg_d"] / 2.0
    off = p["leg_corner_gap"] + lr
    sx = W - 2 * off
    sy = Dc - 2 * off
    nx = math.ceil(sx / p["leg_max_spacing"]) + 1
    ny = math.ceil(sy / p["leg_max_spacing"]) + 1
    legs = []
    for ix in range(nx):
        for iy in range(ny):
            x = off + sx * ix / (nx - 1)
            y = off + sy * iy / (ny - 1)
            legs.append(_cyl(lr, leg_h, (x, y, 0), (0, 0, 1)))

    # ---------- collect ----------
    out = []
    out.append(("side_left", panels["side_left"]))
    out.append(("side_right", panels["side_right"]))
    if "top" in parts:
        out.append(("top", parts["top"]))
    out.append(("bottom", parts["bottom"]))
    out.append(("back", parts["back"]))
    for i in range(len(wall_x)):
        out.append(("divider_%d" % (i + 1), panels["divider_%d" % (i + 1)]))
    for i, s in enumerate(shelves):
        out.append(("shelf_%d" % (i + 1), s))
    for i, s in enumerate(pins):
        out.append(("pin_%d" % (i + 1), s))
    for i, s in enumerate(doors):
        out.append(("door_%d" % (i + 1), s))
    for i, s in enumerate(legs):
        out.append(("leg_%d" % (i + 1), s))
    return out
