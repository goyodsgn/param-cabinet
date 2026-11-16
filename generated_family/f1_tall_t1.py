import math
import cadquery as cq

PARAMS = {
    "W": 600,
    "H": 2100,
    "D": 600,
    "leg_h": 100,
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
    "notes": [
        "키큰장: 폭 600이라 문 1개(600 이하 규칙), 문 높이 약 1996이라 경첩 4개(1600 초과 규칙 적용).",
        "문은 위아래로 나누지 않고 통짜 한 장으로 함: 문 개수 규칙이 폭 기준이라 그대로 따름.",
        "다릿발 유지: 주방 하부장과 높이를 맞추는 바닥 설치 가구라 다릿발 규칙(100, 모서리 30 간격) 그대로 적용.",
        "상판 안붙임(inset)·뒤판 onset: 기본값 유지. 싱크 등 요청이 없어 상판 있음.",
        "선반 개수 자동: 내경 높이 1964 기준 규칙 공식으로 4개, 선반 두께 30 유지.",
        "선반핀 규칙 그대로: 선반 깊이 566, 한쪽 핀 2개씩.",
        "전도 방지: 높이 2100의 키큰장이므로 설치 시 벽 고정(앵커) 권장. 모델에는 넣지 않음.",
        "고정 선반 없음: 모든 선반은 핀으로 고정하는 규칙을 그대로 따름.",
    ],
}


def _box(x, y, z, dx, dy, dz):
    return cq.Solid.makeBox(dx, dy, dz, cq.Vector(x, y, z))


def _solid(shape):
    if isinstance(shape, cq.Solid):
        return shape
    return shape.Solids()[0]


def _cyl(r, h, x, y, z, dx, dy, dz):
    return cq.Solid.makeCylinder(r, h, cq.Vector(x, y, z), cq.Vector(dx, dy, dz))


def build(params):
    p = params
    W, H, D = p["W"], p["H"], p["D"]
    leg_h = p["leg_h"]
    t, back_t, div_t = p["t"], p["back_t"], p["divider_t"]
    door_t, shelf_t, gap = p["door_t"], p["shelf_t"], p["door_gap"]
    top_mode, back_mode = p["top_mode"], p["back_mode"]
    Dc = D - door_t - gap
    Din = Dc - back_t  # inner depth
    side_d = Din if back_mode == "onset" else Dc

    # ---- door layout / bays ----
    layout = p["door_layout"]
    if layout:
        n = sum(layout)
        bays = list(layout)
    else:
        n = p["n_doors"] or max(1, math.ceil(W / p["door_max_w"]))
        n = max(n, math.ceil(W / p["door_max_w"]))
        bays = [1] * n
    cw = W / n

    # bay boundaries (in door cells)
    bounds = [0]
    for b in bays:
        bounds.append(bounds[-1] + b)
    inner_bounds = bounds[1:-1]

    # ---- carcass vertical extents ----
    z_bot = leg_h
    z_top = H
    if top_mode == "onset":
        side_top = H - t
    else:
        side_top = H
    inner_z0 = leg_h + t
    inner_z1 = H - t if top_mode in ("inset", "onset") else H
    clear_h = inner_z1 - inner_z0

    sides = {
        "side_left": [_box(0, 0, z_bot, t, side_d, side_top - z_bot)],
        "side_right": [_box(W - t, 0, z_bot, t, side_d, side_top - z_bot)],
    }
    left = _box(0, 0, z_bot, t, side_d, side_top - z_bot)
    right = _box(W - t, 0, z_bot, t, side_d, side_top - z_bot)

    dividers = []
    for k, j in enumerate(inner_bounds):
        xc = j * cw
        dividers.append(_box(xc - div_t / 2, 0, inner_z0, div_t, Din, clear_h))

    # ---- bays: inner x range ----
    bay_ranges = []
    for bi in range(len(bays)):
        j0, j1 = bounds[bi], bounds[bi + 1]
        xl = t if bi == 0 else j0 * cw + div_t / 2
        xr = W - t if bi == len(bays) - 1 else j1 * cw - div_t / 2
        bay_ranges.append((xl, xr))

    # ---- shelves ----
    if p["n_shelves"] is not None:
        k = p["n_shelves"]
    else:
        bcm = p["bottom_clear_min"]
        base = max(bcm, p["shelf_min_gap"]) if bcm else p["shelf_min_gap"]
        k = max(0, math.floor((clear_h - base) / (p["shelf_min_gap"] + shelf_t)))
    shelf_z = []
    if k > 0:
        g = (clear_h - k * shelf_t) / (k + 1)
        bcm = p["bottom_clear_min"]
        if bcm and g < bcm and p["n_shelves"] is None:
            g1 = bcm
            g2 = (clear_h - bcm - k * shelf_t) / k
            shelf_z.append(inner_z0 + g1)
            for i in range(1, k):
                shelf_z.append(inner_z0 + g1 + shelf_t + g2 + (i - 1) * (g2 + shelf_t))
        else:
            for i in range(k):
                shelf_z.append(inner_z0 + g * (i + 1) + shelf_t * i)

    span = Din - 100
    npin = math.ceil(span / p["pin_max_spacing"]) + 1
    pin_ys = [50 + span * i / (npin - 1) for i in range(npin)]

    shelves = []
    pins = []
    # holes: collect per panel
    left_holes, right_holes = [], []
    div_holes = {j: [] for j in inner_bounds}
    for bi, (xl, xr) in enumerate(bay_ranges):
        j0, j1 = bounds[bi], bounds[bi + 1]
        for zs in shelf_z:
            shelves.append(_box(xl + 1, 0, zs, xr - xl - 2, Din, shelf_t))
            pz = zs - 2.5
            for y in pin_ys:
                # left pin (in panel at xl)
                pins.append(_cyl(2.5, 14, xl - 8, y, pz, 1, 0, 0))
                # right pin (in panel at xr)
                pins.append(_cyl(2.5, 14, xr - 6, y, pz, 1, 0, 0))
                hl = _cyl(2.5, 8, xl - 8, y, pz, 1, 0, 0)
                hr = _cyl(2.5, 8, xr, y, pz, 1, 0, 0)
                if bi == 0:
                    left_holes.append(hl)
                else:
                    div_holes[j0].append(hl)
                if bi == len(bays) - 1:
                    right_holes.append(hr)
                else:
                    div_holes[j1].append(hr)

    for h in left_holes:
        left = _solid(left.cut(h))
    for h in right_holes:
        right = _solid(right.cut(h))
    for idx, j in enumerate(inner_bounds):
        d = dividers[idx]
        for h in div_holes[j]:
            d = _solid(d.cut(h))
        dividers[idx] = d

    parts = [("side_left", left), ("side_right", right)]

    # top / bottom
    bottom_x0, bottom_w = t, W - 2 * t
    parts.append(("bottom", _box(t, 0, leg_h, W - 2 * t, side_d, t)))
    if top_mode == "inset":
        parts.append(("top", _box(t, 0, H - t, W - 2 * t, side_d, t)))
    elif top_mode == "onset":
        parts.append(("top", _box(0, 0, H - t, W, side_d, t)))

    # back
    if back_mode == "onset":
        parts.append(("back", _box(0, Dc - back_t, leg_h, W, back_t, H - leg_h)))
    else:
        parts.append(("back", _box(t, Dc - back_t, inner_z0, W - 2 * t, back_t, clear_h)))

    for i, d in enumerate(dividers):
        parts.append((f"divider_{i + 1}", d))
    for i, s in enumerate(shelves):
        parts.append((f"shelf_{i + 1}", s))
    for i, pn in enumerate(pins):
        parts.append((f"pin_{i + 1}", pn))

    # ---- doors ----
    hinge_sides = []
    if p["single_door_hinge"]:
        hinge_sides = [p["single_door_hinge"]] * n
    elif layout and any(b == 2 for b in bays):
        c = 0
        for b in bays:
            if b == 2:
                hinge_sides += ["left", "right"]
            else:
                xc = (c + 0.5) * cw
                hinge_sides.append("left" if xc <= W / 2 else "right")
            c += b
    else:
        for i in range(n):
            hinge_sides.append("left" if i % 2 == 0 else "right")
        if n > 1 and n % 2 == 1:
            hinge_sides[-1] = "right"

    door_w = cw - 2 * gap
    door_h = (H - leg_h) - 2 * gap
    n_h = 2 if door_h <= 900 else (3 if door_h <= 1600 else 4)
    for i in range(n):
        x0 = i * cw + gap
        door = _box(x0, -(gap + door_t), leg_h + gap, door_w, door_t, door_h)
        cx = x0 + 22.5 if hinge_sides[i] == "left" else x0 + door_w - 22.5
        for m in range(n_h):
            zc = leg_h + gap + 100 + (door_h - 200) * m / (n_h - 1)
            door = _solid(door.cut(_cyl(17.5, 12, cx, -gap, zc, 0, -1, 0)))
        parts.append((f"door_{i + 1}", door))

    # ---- legs ----
    lx0, lx1 = 30 + 20, W - 30 - 20
    ly0, ly1 = 30 + 20, Dc - 30 - 20
    nx = math.ceil((lx1 - lx0) / p["leg_max_spacing"]) + 1
    ny = math.ceil((ly1 - ly0) / p["leg_max_spacing"]) + 1
    c = 0
    for a in range(nx):
        for b in range(ny):
            x = lx0 + (lx1 - lx0) * a / (nx - 1)
            y = ly0 + (ly1 - ly0) * b / (ny - 1)
            c += 1
            parts.append((f"leg_{c}", _cyl(20, leg_h, x, y, 0, 0, 0, 1)))

    return parts
