import math
import cadquery as cq

PARAMS = {
    # overall size
    "W": 900,
    "H": 820,
    "D": 600,
    "leg_h": 150,
    "back_mode": "onset",
    # panels
    "t": 18,
    "back_t": 10,
    "divider_t": 18,
    "door_t": 22,
    "shelf_t": 30,
    # doors
    "door_max_w": 600,
    "door_gap": 2,
    "hinge_d": 35,
    "hinge_depth": 12,
    "hinge_edge": 22.5,
    "hinge_end": 100,
    "hinge_h1": 900,
    "hinge_h2": 1600,
    # shelves
    "shelf_min_gap": 320,
    "shelf_side_clear": 1,
    # pins
    "pin_d": 5,
    "pin_below": 2.5,
    "pin_hole_depth": 8,
    "pin_out": 6,
    "pin_edge": 50,
    # legs
    "leg_d": 40,
    "leg_edge": 30,
    "leg_max_pitch": 600,
}


def _box(x0, x1, y0, y1, z0, z1):
    return cq.Solid.makeBox(x1 - x0, y1 - y0, z1 - z0, cq.Vector(x0, y0, z0))


def _cyl(d, length, origin, direction):
    return cq.Solid.makeCylinder(d / 2.0, length, cq.Vector(*origin), cq.Vector(*direction))


def _cut(solid, cutters):
    res = solid
    for c in cutters:
        res = res.cut(c)
    return res.Solids()[0]


def build(params):
    p = params
    W, H, D = p["W"], p["H"], p["D"]
    leg_h = p["leg_h"]
    t, back_t, dt = p["t"], p["back_t"], p["divider_t"]
    door_t, shelf_t = p["door_t"], p["shelf_t"]
    gap = p["door_gap"]
    inset = p["back_mode"] == "inset"

    Dc = D - door_t - gap
    ch = H - leg_h
    z0c, z1c = leg_h, H
    inner_depth = Dc - back_t
    side_depth = Dc if inset else inner_depth

    parts = []

    n = max(1, math.ceil(W / p["door_max_w"]))
    cell = W / n

    # ---- vertical panels: (name, x0, x1)
    panels = [("side_left", 0.0, t)]
    for j in range(1, n):
        c = j * cell
        panels.append(("divider_%d" % j, c - dt / 2.0, c + dt / 2.0))
    panels.append(("side_right", W - t, W))

    # ---- shelves / pins data
    clear_h = ch - 2 * t
    k = max(0, math.floor((clear_h - p["shelf_min_gap"]) / (p["shelf_min_gap"] + shelf_t)))
    sgap = (clear_h - k * shelf_t) / (k + 1)

    holes = [[] for _ in panels]
    shelves = []
    pins = []
    sc = p["shelf_side_clear"]
    pd = p["pin_d"]
    hd = p["pin_hole_depth"]
    pout = p["pin_out"]
    pin_len = hd + pout

    for b in range(len(panels) - 1):
        bay_l = panels[b][2]
        bay_r = panels[b + 1][1]
        sx0, sx1 = bay_l + sc, bay_r - sc
        for i in range(1, k + 1):
            zb = z0c + t + i * sgap + (i - 1) * shelf_t
            shelves.append(_box(sx0, sx1, 0, inner_depth, zb, zb + shelf_t))
            pz = zb - p["pin_below"]
            for py in (p["pin_edge"], inner_depth - p["pin_edge"]):
                # left panel of the bay (hole goes into panel, toward -x)
                holes[b].append(_cyl(pd, hd, (bay_l - hd, py, pz), (1, 0, 0)))
                pins.append(_cyl(pd, pin_len, (bay_l - hd, py, pz), (1, 0, 0)))
                # right panel of the bay (hole goes toward +x)
                holes[b + 1].append(_cyl(pd, hd, (bay_r, py, pz), (1, 0, 0)))
                pins.append(_cyl(pd, pin_len, (bay_r - pout, py, pz), (1, 0, 0)))

    # ---- sides
    for idx, (name, x0, x1) in enumerate(panels):
        if name.startswith("side"):
            s = _box(x0, x1, 0, side_depth, z0c, z1c)
            parts.append((name, _cut(s, holes[idx])))

    # ---- top, bottom
    parts.append(("top", _box(t, W - t, 0, side_depth, z1c - t, z1c)))
    parts.append(("bottom", _box(t, W - t, 0, side_depth, z0c, z0c + t)))

    # ---- back
    if inset:
        parts.append(("back", _box(t, W - t, Dc - back_t, Dc, z0c + t, z1c - t)))
    else:
        parts.append(("back", _box(0, W, Dc - back_t, Dc, z0c, z1c)))

    # ---- dividers
    for idx, (name, x0, x1) in enumerate(panels):
        if name.startswith("divider"):
            d = _box(x0, x1, 0, inner_depth, z0c + t, z1c - t)
            parts.append((name, _cut(d, holes[idx])))

    # ---- shelves, pins
    for i, s in enumerate(shelves, 1):
        parts.append(("shelf_%d" % i, s))
    for i, pn in enumerate(pins, 1):
        parts.append(("pin_%d" % i, pn))

    # ---- doors
    dw = cell - 2 * gap
    dh = ch - 2 * gap
    if dh <= p["hinge_h1"]:
        nh = 2
    elif dh <= p["hinge_h2"]:
        nh = 3
    else:
        nh = 4
    zb_door = leg_h + gap
    y_back = -gap
    y_front = -(gap + door_t)
    for i in range(n):
        x0 = i * cell + gap
        x1 = x0 + dw
        door = _box(x0, x1, y_front, y_back, zb_door, zb_door + dh)
        if n > 1 and n % 2 == 1 and i == n - 1:
            right = True
        else:
            right = (i % 2 == 1)
        cx = x1 - p["hinge_edge"] if right else x0 + p["hinge_edge"]
        z_first = zb_door + p["hinge_end"]
        z_last = zb_door + dh - p["hinge_end"]
        cups = []
        for m in range(nh):
            cz = z_first + m * (z_last - z_first) / (nh - 1)
            cups.append(_cyl(p["hinge_d"], p["hinge_depth"],
                             (cx, y_back, cz), (0, -1, 0)))
        parts.append(("door_%d" % (i + 1), _cut(door, cups)))

    # ---- legs
    le = p["leg_edge"]
    ld = p["leg_d"]
    r = ld / 2.0
    xa, xb = le + r, W - le - r
    ya, yb = le + r, Dc - le - r
    nx = math.ceil((xb - xa) / p["leg_max_pitch"]) + 1
    ny = math.ceil((yb - ya) / p["leg_max_pitch"]) + 1
    cnt = 1
    for ix in range(nx):
        x = xa + ix * (xb - xa) / (nx - 1)
        for iy in range(ny):
            y = ya + iy * (yb - ya) / (ny - 1)
            parts.append(("leg_%d" % cnt, _cyl(ld, leg_h, (x, y, 0), (0, 0, 1))))
            cnt += 1

    return parts


if __name__ == "__main__":
    result = build(PARAMS)
