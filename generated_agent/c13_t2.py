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
    "n_doors": 3,
    "door_layout": None,
    "single_door_hinge": None,
    "n_shelves": 0,
    "shelf_min_gap": 320,
    "bottom_clear_min": None,
    "pin_max_spacing": 500,
    "leg_max_spacing": 600,
    "notes": [],
}


def _box(x0, x1, y0, y1, z0, z1):
    return (
        cq.Workplane("XY")
        .box(x1 - x0, y1 - y0, z1 - z0, centered=False)
        .translate((x0, y0, z0))
        .val()
    )


def _cyl(r, h, p, d):
    return cq.Solid.makeCylinder(r, h, cq.Vector(*p), cq.Vector(*d))


def _cut(solid, tools):
    wp = cq.Workplane("XY").add(solid)
    for tool in tools:
        wp = wp.cut(cq.Workplane("XY").add(tool))
    return wp.val()


def _spread(a, b, k):
    if k == 1:
        return [(a + b) / 2.0]
    return [a + (b - a) * i / (k - 1) for i in range(k)]


def build(params):
    p = params
    W, H, D = p["W"], p["H"], p["D"]
    leg_h = p["leg_h"]
    t, back_t, dt = p["t"], p["back_t"], p["divider_t"]
    door_t, shelf_t, gap = p["door_t"], p["shelf_t"], p["door_gap"]
    top_mode, back_mode = p["top_mode"], p["back_mode"]

    Dc = D - door_t - gap
    has_top = top_mode != "none"
    onset_top = top_mode == "onset"
    inner_d = Dc - back_t  # depth of inner space (front to back panel inner face)
    side_d = inner_d if back_mode == "onset" else Dc

    z_bot = leg_h
    z_top = H
    side_z1 = H - t if onset_top else H
    inner_z0 = leg_h + t
    inner_z1 = H - t if has_top else H
    clear_h = inner_z1 - inner_z0

    parts = []

    # ---- door layout ----
    layout = p.get("door_layout")
    if layout:
        n = sum(layout)
    else:
        n = max(1, math.ceil(W / p["door_max_w"]))
        if p.get("n_doors"):
            n = max(n, int(p["n_doors"]))
        layout = [1] * n
    if p.get("single_door_hinge"):
        layout = [1] * n
    cell = W / n

    # hinge side per door
    hinge = []
    all_single = all(b == 1 for b in layout)
    if p.get("single_door_hinge"):
        hinge = [p["single_door_hinge"]] * n
    elif all_single:
        for i in range(n):
            hinge.append("left" if i % 2 == 0 else "right")
        if n > 1 and n % 2 == 1:
            hinge[-1] = "right"
    else:
        idx = 0
        for b in layout:
            if b == 2:
                hinge += ["left", "right"]
            else:
                cx = (idx + 0.5) * cell
                hinge.append("left" if cx <= W / 2 else "right")
            idx += b

    # divider centers
    div_x = []
    acc = 0
    for b in layout[:-1]:
        acc += b
        div_x.append(acc * cell)

    # ---- vertical panels list: (x0, x1, name) ----
    panels = [(0.0, float(t))]
    for c in div_x:
        panels.append((c - dt / 2.0, c + dt / 2.0))
    panels.append((W - t, float(W)))

    # ---- shelves ----
    n_sh = p.get("n_shelves")
    bcm = p.get("bottom_clear_min")
    min_gap = p["shelf_min_gap"]
    if n_sh is None:
        base = max(bcm, min_gap) if bcm else min_gap
        k = max(0, int(math.floor((clear_h - base) / (min_gap + shelf_t))))
    else:
        k = int(n_sh)
    shelf_z0 = []  # bottom z of each shelf
    if k > 0:
        space = (clear_h - k * shelf_t) / (k + 1)
        if bcm and n_sh is None and space < bcm:
            low = bcm
            rest = (clear_h - low - k * shelf_t) / k if k > 0 else 0
            z = inner_z0 + low
            for i in range(k):
                shelf_z0.append(z)
                z += shelf_t + rest
        else:
            for i in range(k):
                shelf_z0.append(inner_z0 + space * (i + 1) + shelf_t * i)

    # pins & shelves
    pin_r = 2.5
    span = inner_d - 100.0
    n_pin = int(math.ceil(span / p["pin_max_spacing"])) + 1
    pin_ys = _spread(50.0, inner_d - 50.0, n_pin)
    holes = {i: [] for i in range(len(panels))}
    pins = []
    shelves = []
    for bi in range(len(panels) - 1):
        xl = panels[bi][1]
        xr = panels[bi + 1][0]
        for z0 in shelf_z0:
            shelves.append(_box(xl + 1, xr - 1, 0, inner_d, z0, z0 + shelf_t))
            pz = z0 - pin_r
            for y in pin_ys:
                # left panel (bi): hole into panel from its right face
                holes[bi].append(_cyl(pin_r, 8, (xl - 8, y, pz), (1, 0, 0)))
                pins.append(_cyl(pin_r, 14, (xl - 8, y, pz), (1, 0, 0)))
                # right panel (bi+1): hole into panel from its left face
                holes[bi + 1].append(_cyl(pin_r, 8, (xr, y, pz), (1, 0, 0)))
                pins.append(_cyl(pin_r, 14, (xr - 6, y, pz), (1, 0, 0)))

    # ---- sides ----
    sl = _box(0, t, 0, side_d, z_bot, side_z1)
    sr = _box(W - t, W, 0, side_d, z_bot, side_z1)
    parts.append(("side_left", _cut(sl, holes[0])))
    parts.append(("side_right", _cut(sr, holes[len(panels) - 1])))

    # ---- top / bottom ----
    if has_top:
        if onset_top:
            parts.append(("top", _box(0, W, 0, side_d, H - t, H)))
        else:
            parts.append(("top", _box(t, W - t, 0, side_d, H - t, H)))
    parts.append(("bottom", _box(t, W - t, 0, side_d, leg_h, leg_h + t)))

    # ---- back ----
    if back_mode == "onset":
        parts.append(("back", _box(0, W, Dc - back_t, Dc, leg_h, H)))
    else:
        parts.append(("back", _box(t, W - t, Dc - back_t, Dc, inner_z0, inner_z1)))

    # ---- dividers ----
    for j in range(len(div_x)):
        x0, x1 = panels[j + 1]
        d = _box(x0, x1, 0, inner_d, inner_z0, inner_z1)
        parts.append(("divider_%d" % (j + 1), _cut(d, holes[j + 1])))

    # ---- shelves, pins ----
    for i, s in enumerate(shelves):
        parts.append(("shelf_%d" % (i + 1), s))
    for i, s in enumerate(pins):
        parts.append(("pin_%d" % (i + 1), s))

    # ---- doors ----
    dw = cell - 2 * gap
    dh = (H - leg_h) - 2 * gap
    n_h = 2 if dh <= 900 else (3 if dh <= 1600 else 4)
    for i in range(n):
        x0 = i * cell + gap
        z0 = leg_h + gap
        door = _box(x0, x0 + dw, -(gap + door_t), -gap, z0, z0 + dh)
        cx = x0 + 22.5 if hinge[i] == "left" else x0 + dw - 22.5
        cups = []
        for hz in _spread(z0 + 100, z0 + dh - 100, n_h):
            cups.append(_cyl(17.5, 12, (cx, -gap - 12, hz), (0, 1, 0)))
        parts.append(("door_%d" % (i + 1), _cut(door, cups)))

    # ---- legs ----
    nx = int(math.ceil((W - 100.0) / p["leg_max_spacing"])) + 1
    ny = int(math.ceil((Dc - 100.0) / p["leg_max_spacing"])) + 1
    lxs = _spread(50.0, W - 50.0, nx)
    lys = _spread(50.0, Dc - 50.0, ny)
    li = 1
    for x in lxs:
        for y in lys:
            parts.append(("leg_%d" % li, _cyl(20, leg_h, (x, y, 0), (0, 0, 1))))
            li += 1

    return parts
