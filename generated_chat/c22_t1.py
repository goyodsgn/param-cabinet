import math
import cadquery as cq

PARAMS = {
    "W": 1200,
    "H": 850,
    "D": 600,
    "leg_h": 100,
    "back_mode": "onset",
    "top_mode": "onset",   # customer: top panel covers the sides
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
    "notes": [],
    # extra values
    "pin_d": 5,
    "pin_len": 14,
    "pin_hole_depth": 8,
    "pin_edge": 50,
    "leg_d": 40,
    "leg_edge_gap": 30,
    "cup_d": 35,
    "cup_depth": 12,
    "cup_edge": 22.5,
    "cup_end": 100,
    "shelf_clear": 1,
}


def _box(x0, x1, y0, y1, z0, z1):
    return cq.Solid.makeBox(x1 - x0, y1 - y0, z1 - z0, cq.Vector(x0, y0, z0))


def _cyl(d, length, x, y, z, direction):
    return cq.Solid.makeCylinder(d / 2.0, length, cq.Vector(x, y, z), cq.Vector(*direction))


def _cut(solid, tools):
    shape = solid
    for tool in tools:
        shape = shape.cut(tool)
    sols = shape.Solids()
    return sols[0] if sols else solid


def build(params):
    p = params
    W, H, D = p["W"], p["H"], p["D"]
    leg_h = p["leg_h"]
    t, back_t, div_t = p["t"], p["back_t"], p["divider_t"]
    door_t, shelf_t, gap = p["door_t"], p["shelf_t"], p["door_gap"]
    back_mode, top_mode = p["back_mode"], p["top_mode"]
    Dc = D - door_t - gap

    parts = []

    # ---------- carcass extents ----------
    has_top = top_mode != "none"
    z_bot = leg_h
    z_in_bot = leg_h + t                       # top face of bottom panel
    z_in_top = (H - t) if has_top else H       # underside of top panel / carcass top
    clear_h = z_in_top - z_in_bot
    side_z1 = (H - t) if top_mode == "onset" else H
    panel_depth = (Dc - back_t) if back_mode == "onset" else Dc
    y_inner = Dc - back_t                      # back panel inner face

    # ---------- doors / bays ----------
    layout = p["door_layout"]
    need = max(1, math.ceil(W / p["door_max_w"]))
    if layout:
        layout = list(layout)
        while sum(layout) < need:
            layout.append(1)
    else:
        n_req = p["n_doors"] if p["n_doors"] else need
        n_req = max(n_req, need)
        layout = [1] * n_req
    n = sum(layout)
    cell = W / n
    all_single = all(b == 1 for b in layout)

    # door list: (index, hinge side)
    hinges = []
    if all_single:
        for i in range(n):
            hinges.append("left" if i % 2 == 0 else "right")
        if n > 1 and n % 2 == 1:
            hinges[-1] = "right"
    else:
        cells_left = 0
        for b in layout:
            if b == 2:
                hinges.extend(["left", "right"])
            else:
                cx = (cells_left + 0.5) * cell
                hinges.append("left" if cx <= W / 2 else "right")
            cells_left += b

    # inner wall centers between bays
    wall_xs = []
    acc = 0
    for b in layout[:-1]:
        acc += b
        wall_xs.append(acc * cell)

    # ---------- vertical panels (list of (name, x0, x1)) ----------
    panels = [("side_left", 0.0, t)]
    for j, xc in enumerate(wall_xs):
        panels.append(("divider_%d" % (j + 1), xc - div_t / 2.0, xc + div_t / 2.0))
    panels.append(("side_right", W - t, float(W)))

    # bays
    bays = []
    for b in range(len(panels) - 1):
        bays.append((panels[b][2], panels[b + 1][1]))

    # ---------- shelves ----------
    st = shelf_t
    bcm = p["bottom_clear_min"]
    min_gap = p["shelf_min_gap"]
    if p["n_shelves"] is not None:
        k = max(0, int(p["n_shelves"]))
    elif bcm is not None:
        k = max(0, math.floor((clear_h - max(bcm, min_gap)) / (min_gap + st)))
    else:
        k = max(0, math.floor((clear_h - min_gap) / (min_gap + st)))

    shelf_bottoms = []  # z of shelf bottom faces
    if k > 0:
        g = (clear_h - k * st) / (k + 1)
        if bcm is not None and g < bcm:
            g1 = bcm
            g2 = (clear_h - bcm - k * st) / k
            z = z_in_bot + g1
            for i in range(k):
                shelf_bottoms.append(z)
                z += st + g2
        else:
            for i in range(k):
                shelf_bottoms.append(z_in_bot + g * (i + 1) + st * i)

    # pins per side
    shelf_depth = y_inner
    pe = p["pin_edge"]
    span = shelf_depth - 2 * pe
    n_pins = math.ceil(span / p["pin_max_spacing"]) + 1
    pin_ys = [pe + span * i / (n_pins - 1) for i in range(n_pins)]
    pin_d, pin_len, hole_d = p["pin_d"], p["pin_len"], p["pin_hole_depth"]
    pin_out = pin_len - hole_d

    holes = {name: [] for name, _, _ in panels}
    pins = []
    shelves = []
    sc = p["shelf_clear"]
    for b, (x0, x1) in enumerate(bays):
        lname = panels[b][0]
        rname = panels[b + 1][0]
        for zb in shelf_bottoms:
            shelves.append(_box(x0 + sc, x1 - sc, 0, shelf_depth, zb, zb + st))
            pz = zb - pin_d / 2.0
            for y in pin_ys:
                # left pin: sunk 8 into left panel, sticks 6 out
                pins.append(_cyl(pin_d, pin_len, x0 - hole_d, y, pz, (1, 0, 0)))
                holes[lname].append(_cyl(pin_d, hole_d, x0 - hole_d, y, pz, (1, 0, 0)))
                # right pin
                pins.append(_cyl(pin_d, pin_len, x1 - pin_out, y, pz, (1, 0, 0)))
                holes[rname].append(_cyl(pin_d, hole_d, x1, y, pz, (1, 0, 0)))

    # ---------- build panels ----------
    for name, x0, x1 in panels:
        if name.startswith("side"):
            solid = _box(x0, x1, 0, panel_depth, z_bot, side_z1)
        else:
            solid = _box(x0, x1, 0, y_inner, z_in_bot, z_in_top)
        if holes[name]:
            solid = _cut(solid, holes[name])
        parts.append((name, solid))

    # top
    if top_mode == "onset":
        parts.append(("top", _box(0, W, 0, panel_depth, H - t, H)))
    elif top_mode == "inset":
        parts.append(("top", _box(t, W - t, 0, panel_depth, H - t, H)))

    # bottom
    parts.append(("bottom", _box(t, W - t, 0, panel_depth, z_bot, z_in_bot)))

    # back
    if back_mode == "onset":
        parts.append(("back", _box(0, W, Dc - back_t, Dc, z_bot, H)))
    else:
        parts.append(("back", _box(t, W - t, Dc - back_t, Dc, z_in_bot, z_in_top)))

    # dividers already added in panels loop (names divider_j)

    # shelves
    for i, s in enumerate(shelves):
        parts.append(("shelf_%d" % (i + 1), s))

    # pins
    for i, s in enumerate(pins):
        parts.append(("pin_%d" % (i + 1), s))

    # ---------- doors ----------
    door_w = cell - 2 * gap
    door_h = (H - leg_h) - 2 * gap
    if door_h <= 900:
        n_cups = 2
    elif door_h <= 1600:
        n_cups = 3
    else:
        n_cups = 4
    cup_end = p["cup_end"]
    cup_d, cup_depth, cup_edge = p["cup_d"], p["cup_depth"], p["cup_edge"]
    dz0 = leg_h + gap
    for i in range(n):
        dx0 = i * cell + gap
        door = _box(dx0, dx0 + door_w, -(gap + door_t), -gap, dz0, dz0 + door_h)
        cx = dx0 + cup_edge if hinges[i] == "left" else dx0 + door_w - cup_edge
        cups = []
        for c in range(n_cups):
            zc = dz0 + cup_end + (door_h - 2 * cup_end) * c / (n_cups - 1)
            cups.append(_cyl(cup_d, cup_depth + 1, cx, -gap - cup_depth, zc, (0, 1, 0)))
        door = _cut(door, cups)
        parts.append(("door_%d" % (i + 1), door))

    # ---------- legs ----------
    ld = p["leg_d"]
    off = p["leg_edge_gap"] + ld / 2.0
    lmax = p["leg_max_spacing"]
    span_x = W - 2 * off
    span_y = Dc - 2 * off
    nx = math.ceil(span_x / lmax) + 1
    ny = math.ceil(span_y / lmax) + 1
    xs = [off + span_x * i / (nx - 1) for i in range(nx)]
    ys = [off + span_y * j / (ny - 1) for j in range(ny)]
    idx = 1
    for y in ys:
        for x in xs:
            parts.append(("leg_%d" % idx, _cyl(ld, leg_h, x, y, 0, (0, 0, 1))))
            idx += 1

    return parts
