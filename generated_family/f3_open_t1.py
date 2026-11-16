import math
import cadquery as cq

PARAMS = {
    "W": 800, "H": 1800, "D": 300,
    "leg_h": 100,
    "back_mode": "onset",
    "top_mode": "inset",
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
    "n_bays": None,
    "shelf_max_span": 900,
    "notes": [
        "문 없음: 오픈 책장이라 문, 경첩, 문 개수 규칙은 적용하지 않음 (n_doors=0)",
        "깊이: 문이 없으므로 문 두께와 틈을 빼지 않고 본체 깊이 Dc = D = 300 (전체 깊이 300 유지)",
        "다릿발 유지: 바닥에 놓는 가구라 기존 다릿발 규칙(지름 40, 높이 100, 모서리 30 간격, 간격 600 이하)을 그대로 적용",
        "상판 inset, 뒷판 onset(10mm) 기본값 유지: 뒷판이 책장의 흔들림을 잡아줌",
        "선반 규칙 유지: 선반 두께 30, 선반 사이 높이 320 이상이 되는 최대 개수를 자동 계산하고 균등 배치",
        "선반핀 규칙 유지: 선반 앞뒤 50mm 지점, 간격 500 이하, 좌우 판에 각각 설치",
        "칸 나눔: 선반 처짐 방지를 위해 한 칸 폭이 900 이하가 되도록 칸막이 개수를 자동 계산 (폭 800은 칸막이 없이 1칸)",
        "전도 방지: 키 큰 가구(1800)에 깊이 300이라 벽에 고정 권장",
    ],
}


def _solid(wp):
    v = wp.val()
    if isinstance(v, cq.Solid):
        return v
    return v.Solids()[0]


def _box(x0, x1, y0, y1, z0, z1):
    return (cq.Workplane("XY")
            .box(x1 - x0, y1 - y0, z1 - z0, centered=False)
            .translate((x0, y0, z0)))


def _cyl_x(x0, x1, y, z, d):
    return (cq.Workplane("YZ").workplane(offset=x0)
            .center(y, z).circle(d / 2.0).extrude(x1 - x0))


def build(params):
    p = params
    W, H, D = p["W"], p["H"], p["D"]
    leg_h, t, back_t = p["leg_h"], p["t"], p["back_t"]
    divider_t, shelf_t = p["divider_t"], p["shelf_t"]
    top_mode, back_mode = p["top_mode"], p["back_mode"]
    has_doors = bool(p["n_doors"])
    Dc = D - (p["door_t"] + p["door_gap"] if has_doors else 0)

    has_top = top_mode != "none"
    z_bot = leg_h + t                       # top face of bottom panel
    z_top = H - t if has_top else H         # underside of top panel
    clear_h = z_top - z_bot
    inner_d = Dc - back_t
    side_d = inner_d if back_mode == "onset" else Dc
    side_z1 = H - t if top_mode == "onset" else H

    # bays
    n_bays = p["n_bays"] or max(1, math.ceil((W - 2 * t) / p["shelf_max_span"]))
    parts = {}
    holes = {}

    parts["side_left"] = _box(0, t, 0, side_d, leg_h, side_z1)
    parts["side_right"] = _box(W - t, W, 0, side_d, leg_h, side_z1)
    parts["bottom"] = _box(t, W - t, 0, side_d, leg_h, z_bot)
    if has_top:
        if top_mode == "onset":
            parts["top"] = _box(0, W, 0, side_d, H - t, H)
        else:
            parts["top"] = _box(t, W - t, 0, side_d, H - t, H)
    if back_mode == "onset":
        parts["back"] = _box(0, W, Dc - back_t, Dc, leg_h, H)
    else:
        parts["back"] = _box(t, W - t, Dc - back_t, Dc, z_bot, z_top)

    # vertical panels: list of (name, x_left_face, x_right_face)
    panels = [("side_left", 0.0, t)]
    for j in range(1, n_bays):
        xc = j * W / n_bays
        nm = "divider_%d" % j
        parts[nm] = _box(xc - divider_t / 2.0, xc + divider_t / 2.0, 0, inner_d, z_bot, z_top)
        panels.append((nm, xc - divider_t / 2.0, xc + divider_t / 2.0))
    panels.append(("side_right", W - t, W))

    # shelves
    if p["n_shelves"] is not None:
        k = p["n_shelves"]
    else:
        bmin = p["bottom_clear_min"]
        base = max(bmin, p["shelf_min_gap"]) if bmin else p["shelf_min_gap"]
        k = max(0, int(math.floor((clear_h - base) / (p["shelf_min_gap"] + shelf_t))))
    gap = (clear_h - k * shelf_t) / (k + 1)
    if p["bottom_clear_min"] and k > 0 and gap < p["bottom_clear_min"]:
        first = p["bottom_clear_min"]
        gaps = [first] + [(clear_h - first - k * shelf_t) / k] * k
    else:
        gaps = [gap] * (k + 1)

    shelf_z = []
    z = z_bot
    for i in range(k):
        z += gaps[i]
        shelf_z.append(z)
        z += shelf_t

    pin_d, pin_in, pin_out = 5.0, 8.0, 6.0
    span = inner_d - 100
    n_pin = math.ceil(span / p["pin_max_spacing"]) + 1
    pin_ys = [50 + i * span / (n_pin - 1) for i in range(n_pin)]

    pins = []
    shelves = []
    for b in range(n_bays):
        _, _, xl = panels[b]
        _, xr, _ = panels[b + 1]
        for zs in shelf_z:
            shelves.append(_box(xl + 1, xr - 1, 0, inner_d, zs, zs + shelf_t))
            for y in pin_ys:
                zc = zs - pin_d / 2.0
                pins.append(_cyl_x(xl - pin_in, xl + pin_out, y, zc, pin_d))
                holes.setdefault(panels[b][0], []).append(_cyl_x(xl - pin_in, xl, y, zc, pin_d))
                pins.append(_cyl_x(xr - pin_out, xr + pin_in, y, zc, pin_d))
                holes.setdefault(panels[b + 1][0], []).append(_cyl_x(xr, xr + pin_in, y, zc, pin_d))

    for nm, wp in holes.items():
        base_wp = parts[nm]
        for h in wp:
            base_wp = base_wp.cut(h)
        parts[nm] = base_wp

    out = []
    for nm in ["side_left", "side_right", "top", "bottom", "back"]:
        if nm in parts:
            out.append((nm, _solid(parts[nm])))
    for j in range(1, n_bays):
        out.append(("divider_%d" % j, _solid(parts["divider_%d" % j])))
    for i, s in enumerate(shelves):
        out.append(("shelf_%d" % (i + 1), _solid(s)))
    for i, pn in enumerate(pins):
        out.append(("pin_%d" % (i + 1), _solid(pn)))

    # legs
    if leg_h > 0:
        leg_d, edge = 40.0, 30.0
        x0, x1 = edge + leg_d / 2.0, W - edge - leg_d / 2.0
        y0, y1 = edge + leg_d / 2.0, Dc - edge - leg_d / 2.0
        nx = math.ceil((x1 - x0) / p["leg_max_spacing"]) + 1
        ny = math.ceil((y1 - y0) / p["leg_max_spacing"]) + 1
        n = 0
        for i in range(nx):
            for j in range(ny):
                x = x0 + i * (x1 - x0) / (nx - 1)
                y = y0 + j * (y1 - y0) / (ny - 1) if ny > 1 else y0
                n += 1
                leg = (cq.Workplane("XY").workplane(offset=0).center(x, y)
                       .circle(leg_d / 2.0).extrude(leg_h))
                out.append(("leg_%d" % n, _solid(leg)))
    return out
