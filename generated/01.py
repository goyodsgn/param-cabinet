import math
import cadquery as cq

PARAMS = {
    # main dimensions
    "W": 1200.0,
    "H": 850.0,
    "D": 580.0,
    "leg_h": 100.0,
    # carcass
    "t": 18.0,
    "back_t": 6.0,
    # doors
    "door_max_w": 600.0,
    "door_gap": 3.0,
    "door_t": 18.0,
    # hinge cups
    "hinge_d": 35.0,
    "hinge_depth": 12.0,
    "hinge_edge": 22.5,
    "hinge_end": 100.0,
    "hinge_h1": 900.0,   # up to this door height -> 2 hinges
    "hinge_h2": 1600.0,  # up to this door height -> 3 hinges, above -> 4
    # legs
    "leg_d": 40.0,
    "leg_inset": 30.0,   # gap between leg edge and carcass edge
    "leg_max_spacing": 600.0,
}


def _box(x0, x1, y0, y1, z0, z1):
    return (
        cq.Workplane("XY")
        .box(x1 - x0, y1 - y0, z1 - z0, centered=False)
        .translate((x0, y0, z0))
        .solids()
        .vals()[0]
    )


def _count_per_line(span, max_spacing):
    if span <= 1e-9:
        return 1
    return int(math.ceil(round(span / max_spacing, 9))) + 1


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
    hinge_end = params["hinge_end"]
    hinge_h1 = params["hinge_h1"]
    hinge_h2 = params["hinge_h2"]
    leg_d = params["leg_d"]
    leg_inset = params["leg_inset"]
    leg_max = params["leg_max_spacing"]

    parts = []
    z0 = leg_h
    z1 = leg_h + H

    # ---- Carcass ----
    parts.append(("side_left", _box(0, t, 0, D, z0, z1)))
    parts.append(("side_right", _box(W - t, W, 0, D, z0, z1)))
    parts.append(("top", _box(t, W - t, 0, D - back_t, z1 - t, z1)))
    parts.append(("bottom", _box(t, W - t, 0, D - back_t, z0, z0 + t)))
    parts.append(("back", _box(t, W - t, D - back_t, D, z0, z1)))

    # ---- Doors ----
    count = max(1, int(math.ceil(round(W / door_max_w, 9))))
    door_w = (W - (count + 1) * gap) / count
    door_h = H - 2 * gap
    door_z0 = leg_h + gap

    if door_h <= hinge_h1:
        n_hinge = 2
    elif door_h <= hinge_h2:
        n_hinge = 3
    else:
        n_hinge = 4

    for i in range(count):
        idx = i + 1
        x_left = gap + i * (door_w + gap)
        x_right = x_left + door_w

        # hinge side: odd -> left, even -> right; last of odd count (>1) -> right
        hinge_left = (idx % 2 == 1)
        if count > 1 and count % 2 == 1 and idx == count:
            hinge_left = False

        door = _box(x_left, x_right, -door_t, 0, door_z0, door_z0 + door_h)

        cup_x = x_left + hinge_edge if hinge_left else x_right - hinge_edge
        z_first = door_z0 + hinge_end
        z_last = door_z0 + door_h - hinge_end
        for k in range(n_hinge):
            cz = z_first + k * (z_last - z_first) / (n_hinge - 1)
            cup = cq.Solid.makeCylinder(
                hinge_d / 2.0,
                hinge_depth,
                cq.Vector(cup_x, 0, cz),
                cq.Vector(0, -1, 0),
            )
            door = door.cut(cup)
        door = cq.Workplane("XY").add(door).solids().vals()[0]
        parts.append(("door_%d" % idx, door))

    # ---- Legs ----
    off = leg_inset + leg_d / 2.0
    span_x = W - 2 * off
    span_y = D - 2 * off
    nx = _count_per_line(span_x, leg_max)
    ny = _count_per_line(span_y, leg_max)

    xs = [off + i * span_x / (nx - 1) for i in range(nx)] if nx > 1 else [W / 2.0]
    ys = [off + j * span_y / (ny - 1) for j in range(ny)] if ny > 1 else [D / 2.0]

    n = 1
    for y in ys:
        for x in xs:
            leg = cq.Solid.makeCylinder(
                leg_d / 2.0, leg_h, cq.Vector(x, y, 0), cq.Vector(0, 0, 1)
            )
            parts.append(("leg_%d" % n, leg))
            n += 1

    return parts
