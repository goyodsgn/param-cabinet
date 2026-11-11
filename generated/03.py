import cadquery as cq
import math

PARAMS = {
    # user request
    "W": 900.0,
    "H": 820.0,
    "D": 600.0,
    "leg_h": 150.0,
    # carcass
    "t": 18.0,
    "back_t": 6.0,
    # doors
    "door_max_w": 600.0,
    "door_gap": 3.0,
    "door_t": 18.0,
    # hinges
    "hinge_d": 35.0,
    "hinge_depth": 12.0,
    "hinge_edge": 22.5,
    "hinge_end": 100.0,
    "hinge_h1": 900.0,
    "hinge_h2": 1600.0,
    # legs
    "leg_d": 40.0,
    "leg_edge_gap": 30.0,
    "leg_max_spacing": 600.0,
}


def _box(x0, x1, y0, y1, z0, z1):
    return (
        cq.Workplane("XY")
        .box(x1 - x0, y1 - y0, z1 - z0, centered=False)
        .translate((x0, y0, z0))
    )


def _solid(wp):
    v = wp.val()
    if isinstance(v, cq.Solid):
        return v
    return wp.solids().vals()[0]


def _line_positions(start, end, max_spacing):
    span = end - start
    n = int(math.ceil(round(span / max_spacing, 9))) + 1
    n = max(n, 2)
    return [start + i * span / (n - 1) for i in range(n)]


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
    leg_max = params["leg_max_spacing"]

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
    count = max(1, int(math.ceil(round(W / door_max_w, 9))))
    door_w = (W - (count + 1) * gap) / count
    door_h = H - 2 * gap
    door_z0 = leg_h + gap
    door_z1 = door_z0 + door_h

    if door_h <= params["hinge_h1"]:
        n_hinge = 2
    elif door_h <= params["hinge_h2"]:
        n_hinge = 3
    else:
        n_hinge = 4

    cup_z_first = door_z0 + hinge_end
    cup_z_last = door_z1 - hinge_end
    cup_zs = [
        cup_z_first + i * (cup_z_last - cup_z_first) / (n_hinge - 1)
        for i in range(n_hinge)
    ]

    for i in range(count):
        dx0 = gap + i * (door_w + gap)
        dx1 = dx0 + door_w
        # hinge side: odd-numbered (1st, 3rd...) left, even right
        hinge_left = (i % 2 == 0)
        if count > 1 and count % 2 == 1 and i == count - 1:
            hinge_left = False
        cup_x = dx0 + hinge_edge if hinge_left else dx1 - hinge_edge

        door = _box(dx0, dx1, -door_t, 0, door_z0, door_z1)
        door_solid = _solid(door)
        for cz in cup_zs:
            cyl = cq.Solid.makeCylinder(
                hinge_d / 2.0,
                hinge_depth,
                cq.Vector(cup_x, 0, cz),
                cq.Vector(0, -1, 0),
            )
            door_solid = door_solid.cut(cyl)
            if not isinstance(door_solid, cq.Solid):
                door_solid = cq.Workplane("XY").add(door_solid).solids().vals()[0]
        parts.append((f"door_{i + 1}", door_solid))

    # ---- legs ----
    inset = leg_edge_gap + leg_d / 2.0
    xs = _line_positions(inset, W - inset, leg_max)
    ys = _line_positions(inset, D - inset, leg_max)
    k = 1
    for y in ys:
        for x in xs:
            leg = cq.Solid.makeCylinder(
                leg_d / 2.0, leg_h, cq.Vector(x, y, 0), cq.Vector(0, 0, 1)
            )
            parts.append((f"leg_{k}", leg))
            k += 1

    return parts


result = build(PARAMS)
