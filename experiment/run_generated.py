"""Run every generated model once at its own default parameters and tabulate the result.

usage: python experiment/run_generated.py [--dir generated] [--out results/step3]
Each model runs in its own process with a time limit. Writes <out>.csv and <out>.md.
"""

import argparse
import csv
import glob
import json
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CHECKS = ["params", "solids", "carcass_parts", "door_count", "hinge_count", "hinge_sides",
          "leg_count", "overall_size"]


def run_one(path, overrides=None, timeout=180):
    cmd = [sys.executable, os.path.join(ROOT, "experiment", "evaluate_one.py"), path]
    if overrides:
        cmd.append(json.dumps(overrides))
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, cwd=ROOT)
        line = r.stdout.strip().splitlines()[-1] if r.stdout.strip() else ""
        return json.loads(line) if line else {"runs": False, "error": (r.stderr or "no output")[-300:]}
    except subprocess.TimeoutExpired:
        return {"runs": False, "error": f"timeout after {timeout}s"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default="generated")
    ap.add_argument("--out", default="results/step3")
    args = ap.parse_args()

    sentences = {r["id"]: r for r in csv.DictReader(
        open(os.path.join(ROOT, "experiment", "sentences.csv"), encoding="utf-8"))}
    files = sorted(glob.glob(os.path.join(ROOT, args.dir, "*.py")))
    rows = []
    for f in files:
        mid = os.path.splitext(os.path.basename(f))[0]
        res = run_one(f)
        s = sentences.get(mid, {})
        want = {k: float(s[k]) for k in ("W", "H", "D", "leg_h") if s.get(k)}
        got = res.get("defaults", {}) or {}
        read_ok = bool(want) and all(got.get(k) is not None and abs(float(got[k]) - v) < 1e-6
                                     for k, v in want.items())
        row = {"id": mid, "sentence": s.get("sentence", ""), "runs": res.get("runs", False),
               "read_request": read_ok if want else "",
               "param_count": res.get("param_count", ""),
               "pass": res.get("pass", False), "error": res.get("error", "")}
        for c in CHECKS:
            row[c] = res.get("checks", {}).get(c, "")
        row["got"] = json.dumps(res.get("got", {}), ensure_ascii=False)
        row["expected"] = json.dumps(res.get("expected", {}), ensure_ascii=False)
        rows.append(row)
        print(mid, "PASS" if row["pass"] else "FAIL", row["error"][:120])

    os.makedirs(os.path.dirname(os.path.join(ROOT, args.out)), exist_ok=True)
    fields = list(rows[0].keys()) if rows else ["id"]
    with open(os.path.join(ROOT, args.out + ".csv"), "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)

    def mark(v):
        return "O" if v is True else "X" if v is False else "-"

    n = len(rows)
    lines = [f"# Step 3 results: {sum(r['pass'] for r in rows)} / {n} pass all checks", "",
             "| id | runs | read request | " + " | ".join(CHECKS) + " | param count | error |",
             "|" + "---|" * (len(CHECKS) + 5)]
    for r in rows:
        lines.append(f"| {r['id']} | {mark(r['runs'])} | {mark(r['read_request'])} | "
                     + " | ".join(mark(r[c]) for c in CHECKS)
                     + f" | {r['param_count']} | {r['error'][:80].replace('|', '/')} |")
    lines += ["", "Pass rate per check:", ""]
    for c in ["runs", "read_request"] + CHECKS:
        ok = sum(1 for r in rows if r[c] is True)
        lines.append(f"- {c}: {ok} / {n}")
    open(os.path.join(ROOT, args.out + ".md"), "w", encoding="utf-8").write("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
