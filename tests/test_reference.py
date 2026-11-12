import pytest

from cabinet_reference import Params, compute_layout, validate, shelf_count, pin_ys

# (W, H, D, leg_h) -> doors, hinges per door, inner walls, shelves per bay
CASES = [
    (600, 700, 560, 100, 1, 2, 0, 0),
    (900, 850, 580, 100, 2, 2, 1, 1),
    (1200, 850, 580, 100, 2, 2, 1, 1),
    (1500, 850, 600, 150, 3, 2, 2, 0),   # clear height 664 -> no shelf (needs 670)
    (1800, 1000, 650, 100, 3, 2, 2, 1),
    (2400, 1700, 900, 120, 4, 3, 3, 3),
]


@pytest.mark.parametrize("W,H,D,leg_h,n_doors,n_hinges,n_walls,n_shelves", CASES)
@pytest.mark.parametrize("back_mode", ["onset", "inset"])
def test_rules(W, H, D, leg_h, n_doors, n_hinges, n_walls, n_shelves, back_mode):
    p = Params(W=W, H=H, D=D, leg_h=leg_h, back_mode=back_mode)
    lay = compute_layout(p)
    assert lay.n_doors == n_doors
    assert lay.n_hinges == n_hinges
    assert len(lay.dividers) == n_walls
    assert lay.n_shelves == n_shelves
    assert validate(p, lay) == []


def test_door_gap_every_side():
    p = Params(W=1200, H=850, leg_h=100)
    lay = compute_layout(p)
    a, b = lay.doors
    assert a.x == pytest.approx(2)                      # outer edge
    assert b.x - (a.x + a.w) == pytest.approx(4)        # between doors: 2 + 2
    assert a.w == pytest.approx(596)
    assert a.z == pytest.approx(100 + 2)
    assert a.h == pytest.approx(750 - 4)


def test_depth_includes_door_and_gap():
    p = Params(D=580)
    assert p.Dc == pytest.approx(580 - 22 - 2)


@pytest.mark.parametrize("clear_h,expected", [(300, 0), (670, 1), (700, 1), (1019, 1), (1020, 2), (1500, 3)])
def test_shelf_spaces_stay_at_least_320(clear_h, expected):
    assert shelf_count(clear_h, 30, 320) == expected


@pytest.mark.parametrize("n,expected", [
    (1, ["left"]), (2, ["left", "right"]), (3, ["left", "right", "right"]),
    (4, ["left", "right", "left", "right"]),
])
def test_doors_open_in_facing_pairs(n, expected):
    lay = compute_layout(Params(W=n * 590))
    assert [d.hinge_side for d in lay.doors] == expected


def test_wall_behind_every_door_joint():
    p = Params(W=2400)
    lay = compute_layout(p)
    for j, (x0, x1) in enumerate(lay.dividers, start=1):
        assert (x0 + x1) / 2 == pytest.approx(j * 600)


def test_too_narrow_is_flagged():
    assert any("door width" in e for e in validate(Params(W=200)))


@pytest.mark.parametrize("W,H,D,leg_h,n_doors,n_hinges,n_walls,n_shelves", CASES)
@pytest.mark.parametrize("back_mode", ["onset", "inset"])
def test_geometry(W, H, D, leg_h, n_doors, n_hinges, n_walls, n_shelves, back_mode):
    pytest.importorskip("cadquery")
    from cabinet_reference import build, check_solids, bbox_size

    p = Params(W=W, H=H, D=D, leg_h=leg_h, back_mode=back_mode)
    parts = build(p)
    names = [n for n, _ in parts]
    assert sum(n.startswith("door_") for n in names) == n_doors
    assert sum(n.startswith("divider_") for n in names) == n_walls
    assert sum(n.startswith("shelf_") for n in names) == n_shelves * (n_walls + 1)
    assert sum(n.startswith("pin_") for n in names) == 2 * len(pin_ys(p)) * n_shelves * (n_walls + 1)
    assert check_solids(parts) == []
    assert bbox_size(parts) == pytest.approx((W, D, H), abs=1e-3)


@pytest.mark.parametrize("D,per_side", [(580, 2), (700, 3), (900, 3), (1200, 4)])
def test_more_pins_for_deeper_shelves(D, per_side):
    p = Params(D=D)
    ys = pin_ys(p)
    assert len(ys) == per_side
    assert all(b - a <= p.pin_max_spacing + 1e-9 for a, b in zip(ys, ys[1:]))


def test_customer_can_add_doors_and_set_shelves():
    p = Params(W=1200, n_doors=3, n_shelves=3)
    lay = compute_layout(p)
    assert lay.n_doors == 3 and len(lay.dividers) == 2 and lay.n_shelves == 3
    assert validate(p, lay) == []


def test_customer_cannot_make_doors_wider_than_600():
    lay = compute_layout(Params(W=1800, n_doors=2))
    assert lay.n_doors == 3


# ---- top panel, door arrangement, inner space -------------------------------------------------
def test_one_single_and_one_pair():
    """'세칸짜리에 가장 왼쪽이 한쪽문이고 양문형이 오른쪽' -> door_layout [1, 2]."""
    p = Params(W=1500, door_layout=[1, 2])
    lay = compute_layout(p)
    assert lay.n_doors == 3 and lay.groups == [1, 2]
    assert len(lay.dividers) == 1
    assert sum(lay.dividers[0]) / 2 == pytest.approx(500)
    assert [d.hinge_side for d in lay.doors] == ["left", "left", "right"]
    assert validate(p, lay) == []


def test_pair_on_the_left():
    lay = compute_layout(Params(W=1500, door_layout=[2, 1]))
    assert sum(lay.dividers[0]) / 2 == pytest.approx(1000)
    assert [d.hinge_side for d in lay.doors] == ["left", "right", "right"]


def test_pair_wider_than_600_cell_is_flagged():
    errs = validate(Params(W=1500, door_layout=[2]))
    assert any(e.startswith("ABSOLUTE") for e in errs)


def test_layout_of_all_singles_matches_default():
    a = compute_layout(Params(W=1800))
    b = compute_layout(Params(W=1800, door_layout=[1, 1, 1]))
    assert [d.hinge_side for d in a.doors] == [d.hinge_side for d in b.doors]
    assert a.dividers == b.dividers


def test_sink_has_no_top_and_taller_clear_height():
    p = Params(H=850, top_mode="none")
    assert p.clear_h == pytest.approx(750 - 18)
    assert validate(p) == []


@pytest.mark.parametrize("H,B,k", [(850, None, 1), (850, 350, 1), (850, 400, 0), (1200, 350, 2)])
def test_bottom_space_for_albums(H, B, k):
    p = Params(H=H, bottom_clear_min=B)
    lay = compute_layout(p)
    assert lay.n_shelves == k
    assert validate(p, lay) == []
    if k and B:
        assert lay.shelf_z[0] - p.inner_bottom >= B - 1e-6


@pytest.mark.parametrize("top_mode", ["inset", "onset", "none"])
@pytest.mark.parametrize("back_mode", ["onset", "inset"])
def test_geometry_top_modes(top_mode, back_mode):
    pytest.importorskip("cadquery")
    from cabinet_reference import build, check_solids, bbox_size

    p = Params(W=1500, H=850, D=600, top_mode=top_mode, back_mode=back_mode, door_layout=[1, 2],
               bottom_clear_min=350)
    parts = build(p)
    names = [n for n, _ in parts]
    assert ("top" in names) == (top_mode != "none")
    assert sum(n.startswith("divider_") for n in names) == 1
    assert check_solids(parts) == []
    assert bbox_size(parts) == pytest.approx((1500, 600, 850), abs=1e-3)
