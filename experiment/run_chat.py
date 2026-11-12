"""Check every turn of the conversation test against what the customer had asked for by then.

For each conversation and turn k:
- read request: the model's PARAMS hold the values asked so far (sizes, top/back mode, door arrangement,
  shelves, lowest space at least the asked height)
- geometry: the model's parts match the reference built from the ASKED spec (evaluate_one with a
  reference), including every company rule
A turn passes when both hold. The final turn is the result of the conversation.

usage: python experiment/run_chat.py [--dir generated_chat] [--out results/chat] [--previews]
"""

import argparse
import csv
import json
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from cabinet_reference import Params, door_count  # noqa: E402

CHECKS = ["params", "absolute_rules", "solids", "carcass_parts", "top_panel", "back_panel", "overall_size",
          "door_count", "door_gap", "hinge_count", "hinge_sides", "divider_count", "divider_position",
          "shelf_count", "shelf_spaces", "pin_count", "leg_count"]
DEFAULTS = {"leg_h": 100, "top_mode": "inset", "back_mode": "onset"}


def run_eval(path, reference, timeout=240):
    cmd = [sys.executable, os.path.join(ROOT, "experiment", "evaluate_one.py"), path, "null", json.dumps(reference)]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, cwd=ROOT)
        line = r.stdout.strip().splitlines()[-1] if r.stdout.strip() else ""
        return json.loads(line) if line else {"runs": False, "error": (r.stderr or "no output")[-300:]}
    except subprocess.TimeoutExpired:
        return {"runs": False, "error": f"timeout after {timeout}s"}


def norm_layout(layout, W):
    """None and an all-single-door layout with the default count mean the same cabinet."""
    if not layout:
        return None
    layout = [int(g) for g in layout]
    if all(g == 1 for g in layout) and len(layout) == door_count(Params(W=float(W))):
        return None
    return layout


def read_check(got, want):
    """Compare the model's PARAMS with the asked spec. Returns a list of mismatches."""
    bad = []
    full = {**DEFAULTS, **want}
    for k, v in full.items():
        g = got.get(k)
        if k == "door_layout":
            continue
        if k == "bottom_clear_min":
            ok = g is not None and float(g) >= float(v) - 1e-6
        elif isinstance(v, str):
            ok = str(g) == v
        else:
            ok = g is not None and abs(float(g) - float(v)) < 1e-6
        if not ok:
            bad.append(f"{k}={g} (asked {v})")
    W = want.get("W", 1200)
    try:
        if norm_layout(got.get("door_layout"), W) != norm_layout(want.get("door_layout"), W):
            bad.append(f"door_layout={got.get('door_layout')} (asked {want.get('door_layout')})")
    except (TypeError, ValueError):
        bad.append(f"door_layout={got.get('door_layout')} unreadable")
    if "n_shelves" not in want and got.get("n_shelves") is not None:
        bad.append(f"n_shelves={got.get('n_shelves')} (not asked)")
    return bad


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default="generated_chat")
    ap.add_argument("--out", default="results/chat")
    ap.add_argument("--conversations", default="experiment/conversations.json")
    ap.add_argument("--previews", action="store_true")
    args = ap.parse_args()

    convs = json.load(open(os.path.join(ROOT, args.conversations), encoding="utf-8"))
    rows = []
    for c in convs:
        for k, want in enumerate(c["expect"], start=1):
            path = os.path.join(ROOT, args.dir, f"{c['id']}_t{k}.py")
            if not os.path.exists(path):
                continue
            # First pass: read the model's own PARAMS (no reference), to compare with the request
            own = run_eval(path, {**DEFAULTS, **want})
            got = own.get("defaults") or {}
            ref = {**DEFAULTS, **want}
            # A lowest space asked as "fits albums" is a minimum: judge with the model's own height if higher
            if "bottom_clear_min" in want and got.get("bottom_clear_min") is not None:
                try:
                    ref["bottom_clear_min"] = max(float(want["bottom_clear_min"]), float(got["bottom_clear_min"]))
                except (TypeError, ValueError):
                    pass
            res = own if ref == {**DEFAULTS, **want} else run_eval(path, ref)
            mism = read_check(got, want) if res.get("runs") else ["did not run"]
            failed = [ch for ch in CHECKS if (res.get("checks") or {}).get(ch) is False]
            row = {"id": c["id"], "turn": k, "of": len(c["expect"]), "customer": c["turns"][k - 1],
                   "runs": bool(res.get("runs")), "read_request": not mism, "geometry": bool(res.get("pass")),
                   "pass": bool(res.get("runs")) and not mism and bool(res.get("pass")),
                   "read_mismatch": "; ".join(mism), "failed_checks": " ".join(failed),
                   "notes": " / ".join(res.get("notes") or []), "error": res.get("error", ""),
                   "got": json.dumps(res.get("got", {}), ensure_ascii=False)[:600],
                   "expected": json.dumps(res.get("expected", {}), ensure_ascii=False)[:600]}
            for ch in CHECKS:
                row[ch] = (res.get("checks") or {}).get(ch, "")
            rows.append(row)
            print(f"{c['id']} t{k}", "PASS" if row["pass"] else "FAIL", row["read_mismatch"][:80],
                  row["failed_checks"], row["error"][:80], flush=True)
            if args.previews and res.get("runs"):
                png = os.path.join(ROOT, args.dir, f"{c['id']}_t{k}.png")
                title = f"{c['id']} turn {k}: " + json.dumps(want, ensure_ascii=False)
                try:
                    subprocess.run([sys.executable, os.path.join(ROOT, "experiment", "preview_one.py"), path, png, title],
                                   cwd=ROOT, timeout=240, capture_output=True)
                except subprocess.TimeoutExpired:
                    pass

    os.makedirs(os.path.dirname(os.path.join(ROOT, args.out)), exist_ok=True)
    fields = list(rows[0].keys()) if rows else ["id"]
    with open(os.path.join(ROOT, args.out + ".csv"), "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)

    def mark(v):
        return "O" if v is True else "X" if v is False else "-"

    finals = [r for r in rows if r["turn"] == r["of"]]
    firsts = [r for r in rows if r["turn"] == 1]
    lines = [f"# {os.path.basename(args.out)}: conversation test",
             "",
             f"- Turn 1 pass: {sum(r['pass'] for r in firsts)} / {len(firsts)}",
             f"- Final turn pass: {sum(r['pass'] for r in finals)} / {len(finals)}",
             f"- Final turn, request read correctly: {sum(r['read_request'] for r in finals)} / {len(finals)}",
             f"- Final turn, geometry and company rules: {sum(r['geometry'] for r in finals)} / {len(finals)}",
             "",
             "| id | turn | customer | runs | read | geometry | pass | what went wrong |",
             "|---|---|---|---|---|---|---|---|"]
    for r in rows:
        wrong = "; ".join(x for x in (r["read_mismatch"], r["failed_checks"], r["error"][:80]) if x)
        lines.append(f"| {r['id']} | {r['turn']} | {r['customer']} | {mark(r['runs'])} | {mark(r['read_request'])} | "
                     f"{mark(r['geometry'])} | {mark(r['pass'])} | {wrong.replace('|', '/')} |")
    lines += ["", "Pass rate per check, final turn:", ""]
    for ch in CHECKS:
        ok = sum(1 for r in finals if r[ch] is True)
        applies = sum(1 for r in finals if r[ch] != "")
        lines.append(f"- {ch}: {ok} / {applies}")
    notes = [r for r in finals if r["notes"]]
    if notes:
        lines += ["", "Notes the model wrote (final turn):", ""]
        lines += [f"- {r['id']}: {r['notes']}" for r in notes]
    open(os.path.join(ROOT, args.out + ".md"), "w", encoding="utf-8").write("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
