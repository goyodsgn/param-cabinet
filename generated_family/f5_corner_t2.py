import math
import cadquery as cq

PARAMS = {
    "W": 1000, "H": 850, "D": 580,
    "leg_h": 100,
    "back_mode": "onset",
    "top_mode": "rail",
    "rail_d": 100,
    "t": 18, "back_t": 10, "divider_t": 18, "door_t": 22, "shelf_t": 30,
    "door_gap": 2, "door_max_w": 600,
    "n_doors": None,
    "door_layout": None,
    "single_door_hinge": "left",
    "n_shelves": None,
    "shelf_min_gap": 320,
    "bottom_clear_min": None,
    "pin_max_spacing": 500,
    "leg_max_spacing": 600,
    "leg_d": 40, "leg_corner_gap": 30,
    "pin_d": 5, "pin_len": 14, "pin_hole_depth": 8, "pin_edge": 50,
    "hinge_cup_d": 35, "hinge_cup_depth": 12, "hinge_edge": 22.5, "hinge_end": 100,
    "corner_door_side": "left",
    "notes": [
        "코너장 구조: ㄱ자 모서리용 직육면체 하부장이며 L자 형상이 아님. 상판 없음(하부장 규칙), 앞 상부 레일만 적용.",
        "정면 분할: 문 칸 폭 규칙(ceil(1000/600)=2칸, 칸당 500)을 그대로 적용해 왼쪽 칸에 문 1개,오른쪽 칸은 이웃 캐비닛에 가려지는 고정 blind_panel(경첩 없음).",
        "문은 왼쪽 요청에 따라 왼쪽 칸에 배치하고 경첩도 왼쪽(바깥쪽)에 둠: 열었을 때 이웃 캐비닛과 부딪히지 않음.",
        "blind_panel 크기는 문과 동일(같은 칸 폭, 문 간격 2 적용)하고 문과 같은 면에 놓아 정면이 일체로 보이게 함.",
        "칸막이 없음: 칸막이 규칙은 문 사이 이음매에 서는 벽인데, 이 모서리장은 문이 1개이고 막힌 쪽 안쪽은 문으로 연결된 하나의 수납공간이어야 해서 제외.",
        "선반: 칸막이가 없어 전체 내경 폭이 한 칸. 선반 개수는 규칙대로 계산(내경 높이 714 -> 1장), 폭은 내경 폭 - 2, 핀은 좌우 측판에 고정.",
        "다릿발: 기본 규칙 그대로(지름 40, 모서리 30 간격, 간격 600 이하 격자).",
        "경첩 컵: 문 높이 746 -> 2개, 경첩쪽(오른쪽) 모서리에서 22.5, 위아래 100.",
    ],
}


def _solid(wp):
    v = wp.val()
    if isinstance(v, cq.Solid):
        return v
    return v.Solids()[0]


def _box(x0, x1, y0, y1, z0, z1):
    return cq.Workplane("XY").box(x1 - x0, y1 - y0, z1 - z0, centered=False).translate((x0, y0, z0))


def _cyl_x(x0, y, z, d, length):
    return cq.Workplane("YZ", origin=(x0, 0, 0)).center(y, z).circle(d / 2.0).extrude(length)


def _line_positions(span, max_sp):
    n = math.ceil(span / max_sp - 1e-9) + 1
    if span <= 0:
        return [0.0]
    return [i * span / (n - 1) for i in range(n)]


def build(params):
    p = params
    W, H, D = p["W"], p["H"], p["D"]
    leg_h, t, back_t = p["leg_h"], p["t"], p["back_t"]
    door_t, gap, shelf_t = p["door_t"], p["door_gap"], p["shelf_t"]
    Dc = D - door_t - gap
    onset = p["back_mode"] == "onset"
    side_d = Dc - back_t if onset else Dc
    top_mode = p["top_mode"]
    parts = []

    # carcass height / sides
    z_bot, z_top = leg_h, H
    side_z1 = H
    if top_mode == "onset":
        side_z1 = H - t
    inner_top = H - t if top_mode in ("rail", "inset", "onset") else H
    clear_h = inner_top - (leg_h + t)

    # shelves count
    sg = p["shelf_min_gap"]
    if p["n_shelves"] is not None:
        k = p["n_shelves"]
    else:
        bcm = p["bottom_clear_min"]
        low = max(bcm, sg) if bcm else sg
        k = max(0, math.floor((clear_h - low) / (sg + shelf_t)))
    shelves_z = []
    if k > 0:
        gsp = (clear_h - k * shelf_t) / (k + 1)
        for i in range(1, k + 1):
            shelves_z.append(leg_h + t + i * gsp + (i - 1) * shelf_t)

    # pin positions along depth
    shelf_d = Dc - back_t
    span = shelf_d - 2 * p["pin_edge"]
    npin = math.ceil(span / p["pin_max_spacing"] - 1e-9) + 1
    pin_ys = [p["pin_edge"] + i * span / (npin - 1) for i in range(npin)]
    pr = p["pin_d"]
    hd, pl = p["pin_hole_depth"], p["pin_len"]

    side_l = _box(0, t, 0, side_d, z_bot, side_z1)
    side_r = _box(W - t, W, 0, side_d, z_bot, side_z1)
    pins = []
    for sz in shelves_z:
        pz = sz - pr / 2.0
        for y in pin_ys:
            side_l = side_l.cut(_cyl_x(t - hd, y, pz, pr, hd))
            side_r = side_r.cut(_cyl_x(W - t, y, pz, pr, hd))
            pins.append(_cyl_x(t - hd, y, pz, pr, pl))
            pins.append(_cyl_x(W - t - (pl - hd), y, pz, pr, pl))
    parts.append(("side_left", _solid(side_l)))
    parts.append(("side_right", _solid(side_r)))

    # bottom
    parts.append(("bottom", _solid(_box(t, W - t, 0, side_d, leg_h, leg_h + t))))
    # top
    if top_mode == "rail":
        parts.append(("top_rail", _solid(_box(t, W - t, 0, p["rail_d"], H - t, H))))
    elif top_mode == "inset":
        parts.append(("top", _solid(_box(t, W - t, 0, side_d, H - t, H))))
    elif top_mode == "onset":
        parts.append(("top", _solid(_box(0, W, 0, side_d, H - t, H))))
    # back
    if onset:
        parts.append(("back", _solid(_box(0, W, Dc - back_t, Dc, leg_h, H))))
    else:
        parts.append(("back", _solid(_box(t, W - t, Dc - back_t, Dc, leg_h + t, inner_top))))

    # shelves
    for i, sz in enumerate(shelves_z):
        parts.append(("shelf_%d" % (i + 1), _solid(_box(t + 1, W - t - 1, 0, shelf_d, sz, sz + shelf_t))))
    for i, pn in enumerate(pins):
        parts.append(("pin_%d" % (i + 1), _solid(pn)))

    # front: two cells, one door + one blind panel
    n = max(2, math.ceil(W / p["door_max_w"]))
    cell = W / n
    door_w = cell - 2 * gap
    door_h = (H - leg_h) - 2 * gap
    door_side = p["corner_door_side"]
    cell_door = n - 1 if door_side == "right" else 0
    hinge = door_side if p["single_door_hinge"] is None else p["single_door_hinge"]
    y0, y1 = -(gap + door_t), -gap

    def front_panel(ci):
        x0 = ci * cell + gap
        return x0, _box(x0, x0 + door_w, y0, y1, leg_h + gap, leg_h + gap + door_h)

    # blind panel(s): every cell except the door cell
    bi = 0
    for ci in range(n):
        if ci == cell_door:
            continue
        bi += 1
        _, bp = front_panel(ci)
        parts.append(("blind_panel" if bi == 1 else "blind_panel_%d" % bi, _solid(bp)))

    x0, door = front_panel(cell_door)
    nh = 2 if door_h <= 900 else (3 if door_h <= 1600 else 4)
    zb = leg_h + gap
    zs = [zb + p["hinge_end"] + i * (door_h - 2 * p["hinge_end"]) / (nh - 1) for i in range(nh)]
    cx = x0 + p["hinge_edge"] if hinge == "left" else x0 + door_w - p["hinge_edge"]
    for z in zs:
        cup = (cq.Workplane("XZ", origin=(0, y1, 0)).center(cx, z)
               .circle(p["hinge_cup_d"] / 2.0).extrude(p["hinge_cup_depth"]))
        door = door.cut(cup)
    parts.append(("door_1", _solid(door)))

    # legs
    cg, ld = p["leg_corner_gap"], p["leg_d"]
    off = cg + ld / 2.0
    xs = [off + v for v in _line_positions(W - 2 * off, p["leg_max_spacing"])]
    ys = [off + v for v in _line_positions(Dc - 2 * off, p["leg_max_spacing"])]
    li = 0
    for x in xs:
        for y in ys:
            li += 1
            leg = cq.Workplane("XY").center(x, y).circle(ld / 2.0).extrude(leg_h)
            parts.append(("leg_%d" % li, _solid(leg)))
    return parts
