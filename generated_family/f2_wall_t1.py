import math
import cadquery as cq

PARAMS = {
    "W": 1200,
    "H": 700,
    "D": 350,
    "leg_h": 0,
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
    "single_door_hinge": None,
    "n_shelves": None,
    "shelf_min_gap": 320,
    "bottom_clear_min": None,
    "pin_max_spacing": 500,
    "leg_max_spacing": 600,
    "hang_rail_h": 80,
    "hang_rail_t": 18,
    "notes": [
        "다릿발 없음: 벽에 거는 상부장이라 다릿발 규칙 제외, leg_h=0 (몸통이 z=0~H)",
        "상판 유지: '싱크대'는 장 아래 설치 위치라서 싱크 설치용 상판 없음 규칙은 적용하지 않고 기본 inset 상판 사용",
        "벽 고정용 걸이대(hanging_rail) 추가: 상판 아래 뒤쪽에 높이 80, 두께 18 보강대를 칸마다 넣어 벽에 나사로 고정",
        "문 규칙 유지: 폭 1200이라 문 2개(칸 600), 문 높이 696이라 경첩 2개, 가운데 칸막이 1개",
        "선반 없음: 내부 높이 664라 선반을 넣으면 칸 높이가 320 미만이 되어 기본 규칙(최소 320)상 선반 0개",
        "깊이 350: 문(22)+틈(2)을 빼 몸통 깊이 326, 상부장 표준 깊이에 맞음",
    ],
}


def _box(x0, x1, y0, y1, z0, z1):
    return (cq.Workplane("XY")
            .box(x1 - x0, y1 - y0, z1 - z0, centered=False)
            .translate((x0, y0, z0)))


def _cyl_x(x0, length, y, z, d):
    return cq.Workplane("YZ", origin=(x0, 0, 0)).center(y, z).circle(d / 2.0).extrude(length)


def build(params):
    p = params
    W, H, D = p["W"], p["H"], p["D"]
    leg_h, t, back_t = p["leg_h"], p["t"], p["back_t"]
    div_t, door_t, shelf_t = p["divider_t"], p["door_t"], p["shelf_t"]
    gap = p["door_gap"]
    top_mode, back_mode = p["top_mode"], p["back_mode"]
    Dc = D - door_t - gap
    y_in = Dc - back_t                      # back panel inner face
    ds = y_in if back_mode == "onset" else Dc  # depth of sides/top/bottom

    has_top = top_mode != "none"
    z_bot_top = leg_h + t                   # top face of bottom panel
    z_clear_top = H - t if has_top else H   # underside of top / carcass top
    clear_h = z_clear_top - z_bot_top

    # ---- door layout ----
    layout = p["door_layout"]
    if layout:
        n = sum(layout)
    else:
        n = max(1, math.ceil(W / p["door_max_w"]))
        if p["n_doors"]:
            n = max(n, p["n_doors"])
        layout = [1] * n
    cell = W / n

    # bays: (first cell index, count)
    bays = []
    c = 0
    for b in layout:
        bays.append((c, b))
        c += b

    # hinge sides
    hinges = []
    if p["single_door_hinge"]:
        hinges = [p["single_door_hinge"]] * n
    elif p["door_layout"]:
        for (c0, cnt) in bays:
            if cnt == 2:
                hinges += ["left", "right"]
            else:
                cx = (c0 + 0.5) * cell
                hinges.append("left" if cx <= W / 2 else "right")
    else:
        for i in range(n):
            hinges.append("left" if i % 2 == 0 else "right")
        if n > 1 and n % 2 == 1:
            hinges[-1] = "right"

    # ---- panels (as Workplane objects, so holes can be cut later) ----
    z_side_top = (H - t) if top_mode == "onset" else H
    panels = {}
    panels["side_left"] = _box(0, t, 0, ds, leg_h, z_side_top)
    panels["side_right"] = _box(W - t, W, 0, ds, leg_h, z_side_top)
    panels["bottom"] = _box(t, W - t, 0, ds, leg_h, leg_h + t)
    if top_mode == "inset":
        panels["top"] = _box(t, W - t, 0, ds, H - t, H)
    elif top_mode == "onset":
        panels["top"] = _box(0, W, 0, ds, H - t, H)
    if back_mode == "onset":
        panels["back"] = _box(0, W, Dc - back_t, Dc, leg_h, H)
    else:
        panels["back"] = _box(t, W - t, Dc - back_t, Dc, z_bot_top, z_clear_top)

    # inner walls between bays
    wall_x = []
    for k in range(1, len(bays)):
        j = bays[k][0]
        x = j * cell
        wall_x.append(x)
        panels["divider_%d" % k] = _box(x - div_t / 2, x + div_t / 2, 0, y_in, z_bot_top, z_clear_top)

    # bay inner faces (left face, right face, left panel name, right panel name)
    bay_info = []
    for k, (c0, cnt) in enumerate(bays):
        if k == 0:
            xl, ln = t, "side_left"
        else:
            xl, ln = wall_x[k - 1] + div_t / 2, "divider_%d" % k
        if k == len(bays) - 1:
            xr, rn = W - t, "side_right"
        else:
            xr, rn = wall_x[k] - div_t / 2, "divider_%d" % (k + 1)
        bay_info.append((xl, xr, ln, rn))

    # ---- shelf count and positions ----
    gmin = p["shelf_min_gap"]
    bcm = p["bottom_clear_min"]
    if p["n_shelves"] is not None:
        k_sh = p["n_shelves"]
    elif bcm:
        k_sh = max(0, math.floor((clear_h - max(bcm, gmin)) / (gmin + shelf_t)))
    else:
        k_sh = max(0, math.floor((clear_h - gmin) / (gmin + shelf_t)))

    shelf_z = []  # bottom z of each shelf
    if k_sh > 0:
        sp = (clear_h - k_sh * shelf_t) / (k_sh + 1)
        if bcm and p["n_shelves"] is None and sp < bcm:
            first = bcm
            rest = (clear_h - bcm - k_sh * shelf_t) / k_sh
            z = z_bot_top + first
            for i in range(k_sh):
                shelf_z.append(z)
                z += shelf_t + rest
        else:
            for i in range(k_sh):
                shelf_z.append(z_bot_top + sp * (i + 1) + shelf_t * i)

    shelves = []
    pins = []
    holes = {}  # panel name -> list of (x_face, y, z, direction)
    shelf_d = y_in
    span = shelf_d - 100
    n_pin = math.ceil(span / p["pin_max_spacing"]) + 1
    pin_ys = [50 + i * span / (n_pin - 1) for i in range(n_pin)]
    for (xl, xr, ln, rn) in bay_info:
        for zb in shelf_z:
            shelves.append(_box(xl + 1, xr - 1, 0, shelf_d, zb, zb + shelf_t))
            for y in pin_ys:
                zc = zb - 2.5
                pins.append(_cyl_x(xl - 8, 14, y, zc, 5))
                pins.append(_cyl_x(xr - 6, 14, y, zc, 5))
                holes.setdefault(ln, []).append((xl, y, zc, "L"))
                holes.setdefault(rn, []).append((xr, y, zc, "R"))

    for name, hl in holes.items():
        wp = panels[name]
        for (xf, y, zc, side) in hl:
            x0 = xf - 8 if side == "L" else xf
            wp = wp.cut(_cyl_x(x0, 8, y, zc, 5))
        panels[name] = wp

    parts = []
    for name, wp in panels.items():
        parts.append((name, wp.val()))

    # hanging rails (wall fixing), one per bay, under the top at the rear
    rail_h, rail_t = p["hang_rail_h"], p["hang_rail_t"]
    for k, (xl, xr, ln, rn) in enumerate(bay_info):
        r = _box(xl, xr, y_in - rail_t, y_in, z_clear_top - rail_h, z_clear_top)
        parts.append(("hanging_rail_%d" % (k + 1), r.val()))

    for i, s in enumerate(shelves):
        parts.append(("shelf_%d" % (i + 1), s.val()))
    for i, pn in enumerate(pins):
        parts.append(("pin_%d" % (i + 1), pn.val()))

    # ---- doors ----
    dw = cell - 2 * gap
    dh = (H - leg_h) - 2 * gap
    n_h = 2 if dh <= 900 else (3 if dh <= 1600 else 4)
    hz = [100 + i * (dh - 200) / (n_h - 1) for i in range(n_h)]
    for i in range(n):
        x0 = i * cell + gap
        z0 = leg_h + gap
        door = _box(x0, x0 + dw, -(gap + door_t), -gap, z0, z0 + dh)
        cx = x0 + 22.5 if hinges[i] == "left" else x0 + dw - 22.5
        for h in hz:
            cup = (cq.Workplane("XZ", origin=(0, -gap, 0))
                   .center(cx, z0 + h).circle(17.5).extrude(12))
            door = door.cut(cup)
        parts.append(("door_%d" % (i + 1), door.val()))

    # ---- legs ----
    if leg_h > 0:
        lx0, lx1 = 30 + 20, W - 50
        ly0, ly1 = 30 + 20, Dc - 50
        nx = math.ceil((lx1 - lx0) / p["leg_max_spacing"]) + 1
        ny = math.ceil((ly1 - ly0) / p["leg_max_spacing"]) + 1
        idx = 1
        for a in range(nx):
            for b in range(ny):
                x = lx0 + a * (lx1 - lx0) / (nx - 1)
                y = ly0 + b * (ly1 - ly0) / (ny - 1)
                leg = cq.Workplane("XY").center(x, y).circle(20).extrude(leg_h)
                parts.append(("leg_%d" % idx, leg.val()))
                idx += 1

    return parts
