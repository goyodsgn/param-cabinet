"""Cut list, edge banding and hardware list from any cabinet's parts (no extra company rules given).

Edge banding was not given as a rule. It is inferred from the existing joinery, and every inference is
written out so a person can check it (EDGE_RULES):
  1. A panel edge gets banding when it stays visible: no other panel covers it. An edge counts as covered
     when another panel or shelf lies against it within 2.5 mm (shelves keep a 1 mm side clearance).
     So the onset/inset choices for top, back and doors decide which edges are banded.
  2. Doors do not cover the carcass: they open, so the carcass front edges behind them are banded.
  3. Edges facing the wall (the rear of the cabinet) are not banded.
  4. The back panel is not banded (it faces the wall and is the thin 10 mm board).
  5. Doors are banded on all four edges (every door edge stays visible).
Banding thickness is unknown, so sizes are finished sizes; subtract the banding thickness from the cut
size per banded edge if the panel saw needs it.

usage: python experiment/cutlist.py MODEL.py OUT_STEM   -> OUT_STEM.csv, OUT_STEM.md, OUT_STEM.png
"""

import csv
import os
import sys
from collections import OrderedDict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

COVER_TOL = 2.5
EDGE_RULES = [
    "패널 모서리는 다른 판재가 2.5mm 안에 닿아 가리지 않으면 엣지를 붙인다 (선반 옆 1mm 여유는 가려진 것으로 봄)",
    "문은 열리므로 몸통 앞 모서리를 가리지 않는다고 본다: 측판·상하판·칸막이·선반 앞 모서리는 엣지",
    "벽을 향하는 뒤쪽 모서리는 엣지를 붙이지 않는다",
    "뒷판(10mm)은 엣지를 붙이지 않는다",
    "문은 네 모서리 모두 엣지",
]
KOR = {"side_left": "측판(좌)", "side_right": "측판(우)", "top": "상판", "bottom": "하판", "back": "뒷판",
       "divider": "칸막이", "shelf": "선반", "door": "문"}
DIR_KOR = {("y", -1): "앞", ("y", 1): "뒤", ("z", 1): "위", ("z", -1): "아래", ("x", -1): "왼쪽", ("x", 1): "오른쪽"}


def kind(name):
    for k in ("door", "shelf", "pin", "leg", "divider", "back", "side", "top", "bottom"):
        if name.startswith(k):
            return k
    return "panel"


def bbox(s):
    b = s.BoundingBox()
    return {"x": (b.xmin, b.xmax), "y": (b.ymin, b.ymax), "z": (b.zmin, b.zmax)}


def label(name):
    k = kind(name)
    if name in KOR:
        return KOR[name]
    return KOR.get(k, name)


def edges_of(name, b, others, y_rear):
    """Return (thickness axis, [(axis, direction)] of banded edges)."""
    dims = {a: b[a][1] - b[a][0] for a in "xyz"}
    thin = min(dims, key=dims.get)
    k = kind(name)
    faces = [(a, d) for a in "xyz" if a != thin for d in (-1, 1)]
    if k == "back":
        return thin, []
    if k == "door":
        return thin, faces
    banded = []
    for a, d in faces:
        c = b[a][1] if d > 0 else b[a][0]
        if a == "y" and d > 0 and abs(c - y_rear) < COVER_TOL:
            continue                                   # rear edge against the wall
        covered = False
        u, v = [x for x in "xyz" if x != a]
        area = (b[u][1] - b[u][0]) * (b[v][1] - b[v][0])
        for on, ob in others:
            if on == name:
                continue
            gap = (ob[a][0] - c) if d > 0 else (c - ob[a][1])
            if not (-COVER_TOL <= gap <= COVER_TOL):
                continue
            ou = min(b[u][1], ob[u][1]) - max(b[u][0], ob[u][0])
            ov = min(b[v][1], ob[v][1]) - max(b[v][0], ob[v][0])
            if ou > 0 and ov > 0 and ou * ov >= 0.5 * area:
                covered = True
                break
        if not covered:
            banded.append((a, d))
    return thin, banded


def cut_rows(parts):
    boxes = [(n, bbox(s)) for n, s in parts]
    cover = [(n, b) for n, b in boxes if kind(n) not in ("door", "pin", "leg")]
    y_rear = max(b["y"][1] for _, b in cover)
    rows = OrderedDict()
    hardware = {"경첩(컵 35)": 0, "선반 다보": 0, "다릿발": 0}
    from rule_check import cups_of

    for (n, s), (_, b) in zip(parts, boxes):
        k = kind(n)
        if k == "pin":
            hardware["선반 다보"] += 1
            continue
        if k == "leg":
            hardware["다릿발"] += 1
            continue
        if k == "door":
            hardware["경첩(컵 35)"] += len(cups_of(s))
        thin, banded = edges_of(n, b, cover, y_rear)
        dims = {a: round(b[a][1] - b[a][0], 1) for a in "xyz"}
        a1, a2 = sorted([a for a in "xyz" if a != thin], key=lambda a: -dims[a])   # length axis, width axis
        L, W, T = dims[a1], dims[a2], dims[thin]
        # Banded sides in cut-list notation: L = along the length (long sides), W = along the width
        nL = sum(1 for a, _ in banded if a == a2)        # faces normal to the width axis run along the length
        nW = sum(1 for a, _ in banded if a == a1)
        where = " ".join(DIR_KOR[(a, d)] for a, d in banded)
        key = (label(n), L, W, T, nL, nW, where)
        rows.setdefault(key, []).append(n)
    out = []
    for (lab, L, W, T, nL, nW, where), names in rows.items():
        out.append({"부재": lab, "수량": len(names), "길이": L, "폭": W, "두께": T,
                    "엣지 긴변": nL, "엣지 짧은변": nW, "엣지 위치": where or "없음",
                    "엣지 길이(mm)": round(len(names) * (nL * L + nW * W)), "부품 이름": " ".join(names)})
    return out, hardware


def draw(rows, path, title):
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Rectangle

    plt.rcParams["font.family"] = ["Noto Sans CJK KR", "NanumGothic", "DejaVu Sans"]

    ink, band, fill = "#1f1f1f", "#d1462f", "#f2efe8"
    n = len(rows)
    cols = 3
    nrow = (n + cols - 1) // cols
    fig, axes = plt.subplots(nrow, cols, figsize=(cols * 4.2, nrow * 3.0 + 0.8), dpi=130)
    axes = axes.flatten() if hasattr(axes, "flatten") else [axes]
    for ax, r in zip(axes, rows):
        L, W = r["길이"], r["폭"]
        s = 1.0 / max(L, W)
        w, h = L * s, W * s
        x0, y0 = (1 - w) / 2, (1 - h) / 2
        ax.add_patch(Rectangle((x0, y0), w, h, facecolor=fill, edgecolor=ink, linewidth=0.8))
        # long sides (top/bottom of the drawing), short sides (left/right)
        lw = 3.2
        if r["엣지 긴변"] >= 1:
            ax.plot([x0, x0 + w], [y0, y0], color=band, linewidth=lw, solid_capstyle="butt")
        if r["엣지 긴변"] >= 2:
            ax.plot([x0, x0 + w], [y0 + h, y0 + h], color=band, linewidth=lw, solid_capstyle="butt")
        if r["엣지 짧은변"] >= 1:
            ax.plot([x0, x0], [y0, y0 + h], color=band, linewidth=lw, solid_capstyle="butt")
        if r["엣지 짧은변"] >= 2:
            ax.plot([x0 + w, x0 + w], [y0, y0 + h], color=band, linewidth=lw, solid_capstyle="butt")
        ax.set_title(f"{r['부재']} × {r['수량']}", fontsize=11, color=ink, loc="left")
        ax.text(0.5, -0.02, f"{r['길이']:g} × {r['폭']:g} × {r['두께']:g}   엣지: {r['엣지 위치']}",
                ha="center", va="top", fontsize=8.5, color=ink, transform=ax.transAxes)
        ax.set_xlim(-0.02, 1.02)
        ax.set_ylim(-0.02, 1.02)
        ax.set_aspect("equal")
        ax.axis("off")
    for ax in list(axes)[n:]:
        ax.axis("off")
    fig.suptitle(title + "   (빨간 선 = 엣지, 도면 비율은 부재마다 따로 맞춤)", fontsize=11, color=ink, x=0.01, ha="left")
    fig.tight_layout()
    fig.savefig(path, facecolor="white")
    plt.close(fig)


def write(parts, stem, title):
    rows, hw = cut_rows(parts)
    with open(stem + ".csv", "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    total_edge = sum(r["엣지 길이(mm)"] for r in rows)
    md = [f"# 재단표: {title}", "", "| 부재 | 수량 | 길이 | 폭 | 두께 | 엣지 긴변 | 엣지 짧은변 | 엣지 위치 |",
          "|---|---|---|---|---|---|---|---|"]
    md += [f"| {r['부재']} | {r['수량']} | {r['길이']:g} | {r['폭']:g} | {r['두께']:g} | {r['엣지 긴변']} | "
           f"{r['엣지 짧은변']} | {r['엣지 위치']} |" for r in rows]
    md += ["", f"엣지 총 길이: {total_edge / 1000:.2f} m", "",
           "하드웨어: " + ", ".join(f"{k} {v}개" for k, v in hw.items()), "",
           "엣지 판단 근거 (규칙을 받지 않고 기존 규칙에서 추론):", ""]
    md += [f"{i}. {t}" for i, t in enumerate(EDGE_RULES, 1)]
    md += ["", "치수는 완성 치수입니다. 엣지 두께만큼 재단 치수를 줄여야 하면 엣지 붙는 변마다 빼야 합니다."]
    open(stem + ".md", "w", encoding="utf-8").write("\n".join(md) + "\n")
    draw(rows, stem + ".png", title)
    return rows, hw


if __name__ == "__main__":
    from evaluate_one import as_shape, load

    mod = load(sys.argv[1])
    ps = [(n, as_shape(s)) for n, s in mod.build(dict(mod.PARAMS))]
    write(ps, sys.argv[2], os.path.basename(sys.argv[1]))
