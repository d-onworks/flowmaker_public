# -*- coding: utf-8 -*-
"""컷 경계의 빠른 전환 — 조립(assemble) 때 앞 컷 끝 0.25초와 다음 컷 처음 0.25초에 카메라 움직임을 넣는다 (크레딧 0).

왜 (2026-11 사용자): 레퍼런스 쇼츠는 장면 안에서는 천천히 움직이다가 넘어가는 0.5~1초에 카메라가 휙 움직이며 넘어간다
(측정: 약 5~6초마다, 휙 패닝·빠르게 빠지기·기울며 휙). 따로 만든 클립을 그냥 붙이면 이 '호흡'이 없다.
ffmpeg 만 쓴다(맥 .venv 에 numpy 가 없다). 클립만 움직이고 자막·그래픽은 그 위에 얹으므로 흔들리지 않는다.

cuts.json 컷에 "trans": 종류 — 이 컷에서 다음 컷으로 넘어갈 때.
    cut        그냥 넘김 (기본)
    zoom_in    앞 컷이 가속하며 확대(빨려 들어감) → 다음 컷이 확대된 채 들어와 감속하며 제자리. 전체 → 부분(같은 각도)
    zoom_out   앞 컷이 살짝 확대되며 흐려짐 → 다음 컷이 크게 확대된 채 들어와 빠르게 빠짐. 부분 → 전체
    whip_left  카메라가 왼쪽으로 휙(그림은 오른쪽으로 흐름) — 같은 수준 장면끼리
    whip_right · whip_up · whip_down  같은 방식, 방향만 다름
시점이 바뀌는 전환(드론 전경 → 정면)은 이걸로 안 된다 — Flow 시작·끝 장면 비행(frames "end")으로 (guides/prompting.md 8-1절).
"""
from __future__ import annotations

import subprocess
from pathlib import Path

KINDS = ("cut", "zoom_in", "zoom_out", "whip_left", "whip_right", "whip_up", "whip_down")
D = 0.25          # 경계 한쪽의 길이(초) — 앞 0.25 + 뒤 0.25 = 0.5초 전환
OVER = 2.0        # 휙 패닝 끝 배율 — 이 여유만큼(화면 절반) 옆으로 밀린다
W, H = 720, 1280


def _expr(kind: str, side: str, t0: float) -> tuple[str, str, str]:
    """(배율 S, x 이동, y 이동) — ffmpeg 식. 창 안 진행 u: tail 은 t0 부터 D 동안, head 는 0 부터 D 동안 0→1."""
    u = f"clip((t-{t0:.3f})/{D},0,1)"
    acc = f"pow({u},2)"            # 가속 (끝 쪽)
    dec = f"pow(1-{u},2)"          # 감속 (처음 쪽)
    if kind == "zoom_in":
        return (f"(1+0.9*{acc})", "0", "0") if side == "tail" else (f"(1+0.6*{dec})", "0", "0")
    if kind == "zoom_out":
        return (f"(1+0.25*{acc})", "0", "0") if side == "tail" else (f"(1+0.9*{dec})", "0", "0")
    if kind.startswith("whip_"):
        span_x = f"(in_w-{W})/2"; span_y = f"(in_h-{H})/2"
        # 카메라가 왼쪽으로 가면 그림은 오른쪽으로 → 잘라 보는 창(x)은 왼쪽(음수)으로
        sx = {"whip_left": -1, "whip_right": 1, "whip_up": 0, "whip_down": 0}[kind]
        sy = {"whip_left": 0, "whip_right": 0, "whip_up": -1, "whip_down": 1}[kind]
        # 확대도 같이 키운다(처음부터 OVER 로 확대하면 창이 열리는 순간 화면이 '툭' 커진다 — 2026-11 시험)
        if side == "tail":       # 가운데 → 한쪽 끝으로 가속
            return (f"(1+{OVER - 1}*{acc})", f"{sx}*{span_x}", f"{sy}*{span_y}")
        return (f"(1+{OVER - 1}*{dec})", f"{-sx}*{span_x}", f"{-sy}*{span_y}")   # 반대쪽 끝에서 가운데로 감속
    return ("1", "0", "0")


def _vf(kind: str, side: str, t0: float) -> str:
    S, X, Y = _expr(kind, side, t0)
    blur = "tblend=all_mode=average,tblend=all_mode=average"   # 이웃 프레임을 섞어 움직임 흐림 (tmix 는 overlay 와 같이 쓰면 앞 프레임이 크게 번졌다)
    # gblur 는 넣지 않는다 — 창이 열리는 순간 화면 전체가 '툭' 흐려졌다(2026-11 시험). 흐림은 움직임에 비례하는 tmix 만.
    return (f"scale=w='trunc({W}*{S}/2)*2':h='trunc({H}*{S}/2)*2':eval=frame,"
            f"crop={W}:{H}:x='(in_w-{W})/2+{X}':y='(in_h-{H})/2+{Y}',setsar=1,{blur}")


def apply(path: Path, kind: str, side: str) -> bool:
    """path(720x1280·30fps 토막)의 끝(tail) 또는 처음(head) D 초에 전환을 입힌다. 길이는 그대로. 바꿨으면 True."""
    if kind in (None, "", "cut"):
        return False
    if kind not in KINDS:
        raise SystemExit(f"trans '{kind}' 는 없는 전환이다 — {', '.join(KINDS)}")
    dur = float(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                                         "-of", "csv=p=0", str(path)]).decode().strip())
    if dur < D * 2 + 0.1:
        return False
    # 전환된 흐름을 원본 위에 창 구간에서만 덮는다(overlay enable) — trim·concat 은 tmix 때문에 프레임이 빠졌다
    t0 = dur - D if side == "tail" else 0.0
    win = f"between(t,{t0:.3f},{dur:.3f})" if side == "tail" else f"lt(t,{D})"
    # tblend 두 번은 앞 프레임 2장을 먹는다 → 앞에 2장을 복제해 붙이고 시각을 되돌린다(다음 컷 처음이 2프레임 원본으로 보였다)
    pre = "tpad=start=2:start_mode=clone,setpts=PTS-2/(30*TB),"
    fc = f"[0:v]split=2[o][m];[m]{pre}{_vf(kind, side, t0)}[w];[o][w]overlay=0:0:enable='{win}'[v]"
    tmp = path.with_name(path.stem + f"_{side}.mp4")
    subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-filter_complex", fc, "-map", "[v]", "-an",
                    "-c:v", "libx264", "-preset", "medium", "-crf", "17", "-pix_fmt", "yuv420p", "-r", "30",
                    str(tmp), "-y"], check=True)
    tmp.replace(path)
    return True
