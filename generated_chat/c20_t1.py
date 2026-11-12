import math
import cadquery as cq

PARAMS = {
    "W": 1800,
    "H": 850,
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
    "door_layout": [2, 1, 1],   # double door, single door, single door (left to right)
    "n_shelves": None,
    "shelf_min_gap": 320,
    "bottom_clear_min": None,
    "pin_max_spacing": 500,
    "leg_max_spacing": 600,
    "notes": [],
    # extra rule values
    "hinge_d": 35,
    "hinge_depth": 12,
    "hinge_edge": 22.5,
    "hinge_end": 100,
    "pin_d": 5,
    "pin_in": 8,
    "pin_out": 6,
    "pin_edge": 50,
    "shelf_clear": 1,
    "leg_d": 40,
    "leg_gap": 30,
}


def _box(x0, x1, y0, y1, z0, z1):
    return cq.Solid.makeBox(x1 - x0, y1 - y0, z1 - z0, cq.Vector(x0, y0, z0))


def _cyl_x(xa, xb, y, z, d):
    return cq.Solid.makeCylinder(d / 2.0, xb - xa, cq.Vector(xa, y, z), cq.Vector(1, 0, 0))


def _cyl_y(ya, yb, x, z, d):
    return cq.Solid.makeCylinder(d / 2.0, yb - ya, cq.Vector(x, ya, z), cq.Vector(0, 1, 0))


def _cut(solid, tools):
    res = solid
    for tl in tools:
        res = res.cut(tl)
    sols = res.Solids()
    return sols[0] if sols else solid


def _linspace(a, b, n):
    if n == 1:
        return [a]
    return [a + (b - a) * i / (n - 1) for i in range(n)]


def build(params):
    p = params
    W, H, D = p["W"], p["H"], p["D"]
    leg_h = p["leg_h"]
    t, back_t, div_t = p["t"], p["back_t"], p["divider_t"]
    door_t, shelf_t, gap = p["door_t"], p["shelf_t"], p["door_gap"]
    door_max_w = p["door_max_w"]
    back_mode, top_mode = p["back_mode"], p["top_mode"]
    Dc = D - door_t - gap

    # ---------- door layout ----------
    layout = p["door_layout"]
    if layout:
        n = int(sum(layout))
        n_min = max(1, math.ceil(W / door_max_w - 1e-9))
        if n < n_min:
            # enforce absolute 600 limit: fall back to every door its own bay
            n = n_min
            layout = None
    if not layout:
        n = max(1, math.ceil(W / door_max_w - 1e-9))
        if p["n_doors"]:
            n = max(n, int(p["n_doors"]))
        layout = [1] * n
    cell = W / n

    # bays: (first cell index, number of cells)
    bays = []
    c = 0
    for b in layout:
        bays.append((c, b))
        c += b

    # hinge sides
    hinge = []
    if all(b == 1 for b in layout):
        for i in range(n):
            hinge.append("L" if i % 2 == 0 else "R")
        if n > 1 and n % 2 == 1:
            hinge[-1] = "R"
    else:
        for (c0, b) in bays:
            if b == 2:
                hinge += ["L", "R"]
            else:
                cx = (c0 + 0.5) * cell
                hinge.append("L" if cx <= W / 2 else "R")

    # ---------- carcass geometry ----------
    z_bot = leg_h
    z_top = H
    has_top = top_mode != "none"
    carc_top_inner = H - t if has_top else H      # top of clear space
    clear_h = carc_top_inner - (leg_h + t)

    if back_mode == "onset":
        side_d = Dc - back_t
    else:
        side_d = Dc
    inner_d = Dc - back_t   # shelf / divider depth

    side_top = H - t if top_mode == "onset" else H

    parts = {}
    holes = {}   # panel name -> list of cutting solids

    side_l = _box(0, t, 0, side_d, z_bot, side_top)
    side_r = _box(W - t, W, 0, side_d, z_bot, side_top)
    holes["side_left"] = []
    holes["side_right"] = []
    panels_solid = {"side_left": side_l, "side_right": side_r}

    bottom = _box(t, W - t, 0, side_d, leg_h, leg_h + t)
    top = None
    if top_mode == "inset":
        top = _box(t, W - t, 0, side_d, H - t, H)
    elif top_mode == "onset":
        top = _box(0, W, 0, side_d, H - t, H)

    if back_mode == "onset":
        back = _box(0, W, Dc - back_t, Dc, leg_h, H)
    else:
        zt = H - t if has_top else H
        back = _box(t, W - t, Dc - back_t, Dc, leg_h + t, zt)

    # dividers
    wall_x = []
    for (c0, b) in bays[1:]:
        wall_x.append(c0 * cell)
    for i, x in enumerate(wall_x):
        name = "divider_%d" % (i + 1)
        panels_solid[name] = _box(x - div_t / 2, x + div_t / 2, 0, inner_d,
                                  leg_h + t, carc_top_inner)
        holes[name] = []

    # panel names left/right of each bay
    nb = len(bays)
    bay_info = []
    for bi, (c0, b) in enumerate(bays):
        if bi == 0:
            xl, lname = t, "side_left"
        else:
            xl, lname = wall_x[bi - 1] + div_t / 2, "divider_%d" % bi
        if bi == nb - 1:
            xr, rname = W - t, "side_right"
        else:
            xr, rname = wall_x[bi] - div_t / 2, "divider_%d" % (bi + 1)
        bay_info.append((xl, xr, lname, rname))

    # ---------- shelves ----------
    min_gap = p["shelf_min_gap"]
    bcm = p["bottom_clear_min"]
    if p["n_shelves"] is not None:
        k = max(0, int(p["n_shelves"]))
    elif bcm:
        k = max(0, math.floor((clear_h - max(bcm, min_gap)) / (min_gap + shelf_t)))
    else:
        k = max(0, math.floor((clear_h - min_gap) / (min_gap + shelf_t)))

    shelf_bottoms = []   # z of shelf underside
    z0 = leg_h + t
    if k > 0:
        g = (clear_h - k * shelf_t) / (k + 1)
        if bcm and p["n_shelves"] is None and g < bcm - 1e-9:
            first = bcm
            if k > 1:
                g2 = (clear_h - bcm - k * shelf_t) / k
            else:
                g2 = 0
            shelf_bottoms.append(z0 + first)
            for i in range(1, k):
                shelf_bottoms.append(z0 + first + shelf_t + i * g2 + (i - 1) * shelf_t)
        else:
            for i in range(k):
                shelf_bottoms.append(z0 + g * (i + 1) + shelf_t * i)

    shelves = []
    pins = []
    pin_d = p["pin_d"]
    pe = p["pin_edge"]
    span = inner_d - 2 * pe
    npin = math.ceil(span / p["pin_max_spacing"] - 1e-9) + 1
    pin_ys = _linspace(pe, inner_d - pe, npin)
    sc = p["shelf_clear"]
    for (xl, xr, lname, rname) in bay_info:
        for zb in shelf_bottoms:
            shelves.append(_box(xl + sc, xr - sc, 0, inner_d, zb, zb + shelf_t))
            pz = zb - pin_d / 2.0
            for y in pin_ys:
                # left panel
                pins.append(_cyl_x(xl - p["pin_in"], xl + p["pin_out"], y, pz, pin_d))
                holes[lname].append(_cyl_x(xl - p["pin_in"], xl, y, pz, pin_d))
                # right panel
                pins.append(_cyl_x(xr - p["pin_out"], xr + p["pin_in"], y, pz, pin_d))
                holes[rname].append(_cyl_x(xr, xr + p["pin_in"], y, pz, pin_d))

    # ---------- doors ----------
    doors = []
    dw = cell - 2 * gap
    dh = (H - leg_h) - 2 * gap
    if dh <= 900:
        nh = 2
    elif dh <= 1600:
        nh = 3
    else:
        nh = 4
    for i in range(n):
        x0 = i * cell + gap
        zb = leg_h + gap
        y0 = -(gap + door_t)
        y1 = -gap
        d = _box(x0, x0 + dw, y0, y1, zb, zb + dh)
        cx = x0 + p["hinge_edge"] if hinge[i] == "L" else x0 + dw - p["hinge_edge"]
        cups = []
        for z in _linspace(zb + p["hinge_end"], zb + dh - p["hinge_end"], nh):
            cups.append(_cyl_y(y1 - p["hinge_depth"], y1, cx, z, p["hinge_d"]))
        doors.append(_cut(d, cups))

    # ---------- legs ----------
    legs = []
    ld = p["leg_d"]
    off = p["leg_gap"] + ld / 2.0
    xs_span = (W - off) - off
    ys_span = (Dc - off) - off
    nx = math.ceil(xs_span / p["leg_max_spacing"] - 1e-9) + 1
    ny = math.ceil(ys_span / p["leg_max_spacing"] - 1e-9) + 1
    for yy in _linspace(off, Dc - off, ny):
        for xx in _linspace(off, W - off, nx):
            legs.append(cq.Solid.makeCylinder(ld / 2.0, leg_h, cq.Vector(xx, yy, 0), cq.Vector(0, 0, 1)))

    # ---------- assemble ----------
    out = []
    for name in ["side_left", "side_right"]:
        out.append((name, _cut(panels_solid[name], holes[name])))
    if top is not None:
        out.append(("top", top))
    out.append(("bottom", bottom))
    out.append(("back", back))
    for i in range(len(wall_x)):
        name = "divider_%d" % (i + 1)
        out.append((name, _cut(panels_solid[name], holes[name])))
    for i, s in enumerate(shelves):
        out.append(("shelf_%d" % (i + 1), s))
    for i, s in enumerate(pins):
        out.append(("pin_%d" % (i + 1), s))
    for i, s in enumerate(doors):
        out.append(("door_%d" % (i + 1), s))
    for i, s in enumerate(legs):
        out.append(("leg_%d" % (i + 1), s))
    return out
