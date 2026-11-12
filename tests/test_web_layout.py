"""The browser viewer (web/layout.js) must compute the same layout as the Python reference model."""
import json
import shutil
import subprocess

import pytest

from cabinet_reference import Params, compute_layout

CASES = [
    dict(W=450, H=600, D=600), dict(W=600, H=700, D=560), dict(W=1200, H=850, D=580),
    dict(W=1500, H=850, D=600, door_layout=[1, 2], top_mode="onset"),
    dict(W=1500, H=1300, D=600, door_layout=[2, 1], top_mode="none"),
    dict(W=1800, H=2000, D=600, door_layout=[2, 2], back_mode="inset"),
    dict(W=1790, H=1640, D=600, top_mode="none"), dict(W=1210, H=905, D=600, door_layout=[2, 2]),
]


@pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")
@pytest.mark.parametrize("case", CASES)
def test_js_matches_python(case):
    js = ("import {computeLayout} from './web/layout.js';"
          f"const L=computeLayout({json.dumps(case)});"
          "console.log(JSON.stringify({n:L.n, groups:L.groups, sides:L.doors.map(d=>d.side), nh:L.nh,"
          "doors:L.doors.map(d=>[d.x,d.z,d.w,d.h,...d.hingeZ]), dividers:L.dividers, shelves:L.shelfZ,"
          "legs:L.legs}))")
    out = json.loads(subprocess.run(["node", "--input-type=module", "-e", js], capture_output=True,
                                    text=True, check=True).stdout)
    p = Params(**{k: (float(v) if isinstance(v, int) else v) for k, v in case.items()})
    lay = compute_layout(p)
    assert out["n"] == lay.n_doors and out["groups"] == lay.groups and out["nh"] == lay.n_hinges
    assert out["sides"] == [d.hinge_side for d in lay.doors]
    for a, d in zip(out["doors"], lay.doors):
        assert a == pytest.approx([d.x, d.z, d.w, d.h, *d.hinge_z])
    flat = lambda xs: [v for x in xs for v in x]  # noqa: E731
    assert len(out["dividers"]) == len(lay.dividers)
    assert flat(out["dividers"]) == pytest.approx(flat(lay.dividers))
    assert out["shelves"] == pytest.approx(lay.shelf_z)
    assert len(out["legs"]) == len(lay.legs)
    assert flat(out["legs"]) == pytest.approx(flat(lay.legs))
