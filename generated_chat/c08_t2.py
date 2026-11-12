import math
import cadquery as cq

PARAMS = {
    "W": 1500,
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
    "door_layout": [1, 2],   # single door on the left, double door on the right
    "n_shelves": None,
    "shelf_min_gap": 320,
    "bottom_clear_min": None,
    "pin_max_spacing": 500,
    "leg_max_spacing": 600,
    # extra values
    "leg_d": 40,
    "leg_edge_gap": 30,
    "cup_d": 35,
    "cup_depth": 12,
    "cup_edge": 22.5,
    "cup_end": 100,
    "pin_d": 5,
    "pin_len": 14,
    "pin_in": 8,
    "pin_out": 6,
    "pin_edge": 50,
    "shelf_clear": 1,
    "notes": [],
}


def _box(x0, x1, y0, y1, z0, z1):
    return cq.Solid.makeBox(x1 - x0, y1 - y0, z1 - z0, cq.Vector(x0, y0, z0))


def _first_solid(shape):
    sols = shape.Solids()
    return sols[0] if sols else shape


def build(params):
    p = params
    W, H, D = p["W"], p["H"], p["D"]
    leg_h = p["leg_h"]
    t, back_t, dt = p["t"], p["back_t"], p["divider_t"]
    door_t, shelf_t, gap = p["door_t"], p["shelf_t"], p["door_gap"]
    door_max_w = p["door_max_w"]
    top_mode, back_mode = p["top_mode"], p["back_mode"]
    has_top = top_mode != "none"

    Dc = D - door_t - gap
    carcass_depth = Dc - back_t if back_mode == "onset" else Dc   # depth of sides/top/bottom
    inner_depth = Dc - back_t                                      # shelves, walls

    # ---------------- doors / bays ----------------
    layout = p.get("door_layout")
    if layout:
        layout = list(layout)
        while W / sum(layout) > door_max_w:
            layout.append(1)
        n = sum(layout)
    else:
        n = max(1, math.ceil(W / door_max_w))
        if p.get("n_doors"):
            n = max(n, int(p["n_doors"]))
        layout = [1] * n
    cell = W / n

    bays = []  # (start_cell, count)
    s = 0
    for c in layout:
        bays.append((s, c))
        s += c

    # hinge sides
    all_single = all(c == 1 for c in layout)
    hinges = []
    if all_single:
        for i in range(n):
            hinges.append("L" if i % 2 == 0 else "R")
        if n > 1 and n % 2 == 1:
            hinges[-1] = "R"
    else:
        for (st, c) in bays:
            if c == 2:
                hinges += ["L", "R"]
            else:
                cx = (st + 0.5) * cell
                hinges.append("L" if cx <= W / 2 else "R")

    # ---------------- carcass extents ----------------
    z_floor = leg_h
    z_in_bot = leg_h + t
    z_in_top = H - t if has_top else H
    clear_h = z_in_top - z_in_bot

    # sides
    side_z1 = H - t if top_mode == "onset" else H
    side_L = _box(0, t, 0, carcass_depth, z_floor, side_z1)
    side_R = _box(W - t, W, 0, carcass_depth, z_floor, side_z1)

    # dividers
    wall_x = [bays[j][0] * cell for j in range(1, len(bays))]
    dividers = [_box(xc - dt / 2, xc + dt / 2, 0, inner_depth, z_in_bot, z_in_top)
                for xc in wall_x]

    # bottom / top
    bottom = _box(t, W - t, 0, carcass_depth, z_floor, z_floor + t)
    top = None
    if top_mode == "inset":
        top = _box(t, W - t, 0, carcass_depth, H - t, H)
    elif top_mode == "onset":
        top = _box(0, W, 0, carcass_depth, H - t, H)

    # back
    if back_mode == "onset":
        back = _box(0, W, Dc - back_t, Dc, z_floor, H)
    else:
        back = _box(t, W - t, Dc - back_t, Dc, z_in_bot, z_in_top)

    # ---------------- shelves and pins ----------------
    shelf_min_gap = p["shelf_min_gap"]
    bcm = p.get("bottom_clear_min")
    if p.get("n_shelves") is not None:
        k = max(0, int(p["n_shelves"]))
    elif bcm:
        k = max(0, math.floor((clear_h - max(bcm, shelf_min_gap)) / (shelf_min_gap + shelf_t)))
    else:
        k = max(0, math.floor((clear_h - shelf_min_gap) / (shelf_min_gap + shelf_t)))

    shelf_bottoms = []
    if k > 0:
        even_gap = (clear_h - k * shelf_t) / (k + 1)
        if bcm and even_gap < bcm:
            g2 = (clear_h - bcm - k * shelf_t) / k
            for i in range(k):
                shelf_bottoms.append(z_in_bot + bcm + i * (shelf_t + g2))
        else:
            for i in range(k):
                shelf_bottoms.append(z_in_bot + even_gap * (i + 1) + i * shelf_t)

    pin_r = p["pin_d"] / 2.0
    pin_len, pin_in = p["pin_len"], p["pin_in"]
    pin_edge = p["pin_edge"]
    span = inner_depth - 2 * pin_edge
    m_pins = math.ceil(span / p["pin_max_spacing"]) + 1
    pin_ys = [pin_edge + i * span / (m_pins - 1) for i in range(m_pins)] if m_pins > 1 else [pin_edge]

    shelves = []
    pins = []
    holes = {}  # panel key -> list of cylinders
    nb = len(bays)
    for bi, (st, c) in enumerate(bays):
        if bi == 0:
            xl = t
            lkey = "side_left"
        else:
            xl = st * cell + dt / 2
            lkey = ("div", bi - 1)
        if bi == nb - 1:
            xr = W - t
            rkey = "side_right"
        else:
            xr = (st + c) * cell - dt / 2
            rkey = ("div", bi)
        sc = p["shelf_clear"]
        for zb in shelf_bottoms:
            shelves.append(_box(xl + sc, xr - sc, 0, inner_depth, zb, zb + shelf_t))
            zc = zb - pin_r
            for y in pin_ys:
                # left panel pin: 8 into panel, 6 out into bay
                pins.append(cq.Solid.makeCylinder(pin_r, pin_len, cq.Vector(xl - pin_in, y, zc),
                                                  cq.Vector(1, 0, 0)))
                holes.setdefault(lkey, []).append(
                    cq.Solid.makeCylinder(pin_r, pin_in, cq.Vector(xl - pin_in, y, zc),
                                          cq.Vector(1, 0, 0)))
                # right panel pin
                pins.append(cq.Solid.makeCylinder(pin_r, pin_len, cq.Vector(xr + pin_in, y, zc),
                                                  cq.Vector(-1, 0, 0)))
                holes.setdefault(rkey, []).append(
                    cq.Solid.makeCylinder(pin_r, pin_in, cq.Vector(xr, y, zc),
                                          cq.Vector(1, 0, 0)))

    def drill(solid, key):
        for h in holes.get(key, []):
            solid = _first_solid(solid.cut(h))
        return solid

    side_L = drill(side_L, "side_left")
    side_R = drill(side_R, "side_right")
    dividers = [drill(d, ("div", i)) for i, d in enumerate(dividers)]

    # ---------------- doors ----------------
    door_w = cell - 2 * gap
    door_h = (H - leg_h) - 2 * gap
    if door_h <= 900:
        n_h = 2
    elif door_h <= 1600:
        n_h = 3
    else:
        n_h = 4
    z0d = leg_h + gap
    cup_r = p["cup_d"] / 2.0
    cz_first = z0d + p["cup_end"]
    cz_last = z0d + door_h - p["cup_end"]
    cup_zs = [cz_first + i * (cz_last - cz_first) / (n_h - 1) for i in range(n_h)]

    doors = []
    for i in range(n):
        x0 = i * cell + gap
        d = _box(x0, x0 + door_w, -(gap + door_t), -gap, z0d, z0d + door_h)
        cx = x0 + p["cup_edge"] if hinges[i] == "L" else x0 + door_w - p["cup_edge"]
        for cz in cup_zs:
            cup = cq.Solid.makeCylinder(cup_r, p["cup_depth"] + 1.0,
                                        cq.Vector(cx, -gap + 1.0, cz), cq.Vector(0, -1, 0))
            d = _first_solid(d.cut(cup))
        doors.append(d)

    # ---------------- legs ----------------
    leg_r = p["leg_d"] / 2.0
    off = p["leg_edge_gap"] + leg_r
    x_a, x_b = off, W - off
    y_a, y_b = off, Dc - off
    nx = math.ceil((x_b - x_a) / p["leg_max_spacing"]) + 1
    ny = math.ceil((y_b - y_a) / p["leg_max_spacing"]) + 1
    xs = [x_a + i * (x_b - x_a) / (nx - 1) for i in range(nx)]
    ys = [y_a + j * (y_b - y_a) / (ny - 1) for j in range(ny)]
    legs = []
    for x in xs:
        for y in ys:
            legs.append(cq.Solid.makeCylinder(leg_r, leg_h, cq.Vector(x, y, 0), cq.Vector(0, 0, 1)))

    # ---------------- assemble ----------------
    out = [("side_left", side_L), ("side_right", side_R)]
    if top is not None:
        out.append(("top", top))
    out.append(("bottom", bottom))
    out.append(("back", back))
    for i, d in enumerate(dividers, 1):
        out.append((f"divider_{i}", d))
    for i, s_ in enumerate(shelves, 1):
        out.append((f"shelf_{i}", s_))
    for i, pn in enumerate(pins, 1):
        out.append((f"pin_{i}", pn))
    for i, d in enumerate(doors, 1):
        out.append((f"door_{i}", d))
    for i, l in enumerate(legs, 1):
        out.append((f"leg_{i}", l))
    return out
