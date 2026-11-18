import math
import cadquery as cq

PARAMS = {
    "W": 600, "H": 850, "D": 580,
    "leg_h": 100,
    "back_mode": "onset",
    "top_mode": "onset",
    "rail_d": 100,
    "t": 18, "back_t": 10, "divider_t": 18, "door_t": 22, "shelf_t": 30,
    "door_gap": 2, "door_max_w": 600,
    "n_doors": 0,
    "door_layout": None,
    "single_door_hinge": None,
    "n_shelves": 0,
    "shelf_min_gap": 320,
    "bottom_clear_min": None,
    "pin_max_spacing": 500,
    "leg_max_spacing": 600,
    "leg_d": 40, "leg_edge_gap": 30,
    "n_drawers": 4,
    "slide_clear": 12.5,      # 서랍 레일 한쪽 여유
    "drawer_side_t": 16,
    "drawer_bottom_t": 8,
    "drawer_depth_max": 500,
    "drawer_z_clear": 10,     # 서랍 상자 아래/위 여유
    "notes": [
        "서랍장: 문 대신 서랍 4단. 문/힌지/칸막이/선반/선반핀은 없음 (n_doors=0, n_shelves=0)",
        "서랍 앞판: 문 규칙 이월. 한 칸 = 높이/4, 사방 door_gap 2 여유, 두께 22, 폭 596(600 이하)",
        "상판 있음(top_mode onset): 하부장 규칙(상판 없음)은 일반 수납장에는 적용하지 않고 상판을 W 폭으로 덮음. 측판은 H-t까지",
        "다릿발 유지: 하부장 규칙 그대로 지름 40, 높이 100, 모서리 30 간격, 간격 600 이하 (4개)",
        "서랍 상자: 레일 한쪽 12.5 여유, 옆판 16, 바닥 8, 깊이 500(내경 깊이에 맞춰 제한), 앞/뒤판은 옆판 사이",
        "서랍 상자 높이는 안쪽 높이를 4등분한 칸에서 위아래 10씩 띄움. 손잡이는 고객 요청 없어 생략",
        "뒤판 onset(기본값) 유지: 뒤판 10mm가 측판/상판/하판 뒤를 덮음",
    ],
}


def _box(x0, x1, y0, y1, z0, z1):
    return (cq.Workplane("XY")
            .box(x1 - x0, y1 - y0, z1 - z0, centered=False)
            .translate((x0, y0, z0)).val())


def build(params):
    p = params
    W, H, D = p["W"], p["H"], p["D"]
    t, bt, dt, g = p["t"], p["back_t"], p["door_t"], p["door_gap"]
    lh = p["leg_h"]
    Dc = D - dt - g
    Dd = Dc - bt          # depth of sides/top/bottom (back onset)
    parts = []

    # carcass
    top_z = H - t
    parts.append(("side_left", _box(0, t, 0, Dd, lh, top_z)))
    parts.append(("side_right", _box(W - t, W, 0, Dd, lh, top_z)))
    parts.append(("bottom", _box(t, W - t, 0, Dd, lh, lh + t)))
    parts.append(("top", _box(0, W, 0, Dd, H - t, H)))
    parts.append(("back", _box(0, W, Dd, Dc, lh, H)))

    # drawers
    n = p["n_drawers"]
    cell = (H - lh) / n
    inner_h = H - lh - 2 * t
    pitch = inner_h / n
    inner_w = W - 2 * t
    box_w = inner_w - 2 * p["slide_clear"]
    bx0 = t + p["slide_clear"]
    bx1 = bx0 + box_w
    box_d = min(p["drawer_depth_max"], Dd - 30)
    st, bot = p["drawer_side_t"], p["drawer_bottom_t"]
    for i in range(n):
        k = i + 1
        fz0 = lh + i * cell + g
        parts.append((f"drawer_front_{k}",
                      _box(g, W - g, -(g + dt), -g, fz0, fz0 + cell - 2 * g)))
        z0 = lh + t + i * pitch + p["drawer_z_clear"]
        h = pitch - 2 * p["drawer_z_clear"]
        parts.append((f"drawer_{k}_side_left", _box(bx0, bx0 + st, 0, box_d, z0, z0 + h)))
        parts.append((f"drawer_{k}_side_right", _box(bx1 - st, bx1, 0, box_d, z0, z0 + h)))
        parts.append((f"drawer_{k}_bottom", _box(bx0 + st, bx1 - st, 0, box_d, z0, z0 + bot)))
        parts.append((f"drawer_{k}_end_inner", _box(bx0 + st, bx1 - st, 0, st, z0 + bot, z0 + h)))
        parts.append((f"drawer_{k}_back", _box(bx0 + st, bx1 - st, box_d - st, box_d, z0 + bot, z0 + h)))

    # legs
    r = p["leg_d"] / 2
    off = p["leg_edge_gap"] + r
    def line(a, b):
        span = b - a
        c = math.ceil(span / p["leg_max_spacing"]) + 1
        return [a + span * j / (c - 1) for j in range(c)]
    xs = line(off, W - off)
    ys = line(off, Dc - off)
    idx = 1
    for y in ys:
        for x in xs:
            leg = cq.Workplane("XY").circle(r).extrude(lh).translate((x, y, 0)).val()
            parts.append((f"leg_{idx}", leg))
            idx += 1
    return parts
