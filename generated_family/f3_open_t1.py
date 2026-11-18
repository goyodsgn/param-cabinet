import math
import cadquery as cq

PARAMS = {
    "W": 800, "H": 1800, "D": 300,
    "leg_h": 60,
    "back_mode": "onset",
    "top_mode": "onset",
    "rail_d": 100,
    "t": 18, "back_t": 10, "divider_t": 18, "door_t": 22, "shelf_t": 30,
    "door_gap": 2, "door_max_w": 600,
    "n_doors": 0,
    "door_layout": None,
    "single_door_hinge": None,
    "n_shelves": None,
    "shelf_min_gap": 320,
    "bottom_clear_min": None,
    "pin_max_spacing": 500,
    "leg_max_spacing": 600,
    "leg_d": 40, "leg_corner_gap": 30,
    "notes": [
        "문 없음: 오픈 책장이라 문, 경첩, 칸막이(내벽)를 만들지 않음. 문 규칙은 적용 제외",
        "깊이: 문이 없어서 문 두께와 문 간격을 빼지 않고 D=300 전체를 본체 깊이로 사용",
        "상판 있음: 하부장 규칙(상판 없음)은 제외. 책장은 일반 수납장이라 onset 상판(W 폭, 옆판 위를 덮음)을 사용",
        "다릿발 유지, 높이 60: 키 큰 가구는 바닥 청소와 수평 조절을 위해 다릿발 규칙(지름 40, 모서리 30 간격, 간격 600 이하)을 그대로 적용하되 높이만 100에서 60으로 낮춤",
        "선반 개수 자동: 내경 높이 기준 선반 사이 간격 320 이상(책 높이 고려) 규칙을 그대로 적용해 균등 배치",
        "선반 두께 30 유지: 폭 764 책장이라 책 무게에 처짐을 줄이기 위해 기본 선반 두께를 그대로 사용",
        "뒤판 onset 10 유지: 뒤판이 옆판, 상판, 하판 뒤를 덮어 흔들림을 잡아줌",
        "선반핀 규칙 그대로: 선반 앞뒤 50 위치부터 간격 500 이하, 좌우 옆판에 구멍 8 깊이",
    ],
}


def _cyl_x(x0, length, y, z, d):
    return (cq.Workplane("YZ").workplane(offset=x0)
            .center(y, z).circle(d / 2.0).extrude(length))


def _box(x0, x1, y0, y1, z0, z1):
    return (cq.Workplane("XY")
            .box(x1 - x0, y1 - y0, z1 - z0, centered=False)
            .translate((x0, y0, z0)))


def build(params):
    p = params
    W, H, D = p["W"], p["H"], p["D"]
    leg_h, t, bt, st = p["leg_h"], p["t"], p["back_t"], p["shelf_t"]
    n_doors = p["n_doors"]
    if n_doors == 0:
        Dc = D
    else:
        Dc = D - p["door_t"] - p["door_gap"]
    inner_d = Dc - bt  # depth of sides/top/bottom/shelves (back onset)

    parts = []

    # ---- carcass dimensions
    top_mode = p["top_mode"]
    if top_mode == "onset":
        side_top = H - t
    else:
        side_top = H
    top_under = H - t  # underside of the top panel
    clear_h = top_under - (leg_h + t)

    # ---- shelves
    if p["n_shelves"] is None:
        bcm = p["bottom_clear_min"]
        gap_min = p["shelf_min_gap"]
        base = max(bcm, gap_min) if bcm else gap_min
        k = max(0, int(math.floor((clear_h - base) / (gap_min + st))))
    else:
        k = p["n_shelves"]
    space = (clear_h - k * st) / (k + 1)
    shelf_z = [leg_h + t + space * (i + 1) + st * i for i in range(k)]

    # pins per shelf
    span = inner_d - 100
    n_pin = int(math.ceil(span / p["pin_max_spacing"])) + 1
    pin_ys = [50 + span * j / (n_pin - 1) for j in range(n_pin)]
    pin_d = 5.0

    # ---- side panels (with pin holes)
    left = _box(0, t, 0, inner_d, leg_h, side_top)
    right = _box(W - t, W, 0, inner_d, leg_h, side_top)
    for z in shelf_z:
        for y in pin_ys:
            zc = z - pin_d / 2.0
            left = left.cut(_cyl_x(t - 8, 8, y, zc, pin_d))
            right = right.cut(_cyl_x(W - t, 8, y, zc, pin_d))
    parts.append(("side_left", left.val()))
    parts.append(("side_right", right.val()))

    # ---- bottom, top, back
    parts.append(("bottom", _box(t, W - t, 0, inner_d, leg_h, leg_h + t).val()))
    parts.append(("top", _box(0, W, 0, inner_d, H - t, H).val()))
    parts.append(("back", _box(0, W, Dc - bt, Dc, leg_h, H).val()))

    # ---- shelves + pins
    for i, z in enumerate(shelf_z):
        parts.append((f"shelf_{i+1}", _box(t + 1, W - t - 1, 0, inner_d, z, z + st).val()))
    n = 0
    for z in shelf_z:
        zc = z - pin_d / 2.0
        for y in pin_ys:
            n += 1
            parts.append((f"pin_{n}", _cyl_x(t - 8, 14, y, zc, pin_d).val()))
            n += 1
            parts.append((f"pin_{n}", _cyl_x(W - t - 6, 14, y, zc, pin_d).val()))

    # ---- legs
    g = p["leg_corner_gap"] + p["leg_d"] / 2.0
    sx = (W - g) - g
    sy = (Dc - g) - g
    nx = int(math.ceil(sx / p["leg_max_spacing"])) + 1
    ny = int(math.ceil(sy / p["leg_max_spacing"])) + 1
    m = 0
    for a in range(nx):
        for b in range(ny):
            m += 1
            x = g + sx * a / (nx - 1)
            y = g + sy * b / (ny - 1)
            leg = (cq.Workplane("XY").center(x, y)
                   .circle(p["leg_d"] / 2.0).extrude(leg_h))
            parts.append((f"leg_{m}", leg.val()))

    return parts
