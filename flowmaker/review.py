# -*- coding: utf-8 -*-
"""검수 — 클립마다 중간 프레임을 원본 해상도로 뽑고, 4장씩 가로 시트를 만든다.

★시트는 '무엇이 찍혔나' 훑어보는 용도다. 통과 판정은 원본 프레임(build/review/C##.png)을
  열어서 한다. 축소 시트에서는 손가락 뭉개짐·부유 사지·엉뚱한 숫자가 안 보인다.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

from .assemble import duration
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
    for i in range(0, len(have), 4):
        grp = have[i:i+4]
        lab = "-".join(f"C{c['n']:02d}" for c, _, _ in grp)
        make_sheet([p for _, p, _ in grp], out / f"sheet-{lab}.png")
    print(f"프레임 {len(have)}장 → {out.relative_to(project.dir)}/ · 없는 컷 {['C%02d' % n for n in miss] or '없음'}")
    for c, _, d in have:
        need = c.get("need")
        flag = " ★짧음" if need and need > d * 1.7 else ""
        print(f"  C{c['n']:02d} {d:5.2f}s (need {need if need is not None else '-'}){flag}  {c.get('desc','')}")
