"""Conversation test with an agent (Claude Code, Pro subscription) instead of a single model call.

For each conversation, a fresh empty folder gets only: the rule check tool (check.py). The agent gets the
company rules as its system prompt, writes model.py, runs the checker, fixes, and answers. The second
customer turn resumes the same session. After each turn model.py is saved as <id>_t<k>.py so
run_chat.py can grade it exactly like the model-only baseline.

Usage is kept small: our short system prompt replaces Claude Code's default one, only four tools are
allowed (read/write/edit inside the folder, and the one check command), and turns are capped.

usage: python experiment/run_agent.py --only c01,c08 [--model claude-sonnet-5-5] [--max-turns 8]
Needs CLAUDE_CODE_OAUTH_TOKEN (claude setup-token) and the claude CLI.
Writes generated_agent/<id>_t<k>.py, <id>.chat.md and results/agent_usage.csv / .md
"""

import argparse
import csv
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOLS = "Read(./**),Edit(./**),Write(./**),Bash(python check.py:*)"


def ask(prompt, cwd, system, model, max_turns, session=None):
    cmd = ["claude", "-p", prompt, "--output-format", "json", "--model", model, "--max-turns", str(max_turns),
           "--system-prompt", system, "--allowedTools", TOOLS,
           "--disallowedTools", "WebFetch,WebSearch,Task,NotebookEdit"]
    if session:
        cmd += ["--resume", session]
    env = dict(os.environ, REPO_ROOT=ROOT)
    t0 = time.time()
    r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, env=env, timeout=1200)
    try:
        out = json.loads(r.stdout.strip().splitlines()[-1])
    except Exception:  # noqa: BLE001
        out = {"is_error": True, "result": (r.stderr or r.stdout)[-500:]}
    out["_seconds"] = round(time.time() - t0)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default="c01,c08,c13,c21")
    ap.add_argument("--model", default="claude-sonnet-5-5")
    ap.add_argument("--max-turns", type=int, default=8)
    ap.add_argument("--out-dir", default="generated_agent")
    args = ap.parse_args()

    if not os.environ.get("CLAUDE_CODE_OAUTH_TOKEN"):
        sys.exit("CLAUDE_CODE_OAUTH_TOKEN is not set (run claude setup-token, add it as a repository secret).")
    rules = open(os.path.join(ROOT, "prompts", "system.md"), encoding="utf-8").read()
    head = open(os.path.join(ROOT, "experiment", "agent", "agent_prompt.md"), encoding="utf-8").read()
    system = head + "\n\n" + rules
    convs = json.load(open(os.path.join(ROOT, "experiment", "conversations.json"), encoding="utf-8"))
    keep = set(args.only.split(",")) if args.only else None
    convs = [c for c in convs if not keep or c["id"] in keep]
    out_dir = os.path.join(ROOT, args.out_dir)
    os.makedirs(out_dir, exist_ok=True)

    rows = []
    for c in convs:
        work = tempfile.mkdtemp(prefix=f"agent_{c['id']}_")
        shutil.copy(os.path.join(ROOT, "experiment", "agent", "check.py"), work)
        session, log = None, [f"# {c['id']} (agent)", ""]
        for k, turn in enumerate(c["turns"], start=1):
            res = ask(turn, work, system, args.model, args.max_turns, session)
            session = res.get("session_id", session)
            model_py = os.path.join(work, "model.py")
            if os.path.exists(model_py):
                shutil.copy(model_py, os.path.join(out_dir, f"{c['id']}_t{k}.py"))
            u = res.get("usage") or {}
            row = {"id": c["id"], "turn": k, "error": bool(res.get("is_error")),
                   "num_turns": res.get("num_turns"), "seconds": res["_seconds"],
                   "input": u.get("input_tokens", 0), "cache_write": u.get("cache_creation_input_tokens", 0),
                   "cache_read": u.get("cache_read_input_tokens", 0), "output": u.get("output_tokens", 0),
                   "api_equivalent_usd": res.get("total_cost_usd"), "reply": (res.get("result") or "")[:300]}
            rows.append(row)
            log += [f"## Turn {k}", "", f"**Customer:** {turn}", "", f"**Agent:** {row['reply']}", "",
                    f"(steps {row['num_turns']}, {row['seconds']}s, output tokens {row['output']})", ""]
            print(c["id"], k, {x: row[x] for x in ("num_turns", "seconds", "input", "cache_read", "output", "error")},
                  flush=True)
        open(os.path.join(out_dir, f"{c['id']}.chat.md"), "w", encoding="utf-8").write("\n".join(log))
        shutil.rmtree(work, ignore_errors=True)

    os.makedirs(os.path.join(ROOT, "results"), exist_ok=True)
    with open(os.path.join(ROOT, "results", "agent_usage.csv"), "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    tot = {k: sum(r[k] or 0 for r in rows) for k in ("input", "cache_write", "cache_read", "output", "seconds")}
    usd = sum(r["api_equivalent_usd"] or 0 for r in rows)
    md = ["# 에이전트 사용량 (Pro 구독, Claude Code)", "",
          f"- 대화 {len(convs)}개, 고객 턴 {len(rows)}회, 모델: {args.model}, 턴당 단계 상한 {args.max_turns}",
          f"- 토큰 합계: 입력 {tot['input']:,} · 캐시 쓰기 {tot['cache_write']:,} · 캐시 읽기 {tot['cache_read']:,} · 출력 {tot['output']:,}",
          f"- 같은 양을 API로 냈다면: 약 {usd:.2f}달러 (Claude Code가 계산한 값, Pro에서는 청구되지 않음)",
          f"- 걸린 시간: {tot['seconds'] // 60}분", "",
          "| id | 턴 | 단계 | 초 | 입력 | 캐시 읽기 | 출력 | API 환산 달러 | 오류 |", "|---|---|---|---|---|---|---|---|---|"]
    md += [f"| {r['id']} | {r['turn']} | {r['num_turns']} | {r['seconds']} | {r['input']:,} | {r['cache_read']:,} | "
           f"{r['output']:,} | {(r['api_equivalent_usd'] or 0):.3f} | {'O' if r['error'] else ''} |" for r in rows]
    open(os.path.join(ROOT, "results", "agent_usage.md"), "w", encoding="utf-8").write("\n".join(md) + "\n")


if __name__ == "__main__":
    main()
