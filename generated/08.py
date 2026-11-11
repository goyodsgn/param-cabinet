import math
import cadquery as cq

PARAMS = {
    "W": 1100,
    "H": 870,
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
    "notes": [],
    # additional rule values
    "hinge_d": 35,
    "hinge_depth": 12,
    "hinge_edge": 22.5,
    "hinge_end_margin": 100,
    "pin_d": 5,
    "pin_edge": 50,
    "pin_hole_depth": 8,
    "pin_out": 6,
    "shelf_clear": 1,
    "leg_d": 40,
    "leg_corner_gap": 30,
}


def _box(x0, y0, z0, dx, dy, dz):
    return cq.Workplane("XY").box(dx, dy, dz, centered=False).translate((x0, y0, z0)).val()


def _cyl(r, h, x, y, z, d):
    return cq.Solid.makeCylinder(r, h, cq.Vector(x, y, z), cq.Vector(*d))


def _cut(solid, cutters):
    if not cutters:
        return solid
    res = solid
    for c in cutters:
        res = res.cut(c)
    sols = res.Solids()
    return sols[0] if sols else solid


def build(params):
    p = params
    W, H, D = p["W"], p["H"], p["D"]
    leg_h = p["leg_h"]
    t, back_t, div_t = p["t"], p["back_t"], p["divider_t"]
    door_t, shelf_t, gap = p["door_t"], p["shelf_t"], p["door_gap"]
    Dc = D - door_t - gap
    Hc = H - leg_h
    inner_d = Dc - back_t  # depth up to the back panel's inner face
    carcass_d = inner_d if p["back_mode"] == "onset" else Dc

    # door count
    n = max(1, math.ceil(W / p["door_max_w"]))
    if p["n_doors"] is not None:
        n = max(n, int(p["n_doors"]))
    cell = W / n

    parts = {}
    cuts = {}

    # ---- carcass
    parts["side_left"] = _box(0, 0, leg_h, t, carcass_d, Hc)
    parts["side_right"] = _box(W - t, 0, leg_h, t, carcass_d, Hc)
    parts["top"] = _box(t, 0, H - t, W - 2 * t, carcass_d, t)
    parts["bottom"] = _box(t, 0, leg_h, W - 2 * t, carcass_d, t)
    if p["back_mode"] == "onset":
        parts["back"] = _box(0, Dc - back_t, leg_h, W, back_t, Hc)
    else:
        parts["back"] = _box(t, Dc - back_t, leg_h + t, W - 2 * t, back_t, Hc - 2 * t)

    # ---- dividers
    clear_h = Hc - 2 * t
    for j in range(1, n):
        cx = j * cell
        parts["divider_%d" % j] = _box(cx - div_t / 2, 0, leg_h + t, div_t, inner_d, clear_h)

    # ---- shelves and pins
    if p["n_shelves"] is None:
        k = max(0, math.floor((clear_h - p["shelf_min_gap"]) / (p["shelf_min_gap"] + shelf_t)))
    else:
        k = max(0, int(p["n_shelves"]))

    pr = p["pin_d"] / 2
    pin_len = p["pin_hole_depth"] + p["pin_out"]
    sc = p["shelf_clear"]
    pins = []
    shelf_list = []
    if k > 0:
        space = (clear_h - k * shelf_t) / (k + 1)
        for i in range(n):
            left = t if i == 0 else i * cell + div_t / 2
            right = (W - t) if i == n - 1 else (i + 1) * cell - div_t / 2
            lname = "side_left" if i == 0 else "divider_%d" % i
            rname = "side_right" if i == n - 1 else "divider_%d" % (i + 1)
            for s in range(k):
                zb = leg_h + t + space * (s + 1) + shelf_t * s
                shelf_list.append(_box(left + sc, 0, zb, (right - left) - 2 * sc, inner_d, shelf_t))
                span = inner_d - 2 * p["pin_edge"]
                m = math.ceil(span / p["pin_max_spacing"]) + 1
                zc = zb - p["pin_d"] / 2
                for q in range(m):
                    y = p["pin_edge"] + span * q / (m - 1) if m > 1 else inner_d / 2
                    # left panel of bay
                    pins.append(_cyl(pr, pin_len, left - p["pin_hole_depth"], y, zc, (1, 0, 0)))
                    cuts.setdefault(lname, []).append(
                        _cyl(pr, p["pin_hole_depth"], left - p["pin_hole_depth"], y, zc, (1, 0, 0)))
                    # right panel of bay
                    pins.append(_cyl(pr, pin_len, right - p["pin_out"], y, zc, (1, 0, 0)))
                    cuts.setdefault(rname, []).append(
                        _cyl(pr, p["pin_hole_depth"], right, y, zc, (1, 0, 0)))

    for name, cl in cuts.items():
        if name in parts:
            parts[name] = _cut(parts[name], cl)

    result = []
    for nm in ["side_left", "side_right", "top", "bottom", "back"]:
        result.append((nm, parts[nm]))
    for j in range(1, n):
        result.append(("divider_%d" % j, parts["divider_%d" % j]))
    for i, s in enumerate(shelf_list):
        result.append(("shelf_%d" % (i + 1), s))
    for i, pn in enumerate(pins):
        result.append(("pin_%d" % (i + 1), pn))

    # ---- doors
    dw = cell - 2 * gap
    dh = Hc - 2 * gap
    nh = 2 if dh <= 900 else (3 if dh <= 1600 else 4)
    hr = p["hinge_d"] / 2
    zb0 = leg_h + gap
    for i in range(n):
        x0 = i * cell + gap
        door = _box(x0, -(gap + door_t), zb0, dw, door_t, dh)
        hinge_left = (i % 2 == 0)
        if n > 1 and n % 2 == 1 and i == n - 1:
            hinge_left = False
        cxh = x0 + p["hinge_edge"] if hinge_left else x0 + dw - p["hinge_edge"]
        z_first = zb0 + p["hinge_end_margin"]
        z_last = zb0 + dh - p["hinge_end_margin"]
        cl = []
        for q in range(nh):
            zc = z_first + (z_last - z_first) * q / (nh - 1)
            cl.append(_cyl(hr, p["hinge_depth"], cxh, -gap, zc, (0, -1, 0)))
        door = _cut(door, cl)
        result.append(("door_%d" % (i + 1), door))

    # ---- legs
    lr = p["leg_d"] / 2
    off = p["leg_corner_gap"] + lr
    spanx = W - 2 * off
    spany = Dc - 2 * off
    nx = math.ceil(spanx / p["leg_max_spacing"]) + 1
    ny = math.ceil(spany / p["leg_max_spacing"]) + 1
    idx = 1
    for a in range(nx):
        x = off + spanx * a / (nx - 1)
        for b in range(ny):
            y = off + spany * b / (ny - 1)
            result.append(("leg_%d" % idx, _cyl(lr, leg_h, x, y, 0, (0, 0, 1))))
            idx += 1

    return result
