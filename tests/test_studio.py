import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "local"))
sys.path.insert(0, os.path.join(ROOT, "experiment"))


def test_studio_builds_a_model_and_changes_a_parameter():
    pytest.importorskip("cadquery")
    import studio
    from evaluate_one import load

    path = os.path.join(ROOT, "examples", "reference_generated.py")
    params = dict(load(path).PARAMS)
    a = studio.build_payload(path, params)
    assert a["parts"] and a["check"]["pass"] is True
    assert abs((a["box"][3] - a["box"][0]) - params["W"]) < 1
    b = studio.build_payload(path, dict(params, W=900.0))
    assert abs((b["box"][3] - b["box"][0]) - 900) < 1
    assert any(p.get("o", {}).get("t") == "hinge" for p in b["parts"])
