#!/usr/bin/env python3
# 필요: numpy · opencv-python · scipy · scikit-image · ffmpeg  (Claude 의 클라우드 작업 공간에서 돌린다 — 맥 VM 에는 이 라이브러리가 없다)
"""보드 이미지의 관을 따라 물이 차오르는 영상 (크레딧 0).
1) 관 찾기: 밝기 top-hat + 영역 다각형 → 가장 큰 덩어리 → 뼈대(skeleton)
2) 출수 쪽 끝점(--start 근처)에서 뼈대를 따라간 거리 = 관 위 위치 s (0 출수 → 1 환수)
3) 회색 관이 s 순서로 빨강 → 파랑으로 차오르고, period 초마다 반복 (흰 하이라이트 없음)
"""
import argparse, json, subprocess
from collections import deque
import numpy as np, cv2
from scipy import ndimage
from skimage.morphology import skeletonize, white_tophat, disk, remove_small_objects
from skimage.measure import label
ap = argparse.ArgumentParser()
ap.add_argument("src"); ap.add_argument("out")
ap.add_argument("--poly", required=True, help="관이 있는 영역 다각형 (보드 좌표) JSON")
ap.add_argument("--start", required=True, help="출수 쪽 끝점 근처 x,y (보드 좌표)")
ap.add_argument("--dur", type=float, default=6.4); ap.add_argument("--period", type=float, default=1.6)
ap.add_argument("--zoom", type=float, default=1.04); ap.add_argument("--th", type=float, default=20)
ap.add_argument("--red", default="225,55,35"); ap.add_argument("--blue", default="60,120,235")
ap.add_argument("--blend", default="0.10,0.85", help="빨강→파랑이 바뀌는 s 구간")
ap.add_argument("--mark", default="640,1250,60,60", help="보드 좌표의 별 마크 x,y,w,h")
ap.add_argument("--debug"); ap.add_argument("--empty", type=float, default=0.68, help="빈 관의 밝기 비율(회색)")
ap.add_argument("--once", action="store_true", help="한 번만 차오르고 그대로 둔다")
ap.add_argument("--cut", action="append", default=[], help="관 마스크에서 지울 x,y,w,h (붙어 있는 두 끝을 떼어 놓을 때)")
a = ap.parse_args()
im = cv2.imread(a.src)[:, :, ::-1].astype(np.float32)
mx, my, mw, mh = map(int, a.mark.split(","))
im[my:my + mh, mx:mx + mw] = im[my:my + mh, mx - mw - 10:mx - 10]
lum = 0.3 * im[..., 0] + 0.59 * im[..., 1] + 0.11 * im[..., 2]
th = white_tophat(np.clip(lum, 0, 255).astype(np.uint8), disk(12))
reg = np.zeros(lum.shape, np.uint8); cv2.fillPoly(reg, [np.array(json.loads(a.poly), np.int32)], 1)
m = (th > a.th) & (reg > 0)
for c in a.cut:
    cx, cy, cw, ch = map(int, c.split(",")); m[cy:cy + ch, cx:cx + cw] = False
m = remove_small_objects(m, max_size=150)
m = cv2.morphologyEx(m.astype(np.uint8), cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8)) > 0
lab = label(m); m = lab == (np.argmax(np.bincount(lab.ravel())[1:]) + 1)
sk = skeletonize(m)
ys, xs = np.nonzero(sk)
sx, sy = map(float, a.start.split(","))
i0 = np.argmin((xs - sx) ** 2 + (ys - sy) ** 2)
dist = np.full(sk.shape, -1.0); dist[ys[i0], xs[i0]] = 0
q = deque([(ys[i0], xs[i0])])
while q:
    y, x = q.popleft()
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            yy, xx = y + dy, x + dx
            if (dy or dx) and 0 <= yy < sk.shape[0] and 0 <= xx < sk.shape[1] and sk[yy, xx] and dist[yy, xx] < 0:
                dist[yy, xx] = dist[y, x] + (1.414 if dy and dx else 1.0); q.append((yy, xx))
L = dist.max()
print(f"관 픽셀 {m.sum()} · 뼈대 {sk.sum()} (닿음 {(dist >= 0).sum()}) · 관 길이 {L:.0f}px")
# 관 픽셀마다 가장 가까운 뼈대의 s
_, (iy, ix) = ndimage.distance_transform_edt(~(dist >= 0), return_indices=True)
s = np.where(m, dist[iy, ix] / L, -1.0)
# 720x1280 으로 (보드 768x1376 → 0.9375 배, 위아래 5px 자름)
W, H, FPS = 720, 1280, 30
def fit(arr, interp):
    h, w = arr.shape[:2]; k = max(W / w, H / h)
    r = cv2.resize(arr, (round(w * k), round(h * k)), interpolation=interp)
    t0, l0 = (r.shape[0] - H) // 2, (r.shape[1] - W) // 2
    return r[t0:t0 + H, l0:l0 + W]
im_o = fit(im, cv2.INTER_AREA); s_o = fit(s.astype(np.float32), cv2.INTER_NEAREST)
pipe = s_o >= 0
lum_o = 0.3 * im_o[..., 0] + 0.59 * im_o[..., 1] + 0.11 * im_o[..., 2]
grey_scene = np.repeat(lum_o[..., None], 3, -1)                 # 바닥의 색 번짐(헤일로)도 없앤다 — 전부 회색
near = cv2.dilate(pipe.astype(np.uint8), np.ones((15, 15), np.uint8)) > 0
smooth = cv2.medianBlur(np.clip(lum_o, 0, 255).astype(np.uint8), 21).astype(np.float32)
grey_scene[near & ~pipe] = np.repeat(smooth[..., None], 3, -1)[near & ~pipe]   # 관 옆 흰 반짝임 제거
empty = grey_scene * a.empty                                      # 물이 없을 때의 관: 어두운 회색
shade = np.clip(lum_o / np.percentile(lum_o[pipe], 85), 0.35, 1.1)[..., None]
RED, BLUE = np.array(list(map(float, a.red.split(",")))), np.array(list(map(float, a.blue.split(","))))
b0, b1 = map(float, a.blend.split(","))
k = np.clip((np.clip(s_o, 0, 1) - b0) / (b1 - b0), 0, 1)[..., None]
k = k * k * (3 - 2 * k)                                           # 부드럽게
hot = ((1 - k) * RED + k * BLUE) * shade
if a.debug:
    dbg = grey_scene.copy(); dbg[pipe] = hot[pipe]
    cv2.imwrite(a.debug.replace(".png", "_empty.png"), np.clip(np.where(pipe[..., None], empty, grey_scene), 0, 255).astype(np.uint8)[:, :, ::-1]); cv2.imwrite(a.debug, np.clip(dbg, 0, 255).astype(np.uint8)[:, :, ::-1])
n = int(round(a.dur * FPS))
ff = subprocess.Popen(["ffmpeg", "-loglevel", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
                       "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-preset", "medium", "-crf", "16",
                       "-pix_fmt", "yuv420p", a.out], stdin=subprocess.PIPE)
pm = pipe[..., None]
for i in range(n):
    tt = i / FPS
    ph = min(tt / a.period, 1.0) if a.once else (tt % a.period) / a.period
    front = ph / 0.82                                              # 82% 동안 출수→환수로 차오름
    fade = 1.0 if (a.once or ph < 0.86) else max(0.0, 1 - (ph - 0.86) / 0.14)  # 마지막에 빠지고 다시 처음부터
    fill = np.clip((front - s_o) / 0.025, 0, 1)[..., None] * fade
    fr = np.where(pm, empty * (1 - fill) + hot * fill, grey_scene)
    glow = cv2.GaussianBlur((np.where(pm, hot * fill, 0)).astype(np.float32), (0, 0), 6)
    fr = fr + 0.35 * glow * (~pm)
    z = 1 + (a.zoom - 1) * (tt / a.dur)
    M = np.float32([[z, 0, W / 2 * (1 - z)], [0, z, H / 2 * (1 - z)]])
    fr = cv2.warpAffine(np.clip(fr, 0, 255).astype(np.uint8), M, (W, H), flags=cv2.INTER_CUBIC)
    ff.stdin.write(fr.tobytes())
ff.stdin.close(); ff.wait(); print("ok", a.out, n, "frames")
