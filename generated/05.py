import math
import cadquery as cq

PARAMS = {
    # overall size (customer)
    "W": 1800,
    "H": 1000,
    "D": 650,
    # company defaults
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
    # additional rule values
    "shelf_clearance": 1,
    "pin_edge": 50,
    "pin_d": 5,
    "pin_len": 14,
    "pin_hole_depth": 8,
    "pin_drop": 2.5,
    "hinge_cup_d": 35,
    "hinge_cup_depth": 12,
    "hinge_cup_edge": 22.5,
    "hinge_end_offset": 100,
    "leg_d": 40,
    "leg_corner_gap": 30,
    "notes": [],
}


def _solid(shape):
    if isinstance(shape, cq.Workplane):
        shape = shape.val()
    if isinstance(shape, cq.Solid):
        return shape
    sols = shape.Solids()
    if len(sols) == 1:
        return sols[0]
    return cq.Solid(shape.wrapped)


def _box(x0, x1, y0, y1, z0, z1):
    return cq.Solid.makeBox(
        x1 - x0, y1 - y0, z1 - z0, cq.Vector(x0, y0, z0)
    )


def _cut_all(solid, cutters):
    s = solid
    for c in cutters:
        s = _solid(s.cut(c))
    return s


def _linspace(a, b, n):
    if n == 1:
        return [a]
    return [a + (b - a) * i / (n - 1) for i in range(n)]


def build(params):
    W = params["W"]
    H = params["H"]
    D = params["D"]
    leg_h = params["leg_h"]
    mode = params["back_mode"]
    t = params["t"]
    back_t = params["back_t"]
    div_t = params["divider_t"]
    door_t = params["door_t"]
    shelf_t = params["shelf_t"]
    gap = params["door_gap"]
    door_max_w = params["door_max_w"]
    min_gap = params["shelf_min_gap"]
    pin_max = params["pin_max_spacing"]
    leg_max = params["leg_max_spacing"]

    Dc = D - door_t - gap
    z0 = leg_h
    z1 = H
    ch = z1 - z0  # carcass height
    panel_d = Dc - back_t if mode == "onset" else Dc  # depth of sides/top/bottom
    inner_d = Dc - back_t  # depth of dividers & shelves

    # ---- door count (never fewer than automatic) ----
    n_auto = max(1, math.ceil(W / door_max_w))
    n = n_auto if params["n_doors"] is None else max(int(params["n_doors"]), n_auto)
    cell = W / n

    # ---- vertical panels: (x_min, x_max, kind) ----
    panels = [(0, t)]
    for j in range(1, n):
        cx = j * cell
        panels.append((cx - div_t / 2, cx + div_t / 2))
    panels.append((W - t, W))

    # ---- shelves / pins ----
    clear_h = ch - 2 * t
    if params["n_shelves"] is None:
        k = max(0, math.floor((clear_h - min_gap) / (min_gap + shelf_t)))
    else:
        k = max(0, int(params["n_shelves"]))
    space = (clear_h - k * shelf_t) / (k + 1)

    clr = params["shelf_clearance"]
    pin_edge = params["pin_edge"]
    pin_d = params["pin_d"]
    pin_len = params["pin_len"]
    hole_depth = params["pin_hole_depth"]
    pin_drop = params["pin_drop"]
    pin_out = pin_len - hole_depth

    holes = {i: [] for i in range(len(panels))}
    shelves = []
    pins = []

    span = inner_d - 2 * pin_edge
    n_pins = math.ceil(span / pin_max) + 1
    pin_ys = _linspace(pin_edge, inner_d - pin_edge, n_pins)

    for b in range(len(panels) - 1):
        left_face = panels[b][1]
        right_face = panels[b + 1][0]
        for s in range(k):
            zb = z0 + t + space * (s + 1) + shelf_t * s
            shelves.append(
                _box(left_face + clr, right_face - clr, 0, inner_d, zb, zb + shelf_t)
            )
            zc = zb - pin_drop
            for y in pin_ys:
                # left panel of bay
                pins.append(
                    cq.Solid.makeCylinder(
                        pin_d / 2, pin_len,
                        cq.Vector(left_face - hole_depth, y, zc),
                        cq.Vector(1, 0, 0),
                    )
                )
                holes[b].append(
                    cq.Solid.makeCylinder(
                        pin_d / 2, hole_depth,
                        cq.Vector(left_face - hole_depth, y, zc),
                        cq.Vector(1, 0, 0),
                    )
                )
                # right panel of bay
                pins.append(
                    cq.Solid.makeCylinder(
                        pin_d / 2, pin_len,
                        cq.Vector(right_face - pin_out, y, zc),
                        cq.Vector(1, 0, 0),
                    )
                )
                holes[b + 1].append(
                    cq.Solid.makeCylinder(
                        pin_d / 2, hole_depth,
                        cq.Vector(right_face, y, zc),
                        cq.Vector(1, 0, 0),
                    )
                )

    parts = []

    # ---- carcass ----
    side_l = _box(0, t, 0, panel_d, z0, z1)
    side_r = _box(W - t, W, 0, panel_d, z0, z1)
    parts.append(("side_left", _cut_all(side_l, holes[0])))
    parts.append(("side_right", _cut_all(side_r, holes[len(panels) - 1])))
    parts.append(("top", _box(t, W - t, 0, panel_d, z1 - t, z1)))
    parts.append(("bottom", _box(t, W - t, 0, panel_d, z0, z0 + t)))

    if mode == "onset":
        back = _box(0, W, Dc - back_t, Dc, z0, z1)
    else:
        back = _box(t, W - t, Dc - back_t, Dc, z0 + t, z1 - t)
    parts.append(("back", back))

    # ---- dividers ----
    for j in range(1, n):
        x0, x1 = panels[j]
        d = _box(x0, x1, 0, inner_d, z0 + t, z1 - t)
        parts.append((f"divider_{j}", _cut_all(d, holes[j])))

    # ---- shelves ----
    for i, s in enumerate(shelves):
        parts.append((f"shelf_{i + 1}", s))

    # ---- pins ----
    for i, p in enumerate(pins):
        parts.append((f"pin_{i + 1}", p))

    # ---- doors ----
    dw = cell - 2 * gap
    dh = ch - 2 * gap
    if dh <= 900:
        n_h = 2
    elif dh <= 1600:
        n_h = 3
    else:
        n_h = 4
    cup_r = params["hinge_cup_d"] / 2
    cup_depth = params["hinge_cup_depth"]
    cup_edge = params["hinge_cup_edge"]
    end_off = params["hinge_end_offset"]
    for i in range(n):
        dx = i * cell + gap
        dz = z0 + gap
        door = _box(dx, dx + dw, -(gap + door_t), -gap, dz, dz + dh)
        hinge_left = (i % 2 == 0)
        if n > 1 and n % 2 == 1 and i == n - 1:
            hinge_left = False
        cx = dx + cup_edge if hinge_left else dx + dw - cup_edge
        cups = []
        for cz in _linspace(dz + end_off, dz + dh - end_off, n_h):
            cups.append(
                cq.Solid.makeCylinder(
                    cup_r, cup_depth,
                    cq.Vector(cx, -gap, cz),
                    cq.Vector(0, -1, 0),
                )
            )
        parts.append((f"door_{i + 1}", _cut_all(door, cups)))

    # ---- legs ----
    leg_d = params["leg_d"]
    inset = params["leg_corner_gap"] + leg_d / 2
    span_x = W - 2 * inset
    span_y = Dc - 2 * inset
    nx = math.ceil(span_x / leg_max) + 1
    ny = math.ceil(span_y / leg_max) + 1
    xs = _linspace(inset, W - inset, nx)
    ys = _linspace(inset, Dc - inset, ny)
    idx = 1
    for x in xs:
        for y in ys:
            parts.append(
                (
                    f"leg_{idx}",
                    cq.Solid.makeCylinder(
                        leg_d / 2, leg_h, cq.Vector(x, y, 0), cq.Vector(0, 0, 1)
                    ),
                )
            )
            idx += 1

    return parts


if __name__ == "__main__":
    result = build(PARAMS)
    print(len(result), "parts")
