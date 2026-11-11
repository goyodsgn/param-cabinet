import math
import cadquery as cq

PARAMS = {
    # main dimensions
    "W": 1100.0,
    "H": 870.0,
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
    "hinge_h_2": 900.0,
    "hinge_h_3": 1600.0,
    # legs
    "leg_d": 40.0,
    "leg_edge_gap": 30.0,
    "leg_max_dist": 600.0,
}


def _ceil(x):
    return int(math.ceil(round(x, 9)))


def _solid(shape):
    if isinstance(shape, cq.Solid):
        return shape
    return shape.Solids()[0]


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
    hinge_d = params["hinge_d"]
    hinge_depth = params["hinge_depth"]
    hinge_edge = params["hinge_edge"]
    hinge_end = params["hinge_end"]
    leg_d = params["leg_d"]
    leg_edge_gap = params["leg_edge_gap"]
    leg_max_dist = params["leg_max_dist"]

    parts = []
    z0 = leg_h
    z1 = leg_h + H

    # Carcass
    parts.append(("side_left", _box(0, t, 0, D, z0, z1)))
    parts.append(("side_right", _box(W - t, W, 0, D, z0, z1)))
    parts.append(("top", _box(t, W - t, 0, D - back_t, z1 - t, z1)))
    parts.append(("bottom", _box(t, W - t, 0, D - back_t, z0, z0 + t)))
    parts.append(("back", _box(t, W - t, D - back_t, D, z0, z1)))

    # Doors
    count = max(1, _ceil(W / door_max_w))
    door_w = (W - (count + 1) * gap) / count
    door_h = H - 2 * gap
    door_z = leg_h + gap

    if door_h <= params["hinge_h_2"]:
        n_hinges = 2
    elif door_h <= params["hinge_h_3"]:
        n_hinges = 3
    else:
        n_hinges = 4

    for i in range(count):
        x0 = gap + i * (door_w + gap)
        door = _box(x0, x0 + door_w, -door_t, 0, door_z, door_z + door_h)

        # hinge side: 1st left, 2nd right, ...; odd last (count>1) -> right
        hinge_left = (i % 2 == 0)
        if count > 1 and count % 2 == 1 and i == count - 1:
            hinge_left = False
        cx = x0 + hinge_edge if hinge_left else x0 + door_w - hinge_edge

        zs = door_z + hinge_end
        ze = door_z + door_h - hinge_end
        for k in range(n_hinges):
            cz = zs + k * (ze - zs) / (n_hinges - 1)
            cup = cq.Solid.makeCylinder(
                hinge_d / 2.0, hinge_depth,
                cq.Vector(cx, -hinge_depth, cz), cq.Vector(0, 1, 0))
            door = _solid(door.cut(cup))

        parts.append(("door_%d" % (i + 1), door))

    # Legs
    inset = leg_edge_gap + leg_d / 2.0
    span_x = W - 2 * inset
    span_y = D - 2 * inset
    nx = _ceil(span_x / leg_max_dist) + 1
    ny = _ceil(span_y / leg_max_dist) + 1

    n = 0
    for ix in range(nx):
        lx = inset + ix * span_x / (nx - 1)
        for iy in range(ny):
            ly = inset + iy * span_y / (ny - 1)
            n += 1
            leg = cq.Solid.makeCylinder(
                leg_d / 2.0, leg_h, cq.Vector(lx, ly, 0), cq.Vector(0, 0, 1))
            parts.append(("leg_%d" % n, leg))

    return parts
