import math
import cadquery as cq

PARAMS = {
    "W": 900,
    "H": 832,  # no top: inner height 714 = H - leg_h - t  ->  H = 714 + 100 + 18
    "D": 580,
    "leg_h": 100,
    "back_mode": "onset",
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
    "single_door_hinge": None,
    "n_shelves": None,
    "shelf_min_gap": 320,
    "bottom_clear_min": None,
    "pin_max_spacing": 500,
    "leg_max_spacing": 600,
    "notes": [
        "싱크대 설치를 위해 상판을 없앴습니다(top 없음).",
        "상판이 없어 안쪽 높이 714 -> H = 714 + 다리 100 + 하판 18 = 832로 환산했습니다.",
    ],
}


def _box(x0, y0, z0, dx, dy, dz):
    return cq.Workplane("XY").box(dx, dy, dz, centered=False).translate((x0, y0, z0)).val()


def _solid(shape):
    if isinstance(shape, cq.Solid):
        return shape
    sols = shape.Solids()
    return sols[0] if len(sols) == 1 else cq.Compound.makeCompound(sols)


def _cyl(r, h, pnt, d):
    return cq.Solid.makeCylinder(r, h, cq.Vector(*pnt), cq.Vector(*d))


def build(params):
    p = params
    W, H, D = p["W"], p["H"], p["D"]
    leg_h, t, back_t = p["leg_h"], p["t"], p["back_t"]
    div_t, door_t, shelf_t, gap = p["divider_t"], p["door_t"], p["shelf_t"], p["door_gap"]
    top_mode, back_mode = p["top_mode"], p["back_mode"]
    Dc = D - door_t - gap
    has_top = top_mode != "none"
    parts = []

    # ---- doors / bays
    layout = p["door_layout"]
    if layout:
        n = sum(layout)
        bays = list(layout)
    else:
        n = max(1, math.ceil(W / p["door_max_w"]))
        if p["n_doors"]:
            n = max(n, int(p["n_doors"]))
        bays = [1] * n
    cw = W / n

    # ---- carcass dimensions
    car_h = H - leg_h
    side_depth = Dc - back_t if back_mode == "onset" else Dc
    z_bot = leg_h
    z_top = H
    if top_mode == "onset":
        side_top = H - t
    else:
        side_top = H
    clear_h = car_h - 2 * t if has_top else car_h - t
    z_in0 = leg_h + t
    z_in1 = z_in0 + clear_h
    inner_depth = Dc - back_t

    # ---- bay boundaries (inner walls)
    wall_x = []
    j = 0
    for b in bays[:-1]:
        j += b
        wall_x.append(j * cw)

    # vertical panels: (name, x_min, x_max)
    # bay edges
    bay_edges = []
    left = t
    for wx in wall_x:
        bay_edges.append((left, wx - div_t / 2))
        left = wx + div_t / 2
    bay_edges.append((left, W - t))

    # ---- shelves layout (z of shelf bottoms)
    gmin = p["shelf_min_gap"]
    bcm = p["bottom_clear_min"]
    if p["n_shelves"] is not None:
        k = int(p["n_shelves"])
        sp = (clear_h - k * shelf_t) / (k + 1)
        shelf_z = [z_in0 + sp * (i + 1) + shelf_t * i for i in range(k)]
    else:
        base = max(bcm, gmin) if bcm else gmin
        k = max(0, math.floor((clear_h - base) / (gmin + shelf_t)))
        if k == 0:
            shelf_z = []
        else:
            sp = (clear_h - k * shelf_t) / (k + 1)
            if bcm and sp < bcm:
                rest = (clear_h - bcm - k * shelf_t) / k
                shelf_z = [z_in0 + bcm + (rest + shelf_t) * i for i in range(k)]
            else:
                shelf_z = [z_in0 + sp * (i + 1) + shelf_t * i for i in range(k)]

    shelf_depth = inner_depth
    span = shelf_depth - 100
    n_pin = math.ceil(span / p["pin_max_spacing"]) + 1
    pin_y = [50 + span * i / (n_pin - 1) for i in range(n_pin)]

    # collect pins and holes per panel
    holes = {"side_left": [], "side_right": []}
    for i in range(len(wall_x)):
        holes["divider_%d" % (i + 1)] = []
    shelves, pins = [], []
    for bi, (xl, xr) in enumerate(bay_edges):
        left_panel = "side_left" if bi == 0 else "divider_%d" % bi
        right_panel = "side_right" if bi == len(bay_edges) - 1 else "divider_%d" % (bi + 1)
        for zb in shelf_z:
            shelves.append(_box(xl + 1, 0, zb, (xr - xl) - 2, shelf_depth, shelf_t))
            zc = zb - 2.5
            for y in pin_y:
                # left pin: 8 in the panel, 6 out
                pins.append(_cyl(2.5, 14, (xl - 8, y, zc), (1, 0, 0)))
                holes[left_panel].append(_cyl(2.5, 8, (xl - 8, y, zc), (1, 0, 0)))
                pins.append(_cyl(2.5, 14, (xr - 6, y, zc), (1, 0, 0)))
                holes[right_panel].append(_cyl(2.5, 8, (xr, y, zc), (1, 0, 0)))

    def drill(name, box):
        for c in holes.get(name, []):
            box = box.cut(c)
        return _solid(box)

    # ---- carcass panels
    parts.append(("side_left", drill("side_left", _box(0, 0, z_bot, t, side_depth, side_top - z_bot))))
    parts.append(("side_right", drill("side_right", _box(W - t, 0, z_bot, t, side_depth, side_top - z_bot))))
    parts.append(("bottom", _box(t, 0, z_bot, W - 2 * t, side_depth, t)))
    if top_mode == "inset":
        parts.append(("top", _box(t, 0, H - t, W - 2 * t, side_depth, t)))
    elif top_mode == "onset":
        parts.append(("top", _box(0, 0, H - t, W, side_depth, t)))
    if back_mode == "onset":
        parts.append(("back", _box(0, Dc - back_t, z_bot, W, back_t, car_h)))
    else:
        bz1 = H - t if has_top else H
        parts.append(("back", _box(t, Dc - back_t, z_bot + t, W - 2 * t, back_t, bz1 - (z_bot + t))))

    for i, wx in enumerate(wall_x):
        name = "divider_%d" % (i + 1)
        parts.append((name, drill(name, _box(wx - div_t / 2, 0, z_in0, div_t, inner_depth, clear_h))))

    for i, s in enumerate(shelves):
        parts.append(("shelf_%d" % (i + 1), _solid(s)))
    for i, s in enumerate(pins):
        parts.append(("pin_%d" % (i + 1), _solid(s)))

    # ---- doors
    # hinge sides
    hinge = []
    if p["single_door_hinge"]:
        hinge = [p["single_door_hinge"]] * n
    elif layout:
        idx = 0
        for b in bays:
            if b == 2:
                hinge += ["left", "right"]
            else:
                cx = (idx + 0.5) * cw
                hinge.append("left" if cx <= W / 2 else "right")
            idx += b
    else:
        hinge = ["left" if i % 2 == 0 else "right" for i in range(n)]
        if n > 1 and n % 2 == 1:
            hinge[-1] = "right"

    door_w = cw - 2 * gap
    door_h = car_h - 2 * gap
    n_h = 2 if door_h <= 900 else (3 if door_h <= 1600 else 4)
    hz = [100 + (door_h - 200) * i / (n_h - 1) for i in range(n_h)]
    for i in range(n):
        x0 = i * cw + gap
        z0 = leg_h + gap
        d = _box(x0, -(gap + door_t), z0, door_w, door_t, door_h)
        cx = x0 + 22.5 if hinge[i] == "left" else x0 + door_w - 22.5
        for h in hz:
            d = d.cut(_cyl(17.5, 12, (cx, -(gap + 12), z0 + h), (0, 1, 0)))
        parts.append(("door_%d" % (i + 1), _solid(d)))

    # ---- legs
    lm = 30 + 20
    xs0, xs1 = lm, W - lm
    ys0, ys1 = lm, Dc - lm
    nx = math.ceil((xs1 - xs0) / p["leg_max_spacing"]) + 1
    ny = math.ceil((ys1 - ys0) / p["leg_max_spacing"]) + 1
    li = 1
    for a in range(nx):
        x = xs0 + (xs1 - xs0) * a / (nx - 1)
        for b in range(ny):
            y = ys0 + (ys1 - ys0) * b / (ny - 1)
            parts.append(("leg_%d" % li, _solid(_cyl(20, leg_h, (x, y, 0), (0, 0, 1)))))
            li += 1

    return parts
