import math
import cadquery as cq

PARAMS = {
    "W": 1400, "H": 1800, "D": 300,
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
    "bay_max_w": 800,
    "notes": [
        "문 없음: 오픈 책장이라 문, 경첩은 만들지 않음. 문 규칙은 적용 제외",
        "깊이: 문이 없어서 문 두께와 문 간격을 빼지 않고 D=300 전체를 본체 깊이로 사용",
        "상판 있음: 하부장 규칙(상판 없음)은 제외. 책장은 일반 수납장이라 onset 상판(W 폭, 옆판 위를 덮음)을 사용",
        "세로 칸막이 추가: 폭 1400이면 선반 한 장이 1364로 길어 책 무게에 처지므로 칸 폭 최대 800(bay_max_w)으로 나눠 가운데에 칸막이 1개를 세움",
        "칸막이 위치: 문 칸막이 규칙을 carry-over, 전체 폭을 칸 수로 균등 분할한 경계(x = W/2)에 중심을 둠. 두께 18",
        "선반은 칸마다 한 세트: 칸 폭 - 2(좌우 1 여유), 칸마다 같은 개수와 같은 높이로 균등 배치",
        "선반핀: 칸마다 선반 좌우 판(옆판 또는 칸막이)에 규칙대로 설치. 칸막이는 양쪽 면에 8 깊이 구멍(18 두께라 서로 관통하지 않음)",
        "다릿발 유지, 높이 60: 키 큰 가구는 바닥 청소와 수평 조절을 위해 다릿발 규칙(지름 40, 모서리 30 간격, 간격 600 이하)을 그대로 적용하되 높이만 100에서 60으로 낮춤. 폭이 넓어져 폭 방향 4개",
        "선반 개수 자동: 내경 높이 기준 선반 사이 간격 320 이상(책 높이 고려) 규칙을 그대로 적용해 균등 배치",
        "선반 두께 30 유지: 책 무게에 처짐을 줄이기 위해 기본 선반 두께를 그대로 사용",
        "뒤판 onset 10 유지: 뒤판이 옆판, 상판, 하판 뒤를 덮어 흔들림을 잡아줌",
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
    dt = p["divider_t"]
    if p["n_doors"] == 0:
        Dc = D
    else:
        Dc = D - p["door_t"] - p["door_gap"]
    inner_d = Dc - bt  # depth of sides/top/bottom/dividers/shelves (back onset)

    parts = []

    # ---- carcass heights
    side_top = H - t if p["top_mode"] == "onset" else H
    clear_h = (H - t) - (leg_h + t)

    # ---- bays (vertical dividers between them)
    n_bays = max(1, int(math.ceil(W / p["bay_max_w"])))
    cell = W / n_bays
    bounds = []  # (xl, xr) clear x-range of each bay
    for i in range(n_bays):
        xl = t if i == 0 else i * cell + dt / 2.0
        xr = W - t if i == n_bays - 1 else (i + 1) * cell - dt / 2.0
        bounds.append((xl, xr))

    # ---- shelves (same set in every bay)
    if p["n_shelves"] is None:
        bcm = p["bottom_clear_min"]
        gap_min = p["shelf_min_gap"]
        base = max(bcm, gap_min) if bcm else gap_min
        k = max(0, int(math.floor((clear_h - base) / (gap_min + st))))
    else:
        k = p["n_shelves"]
    space = (clear_h - k * st) / (k + 1)
    shelf_z = [leg_h + t + space * (i + 1) + st * i for i in range(k)]

    span = inner_d - 100
    n_pin = int(math.ceil(span / p["pin_max_spacing"])) + 1
    pin_ys = [50 + span * j / (n_pin - 1) for j in range(n_pin)]
    pin_d = 5.0

    # ---- hole cutters per vertical panel
    # panels: 0 = left side, 1..n_bays-1 = dividers, n_bays = right side
    # the panel left of a bay ends at xl (hole spans xl-8..xl),
    # the panel right of a bay starts at xr (hole spans xr..xr+8)
    cuts = [[] for _ in range(n_bays + 1)]
    for bi, (xl, xr) in enumerate(bounds):
        for z in shelf_z:
            zc = z - pin_d / 2.0
            for y in pin_ys:
                cuts[bi].append(_cyl_x(xl - 8, 8, y, zc, pin_d))
                cuts[bi + 1].append(_cyl_x(xr, 8, y, zc, pin_d))

    def drill(panel, idx):
        for c in cuts[idx]:
            panel = panel.cut(c)
        return panel

    # ---- side panels
    left = drill(_box(0, t, 0, inner_d, leg_h, side_top), 0)
    right = drill(_box(W - t, W, 0, inner_d, leg_h, side_top), n_bays)
    parts.append(("side_left", left.val()))
    parts.append(("side_right", right.val()))

    # ---- dividers
    for j in range(1, n_bays):
        x0 = j * cell - dt / 2.0
        d = drill(_box(x0, x0 + dt, 0, inner_d, leg_h + t, H - t), j)
        parts.append((f"divider_{j}", d.val()))

    # ---- bottom, top, back
    parts.append(("bottom", _box(t, W - t, 0, inner_d, leg_h, leg_h + t).val()))
    parts.append(("top", _box(0, W, 0, inner_d, H - t, H).val()))
    parts.append(("back", _box(0, W, Dc - bt, Dc, leg_h, H).val()))

    # ---- shelves + pins
    s = 0
    n = 0
    for (xl, xr) in bounds:
        for z in shelf_z:
            s += 1
            parts.append((f"shelf_{s}", _box(xl + 1, xr - 1, 0, inner_d, z, z + st).val()))
            zc = z - pin_d / 2.0
            for y in pin_ys:
                n += 1
                parts.append((f"pin_{n}", _cyl_x(xl - 8, 14, y, zc, pin_d).val()))
                n += 1
                parts.append((f"pin_{n}", _cyl_x(xr - 6, 14, y, zc, pin_d).val()))

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
