import math
import cadquery as cq

PARAMS = {
    # overall size
    "W": 1100,
    "H": 870,
    "D": 580,
    "leg_h": 100,
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
    # hinge cups
    "cup_d": 35,
    "cup_depth": 12,
    "cup_edge": 22.5,
    "cup_end_offset": 100,
    "hinge_h_limit_2": 900,
    "hinge_h_limit_3": 1600,
    # shelves
    "shelf_min_gap": 320,
    "shelf_clearance": 1,
    # pins
    "pin_per_side": 2,
    "pin_edge": 50,
    "pin_d": 5,
    "pin_below": 2.5,
    "pin_hole_depth": 8,
    "pin_out": 6,
    # legs
    "leg_d": 40,
    "leg_corner_gap": 30,
    "leg_max_spacing": 600,
}


def _solid(shape):
    """Normalize a boolean result to a single cq.Solid."""
    if isinstance(shape, cq.Solid):
        return shape
    solids = shape.Solids()
    if len(solids) == 1:
        return solids[0]
    return cq.Compound.makeCompound(solids)


def _box(x0, x1, y0, y1, z0, z1):
    return cq.Solid.makeBox(x1 - x0, y1 - y0, z1 - z0, cq.Vector(x0, y0, z0))


def _cyl_x(r, x_start, length, y, z):
    return cq.Solid.makeCylinder(r, length, cq.Vector(x_start, y, z), cq.Vector(1, 0, 0))


def build(params: dict):
    p = params
    W, H, D = p["W"], p["H"], p["D"]
    leg_h = p["leg_h"]
    t, back_t, div_t = p["t"], p["back_t"], p["divider_t"]
    door_t, shelf_t = p["door_t"], p["shelf_t"]
    gap = p["door_gap"]
    inset = p["back_mode"] == "inset"

    Dc = D - door_t - gap
    Hc = H - leg_h
    z_bot = leg_h
    z_top = H
    inner_depth = Dc - back_t              # y of the back panel's inner face
    panel_d = Dc if inset else inner_depth  # depth of sides, top, bottom
    clear_h = Hc - 2 * t

    n = max(1, math.ceil(W / p["door_max_w"]))
    cell = W / n

    parts = []

    # ---------- vertical panels (x ranges) ----------
    vpanels = [{"name": "side_left", "x0": 0.0, "x1": float(t), "d": panel_d,
                "z0": z_bot, "z1": z_top}]
    for j in range(1, n):
        c = j * cell
        vpanels.append({"name": f"divider_{j}", "x0": c - div_t / 2, "x1": c + div_t / 2,
                        "d": inner_depth, "z0": z_bot + t, "z1": z_top - t})
    vpanels.append({"name": "side_right", "x0": float(W - t), "x1": float(W), "d": panel_d,
                    "z0": z_bot, "z1": z_top})
    holes = {vp["name"]: [] for vp in vpanels}

    # ---------- shelves and pins ----------
    k = max(0, math.floor((clear_h - p["shelf_min_gap"]) / (p["shelf_min_gap"] + shelf_t)))
    shelves, pins = [], []
    if k > 0:
        space = (clear_h - k * shelf_t) / (k + 1)
        pr = p["pin_d"] / 2
        hd = p["pin_hole_depth"]
        po = p["pin_out"]
        pin_len = hd + po
        shelf_d = inner_depth
        ys = []
        m = p["pin_per_side"]
        if m == 2:
            ys = [p["pin_edge"], shelf_d - p["pin_edge"]]
        else:
            ys = [p["pin_edge"]]
        for b in range(len(vpanels) - 1):
            lp, rp = vpanels[b], vpanels[b + 1]
            bl, br = lp["x1"], rp["x0"]
            sc = p["shelf_clearance"]
            for i in range(1, k + 1):
                zb = z_bot + t + i * space + (i - 1) * shelf_t
                shelves.append(_box(bl + sc, br - sc, 0, shelf_d, zb, zb + shelf_t))
                pz = zb - p["pin_below"]
                for y in ys:
                    # left panel of the bay (pin goes into its right face)
                    holes[lp["name"]].append(_cyl_x(pr, bl - hd, hd, y, pz))
                    pins.append(_cyl_x(pr, bl - hd, pin_len, y, pz))
                    # right panel of the bay (pin goes into its left face)
                    holes[rp["name"]].append(_cyl_x(pr, br, hd, y, pz))
                    pins.append(_cyl_x(pr, br - po, pin_len, y, pz))

    # ---------- carcass panels ----------
    for vp in vpanels:
        s = _box(vp["x0"], vp["x1"], 0, vp["d"], vp["z0"], vp["z1"])
        for h in holes[vp["name"]]:
            s = _solid(s.cut(h))
        parts.append((vp["name"], _solid(s)))
        if vp["name"] == "side_left":
            pass

    # order: sides first then dividers is not required, but keep names stable
    parts.append(("top", _box(t, W - t, 0, panel_d, z_top - t, z_top)))
    parts.append(("bottom", _box(t, W - t, 0, panel_d, z_bot, z_bot + t)))
    if inset:
        parts.append(("back", _box(t, W - t, Dc - back_t, Dc, z_bot + t, z_top - t)))
    else:
        parts.append(("back", _box(0, W, Dc - back_t, Dc, z_bot, z_top)))

    for i, s in enumerate(shelves, 1):
        parts.append((f"shelf_{i}", s))
    for i, s in enumerate(pins, 1):
        parts.append((f"pin_{i}", s))

    # ---------- doors ----------
    dw = cell - 2 * gap
    dh = Hc - 2 * gap
    if dh <= p["hinge_h_limit_2"]:
        nh = 2
    elif dh <= p["hinge_h_limit_3"]:
        nh = 3
    else:
        nh = 4
    cup_r = p["cup_d"] / 2
    for i in range(n):
        x0 = i * cell + gap
        z0 = leg_h + gap
        d = _box(x0, x0 + dw, -(gap + door_t), -gap, z0, z0 + dh)
        hinge_left = (i % 2 == 0)
        if n > 1 and n % 2 == 1 and i == n - 1:
            hinge_left = False
        cx = x0 + p["cup_edge"] if hinge_left else x0 + dw - p["cup_edge"]
        zs = z0 + p["cup_end_offset"]
        ze = z0 + dh - p["cup_end_offset"]
        for h in range(nh):
            cz = zs + h * (ze - zs) / (nh - 1)
            cup = cq.Solid.makeCylinder(cup_r, p["cup_depth"],
                                        cq.Vector(cx, -gap, cz), cq.Vector(0, -1, 0))
            d = _solid(d.cut(cup))
        parts.append((f"door_{i + 1}", _solid(d)))

    # ---------- legs ----------
    lr = p["leg_d"] / 2
    off = p["leg_corner_gap"] + lr
    spacing = p["leg_max_spacing"]
    span_x = W - 2 * off
    span_y = Dc - 2 * off
    nx = math.ceil(span_x / spacing) + 1
    ny = math.ceil(span_y / spacing) + 1
    idx = 1
    for a in range(nx):
        x = off + (span_x * a / (nx - 1) if nx > 1 else 0)
        for c in range(ny):
            y = off + (span_y * c / (ny - 1) if ny > 1 else 0)
            leg = cq.Solid.makeCylinder(lr, leg_h, cq.Vector(x, y, 0), cq.Vector(0, 0, 1))
            parts.append((f"leg_{idx}", leg))
            idx += 1

    return parts
