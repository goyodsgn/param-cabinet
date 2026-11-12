import math
import cadquery as cq

PARAMS = {
    "W": 1100,
    "H": 850,
    "D": 580,
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
    "n_doors": 3,
    "door_layout": [1, 2],
    "n_shelves": None,
    "shelf_min_gap": 320,
    "bottom_clear_min": None,
    "pin_max_spacing": 500,
    "leg_max_spacing": 600,
    "notes": [
        "Three door cells (n_doors = 3), each W/3 = 366.7 mm wide, under the 600 mm limit.",
        "door_layout = [1, 2]: a single door on the left (bay 1) and a double door (pair) made of the right two doors (bay 2).",
        "Hinges: door 1 (single, center left of W/2) hinges left; the pair opens left-right, so door 2 hinges left and door 3 hinges right.",
        "Only one inner wall is built, between the single door and the pair at x = W/3 (none behind the joint of the pair). This gives two bays, each with its own shelf set.",
    ],
}


def _box(x0, x1, y0, y1, z0, z1):
    return (
        cq.Workplane("XY")
        .box(x1 - x0, y1 - y0, z1 - z0, centered=False)
        .translate((x0, y0, z0))
    )


def _to_solid(wp):
    sols = wp.solids().vals()
    if len(sols) == 1:
        return sols[0]
    return wp.val()


def build(params):
    p = params
    W, H, D = p["W"], p["H"], p["D"]
    leg_h = p["leg_h"]
    t, back_t, div_t = p["t"], p["back_t"], p["divider_t"]
    door_t, shelf_t, g = p["door_t"], p["shelf_t"], p["door_gap"]
    door_max_w = p["door_max_w"]
    back_mode, top_mode = p["back_mode"], p["top_mode"]
    has_top = top_mode != "none"

    Dc = D - door_t - g
    inner_d = Dc - back_t
    side_d = inner_d if back_mode == "onset" else Dc

    parts = []

    # ---------------- carcass ----------------
    if top_mode == "onset":
        side_top = H - t
    else:
        side_top = H
    z0 = leg_h + t
    z1 = (H - t) if has_top else H
    clear_h = z1 - z0

    sides = {
        "side_left": _box(0, t, 0, side_d, leg_h, side_top),
        "side_right": _box(W - t, W, 0, side_d, leg_h, side_top),
    }

    # ---------------- doors / bays ----------------
    n_min = max(1, math.ceil(W / door_max_w - 1e-9))
    layout = p["door_layout"]
    if layout:
        n = sum(layout)
        if n < n_min:
            n = n_min
            layout = [1] * n
    else:
        n = max(p["n_doors"] or 0, n_min)
        layout = [1] * n
    cell = W / n

    bounds = []
    acc = 0
    for b in layout[:-1]:
        acc += b
        bounds.append(acc)
    div_x = [j * cell for j in bounds]

    dividers = {}
    for i, xc in enumerate(div_x):
        dividers["divider_%d" % (i + 1)] = _box(
            xc - div_t / 2, xc + div_t / 2, 0, inner_d, z0, z1
        )

    bays = []
    for b in range(len(layout)):
        if b == 0:
            xl, lname = t, "side_left"
        else:
            xl, lname = div_x[b - 1] + div_t / 2, "divider_%d" % b
        if b == len(layout) - 1:
            xr, rname = W - t, "side_right"
        else:
            xr, rname = div_x[b] - div_t / 2, "divider_%d" % (b + 1)
        bays.append((xl, xr, lname, rname))

    # ---------------- shelves ----------------
    bcm = p["bottom_clear_min"]
    if p["n_shelves"] is not None:
        k = max(0, int(p["n_shelves"]))
        use_bcm = False
    else:
        use_bcm = bcm is not None
        base = max(bcm, p["shelf_min_gap"]) if use_bcm else p["shelf_min_gap"]
        k = max(0, math.floor((clear_h - base) / (p["shelf_min_gap"] + shelf_t)))

    shelf_zb = []
    if k > 0:
        gap = (clear_h - k * shelf_t) / (k + 1)
        g0 = gap
        g1 = gap
        if use_bcm and gap < bcm:
            g0 = bcm
            g1 = (clear_h - bcm - k * shelf_t) / k
        for i in range(k):
            shelf_zb.append(z0 + g0 + i * (g1 + shelf_t))

    # pins
    pin_d = 5.0
    pin_len = 14.0
    pin_in = 8.0
    span = inner_d - 100
    n_pins = math.ceil(span / p["pin_max_spacing"] - 1e-9) + 1
    pin_ys = [50 + i * span / (n_pins - 1) for i in range(n_pins)] if n_pins > 1 else [50]

    panels = dict(sides)
    panels.update(dividers)

    shelves = []
    pins = []
    for (xl, xr, lname, rname) in bays:
        for zb in shelf_zb:
            shelves.append(_box(xl + 1, xr - 1, 0, inner_d, zb, zb + shelf_t))
            zc = zb - pin_d / 2
            for y in pin_ys:
                xs = xl - pin_in
                pins.append(
                    cq.Workplane("YZ", origin=(xs, y, zc)).circle(pin_d / 2).extrude(pin_len)
                )
                hole_l = cq.Workplane("YZ", origin=(xs, y, zc)).circle(pin_d / 2).extrude(pin_in)
                panels[lname] = panels[lname].cut(hole_l)
                xs = xr - (pin_len - pin_in)
                pins.append(
                    cq.Workplane("YZ", origin=(xs, y, zc)).circle(pin_d / 2).extrude(pin_len)
                )
                hole_r = cq.Workplane("YZ", origin=(xr, y, zc)).circle(pin_d / 2).extrude(pin_in)
                panels[rname] = panels[rname].cut(hole_r)

    # ---------------- back, top, bottom ----------------
    if back_mode == "onset":
        back = _box(0, W, Dc - back_t, Dc, leg_h, H)
    else:
        back = _box(t, W - t, Dc - back_t, Dc, z0, z1)

    bottom = _box(t, W - t, 0, side_d, leg_h, leg_h + t)

    parts.append(("side_left", _to_solid(panels["side_left"])))
    parts.append(("side_right", _to_solid(panels["side_right"])))
    if has_top:
        if top_mode == "onset":
            top = _box(0, W, 0, side_d, H - t, H)
        else:
            top = _box(t, W - t, 0, side_d, H - t, H)
        parts.append(("top", _to_solid(top)))
    parts.append(("bottom", _to_solid(bottom)))
    parts.append(("back", _to_solid(back)))
    for name in sorted(dividers.keys(), key=lambda s: int(s.split("_")[1])):
        parts.append((name, _to_solid(panels[name])))
    for i, s in enumerate(shelves):
        parts.append(("shelf_%d" % (i + 1), _to_solid(s)))
    for i, pn in enumerate(pins):
        parts.append(("pin_%d" % (i + 1), _to_solid(pn)))

    # ---------------- doors ----------------
    hinges = []
    if all(b == 1 for b in layout):
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
                center = (idx + 0.5) * cell
                hinges.append("L" if center <= W / 2 else "R")
            idx += b

    door_w = cell - 2 * g
    door_h = (H - leg_h) - 2 * g
    if door_h <= 900:
        n_cups = 2
    elif door_h <= 1600:
        n_cups = 3
    else:
        n_cups = 4
    cup_zs = [100 + i * (door_h - 200) / (n_cups - 1) for i in range(n_cups)]

    for i in range(n):
        dx0 = i * cell + g
        dz0 = leg_h + g
        door = _box(dx0, dx0 + door_w, -(g + door_t), -g, dz0, dz0 + door_h)
        cx = dx0 + 22.5 if hinges[i] == "L" else dx0 + door_w - 22.5
        for cz in cup_zs:
            cup = cq.Workplane("XZ", origin=(cx, -g, dz0 + cz)).circle(17.5).extrude(12)
            door = door.cut(cup)
        parts.append(("door_%d" % (i + 1), _to_solid(door)))

    # ---------------- legs ----------------
    leg_d = 40.0
    edge = 30.0
    x_a, x_b = edge + leg_d / 2, W - edge - leg_d / 2
    y_a, y_b = edge + leg_d / 2, Dc - edge - leg_d / 2
    nx = math.ceil((x_b - x_a) / p["leg_max_spacing"] - 1e-9) + 1
    ny = math.ceil((y_b - y_a) / p["leg_max_spacing"] - 1e-9) + 1
    xs_ = [x_a + i * (x_b - x_a) / (nx - 1) for i in range(nx)]
    ys_ = [y_a + j * (y_b - y_a) / (ny - 1) for j in range(ny)]
    li = 1
    for yy in ys_:
        for xx in xs_:
            leg = cq.Workplane("XY", origin=(xx, yy, 0)).circle(leg_d / 2).extrude(leg_h)
            parts.append(("leg_%d" % li, _to_solid(leg)))
            li += 1

    return parts
