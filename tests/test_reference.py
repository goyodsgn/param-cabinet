import pytest

from cabinet_reference import Params, compute_layout, validate, shelf_count

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
    assert sum(n.startswith("pin_") for n in names) == 4 * n_shelves * (n_walls + 1)
    assert check_solids(parts) == []
    assert bbox_size(parts) == pytest.approx((W, D, H), abs=1e-3)
