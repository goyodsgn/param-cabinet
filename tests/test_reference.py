import pytest

from cabinet_reference import Params, compute_layout, validate

# (W, H) -> expected doors, hinges per door
CASES = [
    (600, 700, 1, 2),
    (900, 850, 2, 2),
    (1200, 850, 2, 2),
    (1500, 850, 3, 2),
    (1800, 1000, 3, 3),
    (2400, 1700, 4, 4),
]


@pytest.mark.parametrize("W,H,n_doors,n_hinges", CASES)
def test_rules(W, H, n_doors, n_hinges):
    p = Params(W=W, H=H)
    lay = compute_layout(p)
    assert lay.n_doors == n_doors
    assert lay.n_hinges == n_hinges
    assert validate(p, lay) == []


def test_too_narrow_is_flagged():
    errs = validate(Params(W=200))
    assert any("door width" in e for e in errs)


def test_doors_fill_width():
    p = Params(W=1537)
    lay = compute_layout(p)
    total = sum(d.w for d in lay.doors) + (lay.n_doors + 1) * p.door_gap
    assert abs(total - p.W) < 1e-6


@pytest.mark.parametrize("W,H,n_doors,n_hinges", CASES)
def test_geometry(W, H, n_doors, n_hinges):
    pytest.importorskip("cadquery")
    from cabinet_reference import build, check_solids

    p = Params(W=W, H=H)
    parts = build(p)
    assert sum(1 for name, _ in parts if name.startswith("door_")) == n_doors
    assert check_solids(parts) == []
