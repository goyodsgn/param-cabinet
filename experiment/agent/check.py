"""Tool for the agent: build model.py and measure the company rules. Prints a short JSON summary."""
import json
import os
import sys

sys.path.insert(0, os.environ["REPO_ROOT"])
sys.path.insert(0, os.path.join(os.environ["REPO_ROOT"], "experiment"))

from rule_check import check_file  # noqa: E402

res = check_file(sys.argv[1] if len(sys.argv) > 1 else "model.py")
out = {"pass": res.get("pass"), "runs": res.get("runs"), "error": res.get("error", "")}
if res.get("runs"):
    out["failed"] = {k: res["messages"].get(k, [])[:3] for k, v in res["rules"].items() if not v}
    out["counts"] = res.get("counts")
print(json.dumps(out, ensure_ascii=False))
