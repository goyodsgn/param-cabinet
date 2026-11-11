"""Step 4: robustness test. Resize every generated model many times and check it against the rules.

usage: python experiment/robustness.py --dirs generated generated_priority --n 30 --out results/step4

For each model the same random set of sizes is used (fixed seed), plus a few extreme corner cases.
Only W, H, D, leg_h and back_mode are changed, which every model must expose. A sample counts only
if the reference model itself is valid for that model's parameters at that size.
"""

import argparse
import csv
import glob
import json
import os
import random
import sys
from concurrent.futures import ProcessPoolExecutor, as_completed

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "experiment"))

CORNERS = [
    {"W": 400, "H": 500, "D": 350, "leg_h": 50, "back_mode": "onset"},
    {"W": 3600, "H": 2200, "D": 1000, "leg_h": 200, "back_mode": "inset"},
    {"W": 601, "H": 850, "D": 580, "leg_h": 100, "back_mode": "onset"},     # just over one door
    {"W": 1200, "H": 1004, "D": 580, "leg_h": 100, "back_mode": "onset"},   # door height exactly 900
    {"W": 1800, "H": 1704, "D": 580, "leg_h": 100, "back_mode": "inset"},   # door height exactly 1600
    {"W": 2400, "H": 850, "D": 700, "leg_h": 100, "back_mode": "inset"},    # 3 pins per side
]


def samples(n, seed):
    rng = random.Random(seed)
    out = [dict(c) for c in CORNERS]
    while len(out) < n:
        out.append({"W": round(rng.uniform(400, 3600)), "H": round(rng.uniform(500, 2200)),
                    "D": round(rng.uniform(350, 1000)), "leg_h": round(rng.uniform(50, 200)),
                    "back_mode": rng.choice(["onset", "inset"])})
    return out[:n]


def run_model(path, sample_list):
    """Runs in a worker process: load the model once, evaluate every sample."""
    import evaluate_one as ev
    from cabinet_reference import Params, compute_layout, validate

    rows = []
    try:
        mod = ev.load(path)
        base = dict(mod.PARAMS)
    except Exception as e:  # noqa: BLE001
        return [{"model": path, "i": -1, "status": "load_error", "error": str(e)[:200]}]
    for i, ov in enumerate(sample_list):
        params = dict(base)
        params.update(ov)
        # Is this size valid for the reference with the model's own settings?
        kw = {}
        for k in ev.OVERRIDABLE:
            v = params.get(k)
            if v is not None:
                kw[k] = str(v) if k == "back_mode" else (int(v) if k in ("n_doors", "n_shelves") else float(v))
        p = Params(**kw)
        if validate(p, compute_layout(p)):
            rows.append({"model": path, "i": i, "status": "skipped", **ov})
            continue
        res = ev.evaluate(path, ov, mod=mod)
        failed = [k for k, v in (res.get("checks") or {}).items() if not v]
        if not res.get("runs"):
            failed = ["runs"]
        rows.append({"model": path, "i": i, "status": "pass" if res.get("pass") else "fail",
                     "failed": " ".join(failed), "error": res.get("error", "")[:200],
                     "got": json.dumps(res.get("got", {}), ensure_ascii=False)[:400],
                     "expected": json.dumps(res.get("expected", {}), ensure_ascii=False)[:400], **ov})
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dirs", nargs="+", default=["generated", "generated_priority"])
    ap.add_argument("--n", type=int, default=30)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--out", default="results/step4")
    args = ap.parse_args()

    sample_list = samples(args.n, args.seed)
    models = []
    for d in args.dirs:
        models += sorted(glob.glob(os.path.join(ROOT, d, "*.py")))
    models.append(os.path.join(ROOT, "examples", "reference_generated.py"))

    rows = []
    with ProcessPoolExecutor(max_workers=args.workers) as ex:
        futs = {ex.submit(run_model, m, sample_list): m for m in models}
        for f in as_completed(futs):
            m = futs[f]
            try:
                r = f.result()
            except Exception as e:  # noqa: BLE001
                r = [{"model": m, "i": -1, "status": "crash", "error": str(e)[:200]}]
            rows += r
            done = [x for x in r if x["status"] in ("pass", "fail")]
            print(os.path.relpath(m, ROOT), sum(x["status"] == "pass" for x in done), "/", len(done), flush=True)

    for r in rows:
        r["model"] = os.path.relpath(r["model"], ROOT)
    os.makedirs(os.path.dirname(os.path.join(ROOT, args.out)), exist_ok=True)
    fields = ["model", "i", "status", "failed", "W", "H", "D", "leg_h", "back_mode", "error", "got", "expected"]
    with open(os.path.join(ROOT, args.out + ".csv"), "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(sorted(rows, key=lambda r: (r["model"], r["i"])))

    # Summary
    by_model = {}
    for r in rows:
        by_model.setdefault(r["model"], []).append(r)
    lines = [f"# Step 4 robustness: {args.n} sizes per model (seed {args.seed})", "",
             "Each model is resized to the same sizes (6 extreme cases + random). A size is skipped when",
             "the reference itself is invalid there for that model's own settings.", "",
             "| model | pass | tested | pass rate | most common failure |", "|---|---|---|---|---|"]
    total_pass = total = 0
    fail_counts = {}
    for m in sorted(by_model):
        rs = [r for r in by_model[m] if r["status"] in ("pass", "fail")]
        ok = sum(r["status"] == "pass" for r in rs)
        fc = {}
        for r in rs:
            for k in (r.get("failed") or "").split():
                fc[k] = fc.get(k, 0) + 1
        top = max(fc, key=fc.get) if fc else ""
        is_ref = m.startswith("examples/")
        if not is_ref:
            total_pass += ok
            total += len(rs)
            for k, v in fc.items():
                fail_counts[k] = fail_counts.get(k, 0) + v
        rate = f"{100 * ok / len(rs):.0f}%" if rs else "-"
        status = next((r["status"] for r in by_model[m] if r["status"] in ("load_error", "crash")), "")
        lines.append(f"| {m}{' (reference)' if is_ref else ''} | {ok} | {len(rs)} | {rate} | "
                     f"{top + (f' ({fc[top]})' if top else '') or status} |")
    lines += ["", f"**All generated models: {total_pass} / {total} resized samples pass "
              f"({100 * total_pass / max(total, 1):.0f}%)**", "", "Failures by check (generated models):", ""]
    for k, v in sorted(fail_counts.items(), key=lambda x: -x[1]):
        lines.append(f"- {k}: {v}")
    examples = [r for r in rows if r["status"] == "fail" and not r["model"].startswith("examples/")][:15]
    if examples:
        lines += ["", "Example failures:", "", "| model | W | H | D | leg_h | back | failed | error |",
                  "|---|---|---|---|---|---|---|---|"]
        for r in examples:
            lines.append(f"| {r['model']} | {r['W']} | {r['H']} | {r['D']} | {r['leg_h']} | {r['back_mode']} | "
                         f"{r['failed']} | {r['error'][:60].replace('|', '/')} |")
    open(os.path.join(ROOT, args.out + ".md"), "w", encoding="utf-8").write("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
