import math
import cadquery as cq

PARAMS = {
    "W": 1500, "H": 850, "D": 600,
    "leg_h": 100,
    "back_mode": "onset",
    "top_mode": "inset",
    "t": 18, "back_t": 10, "divider_t": 18, "door_t": 22, "shelf_t": 30,
    "door_gap": 2, "door_max_w": 600,
    "n_doors": None,
    "door_layout": [1, 2],
    "single_door_hinge": None,
    "n_shelves": None,
    "shelf_min_gap": 320,
    "bottom_clear_min": None,
    "pin_max_spacing": 500,
    "leg_max_spacing": 600,
    "notes": ["한쪽문(1칸)은 왼쪽, 양문형(2칸)은 오른쪽으로 배치했습니다 (door_layout=[1,2], 문 3개, 칸당 500mm)."],
}


def _box(x0, x1, y0, y1, z0, z1):
    return cq.Workplane("XY").box(x1 - x0, y1 - y0, z1 - z0, centered=False).translate((x0, y0, z0))


def _cyl(r, h, p, d):
    return cq.Solid.makeCylinder(r, h, cq.Vector(*p), cq.Vector(*d))


def _solid(wp):
    return wp.solids().val()


def build(params):
    p = params
    W, H, D = p["W"], p["H"], p["D"]
    leg_h, t, back_t = p["leg_h"], p["t"], p["back_t"]
    div_t, door_t, shelf_t = p["divider_t"], p["door_t"], p["shelf_t"]
    gap = p["door_gap"]
    back_mode, top_mode = p["back_mode"], p["top_mode"]
    Dc = D - door_t - gap
    parts = []

    # ---- doors / bays
    layout = p["door_layout"]
    if layout:
        n = sum(layout)
        bays = layout
    else:
        n = p["n_doors"] or max(1, math.ceil(W / p["door_max_w"]))
        n = max(n, math.ceil(W / p["door_max_w"]))
        bays = [1] * n
    cell = W / n

    # ---- carcass extents
    has_top = top_mode != "none"
    z_bot = leg_h
    z_top = H
    if top_mode == "onset":
        side_top = H - t
    else:
        side_top = H
    inner_top = H - t if has_top else H  # top of clear space
    depth_box = Dc - back_t if back_mode == "onset" else Dc
    y_in = Dc - back_t  # inner face of back

    # ---- bay boundaries
    bounds = []  # wall centers
    j = 0
    for b in bays[:-1]:
        j += b
        bounds.append(j * cell)
    bay_x = []
    for i in range(len(bays)):
        x0 = t if i == 0 else bounds[i - 1] + div_t / 2
        x1 = W - t if i == len(bays) - 1 else bounds[i] - div_t / 2
        bay_x.append((x0, x1))

    # ---- shelves
    clear_h = inner_top - (leg_h + t)
    gmin = p["shelf_min_gap"]
    bcm = p["bottom_clear_min"]
    if p["n_shelves"] is not None:
        k = p["n_shelves"]
    elif bcm:
        k = max(0, int((clear_h - max(bcm, gmin)) // (gmin + shelf_t)))
    else:
        k = max(0, int((clear_h - gmin) // (gmin + shelf_t)))
    z0 = leg_h + t
    shelf_z = []  # bottom z of each shelf
    if k > 0:
        sp = (clear_h - k * shelf_t) / (k + 1)
        if bcm and p["n_shelves"] is None and sp < bcm:
            low = bcm
            sp2 = (clear_h - low - k * shelf_t) / k
            shelf_z = [z0 + low + i * (sp2 + shelf_t) for i in range(k)]
        else:
            shelf_z = [z0 + sp * (i + 1) + shelf_t * i for i in range(k)]

    # ---- pins
    shelf_depth = y_in
    span = shelf_depth - 100
    npin = math.ceil(span / p["pin_max_spacing"]) + 1
    pin_ys = [50 + span * i / (npin - 1) for i in range(npin)]
    holes = {}  # panel name -> list of cylinders
    pins = []
    for bi, (x0, x1) in enumerate(bay_x):
        lname = "side_left" if bi == 0 else "divider_%d" % bi
        rname = "side_right" if bi == len(bays) - 1 else "divider_%d" % (bi + 1)
        for zb in shelf_z:
            zc = zb - 2.5
            for y in pin_ys:
                pins.append(_cyl(2.5, 14, (x0 - 8, y, zc), (1, 0, 0)))
                holes.setdefault(lname, []).append(_cyl(2.5, 8, (x0 - 8, y, zc), (1, 0, 0)))
                pins.append(_cyl(2.5, 14, (x1 - 6, y, zc), (1, 0, 0)))
                holes.setdefault(rname, []).append(_cyl(2.5, 8, (x1, y, zc), (1, 0, 0)))

    def panel(name, wp):
        for h in holes.get(name, []):
            wp = wp.cut(h)
        parts.append((name, _solid(wp)))

    # ---- panels
    panel("side_left", _box(0, t, 0, depth_box, z_bot, side_top))
    panel("side_right", _box(W - t, W, 0, depth_box, z_bot, side_top))
    parts.append(("bottom", _solid(_box(t, W - t, 0, depth_box, z_bot, z_bot + t))))
    if top_mode == "inset":
        parts.append(("top", _solid(_box(t, W - t, 0, depth_box, H - t, H))))
    elif top_mode == "onset":
        parts.append(("top", _solid(_box(0, W, 0, depth_box, H - t, H))))
    if back_mode == "onset":
        parts.append(("back", _solid(_box(0, W, Dc - back_t, Dc, z_bot, H))))
    else:
        parts.append(("back", _solid(_box(t, W - t, Dc - back_t, Dc, z_bot + t, inner_top))))
    for i, xc in enumerate(bounds):
        panel("divider_%d" % (i + 1),
              _box(xc - div_t / 2, xc + div_t / 2, 0, y_in, leg_h + t, inner_top))

    # ---- shelves
    si = 1
    for (x0, x1) in bay_x:
        for zb in shelf_z:
            parts.append(("shelf_%d" % si, _solid(_box(x0 + 1, x1 - 1, 0, y_in, zb, zb + shelf_t))))
            si += 1
    for i, pn in enumerate(pins):
        parts.append(("pin_%d" % (i + 1), pn))

    # ---- hinge sides
    sides = []
    if p["single_door_hinge"]:
        sides = [p["single_door_hinge"]] * n
    elif not layout or all(b == 1 for b in layout):
        for i in range(n):
            sides.append("left" if i % 2 == 0 else "right")
        if n > 1 and n % 2 == 1:
            sides[-1] = "right"
    else:
        c = 0
        for b in bays:
            if b == 2:
                sides += ["left", "right"]
            else:
                cx = (c + 0.5) * cell
                sides.append("left" if cx <= W / 2 else "right")
            c += b

    # ---- doors
    dw = cell - 2 * gap
    dh = (H - leg_h) - 2 * gap
    nh = 2 if dh <= 900 else (3 if dh <= 1600 else 4)
    for i in range(n):
        xl = i * cell + gap
        zb = leg_h + gap
        d = _box(xl, xl + dw, -(gap + door_t), -gap, zb, zb + dh)
        cx = xl + 22.5 if sides[i] == "left" else xl + dw - 22.5
        for h in range(nh):
            zc = zb + 100 + (dh - 200) * h / (nh - 1)
            d = d.cut(_cyl(17.5, 12, (cx, -gap, zc), (0, -1, 0)))
        parts.append(("door_%d" % (i + 1), _solid(d)))

    # ---- legs
    lx0, lx1 = 50, W - 50
    ly0, ly1 = 50, Dc - 50
    nx = math.ceil((lx1 - lx0) / p["leg_max_spacing"]) + 1
    ny = math.ceil((ly1 - ly0) / p["leg_max_spacing"]) + 1
    li = 1
    for a in range(nx):
        for b in range(ny):
            x = lx0 + (lx1 - lx0) * a / (nx - 1)
            y = ly0 + (ly1 - ly0) * b / (ny - 1) if ny > 1 else ly0
            parts.append(("leg_%d" % li, cq.Solid.makeCylinder(20, leg_h, cq.Vector(x, y, 0), cq.Vector(0, 0, 1))))
            li += 1
    return parts
