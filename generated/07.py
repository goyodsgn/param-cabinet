import cadquery as cq
import math

PARAMS = {
    # overall size
    "W": 750.0,
    "H": 720.0,
    "D": 550.0,
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
    "pin_d": 5.0,
    "pin_len": 14.0,
    "pin_hole_depth": 8.0,
    "pin_out": 6.0,
    "pin_y_off": 50.0,
    "pin_below": 2.5,
    # legs
    "leg_d": 40.0,
    "leg_edge_gap": 30.0,
    "leg_max_spacing": 600.0,
}


def _box(x0, x1, y0, y1, z0, z1):
    return (cq.Workplane("XY")
            .box(x1 - x0, y1 - y0, z1 - z0, centered=False)
            .translate((x0, y0, z0))
            .solids().val())


def _cyl(r, h, p, d):
    return cq.Solid.makeCylinder(r, h, cq.Vector(*p), cq.Vector(*d))


def _cut(solid, tool):
    return cq.Workplane("XY").add(solid).cut(cq.Workplane("XY").add(tool)).solids().val()


def build(params):
    p = params
    W, H, D = p["W"], p["H"], p["D"]
    leg_h = p["leg_h"]
    t, back_t, div_t = p["t"], p["back_t"], p["divider_t"]
    door_t, shelf_t = p["door_t"], p["shelf_t"]
    gap = p["door_gap"]
    inset = (p["back_mode"] == "inset")

    Dc = D - door_t - gap
    Hc = H - leg_h
    z_bot = leg_h
    z_top = H
    body_d = Dc if inset else Dc - back_t     # depth of sides/top/bottom
    inner_d = Dc - back_t                     # depth of dividers/shelves
    clear_h = Hc - 2 * t

    parts = []  # (name, solid) in order, non-panel parts
    panels = {}  # name -> solid (vertical panels, may be cut by pin holes)
    panel_order = []

    # ---- carcass ----
    panels["side_left"] = _box(0, t, 0, body_d, z_bot, z_top)
    panels["side_right"] = _box(W - t, W, 0, body_d, z_bot, z_top)
    top = _box(t, W - t, 0, body_d, z_top - t, z_top)
    bottom = _box(t, W - t, 0, body_d, z_bot, z_bot + t)
    if inset:
        back = _box(t, W - t, Dc - back_t, Dc, z_bot + t, z_top - t)
    else:
        back = _box(0, W, Dc - back_t, Dc, z_bot, z_top)

    # ---- doors count ----
    n = max(1, math.ceil(W / p["door_max_w"]))
    cell = W / n

    # ---- dividers ----
    div_names = []
    for j in range(1, n):
        xc = j * cell
        name = f"divider_{j}"
        panels[name] = _box(xc - div_t / 2, xc + div_t / 2, 0, inner_d,
                            z_bot + t, z_top - t)
        div_names.append((name, xc - div_t / 2, xc + div_t / 2))

    # ---- bays ----
    vpanels = [("side_left", 0.0, t)] + div_names + [("side_right", W - t, W)]
    vpanels.sort(key=lambda v: v[1])
    bays = []
    for a, b in zip(vpanels[:-1], vpanels[1:]):
        bays.append((a[0], a[2], b[0], b[1]))  # left panel name, xl, right panel name, xr

    # ---- shelves and pins ----
    k = max(0, math.floor((clear_h - p["shelf_min_gap"]) / (p["shelf_min_gap"] + shelf_t)))
    space = (clear_h - k * shelf_t) / (k + 1)
    sc = p["shelf_clear"]
    pr = p["pin_d"] / 2.0
    hole_d = p["pin_hole_depth"]
    pin_out = p["pin_out"]
    pin_len = p["pin_len"]

    shelves = []
    pins = []
    cuts = {}
    for (lname, xl, rname, xr) in bays:
        for i in range(k):
            zb = z_bot + t + space * (i + 1) + shelf_t * i
            shelves.append(_box(xl + sc, xr - sc, 0, inner_d, zb, zb + shelf_t))
            zc = zb - p["pin_below"]
            for y in (p["pin_y_off"], inner_d - p["pin_y_off"]):
                # left panel pin: from xl - hole_d to xl + pin_out
                pins.append(_cyl(pr, pin_len, (xl - hole_d, y, zc), (1, 0, 0)))
                cuts.setdefault(lname, []).append(
                    _cyl(pr, hole_d, (xl - hole_d, y, zc), (1, 0, 0)))
                # right panel pin: from xr - pin_out to xr + hole_d
                pins.append(_cyl(pr, pin_len, (xr - pin_out, y, zc), (1, 0, 0)))
                cuts.setdefault(rname, []).append(
                    _cyl(pr, hole_d, (xr, y, zc), (1, 0, 0)))

    for name, tools in cuts.items():
        s = panels[name]
        for tool in tools:
            s = _cut(s, tool)
        panels[name] = s

    # ---- doors ----
    door_w = cell - 2 * gap
    door_h = Hc - 2 * gap
    door_z0 = leg_h + gap
    door_z1 = door_z0 + door_h
    if door_h <= p["hinge_h1"]:
        nh = 2
    elif door_h <= p["hinge_h2"]:
        nh = 3
    else:
        nh = 4
    cz0 = door_z0 + p["cup_end_offset"]
    cz1 = door_z1 - p["cup_end_offset"]
    cup_zs = [cz0 + (cz1 - cz0) * m / (nh - 1) for m in range(nh)]

    doors = []
    for i in range(n):
        x0 = i * cell + gap
        x1 = x0 + door_w
        d = _box(x0, x1, -(gap + door_t), -gap, door_z0, door_z1)
        hinge_left = (i % 2 == 0)
        if n > 1 and n % 2 == 1 and i == n - 1:
            hinge_left = False
        cx = x0 + p["cup_edge"] if hinge_left else x1 - p["cup_edge"]
        for cz in cup_zs:
            cup = _cyl(p["cup_d"] / 2.0, p["cup_depth"], (cx, -gap, cz), (0, -1, 0))
            d = _cut(d, cup)
        doors.append(d)

    # ---- legs ----
    r_leg = p["leg_d"] / 2.0
    off = p["leg_edge_gap"] + r_leg
    span_x = W - 2 * off
    span_y = Dc - 2 * off
    nx = math.ceil(span_x / p["leg_max_spacing"]) + 1
    ny = math.ceil(span_y / p["leg_max_spacing"]) + 1
    legs = []
    for ix in range(nx):
        x = off + span_x * ix / (nx - 1)
        for iy in range(ny):
            y = off + span_y * iy / (ny - 1)
            legs.append(_cyl(r_leg, leg_h, (x, y, 0), (0, 0, 1)))

    # ---- assemble ----
    out = []
    out.append(("side_left", panels["side_left"]))
    out.append(("side_right", panels["side_right"]))
    out.append(("top", top))
    out.append(("bottom", bottom))
    out.append(("back", back))
    for j in range(1, n):
        out.append((f"divider_{j}", panels[f"divider_{j}"]))
    for i, s in enumerate(shelves):
        out.append((f"shelf_{i + 1}", s))
    for i, s in enumerate(pins):
        out.append((f"pin_{i + 1}", s))
    for i, s in enumerate(doors):
        out.append((f"door_{i + 1}", s))
    for i, s in enumerate(legs):
        out.append((f"leg_{i + 1}", s))
    return out
