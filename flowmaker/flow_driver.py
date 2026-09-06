# -*- coding: utf-8 -*-
"""구글 Flow 브라우저 조작 — 플레이라이트.

흐름
    login    창을 띄워 사용자가 구글에 로그인한다. 쿠키는 ~/.flowmaker/profile 에 남는다(한 번만).
             ★같은 창에서 생성 설정(동영상 · 세로 9:16 · 출력 1개)을 한 번 맞춰 둔다 — Flow 는 계정별로 기억한다.
    submit   길이 그룹(4/6/8/10초) 하나를 새 프로젝트에 제출하고 프로젝트 URL과 **실제로 전송된 컷 순서**를 저장한다.
             ★제출 직전에 style.check() 를 다시 돌린다 — 크레딧을 쓰기 전 마지막 관문.
    collect  저장된 프로젝트를 다시 열어 생성이 끝난 클립을 내려받는다. 기다리지 않는다 —
             덜 됐으면 종료코드 2로 빠지므로 잠시 뒤 다시 부르면 된다.

왜 제출과 회수를 나눴나
    생성에는 몇 분이 걸리고 길이 그룹마다 프로젝트를 따로 두는 편이 매핑이 안전하다.
    한 프로젝트 안에서 화면의 동영상 순서는 "최신이 위"라서, 제출 역순으로 매핑한다.
    화면의 동영상 수가 제출 수와 **정확히 같을 때만** 회수한다 — 많으면 출력 개수 설정이 1이 아닌 것이다.

화면 요소를 찾는 법
    Flow 화면은 자주 바뀐다. 그래서 CSS 선택자 대신 **버튼에 적힌 글자**로 찾는다
    (새 프로젝트 / 동영상 · / 8s / arrow_forward). 글자가 바뀌면 guides/flow-ui.md 를 보고
    아래 TEXT 표만 고치면 된다. 화면이 한국어(/ko/)로 열린다는 전제다.
"""
from __future__ import annotations

import json
import sys
import time
import urllib.request
from pathlib import Path

from . import style
from .env import home
from .project import CREDITS, Project

FLOW_URL = "https://labs.google/fx/ko/tools/flow"

# 화면 글자 (한국어 · 영어 둘 다 받는다). 화면이 바뀌면 여기만 고친다.
TEXT = {
    "dismiss": r"^(시작하기|Get started|닫기|Close|확인|OK)$",
    "new_project": r"새 프로젝트|New project",
    "mode_chip": r"동영상 ·|Video ·",           # 프롬프트 입력창 옆 생성 설정 칩 ("동영상 · 8s · 9:16 · 1")
    "length": "^{len}s$",                        # 길이 버튼 (4s/6s/8s/10s)
    "send": r"arrow_forward",                    # 전송 버튼(머티리얼 아이콘 글자)
}
EXIT_NOT_READY = 2      # collect: 아직 생성 중
EXIT_PARTIAL = 3        # submit: 일부만 전송됨


def profile_dir() -> Path:
    p = home() / "profile"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _context(pw, headless: bool = False):
    """로그인 쿠키가 남는 전용 프로필. 시스템 크롬이 있으면 그걸 쓰고, 없으면 내장 크로미엄."""
    kwargs = dict(headless=headless, viewport={"width": 1440, "height": 960},
                  locale="ko-KR", args=["--disable-blink-features=AutomationControlled"])
    try:
        return pw.chromium.launch_persistent_context(str(profile_dir()), channel="chrome", **kwargs)
    except Exception:
        return pw.chromium.launch_persistent_context(str(profile_dir()), **kwargs)


def _log(msg: str) -> None:
    print(f"[flow] {msg}", flush=True)


# ── 순수 로직 (테스트 대상) ──────────────────────────────────────────────────
def map_clips(order: list[int], urls: list[str]) -> dict[int, str]:
    """화면(최신순) 동영상 주소를 제출 순서의 컷 번호에 매핑한다. 개수가 정확히 같아야 한다."""
    if len(urls) != len(order):
        raise ValueError(f"동영상 {len(urls)}개 / 제출 {len(order)}개 — 개수가 다르면 매핑할 수 없다")
    return dict(zip(order[::-1], urls))


def readiness(n_videos: int, n_expected: int) -> str:
    """'ready' | 'pending' | 'too_many'"""
    if n_videos < n_expected:
        return "pending"
    if n_videos > n_expected:
        return "too_many"
    return "ready"


# ── 화면 조작 헬퍼 ────────────────────────────────────────────────────────────
_JS_FIND = """
(pattern) => {
  const rx = new RegExp(pattern);
  const vis = e => { const r = e.getBoundingClientRect();
    return r.width > 8 && r.height > 8 && r.bottom > 0 && r.top < innerHeight
           && getComputedStyle(e).visibility !== "hidden"; };
  const el = [...document.querySelectorAll("button,[role=button],a")].filter(vis)
    .find(e => rx.test((e.innerText || "").replace(/\\s+/g, " ").trim()));
  if (!el) return null;
  const r = el.getBoundingClientRect();
  return { x: Math.round(r.x + r.width / 2), y: Math.round(r.y + r.height / 2),
           text: (el.innerText || "").replace(/\\s+/g, " ").trim().slice(0, 60) };
}
"""


def click_text(page, pattern: str, label: str, wait_ms: int = 1000) -> bool:
    """버튼 글자를 정규식으로 찾아 가운데를 클릭한다. 못 찾으면 False."""
    hit = page.evaluate(_JS_FIND, pattern)
    if not hit:
        _log(f"  못 찾음: {label} (/{pattern}/)")
        return False
    page.mouse.click(hit["x"], hit["y"])
    page.wait_for_timeout(wait_ms)
    return True


def dismiss_modals(page) -> None:
    for _ in range(3):
        if not click_text(page, TEXT["dismiss"], "공지 닫기", 1500):
            break
    page.keyboard.press("Escape")
    page.wait_for_timeout(600)


def logged_in(page) -> bool:
    if "accounts.google.com" in page.url:
        return False
    return bool(page.evaluate(_JS_FIND, TEXT["new_project"]))


def _editor(page):
    return page.locator('[contenteditable="true"]').first


# ── 명령 ──────────────────────────────────────────────────────────────────────
def login(timeout_min: int = 10) -> None:
    """창을 띄우고 로그인이 확인될 때까지 기다린다. 확인되면 스스로 닫는다."""
    from playwright.sync_api import sync_playwright
    with sync_playwright() as pw:
        ctx = _context(pw, headless=False)
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        page.goto(FLOW_URL, wait_until="domcontentloaded", timeout=90_000)
        _log("브라우저 창에서 구글 계정으로 로그인하세요 (Flow 크레딧이 있는 계정).")
        _log("로그인 뒤 프로젝트 하나를 열어 생성 설정을 '동영상 · 세로 9:16 · 출력 1개'로 맞춰 두세요 — 계정별로 기억됩니다.")
        _log("확인되면 창이 저절로 닫힙니다.")
        deadline = time.time() + timeout_min * 60
        while time.time() < deadline:
            page.wait_for_timeout(4000)
            try:
                dismiss_modals(page)
                if logged_in(page):
                    _log("로그인 확인 — 프로필에 저장했습니다.")
                    ctx.close()
                    return
            except Exception:
                pass
        ctx.close()
        raise SystemExit("시간 안에 로그인이 확인되지 않았습니다 — 다시 `login` 을 실행하세요")


def submit(project: Project, length: int, only: set[int] | None = None, headless: bool = False) -> Path:
    cuts = project.load_cuts()
    targets = [c for c in cuts if not c["done"] and c["len"] == length
               and (only is None or c["n"] in only)]
    if not targets:
        _log(f"[{length}s] 제출할 컷 없음")
        sys.exit(0)

    # ★마지막 관문 — 이번에 크레딧을 쓸 컷만 검사하고, 구성 규칙은 전체로 한 번 더 본다
    bad = style.check(targets) + style.composition_only(style.check(cuts))
    if bad:
        for b in bad:
            print("★위반:", b)
        raise SystemExit("정본 검증 실패 — 제출하지 않았다 (크레딧 소모 0)")
    _log(f"[{length}s] {len(targets)}컷 제출 (크레딧 약 {CREDITS[length]*len(targets)}): "
         + ", ".join(f"C{c['n']:02d}" for c in targets))

    project.build.mkdir(parents=True, exist_ok=True)
    meta = project.build / f"submit_{length}s.json"
    sent: list[int] = []
    url = ""

    def save():
        meta.write_text(json.dumps({"url": url, "order": sent}, ensure_ascii=False))

    from playwright.sync_api import sync_playwright
    with sync_playwright() as pw:
        ctx = _context(pw, headless=headless)
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        try:
            page.goto(FLOW_URL, wait_until="domcontentloaded", timeout=90_000)
            page.wait_for_timeout(7000)
            dismiss_modals(page)
            if not logged_in(page):
                raise SystemExit("로그인이 안 돼 있다 — 먼저 `login` 을 실행하라")

            if not click_text(page, TEXT["new_project"], "새 프로젝트", 9000):
                raise SystemExit("'새 프로젝트' 버튼을 못 찾았다 — guides/flow-ui.md 를 보고 TEXT 를 고쳐라")
            url = page.url
            save()
            _log(f"프로젝트: {url}")

            page.keyboard.press("Escape"); page.wait_for_timeout(500)
            click_text(page, TEXT["mode_chip"], "설정 칩", 1200)
            click_text(page, TEXT["length"].format(len=length), f"{length}s 버튼", 1000)
            page.keyboard.press("Escape"); page.wait_for_timeout(600)
            now = page.evaluate(_JS_FIND, TEXT["mode_chip"])
            chip = now["text"] if now else "?"
            _log(f"설정 칩 → {chip}")
            if f"{length}s" not in chip:
                raise SystemExit(f"길이 {length}s 가 적용되지 않았다 (칩: {chip}) — 제출하지 않았다")
            if "9:16" not in chip:
                _log("  ⚠ 칩에 '9:16' 이 안 보인다 — 세로 설정을 login 창에서 맞췄는지 확인하라 (가로로 나올 수 있다)")

            for c in targets:
                ed = _editor(page)
                ed.click(timeout=15_000)
                page.keyboard.press("Meta+A" if sys.platform == "darwin" else "Control+A")
                page.keyboard.press("Delete")
                page.wait_for_timeout(300)
                page.keyboard.type(c["prompt"], delay=0)
                page.wait_for_timeout(900)
                typed = ed.inner_text()
                if len("".join(typed.split())) < len("".join(c["prompt"].split())) * 0.95:
                    _log(f"  C{c['n']:02d} 입력이 잘렸다 ({len(typed)}자) — 이 컷은 건너뜀")
                    continue
                if not click_text(page, TEXT["send"], "전송 버튼", 3500):
                    _log(f"  C{c['n']:02d} 전송 버튼 못 찾음 — 건너뜀")
                    continue
                sent.append(c["n"])
                save()                                   # 성공한 것만 즉시 기록
                _log(f"  C{c['n']:02d} 제출")
        finally:
            ctx.close()

    _log(f"제출 {len(sent)}/{len(targets)} → {meta.relative_to(project.dir)}")
    if not sent:
        raise SystemExit("하나도 제출되지 않았다")
    if len(sent) < len(targets):
        missed = [c["n"] for c in targets if c["n"] not in sent]
        _log(f"★일부만 전송됨. 빠진 컷 {missed} 은 나중에 `submit {project.name} {length} --only "
             f"{','.join(map(str, missed))}` 로 다시. 지금 것은 `collect` 로 회수할 수 있다")
        sys.exit(EXIT_PARTIAL)
    return meta


def collect(project: Project, length: int, headless: bool = False) -> int:
    meta_path = project.build / f"submit_{length}s.json"
    if not meta_path.exists():
        raise SystemExit(f"{meta_path.name} 이 없다 — 먼저 `submit {length}` 를 실행하라")
    meta = json.loads(meta_path.read_text())
    url, order = meta["url"], meta["order"]
    if not order:
        raise SystemExit("제출된 컷이 없다 (order 비어 있음)")

    from playwright.sync_api import sync_playwright
    with sync_playwright() as pw:
        ctx = _context(pw, headless=headless)
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=90_000)
            page.wait_for_timeout(11_000)
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            page.wait_for_timeout(2500)
            n = page.evaluate("document.querySelectorAll('video').length")
            state = readiness(n, len(order))
            _log(f"[{length}s] 화면의 동영상 {n}개 / 제출 {len(order)}개 → {state}")
            if state == "pending":
                _log("아직 생성 중 — 잠시 뒤 다시 실행하라")
                sys.exit(EXIT_NOT_READY)
            if state == "too_many":
                raise SystemExit("동영상이 제출 수보다 많다 — 출력 개수 설정이 1이 아니거나 다른 생성물이 섞였다. "
                                 "프로젝트를 브라우저에서 열어 확인하고, 설정을 '출력 1개'로 맞춘 뒤 새로 제출하라")
            urls = page.evaluate("""async () => {
                const out = [];
                for (const v of [...document.querySelectorAll('video')]) {
                  const src = v.currentSrc || v.src;
                  try { const r = await fetch(src, {redirect: 'follow'}); out.push(r.url); }
                  catch (e) { out.push('ERR'); }
                }
                return out; }""")
        finally:
            ctx.close()

    urls = [u for u in urls if isinstance(u, str) and u.startswith("http")]
    try:
        mapping = map_clips(order, urls)
    except ValueError as e:
        raise SystemExit(f"{e} — 다시 시도하라")

    project.clips.mkdir(parents=True, exist_ok=True)
    got: dict[int, float] = {}
    for n, u in mapping.items():
        dst = project.clip(n)
        urllib.request.urlretrieve(u, dst)
        got[n] = _duration(dst)
        _log(f"  C{n:02d} ← {got[n]:.2f}s")
    (project.build / f"collected_{length}s.json").write_text(json.dumps(got))
    _log(f"[{length}s] 회수 {len(got)}/{len(order)}")
    return len(got)


def _duration(path: Path) -> float:
    import subprocess
    out = subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                                   "-of", "csv=p=0", str(path)])
    return float(out.decode().strip())
