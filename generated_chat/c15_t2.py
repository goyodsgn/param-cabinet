import math
import cadquery as cq

PARAMS = {
    "W": 1000,
    "H": 850,
    "D": 600,
    "leg_h": 100,
    "back_mode": "onset",
    "top_mode": "onset",  # top panel covers the sides
    "t": 18,
    "back_t": 10,
    "divider_t": 18,
    "door_t": 22,
    "shelf_t": 30,
    "door_gap": 2,
    "door_max_w": 600,
    "n_doors": None,
    "door_layout": [2],  # one bay with a double (pair) door
    "n_shelves": None,
    "shelf_min_gap": 320,
    "bottom_clear_min": None,
    "pin_max_spacing": 500,
    "leg_max_spacing": 600,
    "notes": [
        "양문형 요청: 문 2개가 한 쌍(door_layout=[2])이므로 두 문 사이 뒤에는 내벽을 두지 않았습니다.",
        "폭 1000 / 최대 문 폭 600 규칙에 따라 문 2개, 각 칸 폭 500.",
        "상판이 위를 덮게(top_mode='onset'): 상판 폭 W, 옆판은 H - t 까지만 올라갑니다.",
        "깊이 600은 문과 다리를 포함한 전체 치수이므로 본체 깊이 Dc = 600 - 22 - 2 = 576 입니다.",
    ],
}


def _box(x0, x1, y0, y1, z0, z1):
    return (cq.Workplane("XY")
            .box(x1 - x0, y1 - y0, z1 - z0, centered=False)
            .translate((x0, y0, z0)))


def _solid(wp):
    shape = wp.val()
    sols = shape.Solids()
    return sols[0] if len(sols) == 1 else shape


def _ceil(v):
    return int(math.ceil(v - 1e-9))


def build(params):
    p = params
    W, H, D = p["W"], p["H"], p["D"]
    leg_h = p["leg_h"]
    t, back_t, div_t = p["t"], p["back_t"], p["divider_t"]
    door_t, shelf_t, g = p["door_t"], p["shelf_t"], p["door_gap"]
    back_mode, top_mode = p["back_mode"], p["top_mode"]
    has_top = top_mode != "none"

    Dc = D - door_t - g
    Hc = H - leg_h
    depth_panels = Dc - back_t if back_mode == "onset" else Dc  # sides/top/bottom depth
    inner_y = Dc - back_t  # shelves, walls depth

    # ---------- doors / bays ----------
    n_min = max(1, _ceil(W / p["door_max_w"]))
    layout = p.get("door_layout")
    if layout:
        layout = list(layout)
        while sum(layout) < n_min:
            layout.append(1)
        n = sum(layout)
    else:
        n = p.get("n_doors") or n_min
        n = max(n, n_min)
        layout = [1] * n
    cell = W / n

    # wall boundaries (between bays)
    boundaries = []
    acc = 0
    for b in layout[:-1]:
        acc += b
        boundaries.append(acc * cell)

    # ---------- carcass panels ----------
    panels = {}  # name -> workplane (for cutting holes)
    side_z0 = leg_h
    side_z1 = H - t if top_mode == "onset" else H
    panels["side_left"] = _box(0, t, 0, depth_panels, side_z0, side_z1)
    panels["side_right"] = _box(W - t, W, 0, depth_panels, side_z0, side_z1)
    panels["bottom"] = _box(t, W - t, 0, depth_panels, leg_h, leg_h + t)
    if top_mode == "inset":
        panels["top"] = _box(t, W - t, 0, depth_panels, H - t, H)
    elif top_mode == "onset":
        panels["top"] = _box(0, W, 0, depth_panels, H - t, H)

    # back
    if back_mode == "onset":
        panels["back"] = _box(0, W, Dc - back_t, Dc, leg_h, H)
    else:
        bz1 = H - t if has_top else H
        panels["back"] = _box(t, W - t, Dc - back_t, Dc, leg_h + t, bz1)

    # inner walls
    wall_z0 = leg_h + t
    wall_z1 = H - t if has_top else H
    div_names = []
    for i, xb in enumerate(boundaries):
        name = "divider_%d" % (i + 1)
        panels[name] = _box(xb - div_t / 2, xb + div_t / 2, 0, inner_y, wall_z0, wall_z1)
        div_names.append(name)

    # vertical panels sorted by x: (name, left_face, right_face)
    verts = [("side_left", 0, t)]
    for i, xb in enumerate(boundaries):
        verts.append((div_names[i], xb - div_t / 2, xb + div_t / 2))
    verts.append(("side_right", W - t, W))

    # ---------- shelves ----------
    clear_h = Hc - 2 * t if has_top else Hc - t
    bcm = p.get("bottom_clear_min")
    if p.get("n_shelves") is not None:
        k = max(0, int(p["n_shelves"]))
    else:
        bm = p["shelf_min_gap"] if bcm is None else max(bcm, p["shelf_min_gap"])
        k = max(0, int(math.floor((clear_h - bm) / (p["shelf_min_gap"] + shelf_t))))

    zb = leg_h + t
    shelf_zs = []  # bottom z of each shelf
    if k > 0:
        gap = (clear_h - k * shelf_t) / (k + 1)
        if bcm is not None and gap < bcm:
            g2 = (clear_h - bcm - k * shelf_t) / k
            for j in range(k):
                shelf_zs.append(zb + bcm + j * (shelf_t + g2))
        else:
            for j in range(k):
                shelf_zs.append(zb + gap + j * (gap + shelf_t))

    # pins
    shelf_depth = inner_y
    span = shelf_depth - 100
    n_pins = _ceil(span / p["pin_max_spacing"]) + 1
    pin_ys = [50 + i * span / (n_pins - 1) for i in range(n_pins)]
    pin_rad = 2.5

    shelves = []
    pins = []
    for bi in range(len(verts) - 1):
        lname, _, xl = verts[bi]
        rname, xr, _ = verts[bi + 1]
        for zs in shelf_zs:
            shelves.append(_solid(_box(xl + 1, xr - 1, 0, shelf_depth, zs, zs + shelf_t)))
            pz = zs - 2.5
            for y in pin_ys:
                # pin in the left panel of the bay: 8 in the panel, 6 out
                hole_l = cq.Workplane("YZ", origin=(xl - 8, y, pz)).circle(pin_rad).extrude(8)
                panels[lname] = panels[lname].cut(hole_l)
                pin_l = cq.Workplane("YZ", origin=(xl - 8, y, pz)).circle(pin_rad).extrude(14)
                pins.append(_solid(pin_l))
                # pin in the right panel of the bay
                hole_r = cq.Workplane("YZ", origin=(xr, y, pz)).circle(pin_rad).extrude(8)
                panels[rname] = panels[rname].cut(hole_r)
                pin_r = cq.Workplane("YZ", origin=(xr - 6, y, pz)).circle(pin_rad).extrude(14)
                pins.append(_solid(pin_r))

    # ---------- doors ----------
    hinge = []
    if all(b == 1 for b in layout):
        for i in range(n):
            hinge.append("L" if i % 2 == 0 else "R")
        if n > 1 and n % 2 == 1:
            hinge[-1] = "R"
    else:
        idx = 0
        for b in layout:
            if b == 2:
                hinge.append("L")
                hinge.append("R")
            else:
                cx = (idx + 0.5) * cell
                hinge.append("L" if cx <= W / 2 else "R")
            idx += b

    dw = cell - 2 * g
    dh = Hc - 2 * g
    hcount = 2 if dh <= 900 else (3 if dh <= 1600 else 4)
    doors = []
    for i in range(n):
        x0 = i * cell + g
        z0 = leg_h + g
        door = _box(x0, x0 + dw, -(g + door_t), -g, z0, z0 + dh)
        cx = x0 + 22.5 if hinge[i] == "L" else x0 + dw - 22.5
        for h in range(hcount):
            cz = z0 + 100 + h * (dh - 200) / (hcount - 1)
            cup = cq.Workplane("XZ", origin=(cx, -g, cz)).circle(17.5).extrude(12)
            door = door.cut(cup)
        doors.append(_solid(door))

    # ---------- legs ----------
    leg_r = 20
    lx0, lx1 = 30 + leg_r, W - 30 - leg_r
    ly0, ly1 = 30 + leg_r, Dc - 30 - leg_r
    nx = _ceil((lx1 - lx0) / p["leg_max_spacing"]) + 1
    ny = _ceil((ly1 - ly0) / p["leg_max_spacing"]) + 1
    legs = []
    for ix in range(nx):
        x = lx0 + ix * (lx1 - lx0) / (nx - 1)
        for iy in range(ny):
            y = ly0 + iy * (ly1 - ly0) / (ny - 1)
            legs.append(_solid(cq.Workplane("XY", origin=(x, y, 0)).circle(leg_r).extrude(leg_h)))

    # ---------- collect ----------
    parts = []
    for name in ("side_left", "side_right", "top", "bottom", "back"):
        if name in panels:
            parts.append((name, _solid(panels[name])))
    for name in div_names:
        parts.append((name, _solid(panels[name])))
    for i, s in enumerate(shelves):
        parts.append(("shelf_%d" % (i + 1), s))
    for i, s in enumerate(pins):
        parts.append(("pin_%d" % (i + 1), s))
    for i, s in enumerate(doors):
        parts.append(("door_%d" % (i + 1), s))
    for i, s in enumerate(legs):
        parts.append(("leg_%d" % (i + 1), s))
    return parts


if __name__ == "__main__":
    result = build(PARAMS)
    print(len(result), "parts")
