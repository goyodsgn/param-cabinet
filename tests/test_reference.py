import pytest

from cabinet_reference import Params, compute_layout, validate

# (W, H, D, leg_h) -> expected doors, hinges per door, legs along width, legs along depth
CASES = [
    (600, 700, 560, 100, 1, 2, 2, 2),
    (900, 850, 580, 100, 2, 2, 3, 2),
    (1200, 850, 580, 100, 2, 2, 3, 2),
    (1500, 850, 600, 150, 3, 2, 4, 2),
    (1800, 1000, 650, 100, 3, 3, 4, 2),
    (2400, 1700, 900, 120, 4, 4, 5, 3),
]


@pytest.mark.parametrize("W,H,D,leg_h,n_doors,n_hinges,lx,ly", CASES)
def test_rules(W, H, D, leg_h, n_doors, n_hinges, lx, ly):
    p = Params(W=W, H=H, D=D, leg_h=leg_h)
    lay = compute_layout(p)
    assert lay.n_doors == n_doors
    assert lay.n_hinges == n_hinges
    assert (lay.legs_x, lay.legs_y) == (lx, ly)
    assert validate(p, lay) == []


@pytest.mark.parametrize("n,expected", [
    (1, ["left"]),
    (2, ["left", "right"]),
    (3, ["left", "right", "right"]),
    (4, ["left", "right", "left", "right"]),
    (6, ["left", "right"] * 3),
])
def test_doors_open_in_facing_pairs(n, expected):
    p = Params(W=n * 590)
    lay = compute_layout(p)
    assert lay.n_doors == n
    assert [d.hinge_side for d in lay.doors] == expected


def test_doors_sit_on_legs():
    p = Params(leg_h=150)
    lay = compute_layout(p)
    assert all(d.z == pytest.approx(150 + p.door_gap) for d in lay.doors)


def test_corner_legs_keep_margin():
    p = Params(W=1200, D=580)
    lay = compute_layout(p)
    xs = sorted({x for x, _ in lay.legs})
    assert xs[0] - p.leg_d / 2 == pytest.approx(p.leg_inset)
    assert p.W - (xs[-1] + p.leg_d / 2) == pytest.approx(p.leg_inset)


def test_too_narrow_is_flagged():
    errs = validate(Params(W=200))
    assert any("door width" in e for e in errs)


def test_doors_fill_width():
    p = Params(W=1537)
    lay = compute_layout(p)
    total = sum(d.w for d in lay.doors) + (lay.n_doors + 1) * p.door_gap
    assert abs(total - p.W) < 1e-6


@pytest.mark.parametrize("W,H,D,leg_h,n_doors,n_hinges,lx,ly", CASES)
def test_geometry(W, H, D, leg_h, n_doors, n_hinges, lx, ly):
    pytest.importorskip("cadquery")
    from cabinet_reference import build, check_solids

    p = Params(W=W, H=H, D=D, leg_h=leg_h)
    parts = build(p)
    names = [name for name, _ in parts]
    assert sum(n.startswith("door_") for n in names) == n_doors
    assert sum(n.startswith("leg_") for n in names) == lx * ly
    assert "top" in names
    assert check_solids(parts) == []
