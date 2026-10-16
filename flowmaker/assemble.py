# -*- coding: utf-8 -*-
"""조립 — 클립 트림·이어붙이기 → 자막 얹기 → 나레이션 + BGM(덕킹) + 효과음 → -14 LUFS.

오디오 수치 (완성 편 실측 확정값 — 매번 귀로 맞추지 않는다)
    BGM 0.82 · 사이드체인 덕킹 threshold 0.10 / ratio 4 · loudnorm I=-14 TP=-1.5 · 리미터 0.87
클립 길이 맞추기
    클립이 need 보다 길면 앞에서 need 만큼 쓰고, 짧으면 느리게 재생해 채운다(1.7배까지).
    Flow 에는 배속 생성 옵션이 없어서 후처리가 유일한 방법이다.
"""
from __future__ import annotations

import json
import subprocess

from . import unmark
from .project import Project

BGM_VOL = 0.82
MAX_STRETCH = 1.7


def usable(c: dict, clip_len: float) -> tuple[float, float]:
    """클립에서 쓸 수 있는 구간 → (시작 초, 길이). offset 은 앞을, until 은 뒤를 자른다(클립 안 시각).
    until 은 클립 끝에만 오류가 있을 때 재생성 대신 쓴다 — 남은 길이를 need 까지 늘린다(MAX_STRETCH 까지)."""
    off = float(c.get("offset", 0) or 0)
    if off >= clip_len:
        raise SystemExit(f"C{c['n']:02d}: offset {off}s 가 클립 길이 {clip_len:.2f}s 이상이다")
    until = float(c.get("until", 0) or 0)
    if until and until <= off:
        raise SystemExit(f"C{c['n']:02d}: until {until}s 가 offset {off}s 보다 앞이다")
    return off, (min(until, clip_len) if until else clip_len) - off


def lead_of(c: dict):
    """이 컷 앞에 붙일 다른 컷의 한 토막 → (컷 번호, 시작 초, 길이) 또는 None.
    훅에서 영상의 가장 센 그림을 먼저 보여줄 때 쓴다(이미 만든 클립을 다시 쓰므로 크레딧 0)."""
    ld = c.get("lead")
    return (int(ld["cut"]), float(ld.get("from", 0) or 0), float(ld["dur"])) if ld else None


def own_need(c: dict) -> float:
    """이 컷 자기 클립이 채워야 하는 길이 — need 에서 lead 토막을 뺀 것."""
    ld = lead_of(c)
    return float(c["need"]) - (ld[2] if ld else 0.0)


def used_span(c: dict, clip_len: float) -> tuple[float, float]:
    """완성본에 실제로 들어가는 (이 컷 자기) 클립 구간 (시작, 끝) — 늘리지 않으면 own_need 만큼, 늘리면 쓸 수 있는 구간 전부."""
    off, raw = usable(c, clip_len)
    need = own_need(c) if c.get("need") else raw
    return off, off + min(raw, need)


def _segment(src, args: list, k: float, dur: float, out, mask, n: int) -> None:
    """클립 한 토막을 k 배로 늘려 dur 초만큼 720x1280·30fps 로 인코딩한다. 마스크가 있으면 AI 마크를 지운다."""
    vf = (f"setpts=PTS*{k:.5f},fps=30,scale=720:1280:force_original_aspect_ratio=increase,"
          "crop=720:1280,setsar=1")
    enc = ["-t", f"{dur:.3f}", "-an", "-c:v", "libx264", "-preset", "medium", "-crf", "17",
           "-pix_fmt", "yuv420p", out, "-y"]
    if mask and unmark.clip_size(src) == unmark.FRAME:
        _ff(*args, "-i", src, "-loop", "1", "-i", mask,
            "-filter_complex", unmark.blend_chain() + f";[um]{vf}[v]", "-map", "[v]", *enc)
    else:
        if mask:
            print(f"  C{n:02d} 크기가 {unmark.FRAME} 가 아니라 마크를 못 지웠다 — 검수 때 확인")
        _ff(*args, "-i", src, "-vf", vf, *enc)


def _ff(*args) -> None:
    subprocess.run(["ffmpeg", "-v", "error", *map(str, args)], check=True)


def duration(path) -> float:
    out = subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                                   "-of", "csv=p=0", str(path)])
    return float(out.decode().strip())


def run(project: Project, keep_mark: bool = False) -> float:
    cuts = project.load_cuts()
    cards = project.load_timing()
    if any("need" not in c for c in cuts):
        raise SystemExit("need 가 없는 컷이 있다 — 먼저 `sync-need` 를 실행하라")
    total = round(sum(c["need"] for c in cuts), 2)
    missing = [c["n"] for c in cuts if not c["done"]]
    if missing:
        raise SystemExit(f"클립 없음: {['C%02d' % n for n in missing]} — submit/collect 를 마쳐라")
    if not project.narration.exists():
        raise SystemExit("narration.wav 가 없다 — `timing` 을 먼저")
    subs_missing = [c["i"] for c in cards if not (project.subs / f"{c['i']:02d}.png").exists()]
    if subs_missing:
        raise SystemExit(f"자막 PNG 없음: {subs_missing} — `subs` 를 먼저")
    print(f"목표 {total}초 · {len(cuts)}컷 · 자막 {len(cards)}장")

    # 1) 클립 트림 → 이어붙이기  (Flow 의 별 모양 AI 마크는 여기서 지운다 — unmark.py 머리말 참고)
    trim = project.build / "trim"; trim.mkdir(parents=True, exist_ok=True)
    mask = None if keep_mark else unmark.mask_for(project)
    print("AI 마크: " + ("남김 (--keep-mark)" if keep_mark else f"지움 · 마스크 {mask.name}" if mask
                       else "마스크 없음 — 남김"))
    parts = []
    for c in cuts:
        src, out = project.clip(c["n"]), trim / f"C{c['n']:02d}.mp4"
        clip_len = duration(src)
        if not c["need"] or c["need"] <= 0:
            raise SystemExit(f"C{c['n']:02d}: need 가 {c['need']} 다 — `sync-need` 를 다시 실행하라")
        off, raw = usable(c, clip_len)
        need = own_need(c)
        k = 1.0 if need <= raw else need / raw
        if k > MAX_STRETCH:
            raise SystemExit(f"C{c['n']:02d}: {k:.2f}배 늘려야 한다 — 너무 느리다. len 을 올려 재생성하라")
        if k > 1.0:
            print(f"  C{c['n']:02d} 늘림 ×{k:.2f} ({raw:.2f}s → {need:.2f}s)")
        ld = lead_of(c)
        if ld:                                       # 훅 미리보기: 다른 컷의 한 토막을 앞에 붙인다
            lsrc = project.clip(ld[0])
            if ld[1] + ld[2] > duration(lsrc) + 0.05:
                raise SystemExit(f"C{c['n']:02d}: lead 가 C{ld[0]:02d} 클립 길이를 넘는다")
            lout = trim / f"C{c['n']:02d}_lead.mp4"
            _segment(lsrc, ["-ss", ld[1]], 1.0, ld[2], lout, mask, c["n"])
            parts.append(lout)
            print(f"  C{c['n']:02d} 앞에 C{ld[0]:02d} {ld[1]:.2f}~{ld[1] + ld[2]:.2f}s 를 붙임 (훅 미리보기)")
        _segment(src, ["-ss", c["offset"]] if c.get("offset") else [], k, need, out,
                 mask if c.get("unmark", True) else None, c["n"])     # unmark:false — 보드로 만든 클립(마크 없음)
        parts.append(out)
    lst = project.build / "list.txt"
    lst.write_text("".join("file '" + str(p).replace("'", "'\\''") + "'\n" for p in parts),
                   encoding="utf-8")
    silent = project.build / "video_silent.mp4"
    _ff("-f", "concat", "-safe", "0", "-i", lst, "-c", "copy", silent, "-y")

    # 2) 자막 얹기
    ins, filt, cur = ["-i", str(silent)], [], "[0:v]"
    for k, c in enumerate(cards):
        ins += ["-i", str(project.subs / f"{c['i']:02d}.png")]
        nxt = f"[v{k}]"
        filt.append(f"{cur}[{k+1}:v]overlay=0:0:enable='between(t,{c['start']:.3f},{c['end']:.3f})'{nxt}")
        cur = nxt
    with_subs = project.build / "video_subs.mp4"
    _ff(*ins, "-filter_complex", ";".join(filt), "-map", cur,
        "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p", with_subs, "-y")

    # 3) 오디오 — 나레이션 + (BGM) + (효과음)
    first: dict[int, float] = {}
    for c in cards:
        first.setdefault(c["sentence"], c["start"])
    ins, f = ["-i", str(project.narration)], []
    idx = 1
    beds = []
    if project.bgm.exists():
        ins += ["-i", str(project.bgm)]
        f.append(f"[{idx}:a]aformat=channel_layouts=mono,volume={BGM_VOL},afade=t=in:st=0:d=2,"
                 f"afade=t=out:st={max(total-3.5, 0):.2f}:d=3.2[bgm]")
        beds.append("[bgm]"); idx += 1
    sfx_plan = json.loads(project.sfx_path.read_text(encoding="utf-8")) if project.sfx_path.exists() else []
    mixes = []
    for s in sfx_plan:
        src = project.build / "sfx" / f"{s['name']}.mp3"
        if not src.exists():
            print(f"  효과음 파일 없음, 건너뜀: {s['name']} (`sfx` 를 먼저)")
            continue
        at = max(first.get(int(s["sentence"]), 0.0) + float(s.get("offset", 0)), 0.0)
        ins += ["-i", str(src)]
        f.append(f"[{idx}:a]aformat=channel_layouts=mono,volume={float(s.get('volume', 0.5))},"
                 f"adelay={int(at*1000)}|{int(at*1000)}[s{idx}]")
        mixes.append(f"[s{idx}]"); idx += 1
        print(f"  효과음 {s['name']} @ {at:.2f}s")
    if mixes:
        f.append("".join(mixes) + f"amix=inputs={len(mixes)}:normalize=0:dropout_transition=0[sfx]")
        beds.append("[sfx]")
    master = f"apad,atrim=0:{total},loudnorm=I=-14:TP=-1.5:LRA=11,alimiter=limit=0.87[out]"
    if beds:
        f.append("[0:a]aformat=channel_layouts=mono,asplit=2[nar1][narsc]")
        if len(beds) > 1:
            f.append("".join(beds) + f"amix=inputs={len(beds)}:normalize=0:dropout_transition=0[bed]")
        else:
            f.append(f"{beds[0]}anull[bed]")
        f.append("[bed][narsc]sidechaincompress=threshold=0.10:ratio=4:attack=8:release=280[bedduck]")
        f.append(f"[nar1][bedduck]amix=inputs=2:normalize=0:dropout_transition=0," + master)
    else:                                          # 나레이션만 — BGM·효과음 없음
        f.append("[0:a]aformat=channel_layouts=mono," + master)
    audio = project.build / "audio.wav"
    _ff(*ins, "-filter_complex", ";".join(f), "-map", "[out]", "-ar", "48000", "-ac", "2", audio, "-y")

    # 4) 합치기
    _ff("-i", with_subs, "-i", audio, "-map", "0:v", "-map", "1:a", "-c:v", "copy",
        "-c:a", "aac", "-b:a", "192k", "-shortest", project.final, "-y")
    d = duration(project.final)
    print(f"\n완성 {d:.2f}초 → {project.final}")
    return d
