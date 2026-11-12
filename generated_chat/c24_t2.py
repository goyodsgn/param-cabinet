import math
import cadquery as cq

PARAMS = {
    "W": 1200,
    "H": 850,
    "D": 534,  # inner depth 500 -> Dc = 500 + back_t(10) = 510 -> D = 510 + door_t(22) + door_gap(2)
    "leg_h": 100,
    "back_mode": "inset",
    "top_mode": "inset",
    "t": 18,
    "back_t": 10,
    "divider_t": 18,
    "door_t": 22,
    "shelf_t": 30,
    "door_gap": 2,
    "door_max_w": 600,
    "n_doors": None,
    "door_layout": [2],
    "n_shelves": None,
    "shelf_min_gap": 320,
    "bottom_clear_min": None,
    "pin_max_spacing": 500,
    "leg_max_spacing": 600,
    # extra rule values
    "pin_edge": 50,
    "pin_d": 5,
    "pin_hole_depth": 8,
    "pin_out": 6,
    "hinge_cup_d": 35,
    "hinge_cup_depth": 12,
    "hinge_cup_edge": 22.5,
    "hinge_end_offset": 100,
    "leg_d": 40,
    "leg_corner_gap": 30,
    "shelf_clearance": 1,
    "notes": [
        "내경 깊이 500 -> 캐비닛 깊이 Dc = 500 + 뒤판 10 = 510, 전체 깊이 D = 510 + 문 22 + 간격 2 = 534.",
        "뒷판은 인셋: 옆판 사이, 바닥판과 상판 사이에 끼워지고 뒤쪽 모서리가 면을 맞춥니다.",
        "문은 양문형 하나(door_layout = [1개 베이 = 문 2짝]): 문 2짝(각 셀 600), 가운데 칸막이 없음.",
        "칸막이가 없으므로 선반은 하나의 칸에만 들어갑니다.",
    ],
}


def _box(x0, x1, y0, y1, z0, z1):
    return cq.Solid.makeBox(x1 - x0, y1 - y0, z1 - z0, cq.Vector(x0, y0, z0))


def _cyl(r, length, x, y, z, d):
    return cq.Solid.makeCylinder(r, length, cq.Vector(x, y, z), cq.Vector(*d))


def _cut(solid, tools):
    res = solid
    for tl in tools:
        res = res.cut(tl)
    sols = res.Solids()
    return sols[0] if sols else solid


def build(params):
    p = params
    W, H, D = p["W"], p["H"], p["D"]
    leg_h, t, back_t = p["leg_h"], p["t"], p["back_t"]
    div_t, door_t, shelf_t = p["divider_t"], p["door_t"], p["shelf_t"]
    gap = p["door_gap"]
    max_w = p["door_max_w"]
    back_mode, top_mode = p["back_mode"], p["top_mode"]

    Dc = D - door_t - gap
    ds = Dc - back_t if back_mode == "onset" else Dc  # depth of sides/top/bottom
    d_in = Dc - back_t  # inner depth (to back panel inner face)

    has_top = top_mode != "none"
    z_bot_top = leg_h + t
    z_top_in = H - t if has_top else H
    clear_h = z_top_in - z_bot_top

    parts = {}
    order = []

    def add(name, solid):
        parts[name] = solid
        order.append(name)

    # ---------- doors count / layout ----------
    n_min = max(1, math.ceil(W / max_w - 1e-9))
    layout = p["door_layout"]
    if layout:
        n = sum(layout)
        if n < n_min:
            layout = None
    if not layout:
        n = n_min
        if p["n_doors"]:
            n = max(n, int(p["n_doors"]))
        layout = [1] * n
    cell = W / n

    # ---------- carcass ----------
    side_z1 = H - t if top_mode == "onset" else H
    add("side_left", _box(0, t, 0, ds, leg_h, side_z1))
    add("side_right", _box(W - t, W, 0, ds, leg_h, side_z1))
    add("bottom", _box(t, W - t, 0, ds, leg_h, leg_h + t))
    if top_mode == "inset":
        add("top", _box(t, W - t, 0, ds, H - t, H))
    elif top_mode == "onset":
        add("top", _box(0, W, 0, ds, H - t, H))
    if back_mode == "onset":
        add("back", _box(0, W, Dc - back_t, Dc, leg_h, H))
    else:
        add("back", _box(t, W - t, Dc - back_t, Dc, z_bot_top, z_top_in))

    # ---------- bays and dividers ----------
    bounds = []  # cell index of boundaries between bays
    acc = 0
    for b in layout[:-1]:
        acc += b
        bounds.append(acc)
    for i, j in enumerate(bounds):
        xc = j * cell
        add("divider_%d" % (i + 1),
            _box(xc - div_t / 2, xc + div_t / 2, 0, d_in, z_bot_top, z_top_in))

    nb = len(layout)
    bays = []
    for b in range(nb):
        if b == 0:
            xl, lname = t, "side_left"
        else:
            xl, lname = bounds[b - 1] * cell + div_t / 2, "divider_%d" % b
        if b == nb - 1:
            xr, rname = W - t, "side_right"
        else:
            xr, rname = bounds[b] * cell - div_t / 2, "divider_%d" % (b + 1)
        bays.append((xl, xr, lname, rname))

    # ---------- shelf count / positions ----------
    gmin = p["shelf_min_gap"]
    bcm = p["bottom_clear_min"]
    if p["n_shelves"] is not None:
        k = max(0, int(p["n_shelves"]))
        bcm_eff = None
    elif bcm:
        k = max(0, math.floor((clear_h - max(bcm, gmin)) / (gmin + shelf_t)))
        bcm_eff = bcm
    else:
        k = max(0, math.floor((clear_h - gmin) / (gmin + shelf_t)))
        bcm_eff = None

    shelf_zs = []  # bottom z of each shelf
    if k > 0:
        g = (clear_h - k * shelf_t) / (k + 1)
        if bcm_eff and g < bcm_eff:
            g2 = (clear_h - bcm_eff - k * shelf_t) / k
            for i in range(k):
                shelf_zs.append(z_bot_top + bcm_eff + i * (shelf_t + g2))
        else:
            for i in range(1, k + 1):
                shelf_zs.append(z_bot_top + i * g + (i - 1) * shelf_t)

    # ---------- shelves + pins ----------
    clr = p["shelf_clearance"]
    edge = p["pin_edge"]
    pr = p["pin_d"] / 2.0
    hole_d = p["pin_hole_depth"]
    pin_out = p["pin_out"]
    span = d_in - 2 * edge
    if span > 0:
        m = math.ceil(span / p["pin_max_spacing"] - 1e-9) + 1
        pin_ys = [edge + i * span / (m - 1) for i in range(m)]
    else:
        pin_ys = [d_in / 2.0]

    holes = {}
    pins = []
    shelf_no = 0
    for (xl, xr, lname, rname) in bays:
        for zb in shelf_zs:
            shelf_no += 1
            add("shelf_%d" % shelf_no,
                _box(xl + clr, xr - clr, 0, d_in, zb, zb + shelf_t))
            zc = zb - pr
            for y in pin_ys:
                # left panel
                holes.setdefault(lname, []).append(
                    _cyl(pr, hole_d, xl - hole_d, y, zc, (1, 0, 0)))
                pins.append(_cyl(pr, hole_d + pin_out, xl - hole_d, y, zc, (1, 0, 0)))
                # right panel
                holes.setdefault(rname, []).append(
                    _cyl(pr, hole_d, xr, y, zc, (1, 0, 0)))
                pins.append(_cyl(pr, hole_d + pin_out, xr + hole_d, y, zc, (-1, 0, 0)))

    for name, tools in holes.items():
        parts[name] = _cut(parts[name], tools)

    for i, pn in enumerate(pins):
        add("pin_%d" % (i + 1), pn)

    # ---------- door hinge sides ----------
    hinge = []  # 'L' or 'R' per door
    all_single = all(b == 1 for b in layout)
    if all_single:
        for i in range(n):
            hinge.append("L" if i % 2 == 0 else "R")
        if n > 1 and n % 2 == 1:
            hinge[-1] = "R"
    else:
        idx = 0
        for b in layout:
            if b == 2:
                hinge.append("L")
                hinge.append("R")
            else:
                cx = (idx + 0.5) * cell
                hinge.append("L" if cx <= W / 2 else "R")
            idx += b

    # ---------- doors ----------
    door_w = cell - 2 * gap
    door_h = (H - leg_h) - 2 * gap
    if door_h <= 900:
        nh = 2
    elif door_h <= 1600:
        nh = 3
    else:
        nh = 4
    zd0 = leg_h + gap
    zd1 = zd0 + door_h
    cup_r = p["hinge_cup_d"] / 2.0
    cup_depth = p["hinge_cup_depth"]
    cup_edge = p["hinge_cup_edge"]
    end_off = p["hinge_end_offset"]
    cup_zs = [zd1 - end_off - i * (door_h - 2 * end_off) / (nh - 1) for i in range(nh)]
    for i in range(n):
        x0 = i * cell + gap
        x1 = x0 + door_w
        door = _box(x0, x1, -(gap + door_t), -gap, zd0, zd1)
        cx = x0 + cup_edge if hinge[i] == "L" else x1 - cup_edge
        cups = [_cyl(cup_r, cup_depth, cx, -gap - cup_depth, z, (0, 1, 0)) for z in cup_zs]
        add("door_%d" % (i + 1), _cut(door, cups))

    # ---------- legs ----------
    leg_r = p["leg_d"] / 2.0
    off = p["leg_corner_gap"] + leg_r
    sx = W - 2 * off
    sy = Dc - 2 * off
    nx = math.ceil(sx / p["leg_max_spacing"] - 1e-9) + 1 if sx > 0 else 1
    ny = math.ceil(sy / p["leg_max_spacing"] - 1e-9) + 1 if sy > 0 else 1
    nx = max(nx, 2)
    ny = max(ny, 2)
    li = 0
    for ix in range(nx):
        for iy in range(ny):
            li += 1
            x = off + ix * sx / (nx - 1)
            y = off + iy * sy / (ny - 1)
            add("leg_%d" % li, _cyl(leg_r, leg_h, x, y, 0, (0, 0, 1)))

    return [(name, parts[name]) for name in order]
