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

from .project import Project

BGM_VOL = 0.82
MAX_STRETCH = 1.7


def _ff(*args) -> None:
    subprocess.run(["ffmpeg", "-v", "error", *map(str, args)], check=True)


def duration(path) -> float:
    out = subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                                   "-of", "csv=p=0", str(path)])
    return float(out.decode().strip())


def run(project: Project) -> float:
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

    # 1) 클립 트림 → 이어붙이기
    trim = project.build / "trim"; trim.mkdir(parents=True, exist_ok=True)
    parts = []
    for c in cuts:
        src, out = project.clip(c["n"]), trim / f"C{c['n']:02d}.mp4"
        clip_len = duration(src)
        off = float(c.get("offset", 0) or 0)
        if off >= clip_len:
            raise SystemExit(f"C{c['n']:02d}: offset {off}s 가 클립 길이 {clip_len:.2f}s 이상이다")
        if not c["need"] or c["need"] <= 0:
            raise SystemExit(f"C{c['n']:02d}: need 가 {c['need']} 다 — `sync-need` 를 다시 실행하라")
        raw = clip_len - off
        k = 1.0 if c["need"] <= raw else c["need"] / raw
        if k > MAX_STRETCH:
            raise SystemExit(f"C{c['n']:02d}: {k:.2f}배 늘려야 한다 — 너무 느리다. len 을 올려 재생성하라")
        if k > 1.0:
            print(f"  C{c['n']:02d} 늘림 ×{k:.2f} ({raw:.2f}s → {c['need']:.2f}s)")
        vf = (f"setpts=PTS*{k:.5f},fps=30,scale=720:1280:force_original_aspect_ratio=increase,"
              "crop=720:1280,setsar=1")
        args = []
        if c.get("offset"):
            args += ["-ss", c["offset"]]
        _ff(*args, "-i", src, "-vf", vf, "-t", c["need"], "-an",
            "-c:v", "libx264", "-preset", "medium", "-crf", "17", "-pix_fmt", "yuv420p", out, "-y")
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
