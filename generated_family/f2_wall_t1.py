import math
import cadquery as cq

PARAMS = {
    "W": 1200, "H": 700, "D": 350,
    "leg_h": 0,
    "back_mode": "onset",
    "top_mode": "inset",
    "rail_d": 100,
    "t": 18, "back_t": 10, "divider_t": 18, "door_t": 22, "shelf_t": 30,
    "door_gap": 2, "door_max_w": 600,
    "n_doors": None, "door_layout": None, "single_door_hinge": None,
    "n_shelves": None, "shelf_min_gap": 320, "bottom_clear_min": None,
    "pin_max_spacing": 500, "leg_max_spacing": 600,
    "hinge_cup_d": 35, "hinge_cup_depth": 12, "hinge_edge": 22.5, "hinge_end": 100,
    "pin_d": 5, "pin_hole_depth": 8, "pin_out": 6, "pin_edge": 50,
    "hang_rail": True,
    "notes": [
        "다릿발 없음: 벽에 거는 상부장이라 다릿발 규칙 제외, leg_h=0 (캐비닛이 z=0~H, 바닥 기준은 설치 높이에서 따로 정함)",
        "상판 있음: 하부장 규칙(상판 없음)은 제외하고, 일반 수납장처럼 top_mode=inset으로 옆판 사이에 상판을 넣음 (싱크 위 상부장이라 위가 막혀야 함)",
        "뒷판 onset, 문 onset, 판재 두께(t 18, 뒷판 10, 문 22)는 기본 규칙 그대로 적용",
        "문 개수: 폭 1200 / 최대 600 = 2개(양문), 문 간격 2mm, 경첩 컵 문당 2개(문 높이 696 <= 900) 규칙 그대로 적용",
        "가운데 칸막이 1개: 양문 사이 이음부 뒤에 기본 규칙대로 세움 (폭 1200 상부장의 처짐을 막는 역할도 함)",
        "선반 자동 0개: 내경 높이 664에서 선반 1개를 넣으면 칸이 317로 최소 320보다 낮아져 기본 규칙(최소 320)대로 선반 없음. 필요하면 n_shelves=1로 지정",
        "벽 걸이용 보강대(hanging_rail) 추가: 뒷판 10mm만으로는 무게를 못 받으므로 상판 아래 뒤쪽에 폭 100(rail_d), 두께 t의 보강대를 칸막이 사이마다 넣음 (고정 나사 위치)",
        "하부장의 상판 레일 대신 상판은 전체 깊이 판으로 처리하고 레일 규칙은 제외",
    ],
}


def _solid(wp):
    v = wp.val()
    if isinstance(v, cq.Solid):
        return v
    return wp.solids().vals()[0]


def _box(x0, x1, y0, y1, z0, z1):
    return (cq.Workplane("XY")
            .box(x1 - x0, y1 - y0, z1 - z0, centered=False)
            .translate((x0, y0, z0)))


def build(params):
    p = params
    W, H, D = p["W"], p["H"], p["D"]
    leg_h, t, back_t = p["leg_h"], p["t"], p["back_t"]
    dt, door_t, shelf_t, gap = p["divider_t"], p["door_t"], p["shelf_t"], p["door_gap"]
    Dc = D - door_t - gap
    top_mode, back_mode = p["top_mode"], p["back_mode"]
    parts = []

    # ---- carcass extents
    inner_depth = Dc - back_t
    carc_d = inner_depth if back_mode == "onset" else Dc
    z_bot = leg_h
    if top_mode == "onset":
        side_top = H - t
    else:
        side_top = H
    if top_mode == "none":
        ceil_z = H
    elif top_mode == "rail":
        ceil_z = H - t
    else:
        ceil_z = H - t
    clear_h = ceil_z - (leg_h + t)

    # ---- doors / bays
    layout = p["door_layout"]
    if layout:
        n = sum(layout)
    elif p["n_doors"]:
        n = max(p["n_doors"], math.ceil(W / p["door_max_w"]))
        layout = [1] * n
    else:
        n = max(1, math.ceil(W / p["door_max_w"]))
        layout = [1] * n
    cell = W / n

    # divider centers
    div_x = []
    j = 0
    for b in layout[:-1]:
        j += b
        div_x.append(j * cell)

    # ---- panel solids (cut later for pin holes)
    panels = {}
    panels["side_left"] = _box(0, t, 0, carc_d, z_bot, side_top)
    panels["side_right"] = _box(W - t, W, 0, carc_d, z_bot, side_top)
    for i, x in enumerate(div_x, start=1):
        panels["divider_%d" % i] = _box(x - dt / 2, x + dt / 2, 0, inner_depth,
                                        leg_h + t, ceil_z)

    # bays: (x_left_face, x_right_face, left_panel, right_panel)
    edges = [(t, "side_left")]
    bays = []
    left_x, left_name = t, "side_left"
    for i, x in enumerate(div_x, start=1):
        bays.append((left_x, x - dt / 2, left_name, "divider_%d" % i))
        left_x, left_name = x + dt / 2, "divider_%d" % i
    bays.append((left_x, W - t, left_name, "side_right"))

    # ---- shelves
    k_auto = max(0, int((clear_h - p["shelf_min_gap"]) // (p["shelf_min_gap"] + shelf_t)))
    bcm = p["bottom_clear_min"]
    if bcm:
        k_auto = max(0, int((clear_h - max(bcm, p["shelf_min_gap"])) // (p["shelf_min_gap"] + shelf_t)))
    k = p["n_shelves"] if p["n_shelves"] is not None else k_auto
    base = leg_h + t
    shelf_bottoms = []
    if k > 0:
        if bcm and p["n_shelves"] is None:
            sp = (clear_h - k * shelf_t) / (k + 1)
            if sp < bcm:
                rest = (clear_h - bcm - k * shelf_t) / k
                for i in range(k):
                    shelf_bottoms.append(base + bcm + i * (rest + shelf_t))
            else:
                shelf_bottoms = [base + (i + 1) * sp + i * shelf_t for i in range(k)]
        else:
            sp = (clear_h - k * shelf_t) / (k + 1)
            shelf_bottoms = [base + (i + 1) * sp + i * shelf_t for i in range(k)]

    shelves = []
    pins = []
    span = inner_depth - 2 * p["pin_edge"]
    m = math.ceil(span / p["pin_max_spacing"]) + 1
    ys = [p["pin_edge"] + i * span / (m - 1) for i in range(m)]
    pd, hd, po = p["pin_d"], p["pin_hole_depth"], p["pin_out"]
    for (xl, xr, lname, rname) in bays:
        for zb in shelf_bottoms:
            shelves.append(_box(xl + 1, xr - 1, 0, inner_depth, zb, zb + shelf_t))
            zc = zb - pd / 2
            for y in ys:
                for (xface, pname, direction) in ((xl, lname, 1), (xr, rname, -1)):
                    # direction +1: pin goes from the left panel face into the bay (+x)
                    x_start = xface - direction * hd
                    length = hd + po
                    cyl = (cq.Workplane("YZ").circle(pd / 2).extrude(length * direction)
                           .translate((x_start, y, zc)))
                    pins.append(_solid(cyl))
                    hole = (cq.Workplane("YZ").circle(pd / 2).extrude(hd * direction)
                            .translate((x_start, y, zc)))
                    panels[pname] = panels[pname].cut(hole)

    # ---- bottom, top, back
    parts_wp = []
    parts_wp.append(("bottom", _box(t, W - t, 0, carc_d, leg_h, leg_h + t)))
    if top_mode == "inset":
        parts_wp.append(("top", _box(t, W - t, 0, carc_d, H - t, H)))
    elif top_mode == "onset":
        parts_wp.append(("top", _box(0, W, 0, carc_d, H - t, H)))
    elif top_mode == "rail":
        parts_wp.append(("top_rail", _box(t, W - t, 0, p["rail_d"], H - t, H)))
    if back_mode == "onset":
        parts_wp.append(("back", _box(0, W, Dc - back_t, Dc, leg_h, H)))
    else:
        parts_wp.append(("back", _box(t, W - t, Dc - back_t, Dc, leg_h + t, ceil_z if top_mode != "none" else H)))

    for name in ("side_left", "side_right"):
        parts.append((name, _solid(panels[name])))
    for name, wp in parts_wp:
        parts.append((name, _solid(wp)))
    for i in range(1, len(div_x) + 1):
        parts.append(("divider_%d" % i, _solid(panels["divider_%d" % i])))

    # ---- hanging rails (between the vertical panels, under the top panel, at the back)
    if p.get("hang_rail") and top_mode in ("inset", "onset"):
        for i, (xl, xr, _, _) in enumerate(bays, start=1):
            y1 = inner_depth
            y0 = max(0, y1 - p["rail_d"])
            parts.append(("hanging_rail_%d" % i,
                          _solid(_box(xl, xr, y0, y1, ceil_z - t, ceil_z))))

    for i, s in enumerate(shelves, start=1):
        parts.append(("shelf_%d" % i, _solid(s)))
    for i, s in enumerate(pins, start=1):
        parts.append(("pin_%d" % i, s))

    # ---- doors
    hinges = []
    if p["single_door_hinge"]:
        hinges = [p["single_door_hinge"]] * n
    elif any(b == 2 for b in layout):
        idx = 0
        for b in layout:
            if b == 2:
                hinges += ["left", "right"]
            else:
                cx = (idx + 0.5) * cell
                hinges.append("left" if cx <= W / 2 else "right")
            idx += b
    else:
        for i in range(n):
            hinges.append("left" if i % 2 == 0 else "right")
        if n > 1 and n % 2 == 1:
            hinges[-1] = "right"

    dw = cell - 2 * gap
    dh = (H - leg_h) - 2 * gap
    nh = 2 if dh <= 900 else (3 if dh <= 1600 else 4)
    cup_r = p["hinge_cup_d"] / 2
    for i in range(n):
        x0 = i * cell + gap
        z0 = leg_h + gap
        door = _box(x0, x0 + dw, -(gap + door_t), -gap, z0, z0 + dh)
        cx = x0 + p["hinge_edge"] if hinges[i] == "left" else x0 + dw - p["hinge_edge"]
        e = p["hinge_end"]
        for h in range(nh):
            zc = z0 + e + h * (dh - 2 * e) / (nh - 1)
            cup = (cq.Workplane("XZ").center(cx, zc).circle(cup_r)
                   .extrude(p["hinge_cup_depth"]))  # XZ normal is -y: goes toward front
            cup = cup.translate((0, -gap, 0))
            door = door.cut(cup)
        parts.append(("door_%d" % (i + 1), _solid(door)))

    # ---- legs (only if leg_h > 0)
    if leg_h > 0:
        ld, edge = 40, 30
        xs0, xs1 = edge + ld / 2, W - edge - ld / 2
        ys0, ys1 = edge + ld / 2, Dc - edge - ld / 2
        nx = math.ceil((xs1 - xs0) / p["leg_max_spacing"]) + 1
        ny = math.ceil((ys1 - ys0) / p["leg_max_spacing"]) + 1
        c = 1
        for a in range(nx):
            for b in range(ny):
                x = xs0 + a * (xs1 - xs0) / (nx - 1)
                y = ys0 + b * (ys1 - ys0) / (ny - 1)
                leg = cq.Workplane("XY").circle(ld / 2).extrude(leg_h).translate((x, y, 0))
                parts.append(("leg_%d" % c, _solid(leg)))
                c += 1
    return parts
