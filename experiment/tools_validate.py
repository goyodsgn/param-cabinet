"""Validate the general rule checker and produce sample cut lists.

1. Reference cabinets that follow every rule must pass.
2. Reference cabinets broken on purpose (one rule at a time) must fail on that rule.
3. Every LLM-generated model so far: the checker's verdict is compared with the reference-based evaluator.
4. Cut lists with edge banding for a few cabinets.

usage: python experiment/tools_validate.py   -> results/rule_check.md, results/cutlist/*
"""

import csv
import glob
import json
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "experiment"))

import cadquery as cq  # noqa: E402

from cabinet_reference import Params, build  # noqa: E402
from cutlist import EDGE_RULES, write  # noqa: E402
from rule_check import check_parts  # noqa: E402

GOOD = [
    ("기본 1200x850x580", {}),
    ("600x700x560 문 1짝", dict(W=600, H=700, D=560)),
    ("2400x1700x900 키큰장 크기", dict(W=2400, H=1700, D=900, leg_h=120)),
    ("1500 한쪽문+양문, 상판 덮음", dict(W=1500, D=600, door_layout=[1, 2], top_mode="onset")),
    ("900 싱크대(상판 없음), 뒷판 인셋", dict(W=900, D=600, top_mode="none", back_mode="inset")),
    ("1200x1500x450 아래칸 330 이상, 선반 3", dict(W=1200, H=1500, D=450, bottom_clear_min=330, n_shelves=3)),
    ("2100 한쪽문+양문+양문", dict(W=2100, D=600, door_layout=[1, 2, 2])),
]


def moved(solid, dz):
    return solid.translate(cq.Vector(0, 0, dz))


def broken_cases():
    out = [
        ("도어갭 3으로", dict(door_gap=3.0), None, ["door_gap"]),
        ("문 칸 폭 750 (W 1500, 최대 800으로)", dict(W=1500, door_max_w=800.0), None, ["door_cell"]),
        ("높이 1700인데 힌지 2개", dict(H=1700, hinge_rule=[(float("inf"), 2)]), None, ["hinge_count"]),
        ("힌지 끝 거리 150", dict(hinge_edge_offset=150.0), None, ["hinge_place"]),
        ("깊이 900인데 다보 간격 800", dict(D=900, H=1200, pin_max_spacing=800.0), None, ["shelf_pins"]),
        ("다릿발 간격 800", dict(W=2400, leg_max_spacing=800.0), None, ["leg_spacing"]),
        ("양문 사이에 칸막이를 빼버림 (경첩 R R)", dict(W=1800), "drop_divider_2", ["pair_sides"]),
        ("선반을 같은 자리에 하나 더", {}, "dup_shelf", ["overlap"]),
        ("선반 하나가 공중에 떠 있음", {}, "float_shelf", ["connected"]),
    ]
    return out


def mutate(parts, how):
    if how == "drop_divider_2":
        return [(n, s) for n, s in parts if n != "divider_2"]
    if how == "dup_shelf":
        s = dict(parts)["shelf_1"]
        return parts + [("shelf_99", s.copy())]
    if how == "float_shelf":
        s = dict(parts)["shelf_1"]
        return parts + [("shelf_98", moved(s, 3000))]
    return parts


def run_file(path, timeout=300):
    cmd = [sys.executable, os.path.join(ROOT, "experiment", "rule_check.py"), path]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, cwd=ROOT)
        line = r.stdout.strip().splitlines()[-1] if r.stdout.strip() else ""
        return json.loads(line) if line else {"pass": False, "runs": False, "error": r.stderr[-200:]}
    except subprocess.TimeoutExpired:
        return {"pass": False, "runs": False, "error": "timeout"}


def failed(res):
    return [k for k, v in (res.get("rules") or {}).items() if not v]


def main():
    md = ["# 범용 규칙 검사기 검증", "",
          "정답 모델 없이 형상만 재서 회사 규칙을 검사합니다. 아래 세 가지로 검사기가 믿을 만한지 확인했습니다.", ""]

    # 1. good
    md += ["## 1. 규칙을 지킨 캐비닛 (전부 통과해야 함)", "", "| 캐비닛 | 결과 | 걸린 규칙 |", "|---|---|---|"]
    good_ok = 0
    for name, kw in GOOD:
        res = check_parts(build(Params(**kw)))
        good_ok += res["pass"]
        md.append(f"| {name} | {'통과' if res['pass'] else '실패'} | {', '.join(failed(res)) or '-'} |")
        print(name, res["pass"], res.get("messages"))
    md += ["", f"{good_ok} / {len(GOOD)} 통과", ""]

    # 2. broken
    md += ["## 2. 일부러 규칙 하나를 깨뜨린 캐비닛 (그 규칙에서 걸려야 함)", "",
           "| 깨뜨린 것 | 걸려야 할 규칙 | 실제로 걸린 규칙 | 판정 |", "|---|---|---|---|"]
    bad_ok, cases = 0, broken_cases()
    for name, kw, how, want in cases:
        res = check_parts(mutate(build(Params(**kw)), how))
        got = failed(res)
        hit = all(w in got for w in want)
        bad_ok += hit
        md.append(f"| {name} | {', '.join(want)} | {', '.join(got) or '-'} | {'맞게 잡음' if hit else '놓침'} |")
        print(name, got, res.get("messages"))
    md += ["", f"{bad_ok} / {len(cases)} 맞게 잡음", ""]

    # 3. generated models vs the reference-based evaluator
    md += ["## 3. 지금까지 AI가 만든 모델: 정답 모델 채점과 비교", "",
           "정답 모델 채점은 요청한 사양의 정답과 비교하고, 검사기는 규칙만 봅니다. 둘의 판정이 같으면 "
           "정답 모델이 없는 새 제품군에서도 검사기를 채점 도구로 쓸 수 있습니다.", "",
           "| 묶음 | 모델 수 | 검사기 통과 | 정답 채점 통과 | 판정 일치 |", "|---|---|---|---|---|"]
    sets = [("대화형 1턴", "generated_chat/*_t1.py", "results/chat.csv", lambda r: (r["id"] + "_t" + r["turn"])),
            ("대화형 최종 턴", "generated_chat/*_t2.py", "results/chat.csv", lambda r: (r["id"] + "_t" + r["turn"])),
            ("문장 기본", "generated/*.py", "results/step3.csv", lambda r: r["id"]),
            ("문장 우선순위", "generated_priority/*.py", "results/step3_priority.csv", lambda r: r["id"])]
    disagree = []
    for title, pattern, csv_path, key in sets:
        ev = {}
        if os.path.exists(os.path.join(ROOT, csv_path)):
            for r in csv.DictReader(open(os.path.join(ROOT, csv_path), encoding="utf-8")):
                ev[key(r)] = r["pass"] == "True"
        files = sorted(glob.glob(os.path.join(ROOT, pattern)))
        n = agree = chk = evp = 0
        for f in files:
            mid = os.path.splitext(os.path.basename(f))[0]
            res = run_file(f)
            n += 1
            chk += bool(res.get("pass"))
            e = ev.get(mid)
            evp += bool(e)
            if e is not None and e == bool(res.get("pass")):
                agree += 1
            elif e is not None:
                disagree.append((title, mid, e, failed(res), res.get("messages"), res.get("error", "")))
            print(title, mid, res.get("pass"), e, failed(res))
        md.append(f"| {title} | {n} | {chk} | {evp} | {agree} / {n} |")
    if disagree:
        md += ["", "판정이 다른 모델:", ""]
        for title, mid, e, got, msgs, err in disagree:
            md.append(f"- {title} {mid}: 정답 채점 {'통과' if e else '실패'}, 검사기 걸린 규칙 {', '.join(got) or '-'} "
                      f"{json.dumps(msgs, ensure_ascii=False)[:300]} {err}")
    md += ["", "검사기가 보지 않는 것: 고객 요청을 제대로 읽었는지(치수, 문 배치 등)와 한쪽문의 경첩 방향 "
           "선호(홀수 문의 마지막 문 오른쪽 등)는 규칙이 아니라 요청과 기본값의 문제라 정답 채점에서만 봅니다.", ""]

    # 4. cut lists
    os.makedirs(os.path.join(ROOT, "results", "cutlist"), exist_ok=True)
    samples = [("ref_1200x850x580", "기본 하부장 1200x850x580", Params()),
               ("ref_1500_onset_1-2", "1500 한쪽문+양문, 상판 덮음", Params(W=1500, D=600, door_layout=[1, 2], top_mode="onset")),
               ("ref_900_sink_inset", "900 싱크대, 뒷판 인셋", Params(W=900, D=600, top_mode="none", back_mode="inset"))]
    md += ["## 4. 재단표·엣지 샘플", ""]
    for stem, title, p in samples:
        rows, hw = write(build(p), os.path.join(ROOT, "results", "cutlist", stem), title)
        md.append(f"- {title}: `results/cutlist/{stem}.md` (부재 {sum(r['수량'] for r in rows)}개, "
                  + ", ".join(f"{k} {v}" for k, v in hw.items()) + ")")
    gen = os.path.join(ROOT, "generated_chat", "c12_t2.py")
    if os.path.exists(gen):
        from evaluate_one import as_shape, load

        mod = load(gen)
        parts = [(n, as_shape(s)) for n, s in mod.build(dict(mod.PARAMS))]
        rows, hw = write(parts, os.path.join(ROOT, "results", "cutlist", "ai_c12_final"),
                         "AI가 만든 모델 c12 최종 (1500 양문+한쪽문, 상판 덮음, 뒷판 인셋)")
        md.append("- AI가 만든 모델 c12 최종: `results/cutlist/ai_c12_final.md`")
    md += ["", "엣지 판단 근거 (규칙을 받지 않고 기존 규칙에서 추론):", ""]
    md += [f"{i}. {t}" for i, t in enumerate(EDGE_RULES, 1)]
    open(os.path.join(ROOT, "results", "rule_check.md"), "w", encoding="utf-8").write("\n".join(md) + "\n")


if __name__ == "__main__":
    main()
