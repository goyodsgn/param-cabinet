import math
import cadquery as cq

PARAMS = {
    # main dimensions (mm)
    "W": 1500,
    "H": 850,
    "D": 600,
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
    "leg_max_pitch": 600,
}


def _ceil(x):
    return int(math.ceil(round(x, 9)))


def _box(x0, x1, y0, y1, z0, z1):
    return cq.Workplane("XY").box(
        x1 - x0, y1 - y0, z1 - z0, centered=False
    ).translate((x0, y0, z0)).val()


def _solid(shape):
    if isinstance(shape, cq.Solid):
        return shape
    sols = shape.Solids()
    return sols[0]


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
    cup_end = params["cup_end_offset"]
    h1 = params["hinge_h1"]
    h2 = params["hinge_h2"]
    leg_d = params["leg_d"]
    leg_gap = params["leg_edge_gap"]
    leg_pitch = params["leg_max_pitch"]

    parts = []
    z0 = leg_h
    z1 = leg_h + H

    # ---- carcass ----
    parts.append(("side_left", _solid(_box(0, t, 0, D, z0, z1))))
    parts.append(("side_right", _solid(_box(W - t, W, 0, D, z0, z1))))
    parts.append(("top", _solid(_box(t, W - t, 0, D - back_t, z1 - t, z1))))
    parts.append(("bottom", _solid(_box(t, W - t, 0, D - back_t, z0, z0 + t))))
    parts.append(("back", _solid(_box(t, W - t, D - back_t, D, z0, z1))))

    # ---- doors ----
    count = max(1, _ceil(W / door_max_w))
    dw = (W - (count + 1) * gap) / count
    dh = H - 2 * gap
    d_bottom = leg_h + gap
    if dh <= h1:
        n_h = 2
    elif dh <= h2:
        n_h = 3
    else:
        n_h = 4

    for i in range(count):
        idx = i + 1
        x0 = gap + i * (dw + gap)
        # odd index -> left, even -> right; odd count >1: last door right
        hinge_left = (idx % 2 == 1)
        if count % 2 == 1 and count > 1 and idx == count:
            hinge_left = False

        door = _box(x0, x0 + dw, -door_t, 0, d_bottom, d_bottom + dh)
        cx = x0 + cup_edge if hinge_left else x0 + dw - cup_edge

        span = dh - 2 * cup_end
        for k in range(n_h):
            zc = d_bottom + cup_end + (span * k / (n_h - 1))
            cup = cq.Solid.makeCylinder(
                cup_d / 2.0, cup_depth,
                cq.Vector(cx, 0, zc), cq.Vector(0, -1, 0)
            )
            door = door.cut(cup)
        parts.append(("door_%d" % idx, _solid(door)))

    # ---- legs ----
    r = leg_d / 2.0
    inset = leg_gap + r
    x_span = W - 2 * inset
    y_span = D - 2 * inset
    nx = _ceil(x_span / leg_pitch) + 1
    ny = _ceil(y_span / leg_pitch) + 1
    n = 0
    for ix in range(nx):
        x = inset + (x_span * ix / (nx - 1) if nx > 1 else 0)
        for iy in range(ny):
            y = inset + (y_span * iy / (ny - 1) if ny > 1 else 0)
            n += 1
            leg = cq.Solid.makeCylinder(
                r, leg_h, cq.Vector(x, y, 0), cq.Vector(0, 0, 1)
            )
            parts.append(("leg_%d" % n, leg))

    return parts
