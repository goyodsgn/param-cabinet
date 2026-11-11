import math
import cadquery as cq

PARAMS = {
    "W": 1500.0,
    "H": 850.0,
    "D": 600.0,
    "leg_h": 100.0,
    "back_mode": "onset",
    "t": 18.0,
    "back_t": 10.0,
    "divider_t": 18.0,
    "door_t": 22.0,
    "shelf_t": 30.0,
    "door_gap": 2.0,
    "door_max_w": 600.0,
    "n_doors": None,
    "n_shelves": None,
    "shelf_min_gap": 320.0,
    "pin_max_spacing": 500.0,
    "leg_max_spacing": 600.0,
    "notes": [],
}


def _box(x0, y0, z0, dx, dy, dz):
    return (cq.Workplane("XY")
            .box(dx, dy, dz, centered=False)
            .translate((x0, y0, z0)))


def _solid(wp):
    return wp.solids().val()


def _cyl(r, h, p, d):
    return cq.Solid.makeCylinder(r, h, cq.Vector(*p), cq.Vector(*d))


def build(params):
    W = params["W"]
    H = params["H"]
    D = params["D"]
    leg_h = params["leg_h"]
    back_mode = params["back_mode"]
    t = params["t"]
    back_t = params["back_t"]
    div_t = params["divider_t"]
    door_t = params["door_t"]
    shelf_t = params["shelf_t"]
    gap = params["door_gap"]
    door_max_w = params["door_max_w"]
    pin_max = params["pin_max_spacing"]
    leg_max = params["leg_max_spacing"]
    min_gap = params["shelf_min_gap"]

    parts = []

    Dc = D - door_t - gap
    z0 = leg_h
    ch = H - leg_h                      # carcass height
    inner_d = Dc - back_t               # depth to the back panel's inner face
    panel_d = inner_d if back_mode == "onset" else Dc

    # ---------- door count ----------
    n_auto = max(1, math.ceil(W / door_max_w - 1e-9))
    n = n_auto
    if params.get("n_doors") is not None:
        n = max(int(params["n_doors"]), n_auto)   # never fewer than automatic
    cell = W / n

    # ---------- vertical panels (sides + dividers) ----------
    clear_h = ch - 2 * t
    panels = {}
    panels["side_left"] = _box(0, 0, z0, t, panel_d, ch)
    panels["side_right"] = _box(W - t, 0, z0, t, panel_d, ch)
    for j in range(1, n):
        cx = j * cell
        panels["divider_%d" % j] = _box(cx - div_t / 2, 0, z0 + t,
                                        div_t, inner_d, clear_h)

    # bays: (xl, xr, left panel name, right panel name)
    bays = []
    for i in range(n):
        if i == 0:
            xl, ln = t, "side_left"
        else:
            xl, ln = i * cell + div_t / 2, "divider_%d" % i
        if i == n - 1:
            xr, rn = W - t, "side_right"
        else:
            xr, rn = (i + 1) * cell - div_t / 2, "divider_%d" % (i + 1)
        bays.append((xl, xr, ln, rn))

    # ---------- shelves ----------
    if params.get("n_shelves") is None:
        k = max(0, math.floor((clear_h - min_gap) / (min_gap + shelf_t)))
    else:
        k = max(0, int(params["n_shelves"]))
    space = (clear_h - k * shelf_t) / (k + 1) if k >= 0 else clear_h

    shelves = []   # (xl_bay, xr_bay, ln, rn, z_bottom)
    pins = []      # (x_start, y, z, length) along +x
    cuts = {name: [] for name in panels}
    shelf_depth = inner_d
    pin_d = 5.0
    pin_r = pin_d / 2
    span = max(shelf_depth - 2 * 50, 0)
    npins = math.ceil(span / pin_max - 1e-9) + 1
    pin_ys = [50 + span * m / (npins - 1) for m in range(npins)] if npins > 1 else [50]

    shelf_list = []
    for (xl, xr, ln, rn) in bays:
        for s in range(k):
            zb = z0 + t + space * (s + 1) + shelf_t * s
            shelf_list.append(_box(xl + 1, 0, zb, (xr - xl) - 2, shelf_depth, shelf_t))
            zc = zb - pin_r
            for y in pin_ys:
                # left panel: hole xl-8..xl, pin xl-8..xl+6
                cuts[ln].append(_cyl(pin_r, 8, (xl - 8, y, zc), (1, 0, 0)))
                pins.append(_cyl(pin_r, 14, (xl - 8, y, zc), (1, 0, 0)))
                # right panel: hole xr..xr+8, pin xr-6..xr+8
                cuts[rn].append(_cyl(pin_r, 8, (xr, y, zc), (1, 0, 0)))
                pins.append(_cyl(pin_r, 14, (xr - 6, y, zc), (1, 0, 0)))

    # ---------- emit carcass ----------
    def panel_solid(name):
        wp = panels[name]
        for c in cuts[name]:
            wp = wp.cut(cq.Workplane("XY").add(c))
        return _solid(wp)

    parts.append(("side_left", panel_solid("side_left")))
    parts.append(("side_right", panel_solid("side_right")))
    parts.append(("top", _solid(_box(t, 0, H - t, W - 2 * t, panel_d, t))))
    parts.append(("bottom", _solid(_box(t, 0, z0, W - 2 * t, panel_d, t))))
    if back_mode == "onset":
        parts.append(("back", _solid(_box(0, Dc - back_t, z0, W, back_t, ch))))
    else:
        parts.append(("back", _solid(_box(t, Dc - back_t, z0 + t,
                                          W - 2 * t, back_t, ch - 2 * t))))
    for j in range(1, n):
        parts.append(("divider_%d" % j, panel_solid("divider_%d" % j)))
    for i, s in enumerate(shelf_list):
        parts.append(("shelf_%d" % (i + 1), _solid(s)))
    for i, p in enumerate(pins):
        parts.append(("pin_%d" % (i + 1), p))

    # ---------- doors ----------
    dw = cell - 2 * gap
    dh = ch - 2 * gap
    if dh <= 900:
        nh = 2
    elif dh <= 1600:
        nh = 3
    else:
        nh = 4
    cup_zs = [100 + (dh - 200) * m / (nh - 1) for m in range(nh)]
    for i in range(n):
        x0 = i * cell + gap
        zb = z0 + gap
        yf = -(gap + door_t)
        door = _box(x0, yf, zb, dw, door_t, dh)
        hinge_left = (i % 2 == 0)
        if i == n - 1 and n > 1 and n % 2 == 1:
            hinge_left = False
        cx = x0 + 22.5 if hinge_left else x0 + dw - 22.5
        for cz in cup_zs:
            cup = _cyl(17.5, 12, (cx, -gap, zb + cz), (0, -1, 0))
            door = door.cut(cq.Workplane("XY").add(cup))
        parts.append(("door_%d" % (i + 1), _solid(door)))

    # ---------- legs ----------
    leg_r = 20.0
    off = 30 + leg_r
    xs_span = W - 2 * off
    ys_span = Dc - 2 * off
    nx = math.ceil(xs_span / leg_max - 1e-9) + 1
    ny = math.ceil(ys_span / leg_max - 1e-9) + 1
    xs = [off + xs_span * a / (nx - 1) for a in range(nx)] if nx > 1 else [W / 2]
    ys = [off + ys_span * b / (ny - 1) for b in range(ny)] if ny > 1 else [Dc / 2]
    idx = 1
    for y in ys:
        for x in xs:
            parts.append(("leg_%d" % idx, _cyl(leg_r, leg_h, (x, y, 0), (0, 0, 1))))
            idx += 1

    return parts
