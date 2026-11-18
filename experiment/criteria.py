"""Grading criteria version, written into every result file (user decision 2026-11-18).

The version is a hash of the CONTENT of every file that decides a grade: the rules, the reference
model, both graders and the test requests. If any of them changes, the version changes, so a result
always shows which criteria graded it. Every grading run is also appended to results/grading_log.csv,
so a re-grade never replaces an earlier result without a trace.
"""

import csv
import datetime
import hashlib
import os
import subprocess

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

CRITERIA = [
    "prompts/system.md",                 # rules (absolute, common, per product)
    "cabinet_reference.py",              # reference model
    "experiment/evaluate_one.py",        # grader (against the reference model)
    "experiment/rule_check.py",          # checker (rules measured directly)
    "experiment/run_family.py",          # family grading (size, counts, door side)
    "experiment/tools_validate.py",      # checker validation cases
    "experiment/sentences.csv",          # test requests
    "experiment/sentences_priority.csv",
    "experiment/conversations.json",
    "experiment/families.json",
]


def version():
    h = hashlib.sha256()
    for rel in CRITERIA:
        h.update(rel.encode())
        with open(os.path.join(ROOT, rel), "rb") as f:
            h.update(f.read())
    return h.hexdigest()[:10]


def code_commit():
    sha = os.environ.get("GITHUB_SHA")
    if not sha:
        try:
            sha = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
        except Exception:  # noqa: BLE001
            sha = "unknown"
    return sha[:7]


def stamp(lines, experiment):
    """Insert the criteria version under the title and log the run. Returns the new lines."""
    v, c = version(), code_commit()
    now = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9))).strftime("%Y-%m-%d")
    head = [f"채점 기준 버전: `{v}` (규칙서·정답모델·채점기(정답모델기준)·검사기(규칙직접비교)·테스트 요청 파일의 내용 해시) · "
            f"코드 커밋 `{c}` · 채점일 {now}", ""]
    log = os.path.join(ROOT, "results", "grading_log.csv")
    new = not os.path.exists(log)
    with open(log, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if new:
            w.writerow(["graded_date", "experiment", "criteria_version", "code_commit", "summary"])
        w.writerow([now, experiment, v, c, lines[0].lstrip("# ").strip() if lines else ""])
    return lines[:1] + [""] + head + lines[1:]
