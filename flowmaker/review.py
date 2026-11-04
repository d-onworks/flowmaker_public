# -*- coding: utf-8 -*-
"""검수 — 클립마다 중간 프레임을 원본 해상도로 뽑고, 4장씩 가로 시트를 만든다.

★시트는 '무엇이 찍혔나' 훑어보는 용도다. 통과 판정은 원본 프레임(build/review/C##.png)을 열어서 한다.
  축소 시트에서는 손가락 뭉개짐·부유 사지·엉뚱한 숫자가 안 보인다.
★움직임은 motion_C##.png 로 본다 — 완성본에 들어가는 구간 전체를 0.6초 간격으로 깐 시트(왼쪽 위부터 오른쪽으로).
  시작·중간·끝 3장(strip_C##.png)만 보면 그 사이에서 생기는 사고를 놓친다. 2026-10 온돌 편에서 실제로 놓친 것:
  컷 끝에 꺼졌던 불이 되살아남, 꺼진 불빛이 다시 켜짐, 사람이 반투명해지며 순간이동, 장면이 중간에 다른 장면으로 바뀜.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

import math

from .assemble import duration, lead_of, used_span
from .project import Project


def make_sheet(pngs: list[Path], out: Path) -> None:
    """1장이면 그대로 축소, 2장 이상이면 가로로 이어 붙인다 (hstack 은 입력 2개부터)."""
    ins = []
    for p in pngs:
        ins += ["-i", str(p)]
    if len(pngs) == 1:
        graph = "[0]scale=1440:-1"
    else:
        graph = f"[{']['.join(str(k) for k in range(len(pngs)))}]hstack=inputs={len(pngs)},scale=1440:-1"
    subprocess.run(["ffmpeg", "-v", "error", *ins, "-filter_complex", graph, str(out), "-y"], check=True)


STEP = 0.6      # 움직임 시트 간격(초)
COLS = 7


def motion_sheet(src: Path, start: float, end: float, out: Path, step: float = STEP) -> int:
    """src 의 [start, end) 구간을 step 초마다 한 장씩, 가로 COLS 장 격자로 이어 붙인다. 뽑은 장수를 돌려준다."""
    n = max(1, math.ceil((end - start) / step))
    rows = math.ceil(n / COLS)
    subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{start:.2f}", "-t", f"{end - start:.2f}", "-i", str(src),
                    "-vf", f"fps=1/{step},scale=200:-1,tile={min(n, COLS)}x{rows}:padding=4:color=white",
                    "-frames:v", "1", str(out), "-y"], check=True)
    return n


def _mmss(t: float) -> str:
    return f"{int(t // 60)}:{t % 60:04.1f}"


def run(project: Project) -> None:
    cuts = project.load_cuts()
    out = project.build / "review"; out.mkdir(parents=True, exist_ok=True)
    have, miss = [], []
    for c in cuts:
        src = project.clip(c["n"])
        if not src.exists():
            miss.append(c["n"]); continue
        d = duration(src)
        png = out / f"C{c['n']:02d}.png"
        subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{d/2:.2f}", "-i", str(src),
                        "-frames:v", "1", str(png), "-y"], check=True)
        have.append((c, png, d))
    # 움직임 검수용: 컷마다 시작·중간·끝(need 안쪽) 세 프레임을 원본 해상도로 이어 붙인다 → strip_C##.png
    for c, _, d in have:
        need = float(c.get("need") or d)
        ts = [0.4, need / 2, max(min(need, d) - 0.3, 0.5)]
        ins = []
        for k, t in enumerate(ts):
            f = out / f"_f{c['n']:02d}_{k}.png"
            subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{t:.2f}", "-i", str(project.clip(c["n"])),
                            "-frames:v", "1", str(f), "-y"], check=True)
            ins += ["-i", str(f)]
        subprocess.run(["ffmpeg", "-v", "error", *ins, "-filter_complex", "[0][1][2]hstack=inputs=3",
                        str(out / f"strip_C{c['n']:02d}.png"), "-y"], check=True)
    # 움직임 검수용: 완성본에 들어가는 구간 전체를 0.6초 간격으로 → motion_C##.png
    at, spans = 0.0, {}
    for c in cuts:                                   # 완성본 안 위치 (앞 컷 need 의 누적)
        spans[c["n"]] = at; at += float(c.get("need") or 0)
    print(f"움직임 시트 ({STEP}초 간격, 왼쪽 위부터) — 사이에서 생기는 사고(되살아남·깜빡임·순간이동·장면 바뀜)는 여기서 잡는다")
    for c, _, d in have:
        a, b = used_span(c, d)
        k = motion_sheet(project.clip(c["n"]), a, b, out / f"motion_C{c['n']:02d}.png")
        cut = " · until " + str(c["until"]) if c.get("until") else ""
        ld = lead_of(c)
        if ld:
            motion_sheet(project.clip(ld[0]), ld[1], ld[1] + ld[2], out / f"motion_C{c['n']:02d}_lead.png")
            cut += f" · 앞에 C{ld[0]:02d} {ld[1]:.1f}~{ld[1] + ld[2]:.1f}s (motion_C{c['n']:02d}_lead.png)"
        print(f"  motion_C{c['n']:02d}.png  클립 {a:.1f}~{b:.1f}s → 영상 {_mmss(spans[c['n']])}~{_mmss(spans[c['n']] + float(c.get('need') or b - a))} · {k}장{cut}")
        for m in c.get("must") or []:
            print(f"      □ {m}")
        if c.get("abstract"):
            print("      (상징 컷 — 사용자와 정한 그림인지 본다)")
    for i in range(0, len(have), 4):
        grp = have[i:i+4]
        lab = "-".join(f"C{c['n']:02d}" for c, _, _ in grp)
        make_sheet([p for _, p, _ in grp], out / f"sheet-{lab}.png")
    print(f"프레임 {len(have)}장 → {out.relative_to(project.dir)}/ · 없는 컷 {['C%02d' % n for n in miss] or '없음'}")
    for c, _, d in have:
        need = c.get("need")
        flag = " ★짧음" if need and need > d * 1.7 else ""
        print(f"  C{c['n']:02d} {d:5.2f}s (need {need if need is not None else '-'}){flag}  {c.get('desc','')}")
