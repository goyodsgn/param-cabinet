import math
import cadquery as cq

PARAMS = {
    "W": 2400,
    "H": 850,
    "D": 580,
    "leg_h": 100,
    "back_mode": "onset",
    "t": 18,
    "back_t": 10,
    "divider_t": 18,
    "door_t": 22,
    "shelf_t": 30,
    "door_gap": 2,
    "door_max_w": 600,
    "n_doors": None,
    "n_shelves": None,
    "shelf_min_gap": 320,
    "pin_max_spacing": 500,
    "leg_max_spacing": 600,
    "leg_d": 40,
    "leg_edge_gap": 30,
    "pin_d": 5,
    "pin_len": 14,
    "pin_hole_depth": 8,
    "pin_edge": 50,
    "shelf_clear": 1,
    "hinge_d": 35,
    "hinge_depth": 12,
    "hinge_edge": 22.5,
    "hinge_end": 100,
    "notes": [
        "요청하신 '다리 4개(네 귀퉁이만)'는 적용하지 않았습니다. 절대 규칙상 다리 중심 간격은 600mm 이하여야 합니다.",
        "폭 방향 코너 다리 간격이 2300mm이므로 폭 방향 5개 x 깊이 방향 2개 = 총 10개의 다리를 격자로 배치했습니다.",
        "폭 2400 기준 문은 4개(셀 폭 600), 칸막이 3개가 자동 적용됩니다.",
    ],
}


def _box(x0, x1, y0, y1, z0, z1):
    return (cq.Workplane("XY")
            .box(x1 - x0, y1 - y0, z1 - z0, centered=False)
            .translate((x0, y0, z0)).val())


def _cyl(r, h, x, y, z, d):
    return cq.Solid.makeCylinder(r, h, cq.Vector(x, y, z), cq.Vector(*d))


def _cut(solid, cutters):
    s = solid
    for c in cutters:
        s = s.cut(c)
    return s.Solids()[0] if hasattr(s, "Solids") and s.Solids() else s


def build(params):
    p = params
    W, H, D = p["W"], p["H"], p["D"]
    leg_h = p["leg_h"]
    t, back_t, dt = p["t"], p["back_t"], p["divider_t"]
    door_t, shelf_t, gap = p["door_t"], p["shelf_t"], p["door_gap"]
    mode = p["back_mode"]

    Dc = D - door_t - gap
    Hc = H - leg_h
    z0c, z1c = leg_h, H
    inner_depth = Dc - back_t
    body_depth = inner_depth if mode == "onset" else Dc

    # door count
    n = max(1, math.ceil(W / p["door_max_w"] - 1e-9))
    if p["n_doors"] is not None:
        n = max(n, int(p["n_doors"]))
    cell = W / n

    parts = {}
    order = []

    def add(name, solid):
        parts[name] = solid
        order.append(name)

    # carcass
    add("side_left", _box(0, t, 0, body_depth, z0c, z1c))
    add("side_right", _box(W - t, W, 0, body_depth, z0c, z1c))
    add("top", _box(t, W - t, 0, body_depth, z1c - t, z1c))
    add("bottom", _box(t, W - t, 0, body_depth, z0c, z0c + t))
    if mode == "onset":
        add("back", _box(0, W, inner_depth, Dc, z0c, z1c))
    else:
        add("back", _box(t, W - t, Dc - back_t, Dc, z0c + t, z1c - t))

    # dividers
    for j in range(1, n):
        xc = j * cell
        add("divider_%d" % j,
            _box(xc - dt / 2, xc + dt / 2, 0, inner_depth, z0c + t, z1c - t))

    # bays
    lefts = [t] + [j * cell + dt / 2 for j in range(1, n)]
    rights = [j * cell - dt / 2 for j in range(1, n)] + [W - t]

    clear_h = Hc - 2 * t
    if p["n_shelves"] is None:
        k = max(0, math.floor((clear_h - p["shelf_min_gap"]) / (p["shelf_min_gap"] + shelf_t)))
    else:
        k = max(0, int(p["n_shelves"]))

    cuts = {}  # panel name -> list of hole cutters
    pins = []
    shelves = []
    if k > 0:
        space = (clear_h - k * shelf_t) / (k + 1)
        sc = p["shelf_clear"]
        pe = p["pin_edge"]
        pr = p["pin_d"] / 2.0
        hd = p["pin_hole_depth"]
        plen = p["pin_len"]
        for b in range(n):
            bl, br = lefts[b], rights[b]
            lp = "side_left" if b == 0 else "divider_%d" % b
            rp = "side_right" if b == n - 1 else "divider_%d" % (b + 1)
            sd = inner_depth
            span = sd - 2 * pe
            m = max(2, math.ceil(span / p["pin_max_spacing"] - 1e-9) + 1)
            ys = [pe + i * span / (m - 1) for i in range(m)]
            for i in range(1, k + 1):
                zb = z0c + t + i * space + (i - 1) * shelf_t
                shelves.append(_box(bl + sc, br - sc, 0, sd, zb, zb + shelf_t))
                zc = zb - p["pin_d"] / 2.0
                for y in ys:
                    # left panel pin
                    pins.append(_cyl(pr, plen, bl - hd, y, zc, (1, 0, 0)))
                    cuts.setdefault(lp, []).append(_cyl(pr, hd, bl - hd, y, zc, (1, 0, 0)))
                    # right panel pin
                    pins.append(_cyl(pr, plen, br - (plen - hd), y, zc, (1, 0, 0)))
                    cuts.setdefault(rp, []).append(_cyl(pr, hd, br, y, zc, (1, 0, 0)))

    for name, cl in cuts.items():
        parts[name] = _cut(parts[name], cl)

    for i, s in enumerate(shelves, 1):
        add("shelf_%d" % i, s)
    for i, s in enumerate(pins, 1):
        add("pin_%d" % i, s)

    # doors
    dw = cell - 2 * gap
    dh = Hc - 2 * gap
    nh = 2 if dh <= 900 else (3 if dh <= 1600 else 4)
    for i in range(n):
        x0 = i * cell + gap
        zb = leg_h + gap
        door = _box(x0, x0 + dw, -(gap + door_t), -gap, zb, zb + dh)
        right = (i % 2 == 1)
        cx = (x0 + dw - p["hinge_edge"]) if right else (x0 + p["hinge_edge"])
        e = p["hinge_end"]
        cutters = []
        for h in range(nh):
            zc = zb + e + h * (dh - 2 * e) / (nh - 1)
            cutters.append(_cyl(p["hinge_d"] / 2.0, p["hinge_depth"],
                                cx, -gap - p["hinge_depth"], zc, (0, 1, 0)))
        add("door_%d" % (i + 1), _cut(door, cutters))

    # legs
    eg = p["leg_edge_gap"]
    r = p["leg_d"] / 2.0
    cxs0, cxs1 = eg + r, W - eg - r
    cys0, cys1 = eg + r, Dc - eg - r
    sx, sy = cxs1 - cxs0, cys1 - cys0
    nx = (math.ceil(sx / p["leg_max_spacing"] - 1e-9) + 1) if sx > 0 else 1
    ny = (math.ceil(sy / p["leg_max_spacing"] - 1e-9) + 1) if sy > 0 else 1
    nx, ny = max(nx, 2), max(ny, 2)
    idx = 1
    for iy in range(ny):
        y = cys0 + iy * sy / (ny - 1)
        for ix in range(nx):
            x = cxs0 + ix * sx / (nx - 1)
            add("leg_%d" % idx, _cyl(r, leg_h, x, y, 0, (0, 0, 1)))
            idx += 1

    return [(name, parts[name]) for name in order]
