"""The hand-written reference model wrapped in the generated-code contract (PARAMS + build).
Used as a smoke test for the evaluator: it must score 100%."""
import cadquery as cq  # noqa: F401  (contract requires the import)

from cabinet_reference import Params, build as _build

PARAMS = {"W": 1200.0, "H": 850.0, "D": 580.0, "leg_h": 100.0, "back_mode": "onset",
          "door_gap": 2.0, "door_max_w": 600.0, "pin_max_spacing": 500.0, "leg_max_spacing": 600.0,
          "n_doors": None, "n_shelves": None, "notes": []}


def build(params: dict):
    p = Params(**{k: v for k, v in params.items() if k in Params.__dataclass_fields__})
    if p.n_doors is not None:
        p.n_doors = int(p.n_doors)
    return _build(p)
