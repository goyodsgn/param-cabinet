import math
import cadquery as cq

PARAMS = {
    # main dimensions (mm)
    "W": 1800,
    "H": 1000,
    "D": 650,
    "leg_h": 100,
    # carcass
    "t": 18,
    "back_t": 6,
    # doors
    "door_max_w": 600,
    "door_gap": 3,
    "door_t": 18,
    # hinge cups
    "hinge_d": 35,
    "hinge_depth": 12,
    "hinge_edge": 22.5,
    "hinge_end_margin": 100,
    "hinge_h_limit_2": 900,
    "hinge_h_limit_3": 1600,
    # legs
    "leg_d": 40,
    "leg_edge_gap": 30,
    "leg_max_spacing": 600,
}


def _box(x, y, z, dx, dy, dz):
    return (
        cq.Workplane("XY")
        .box(dx, dy, dz, centered=False)
        .translate((x, y, z))
        .val()
    )


def _linspace(a, b, n):
    if n == 1:
        return [(a + b) / 2.0]
    return [a + (b - a) * i / (n - 1) for i in range(n)]


def build(params):
    W = params["W"]
    H = params["H"]
    D = params["D"]
    leg_h = params["leg_h"]
    t = params["t"]
    back_t = params["back_t"]
    door_max_w = params["door_max_w"]
    gap = params["door_gap"]
    door_t = params["door_t"]
    hinge_d = params["hinge_d"]
    hinge_depth = params["hinge_depth"]
    hinge_edge = params["hinge_edge"]
    hinge_margin = params["hinge_end_margin"]
    lim2 = params["hinge_h_limit_2"]
    lim3 = params["hinge_h_limit_3"]
    leg_d = params["leg_d"]
    leg_gap = params["leg_edge_gap"]
    leg_max = params["leg_max_spacing"]

    parts = []

    # ---- Carcass ----
    parts.append(("side_left", _box(0, 0, leg_h, t, D, H)))
    parts.append(("side_right", _box(W - t, 0, leg_h, t, D, H)))
    parts.append(("top", _box(t, 0, leg_h + H - t, W - 2 * t, D - back_t, t)))
    parts.append(("bottom", _box(t, 0, leg_h, W - 2 * t, D - back_t, t)))
    parts.append(("back", _box(t, D - back_t, leg_h, W - 2 * t, back_t, H)))

    # ---- Doors ----
    count = max(1, math.ceil(W / door_max_w))
    door_w = (W - (count + 1) * gap) / count
    door_h = H - 2 * gap
    door_z0 = leg_h + gap

    if door_h <= lim2:
        n_hinges = 2
    elif door_h <= lim3:
        n_hinges = 3
    else:
        n_hinges = 4

    for i in range(count):
        idx = i + 1
        x0 = gap + i * (door_w + gap)
        # odd index -> left, even -> right; last odd door (count>1) -> right
        hinge_left = (idx % 2 == 1)
        if count > 1 and count % 2 == 1 and idx == count:
            hinge_left = False

        door = (
            cq.Workplane("XY")
            .box(door_w, door_t, door_h, centered=False)
            .translate((x0, -door_t, door_z0))
        )

        cx = x0 + hinge_edge if hinge_left else x0 + door_w - hinge_edge
        zs = _linspace(door_z0 + hinge_margin,
                       door_z0 + door_h - hinge_margin, n_hinges)
        for cz in zs:
            # cup drilled from the inner face (y=0) toward the front
            cyl = cq.Solid.makeCylinder(
                hinge_d / 2.0,
                hinge_depth + 1.0,
                cq.Vector(cx, 1.0, cz),
                cq.Vector(0, -1, 0),
            )
            door = door.cut(cq.Workplane("XY").add(cyl))

        parts.append(("door_%d" % idx, door.val()))

    # ---- Legs ----
    off = leg_gap + leg_d / 2.0
    span_x = W - 2 * off
    span_y = D - 2 * off
    nx = math.ceil(round(span_x / leg_max, 9)) + 1
    ny = math.ceil(round(span_y / leg_max, 9)) + 1
    xs = _linspace(off, W - off, nx)
    ys = _linspace(off, D - off, ny)

    n = 1
    for y in ys:
        for x in xs:
            leg = (
                cq.Workplane("XY")
                .circle(leg_d / 2.0)
                .extrude(leg_h)
                .translate((x, y, 0))
                .val()
            )
            parts.append(("leg_%d" % n, leg))
            n += 1

    return parts
