#!/usr/bin/env python3
"""확인된 보드 이미지 여러 장으로 클립을 만든다 — 천천히 줌·이동하고 크로스페이드로 잇는다(크레딧 0).

Flow 영상이 보드의 구조를 따르지 않을 때(층수·모양·연결이 틀어질 때) 쓴다. 움직임이 없는 구조 컷용.
쓰는 법:
  python3 board_pan.py out.mp4 \
      --shot A.jpg:2.4:1.00:1.16:384,740:384,860 \
      --shot B.jpg:2.4:1.00:1.06:384,700:384,690 --fade 0.5
  --shot  이미지:보이는초:시작줌:끝줌:시작중심x,y:끝중심x,y  (보드 좌표)
  --fade  앞뒤 샷이 겹치는 초 (샷 길이에 포함)
  --unmark x0,y0,x1,y1  보드의 AI 마크 자리(기본 768x1376 보드의 오른쪽 아래). 'none' 이면 건너뜀
출력: 720x1280, 30fps, H.264 — clips/C##.mp4 로 두고 cuts.json 에 unmark:false, made 메모.
"""
import argparse, subprocess, numpy as np, cv2

W, H, FPS = 720, 1280, 30

def unmark(im, box, pad=14):
    x0, y0, x1, y1 = box; out = im.astype(np.float32)
    ys, xs = np.mgrid[y0-pad:y1+pad, x0-pad:x1+pad]
    ring = ~((ys >= y0) & (ys < y1) & (xs >= x0) & (xs < x1))
    A = np.c_[xs[ring], ys[ring], np.ones(ring.sum())]
    yy, xx = np.mgrid[y0:y1, x0:x1]
    for c in range(3):
        k, *_ = np.linalg.lstsq(A, out[y0-pad:y1+pad, x0-pad:x1+pad, c][ring], rcond=None)
        out[y0:y1, x0:x1, c] = k[0]*xx + k[1]*yy + k[2]
    m = np.zeros(im.shape[:2], np.float32); m[y0:y1, x0:x1] = 1; m = cv2.GaussianBlur(m, (0, 0), 4)[..., None]
    return (out*m + im.astype(np.float32)*(1-m)).clip(0, 255).astype(np.uint8)

ease = lambda u: 0.5 - 0.5*np.cos(np.pi*np.clip(u, 0, 1))

def frame(im, z, cx, cy):
    ih, iw = im.shape[:2]
    cw = min(iw, ih*W/H) / z; ch = cw*H/W
    cx = np.clip(cx, cw/2, iw-cw/2); cy = np.clip(cy, ch/2, ih-ch/2)
    M = np.float32([[W/cw, 0, -(cx-cw/2)*W/cw], [0, H/ch, -(cy-ch/2)*H/ch]])
    return cv2.warpAffine(im, M, (W, H), flags=cv2.INTER_LANCZOS4, borderMode=cv2.BORDER_REPLICATE)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("out"); ap.add_argument("--shot", action="append", required=True)
    ap.add_argument("--fade", type=float, default=0.5)
    ap.add_argument("--unmark", default="625,1230,715,1325")
    a = ap.parse_args()
    shots = []
    for s in a.shot:
        p, d, z0, z1, c0, c1 = s.split(":")
        im = cv2.imread(p)
        if a.unmark != "none": im = unmark(im, tuple(map(int, a.unmark.split(","))))
        shots.append(dict(im=im, d=float(d), z0=float(z0), z1=float(z1),
                          c0=tuple(map(float, c0.split(","))), c1=tuple(map(float, c1.split(",")))))
    starts, t = [], 0.0
    for i, s in enumerate(shots):
        starts.append(t); t += s["d"] - (a.fade if i < len(shots)-1 else 0)
    total = t
    ff = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{W}x{H}",
                           "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "16",
                           "-preset", "slow", "-movflags", "+faststart", a.out], stdin=subprocess.PIPE)
    for k in range(int(round(total*FPS))):
        tt = k/FPS; acc = None; wsum = 0.0
        for st, s in zip(starts, shots):
            u = (tt - st)/s["d"]
            if u < 0 or u > 1: continue
            w = 1.0
            if tt - st < a.fade and st > 0: w = ease((tt-st)/a.fade)
            if st + s["d"] - tt < a.fade and s is not shots[-1]: w = ease((st + s["d"] - tt)/a.fade)
            e = ease(u)
            f = frame(s["im"], s["z0"] + (s["z1"]-s["z0"])*e,
                      s["c0"][0] + (s["c1"][0]-s["c0"][0])*e, s["c0"][1] + (s["c1"][1]-s["c0"][1])*e).astype(np.float32)
            acc = f*w if acc is None else acc + f*w; wsum += w
        ff.stdin.write((acc/wsum).clip(0, 255).astype(np.uint8).tobytes())
    ff.stdin.close(); ff.wait()
    print(f"{a.out}: {total:.2f}s, {len(shots)} shots")

if __name__ == "__main__":
    main()
