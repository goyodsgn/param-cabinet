import math
import cadquery as cq

# Customer gave INNER sizes: width 864, depth 536, height 678.
# W = 864 + 2*18 = 900
# H = 678 + leg_h(100) + 2*18 = 814
# Dc = 536 + back_t(10) = 546, D = Dc + door_t(22) + door_gap(2) = 570
# Update: the top panel now covers the sides (top_mode "onset").
PARAMS = {
    "W": 900,
    "H": 814,
    "D": 570,
    "leg_h": 100,
    "back_mode": "onset",
    "top_mode": "onset",
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
    "notes": [
        "Inner sizes converted: W = 864 + 2*18 = 900, H = 678 + 100 (legs) + 2*18 = 814, "
        "D = 536 + 10 (back) + 22 (door) + 2 (gap) = 570.",
        "Door count is automatic: ceil(900/600) = 2 doors, each 446 mm wide.",
        "Top panel covers the sides (onset): top is W wide, sides run from leg_h to H - t. "
        "The inner height stays 678 mm.",
    ],
}


def _solid(shape):
    if isinstance(shape, cq.Solid):
        return shape
    sols = shape.Solids()
    return sols[0] if len(sols) == 1 else cq.Solid(cq.Compound.makeCompound(sols).wrapped)


def _box(x0, x1, y0, y1, z0, z1):
    return cq.Workplane("XY").box(x1 - x0, y1 - y0, z1 - z0, centered=False).translate((x0, y0, z0))


def _cyl(r, h, p, d):
    return cq.Solid.makeCylinder(r, h, cq.Vector(*p), cq.Vector(*d))


def build(params):
    P = params
    W, H, D = P["W"], P["H"], P["D"]
    leg_h, t, back_t = P["leg_h"], P["t"], P["back_t"]
    divider_t, door_t, shelf_t = P["divider_t"], P["door_t"], P["shelf_t"]
    gap = P["door_gap"]
    top_mode, back_mode = P["top_mode"], P["back_mode"]
    Dc = D - door_t - gap
    has_top = top_mode != "none"
    side_d = Dc - back_t if back_mode == "onset" else Dc
    inner_d = Dc - back_t

    parts = []

    # ---------- door layout ----------
    layout = P["door_layout"]
    if layout:
        n = sum(layout)
    else:
        n = P["n_doors"] if P["n_doors"] else 1
        n = max(n, math.ceil(W / P["door_max_w"]), 1)
        layout = [1] * n
    cell = W / n

    # ---------- carcass ----------
    if top_mode == "onset":
        side_z1 = H - t
    else:
        side_z1 = H
    clear_h = H - leg_h - 2 * t if has_top else H - leg_h - t
    zb = leg_h + t  # top face of bottom panel

    panels = {}
    panels["side_left"] = _box(0, t, 0, side_d, leg_h, side_z1)
    panels["side_right"] = _box(W - t, W, 0, side_d, leg_h, side_z1)
    top_p = None
    if top_mode == "inset":
        top_p = _box(t, W - t, 0, side_d, H - t, H)
    elif top_mode == "onset":
        top_p = _box(0, W, 0, side_d, H - t, H)
    bottom_p = _box(t, W - t, 0, side_d, leg_h, leg_h + t)
    if back_mode == "onset":
        back_p = _box(0, W, Dc - back_t, Dc, leg_h, H)
    else:
        zt = H - t if has_top else H
        back_p = _box(t, W - t, Dc - back_t, Dc, leg_h + t, zt)

    # ---------- bays and dividers ----------
    bays = []  # (xl, xr, left_name, right_name)
    div_names = []
    cum = 0
    div_x = []
    for b, cnt in enumerate(layout):
        cum += cnt
        if b < len(layout) - 1:
            div_x.append(cum * cell)
    for k, xc in enumerate(div_x):
        name = "divider_%d" % (k + 1)
        panels[name] = _box(xc - divider_t / 2, xc + divider_t / 2, 0, inner_d, zb, zb + clear_h)
        div_names.append(name)
    for b in range(len(layout)):
        if b == 0:
            xl, ln = t, "side_left"
        else:
            xl, ln = div_x[b - 1] + divider_t / 2, div_names[b - 1]
        if b == len(layout) - 1:
            xr, rn = W - t, "side_right"
        else:
            xr, rn = div_x[b] - divider_t / 2, div_names[b]
        bays.append((xl, xr, ln, rn))

    # ---------- shelves ----------
    bcm = P["bottom_clear_min"]
    smin = P["shelf_min_gap"]
    if P["n_shelves"] is not None:
        k = max(0, int(P["n_shelves"]))
    elif bcm:
        k = max(0, int(math.floor((clear_h - max(bcm, smin)) / (smin + shelf_t))))
    else:
        k = max(0, int(math.floor((clear_h - smin) / (smin + shelf_t))))

    shelf_bottoms = []  # z of bottom face of each shelf
    if k > 0:
        g = (clear_h - k * shelf_t) / (k + 1)
        if bcm and P["n_shelves"] is None and g < bcm:
            first = zb + bcm
            shelf_bottoms.append(first)
            if k > 1:
                rem = clear_h - bcm - shelf_t
                g2 = (rem - (k - 1) * shelf_t) / k
                for i in range(1, k):
                    shelf_bottoms.append(first + shelf_t + i * g2 + (i - 1) * shelf_t)
        else:
            for i in range(1, k + 1):
                shelf_bottoms.append(zb + i * g + (i - 1) * shelf_t)

    # pins
    pin_r = 2.5
    span = inner_d - 2 * 50
    m = int(math.ceil(span / P["pin_max_spacing"])) + 1
    pin_ys = [50 + i * span / (m - 1) for i in range(m)] if m > 1 else [50]

    shelves = []
    pins = []
    holes = {}
    for (xl, xr, ln, rn) in bays:
        for zs in shelf_bottoms:
            shelves.append(_box(xl + 1, xr - 1, 0, inner_d, zs, zs + shelf_t))
            zc = zs - 2.5
            for y in pin_ys:
                # left panel: hole 8 deep into panel, pin sticks 6 out
                pins.append(_cyl(pin_r, 14, (xl - 8, y, zc), (1, 0, 0)))
                holes.setdefault(ln, []).append(_cyl(pin_r, 8, (xl - 8, y, zc), (1, 0, 0)))
                # right panel
                pins.append(_cyl(pin_r, 14, (xr + 8, y, zc), (-1, 0, 0)))
                holes.setdefault(rn, []).append(_cyl(pin_r, 8, (xr, y, zc), (1, 0, 0)))

    # ---------- output carcass parts ----------
    def cut_holes(name):
        wp = panels[name]
        for h in holes.get(name, []):
            wp = wp.cut(cq.Workplane(obj=h))
        return _solid(wp.val())

    parts.append(("side_left", cut_holes("side_left")))
    parts.append(("side_right", cut_holes("side_right")))
    if top_p is not None:
        parts.append(("top", _solid(top_p.val())))
    parts.append(("bottom", _solid(bottom_p.val())))
    parts.append(("back", _solid(back_p.val())))
    for name in div_names:
        parts.append((name, cut_holes(name)))
    for i, s in enumerate(shelves):
        parts.append(("shelf_%d" % (i + 1), _solid(s.val())))
    for i, p in enumerate(pins):
        parts.append(("pin_%d" % (i + 1), _solid(p)))

    # ---------- doors ----------
    hinges = []
    if all(c == 1 for c in layout):
        for i in range(n):
            hinges.append("L" if i % 2 == 0 else "R")
        if n > 1 and n % 2 == 1:
            hinges[-1] = "R"
    else:
        idx = 0
        for c in layout:
            if c == 2:
                hinges += ["L", "R"]
            else:
                center = (idx + 0.5) * cell
                hinges.append("L" if center <= W / 2 else "R")
            idx += c

    dw = cell - 2 * gap
    dh = (H - leg_h) - 2 * gap
    nh = 2 if dh <= 900 else (3 if dh <= 1600 else 4)
    for i in range(n):
        x0 = i * cell + gap
        z0 = leg_h + gap
        door = _box(x0, x0 + dw, -(gap + door_t), -gap, z0, z0 + dh)
        cx = x0 + 22.5 if hinges[i] == "L" else x0 + dw - 22.5
        for j in range(nh):
            zc = z0 + 100 + j * (dh - 200) / (nh - 1)
            cup = _cyl(17.5, 12, (cx, -gap, zc), (0, -1, 0))
            door = door.cut(cq.Workplane(obj=cup))
        parts.append(("door_%d" % (i + 1), _solid(door.val())))

    # ---------- legs ----------
    lx0, lx1 = 30 + 20, W - 30 - 20
    ly0, ly1 = 30 + 20, Dc - 30 - 20
    nx = int(math.ceil((lx1 - lx0) / P["leg_max_spacing"])) + 1
    ny = int(math.ceil((ly1 - ly0) / P["leg_max_spacing"])) + 1
    xs = [lx0 + i * (lx1 - lx0) / (nx - 1) for i in range(nx)]
    ys = [ly0 + j * (ly1 - ly0) / (ny - 1) for j in range(ny)]
    c = 1
    for y in ys:
        for x in xs:
            parts.append(("leg_%d" % c, _solid(_cyl(20, leg_h, (x, y, 0), (0, 0, 1)))))
            c += 1

    return parts
