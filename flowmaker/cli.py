# -*- coding: utf-8 -*-
"""python3 -m flowmaker <명령> [프로젝트] [옵션]

제작 순서 (AGENTS.md 의 절차와 같다)
    setup                       clone 직후 한 번 — 파이썬 패키지 · 크로미엄 · ffmpeg · .env · 폰트를 깐다
    doctor                      환경 점검 (깔지는 않는다 — 부족하면 `setup`)
    login                       Flow 로그인 (한 번) — 같은 창에서 생성 설정(동영상·9:16·출력 1개)을 맞춰 둔다
    new <이름> [--from moai] [--style clay]   프로젝트 폴더 만들기 (예시 복사 가능 · diag 그림 스타일 선택)
    frames <프로젝트> [--only N]  "engine": "frames" 컷을 보드 이미지에서 시작하는 영상으로 제출 (회수는 collect)
    title <프로젝트> [제목]       편 주제 제목 (Flow 프로젝트 이름) 보기/바꾸기
    style <프로젝트> [스타일]     diag 그림 스타일 보기/바꾸기 — clay · archviz · flat (크레딧은 같다)
    check <프로젝트>             cuts.json 형식 + 그림체 정본 검사 (크레딧 0)
    tts <프로젝트>               원샷 더빙
    timing <프로젝트> --target 100   배속 + 자막 타임코드   (또는 --tempo 1.2)
    sync-need <프로젝트>         컷 길이(need)를 나레이션에 맞춤
    board <프로젝트>             스토리보드 — 컷마다 Flow 이미지 모드로 대표 이미지 1장 [--only 3,7] [--max-credit N] [--redo]
    storyboard <프로젝트>        board 이미지를 컷 정보와 묶어 storyboard.html 로 [--redo 5,17 = 다시 뽑는 중 표시]
    submit <프로젝트> <len>      Flow 제출 (len = 4|6|8|10) [--only 3,7]   종료코드 3 = 일부만 전송
    collect <프로젝트> <len>     생성된 클립 회수   종료코드 2 = 아직 생성 중
    review <프로젝트>            프레임 검수 시트
    subs <프로젝트>              자막 PNG
    sfx <프로젝트>               효과음 생성 (sfx.json 있을 때)
    music <프로젝트> "prompt"    배경음악 생성 (선택 · ElevenLabs 유료 플랜)
    assemble <프로젝트>          최종 조립 → final.mp4  (Flow 별 모양 AI 마크는 지운다 · 남기려면 --keep-mark)
    unmark <프로젝트>            AI 마크 지우기 미리보기 [--clip 5] · Flow 가 마크를 바꾸면 --calibrate
    status <프로젝트>            진행 상황

<프로젝트> 는 이름(projects/<이름>) 또는 경로(examples/moai) 다.
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys

from . import style
from .env import REPO_ROOT
from .project import Project, is_name, summary, validate_cuts


def _utf8_stdout() -> None:
    """윈도우 기본 코드페이지(cp949)에는 ✅❌⚠— 가 없다.

    콘솔에 직접 찍을 때는 괜찮지만, 출력을 파일·파이프로 받으면(= 에이전트가 결과를 읽는 방식)
    UnicodeEncodeError 로 죽는다. 그래서 출력 스트림을 utf-8 로 고정한다.
    """
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError, OSError):
            pass            # pytest 캡처 등 reconfigure 가 없는 스트림


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
    if a.style:
        p = Project(a.project)
        if a.from_example and a.style != p.style:
            raise SystemExit(f"예시는 {p.style} 스타일로 쓰여 있다 — 복사한 뒤 `style {a.project} {a.style}` 로 바꿔라")
        p.set_style(a.style)
    if a.title:
        Project(a.project).set_config("title", a.title)
        print(f"제목: {a.title}  (Flow 프로젝트 이름으로 쓴다)")
    print(f"diag 그림 스타일: {Project(a.project).style} — {style.DIAG_STYLES[Project(a.project).style]['label']}"
          f"  (diag 꼬리는 style.diag_tail('{Project(a.project).style}'), 강조는 style.accent(대상, '{Project(a.project).style}'))")


def cmd_style(a):
    """diag 그림 스타일 보기/바꾸기. 바꾸면 diag 컷의 첫머리·강조 문장·꼬리를 새 스타일로 옮긴다."""
    p = Project(a.project).must_exist()
    cur = p.style
    if not a.name:
        for k, v in style.DIAG_STYLES.items():
            print(("▶ " if k == cur else "  ") + f"{k:9s} {v['label']}")
        print("바꾸려면: style <프로젝트> <스타일>  — 크레딧은 스타일과 무관하다(모델·길이·해상도로 정해진다)")
        return
    if a.name not in style.DIAG_STYLES:
        raise SystemExit(f"스타일이 없다: {a.name} (있는 것: {', '.join(style.DIAG_STYLES)})")
    cuts = p.read_cuts_raw()
    if getattr(a, "only", None):
        # 컷만 바꾸기 — 한 편 안에서 그림체를 섞는다(2026-11 사용자 원칙). 편 스타일은 그대로.
        only = {int(x) for x in a.only.split(",")}
        out = []
        for c in cuts:
            if c["n"] in only:
                if c.get("kind") != "diag":
                    raise SystemExit(f"C{c['n']:02d} 는 diag 컷이 아니다 — 스타일은 diag 컷에만 있다")
                src = c.get("style") or cur
                if p.clip(c["n"]).exists() and not a.force:
                    raise SystemExit(f"C{c['n']:02d} 는 클립이 있다 — 다시 만들 생각이면 클립을 build/rejected 로 옮기거나 --force")
                if src != a.name:
                    c = dict(c, prompt=style.restyle_prompt(c["prompt"], src, a.name))
                c = {k: v for k, v in c.items() if k != "style"}
                if a.name != cur:
                    c["style"] = a.name
            out.append(c)
        p.build.mkdir(parents=True, exist_ok=True)
        bak = p.build / f"cuts.before_style_{'_'.join(map(str, sorted(only)))}.json"
        bak.write_text(p.cuts_path.read_text(encoding="utf-8"), encoding="utf-8")
        p.cuts_path.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"{', '.join(f'C{n:02d}' for n in sorted(only))} → {a.name} (편 스타일 {cur} 그대로) · 이전 cuts.json → {bak}")
        for x in style.check(out, diag_style=cur):
            print("★위반:", x)
        return
    if a.name == cur:
        print(f"이미 {cur} 이다"); return
    made = [c["n"] for c in cuts if p.clip(c["n"]).exists()]
    if made and not a.force:
        raise SystemExit(f"이미 클립이 있는 컷이 있다({', '.join(f'C{n:02d}' for n in made)}) — 한 편 안에 스타일이 섞인다. "
                         f"정말 바꾸려면 --force (클립은 그대로, 프롬프트만 바뀐다)")
    out = []
    for c in cuts:
        if c.get("kind") == "diag" and not c.get("style"):   # 컷별 스타일을 정한 컷은 그대로
            try:
                c = dict(c, prompt=style.restyle_prompt(c["prompt"], cur, a.name))
            except ValueError as e:
                raise SystemExit(f"C{c['n']:02d}: {e}")
        out.append(c)
    p.build.mkdir(parents=True, exist_ok=True)
    bak = p.build / f"cuts.before_{a.name}.json"
    bak.write_text(p.cuts_path.read_text(encoding="utf-8"), encoding="utf-8")
    p.cuts_path.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    p.set_style(a.name)
    print(f"{cur} → {a.name} ({style.DIAG_STYLES[a.name]['label']}) · diag {sum(c.get('kind') == 'diag' for c in out)}컷 바꿈 · 이전 cuts.json → {bak}")
    bad = style.check(out, diag_style=a.name)
    for x in bad:
        print("★위반:", x)
    print("남은 위반 없음 — 보드부터 다시 뽑아 확인하라 (board <프로젝트> --redo)" if not bad else
          "위 컷의 본문에서 다른 스타일의 말을 직접 고쳐라")


def cmd_check(a):
    p = Project(a.project)
    cuts = p.read_cuts_raw()
    problems = validate_cuts(cuts, p.n_sentences())
    for x in problems:
        print("★형식:", x)
    st = p.style
    bad = (style.check(cuts) if st == "clay" else style.check(cuts, diag_style=st)) if not problems else []
    for x in bad:
        print("★위반:", x)
    if problems or bad:
        raise SystemExit(f"검사 실패 — 형식 {len(problems)}건 · 정본 {len(bad)}건")
    for c in cuts:
        c["done"] = p.clip(c["n"]).exists()
    mixed = {c["n"]: c["style"] for c in cuts if c.get("kind") == "diag" and c.get("style") and c["style"] != st}
    print("통과 ·", summary(cuts), f"· diag 스타일 {st}({style.DIAG_STYLES[st]['label']})"
          + (" · 컷별 스타일 " + ", ".join(f"C{n:02d}={v}" for n, v in sorted(mixed.items())) if mixed else ""))
    lack = [f"C{c['n']:02d}" for c in cuts if not c.get("must") and not c.get("abstract")]
    n_must = sum(len(c.get("must") or []) for c in cuts)
    print(f"구조·고증 명세(must) {n_must}줄" + (f" · ★명세 없는 컷 {', '.join(lack)} — 사실 컷이면 must, 상징 컷이면 abstract: true"
                                              if lack else " · 모든 컷 분류됨"))


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
    _utf8_stdout()
    ap = argparse.ArgumentParser(prog="python3 -m flowmaker", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("setup")
    s.add_argument("--no-ffmpeg", action="store_true", help="ffmpeg 설치를 건너뛴다")
    s.add_argument("--dry-run", action="store_true", help="무엇을 실행할지 보여주기만 한다")
    sub.add_parser("doctor")
    sub.add_parser("login")
    s = sub.add_parser("new"); s.add_argument("project"); s.add_argument("--from", dest="from_example")
    s.add_argument("--style", choices=tuple(style.DIAG_STYLES), help="diag 그림 스타일 (기본 clay)")
    s.add_argument("--title", help="편 주제 제목 — Flow 프로젝트 이름이 된다")
    s = sub.add_parser("title"); s.add_argument("project"); s.add_argument("text", nargs="?")
    s = sub.add_parser("style"); s.add_argument("project"); s.add_argument("name", nargs="?")
    s.add_argument("--only", help="이 컷들만 바꾼다(쉼표). 컷에 \"style\" 이 붙고 편 스타일은 그대로 — 한 편 안에서 그림체 섞기")
    s.add_argument("--force", action="store_true", help="클립이 이미 있어도 바꾼다")
    for name in ("check", "status", "tts", "sync-need", "review", "subs", "sfx", "assemble"):
        s = sub.add_parser(name); s.add_argument("project")
        if name == "assemble":
            s.add_argument("--keep-mark", action="store_true", help="Flow 의 AI 마크를 지우지 않는다")
    s = sub.add_parser("storyboard"); s.add_argument("project")
    s.add_argument("--redo", help="'다시 뽑는 중'으로 표시할 컷 번호, 쉼표 구분")
    s = sub.add_parser("unmark"); s.add_argument("project")
    s.add_argument("--calibrate", action="store_true", help="이 편 클립에서 마크 모양을 다시 잰다")
    s.add_argument("--clip", type=int, help="미리보기할 컷 번호")
    s = sub.add_parser("timing"); s.add_argument("project")
    g = s.add_mutually_exclusive_group(required=True)
    g.add_argument("--target", type=_positive, help="목표 나레이션 길이(초). 보통 100")
    g.add_argument("--tempo", type=_positive, help="배속 직접 지정 (1.0~1.5)")
    for name in ("submit", "collect"):
        s = sub.add_parser(name); s.add_argument("project"); s.add_argument("len", type=int, choices=(4, 6, 8, 10))
        s.add_argument("--headless", action="store_true")
        if name == "submit":
            s.add_argument("--only", help="컷 번호, 쉼표 구분 (예: 3,7)")
    s = sub.add_parser("frames"); s.add_argument("project"); s.add_argument("--only", help="컷 번호, 쉼표 구분")
    s.add_argument("--headless", action="store_true")
    s = sub.add_parser("board"); s.add_argument("project")
    s.add_argument("--only", help="컷 번호, 쉼표 구분 (예: 3,7)")
    s.add_argument("--max-credit", type=int, default=None, help="이미지 1장당 허용 크레딧 상한 (기본: 0일 때만 진행)")
    s.add_argument("--redo", action="store_true", help="이미 있는 컷도 다시 뽑는다")
    s.add_argument("--headless", action="store_true")
    s = sub.add_parser("music"); s.add_argument("project"); s.add_argument("prompt"); s.add_argument("--seconds", type=int, default=100)

    a = ap.parse_args(argv)
    if a.cmd == "setup":
        from . import setup as setup_mod
        sys.exit(0 if setup_mod.run(no_ffmpeg=a.no_ffmpeg, dry_run=a.dry_run) else 1)
    if a.cmd == "doctor":
        from . import doctor; sys.exit(0 if doctor.run() else 1)
    if a.cmd == "login":
        from . import flow_driver; flow_driver.login(); return
    if a.cmd == "new":
        cmd_new(a); return
    if a.cmd == "title":
        p = Project(a.project).must_exist()
        if a.text:
            p.set_config("title", a.text)
        print(f"제목: {p.title}" + (f"  · Flow 이름 확인됨" if p.config().get("flow_titled") == p.title
                                     else "  · 다음 board/submit 때 Flow 프로젝트 이름을 바꾼다"))
        return
    if a.cmd == "style":
        cmd_style(a); return
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
    elif a.cmd == "frames":
        from . import flow_driver
        only = {int(x) for x in a.only.split(",")} if a.only else None
        flow_driver.frames(p, only, headless=a.headless)
    elif a.cmd == "board":
        from . import flow_driver
        only = {int(x) for x in a.only.split(",")} if a.only else None
        flow_driver.board(p, only, max_credit=a.max_credit, redo=a.redo, headless=a.headless)
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
        from . import assemble; assemble.run(p, keep_mark=a.keep_mark)
    elif a.cmd == "storyboard":
        from . import storyboard
        storyboard.run(p, {int(x) for x in a.redo.split(",")} if a.redo else set())
    elif a.cmd == "unmark":
        from . import unmark
        if a.calibrate:
            unmark.calibrate(p)
        unmark.preview(p, a.clip)
