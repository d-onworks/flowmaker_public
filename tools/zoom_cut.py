#!/usr/bin/env python3
"""전경 → 빠른 줌인 → 클로즈업으로 넘어가는 클립 (크레딧 0, VM 에서 돈다).

사용자 요청(2026-11): "경복궁 전경을 보여주고 빠르게 근정전으로 줌인해서, 근정전 클로즈업에서 다음 이야기로".
천천히 움직일 이유가 없으면 빠른 전환으로 지루하지 않게.
Flow 영상은 카메라를 크게 움직이면 배치가 바뀌므로(경복궁 frames 시험), 확인된 보드 두 장으로 직접 만든다.

  1) 전경 유지 --hold 초 (아주 느리게 1.00→1.04)
  2) 빠른 줌인 --zoom 초 : 목표 지점(--target x,y, 전경 보드 좌표)으로 1.04→--to 배, 가속(ease-in)
     프레임마다 앞뒤 확대를 여러 장 섞어 줌 블러를 넣는다(빠른 이동이 자연스럽게 보이고, 확대로 흐려진 화질을 가린다)
  3) 줌 끝에서 --fade 초 동안 클로즈업 보드로 넘어감(클로즈업도 1.10→1.05 로 계속 다가오는 느낌)
  4) 클로즈업 유지 --close 초 (1.05→1.00 이 아니라 계속 다가오도록 1.05→1.12)
쓰는 법:
  python3 zoom_cut.py out.mp4 --wide build/board/C03.jpg --close build/board/C04.jpg --target 408,512 --to 3.2
출력: 720x1280, 30fps. 보드의 AI 마크는 지운다(--unmark none 이면 건너뜀). 두 장면으로 나눠 쓰려면 --split 으로
  out_a.mp4(전경+줌, 줌이 끝나는 순간까지) · out_b.mp4(클로즈업) 를 따로 낸다 — 컷 경계를 문장 경계에 맞출 때.
"""
import argparse, subprocess, numpy as np, cv2, sys, os
sys.path.insert(0, os.path.dirname(__file__))
from board_pan import unmark, frame, W, H

FPS = 30
ease_in = lambda u: np.clip(u, 0, 1) ** 2.2
ease_io = lambda u: 0.5 - 0.5 * np.cos(np.pi * np.clip(u, 0, 1))


def writer(path):
    return subprocess.Popen(["ffmpeg", "-loglevel", "error", "-y", "-f", "rawvideo", "-pix_fmt", "bgr24",
                             "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-pix_fmt", "yuv420p",
                             "-crf", "16", "-preset", "medium", path], stdin=subprocess.PIPE)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("out"); ap.add_argument("--wide", required=True); ap.add_argument("--close", required=True)
    ap.add_argument("--target", required=True, help="전경 보드에서 줌인할 지점 x,y")
    ap.add_argument("--to", type=float, default=3.0, help="줌 끝 배율")
    ap.add_argument("--hold", type=float, default=1.2); ap.add_argument("--zoom", type=float, default=0.7)
    ap.add_argument("--fade", type=float, default=0.2); ap.add_argument("--close-sec", type=float, default=3.0)
    ap.add_argument("--blur", type=int, default=7, help="줌 블러 표본 수 (1 이면 끔)")
    ap.add_argument("--close-center", help="클로즈업에서 다가갈 지점 x,y (클로즈업 보드 좌표, 기본 가운데)")
    ap.add_argument("--unmark", default="625,1230,715,1325"); ap.add_argument("--split", action="store_true")
    a = ap.parse_args()
    wide, close = cv2.imread(a.wide), cv2.imread(a.close)
    if a.unmark != "none":
        box = tuple(map(int, a.unmark.split(",")))
        fits = lambda im: im.shape[1] >= box[2] + 20 and im.shape[0] >= box[3] + 20   # 보드 크기(768x1376)일 때만
        wide = unmark(wide, box) if fits(wide) else wide
        close = unmark(close, box) if fits(close) else close
    tx, ty = map(float, a.target.split(","))
    c0 = (wide.shape[1] / 2, wide.shape[0] / 2)
    cc = tuple(map(float, a.close_center.split(","))) if a.close_center else (close.shape[1] / 2, close.shape[0] / 2)
    z1 = 1.04

    def wide_at(t):                       # t: 전경 구간 안 초 → (줌, 중심)
        if t <= a.hold:
            return 1.0 + (z1 - 1.0) * ease_io(t / a.hold), c0
        u = ease_in((t - a.hold) / a.zoom)
        z = z1 * (a.to / z1) ** u          # 배율은 지수로 — 일정한 '다가감' 느낌
        return z, (c0[0] + (tx - c0[0]) * u, c0[1] + (ty - c0[1]) * u)

    def wide_frame(t):
        if t <= a.hold or a.blur <= 1:
            z, c = wide_at(t); return frame(wide, z, *c).astype(np.float32)
        acc = np.zeros((H, W, 3), np.float32)
        for k in range(a.blur):            # 이 프레임이 비추는 1/FPS 동안의 여러 순간을 섞는다
            z, c = wide_at(t - k / (FPS * a.blur))
            acc += frame(wide, z, *c)
        return acc / a.blur

    close_z = lambda s: 1.10 + (1.16 - 1.10) * (s / (a.fade + a.close_sec))
    t_wide = a.hold + a.zoom
    n_total = int(round((t_wide + a.close_sec) * FPS))
    n_split = int(round(t_wide * FPS))
    outs = [writer(a.out.replace(".mp4", "_a.mp4")), writer(a.out.replace(".mp4", "_b.mp4"))] if a.split else [writer(a.out)]
    for i in range(n_total):
        t = i / FPS
        if t < t_wide - a.fade:
            img = wide_frame(t)
        elif t < t_wide:                    # 줌 끝 겹침: 전경(블러) → 클로즈업
            s = t - (t_wide - a.fade); m = ease_io(s / a.fade)
            img = wide_frame(t) * (1 - m) + frame(close, close_z(s), *cc).astype(np.float32) * m
        else:
            s = t - (t_wide - a.fade)
            img = frame(close, close_z(s), *cc).astype(np.float32)
        p = outs[1] if (a.split and i >= n_split) else outs[0]
        p.stdin.write(np.clip(img, 0, 255).astype(np.uint8).tobytes())
    for p in outs:
        p.stdin.close(); p.wait()
    print(f"{a.out}: 전경 {a.hold}s + 줌 {a.zoom}s (→×{a.to}) + 클로즈업 {a.close_sec}s · {n_total / FPS:.2f}s"
          + (f" · 나눔 {n_split / FPS:.2f}s / {(n_total - n_split) / FPS:.2f}s" if a.split else ""))


if __name__ == "__main__":
    main()
