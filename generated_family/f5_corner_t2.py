import math
import cadquery as cq

PARAMS = {
    "W": 1000, "H": 850, "D": 580,
    "leg_h": 100,
    "back_mode": "onset",
    "top_mode": "rail",
    "rail_d": 100,
    "t": 18, "back_t": 10, "divider_t": 18, "door_t": 22, "shelf_t": 30,
    "door_gap": 2,
    "door_max_w": 600,
    "n_doors": None,
    "door_layout": None,
    "single_door_hinge": "right",
    "n_shelves": None,
    "shelf_min_gap": 320,
    "bottom_clear_min": None,
    "pin_max_spacing": 500,
    "leg_max_spacing": 600,
    "door_side": "left",
    "hinge_cup_d": 35, "hinge_cup_depth": 12, "hinge_edge": 22.5,
    "leg_d": 40, "leg_corner_gap": 30,
    "pin_d": 5, "pin_len": 14, "pin_hole_depth": 8, "pin_edge": 50,
    "shelf_clear": 1,
    "notes": [
        "코너장: 직사각 박스 하부장으로 만들고 ㄱ자는 옆 캐비닛이 앞면에 직각으로 붙어서 만듦",
        "문은 왼쪽 칸 하나(door_1), 오른쪽 칸은 같은 재질의 고정 막이판(blind_panel, 힌지 없음)",
        "문 힌지는 막이판과 가까운 오른쪽 모서리: 문이 왼쪽이면 오른쪽 힌지 규칙 적용 (single_door_hinge = right)",
        "칸 폭 W/n = 1000/2 = 500 (600 이하): 문 칸 폭 규칙을 막이판 칸에도 그대로 적용",
        "칸막이(divider) 없음: 막이판 뒤 공간은 문을 열고 안쪽으로 손이 닿아야 하므로 벽으로 막지 않음",
        "선반은 막힌 칸 없이 한 칸(전체 내경 폭)으로 보고 1세트만 배치, 핀 규칙은 그대로 적용",
        "상판 없음: 하부장 규칙 그대로 앞 상부 레일(top_rail)만 둠, 다릿발 규칙 그대로 적용",
    ],
}


def _box(x0, x1, y0, y1, z0, z1):
    return cq.Workplane("XY").box(x1 - x0, y1 - y0, z1 - z0, centered=False) \
        .translate((x0, y0, z0)).val()


def _cyl(r, h, x, y, z, d):
    return cq.Solid.makeCylinder(r, h, cq.Vector(x, y, z), cq.Vector(*d))


def _cut(a, b):
    return a.cut(b).Solids()[0]


def build(params):
    p = params
    W, H, D = p["W"], p["H"], p["D"]
    leg_h, t, back_t = p["leg_h"], p["t"], p["back_t"]
    door_t, gap, shelf_t = p["door_t"], p["door_gap"], p["shelf_t"]
    Dc = D - door_t - gap
    z0, z1 = leg_h, H
    ch = H - leg_h
    parts = []

    # carcass depth of panels
    if p["back_mode"] == "onset":
        pd = Dc - back_t
    else:
        pd = Dc
    inner_d = Dc - back_t

    # shelves (single bay, full inner width)
    clear_h = ch - 2 * t if p["top_mode"] != "none" else ch - t
    if p["n_shelves"] is not None:
        k = p["n_shelves"]
    else:
        lowest = max(p["bottom_clear_min"] or 0, p["shelf_min_gap"])
        k = max(0, int((clear_h - lowest) // (p["shelf_min_gap"] + shelf_t)))
    sp = (clear_h - k * shelf_t) / (k + 1) if k else 0
    shelf_bottoms = [z0 + t + (i + 1) * sp + i * shelf_t for i in range(k)]

    sh_d = inner_d
    span = sh_d - 2 * p["pin_edge"]
    npin = math.ceil(span / p["pin_max_spacing"]) + 1
    pin_ys = [p["pin_edge"] + span * j / (npin - 1) for j in range(npin)]
    r_pin = p["pin_d"] / 2

    # side panels with pin holes
    sides = {}
    for name, xa, xb in (("side_left", 0, t), ("side_right", W - t, W)):
        s = _box(xa, xb, 0, pd, z0, z1)
        for zb in shelf_bottoms:
            for y in pin_ys:
                zc = zb - r_pin
                if name == "side_left":
                    h = _cyl(r_pin, p["pin_hole_depth"], t - p["pin_hole_depth"], y, zc, (1, 0, 0))
                else:
                    h = _cyl(r_pin, p["pin_hole_depth"], W - t, y, zc, (1, 0, 0))
                s = _cut(s, h)
        sides[name] = s
        parts.append((name, s))

    parts.append(("bottom", _box(t, W - t, 0, pd, z0, z0 + t)))
    if p["top_mode"] == "rail":
        parts.append(("top_rail", _box(t, W - t, 0, p["rail_d"], H - t, H)))
    if p["back_mode"] == "onset":
        parts.append(("back", _box(0, W, Dc - back_t, Dc, z0, z1)))
    else:
        parts.append(("back", _box(t, W - t, Dc - back_t, Dc, z0 + t, z1)))

    # shelves and pins
    for i, zb in enumerate(shelf_bottoms):
        parts.append((f"shelf_{i+1}", _box(t + p["shelf_clear"], W - t - p["shelf_clear"],
                                            0, sh_d, zb, zb + shelf_t)))
    n_pin = 0
    for zb in shelf_bottoms:
        for y in pin_ys:
            zc = zb - r_pin
            n_pin += 1
            parts.append((f"pin_{n_pin}", _cyl(r_pin, p["pin_len"], t - p["pin_hole_depth"], y, zc, (1, 0, 0))))
            n_pin += 1
            parts.append((f"pin_{n_pin}", _cyl(r_pin, p["pin_len"], W - t + p["pin_hole_depth"], y, zc, (-1, 0, 0))))

    # door cells
    n = p["n_doors"] or max(1, math.ceil(W / p["door_max_w"]))
    cell = W / n
    right = p["door_side"] == "right"
    if right:
        door_x0 = (n - 1) * cell + gap
        blind_x0, blind_x1 = gap, (n - 1) * cell - gap
    else:
        door_x0 = gap
        blind_x0, blind_x1 = cell + gap, W - gap
    door_w = cell - 2 * gap
    door_h = ch - 2 * gap
    dz0 = leg_h + gap
    y0, y1 = -(gap + door_t), -gap

    door = _box(door_x0, door_x0 + door_w, y0, y1, dz0, dz0 + door_h)
    nh = 2 if door_h <= 900 else (3 if door_h <= 1600 else 4)
    hinge_left = right  # hinge next to the blind panel
    cx = door_x0 + p["hinge_edge"] if hinge_left else door_x0 + door_w - p["hinge_edge"]
    for j in range(nh):
        zc = dz0 + 100 + (door_h - 200) * j / (nh - 1)
        cup = _cyl(p["hinge_cup_d"] / 2, p["hinge_cup_depth"], cx, y1 - p["hinge_cup_depth"], zc, (0, 1, 0))
        door = _cut(door, cup)
    parts.append(("door_1", door))
    if blind_x1 > blind_x0:
        parts.append(("blind_panel", _box(blind_x0, blind_x1, y0, y1, dz0, dz0 + door_h)))

    # legs
    ld, cg, ms = p["leg_d"], p["leg_corner_gap"], p["leg_max_spacing"]
    off = cg + ld / 2
    sx, sy = W - 2 * off, Dc - 2 * off
    nx = math.ceil(sx / ms) + 1
    ny = math.ceil(sy / ms) + 1
    c = 0
    for a in range(nx):
        for b in range(ny):
            c += 1
            parts.append((f"leg_{c}", _cyl(ld / 2, leg_h, off + sx * a / (nx - 1),
                                           off + sy * b / (ny - 1), 0, (0, 0, 1))))
    return parts
