import math
import cadquery as cq

# ㄱ자 코너 하부장
# 좌표: 뒷벽 y = D, 왼쪽 벽 x = 0. 가구는 두 벽이 만나는 모서리(왼쪽 뒤)에 들어간다.
#   팔 1: 뒷벽을 따라 x = 0..W (앞면 y = D - Dc, 문은 -y 방향)
#   팔 2: 왼쪽 벽을 따라 y = 0..D (앞면 x = Dc, 문은 +x 방향)
#   x > Dc, y < D - Dc 인 오른쪽 앞 사각형은 비어 있는 방 공간이다.
PARAMS = {
    "W": 1000,
    "H": 850,
    "D": 1000,
    "arm_depth": 580,          # 각 팔의 깊이(문 포함)
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
    "leg_d": 40,
    "leg_edge_gap": 30,
    "pin_d": 5,
    "pin_hole": 8,
    "pin_out": 6,
    "pin_edge": 50,
    "shelf_clear": 1,
    "hinge_d": 35,
    "hinge_depth": 12,
    "hinge_edge": 22.5,
    "hinge_end": 100,
    "notes": [
        "ㄱ자 코너장: W=1000은 뒷벽을 따르는 팔, D=1000은 왼쪽 벽을 따르는 팔의 바깥 길이. 팔 깊이는 arm_depth=580(문 포함)로 두 팔 모두 같다.",
        "배치: 뒷벽 y=D, 왼쪽 벽 x=0에 붙이는 방향. 오른쪽 앞 모서리는 비어 있다(반대 방향이 필요하면 좌우 반전).",
        "깊이 규칙 적용: Dc = arm_depth - door_t - door_gap = 556. 본체는 이 깊이로 만들고 문까지 합쳐 정확히 580.",
        "바닥판·상판: 기존 규칙(상판 inset, 옆판 사이)을 그대로 쓰되 ㄱ자 한 장짜리 판으로 만듦.",
        "옆판: 팔 끝마다 하나씩. side_left = y=0 쪽 끝판, side_right = x=W 쪽 끝판. 코너 안쪽 모서리에는 판이 없고 내부가 하나로 트인다.",
        "뒷판 2장: back_1(뒷벽, 폭 W 전체 높이)과 back_2(왼쪽 벽). back_2는 back_1 앞에서 끝나게 해서 겹치지 않게 함. 뒷판 onset 규칙 유지.",
        "문 2개: 팔마다 1짝. 각 문칸이 600 이하여서 더 나눌 필요 없음(문칸 폭 444, 420). 팔 1 문칸은 코너 모서리까지 덮고, 팔 2 문은 그 앞에서 끝나 서로 겹치지 않으며 사이 간격은 door_gap 2.",
        "문 간격·힌지 수 규칙 그대로: 사방 2mm, 문 높이 746이라 힌지 2개, 위아래 끝에서 100, 가장자리에서 22.5.",
        "힌지 방향: 마주보는 문 한 쌍 규칙을 코너에 적용 - 두 문 모두 바깥쪽 끝에 힌지, 손잡이는 코너 이음새 쪽(열면 코너 안이 넓게 보임).",
        "칸막이 없음: 두 문의 이음새가 코너 안쪽으로 이어지는 하나의 ㄱ자 공간이라 칸막이 규칙은 제외(팔의 문이 600을 넘어 늘어날 때만 생성).",
        "선반: 규칙대로 개수 계산(내경 714 -> 1장). ㄱ자 선반 1장을 통판으로 만들고 판에 닿는 면 1mm 여유. 앞쪽 열린 면은 여유 없음.",
        "선반핀: 선반이 닿는 수직판 4면(side_left, side_right, back_1, back_2) 모두에 규칙대로 설치. 통판이 두 끝만 받치면 휘기 때문. 뒷판 10mm에 구멍 8mm라 2mm 남으니 하중이 큰 용도면 뒷판을 두껍게 할 것.",
        "다릿발: ㄱ자 바깥 모서리 6곳에 30 간격 규칙으로 배치하고, 각 변은 간격 600 이하로 중간 다릿발 추가(총 8개). 격자 대신 외곽선 기준.",
        "W, D, H는 전체 외곽 박스(문·다릿발 포함): 1000 x 1000 x 850.",
        "check.py 불일치(직사각형 가정이라 설계 유지): door_gap/hinge는 문 2가 +x를 향해 y 방향으로 달려 있어 앞면 y=0 기준 측정이 맞지 않음(실제 문 간격 2, 힌지 중심 22.5, 문끼리 간격 2). shelf_pins는 선반 bbox 깊이 970 기준으로 세지만 side_right에 닿는 변은 545라 핀 2개가 맞음. leg는 ㄱ자 외곽선이라 x·y 위치가 4개씩이며 인접 간격은 모두 600 이하.",
    ],
}


def _solid(shape):
    s = shape.Solids()
    return s[0] if len(s) == 1 else shape


def _box(x0, x1, y0, y1, z0, z1):
    wp = cq.Workplane("XY").box(x1 - x0, y1 - y0, z1 - z0, centered=False)
    return _solid(wp.translate((x0, y0, z0)).val())


def _poly(pts, z0, z1):
    wp = cq.Workplane("XY").workplane(offset=z0).polyline(pts).close().extrude(z1 - z0)
    return _solid(wp.val())


def _offset_poly(pts, offs):
    """축에 평행한 반시계 다각형의 각 변을 안쪽으로 offs[i]만큼 민다."""
    n = len(pts)
    lines = []
    for i in range(n):
        a, b = pts[i], pts[(i + 1) % n]
        dx, dy = b[0] - a[0], b[1] - a[1]
        L = math.hypot(dx, dy)
        nx, ny = -dy / L, dx / L
        if abs(dy) < 1e-9:
            lines.append(("h", a[1] + ny * offs[i]))
        else:
            lines.append(("v", a[0] + nx * offs[i]))
    out = []
    for i in range(n):
        l0, l1 = lines[i - 1], lines[i]
        if l0[0] == "h":
            out.append((l1[1], l0[1]))
        else:
            out.append((l0[1], l1[1]))
    return out


def _count(span, step):
    return max(1, math.ceil(span / step - 1e-9))


def _hinge_count(h):
    return 2 if h <= 900 else (3 if h <= 1600 else 4)


def _shelf_gaps(p, clear_h):
    """선반 아랫면까지 이어지는 빈 간격 리스트(선반 개수 = len)."""
    st = p["shelf_t"]
    bcm = p["bottom_clear_min"]
    if p["n_shelves"] is not None:
        k = max(0, int(p["n_shelves"]))
    else:
        m = max(bcm or 0, p["shelf_min_gap"])
        k = max(0, math.floor((clear_h - m) / (p["shelf_min_gap"] + st)))
    if k == 0:
        return []
    gap = (clear_h - k * st) / (k + 1)
    if bcm and p["n_shelves"] is None and gap < bcm and k >= 1:
        rest = (clear_h - bcm - k * st) / k
        return [bcm] + [rest] * (k - 1)
    return [gap] * k


def build(params):
    p = params
    W, H, D = p["W"], p["H"], p["D"]
    t, bt, dvt, dt, st = p["t"], p["back_t"], p["divider_t"], p["door_t"], p["shelf_t"]
    g = p["door_gap"]
    leg_h = p["leg_h"]
    top_mode = p["top_mode"]
    A = p["arm_depth"]
    Dc = A - dt - g                      # 본체 깊이
    z0, z1 = leg_h, H
    yf = D - Dc                          # 팔 1 앞면(본체)
    xl, xr, ys, yb = bt, W - t, t, D - bt  # 안쪽 면 위치

    parts = []
    holes = {}
    panels = {}

    # ---- 칸 수(문) ----
    c1 = W - Dc                          # 팔 1 문칸 전체 폭
    c2 = D - A                           # 팔 2 문칸 전체 폭
    m1 = max(1, math.ceil(c1 / p["door_max_w"] - 1e-9))
    m2 = max(1, math.ceil(c2 / p["door_max_w"] - 1e-9))

    # ---- 판재 ----
    has_top = top_mode != "none"
    side_top = z1 - t if top_mode == "onset" else z1
    panels["side_left"] = _box(xl, Dc, 0, t, z0, side_top)
    panels["side_right"] = _box(xr, W, yf, yb, z0, side_top)

    inner = [(xl, ys), (Dc, ys), (Dc, yf), (xr, yf), (xr, yb), (xl, yb)]
    panels["bottom"] = _poly(inner, z0, z0 + t)
    if top_mode == "inset":
        panels["top"] = _poly(inner, z1 - t, z1)
    elif top_mode == "onset":
        outer_top = [(xl, 0), (Dc, 0), (Dc, yf), (W, yf), (W, yb), (xl, yb)]
        panels["top"] = _poly(outer_top, z1 - t, z1)

    panels["back_1"] = _box(0, W, D - bt, D, z0, z1)
    panels["back_2"] = _box(0, bt, 0, D - bt, z0, z1)

    dz0 = z0 + t
    dz1 = z1 - t if has_top else z1
    clear_h = dz1 - dz0

    # ---- 칸막이(문칸이 600을 넘어 나눠질 때만) ----
    xd1 = [Dc + j * c1 / m1 for j in range(1, m1)]
    yd2 = [j * c2 / m2 for j in range(1, m2)]
    div_names = {}
    idx = 1
    for xc in xd1:
        panels["divider_%d" % idx] = _box(xc - dvt / 2, xc + dvt / 2, yf, yb, dz0, dz1)
        div_names[("a1", len(div_names))] = "divider_%d" % idx
        idx += 1
    a1_names = ["divider_%d" % (i + 1) for i in range(len(xd1))]
    for yc in yd2:
        panels["divider_%d" % idx] = _box(xl, Dc, yc - dvt / 2, yc + dvt / 2, dz0, dz1)
        idx += 1
    a2_names = ["divider_%d" % (len(xd1) + i + 1) for i in range(len(yd2))]

    # ---- 칸(bay) 정의: (꼭짓점 반시계, 변별 패널 이름 또는 None=열림) ----
    bays = []
    ya = ys if m2 == 1 else yd2[-1] + dvt / 2
    xb = xr if m1 == 1 else xd1[0] - dvt / 2
    n_bottom = "side_left" if m2 == 1 else a2_names[-1]
    n_right = "side_right" if m1 == 1 else a1_names[0]
    bays.append((
        [(xl, ya), (Dc, ya), (Dc, yf), (xb, yf), (xb, yb), (xl, yb)],
        [n_bottom, None, None, n_right, "back_1", "back_2"],
    ))
    for k in range(1, m1):
        xa = xd1[k - 1] + dvt / 2
        xe = xd1[k] - dvt / 2 if k < m1 - 1 else xr
        nr = a1_names[k] if k < m1 - 1 else "side_right"
        bays.append((
            [(xa, yf), (xe, yf), (xe, yb), (xa, yb)],
            [None, nr, "back_1", a1_names[k - 1]],
        ))
    for k in range(0, m2 - 1):
        yl = ys if k == 0 else yd2[k - 1] + dvt / 2
        yu = yd2[k] - dvt / 2
        nl = "side_left" if k == 0 else a2_names[k - 1]
        bays.append((
            [(xl, yl), (Dc, yl), (Dc, yu), (xl, yu)],
            [nl, None, a2_names[k], "back_2"],
        ))

    # ---- 선반 + 선반핀 ----
    gaps = _shelf_gaps(p, clear_h)
    pin_r = p["pin_d"] / 2
    n_shelf = 0
    n_pin = 0
    shelves = []
    pins = []
    for poly, names in bays:
        offs = [p["shelf_clear"] if nm else 0 for nm in names]
        sp = _offset_poly(poly, offs)
        zc = dz0
        for gp in gaps:
            zc += gp
            n_shelf += 1
            shelves.append(("shelf_%d" % n_shelf, _poly(sp, zc, zc + st)))
            nvert = len(sp)
            for i in range(nvert):
                if not names[i]:
                    continue
                a, b = sp[i], sp[(i + 1) % nvert]
                dx, dy = b[0] - a[0], b[1] - a[1]
                L = math.hypot(dx, dy)
                ux, uy = dx / L, dy / L
                nx, ny = -uy, ux
                span = L - 2 * p["pin_edge"]
                if span <= 0:
                    us = [L / 2]
                else:
                    cnt = math.ceil(span / p["pin_max_spacing"] - 1e-9) + 1
                    us = [p["pin_edge"] + span * q / (cnt - 1) for q in range(cnt)]
                for u in us:
                    fx = a[0] + ux * u - nx * offs[i]
                    fy = a[1] + uy * u - ny * offs[i]
                    pz = zc - p["pin_d"] / 2
                    direction = cq.Vector(nx, ny, 0)
                    start = cq.Vector(fx - nx * p["pin_hole"], fy - ny * p["pin_hole"], pz)
                    n_pin += 1
                    pins.append((
                        "pin_%d" % n_pin,
                        cq.Solid.makeCylinder(pin_r, p["pin_hole"] + p["pin_out"], start, direction),
                    ))
                    hole = cq.Solid.makeCylinder(pin_r, p["pin_hole"], start, direction)
                    holes.setdefault(names[i], []).append(hole)
            zc += st

    # ---- 판재에 핀 구멍 ----
    order = ["side_left", "side_right", "top", "bottom", "back_1", "back_2"]
    order += [k for k in panels if k.startswith("divider_")]
    for nm in order:
        if nm not in panels:
            continue
        s = panels[nm]
        if nm in holes:
            s = _solid(s.cut(*holes[nm]))
        parts.append((nm, s))
    parts += shelves + pins

    # ---- 문 ----
    dh = (z1 - z0) - 2 * g
    dzb = z0 + g
    n_h = _hinge_count(dh)
    hz = [dzb + p["hinge_end"] + q * (dh - 2 * p["hinge_end"]) / (n_h - 1) for q in range(n_h)]
    hr = p["hinge_d"] / 2

    def pick_side(k, m, single_side):
        if p["single_door_hinge"]:
            return p["single_door_hinge"]
        if m == 1:
            return single_side
        if k == m - 1 and m % 2 == 1:
            return "right"
        return "left" if k % 2 == 0 else "right"

    n_door = 0
    # 팔 1: 앞면 y = yf, 문은 -y 쪽. 보는 사람 기준 왼쪽 = 낮은 x
    for k in range(m1):
        x0 = Dc + k * c1 / m1 + g
        w = c1 / m1 - 2 * g
        yb_door = yf - g
        door = _box(x0, x0 + w, yb_door - dt, yb_door, dzb, dzb + dh)
        side = pick_side(k, m1, "right")
        cx = x0 + p["hinge_edge"] if side == "left" else x0 + w - p["hinge_edge"]
        cups = [cq.Solid.makeCylinder(hr, p["hinge_depth"], cq.Vector(cx, yb_door, z), cq.Vector(0, -1, 0)) for z in hz]
        n_door += 1
        parts.append(("door_%d" % n_door, _solid(door.cut(*cups))))
    # 팔 2: 앞면 x = Dc, 문은 +x 쪽. 보는 사람 기준 왼쪽 = 낮은 y
    for k in range(m2):
        y0 = k * c2 / m2 + g
        w = c2 / m2 - 2 * g
        xb_door = Dc + g
        door = _box(xb_door, xb_door + dt, y0, y0 + w, dzb, dzb + dh)
        side = pick_side(k, m2, "left")
        cy = y0 + p["hinge_edge"] if side == "left" else y0 + w - p["hinge_edge"]
        cups = [cq.Solid.makeCylinder(hr, p["hinge_depth"], cq.Vector(xb_door, cy, z), cq.Vector(1, 0, 0)) for z in hz]
        n_door += 1
        parts.append(("door_%d" % n_door, _solid(door.cut(*cups))))

    # ---- 다릿발: ㄱ자 외곽선 기준 ----
    outline = [(0, 0), (Dc, 0), (Dc, yf), (W, yf), (W, D), (0, D)]
    e = p["leg_edge_gap"] + p["leg_d"] / 2
    corners = _offset_poly(outline, [e] * len(outline))
    leg_pts = []

    def add_pt(pt):
        for q in leg_pts:
            if abs(q[0] - pt[0]) < 1e-6 and abs(q[1] - pt[1]) < 1e-6:
                return
        leg_pts.append(pt)

    for i in range(len(corners)):
        a, b = corners[i], corners[(i + 1) % len(corners)]
        span = math.hypot(b[0] - a[0], b[1] - a[1])
        cnt = math.ceil(span / p["leg_max_spacing"] - 1e-9) + 1
        for q in range(cnt):
            f = q / (cnt - 1)
            add_pt((a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f))
    for i, (lx, ly) in enumerate(leg_pts):
        leg = cq.Solid.makeCylinder(p["leg_d"] / 2, leg_h, cq.Vector(lx, ly, 0), cq.Vector(0, 0, 1))
        parts.append(("leg_%d" % (i + 1), leg))

    return parts
