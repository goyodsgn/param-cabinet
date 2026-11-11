import math
import cadquery as cq

PARAMS = {
    # main dimensions (mm)
    "W": 600,
    "H": 700,
    "D": 560,
    "leg_h": 100,
    # carcass
    "t": 18,
    "back_t": 6,
    # doors
    "door_max_w": 600,
    "door_gap": 3,
    "door_t": 18,
    # hinge cups
    "cup_d": 35,
    "cup_depth": 12,
    "cup_edge": 22.5,
    "cup_end_offset": 100,
    "hinge_h1": 900,
    "hinge_h2": 1600,
    # legs
    "leg_d": 40,
    "leg_edge_gap": 30,
    "leg_max_dist": 600,
}


def _box(x0, x1, y0, y1, z0, z1):
    return cq.Solid.makeBox(x1 - x0, y1 - y0, z1 - z0, cq.Vector(x0, y0, z0))


def _hinge_count(door_h, p):
    if door_h <= p["hinge_h1"]:
        return 2
    if door_h <= p["hinge_h2"]:
        return 3
    return 4


def build(params: dict):
    W = params["W"]
    H = params["H"]
    D = params["D"]
    leg_h = params["leg_h"]
    t = params["t"]
    back_t = params["back_t"]
    gap = params["door_gap"]
    door_t = params["door_t"]

    z0 = leg_h
    z1 = leg_h + H

    parts = []

    # Carcass
    parts.append(("side_left", _box(0, t, 0, D, z0, z1)))
    parts.append(("side_right", _box(W - t, W, 0, D, z0, z1)))
    parts.append(("top", _box(t, W - t, 0, D - back_t, z1 - t, z1)))
    parts.append(("bottom", _box(t, W - t, 0, D - back_t, z0, z0 + t)))
    parts.append(("back", _box(t, W - t, D - back_t, D, z0, z1)))

    # Doors
    count = max(1, math.ceil(W / params["door_max_w"] - 1e-9))
    door_w = (W - (count + 1) * gap) / count
    door_h = H - 2 * gap
    door_zb = leg_h + gap
    n_hinge = _hinge_count(door_h, params)
    cup_r = params["cup_d"] / 2.0
    off = params["cup_end_offset"]

    if n_hinge > 1:
        step = (door_h - 2 * off) / (n_hinge - 1)
        cup_zs = [door_zb + off + k * step for k in range(n_hinge)]
    else:
        cup_zs = [door_zb + door_h / 2.0]

    for i in range(1, count + 1):
        x0 = gap + (i - 1) * (door_w + gap)
        door = _box(x0, x0 + door_w, -door_t, 0, door_zb, door_zb + door_h)

        hinge_left = (i % 2 == 1)
        if count > 1 and count % 2 == 1 and i == count:
            hinge_left = False

        cx = x0 + params["cup_edge"] if hinge_left else x0 + door_w - params["cup_edge"]

        for cz in cup_zs:
            cup = cq.Solid.makeCylinder(
                cup_r,
                params["cup_depth"],
                cq.Vector(cx, 0, cz),
                cq.Vector(0, -1, 0),
            )
            door = door.cut(cup)

        parts.append((f"door_{i}", door))

    # Legs
    r = params["leg_d"] / 2.0
    inset = params["leg_edge_gap"] + r
    span_x = W - 2 * inset
    span_y = D - 2 * inset
    nx = math.ceil(span_x / params["leg_max_dist"] - 1e-9) + 1
    ny = math.ceil(span_y / params["leg_max_dist"] - 1e-9) + 1
    nx = max(nx, 2)
    ny = max(ny, 2)

    idx = 1
    for ix in range(nx):
        x = inset + span_x * ix / (nx - 1)
        for iy in range(ny):
            y = inset + span_y * iy / (ny - 1)
            leg = cq.Solid.makeCylinder(r, leg_h, cq.Vector(x, y, 0), cq.Vector(0, 0, 1))
            parts.append((f"leg_{idx}", leg))
            idx += 1

    return parts
