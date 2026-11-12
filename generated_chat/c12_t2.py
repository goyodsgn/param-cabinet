import math
import cadquery as cq

PARAMS = {
    "W": 1500,          # inner width 1464 + 2*18
    "H": 850,
    "D": 600,
    "leg_h": 100,
    "back_mode": "inset",    # back panel fits between the sides, top and bottom
    "top_mode": "onset",     # top panel covers the tops of the sides
    "t": 18,
    "back_t": 10,
    "divider_t": 18,
    "door_t": 22,
    "shelf_t": 30,
    "door_gap": 2,
    "door_max_w": 600,
    "n_doors": None,
    "door_layout": [2, 1],   # left: double door (pair), right: single door -> 3 door cells
    "n_shelves": None,
    "shelf_min_gap": 320,
    "bottom_clear_min": None,
    "pin_max_spacing": 500,
    "leg_max_spacing": 600,
    "notes": [
        "Inner width 1464 -> W = 1464 + 2*18 = 1500 (overall).",
        "Three door cells: the left two form one double door, the right cell is a single door -> door_layout [2, 1], 3 door cells of 500 mm each.",
        "One inner wall at x = 1000 (between the double-door bay and the single-door bay); none behind the pair joint.",
        "Top is 'onset': the top panel is W wide and covers the sides, which run from leg_h to H - t.",
        "Back is 'inset': the back panel fits between the sides and between the bottom and top panels, flush with their rear edges. Sides, top and bottom are Dc deep.",
    ],
}


def _solid(wp):
    return wp.solids().vals()[0]


def _box(x0, x1, y0, y1, z0, z1):
    return (cq.Workplane("XY")
            .box(x1 - x0, y1 - y0, z1 - z0, centered=False)
            .translate((x0, y0, z0)))


def _xcyl(x0, length, y, z, d):
    # cylinder along +x starting at x0
    return (cq.Workplane("YZ").workplane(offset=x0)
            .center(y, z).circle(d / 2.0).extrude(length))


def build(params):
    p = params
    W, H, D = p["W"], p["H"], p["D"]
    leg_h = p["leg_h"]
    t, back_t, div_t = p["t"], p["back_t"], p["divider_t"]
    door_t, shelf_t, gap = p["door_t"], p["shelf_t"], p["door_gap"]
    top_mode, back_mode = p["top_mode"], p["back_mode"]
    Dc = D - door_t - gap

    # ---------- door layout ----------
    layout = p["door_layout"]
    if layout is None:
        n = max(p["n_doors"] or 0, math.ceil(W / p["door_max_w"]), 1)
        layout = [1] * n
    else:
        n = sum(layout)
    cw = W / n

    # hinge sides
    hinges = []
    if all(b == 1 for b in layout):
        for i in range(n):
            h = "L" if i % 2 == 0 else "R"
            if n > 1 and n % 2 == 1 and i == n - 1:
                h = "R"
            hinges.append(h)
    else:
        c = 0
        for b in layout:
            if b == 2:
                hinges += ["L", "R"]
            else:
                center = (c + 0.5) * cw
                hinges.append("L" if center <= W / 2 else "R")
            c += b

    # ---------- carcass geometry ----------
    has_top = top_mode != "none"
    carc_h = H - leg_h
    z_bot0 = leg_h
    z_bot1 = leg_h + t
    if top_mode == "inset":
        z_top0, z_top1 = H - t, H
        side_z1 = H
        clear_top = H - t
    elif top_mode == "onset":
        z_top0, z_top1 = H - t, H
        side_z1 = H - t
        clear_top = H - t
    else:
        side_z1 = H
        clear_top = H
    clear_h = clear_top - z_bot1

    if back_mode == "onset":
        carc_d = Dc - back_t
    else:
        carc_d = Dc
    inner_d = Dc - back_t  # shelf / divider depth

    # ---------- bays ----------
    div_xs = []
    c = 0
    for b in layout[:-1]:
        c += b
        div_xs.append(c * cw)
    bays = []
    lefts = [t] + [x + div_t / 2.0 for x in div_xs]
    rights = [x - div_t / 2.0 for x in div_xs] + [W - t]
    for i in range(len(layout)):
        bays.append((lefts[i], rights[i]))

    # ---------- shelf z positions ----------
    shelf_min_gap = p["shelf_min_gap"]
    bcm = p["bottom_clear_min"]
    if p["n_shelves"] is not None:
        k = max(0, p["n_shelves"])
    elif bcm is None:
        k = max(0, int(math.floor((clear_h - shelf_min_gap) / (shelf_min_gap + shelf_t))))
    else:
        k = max(0, int(math.floor((clear_h - max(bcm, shelf_min_gap)) / (shelf_min_gap + shelf_t))))
    shelf_zs = []
    if k > 0:
        g = (clear_h - k * shelf_t) / (k + 1.0)
        if bcm is not None and g < bcm:
            g2 = (clear_h - bcm - k * shelf_t) / float(k)
            for j in range(k):
                shelf_zs.append(z_bot1 + bcm + (shelf_t + g2) * j)
        else:
            for j in range(k):
                shelf_zs.append(z_bot1 + g * (j + 1) + shelf_t * j)

    # ---------- panels ----------
    side_l = _box(0, t, 0, carc_d, leg_h, side_z1)
    side_r = _box(W - t, W, 0, carc_d, leg_h, side_z1)
    dividers = []
    for x in div_xs:
        dividers.append(_box(x - div_t / 2.0, x + div_t / 2.0, 0, inner_d,
                             z_bot1, clear_top))

    pins = []
    shelves = []
    cuts = {"L": [], "R": [], **{i: [] for i in range(len(dividers))}}

    pin_d = 5.0
    span = inner_d - 2 * 50
    npin = int(math.ceil(span / p["pin_max_spacing"])) + 1
    pin_ys = [50 + span * i / (npin - 1) for i in range(npin)]

    for bi, (bl, br) in enumerate(bays):
        left_key = "L" if bi == 0 else bi - 1
        right_key = "R" if bi == len(bays) - 1 else bi
        for zs in shelf_zs:
            shelves.append(_box(bl + 1, br - 1, 0, inner_d, zs, zs + shelf_t))
            pz = zs - pin_d / 2.0
            for y in pin_ys:
                # left pin: 8 in panel, 6 into bay
                pins.append(_xcyl(bl - 8, 14, y, pz, pin_d))
                cuts[left_key].append(_xcyl(bl - 8, 8, y, pz, pin_d))
                # right pin
                pins.append(_xcyl(br - 6, 14, y, pz, pin_d))
                cuts[right_key].append(_xcyl(br, 8, y, pz, pin_d))

    def apply(panel, key):
        for cy in cuts[key]:
            panel = panel.cut(cy)
        return panel

    side_l = apply(side_l, "L")
    side_r = apply(side_r, "R")
    dividers = [apply(d, i) for i, d in enumerate(dividers)]

    parts = []
    parts.append(("side_left", _solid(side_l)))
    parts.append(("side_right", _solid(side_r)))

    if top_mode == "inset":
        parts.append(("top", _solid(_box(t, W - t, 0, carc_d, z_top0, z_top1))))
    elif top_mode == "onset":
        parts.append(("top", _solid(_box(0, W, 0, carc_d, z_top0, z_top1))))

    parts.append(("bottom", _solid(_box(t, W - t, 0, carc_d, z_bot0, z_bot1))))

    if back_mode == "onset":
        back = _box(0, W, Dc - back_t, Dc, leg_h, H)
    else:
        bz1 = clear_top if has_top else H
        back = _box(t, W - t, Dc - back_t, Dc, z_bot1, bz1)
    parts.append(("back", _solid(back)))

    for i, d in enumerate(dividers):
        parts.append(("divider_%d" % (i + 1), _solid(d)))
    for i, s in enumerate(shelves):
        parts.append(("shelf_%d" % (i + 1), _solid(s)))
    for i, pn in enumerate(pins):
        parts.append(("pin_%d" % (i + 1), _solid(pn)))

    # ---------- doors ----------
    dw = cw - 2 * gap
    dh = carc_h - 2 * gap
    nh = 2 if dh <= 900 else (3 if dh <= 1600 else 4)
    cup_zs_local = [100 + (dh - 200) * j / (nh - 1) for j in range(nh)]
    for i in range(n):
        x0 = i * cw + gap
        z0 = leg_h + gap
        door = _box(x0, x0 + dw, -(gap + door_t), -gap, z0, z0 + dh)
        cx = x0 + 22.5 if hinges[i] == "L" else x0 + dw - 22.5
        for lz in cup_zs_local:
            cup = (cq.Workplane("XZ", origin=(0, -gap, 0))
                   .center(cx, z0 + lz).circle(17.5).extrude(12))
            door = door.cut(cup)
        parts.append(("door_%d" % (i + 1), _solid(door)))

    # ---------- legs ----------
    leg_d = 40
    off = 30 + leg_d / 2.0
    xs_span = W - 2 * off
    ys_span = Dc - 2 * off
    nx = int(math.ceil(xs_span / p["leg_max_spacing"])) + 1
    ny = int(math.ceil(ys_span / p["leg_max_spacing"])) + 1
    li = 1
    for ix in range(nx):
        x = off + xs_span * ix / (nx - 1)
        for iy in range(ny):
            y = off + ys_span * iy / (ny - 1)
            leg = (cq.Workplane("XY").workplane(offset=0)
                   .center(x, y).circle(leg_d / 2.0).extrude(leg_h))
            parts.append(("leg_%d" % li, _solid(leg)))
            li += 1

    return parts
