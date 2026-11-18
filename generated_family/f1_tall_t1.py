import math
import cadquery as cq

PARAMS = {
    "W": 600, "H": 2100, "D": 600,
    "leg_h": 100,
    "back_mode": "onset",
    "top_mode": "inset",
    "rail_d": 100,
    "t": 18, "back_t": 10, "divider_t": 18, "door_t": 22, "shelf_t": 30,
    "door_gap": 2, "door_max_w": 600,
    "n_doors": None, "door_layout": None, "single_door_hinge": None,
    "n_shelves": None, "shelf_min_gap": 320, "bottom_clear_min": None,
    "pin_max_spacing": 500, "leg_max_spacing": 600,
    "leg_d": 40, "leg_corner_gap": 30,
    "notes": [
        "키큰장(전신장): 하부장이 아니라 일반 수납장으로 보고 상판을 얹음 - top_mode 'inset' (옆판 사이에 상판 18mm), 하부장의 '상판 없음' 규칙은 제외",
        "다릿발 유지: 바닥에 세우는 가구라서 하부장 규칙 그대로 leg_h 100, 지름 40, 모서리 30 간격, 중간 간격 600 이하",
        "문 규칙 유지: 폭 600이면 문 1개(셀 600 이하), 문 높이 1996mm라서 경첩 4개(1600 초과 규칙)",
        "문은 한 장으로 통짜 높이: 위아래 분할 도어는 규칙에 없어 만들지 않음. 1개짜리 문은 왼쪽 힌지(홀수 1개 규칙)",
        "선반 규칙 유지: 내부 높이 1964mm, 최소 간격 320 기준으로 4장, 선반 두께 30, 핀 규칙 그대로",
        "뒷판 onset 기본값 유지(뒷판이 옆/위/아래 뒤쪽을 덮음), 옆판은 바닥~상판 끝까지 전체 높이",
    ],
}


def _box(x0, y0, z0, dx, dy, dz):
    return cq.Workplane("XY").box(dx, dy, dz, centered=False).translate((x0, y0, z0))


def _cyl_x(x0, length, y, z, d):
    return (cq.Workplane("YZ").circle(d / 2.0).extrude(length)
            .translate((x0, y, z)))


def _cyl_y(y0, length, x, z, d):
    # extrudes from y0 toward +y by length (length may be negative)
    return (cq.Workplane("XZ").circle(d / 2.0).extrude(-length)
            .translate((x, y0, z)))


def _line(span_start, span_end, max_sp):
    span = span_end - span_start
    n = math.ceil(span / max_sp - 1e-9) + 1
    if n < 2:
        n = 2
    return [span_start + span * i / (n - 1) for i in range(n)]


def build(params):
    p = params
    W, H, D = p["W"], p["H"], p["D"]
    leg_h = p["leg_h"]
    t, back_t, div_t = p["t"], p["back_t"], p["divider_t"]
    door_t, shelf_t, gap = p["door_t"], p["shelf_t"], p["door_gap"]
    top_mode, back_mode = p["top_mode"], p["back_mode"]
    rail_d = p["rail_d"]
    Dc = D - door_t - gap
    parts = []

    # ---- carcass extents
    side_top = H - t if top_mode == "onset" else H
    carcass_depth = Dc - back_t if back_mode == "onset" else Dc
    inner_depth = Dc - back_t
    if top_mode in ("inset", "onset"):
        clear_top = H - t
    elif top_mode == "rail":
        clear_top = H - t
    else:
        clear_top = H
    clear_h = clear_top - (leg_h + t)

    # ---- doors / bays
    layout = p.get("door_layout")
    if layout:
        n = sum(layout)
    else:
        n = max(1, math.ceil(W / p["door_max_w"] - 1e-9))
        if p.get("n_doors"):
            n = max(n, p["n_doors"])
        layout = [1] * n
    cell = W / n

    # wall positions (between bays)
    wall_x = []
    j = 0
    for b in layout[:-1]:
        j += b
        wall_x.append(j * cell)

    # ---- vertical panels as boxes (x0, x1)
    side_l_x = (0, t)
    side_r_x = (W - t, W)
    panels = {
        "side_left": [0, t, side_top],
        "side_right": [W - t, W, side_top],
    }
    wall_top = clear_top
    for k, wx in enumerate(wall_x):
        panels["divider_%d" % (k + 1)] = [wx - div_t / 2.0, wx + div_t / 2.0, wall_top]

    # ---- bays: (left inner face, right inner face)
    bounds = [t] + [wx - div_t / 2.0 for wx in wall_x]
    bounds_r = [wx + div_t / 2.0 for wx in wall_x] + [W - t]
    bays = []
    for i in range(len(layout)):
        left_face = t if i == 0 else wall_x[i - 1] + div_t / 2.0
        right_face = W - t if i == len(layout) - 1 else wall_x[i] - div_t / 2.0
        bays.append((left_face, right_face))

    # ---- shelves
    if p.get("n_shelves") is not None:
        k = p["n_shelves"]
    else:
        bcm = p.get("bottom_clear_min")
        base = max(bcm, p["shelf_min_gap"]) if bcm else p["shelf_min_gap"]
        k = max(0, math.floor((clear_h - base) / (p["shelf_min_gap"] + shelf_t)))
    shelf_z = []  # bottom z of each shelf
    if k > 0:
        z0 = leg_h + t
        bcm = p.get("bottom_clear_min")
        g = (clear_h - k * shelf_t) / (k + 1)
        if bcm and p.get("n_shelves") is None and g < bcm:
            low = bcm
            g2 = (clear_h - low - k * shelf_t) / k
            for i in range(k):
                shelf_z.append(z0 + low + i * (g2 + shelf_t))
        else:
            for i in range(k):
                shelf_z.append(z0 + g * (i + 1) + shelf_t * i)

    # pins
    span = inner_depth - 100
    npin = math.ceil(span / p["pin_max_spacing"] - 1e-9) + 1
    pin_y = [50 + span * i / (npin - 1) for i in range(npin)]
    pin_d = 5.0
    pin_list = []
    holes = {name: [] for name in panels}

    def panel_for(face_x, left):
        # find panel whose inner face is face_x
        for name, (x0, x1, _) in panels.items():
            if left and abs(x1 - face_x) < 1e-6:
                return name
            if (not left) and abs(x0 - face_x) < 1e-6:
                return name
        return None

    for (lf, rf) in bays:
        for sz in shelf_z:
            pz = sz - 2.5
            for py in pin_y:
                # left panel: hole 8 deep into panel, pin sticks 6 into bay
                pin_list.append(_cyl_x(lf - 8, 14, py, pz, pin_d))
                holes[panel_for(lf, True)].append(_cyl_x(lf - 8, 8, py, pz, pin_d))
                pin_list.append(_cyl_x(rf - 6, 14, py, pz, pin_d))
                holes[panel_for(rf, False)].append(_cyl_x(rf, 8, py, pz, pin_d))

    # ---- panels (sides and dividers)
    for name, (x0, x1, ztop) in panels.items():
        if name.startswith("side"):
            zb = leg_h
            dep = carcass_depth
            ztop_ = ztop
        else:
            zb = leg_h + t
            dep = inner_depth
            ztop_ = ztop
        solid = _box(x0, 0, zb, x1 - x0, dep, ztop_ - zb)
        for h in holes[name]:
            solid = solid.cut(h)
        parts.append((name, solid.val()))

    # ---- bottom
    parts.append(("bottom", _box(t, 0, leg_h, W - 2 * t, carcass_depth, t).val()))

    # ---- top
    if top_mode == "rail":
        parts.append(("top_rail", _box(t, 0, H - t, W - 2 * t, rail_d, t).val()))
    elif top_mode == "inset":
        parts.append(("top", _box(t, 0, H - t, W - 2 * t, carcass_depth, t).val()))
    elif top_mode == "onset":
        parts.append(("top", _box(0, 0, H - t, W, carcass_depth, t).val()))

    # ---- back
    if back_mode == "onset":
        parts.append(("back", _box(0, Dc - back_t, leg_h, W, back_t, H - leg_h).val()))
    else:
        parts.append(("back", _box(t, Dc - back_t, leg_h + t, W - 2 * t, back_t, clear_h).val()))

    # ---- shelves
    idx = 1
    for (lf, rf) in bays:
        for sz in shelf_z:
            parts.append(("shelf_%d" % idx,
                          _box(lf + 1, 0, sz, (rf - lf) - 2, inner_depth, shelf_t).val()))
            idx += 1
    for i, pn in enumerate(pin_list):
        parts.append(("pin_%d" % (i + 1), pn.val()))

    # ---- doors
    hinges = []
    if p.get("single_door_hinge"):
        hinges = [p["single_door_hinge"]] * n
    elif p.get("door_layout") is None:
        for i in range(n):
            h = "left" if i % 2 == 0 else "right"
            if n > 1 and n % 2 == 1 and i == n - 1:
                h = "right"
            hinges.append(h)
    else:
        pos = 0
        for b in layout:
            if b == 2:
                hinges += ["left", "right"]
            else:
                c = (pos + 0.5) * cell
                hinges.append("left" if c <= W / 2.0 else "right")
            pos += b

    dw = cell - 2 * gap
    dh = (H - leg_h) - 2 * gap
    nh = 2 if dh <= 900 else (3 if dh <= 1600 else 4)
    hz = [100 + (dh - 200) * i / (nh - 1) for i in range(nh)]
    for i in range(n):
        x0 = i * cell + gap
        z0 = leg_h + gap
        door = _box(x0, -(gap + door_t), z0, dw, door_t, dh)
        cx = x0 + 22.5 if hinges[i] == "left" else x0 + dw - 22.5
        for zz in hz:
            door = door.cut(_cyl_y(-gap, -12, cx, z0 + zz, 35))
        parts.append(("door_%d" % (i + 1), door.val()))

    # ---- legs
    cg = p.get("leg_corner_gap", 30)
    ld = p.get("leg_d", 40)
    r = cg + ld / 2.0
    xs = _line(r, W - r, p["leg_max_spacing"])
    ys = _line(r, Dc - r, p["leg_max_spacing"])
    li = 1
    for x in xs:
        for y in ys:
            leg = cq.Workplane("XY").circle(ld / 2.0).extrude(leg_h).translate((x, y, 0))
            parts.append(("leg_%d" % li, leg.val()))
            li += 1

    return parts
