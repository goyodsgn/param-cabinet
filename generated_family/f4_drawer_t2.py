import math
import cadquery as cq

PARAMS = {
    "W": 900, "H": 850, "D": 580,
    "leg_h": 100,
    "back_mode": "onset",
    "top_mode": "inset",
    "t": 18, "back_t": 10, "divider_t": 18, "door_t": 22, "shelf_t": 30,
    "door_gap": 2, "door_max_w": 600,
    "n_doors": None,
    "door_layout": None,
    "single_door_hinge": None,
    "n_shelves": 0,
    "shelf_min_gap": 320,
    "bottom_clear_min": None,
    "pin_max_spacing": 500,
    "leg_max_spacing": 600,
    # 서랍장 전용 값
    "n_drawers": 3,
    "drawer_side_clear": 13,      # 서랍 박스 좌우 여유(레일 자리)
    "drawer_box_t": 15,           # 서랍 박스 옆/앞/뒤판 두께
    "drawer_bottom_t": 8,         # 서랍 바닥판 두께
    "drawer_box_lift": 25,        # 서랍 앞판 하단 위로 박스 바닥까지 높이
    "drawer_back_gap": 20,        # 서랍 박스 뒤쪽 최소 여유
    "leg_d": 40, "leg_edge_gap": 30,
    "notes": [
        "문 없음: 서랍장이라 도어, 경첩, 칸막이 벽 규칙은 제외하고 서랍 앞판 3개(drawer_front_1~3)로 대체함",
        "서랍 앞판: 도어 규칙 적용 - 사방 door_gap 2, 두께 22, 캐비닛 앞면 전체를 덮음. 높이는 (H-leg_h)/3 칸마다 균등 분할",
        "폭 900 서랍 앞판은 통짜 한 장: 서랍 앞판은 경첩 도어가 아니라 door_max_w 600 한도(문 처짐 방지)를 적용하지 않음. 앞판은 서랍 박스에 고정되고 가로로 열리지 않기 때문",
        "선반과 선반핀 없음: 서랍이 내부를 모두 사용하므로 n_shelves 0",
        "다릿발 유지: 기본 규칙 그대로 지름 40, 높이 100, 모서리 30 간격, 간격 600 이하 격자",
        "서랍 박스: 옆판 사이 양쪽 13mm 여유(측면 레일 자리), 판 두께 15, 바닥 8. 레일은 부품으로 넣지 않음",
        "서랍 박스 깊이: 내부 깊이에서 20 이상 남기고 50 단위 레일 길이로 내림(580 기준 500)",
        "손잡이 없음: 요청이 없어 생략, 필요하면 나중에 추가",
        "뒷판/상판: 기본값 유지 - 뒷판 onset, 상판 inset",
    ],
}


def _box(x, y, z, dx, dy, dz):
    return cq.Workplane("XY").box(dx, dy, dz, centered=False).translate((x, y, z)).val()


def build(params):
    p = params
    W, H, D = p["W"], p["H"], p["D"]
    leg_h, t, bt = p["leg_h"], p["t"], p["back_t"]
    dt, gap = p["door_t"], p["door_gap"]
    top_mode, back_mode = p["top_mode"], p["back_mode"]
    Dc = D - dt - gap
    parts = []

    has_top = top_mode != "none"
    onset_top = top_mode == "onset"
    side_depth = Dc - bt if back_mode == "onset" else Dc
    z_top_inner = H - t if has_top else H           # 안쪽 윗면
    side_top = H - t if onset_top else H
    inner_d = Dc - bt

    # 옆판
    parts.append(("side_left", _box(0, 0, leg_h, t, side_depth, side_top - leg_h)))
    parts.append(("side_right", _box(W - t, 0, leg_h, t, side_depth, side_top - leg_h)))
    # 바닥, 상판
    parts.append(("bottom", _box(t, 0, leg_h, W - 2 * t, side_depth, t)))
    if has_top:
        if onset_top:
            parts.append(("top", _box(0, 0, H - t, W, side_depth, t)))
        else:
            parts.append(("top", _box(t, 0, H - t, W - 2 * t, side_depth, t)))
    # 뒷판
    if back_mode == "onset":
        parts.append(("back", _box(0, Dc - bt, leg_h, W, bt, H - leg_h)))
    else:
        parts.append(("back", _box(t, Dc - bt, leg_h + t, W - 2 * t, bt, z_top_inner - leg_h - t)))

    # 서랍
    n = p["n_drawers"]
    cell = (H - leg_h) / n
    front_w = W - 2 * gap
    front_h = cell - 2 * gap
    sc, bxt, bbt = p["drawer_side_clear"], p["drawer_box_t"], p["drawer_bottom_t"]
    box_w = W - 2 * t - 2 * sc
    box_len = math.floor((inner_d - p["drawer_back_gap"]) / 50) * 50
    box_h = front_h - 2 * p["drawer_box_lift"] - 5
    bx = t + sc
    for i in range(n):
        k = i + 1
        fz = leg_h + i * cell + gap
        parts.append((f"drawer_front_{k}", _box(gap, -(gap + dt), fz, front_w, dt, front_h)))
        bz = fz + p["drawer_box_lift"]
        parts.append((f"drawer_{k}_side_left", _box(bx, 0, bz, bxt, box_len, box_h)))
        parts.append((f"drawer_{k}_side_right", _box(bx + box_w - bxt, 0, bz, bxt, box_len, box_h)))
        parts.append((f"drawer_{k}_box_fore", _box(bx + bxt, 0, bz, box_w - 2 * bxt, bxt, box_h)))
        parts.append((f"drawer_{k}_box_rear", _box(bx + bxt, box_len - bxt, bz, box_w - 2 * bxt, bxt, box_h)))
        parts.append((f"drawer_{k}_bottom", _box(bx + bxt, bxt, bz + 8, box_w - 2 * bxt, box_len - 2 * bxt, bbt)))

    # 다릿발
    r = p["leg_d"] / 2
    eg = p["leg_edge_gap"] + r
    nx = math.ceil((W - 2 * eg) / p["leg_max_spacing"]) + 1
    ny = math.ceil((Dc - 2 * eg) / p["leg_max_spacing"]) + 1
    xs = [eg + i * (W - 2 * eg) / (nx - 1) for i in range(nx)]
    ys = [eg + j * (Dc - 2 * eg) / (ny - 1) for j in range(ny)]
    c = 0
    for x in xs:
        for y in ys:
            c += 1
            leg = cq.Workplane("XY").circle(r).extrude(leg_h).translate((x, y, 0)).val()
            parts.append((f"leg_{c}", leg))
    return parts
