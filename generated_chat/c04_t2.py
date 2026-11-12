import math
import cadquery as cq

PARAMS = {
    "W": 1200,
    "H": 1200,
    "D": 450,
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
    # Lowest space: encyclopedias (~300-350 tall) and old photo albums (~350-380 tall)
    "bottom_clear_min": 400,
    "pin_max_spacing": 500,
    "leg_max_spacing": 600,
    "notes": [
        "Lowest shelf space is kept at least 400 mm high so encyclopedias (about 300-350 mm) and old photo albums (about 350-380 mm) fit.",
        "Width 1200 needs 2 doors: each door cell is exactly 600 mm, which is the maximum allowed, so there is one inner wall at the center.",
        "With these sizes the model gets 1 shelf per bay, which leaves a lowest space of about 517 mm.",
    ],
    # extra values used by the model
    "hinge_d": 35,
    "hinge_depth": 12,
    "hinge_edge": 22.5,
    "hinge_end": 100,
    "pin_d": 5,
    "pin_hole_depth": 8,
    "pin_out": 6,
    "pin_edge": 50,
    "shelf_clear": 1,
    "leg_d": 40,
    "leg_edge_gap": 30,
}


def _solid(shape):
    if isinstance(shape, cq.Solid):
        return shape
    sols = shape.Solids()
    return sols[0]


def _box(x0, y0, z0, dx, dy, dz):
    return cq.Solid.makeBox(dx, dy, dz, pnt=cq.Vector(x0, y0, z0))


def _cyl(r, h, x, y, z, d):
    return cq.Solid.makeCylinder(r, h, cq.Vector(x, y, z), cq.Vector(*d))


def build(params):
    p = params
    W, H, D = p["W"], p["H"], p["D"]
    leg_h = p["leg_h"]
    t, back_t, div_t = p["t"], p["back_t"], p["divider_t"]
    door_t, shelf_t, gap = p["door_t"], p["shelf_t"], p["door_gap"]
    back_mode, top_mode = p["back_mode"], p["top_mode"]
    Dc = D - door_t - gap
    has_top = top_mode != "none"

    parts = []

    # ---------------- carcass ----------------
    carc_depth = Dc if back_mode == "inset" else Dc - back_t
    inner_depth = Dc - back_t
    side_z0 = leg_h
    side_z1 = H - t if top_mode == "onset" else H
    z_bot_top = leg_h + t                      # top face of bottom panel
    z_top_bot = H - t if has_top else H        # underside of top panel / carcass top
    clear_h = z_top_bot - z_bot_top

    # ---------------- doors / bays ----------------
    n_min = max(1, math.ceil(round(W / p["door_max_w"], 9)))
    layout = p.get("door_layout")
    if layout:
        n = sum(layout)
        if n < n_min:
            layout = None
    if layout:
        n = sum(layout)
    else:
        n = n_min
        if p.get("n_doors"):
            n = max(n, int(p["n_doors"]))
        layout = [1] * n
    cw = W / n

    bays = []
    c = 0
    for cnt in layout:
        bays.append((c, cnt))
        c += cnt

    # panel x-extent of each bay (inner faces of the vertical panels)
    bay_x = []
    for bi, (c0, cnt) in enumerate(bays):
        xl = t if bi == 0 else c0 * cw + div_t / 2
        xr = W - t if bi == len(bays) - 1 else (c0 + cnt) * cw - div_t / 2
        bay_x.append((xl, xr))

    # ---------------- shelves layout (z positions) ----------------
    bcm = p.get("bottom_clear_min")
    if p.get("n_shelves") is not None:
        k = max(0, int(p["n_shelves"]))
    else:
        low = max(bcm, p["shelf_min_gap"]) if bcm else p["shelf_min_gap"]
        k = max(0, math.floor((clear_h - low) / (p["shelf_min_gap"] + shelf_t)))
    shelf_z = []
    if k > 0:
        s_even = (clear_h - k * shelf_t) / (k + 1)
        if bcm and s_even < bcm:
            sp = (clear_h - bcm - k * shelf_t) / k
            zb = z_bot_top + bcm
            for i in range(k):
                shelf_z.append(zb)
                zb += shelf_t + sp
        else:
            for i in range(k):
                shelf_z.append(z_bot_top + s_even * (i + 1) + shelf_t * i)

    # ---------------- pins layout ----------------
    pin_edge = p["pin_edge"]
    span = inner_depth - 2 * pin_edge
    n_p = math.ceil(round(span / p["pin_max_spacing"], 9)) + 1
    pin_ys = [pin_edge + span * j / (n_p - 1) for j in range(n_p)]
    pr = p["pin_d"] / 2
    hd = p["pin_hole_depth"]
    po = p["pin_out"]
    plen = hd + po

    # holes per panel: list of (x_start, y, z) for cylinders of hole depth along +x
    holes = {"side_left": [], "side_right": []}
    for i in range(1, len(bays)):
        holes["divider_%d" % i] = []

    pins = []
    for bi, (xl, xr) in enumerate(bay_x):
        left_name = "side_left" if bi == 0 else "divider_%d" % bi
        right_name = "side_right" if bi == len(bays) - 1 else "divider_%d" % (bi + 1)
        for zb in shelf_z:
            zc = zb - pr
            for y in pin_ys:
                # pin on left panel of the bay
                holes[left_name].append((xl - hd, y, zc))
                pins.append(_cyl(pr, plen, xl - hd, y, zc, (1, 0, 0)))
                # pin on right panel of the bay
                holes[right_name].append((xr, y, zc))
                pins.append(_cyl(pr, plen, xr - po, y, zc, (1, 0, 0)))

    def drill(solid, name):
        for (hx, hy, hz) in holes.get(name, []):
            solid = _solid(solid.cut(_cyl(pr, hd, hx, hy, hz, (1, 0, 0))))
        return solid

    # side panels
    sl = _box(0, 0, side_z0, t, carc_depth, side_z1 - side_z0)
    sr = _box(W - t, 0, side_z0, t, carc_depth, side_z1 - side_z0)
    parts.append(("side_left", drill(sl, "side_left")))
    parts.append(("side_right", drill(sr, "side_right")))

    # top
    if top_mode == "inset":
        parts.append(("top", _box(t, 0, H - t, W - 2 * t, carc_depth, t)))
    elif top_mode == "onset":
        parts.append(("top", _box(0, 0, H - t, W, carc_depth, t)))

    # bottom
    parts.append(("bottom", _box(t, 0, leg_h, W - 2 * t, carc_depth, t)))

    # back
    if back_mode == "inset":
        parts.append(("back", _box(t, Dc - back_t, z_bot_top, W - 2 * t, back_t, clear_h)))
    else:
        parts.append(("back", _box(0, Dc - back_t, leg_h, W, back_t, H - leg_h)))

    # dividers
    for i in range(1, len(bays)):
        xc = bays[i][0] * cw
        d = _box(xc - div_t / 2, 0, z_bot_top, div_t, inner_depth, clear_h)
        parts.append(("divider_%d" % i, drill(d, "divider_%d" % i)))

    # shelves
    idx = 1
    cl = p["shelf_clear"]
    for (xl, xr) in bay_x:
        for zb in shelf_z:
            parts.append(("shelf_%d" % idx,
                          _box(xl + cl, 0, zb, (xr - xl) - 2 * cl, inner_depth, shelf_t)))
            idx += 1

    # pins
    for i, pn in enumerate(pins, 1):
        parts.append(("pin_%d" % i, pn))

    # ---------------- doors ----------------
    # hinge sides
    has_pair = any(cnt == 2 for _, cnt in bays)
    hinge = []
    if has_pair:
        for (c0, cnt) in bays:
            if cnt == 2:
                hinge += ["L", "R"]
            else:
                cx = (c0 + 0.5) * cw
                hinge.append("L" if cx <= W / 2 else "R")
    else:
        for i in range(n):
            hinge.append("L" if i % 2 == 0 else "R")
        if n > 1 and n % 2 == 1:
            hinge[-1] = "R"

    door_w = cw - 2 * gap
    door_h = (H - leg_h) - 2 * gap
    if door_h <= 900:
        n_h = 2
    elif door_h <= 1600:
        n_h = 3
    else:
        n_h = 4
    cup_r = p["hinge_d"] / 2
    cup_d = p["hinge_depth"]
    he = p["hinge_end"]
    z_door0 = leg_h + gap
    cup_zs = [z_door0 + he + (door_h - 2 * he) * j / (n_h - 1) for j in range(n_h)]

    for i in range(n):
        x0 = i * cw + gap
        door = _box(x0, -(gap + door_t), z_door0, door_w, door_t, door_h)
        cx = x0 + p["hinge_edge"] if hinge[i] == "L" else x0 + door_w - p["hinge_edge"]
        for cz in cup_zs:
            door = _solid(door.cut(_cyl(cup_r, cup_d, cx, -gap - cup_d, cz, (0, 1, 0))))
        parts.append(("door_%d" % (i + 1), door))

    # ---------------- legs ----------------
    lr = p["leg_d"] / 2
    off = p["leg_edge_gap"] + lr
    span_x = W - 2 * off
    span_y = Dc - 2 * off
    nx = math.ceil(round(span_x / p["leg_max_spacing"], 9)) + 1
    ny = math.ceil(round(span_y / p["leg_max_spacing"], 9)) + 1
    li = 1
    for ix in range(nx):
        x = off + span_x * ix / (nx - 1)
        for iy in range(ny):
            y = off + span_y * iy / (ny - 1)
            parts.append(("leg_%d" % li, _cyl(lr, leg_h, x, y, 0, (0, 0, 1))))
            li += 1

    return parts
