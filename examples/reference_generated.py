"""The hand-written reference model wrapped in the generated-code contract (PARAMS + build).
Used as a smoke test for the evaluator: it must score 100%."""
import cadquery as cq  # noqa: F401  (contract requires the import)

from cabinet_reference import Params, build as _build

PARAMS = {"W": 1200.0, "H": 850.0, "D": 580.0, "leg_h": 100.0}


def build(params: dict):
    p = Params(**{k: v for k, v in params.items() if k in Params.__dataclass_fields__})
    return _build(p)
