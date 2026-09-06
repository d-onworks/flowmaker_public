# -*- coding: utf-8 -*-
"""python3 -m flowmaker <명령> [프로젝트] [옵션]

제작 순서 (AGENTS.md 의 절차와 같다)
    doctor                      환경 점검 · 폰트 설치
    login                       Flow 로그인 (한 번) — 같은 창에서 생성 설정(동영상·9:16·출력 1개)을 맞춰 둔다
    new <이름> [--from moai]     프로젝트 폴더 만들기 (예시 복사 가능)
    check <프로젝트>             cuts.json 형식 + 그림체 정본 검사 (크레딧 0)
    tts <프로젝트>               원샷 더빙
    timing <프로젝트> --target 100   배속 + 자막 타임코드   (또는 --tempo 1.2)
    sync-need <프로젝트>         컷 길이(need)를 나레이션에 맞춤
    submit <프로젝트> <len>      Flow 제출 (len = 4|6|8|10) [--only 3,7]   종료코드 3 = 일부만 전송
    collect <프로젝트> <len>     생성된 클립 회수   종료코드 2 = 아직 생성 중
    review <프로젝트>            프레임 검수 시트
    subs <프로젝트>              자막 PNG
    sfx <프로젝트>               효과음 생성 (sfx.json 있을 때)
    music <프로젝트> "prompt"    배경음악 생성 (선택 · ElevenLabs 유료 플랜)
    assemble <프로젝트>          최종 조립 → final.mp4
    status <프로젝트>            진행 상황

<프로젝트> 는 이름(projects/<이름>) 또는 경로(examples/moai) 다.
"""
from __future__ import annotations

import argparse
import shutil
import sys

from . import style
from .env import REPO_ROOT
from .project import Project, is_name, summary, validate_cuts


def cmd_new(a):
    if not is_name(a.project):
        raise SystemExit("프로젝트 이름에는 경로 구분자를 쓸 수 없다 (예: bridge)")
    dst = REPO_ROOT / "projects" / a.project
    if dst.exists():
        raise SystemExit(f"이미 있다: {dst}")
    if a.from_example:
        src = REPO_ROOT / "examples" / a.from_example
        if not src.is_dir():
            have = sorted(p.name for p in (REPO_ROOT / "examples").iterdir() if p.is_dir())
            raise SystemExit(f"예시가 없다: {a.from_example} (있는 것: {', '.join(have)})")
        shutil.copytree(src, dst)
        print(f"예시 {a.from_example} 를 복사 → {dst}")
    else:
        dst.mkdir(parents=True)
        (dst / "script.txt").write_text("", encoding="utf-8")
        (dst / "subtitles.txt").write_text("", encoding="utf-8")
        (dst / "cuts.json").write_text("[]", encoding="utf-8")
        (dst / "facts.md").write_text("# 사실 검증\n\n", encoding="utf-8")
        print(f"빈 프로젝트 → {dst}\n  script.txt · subtitles.txt · cuts.json · facts.md 를 채워라 (guides/ 참고)")


def cmd_check(a):
    p = Project(a.project)
    cuts = p.read_cuts_raw()
    problems = validate_cuts(cuts, p.n_sentences())
    for x in problems:
        print("★형식:", x)
    bad = style.check(cuts) if not problems else []
    for x in bad:
        print("★위반:", x)
    if problems or bad:
        raise SystemExit(f"검사 실패 — 형식 {len(problems)}건 · 정본 {len(bad)}건")
    for c in cuts:
        c["done"] = p.clip(c["n"]).exists()
    print("통과 ·", summary(cuts))


def cmd_status(a):
    p = Project(a.project)
    cuts = p.load_cuts()
    steps = [
        ("대본 script.txt", p.n_sentences() is not None),
        ("자막 subtitles.txt", p.subtitles.exists() and bool(p.subtitles.read_text(encoding="utf-8").strip())),
        ("컷 계획 cuts.json", bool(cuts)),
        ("더빙 narration_raw.mp3", p.narration_raw.exists()),
        ("타이밍 subtitle_timing.json", p.timing.exists()),
        ("need 계산", all(c.get("need") for c in cuts)),
        (f"클립 {sum(c['done'] for c in cuts)}/{len(cuts)}", all(c["done"] for c in cuts)),
        ("자막 PNG", p.subs.exists() and any(p.subs.glob("*.png"))),
        ("효과음", (p.build / "sfx").exists() or not p.sfx_path.exists()),
        ("배경음악 bgm.mp3 (선택)", p.bgm.exists()),
        ("완성 final.mp4", p.final.exists()),
    ]
    print(f"프로젝트 {p.name} — {summary(cuts)}")
    for name, done in steps:
        print(f"  {'✅' if done else '· '} {name}")
    pending = [c for c in cuts if not c["done"]]
    if pending:
        by_len = {}
        for c in pending:
            by_len.setdefault(c["len"], []).append(c["n"])
        for ln, ns in sorted(by_len.items()):
            print(f"  다음: submit {p.ref} {ln}   (C{', C'.join(f'{n:02d}' for n in ns)})")


def _positive(v: str) -> float:
    x = float(v)
    if x <= 0:
        raise argparse.ArgumentTypeError("양수여야 한다")
    return x


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(prog="python3 -m flowmaker", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("doctor")
    sub.add_parser("login")
    s = sub.add_parser("new"); s.add_argument("project"); s.add_argument("--from", dest="from_example")
    for name in ("check", "status", "tts", "sync-need", "review", "subs", "sfx", "assemble"):
        s = sub.add_parser(name); s.add_argument("project")
    s = sub.add_parser("timing"); s.add_argument("project")
    g = s.add_mutually_exclusive_group(required=True)
    g.add_argument("--target", type=_positive, help="목표 나레이션 길이(초). 보통 100")
    g.add_argument("--tempo", type=_positive, help="배속 직접 지정 (1.0~1.5)")
    for name in ("submit", "collect"):
        s = sub.add_parser(name); s.add_argument("project"); s.add_argument("len", type=int, choices=(4, 6, 8, 10))
        s.add_argument("--headless", action="store_true")
        if name == "submit":
            s.add_argument("--only", help="컷 번호, 쉼표 구분 (예: 3,7)")
    s = sub.add_parser("music"); s.add_argument("project"); s.add_argument("prompt"); s.add_argument("--seconds", type=int, default=100)

    a = ap.parse_args(argv)
    if a.cmd == "doctor":
        from . import doctor; sys.exit(0 if doctor.run() else 1)
    if a.cmd == "login":
        from . import flow_driver; flow_driver.login(); return
    if a.cmd == "new":
        cmd_new(a); return
    if a.cmd == "check":
        cmd_check(a); return
    if a.cmd == "status":
        cmd_status(a); return

    p = Project(a.project).must_exist()
    if a.cmd == "tts":
        from . import tts; tts.synthesize(p)
    elif a.cmd == "timing":
        from . import timing; timing.build(p, target=a.target, tempo=a.tempo)
    elif a.cmd == "sync-need":
        from . import timing; timing.sync_need(p)
    elif a.cmd == "submit":
        from . import flow_driver
        only = {int(x) for x in a.only.split(",")} if a.only else None
        flow_driver.submit(p, a.len, only, headless=a.headless)
    elif a.cmd == "collect":
        from . import flow_driver
        flow_driver.collect(p, a.len, headless=a.headless)
    elif a.cmd == "review":
        from . import review; review.run(p)
    elif a.cmd == "subs":
        from . import subtitles; subtitles.render_all(p)
    elif a.cmd == "sfx":
        from . import sfx
        if not sfx.generate(p):
            sys.exit(1)
    elif a.cmd == "music":
        from . import sfx; sfx.music(p, a.prompt, a.seconds)
    elif a.cmd == "assemble":
        from . import assemble; assemble.run(p)
