# -*- coding: utf-8 -*-
"""Flow 클립 오른쪽 아래의 반투명 별 모양 AI 마크를 조립 때 지운다.

왜 지우나 (2026-10 사용자 결정)
    세로 화면에서 마크가 크게 보여 시청을 방해한다. 대신 AI 생성물이라는 사실은
    ① 설명란 "AI로 만든 3D 애니메이션" ② 유튜브 「AI 사용(변경되거나 합성된 콘텐츠)」 고지로 반드시 밝힌다.
    영상 안에 심긴 보이지 않는 SynthID 워터마크는 그대로 남는다(지울 수도 없다).

어떻게 지우나 — 역 알파 블렌딩
    마크는 흰색을 알파 a 로 덮어 그린 것이다:  보이는 값 = a·255 + (1-a)·원래 값
    → 원래 값 = (보이는 값 - a·255) / (1 - a).  흐리게 뭉개는 delogo 와 달리 원래 화면이 거의 그대로 돌아온다.
    a(마크 모양)는 flowmaker/assets/flow_mark_alpha.png (720×1280, 마크 밖은 0).
    Flow 가 마크 모양·위치를 바꾸면 `unmark <프로젝트> --calibrate` 로 그 편 클립에서 다시 잰다.
"""
from __future__ import annotations

import statistics
import subprocess
from pathlib import Path

from .project import Project

ASSET = Path(__file__).resolve().parent / "assets" / "flow_mark_alpha.png"
FRAME = (720, 1280)
BOX = (564, 1124, 72, 72)          # 마크를 둘러싼 칸 (x, y, w, h) — 2026-10 실측: 별 중심 (600, 1160), 지름 약 48px
RING = 10                          # 배경을 추정할 바깥 테두리 두께(px)


def _ff(*args) -> None:
    subprocess.run(["ffmpeg", "-v", "error", *map(str, args)], check=True)


def blend_chain(src: str = "[0:v]", mask: str = "[1:v]") -> str:
    """filter_complex 앞부분: 마크를 지운 영상을 [um] 로 내보낸다. mask 입력은 `-loop 1 -i 마스크.png`."""
    expr = "if(gt(B\\,0)\\,clip((A-B)/max(1-B/255\\,0.08)\\,0\\,255)\\,A)"
    return (f"{src}format=gbrp[umf];{mask}format=gbrp[umm];"
            f"[umf][umm]blend=all_expr='{expr}':shortest=1,format=yuv420p[um]")


def mask_for(project: Project) -> Path | None:
    """이 편에 쓸 마스크. 편 폴더에 calibrate 결과가 있으면 그것, 없으면 저장소 기본값."""
    own = project.build / "mark_alpha.png"
    if own.exists():
        return own
    return ASSET if ASSET.exists() else None


def clip_size(path) -> tuple[int, int]:
    out = subprocess.check_output(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                                   "stream=width,height", "-of", "csv=p=0", str(path)]).decode().strip()
    w, h = out.split(",")[:2]
    return int(w), int(h)


# ── 마크 모양 재기 (calibrate) ─────────────────────────────────────────────────
def _bg_estimate(px, w, h, x, y, r):
    """칸 안 (x, y) 의 배경값 — 바깥 테두리에서 가로·세로로 선형 보간해 평균."""
    l = px[r - 1, y]; rt = px[w - r, y]; t = px[x, r - 1]; b = px[x, h - r]
    fx = (x - (r - 1)) / ((w - r) - (r - 1)); fy = (y - (r - 1)) / ((h - r) - (r - 1))
    return tuple(((l[c] * (1 - fx) + rt[c] * fx) + (t[c] * (1 - fy) + b[c] * fy)) / 2 for c in range(3))


def calibrate(project: Project, samples_per_clip: int = 5, max_ring_std: float = 6.0) -> Path:
    """편의 클립들에서 배경이 고른 장면만 골라 마크의 알파 모양을 잰다 → build/mark_alpha.png."""
    from PIL import Image
    bx, by, bw, bh = BOX
    r = RING
    W, H = bw + 2 * r, bh + 2 * r
    tmp = project.build / "unmark_cal"; tmp.mkdir(parents=True, exist_ok=True)
    clips = sorted(project.clips.glob("C*.mp4"))
    if not clips:
        raise SystemExit("클립이 없다 — collect 뒤에 하라")
    acc: dict[tuple[int, int], list[float]] = {}
    used = 0
    for clip in clips:
        if clip_size(clip) != FRAME:
            continue
        dur = float(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                                             "-of", "csv=p=0", str(clip)]).decode().strip())
        for k in range(samples_per_clip):
            t = dur * (k + 0.5) / samples_per_clip
            out = tmp / f"{clip.stem}_{k}.png"
            _ff("-ss", f"{t:.2f}", "-i", clip, "-frames:v", "1",
                "-vf", f"crop={W}:{H}:{bx - r}:{by - r}", out, "-y")
            im = Image.open(out).convert("RGB"); px = im.load()
            ring = [sum(px[i, j]) / 3 for i in range(W) for j in range(H)
                    if i < r or j < r or i >= W - r or j >= H - r]
            if statistics.pstdev(ring) > max_ring_std or statistics.mean(ring) > 225:
                continue                                  # 배경이 고르지 않거나 너무 밝으면 못 잰다
            used += 1
            for i in range(r, W - r):
                for j in range(r, H - r):
                    o = px[i, j]; bg = _bg_estimate(px, W, H, i, j, r)
                    vals = [(o[c] - bg[c]) / (255 - bg[c]) for c in range(3) if 255 - bg[c] > 30]
                    if vals:
                        acc.setdefault((i - r, j - r), []).append(sum(vals) / len(vals))
    if used < 5:
        raise SystemExit(f"배경이 고른 장면이 {used}개뿐이라 마크 모양을 못 잰다 — 기본 마스크를 쓴다")
    mask = Image.new("L", FRAME, 0); mp = mask.load()
    peak = 0.0
    for (i, j), v in acc.items():
        a = statistics.median(v)
        a = 0.0 if a < 0.04 else min(a, 0.95)
        peak = max(peak, a)
        mp[bx + i, by + j] = round(a * 255)
    if peak < 0.15:
        raise SystemExit(f"마크가 안 보인다 (최대 알파 {peak:.2f}) — 이 편 클립에는 마크가 없을 수 있다")
    out = project.build / "mark_alpha.png"
    mask.save(out)
    print(f"마크 모양 측정: 장면 {used}개 · 최대 알파 {peak:.2f} → {out}")
    return out


def preview(project: Project, n: int | None = None) -> Path:
    """한 클립의 중간 프레임을 지우기 전/후로 나란히(마크 부분 확대) 저장한다 → build/unmark_preview.png."""
    from PIL import Image
    m = mask_for(project)
    if not m:
        raise SystemExit("마스크가 없다")
    clips = sorted(project.clips.glob("C*.mp4"))
    clip = project.clip(n) if n else clips[len(clips) // 2]
    dur = float(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                                         "-of", "csv=p=0", str(clip)]).decode().strip())
    a, b = project.build / "unmark_a.png", project.build / "unmark_b.png"
    t = f"{dur / 2:.2f}"
    _ff("-ss", t, "-i", clip, "-frames:v", "1", a, "-y")
    _ff("-ss", t, "-i", clip, "-loop", "1", "-i", m, "-filter_complex", blend_chain(),
        "-map", "[um]", "-frames:v", "1", b, "-y")
    bx, by, bw, bh = BOX
    crop = (bx - 40, by - 40, bx + bw + 40, by + bh + 40)
    A, B = Image.open(a).crop(crop), Image.open(b).crop(crop)
    s = 3
    sheet = Image.new("RGB", (A.width * s * 2 + 10, A.height * s), (255, 0, 0))
    sheet.paste(A.resize((A.width * s, A.height * s)), (0, 0))
    sheet.paste(B.resize((B.width * s, B.height * s)), (A.width * s + 10, 0))
    out = project.build / "unmark_preview.png"
    sheet.save(out)
    print(f"미리보기(왼쪽 원본 · 오른쪽 지움) → {out}")
    return out
