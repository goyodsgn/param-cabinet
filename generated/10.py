import math
import cadquery as cq

PARAMS = {
    # overall size
    "W": 1200.0,
    "H": 1650.0,
    "D": 500.0,
    "leg_h": 80.0,
    "back_mode": "onset",
    # panels
    "t": 18.0,
    "back_t": 10.0,
    "divider_t": 18.0,
    "door_t": 22.0,
    "shelf_t": 30.0,
    # doors
    "door_max_w": 600.0,
    "door_gap": 2.0,
    # hinges
    "hinge_d": 35.0,
    "hinge_depth": 12.0,
    "hinge_edge": 22.5,
    "hinge_end": 100.0,
    "hinge_h1": 900.0,
    "hinge_h2": 1600.0,
    # shelves
    "shelf_min_gap": 320.0,
    "shelf_clear": 1.0,
    # pins
    "pin_d": 5.0,
    "pin_inset": 50.0,
    "pin_hole_depth": 8.0,
    "pin_out": 6.0,
    # legs
    "leg_d": 40.0,
    "leg_corner_gap": 30.0,
    "leg_max_spacing": 600.0,
}


def _ceil(x):
    return int(math.ceil(round(x, 9)))


def _floor(x):
    return int(math.floor(round(x, 9)))


def _box(x0, x1, y0, y1, z0, z1):
    return (cq.Workplane("XY")
            .box(x1 - x0, y1 - y0, z1 - z0, centered=False)
            .translate((x0, y0, z0)))


def _cyl(r, h, p, d):
    return cq.Solid.makeCylinder(r, h, cq.Vector(*p), cq.Vector(*d))


def _solid(wp):
    return wp.solids().vals()[0]


def build(params):
    p = params
    W, H, D = p["W"], p["H"], p["D"]
    leg_h = p["leg_h"]
    t, back_t, div_t = p["t"], p["back_t"], p["divider_t"]
    door_t, shelf_t = p["door_t"], p["shelf_t"]
    g = p["door_gap"]
    mode = p["back_mode"]

    Dc = D - door_t - g
    z0 = leg_h
    z1 = H
    Hc = H - leg_h
    inner_d = Dc - back_t                      # depth of inner parts
    ds = inner_d if mode == "onset" else Dc    # depth of sides/top/bottom

    n = max(1, _ceil(W / p["door_max_w"]))
    cell = W / n

    parts = []

    # ---------- carcass ----------
    side_l = _box(0, t, 0, ds, z0, z1)
    side_r = _box(W - t, W, 0, ds, z0, z1)
    top = _box(t, W - t, 0, ds, z1 - t, z1)
    bottom = _box(t, W - t, 0, ds, z0, z0 + t)

    if mode == "onset":
        back = _box(0, W, Dc - back_t, Dc, z0, z1)
    else:
        back = _box(t, W - t, Dc - back_t, Dc, z0 + t, z1 - t)

    # ---------- inner dividers ----------
    dividers = []
    for j in range(1, n):
        xc = j * cell
        dividers.append(_box(xc - div_t / 2, xc + div_t / 2, 0, inner_d,
                             z0 + t, z1 - t))

    # ---------- bays ----------
    # vertical panel names and their inner/outer faces
    # bay i: left face x, right face x, left panel name, right panel name
    bays = []
    left_x = t
    left_name = "side_left"
    for j in range(1, n):
        xc = j * cell
        bays.append((left_x, xc - div_t / 2, left_name, "divider_%d" % j))
        left_x = xc + div_t / 2
        left_name = "divider_%d" % j
    bays.append((left_x, W - t, left_name, "side_right"))

    # ---------- shelves ----------
    clear_h = Hc - 2 * t
    k = max(0, _floor((clear_h - p["shelf_min_gap"]) /
                      (p["shelf_min_gap"] + shelf_t)))
    gap = (clear_h - k * shelf_t) / (k + 1)

    shelves = []
    pins = []
    holes = {}  # panel name -> list of (xa, xb, y, z)
    r_pin = p["pin_d"] / 2
    hd = p["pin_hole_depth"]
    po = p["pin_out"]
    sc = p["shelf_clear"]
    pin_y = [p["pin_inset"], inner_d - p["pin_inset"]]

    for (bx0, bx1, ln, rn) in bays:
        for i in range(1, k + 1):
            zb = z0 + t + i * gap + (i - 1) * shelf_t
            shelves.append(_box(bx0 + sc, bx1 - sc, 0, inner_d, zb, zb + shelf_t))
            zp = zb - p["pin_d"] / 2
            for y in pin_y:
                # left pin: in left panel, sticking into bay
                pins.append((bx0 - hd, bx0 + po, y, zp))
                holes.setdefault(ln, []).append((bx0 - hd, bx0, y, zp))
                # right pin
                pins.append((bx1 - po, bx1 + hd, y, zp))
                holes.setdefault(rn, []).append((bx1, bx1 + hd, y, zp))

    def drill(wp, name):
        for (xa, xb, y, z) in holes.get(name, []):
            # hole depth is 8 into the panel; pin is cut region from panel face
            if name == "side_left" or xb <= xa:
                pass
            wp = wp.cut(_cyl(r_pin, hd, (xa, y, z), (1, 0, 0)))
        return wp

    parts.append(("side_left", _solid(drill(side_l, "side_left"))))
    parts.append(("side_right", _solid(drill(side_r, "side_right"))))
    parts.append(("top", _solid(top)))
    parts.append(("bottom", _solid(bottom)))
    parts.append(("back", _solid(back)))

    for j, d in enumerate(dividers, start=1):
        parts.append(("divider_%d" % j, _solid(drill(d, "divider_%d" % j))))

    for i, s in enumerate(shelves, start=1):
        parts.append(("shelf_%d" % i, _solid(s)))

    for i, (xa, xb, y, z) in enumerate(pins, start=1):
        parts.append(("pin_%d" % i,
                      _cyl(r_pin, xb - xa, (xa, y, z), (1, 0, 0))))

    # ---------- doors ----------
    dw = cell - 2 * g
    dh = Hc - 2 * g
    if dh <= p["hinge_h1"]:
        nh = 2
    elif dh <= p["hinge_h2"]:
        nh = 3
    else:
        nh = 4
    zb_d = z0 + g
    zt_d = zb_d + dh
    zc0 = zb_d + p["hinge_end"]
    zc1 = zt_d - p["hinge_end"]
    cup_zs = [zc0 + (zc1 - zc0) * m / (nh - 1) for m in range(nh)]

    for i in range(n):
        x0 = i * cell + g
        hinge_left = (i % 2 == 0)
        if n > 1 and n % 2 == 1 and i == n - 1:
            hinge_left = False
        door = _box(x0, x0 + dw, -(g + door_t), -g, zb_d, zt_d)
        cx = x0 + p["hinge_edge"] if hinge_left else x0 + dw - p["hinge_edge"]
        for cz in cup_zs:
            door = door.cut(_cyl(p["hinge_d"] / 2, p["hinge_depth"],
                                 (cx, -g - p["hinge_depth"], cz), (0, 1, 0)))
        parts.append(("door_%d" % (i + 1), _solid(door)))

    # ---------- legs ----------
    lr = p["leg_d"] / 2
    off = p["leg_corner_gap"] + lr
    xs0, xs1 = off, W - off
    ys0, ys1 = off, Dc - off
    nx = _ceil((xs1 - xs0) / p["leg_max_spacing"]) + 1
    ny = _ceil((ys1 - ys0) / p["leg_max_spacing"]) + 1
    idx = 1
    for a in range(nx):
        x = xs0 + (xs1 - xs0) * a / (nx - 1) if nx > 1 else xs0
        for b in range(ny):
            y = ys0 + (ys1 - ys0) * b / (ny - 1) if ny > 1 else ys0
            parts.append(("leg_%d" % idx,
                          _cyl(lr, leg_h, (x, y, 0), (0, 0, 1))))
            idx += 1

    return parts
