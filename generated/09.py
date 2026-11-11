import math
import cadquery as cq

PARAMS = {
    # main dimensions (mm)
    "W": 3000.0,
    "H": 850.0,
    "D": 600.0,
    "leg_h": 100.0,
    # carcass
    "t": 18.0,
    "back_t": 6.0,
    # doors
    "door_max_w": 600.0,
    "door_gap": 3.0,
    "door_t": 18.0,
    # hinge cups
    "cup_d": 35.0,
    "cup_depth": 12.0,
    "cup_edge": 22.5,
    "cup_end_margin": 100.0,
    "hinge_h1": 900.0,    # up to this height -> 2 hinges
    "hinge_h2": 1600.0,   # up to this height -> 3 hinges, above -> 4
    # legs
    "leg_d": 40.0,
    "leg_corner_gap": 30.0,
    "leg_max_pitch": 600.0,
}


def _solid(wp):
    v = wp.val()
    if isinstance(v, cq.Solid):
        return v
    return v.Solids()[0]


def _box(x0, x1, y0, y1, z0, z1):
    return cq.Solid.makeBox(x1 - x0, y1 - y0, z1 - z0, cq.Vector(x0, y0, z0))


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
    cup_d = params["cup_d"]
    cup_depth = params["cup_depth"]
    cup_edge = params["cup_edge"]
    cup_margin = params["cup_end_margin"]
    leg_d = params["leg_d"]
    corner_gap = params["leg_corner_gap"]
    max_pitch = params["leg_max_pitch"]

    parts = []
    z0 = leg_h
    z1 = leg_h + H

    # ---- carcass ----
    parts.append(("side_left", _box(0, t, 0, D, z0, z1)))
    parts.append(("side_right", _box(W - t, W, 0, D, z0, z1)))
    parts.append(("top", _box(t, W - t, 0, D - back_t, z1 - t, z1)))
    parts.append(("bottom", _box(t, W - t, 0, D - back_t, z0, z0 + t)))
    parts.append(("back", _box(t, W - t, D - back_t, D, z0, z1)))

    # ---- doors ----
    count = max(1, math.ceil(W / door_max_w))
    door_w = (W - (count + 1) * gap) / count
    door_h = H - 2 * gap
    door_z0 = leg_h + gap

    if door_h <= params["hinge_h1"]:
        n_hinges = 2
    elif door_h <= params["hinge_h2"]:
        n_hinges = 3
    else:
        n_hinges = 4

    for i in range(count):
        idx = i + 1
        x0 = gap + i * (door_w + gap)
        x1 = x0 + door_w

        # facing pairs: odd -> left, even -> right; last door of odd count (>1) -> right
        hinge_left = (idx % 2 == 1)
        if count > 1 and count % 2 == 1 and idx == count:
            hinge_left = False

        door = cq.Workplane("XY").add(_box(x0, x1, -door_t, 0, door_z0, door_z0 + door_h))

        cx = x0 + cup_edge if hinge_left else x1 - cup_edge
        zs = door_z0 + cup_margin
        ze = door_z0 + door_h - cup_margin
        for k in range(n_hinges):
            cz = zs + k * (ze - zs) / (n_hinges - 1)
            cup = cq.Solid.makeCylinder(
                cup_d / 2.0, cup_depth,
                cq.Vector(cx, 0, cz), cq.Vector(0, -1, 0))
            door = door.cut(cq.Workplane("XY").add(cup))

        parts.append(("door_%d" % idx, _solid(door)))

    # ---- legs ----
    off = corner_gap + leg_d / 2.0
    span_x = W - 2 * off
    span_y = D - 2 * off
    nx = max(2, math.ceil(span_x / max_pitch) + 1)
    ny = max(2, math.ceil(span_y / max_pitch) + 1)

    n = 0
    for ix in range(nx):
        x = off + ix * span_x / (nx - 1)
        for iy in range(ny):
            y = off + iy * span_y / (ny - 1)
            n += 1
            leg = cq.Solid.makeCylinder(
                leg_d / 2.0, leg_h,
                cq.Vector(x, y, 0), cq.Vector(0, 0, 1))
            parts.append(("leg_%d" % n, leg))

    return parts
