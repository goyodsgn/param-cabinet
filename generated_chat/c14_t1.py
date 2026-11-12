import math
import cadquery as cq

PARAMS = {
    "W": 1600,
    "H": 900,
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
    # Encyclopedia volumes are about 300 mm tall; 350 mm gives room to slide them in.
    "bottom_clear_min": 350,
    "pin_max_spacing": 500,
    "leg_max_spacing": 600,
    # extra rule values
    "shelf_clear": 1,
    "pin_edge": 50,
    "pin_d": 5,
    "pin_hole_depth": 8,
    "pin_out": 6,
    "hinge_d": 35,
    "hinge_depth": 12,
    "hinge_edge": 22.5,
    "hinge_end": 100,
    "leg_d": 40,
    "leg_gap": 30,
    "notes": [
        "Bottom space sized for encyclopedia volumes (about 300 mm tall) plus clearance: bottom_clear_min = 350 mm.",
        "W = 1600 needs ceil(1600/600) = 3 doors (each cell 533.3 mm wide), with 2 inner walls between them.",
        "Shelf count, pins, hinge cups and legs are computed from the parameters.",
    ],
}


def _box(x0, x1, y0, y1, z0, z1):
    return cq.Solid.makeBox(x1 - x0, y1 - y0, z1 - z0, cq.Vector(x0, y0, z0))


def _to_solid(shape):
    sols = shape.Solids()
    if len(sols) == 1:
        return sols[0]
    return shape


def _cut_all(solid, cutters):
    if not cutters:
        return solid
    comp = cq.Compound.makeCompound(cutters)
    return _to_solid(solid.cut(comp))


def build(params):
    p = params
    W, H, D = p["W"], p["H"], p["D"]
    leg_h = p["leg_h"]
    t, back_t, div_t = p["t"], p["back_t"], p["divider_t"]
    door_t, shelf_t, g = p["door_t"], p["shelf_t"], p["door_gap"]
    door_max_w = p["door_max_w"]
    back_mode, top_mode = p["back_mode"], p["top_mode"]
    Dc = D - door_t - g

    parts = []

    # ---------- carcass ----------
    has_top = top_mode != "none"
    side_depth = Dc - back_t if back_mode == "onset" else Dc
    side_z0 = leg_h
    if top_mode == "onset":
        side_z1 = H - t
    else:
        side_z1 = H
    carcass_top = H
    bottom_top = leg_h + t
    if has_top:
        clear_h = H - leg_h - 2 * t
    else:
        clear_h = H - leg_h - t
    panel_z0 = leg_h + t
    panel_z1 = panel_z0 + clear_h
    inner_depth = Dc - back_t  # depth of dividers/shelves

    # holes to be cut from vertical panels
    holes = {}

    # ---------- doors / bays ----------
    n_req = max(1, math.ceil(W / door_max_w))
    layout = p.get("door_layout")
    if layout:
        n_l = sum(layout)
        if n_l < n_req or any(b not in (1, 2) for b in layout):
            layout = None
    if layout:
        bays = list(layout)
        n = sum(bays)
    else:
        n = n_req
        if p.get("n_doors"):
            n = max(n, int(p["n_doors"]))
        bays = [1] * n
    cell = W / n

    # bay boundaries (in door cells)
    bounds = []
    acc = 0
    for b in bays[:-1]:
        acc += b
        bounds.append(acc)
    div_x = [j * cell for j in bounds]

    # bay interior x ranges
    bay_ranges = []
    for bi in range(len(bays)):
        x0 = t if bi == 0 else div_x[bi - 1] + div_t / 2
        x1 = W - t if bi == len(bays) - 1 else div_x[bi] - div_t / 2
        bay_ranges.append((x0, x1))

    # ---------- panels ----------
    holes["side_left"] = []
    holes["side_right"] = []
    for i in range(len(div_x)):
        holes["divider_%d" % (i + 1)] = []

    sides = {
        "side_left": _box(0, t, 0, side_depth, side_z0, side_z1),
        "side_right": _box(W - t, W, 0, side_depth, side_z0, side_z1),
    }

    if top_mode == "onset":
        top = _box(0, W, 0, side_depth, H - t, H)
    elif top_mode == "inset":
        top = _box(t, W - t, 0, side_depth, H - t, H)
    else:
        top = None
    bottom = _box(t, W - t, 0, side_depth, leg_h, leg_h + t)

    if back_mode == "onset":
        back = _box(0, W, Dc - back_t, Dc, leg_h, H)
    else:
        bz1 = H - t if has_top else H
        back = _box(t, W - t, Dc - back_t, Dc, leg_h + t, bz1)

    dividers = []
    for i, xc in enumerate(div_x):
        dividers.append(("divider_%d" % (i + 1),
                         _box(xc - div_t / 2, xc + div_t / 2, 0, inner_depth, panel_z0, panel_z1)))

    # ---------- shelves ----------
    min_gap = p["shelf_min_gap"]
    bcm = p.get("bottom_clear_min")
    if p.get("n_shelves") is None:
        base = max(bcm, min_gap) if bcm is not None else min_gap
        k = max(0, int(math.floor((clear_h - base) / (min_gap + shelf_t))))
    else:
        k = max(0, int(p["n_shelves"]))
    shelf_z = []  # bottom z of each shelf
    if k > 0:
        s = (clear_h - k * shelf_t) / (k + 1)
        lowest = s
        rest = s
        if p.get("n_shelves") is None and bcm is not None and s < bcm:
            lowest = bcm
            rest = (clear_h - bcm - k * shelf_t) / k
        z = panel_z0 + lowest
        for i in range(k):
            shelf_z.append(z)
            z += shelf_t + rest

    sc = p["shelf_clear"]
    pin_d = p["pin_d"]
    pin_r = pin_d / 2.0
    hole_depth = p["pin_hole_depth"]
    pin_out = p["pin_out"]
    pin_len = hole_depth + pin_out
    edge = p["pin_edge"]
    span = inner_depth - 2 * edge
    n_pin = int(math.ceil(span / p["pin_max_spacing"])) + 1
    pin_ys = [edge + i * span / (n_pin - 1) for i in range(n_pin)]

    shelves = []
    pins = []
    for bi, (x0, x1) in enumerate(bay_ranges):
        left_name = "side_left" if bi == 0 else "divider_%d" % bi
        right_name = "side_right" if bi == len(bays) - 1 else "divider_%d" % (bi + 1)
        for zb in shelf_z:
            shelves.append(_box(x0 + sc, x1 - sc, 0, inner_depth, zb, zb + shelf_t))
            zc = zb - pin_d / 2.0
            for y in pin_ys:
                # left pin: from x0 - hole_depth to x0 + pin_out
                pins.append(cq.Solid.makeCylinder(pin_r, pin_len,
                                                  cq.Vector(x0 - hole_depth, y, zc),
                                                  cq.Vector(1, 0, 0)))
                holes[left_name].append(cq.Solid.makeCylinder(pin_r, hole_depth,
                                                              cq.Vector(x0 - hole_depth, y, zc),
                                                              cq.Vector(1, 0, 0)))
                # right pin: from x1 - pin_out to x1 + hole_depth
                pins.append(cq.Solid.makeCylinder(pin_r, pin_len,
                                                  cq.Vector(x1 - pin_out, y, zc),
                                                  cq.Vector(1, 0, 0)))
                holes[right_name].append(cq.Solid.makeCylinder(pin_r, hole_depth,
                                                               cq.Vector(x1, y, zc),
                                                               cq.Vector(1, 0, 0)))

    # ---------- assemble carcass parts ----------
    parts.append(("side_left", _cut_all(sides["side_left"], holes["side_left"])))
    parts.append(("side_right", _cut_all(sides["side_right"], holes["side_right"])))
    if top is not None:
        parts.append(("top", top))
    parts.append(("bottom", bottom))
    parts.append(("back", back))
    for name, sol in dividers:
        parts.append((name, _cut_all(sol, holes[name])))
    for i, sh in enumerate(shelves):
        parts.append(("shelf_%d" % (i + 1), sh))
    for i, pn in enumerate(pins):
        parts.append(("pin_%d" % (i + 1), pn))

    # ---------- doors ----------
    dw = cell - 2 * g
    dh = (H - leg_h) - 2 * g
    all_single = all(b == 1 for b in bays)
    hinge_sides = [None] * n
    if all_single:
        for i in range(n):
            hinge_sides[i] = "L" if i % 2 == 0 else "R"
        if n > 1 and n % 2 == 1:
            hinge_sides[n - 1] = "R"
    else:
        idx = 0
        for b in bays:
            if b == 2:
                hinge_sides[idx] = "L"
                hinge_sides[idx + 1] = "R"
                idx += 2
            else:
                center = idx * cell + cell / 2.0
                hinge_sides[idx] = "L" if center <= W / 2.0 else "R"
                idx += 1

    if dh <= 900:
        n_h = 2
    elif dh <= 1600:
        n_h = 3
    else:
        n_h = 4
    z_door0 = leg_h + g
    he = p["hinge_end"]
    cup_zs = [z_door0 + he + j * (dh - 2 * he) / (n_h - 1) for j in range(n_h)]
    cup_r = p["hinge_d"] / 2.0

    for i in range(n):
        x0 = i * cell + g
        door = _box(x0, x0 + dw, -(g + door_t), -g, z_door0, z_door0 + dh)
        cx = x0 + p["hinge_edge"] if hinge_sides[i] == "L" else x0 + dw - p["hinge_edge"]
        cups = [cq.Solid.makeCylinder(cup_r, p["hinge_depth"],
                                      cq.Vector(cx, -g, zc), cq.Vector(0, -1, 0))
                for zc in cup_zs]
        parts.append(("door_%d" % (i + 1), _cut_all(door, cups)))

    # ---------- legs ----------
    leg_r = p["leg_d"] / 2.0
    off = p["leg_gap"] + leg_r
    span_x = W - 2 * off
    span_y = Dc - 2 * off
    nx = int(math.ceil(span_x / p["leg_max_spacing"])) + 1
    ny = int(math.ceil(span_y / p["leg_max_spacing"])) + 1
    xs = [off + i * span_x / (nx - 1) for i in range(nx)]
    ys = [off + j * span_y / (ny - 1) for j in range(ny)]
    li = 1
    for y in ys:
        for x in xs:
            parts.append(("leg_%d" % li,
                          cq.Solid.makeCylinder(leg_r, leg_h, cq.Vector(x, y, 0), cq.Vector(0, 0, 1))))
            li += 1

    return parts
