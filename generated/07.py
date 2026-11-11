import math
import cadquery as cq

PARAMS = {
    # main dimensions (mm)
    "W": 750,
    "H": 720,
    "D": 550,
    "leg_h": 100,
    # carcass
    "t": 18,
    "back_t": 6,
    # doors
    "door_t": 18,
    "door_max_w": 600,
    "door_gap": 3,
    # hinge cups
    "cup_d": 35,
    "cup_depth": 12,
    "cup_edge": 22.5,
    "hinge_end": 100,
    "hinge_h1": 900,    # up to this door height -> 2 hinges
    "hinge_h2": 1600,   # up to this door height -> 3 hinges, above -> 4
    # legs
    "leg_d": 40,
    "leg_edge_gap": 30,
    "leg_max_spacing": 600,
}


def _ceil(x):
    return int(math.ceil(round(x, 9)))


def _box(x0, x1, y0, y1, z0, z1):
    return cq.Solid.makeBox(x1 - x0, y1 - y0, z1 - z0, cq.Vector(x0, y0, z0))


def build(params):
    W = params["W"]
    H = params["H"]
    D = params["D"]
    leg_h = params["leg_h"]
    t = params["t"]
    back_t = params["back_t"]
    door_t = params["door_t"]
    door_max_w = params["door_max_w"]
    gap = params["door_gap"]
    cup_d = params["cup_d"]
    cup_depth = params["cup_depth"]
    cup_edge = params["cup_edge"]
    hinge_end = params["hinge_end"]
    leg_d = params["leg_d"]
    leg_edge_gap = params["leg_edge_gap"]
    leg_max = params["leg_max_spacing"]

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
    count = max(1, _ceil(W / door_max_w))
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
        hinge_left = (idx % 2 == 1)
        if count > 1 and count % 2 == 1 and idx == count:
            hinge_left = False

        x0 = gap + i * (door_w + gap)
        x1 = x0 + door_w
        door = _box(x0, x1, -door_t, 0, door_z0, door_z0 + door_h)

        cx = x0 + cup_edge if hinge_left else x1 - cup_edge
        zl = door_z0 + hinge_end
        zh = door_z0 + door_h - hinge_end
        for k in range(n_hinges):
            zc = zl + k * (zh - zl) / (n_hinges - 1)
            cup = cq.Solid.makeCylinder(
                cup_d / 2.0, cup_depth,
                cq.Vector(cx, -cup_depth, zc), cq.Vector(0, 1, 0))
            door = door.cut(cup)
        solids = door.Solids()
        door = solids[0] if solids else door
        parts.append(("door_%d" % idx, door))

    # ---- legs ----
    inset = leg_edge_gap + leg_d / 2.0
    x_a, x_b = inset, W - inset
    y_a, y_b = inset, D - inset
    nx = _ceil((x_b - x_a) / leg_max) + 1
    ny = _ceil((y_b - y_a) / leg_max) + 1
    nx = max(nx, 2)
    ny = max(ny, 2)
    n = 1
    for ix in range(nx):
        x = x_a + ix * (x_b - x_a) / (nx - 1)
        for iy in range(ny):
            y = y_a + iy * (y_b - y_a) / (ny - 1)
            leg = cq.Solid.makeCylinder(
                leg_d / 2.0, leg_h, cq.Vector(x, y, 0), cq.Vector(0, 0, 1))
            parts.append(("leg_%d" % n, leg))
            n += 1

    return parts
