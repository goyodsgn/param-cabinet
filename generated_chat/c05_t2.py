import math
import cadquery as cq

PARAMS = {
    "W": 1800,
    "H": 850,
    "D": 600,
    "leg_h": 100,
    "back_mode": "onset",
    "top_mode": "onset",
    "t": 18,
    "back_t": 10,
    "divider_t": 18,
    "door_t": 22,
    "shelf_t": 30,
    "door_gap": 2,
    "door_max_w": 600,
    "n_doors": 4,
    "door_layout": [2, 2],
    "n_shelves": None,
    "shelf_min_gap": 320,
    "bottom_clear_min": None,
    "pin_max_spacing": 500,
    "leg_max_spacing": 600,
    "notes": [
        "Four doors as two double-door (pair) bays: door_layout = [2, 2], each door cell is 1800/4 = 450 mm wide (under the 600 mm limit).",
        "One inner wall at x = 900 between the two double-door bays; no wall behind the joint of each pair.",
        "Hinges: door 1 left, door 2 right, door 3 left, door 4 right (each pair opens left-right).",
        "top_mode = onset: the top panel is W wide (1800) and covers the top of the side panels; the sides run from leg_h to H - t.",
    ],
}


def _box(x0, x1, y0, y1, z0, z1):
    return cq.Solid.makeBox(x1 - x0, y1 - y0, z1 - z0, cq.Vector(x0, y0, z0))


def _cyl_x(x_start, length, y, z, r):
    return cq.Solid.makeCylinder(r, length, cq.Vector(x_start, y, z), cq.Vector(1, 0, 0))


def _first_solid(shape):
    sols = shape.Solids()
    return sols[0] if sols else shape


def build(params):
    p = params
    W, H, D = p["W"], p["H"], p["D"]
    leg_h = p["leg_h"]
    t, back_t, div_t = p["t"], p["back_t"], p["divider_t"]
    door_t, shelf_t, gap = p["door_t"], p["shelf_t"], p["door_gap"]
    door_max_w = p["door_max_w"]
    top_mode, back_mode = p["top_mode"], p["back_mode"]

    Dc = D - door_t - gap
    inner_d = Dc - back_t                      # depth to back panel inner face
    cd = inner_d if back_mode == "onset" else Dc  # depth of sides/top/bottom
    has_top = top_mode != "none"

    # ---------- doors / bays ----------
    layout = p["door_layout"]
    if layout:
        n = sum(layout)
    else:
        n = max(1, math.ceil(W / door_max_w))
        if p["n_doors"]:
            n = max(n, p["n_doors"])
        layout = [1] * n
    cell = W / n
    if cell > door_max_w + 1e-9:
        raise ValueError("door cell wider than door_max_w")

    # hinge sides
    all_single = all(b == 1 for b in layout)
    hinge = []
    if all_single:
        for i in range(n):
            hinge.append("L" if i % 2 == 0 else "R")
        if n > 1 and n % 2 == 1:
            hinge[-1] = "R"
    else:
        c = 0
        for b in layout:
            if b == 2:
                hinge += ["L", "R"]
            else:
                center = (c + 0.5) * cell
                hinge.append("L" if center <= W / 2 else "R")
            c += b

    # bays
    bays = []  # (cell_start, cell_end)
    c = 0
    for b in layout:
        bays.append((c, c + b))
        c += b
    nb = len(bays)

    # vertical heights
    z_bot_in = leg_h + t
    z_top_in = (H - t) if has_top else H
    clear_h = z_top_in - z_bot_in

    # interior x-range for each bay
    bay_ranges = []
    for i, (s, e) in enumerate(bays):
        bl = t if i == 0 else s * cell + div_t / 2
        br = (W - t) if i == nb - 1 else e * cell - div_t / 2
        bay_ranges.append((bl, br))
    divider_x = [bays[i][1] * cell for i in range(nb - 1)]

    # ---------- shelf count / positions ----------
    bcm = p["bottom_clear_min"]
    if p["n_shelves"] is not None:
        k = p["n_shelves"]
    elif bcm is not None:
        k = max(0, math.floor((clear_h - max(bcm, p["shelf_min_gap"])) / (p["shelf_min_gap"] + shelf_t)))
    else:
        k = max(0, math.floor((clear_h - p["shelf_min_gap"]) / (p["shelf_min_gap"] + shelf_t)))
    g_even = (clear_h - k * shelf_t) / (k + 1)
    g0, g = g_even, g_even
    if bcm is not None and k > 0 and g_even < bcm:
        g0 = bcm
        g = (clear_h - k * shelf_t - bcm) / k
    shelf_z = [z_bot_in + g0 + i * (shelf_t + g) for i in range(k)]

    # ---------- pins ----------
    span = inner_d - 2 * 50
    n_pins = math.ceil(span / p["pin_max_spacing"]) + 1
    pin_ys = [50 + i * span / (n_pins - 1) for i in range(n_pins)]
    pin_r = 2.5

    holes = {"side_left": [], "side_right": []}
    for i in range(nb - 1):
        holes["divider_%d" % (i + 1)] = []

    pins = []
    shelves = []
    for bi, (bl, br) in enumerate(bay_ranges):
        for zb in shelf_z:
            shelves.append(_box(bl + 1, br - 1, 0, inner_d, zb, zb + shelf_t))
            zc = zb - pin_r
            left_panel = "side_left" if bi == 0 else "divider_%d" % bi
            right_panel = "side_right" if bi == nb - 1 else "divider_%d" % (bi + 1)
            for y in pin_ys:
                # left pin: 8 in panel, 6 out into the bay
                pins.append(_cyl_x(bl - 8, 14, y, zc, pin_r))
                holes[left_panel].append(_cyl_x(bl - 8, 8, y, zc, pin_r))
                # right pin
                pins.append(_cyl_x(br - 6, 14, y, zc, pin_r))
                holes[right_panel].append(_cyl_x(br, 8, y, zc, pin_r))

    def drill(name, solid):
        for h in holes.get(name, []):
            solid = solid.cut(h)
        return _first_solid(solid)

    parts = []

    # ---------- carcass ----------
    side_top = (H - t) if top_mode == "onset" else H
    parts.append(("side_left", drill("side_left", _box(0, t, 0, cd, leg_h, side_top))))
    parts.append(("side_right", drill("side_right", _box(W - t, W, 0, cd, leg_h, side_top))))
    parts.append(("bottom", _box(t, W - t, 0, cd, leg_h, leg_h + t)))
    if top_mode == "inset":
        parts.append(("top", _box(t, W - t, 0, cd, H - t, H)))
    elif top_mode == "onset":
        parts.append(("top", _box(0, W, 0, cd, H - t, H)))

    if back_mode == "onset":
        parts.append(("back", _box(0, W, Dc - back_t, Dc, leg_h, H)))
    else:
        parts.append(("back", _box(t, W - t, Dc - back_t, Dc, z_bot_in, z_top_in)))

    # ---------- dividers ----------
    for i, x in enumerate(divider_x):
        name = "divider_%d" % (i + 1)
        d = _box(x - div_t / 2, x + div_t / 2, 0, inner_d, z_bot_in, z_top_in)
        parts.append((name, drill(name, d)))

    # ---------- shelves ----------
    for i, s in enumerate(shelves):
        parts.append(("shelf_%d" % (i + 1), s))

    # ---------- pins ----------
    for i, pn in enumerate(pins):
        parts.append(("pin_%d" % (i + 1), pn))

    # ---------- doors ----------
    dw = cell - 2 * gap
    dh = (H - leg_h) - 2 * gap
    if dh <= 900:
        nh = 2
    elif dh <= 1600:
        nh = 3
    else:
        nh = 4
    cup_zs = [100 + j * (dh - 200) / (nh - 1) for j in range(nh)]
    for i in range(n):
        x0 = i * cell + gap
        z0 = leg_h + gap
        door = _box(x0, x0 + dw, -(gap + door_t), -gap, z0, z0 + dh)
        cx = x0 + 22.5 if hinge[i] == "L" else x0 + dw - 22.5
        for cz in cup_zs:
            cup = cq.Solid.makeCylinder(17.5, 12, cq.Vector(cx, -gap, z0 + cz), cq.Vector(0, -1, 0))
            door = door.cut(cup)
        parts.append(("door_%d" % (i + 1), _first_solid(door)))

    # ---------- legs ----------
    leg_r = 20
    x_a, x_b = 30 + leg_r, W - 30 - leg_r
    y_a, y_b = 30 + leg_r, Dc - 30 - leg_r
    nx = math.ceil((x_b - x_a) / p["leg_max_spacing"]) + 1
    ny = math.ceil((y_b - y_a) / p["leg_max_spacing"]) + 1
    idx = 1
    for ix in range(nx):
        x = x_a + ix * (x_b - x_a) / (nx - 1)
        for iy in range(ny):
            y = y_a + iy * (y_b - y_a) / (ny - 1)
            leg = cq.Solid.makeCylinder(leg_r, leg_h, cq.Vector(x, y, 0), cq.Vector(0, 0, 1))
            parts.append(("leg_%d" % idx, leg))
            idx += 1

    return parts
