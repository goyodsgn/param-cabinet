"""Product family test (research question 3): can the agent build furniture the rules were not written for,
using only the base cabinet rules? Five families, two customer turns each (make it, then resize it).

The agent (Claude Code, Pro subscription) gets the unchanged base cabinet rules plus family_prompt.md.
Every turn is graded without an answer key:
  runs      the file builds
  rules     the general rule checker (experiment/rule_check.py) on the parts it made
  size      overall bounding box of all parts matches the request (1 mm)
  request   drawer / door counts the customer asked for
and the agent's own notes (which rules it carried over, what it decided) are saved for review.

usage: python experiment/run_family.py [--only f1_tall,f2_wall] [--model claude-sonnet-5-5] [--max-turns 10]
       python experiment/run_family.py --grade-only   (re-grade saved models after a checker change)
Writes generated_family/<id>_t<k>.py, results/family.md / .csv, results/family/<id>_t<k>.png
"""

import argparse
import csv
import json
import os
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "experiment"))

from run_agent import ask  # noqa: E402


def grade(path, expect):
    from evaluate_one import as_shape, load
    from rule_check import check_parts

    out = {"runs": False, "rules": False, "size": False, "request": True, "failed": {}, "notes": [], "counts": {}}
    try:
        mod = load(path)
        parts = [(n, as_shape(s)) for n, s in mod.build(dict(mod.PARAMS))]
        out["notes"] = list(mod.PARAMS.get("notes") or [])
    except Exception as e:  # noqa: BLE001
        out["error"] = f"{type(e).__name__}: {e}"[:200]
        return out
    out["runs"] = True
    rc = check_parts(parts)
    out["rules"] = bool(rc.get("pass"))
    out["failed"] = {k: rc["messages"].get(k, [])[:2] for k, v in rc["rules"].items() if not v}
    out["counts"] = dict(rc.get("counts") or {})
    out["counts"]["parts"] = len(parts)
    bbs = [s.BoundingBox() for _, s in parts]
    size = [max(b.xmax for b in bbs) - min(b.xmin for b in bbs), max(b.ymax for b in bbs) - min(b.ymin for b in bbs),
            max(b.zmax for b in bbs) - min(b.zmin for b in bbs)]
    out["bbox"] = [round(v, 1) for v in size]
    out["size"] = all(abs(a - b) <= 1.0 for a, b in zip(size, expect["bbox"]))
    if "door_side" in expect:
        doors = [s.BoundingBox() for n, s in parts if n.startswith("door")]
        mid = (min(b.xmin for b in bbs) + max(b.xmax for b in bbs)) / 2
        side = "right" if doors and sum((b.xmin + b.xmax) / 2 for b in doors) / len(doors) > mid else "left"
        out["counts"]["door_side"] = side
        if side != expect["door_side"]:
            out["request"] = False
            out["failed"]["request"] = [f"door on the {side} (asked {expect['door_side']})"]
    for key in ("doors", "drawers"):
        if key in expect and out["counts"].get(key) != expect[key]:
            out["request"] = False
            out["failed"]["request"] = [f"{key} {out['counts'].get(key)} (asked {expect[key]})"]
    return out


def write_report(rows, model):
    with open(os.path.join(ROOT, "results", "family.csv"), "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        for r in rows:
            w.writerow({k: json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list)) else v for k, v in r.items()})

    ox = lambda v: "O" if v else "X"  # noqa: E731
    out = sum(r["output"] for r in rows)
    md = ["# 제품군 확장 테스트 (연구 질문 3)", "",
          "하부장 설계 규칙만 주고, 규칙이 없는 다른 제품을 만들게 했습니다. 제품마다 만들기 → 크기 바꾸기 2턴입니다.",
          "정답 모델은 없고, 범용 규칙 검사기와 요청 크기·개수로 채점합니다.", "",
          f"- 통과: {sum(r['pass'] for r in rows)} / {len(rows)} 턴",
          f"- 에이전트: Claude Code (Pro), 모델 {model}. 출력 토큰 {out:,}, API 환산 약 {sum(r['usd'] for r in rows):.2f}달러 (Pro라 청구 없음), "
          f"{sum(r['seconds'] for r in rows) // 60}분", "",
          "| 제품 | 턴 | 고객 | 실행 | 규칙 | 크기 | 요청 | 통과 | 부품 수 (문/서랍/선반/다리) | 걸린 것 |",
          "|---|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        c = r["counts"]
        cnt = f"{c.get('parts', '-')} ({c.get('doors', '-')}/{c.get('drawers', '-')}/{c.get('shelves', '-')}/{c.get('legs', '-')})"
        why = "; ".join(f"{k}: {v[0]}" for k, v in r["failed"].items() if v) or r["error"]
        md.append(f"| {r['family']} | {r['turn']} | {r['customer']} | {ox(r['runs'])} | {ox(r['rules'])} | {ox(r['size'])} | "
                  f"{ox(r['request'])} | {ox(r['pass'])} | {cnt} | {why[:160]} |")
    md += ["", "## 에이전트가 기존 규칙을 어떻게 옮겼나 (에이전트 메모, 마지막 턴)", ""]
    for r in rows:
        if r["turn"] == 2:
            md += [f"### {r['family']}", ""] + [f"- {n}" for n in r["notes"]] + [""]
    open(os.path.join(ROOT, "results", "family.md"), "w", encoding="utf-8").write("\n".join(md) + "\n")


def regrade(model):
    """Grade the saved models again (after a checker change) without running the agent."""
    fams = {f["id"]: f for f in json.load(open(os.path.join(ROOT, "experiment", "families.json"), encoding="utf-8"))}
    rows = []
    with open(os.path.join(ROOT, "results", "family.csv"), encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            k = int(r["turn"])
            r["turn"] = k
            g = grade(os.path.join(ROOT, "generated_family", f"{r['id']}_t{k}.py"), fams[r["id"]]["expect"][k - 1])
            for key in ("steps", "seconds", "output"):
                r[key] = int(float(r[key] or 0))
            r["usd"] = float(r["usd"] or 0)
            r.update({"runs": g["runs"], "rules": g["rules"], "size": g["size"], "request": g["request"],
                      "pass": g["runs"] and g["rules"] and g["size"] and g["request"], "bbox": g.get("bbox"),
                      "counts": g["counts"], "failed": g["failed"], "notes": g["notes"],
                      "error": g.get("error", "")})
            rows.append(r)
            print(r["id"], k, {x: r[x] for x in ("runs", "rules", "size", "request")}, g["failed"], flush=True)
    write_report(rows, model)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default="")
    ap.add_argument("--model", default="claude-sonnet-5-5")
    ap.add_argument("--max-turns", type=int, default=10)
    ap.add_argument("--grade-only", action="store_true", help="re-grade saved models, no agent")
    args = ap.parse_args()
    if args.grade_only:
        return regrade(args.model)
    if not os.environ.get("CLAUDE_CODE_OAUTH_TOKEN"):
        sys.exit("CLAUDE_CODE_OAUTH_TOKEN is not set.")

    rules = open(os.path.join(ROOT, "prompts", "system.md"), encoding="utf-8").read()
    head = open(os.path.join(ROOT, "experiment", "agent", "family_prompt.md"), encoding="utf-8").read()
    system = head + "\n\n" + rules
    fams = json.load(open(os.path.join(ROOT, "experiment", "families.json"), encoding="utf-8"))
    keep = set(args.only.split(",")) if args.only else None
    fams = [f for f in fams if not keep or f["id"] in keep]
    gen = os.path.join(ROOT, "generated_family")
    pics = os.path.join(ROOT, "results", "family")
    os.makedirs(gen, exist_ok=True)
    os.makedirs(pics, exist_ok=True)

    rows = []
    for f in fams:
        work = tempfile.mkdtemp(prefix=f"fam_{f['id']}_")
        shutil.copy(os.path.join(ROOT, "experiment", "agent", "check.py"), work)
        session, log = None, [f"# {f['id']} {f['family']} (agent)", ""]
        for k, (turn, expect) in enumerate(zip(f["turns"], f["expect"]), start=1):
            res = ask(turn, work, system, args.model, args.max_turns, session)
            session = res.get("session_id", session)
            name = f"{f['id']}_t{k}"
            dst = os.path.join(gen, name + ".py")
            src = os.path.join(work, "model.py")
            g = {"runs": False, "rules": False, "size": False, "request": False, "failed": {}, "notes": [], "counts": {}}
            if os.path.exists(src):
                shutil.copy(src, dst)
                g = grade(dst, expect)
                if g["runs"]:
                    subprocess.run([sys.executable, os.path.join(ROOT, "experiment", "preview_one.py"), dst,
                                    os.path.join(pics, name + ".png"), f"{f['id']} turn {k}"],
                                   capture_output=True, timeout=300)
            u = res.get("usage") or {}
            row = {"id": f["id"], "family": f["family"], "turn": k, "customer": turn,
                   "runs": g["runs"], "rules": g["rules"], "size": g["size"], "request": g["request"],
                   "pass": g["runs"] and g["rules"] and g["size"] and g["request"],
                   "bbox": g.get("bbox"), "counts": g["counts"], "failed": g["failed"], "notes": g["notes"],
                   "error": g.get("error", "") or ("agent error" if res.get("is_error") else ""),
                   "reply": (res.get("result") or "")[:400], "steps": res.get("num_turns"), "seconds": res["_seconds"],
                   "output": u.get("output_tokens", 0), "usd": res.get("total_cost_usd") or 0}
            rows.append(row)
            log += [f"## Turn {k}", "", f"**Customer:** {turn}", "", f"**Agent:** {row['reply']}", "",
                    "**Notes:**", ""] + [f"- {n}" for n in row["notes"]] + [""]
            print(f["id"], k, {x: row[x] for x in ("runs", "rules", "size", "request", "steps", "seconds", "output")},
                  flush=True)
        open(os.path.join(gen, f["id"] + ".chat.md"), "w", encoding="utf-8").write("\n".join(log))
        shutil.rmtree(work, ignore_errors=True)

    write_report(rows, args.model)


if __name__ == "__main__":
    main()
