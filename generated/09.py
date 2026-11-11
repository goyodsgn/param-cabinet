import math
import cadquery as cq

PARAMS = {
    # overall size
    "W": 3000.0,
    "H": 850.0,
    "D": 600.0,
    "leg_h": 100.0,
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
    # hinge cups
    "cup_d": 35.0,
    "cup_depth": 12.0,
    "cup_edge": 22.5,
    "cup_end_offset": 100.0,
    "hinge_h1": 900.0,
    "hinge_h2": 1600.0,
    # shelves
    "shelf_min_gap": 320.0,
    "shelf_clear": 1.0,
    # pins
    "pin_per_side": 2,
    "pin_edge": 50.0,
    "pin_d": 5.0,
    "pin_below": 2.5,
    "pin_hole_depth": 8.0,
    "pin_out": 6.0,
    # legs
    "leg_d": 40.0,
    "leg_edge_gap": 30.0,
    "leg_max_pitch": 600.0,
}


def _box(x0, y0, z0, dx, dy, dz):
    return (cq.Workplane("XY")
            .box(dx, dy, dz, centered=False)
            .translate((x0, y0, z0)))


def _cyl_x(x0, y, z, d, length):
    return (cq.Workplane("YZ").center(y, z).circle(d / 2.0)
            .extrude(length).translate((x0, 0, 0)))


def _solid(wp):
    v = wp.val()
    if isinstance(v, cq.Solid):
        return v
    solids = v.Solids()
    if len(solids) == 1:
        return solids[0]
    return max(solids, key=lambda s: s.Volume())


def build(params):
    p = params
    W, H, D = p["W"], p["H"], p["D"]
    leg_h = p["leg_h"]
    t, back_t = p["t"], p["back_t"]
    div_t, door_t, shelf_t = p["divider_t"], p["door_t"], p["shelf_t"]
    gap = p["door_gap"]
    inset = (p["back_mode"] == "inset")

    Dc = D - door_t - gap
    Hc = H - leg_h
    z0, z1 = leg_h, H
    inner_d = Dc - back_t
    side_d = Dc if inset else inner_d

    parts = []

    # ---------------- carcass ----------------
    side_l = _box(0, 0, z0, t, side_d, Hc)
    side_r = _box(W - t, 0, z0, t, side_d, Hc)
    top = _box(t, 0, z1 - t, W - 2 * t, side_d, t)
    bottom = _box(t, 0, z0, W - 2 * t, side_d, t)
    if inset:
        back = _box(t, Dc - back_t, z0 + t, W - 2 * t, back_t, Hc - 2 * t)
    else:
        back = _box(0, Dc - back_t, z0, W, back_t, Hc)

    # ---------------- doors count ----------------
    n = max(1, math.ceil(W / p["door_max_w"]))
    cell = W / n

    # ---------------- vertical panels (for bays) ----------------
    clear_h = Hc - 2 * t
    vpanels = [{"name": "side_left", "x0": 0.0, "x1": t, "solid": side_l,
                "z0": z0, "z1": z1}]
    for j in range(1, n):
        xc = j * cell
        vpanels.append({"name": "divider_%d" % j, "x0": xc - div_t / 2.0,
                        "x1": xc + div_t / 2.0,
                        "solid": _box(xc - div_t / 2.0, 0, z0 + t, div_t, inner_d, clear_h),
                        "z0": z0 + t, "z1": z1 - t})
    vpanels.append({"name": "side_right", "x0": W - t, "x1": W, "solid": side_r,
                    "z0": z0, "z1": z1})

    # ---------------- shelves & pins ----------------
    k = max(0, int(math.floor((clear_h - p["shelf_min_gap"]) /
                              (p["shelf_min_gap"] + shelf_t))))
    shelves = []
    pins = []
    holes = {i: [] for i in range(len(vpanels))}
    pin_d = p["pin_d"]
    hd = p["pin_hole_depth"]
    pout = p["pin_out"]
    plen = hd + pout
    sc = p["shelf_clear"]
    if k > 0:
        space = (clear_h - k * shelf_t) / (k + 1)
        for b in range(len(vpanels) - 1):
            xl = vpanels[b]["x1"]
            xr = vpanels[b + 1]["x0"]
            bay_w = xr - xl
            sw = bay_w - 2 * sc
            for i in range(1, k + 1):
                zb = z0 + t + i * space + (i - 1) * shelf_t
                shelves.append(_box(xl + sc, 0, zb, sw, inner_d, shelf_t))
                pz = zb - p["pin_below"]
                ys = [p["pin_edge"], inner_d - p["pin_edge"]]
                for y in ys:
                    # left panel (panel b), right face at xl
                    pins.append(_cyl_x(xl - hd, y, pz, pin_d, plen))
                    holes[b].append(_cyl_x(xl - hd, y, pz, pin_d, hd))
                    # right panel (panel b+1), left face at xr
                    pins.append(_cyl_x(xr - pout, y, pz, pin_d, plen))
                    holes[b + 1].append(_cyl_x(xr, y, pz, pin_d, hd))

    # ---------------- emit carcass parts ----------------
    def vp_solid(i):
        wp = cq.Workplane("XY").add(vpanels[i]["solid"]) if isinstance(
            vpanels[i]["solid"], cq.Solid) else vpanels[i]["solid"]
        for h in holes[i]:
            wp = wp.cut(h)
        return _solid(wp)

    parts.append(("side_left", vp_solid(0)))
    parts.append(("side_right", vp_solid(len(vpanels) - 1)))
    parts.append(("top", _solid(top)))
    parts.append(("bottom", _solid(bottom)))
    parts.append(("back", _solid(back)))
    for j in range(1, n):
        parts.append(("divider_%d" % j, vp_solid(j)))
    for i, s in enumerate(shelves):
        parts.append(("shelf_%d" % (i + 1), _solid(s)))
    for i, s in enumerate(pins):
        parts.append(("pin_%d" % (i + 1), _solid(s)))

    # ---------------- doors ----------------
    dw = cell - 2 * gap
    dh = Hc - 2 * gap
    if dh <= p["hinge_h1"]:
        nh = 2
    elif dh <= p["hinge_h2"]:
        nh = 3
    else:
        nh = 4
    d_bottom = leg_h + gap
    d_top = d_bottom + dh
    zs_first = d_bottom + p["cup_end_offset"]
    zs_last = d_top - p["cup_end_offset"]
    cup_zs = [zs_first + (zs_last - zs_first) * m / (nh - 1) for m in range(nh)]

    for i in range(n):
        dx0 = i * cell + gap
        door = _box(dx0, -(gap + door_t), d_bottom, dw, door_t, dh)
        if n > 1 and n % 2 == 1 and i == n - 1:
            right = True
        else:
            right = (i % 2 == 1)
        if right:
            cx = dx0 + dw - p["cup_edge"]
        else:
            cx = dx0 + p["cup_edge"]
        for cz in cup_zs:
            cup = (cq.Workplane("XZ").center(cx, cz).circle(p["cup_d"] / 2.0)
                   .extrude(p["cup_depth"]).translate((0, -gap, 0)))
            door = door.cut(cup)
        parts.append(("door_%d" % (i + 1), _solid(door)))

    # ---------------- legs ----------------
    if leg_h > 0:
        off = p["leg_edge_gap"] + p["leg_d"] / 2.0
        x_a, x_b = off, W - off
        y_a, y_b = off, Dc - off
        span_x = max(0.0, x_b - x_a)
        span_y = max(0.0, y_b - y_a)
        nx = math.ceil(span_x / p["leg_max_pitch"]) + 1
        ny = math.ceil(span_y / p["leg_max_pitch"]) + 1
        xs = [x_a + span_x * i / (nx - 1) for i in range(nx)]
        ys = [y_a + span_y * j / (ny - 1) for j in range(ny)]
        idx = 1
        for yy in ys:
            for xx in xs:
                leg = (cq.Workplane("XY").circle(p["leg_d"] / 2.0)
                       .extrude(leg_h).translate((xx, yy, 0)))
                parts.append(("leg_%d" % idx, _solid(leg)))
                idx += 1

    return parts
