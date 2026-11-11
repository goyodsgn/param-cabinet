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
CHECKS = ["params", "absolute_rules", "solids", "carcass_parts", "overall_size", "door_count", "door_gap",
          "hinge_count", "hinge_sides", "divider_count", "shelf_count", "pin_count", "leg_count"]


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
    ap.add_argument("--sentences", default="experiment/sentences.csv")
    args = ap.parse_args()

    sentences = {r["id"]: r for r in csv.DictReader(
        open(os.path.join(ROOT, args.sentences), encoding="utf-8"))}
    files = sorted(glob.glob(os.path.join(ROOT, args.dir, "*.py")))
    rows = []
    for f in files:
        mid = os.path.splitext(os.path.basename(f))[0]
        res = run_one(f)
        s = sentences.get(mid, {})
        want = json.loads(s["expect"]) if s.get("expect") else {
            k: float(s[k]) for k in ("W", "H", "D", "leg_h") if s.get(k)}
        got = dict(res.get("defaults", {}) or {})
        got.update(res.get("layout", {}) or {})

        def same(a, b):
            if isinstance(b, str):
                return str(a) == b
            try:
                return a is not None and abs(float(a) - float(b)) < 1e-6
            except (TypeError, ValueError):
                return False

        read_ok = bool(want) and all(same(got.get(k), v) for k, v in want.items())
        conflict = s.get("conflict") == "1"
        row = {"id": mid, "sentence": s.get("sentence", ""), "runs": res.get("runs", False),
               "read_request": read_ok if want else "",
               "conflict_noted": (len(res.get("notes", [])) > 0) if conflict else "",
               "param_count": res.get("param_count", ""),
               "pass": res.get("pass", False), "error": res.get("error", "")}
        for c in CHECKS:
            row[c] = res.get("checks", {}).get(c, "")
        row["got"] = json.dumps(res.get("got", {}), ensure_ascii=False)
        row["notes"] = " / ".join(res.get("notes", []))
        row["expected"] = json.dumps(res.get("expected", {}), ensure_ascii=False)
        if want and not read_ok:
            row["pass"] = False
        if conflict and not row["conflict_noted"]:
            row["pass"] = False
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
    lines = [f"# {os.path.basename(args.out)}: {sum(r['pass'] for r in rows)} / {n} pass all checks", "",
             "| id | runs | read request | conflict noted | " + " | ".join(CHECKS) + " | param count | error |",
             "|" + "---|" * (len(CHECKS) + 6)]
    for r in rows:
        lines.append(f"| {r['id']} | {mark(r['runs'])} | {mark(r['read_request'])} | {mark(r['conflict_noted'])} | "
                     + " | ".join(mark(r[c]) for c in CHECKS)
                     + f" | {r['param_count']} | {r['error'][:80].replace('|', '/')} |")
    lines += ["", "Pass rate per check (out of the rows where it applies):", ""]
    for c in ["runs", "read_request", "conflict_noted"] + CHECKS:
        ok = sum(1 for r in rows if r[c] is True)
        applies = sum(1 for r in rows if r[c] != "")
        lines.append(f"- {c}: {ok} / {applies}")
    notes = [r for r in rows if r["notes"]]
    if notes:
        lines += ["", "Notes the model wrote:", ""]
        lines += [f"- {r['id']}: {r['notes']}" for r in notes]
    open(os.path.join(ROOT, args.out + ".md"), "w", encoding="utf-8").write("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
