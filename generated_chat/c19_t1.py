import math
import cadquery as cq

PARAMS = {
    "W": 1200,
    "H": 1500,
    "D": 450,
    "leg_h": 100,
    "back_mode": "onset",
    "top_mode": "inset",
    "t": 18,
    "back_t": 10,
    "divider_t": 18,
    "door_t": 22,
    "shelf_t": 30,
    "door_gap": 2,
    "door_max_w": 600,
    "n_doors": None,
    "door_layout": None,
    "n_shelves": None,
    "shelf_min_gap": 320,
    "bottom_clear_min": 400,
    "pin_max_spacing": 500,
    "leg_max_spacing": 600,
    # extra values
    "pin_edge": 50,
    "pin_d": 5,
    "pin_hole_depth": 8,
    "pin_out": 6,
    "leg_d": 40,
    "leg_edge_gap": 30,
    "cup_d": 35,
    "cup_depth": 12,
    "cup_edge": 22.5,
    "cup_end_margin": 100,
    "notes": [
        "Lowest compartment: old photo albums (large format, about 350 mm tall) "
        "need clearance, so bottom_clear_min = 400 mm (album plus finger room).",
        "Width 1200 needs 2 doors (door_max_w 600), so one inner wall stands at the joint at x = 600.",
        "Shelf count is automatic. The lowest space stays at least 400 mm and the others at least 320 mm.",
    ],
}


def _box(x, y, z, dx, dy, dz):
    return cq.Workplane("XY").box(dx, dy, dz, centered=False).translate((x, y, z))


def _solid(wp):
    v = wp.val()
    if isinstance(v, cq.Solid):
        return v
    sols = v.Solids()
    return sols[0] if len(sols) == 1 else v


def build(params):
    p = params
    W, H, D = p["W"], p["H"], p["D"]
    leg_h = p["leg_h"]
    t, back_t, dvt = p["t"], p["back_t"], p["divider_t"]
    door_t, shelf_t, gap = p["door_t"], p["shelf_t"], p["door_gap"]
    door_max_w = p["door_max_w"]
    back_mode, top_mode = p["back_mode"], p["top_mode"]
    Dc = D - door_t - gap
    inner_d = Dc - back_t  # depth up to back panel inner face
    panel_d = inner_d if back_mode == "onset" else Dc

    # ---------- doors / bays ----------
    layout = p["door_layout"]
    n_auto = max(1, math.ceil(W / door_max_w))
    if layout:
        n = sum(layout)
        if W / n > door_max_w + 1e-9:
            layout = None
    if not layout:
        n = n_auto
        if p["n_doors"]:
            n = max(n, int(p["n_doors"]))
        layout = [1] * n
    n = sum(layout)
    cell = W / n

    # bays: list of (first_cell, n_cells)
    bays = []
    c = 0
    for b in layout:
        bays.append((c, b))
        c += b
    boundaries = [bays[i][0] * cell for i in range(1, len(bays))]  # divider centers

    # ---------- carcass heights ----------
    if top_mode == "inset":
        clear_h = H - leg_h - 2 * t
        side_top = H
    elif top_mode == "onset":
        clear_h = H - leg_h - 2 * t
        side_top = H - t
    else:
        clear_h = H - leg_h - t
        side_top = H
    z0 = leg_h + t  # top of bottom panel
    z_inner_top = z0 + clear_h

    # ---------- panels ----------
    panels = {}
    panels["side_left"] = _box(0, 0, leg_h, t, panel_d, side_top - leg_h)
    panels["side_right"] = _box(W - t, 0, leg_h, t, panel_d, side_top - leg_h)
    panels["bottom"] = _box(t, 0, leg_h, W - 2 * t, panel_d, t)
    if top_mode == "inset":
        panels["top"] = _box(t, 0, H - t, W - 2 * t, panel_d, t)
    elif top_mode == "onset":
        panels["top"] = _box(0, 0, H - t, W, panel_d, t)
    if back_mode == "onset":
        panels["back"] = _box(0, Dc - back_t, leg_h, W, back_t, H - leg_h)
    else:
        panels["back"] = _box(t, Dc - back_t, z0, W - 2 * t, back_t, clear_h)
    for i, xc in enumerate(boundaries, start=1):
        panels[f"divider_{i}"] = _box(xc - dvt / 2, 0, z0, dvt, inner_d, clear_h)

    # ---------- bay extents ----------
    bay_ext = []
    for bi in range(len(bays)):
        left = t if bi == 0 else boundaries[bi - 1] + dvt / 2
        right = (W - t) if bi == len(bays) - 1 else boundaries[bi] - dvt / 2
        lname = "side_left" if bi == 0 else f"divider_{bi}"
        rname = "side_right" if bi == len(bays) - 1 else f"divider_{bi + 1}"
        bay_ext.append((left, right, lname, rname))

    # ---------- shelf positions (bottom z of each shelf) ----------
    bmin = p["bottom_clear_min"]
    min_gap = p["shelf_min_gap"]
    if p["n_shelves"] is not None:
        k = max(0, int(p["n_shelves"]))
        auto = False
    else:
        base = max(bmin or 0, min_gap)
        k = max(0, math.floor((clear_h - base) / (min_gap + shelf_t)))
        auto = True
    shelf_zs = []
    if k > 0:
        g = (clear_h - k * shelf_t) / (k + 1)
        if auto and bmin and g < bmin:
            g2 = (clear_h - bmin - k * shelf_t) / k
            for i in range(k):
                shelf_zs.append(z0 + bmin + i * (g2 + shelf_t))
        else:
            for i in range(1, k + 1):
                shelf_zs.append(z0 + i * g + (i - 1) * shelf_t)

    # ---------- shelves and pins ----------
    pin_r = p["pin_d"] / 2
    hole_d = p["pin_hole_depth"]
    pin_out = p["pin_out"]
    edge = p["pin_edge"]
    span = inner_d - 2 * edge
    m = math.ceil(span / p["pin_max_spacing"]) + 1
    pin_ys = [edge + j * span / (m - 1) for j in range(m)] if m > 1 else [edge]

    holes = {name: [] for name in panels}
    shelves = []
    pins = []
    for (left, right, lname, rname) in bay_ext:
        for zb in shelf_zs:
            shelves.append(_box(left + 1, 0, zb, (right - left) - 2, inner_d, shelf_t))
            zc = zb - p["pin_d"] / 2
            for y in pin_ys:
                # left panel pin: sticks out into bay by pin_out, hole_d into panel
                x0 = left - hole_d
                pins.append(cq.Workplane("YZ").center(y, zc).circle(pin_r)
                            .extrude(hole_d + pin_out).translate((x0, 0, 0)))
                holes[lname].append(cq.Workplane("YZ").center(y, zc).circle(pin_r)
                                    .extrude(hole_d).translate((x0, 0, 0)))
                # right panel pin
                x1 = right - pin_out
                pins.append(cq.Workplane("YZ").center(y, zc).circle(pin_r)
                            .extrude(pin_out + hole_d).translate((x1, 0, 0)))
                holes[rname].append(cq.Workplane("YZ").center(y, zc).circle(pin_r)
                                    .extrude(hole_d).translate((x1, 0, 0)))

    result = []
    order = ["side_left", "side_right", "top", "bottom", "back"]
    order += [f"divider_{i}" for i in range(1, len(boundaries) + 1)]
    for name in order:
        if name not in panels:
            continue
        wp = panels[name]
        for h in holes.get(name, []):
            wp = wp.cut(h)
        result.append((name, _solid(wp)))
    for i, s in enumerate(shelves, start=1):
        result.append((f"shelf_{i}", _solid(s)))
    for i, pn in enumerate(pins, start=1):
        result.append((f"pin_{i}", _solid(pn)))

    # ---------- hinge sides ----------
    hinge = [None] * n
    all_single = all(b == 1 for b in layout)
    if all_single:
        for i in range(n):
            hinge[i] = "L" if i % 2 == 0 else "R"
        if n > 1 and n % 2 == 1:
            hinge[-1] = "R"
    else:
        for (c0, nb) in bays:
            if nb == 2:
                hinge[c0] = "L"
                hinge[c0 + 1] = "R"
            else:
                center = c0 * cell + cell / 2
                hinge[c0] = "L" if center <= W / 2 else "R"

    # ---------- doors ----------
    door_w = cell - 2 * gap
    door_h = (H - leg_h) - 2 * gap
    if door_h <= 900:
        n_h = 2
    elif door_h <= 1600:
        n_h = 3
    else:
        n_h = 4
    zb_door = leg_h + gap
    cup_zs = []
    if n_h == 1:
        cup_zs = [zb_door + door_h / 2]
    else:
        top_m = p["cup_end_margin"]
        zlo = zb_door + top_m
        zhi = zb_door + door_h - top_m
        cup_zs = [zlo + j * (zhi - zlo) / (n_h - 1) for j in range(n_h)]
    for i in range(n):
        x0 = i * cell + gap
        door = _box(x0, -(gap + door_t), zb_door, door_w, door_t, door_h)
        cx = x0 + p["cup_edge"] if hinge[i] == "L" else x0 + door_w - p["cup_edge"]
        for cz in cup_zs:
            cup = (cq.Workplane("XZ").center(cx, cz).circle(p["cup_d"] / 2)
                   .extrude(p["cup_depth"]).translate((0, -gap, 0)))
            door = door.cut(cup)
        result.append((f"door_{i + 1}", _solid(door)))

    # ---------- legs ----------
    leg_r = p["leg_d"] / 2
    off = p["leg_edge_gap"] + leg_r
    xs_span = W - 2 * off
    ys_span = Dc - 2 * off
    nx = math.ceil(xs_span / p["leg_max_spacing"]) + 1
    ny = math.ceil(ys_span / p["leg_max_spacing"]) + 1
    xs = [off + i * xs_span / (nx - 1) for i in range(nx)]
    ys = [off + j * ys_span / (ny - 1) for j in range(ny)]
    idx = 1
    for y in ys:
        for x in xs:
            leg = cq.Workplane("XY").center(x, y).circle(leg_r).extrude(leg_h)
            result.append((f"leg_{idx}", _solid(leg)))
            idx += 1

    return result
