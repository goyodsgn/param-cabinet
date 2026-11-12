import math
import cadquery as cq

PARAMS = {
    "W": 1200,
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
    "pin_edge": 50,
    "pin_hole_depth": 8,
    "pin_out": 6,
    "shelf_clear": 1,
    "hinge_cup_d": 35,
    "hinge_cup_depth": 12,
    "hinge_cup_edge": 22.5,
    "hinge_end_offset": 100,
    "leg_d": 40,
    "leg_edge_gap": 30,
}


def _ceil(x):
    return int(math.ceil(x - 1e-9))


def _floor(x):
    return int(math.floor(x + 1e-9))


def _box(x0, x1, y0, y1, z0, z1):
    return (cq.Workplane("XY")
            .box(x1 - x0, y1 - y0, z1 - z0, centered=False)
            .translate((x0, y0, z0)))


def _cyl(r, h, x, y, z, d):
    return cq.Workplane("XY").add(
        cq.Solid.makeCylinder(r, h, cq.Vector(x, y, z), cq.Vector(*d)))


def _solid(wp):
    v = wp.val()
    if isinstance(v, cq.Solid):
        return v
    return v.Solids()[0]


def _shelf_bottoms(clear_h, z0, k, shelf_t, bcm):
    """Bottom z of each shelf, spread evenly (lowest space = bcm if needed)."""
    if k <= 0:
        return []
    s = (clear_h - k * shelf_t) / (k + 1)
    res = []
    if bcm is not None and s < bcm - 1e-9:
        if k == 1:
            s_first = bcm
            res.append(z0 + s_first)
            return res
        s2 = (clear_h - bcm - k * shelf_t) / k
        zb = z0 + bcm
        res.append(zb)
        for _ in range(k - 1):
            zb = zb + shelf_t + s2
            res.append(zb)
        return res
    for i in range(1, k + 1):
        res.append(z0 + i * s + (i - 1) * shelf_t)
    return res


def build(params):
    p = params
    W, H, D = p["W"], p["H"], p["D"]
    leg_h = p["leg_h"]
    t, back_t, dt = p["t"], p["back_t"], p["divider_t"]
    door_t, shelf_t, gap = p["door_t"], p["shelf_t"], p["door_gap"]
    top_mode, back_mode = p["top_mode"], p["back_mode"]

    Dc = D - door_t - gap
    inner_d = Dc - back_t  # depth of dividers / shelves

    # ---------- doors / bays ----------
    n_min = max(1, _ceil(W / p["door_max_w"]))
    layout = p["door_layout"]
    n = p["n_doors"] if p["n_doors"] else n_min
    n = max(n, n_min)
    if layout:
        if sum(layout) >= n_min:
            n = sum(layout)
        else:
            layout = None
    if not layout:
        layout = [1] * n
    cell = W / n

    # ---------- carcass extents ----------
    if top_mode == "onset":
        side_z1 = H - t
    else:
        side_z1 = H
    depth_c = inner_d if back_mode == "onset" else Dc
    z_bot0 = leg_h + t
    if top_mode == "none":
        z_clear1 = H
    else:
        z_clear1 = H - t
    clear_h = z_clear1 - z_bot0

    # ---------- wall positions ----------
    wall_x = []
    acc = 0
    for b in layout[:-1]:
        acc += b
        wall_x.append(acc * cell)

    # bays: (xl, xr) clear spans between vertical panels
    edges = [t] + [None] * 0
    bays = []
    left = t
    for xc in wall_x:
        bays.append((left, xc - dt / 2))
        left = xc + dt / 2
    bays.append((left, W - t))

    # ---------- shelves ----------
    bcm = p["bottom_clear_min"]
    if p["n_shelves"] is not None:
        k = p["n_shelves"]
    elif bcm is None:
        k = max(0, _floor((clear_h - p["shelf_min_gap"]) / (p["shelf_min_gap"] + shelf_t)))
    else:
        k = max(0, _floor((clear_h - max(bcm, p["shelf_min_gap"])) /
                          (p["shelf_min_gap"] + shelf_t)))
    shelf_zs = _shelf_bottoms(clear_h, z_bot0, k, shelf_t, bcm)

    # pins along depth
    pin_span = inner_d - 2 * p["pin_edge"]
    n_pin = _ceil(pin_span / p["pin_max_spacing"]) + 1
    pin_ys = [p["pin_edge"] + i * pin_span / (n_pin - 1) for i in range(n_pin)]
    pr = p["pin_d"] / 2
    pin_len = p["pin_hole_depth"] + p["pin_out"]
    hd = p["pin_hole_depth"]

    # ---------- panels ----------
    left_panel = _box(0, t, 0, depth_c, leg_h, side_z1)
    right_panel = _box(W - t, W, 0, depth_c, leg_h, side_z1)
    dividers = [_box(xc - dt / 2, xc + dt / 2, 0, inner_d, z_bot0, z_clear1)
                for xc in wall_x]

    pins = []
    n_bays = len(bays)
    for bi, (xl, xr) in enumerate(bays):
        for zb in shelf_zs:
            zc = zb - p["pin_d"] / 2
            for y in pin_ys:
                # left side of the bay
                hole = _cyl(pr, hd, xl - hd, y, zc, (1, 0, 0))
                if bi == 0:
                    left_panel = left_panel.cut(hole)
                else:
                    dividers[bi - 1] = dividers[bi - 1].cut(hole)
                pins.append(_cyl(pr, pin_len, xl - hd, y, zc, (1, 0, 0)))
                # right side of the bay
                hole = _cyl(pr, hd, xr, y, zc, (1, 0, 0))
                if bi == n_bays - 1:
                    right_panel = right_panel.cut(hole)
                else:
                    dividers[bi] = dividers[bi].cut(hole)
                pins.append(_cyl(pr, pin_len, xr - p["pin_out"], y, zc, (1, 0, 0)))

    parts = []
    parts.append(("side_left", _solid(left_panel)))
    parts.append(("side_right", _solid(right_panel)))

    if top_mode == "inset":
        parts.append(("top", _solid(_box(t, W - t, 0, depth_c, H - t, H))))
    elif top_mode == "onset":
        parts.append(("top", _solid(_box(0, W, 0, depth_c, H - t, H))))

    parts.append(("bottom", _solid(_box(t, W - t, 0, depth_c, leg_h, leg_h + t))))

    if back_mode == "onset":
        back = _box(0, W, Dc - back_t, Dc, leg_h, H)
    else:
        back = _box(t, W - t, Dc - back_t, Dc, leg_h + t, z_clear1)
    parts.append(("back", _solid(back)))

    for i, d in enumerate(dividers):
        parts.append((f"divider_{i + 1}", _solid(d)))

    # shelves
    si = 0
    for (xl, xr) in bays:
        for zb in shelf_zs:
            si += 1
            parts.append((f"shelf_{si}",
                          _solid(_box(xl + p["shelf_clear"], xr - p["shelf_clear"],
                                      0, inner_d, zb, zb + shelf_t))))

    for i, pn in enumerate(pins):
        parts.append((f"pin_{i + 1}", _solid(pn)))

    # ---------- doors ----------
    only_singles = all(b == 1 for b in layout)
    hinge = []  # 'L' / 'R' per door
    if only_singles:
        for i in range(n):
            hinge.append("L" if i % 2 == 0 else "R")
        # odd count > 1: the last door hinges right
        if n > 1 and n % 2 == 1:
            hinge[-1] = "R"
    else:
        idx = 0
        for b in layout:
            if b == 2:
                hinge += ["L", "R"]
            else:
                cx = idx * cell + cell / 2
                hinge.append("L" if cx <= W / 2 else "R")
            idx += b

    door_w = cell - 2 * gap
    door_h = (H - leg_h) - 2 * gap
    if door_h <= 900:
        nh = 2
    elif door_h <= 1600:
        nh = 3
    else:
        nh = 4
    z_bottom = leg_h + gap
    z_top = z_bottom + door_h
    zc0 = z_bottom + p["hinge_end_offset"]
    zc1 = z_top - p["hinge_end_offset"]
    hz = [zc0 + i * (zc1 - zc0) / (nh - 1) for i in range(nh)]

    for i in range(n):
        x0 = i * cell + gap
        door = _box(x0, x0 + door_w, -(gap + door_t), -gap, z_bottom, z_top)
        cx = x0 + p["hinge_cup_edge"] if hinge[i] == "L" else x0 + door_w - p["hinge_cup_edge"]
        for z in hz:
            cup = _cyl(p["hinge_cup_d"] / 2, p["hinge_cup_depth"], cx, -gap, z, (0, -1, 0))
            door = door.cut(cup)
        parts.append((f"door_{i + 1}", _solid(door)))

    # ---------- legs ----------
    lr = p["leg_d"] / 2
    off = p["leg_edge_gap"] + lr
    x_a, x_b = off, W - off
    y_a, y_b = off, Dc - off
    nx = _ceil((x_b - x_a) / p["leg_max_spacing"]) + 1
    ny = _ceil((y_b - y_a) / p["leg_max_spacing"]) + 1
    xs = [x_a + i * (x_b - x_a) / (nx - 1) for i in range(nx)] if nx > 1 else [x_a]
    ys = [y_a + j * (y_b - y_a) / (ny - 1) for j in range(ny)] if ny > 1 else [y_a]
    li = 0
    for y in ys:
        for x in xs:
            li += 1
            parts.append((f"leg_{li}", _solid(_cyl(lr, leg_h, x, y, 0, (0, 0, 1)))))

    return parts
