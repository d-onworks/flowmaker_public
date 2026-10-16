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
import re
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
    "mode_chip": r"^(동영상|Video) ·|crop_\d+_\d+ x[1-4]$",   # 설정 칩 글자 — 모드마다 다르다 ("동영상 · 720p · 8초 crop_9_16 x1" / "🍌 Nano Banana 2.1 crop_16_9 x2")
    "settings_aria": r"^(설정 트리거|Settings trigger)$",       # 설정 칩의 aria-label (글자보다 안정적. 에이전트 모드의 '설정(tune)'은 aria 가 '설정'이라 안 걸린다)
    "portrait": r"^(crop_9_16 )?9:16$",          # 세로 비율
    "res": r"^720p$",                             # 해상도
    "model": r"Omni 1\.1 Flash",                 # 동영상 모델 (크레딧 4초 7 · 6초 10 · 8초 12 · 10초 15 가 이 모델 720p 기준)
    "model_aria": r"^(모델 제품군 선택|Select model family)$",
    "model_item": r"^(volume_up )?Omni 1\.1 Flash$",
    "credit": r"(?:생성 시|Generating will use)\s*(\d+)\s*(?:크레딧|credits?)",   # 설정 패널 아래 '생성 시 12 크레딧이 사용됩니다'
    "length": "^{len}(s|초)$",                   # 길이 버튼 (영어 4s/6s… · 한국어 4초/6초…)
    "video_mode": r"^(videocam )?(동영상|Video)$",  # 설정 메뉴의 이미지/동영상 중 동영상
    "image_mode": r"^(image )?(이미지|Image)$",      # 설정 메뉴의 이미지 (board — 스토리보드 대표 이미지)
    "count1": r"^x1$",                           # 출력 개수 1
    "agent_toggle": r"^(에이전트|Agent)$",        # 프롬프트 상자의 에이전트 모드 켜기/끄기 알약 버튼
    "thumb_alt": r"^(생성된 동영상 썸네일|Generated video thumbnail)$",   # 2026-10: 결과 격자의 썸네일 img alt (격자에는 <video> 가 없다)
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
def gate_violations(targets: list[dict], cuts: list[dict]) -> list[str]:
    """제출 직전 관문. 컷 규칙(숫자·옷·꼬리…)은 이번에 보낼 컷만, 구성 규칙(실사 비중·연속)은 편 전체로 본다.

    2026-10 사고: 6초 그룹(6컷 중 실사 2컷)만 놓고 실사 비중을 재서 33.6% 로 막혔다 — 편 전체는 19%.
    """
    per_cut = [v for v in style.check(targets) if not v.startswith(("실사", "연속"))]
    return per_cut + style.composition_only(style.check(cuts))


def map_clips(order: list[int], urls: list[str]) -> dict[int, str]:
    """화면(최신순) 동영상 주소를 제출 순서의 컷 번호에 매핑한다. 개수가 정확히 같아야 한다."""
    if len(urls) != len(order):
        raise ValueError(f"동영상 {len(urls)}개 / 제출 {len(order)}개 — 개수가 다르면 매핑할 수 없다")
    return dict(zip(order[::-1], urls))


def match_prompts(prompts: dict[int, str], pages: list[str], head: int = 160) -> list[int | None]:
    """상세 화면 글자마다 그 안에 들어 있는 컷 프롬프트를 찾아 컷 번호를 돌려준다.

    2026-10 Flow 는 클립을 열면 생성에 쓴 프롬프트 전문이 보인다 — 화면 순서(최신순) 가정 대신 이걸로 매핑한다.
    전문이 안 맞으면 앞부분(head 글자)으로 한 번 더 본다. 0개 또는 2개 이상 맞으면 None.
    """
    norm = lambda x: " ".join((x or "").split())
    out: list[int | None] = []
    for t in pages:
        t = norm(t)
        hits = [n for n, pr in prompts.items() if norm(pr) and norm(pr) in t]
        if not hits:
            hits = [n for n, pr in prompts.items() if norm(pr) and norm(pr)[:head] in t]
        out.append(hits[0] if len(hits) == 1 else None)
    return out


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


_JS_CLOSE_AGENT = """
() => {
  // 2026-10 Flow 개편: 새 프로젝트를 열면 오른쪽에 AI 에이전트 대화창이 열려 있어 아래 프롬프트 상자(설정 칩)가 가려진다.
  // 대화창의 '닫기' 버튼 = aria-label 이 Close/닫기 이고, 같은 패널 안에 '세션' 관련 버튼이 있는 것.
  const vis = e => { const r = e.getBoundingClientRect(); return r.width > 4 && r.height > 4; };
  const closes = [...document.querySelectorAll("button")].filter(vis)
    .filter(b => /^(Close|닫기)$/.test(b.getAttribute("aria-label") || ""));
  for (const b of closes) {
    let p = b;
    for (let i = 0; i < 8 && p; i++, p = p.parentElement) {
      if (p.querySelector && p.querySelector('button[aria-label*="session" i], button[aria-label*="세션"]')) {
        b.click(); return true;
      }
    }
  }
  return false;
}
"""


def close_agent_panel(page) -> None:
    """에이전트 대화창이 열려 있으면 닫는다(없으면 아무것도 안 한다)."""
    if page.evaluate(_JS_CLOSE_AGENT):
        _log("  에이전트 대화창 닫음")
        page.wait_for_timeout(1200)


_JS_FIND_ARIA = """
(pattern) => {
  const rx = new RegExp(pattern);
  const vis = e => { const r = e.getBoundingClientRect();
    return r.width > 8 && r.height > 8 && r.bottom > 0 && r.top < innerHeight; };
  const el = [...document.querySelectorAll("button,[role=button]")].filter(vis)
    .find(e => rx.test(e.getAttribute("aria-label") || ""));
  if (!el) return null;
  const r = el.getBoundingClientRect();
  return { x: Math.round(r.x + r.width / 2), y: Math.round(r.y + r.height / 2),
           text: (el.innerText || "").replace(/\\s+/g, " ").trim().slice(0, 60) };
}
"""

_JS_CREDIT = """
(pattern) => {
  // 설정 패널의 '생성 시 N 크레딧이 사용됩니다' — 가장 짧게 들어맞는 글자에서 N 을 읽는다
  const rx = new RegExp(pattern);
  const hits = [...document.querySelectorAll("span,div,p,label")]
    .map(e => (e.innerText || "").replace(/\\s+/g, " ").trim()).filter(t => rx.test(t))
    .sort((a, b) => a.length - b.length);
  return hits.length ? parseInt(hits[0].match(rx)[1], 10) : null;
}
"""

_JS_AGENT_STATE = """
() => {
  const b = [...document.querySelectorAll("button")]
    .find(e => /^(에이전트|Agent)$/.test((e.innerText || "").replace(/\\s+/g, " ").trim()));
  if (!b) return "none";
  return (b.getAttribute("aria-pressed") === "true" || /agent-mode-chip-checked/.test(b.className)) ? "on" : "off";
}
"""


def find_settings(page):
    """설정 칩(설정 트리거) 위치·글자. 에이전트 모드가 켜져 있으면 없는 것으로 본다."""
    if page.evaluate(_JS_AGENT_STATE) == "on":
        return None
    return page.evaluate(_JS_FIND_ARIA, TEXT["settings_aria"]) or page.evaluate(_JS_FIND, TEXT["mode_chip"])


_JS_AGENT_OFF = """
() => {
  // 에이전트 알약 버튼: <button class="agent-mode-chip ..." aria-pressed="true|false">에이전트</button>
  const b = [...document.querySelectorAll("button")]
    .find(e => /^(에이전트|Agent)$/.test((e.innerText || "").replace(/\\s+/g, " ").trim()));
  if (!b) return "none";
  if (b.getAttribute("aria-pressed") === "true" || /agent-mode-chip-checked/.test(b.className)) {
    b.click(); return "clicked";
  }
  return "off";
}
"""

_JS_VISIBLE_BUTTONS = """
() => [...document.querySelectorAll("button,[role=button]")].filter(e => {
    const r = e.getBoundingClientRect(); return r.width > 4 && r.height > 4 && r.top < innerHeight; })
  .map(e => ((e.innerText || "").replace(/\\s+/g, " ").trim() || "") + " | " + (e.getAttribute("aria-label") || "")
             + " | pressed=" + e.getAttribute("aria-pressed")).slice(0, 60)
"""


def ensure_direct_mode(page, debug_dir: Path | None = None) -> bool:
    """프롬프트 상자를 '직접 생성' 모드(설정 칩이 보이는 상태)로 만든다.

    2026-10 개편 실측: 넓은 창(1440px)에서 새 프로젝트는 '에이전트' 모드로 열린다 — 이때 설정 칩 대신
    '에이전트 요청 사항'·'설정(tune)' 버튼만 보인다. 상자 왼쪽 '에이전트' 알약(aria-pressed=true)을 끄면 칩이 나타난다.
    좌표 클릭 대신 상태(aria-pressed)를 보고 켜져 있을 때만 DOM click() 한다 — 좌표 클릭은 두 번 눌러 다시 켜는 사고가 났다.
    """
    for attempt in range(6):
        if find_settings(page):
            return True
        close_agent_panel(page)
        state = page.evaluate(_JS_AGENT_OFF)
        if state == "clicked":
            _log("  에이전트 모드를 껐다 → 직접 생성 모드")
        page.wait_for_timeout(1500 if state == "clicked" else 2500)
    if find_settings(page):
        return True
    # 실패 진단: 화면 사진과 보이는 버튼 목록을 남긴다
    try:
        if debug_dir:
            debug_dir.mkdir(parents=True, exist_ok=True)
            page.screenshot(path=str(debug_dir / "flow_fail.png"))
            _log(f"  진단 화면 저장 → {debug_dir / 'flow_fail.png'}")
        for line in page.evaluate(_JS_VISIBLE_BUTTONS):
            _log(f"    버튼: {line}")
    except Exception as e:                       # 진단 실패는 무시
        _log(f"  진단 실패: {e}")
    return False


def _has_len(chip: str, length: int) -> bool:
    import re as _re
    return bool(_re.search(rf"(^|[\s·]){length}(s|초)(\s|$)", chip))


def configure_video(page, length: int) -> str:
    """설정 칩을 열어 '동영상 · 9:16 · Omni 1.1 Flash · 720p · {length}s · x1' 로 맞추고 크레딧까지 확인한다.

    2026-10 실측: 설정은 브라우저(프로필)마다 따로 기억된다 — 플레이라이트 프로필은 '이미지 · 16:9 · x2' 로
    남아 있었다. 그래서 매번 전부 눌러 맞춘다. 하나라도 어긋나면 SystemExit (전송 전이라 크레딧 0).
    """
    hit = find_settings(page)
    if not hit:
        raise SystemExit("설정 칩을 못 찾았다 — 제출하지 않았다")
    page.mouse.click(hit["x"], hit["y"]); page.wait_for_timeout(1200)
    click_text(page, TEXT["video_mode"], "동영상 모드", 1200)     # 이미지 모드였다면 여기서 패널이 동영상 설정으로 바뀐다
    click_text(page, TEXT["portrait"], "세로 9:16", 700)
    m = page.evaluate(_JS_FIND_ARIA, TEXT["model_aria"])
    if m and not re.search(TEXT["model"], m["text"]):
        _log(f"  모델 {m['text']} → Omni 1.1 Flash 로 바꾼다")
        page.mouse.click(m["x"], m["y"]); page.wait_for_timeout(1000)
        click_text(page, TEXT["model_item"], "Omni 1.1 Flash", 1200)
    click_text(page, TEXT["res"], "720p", 700)
    click_text(page, TEXT["length"].format(len=length), f"{length}s 버튼", 900)
    click_text(page, TEXT["count1"], "출력 1개", 900)
    m = page.evaluate(_JS_FIND_ARIA, TEXT["model_aria"])
    model = m["text"] if m else "?"
    credit = page.evaluate(_JS_CREDIT, TEXT["credit"])
    page.keyboard.press("Escape"); page.wait_for_timeout(700)
    now = find_settings(page)
    chip = now["text"] if now else "?"
    _log(f"설정 칩 → {chip} · 모델 {model} · 컷당 {credit} 크레딧")
    if not re.match(r"^(동영상|Video) ·", chip):
        raise SystemExit(f"동영상 모드가 아니다 (칩: {chip}) — 제출하지 않았다")
    if not _has_len(chip, length):
        raise SystemExit(f"길이 {length}s 가 적용되지 않았다 (칩: {chip}) — 제출하지 않았다")
    if not re.search(r"x1\b", chip):
        raise SystemExit(f"출력 개수가 1이 아니다 (칩: {chip}) — 회수 매핑이 틀어져서 제출하지 않았다")
    if "crop_9_16" not in chip and "9:16" not in chip:
        raise SystemExit(f"세로 9:16 이 아니다 (칩: {chip}) — 제출하지 않았다")
    if not re.search(TEXT["model"], model):
        raise SystemExit(f"모델이 Omni 1.1 Flash 가 아니다 ({model}) — 크레딧이 달라져서 제출하지 않았다")
    if credit != CREDITS[length]:
        raise SystemExit(f"컷당 크레딧이 {credit} — 예상 {CREDITS[length]} 와 달라 제출하지 않았다")
    return chip


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
    bad = gate_violations(targets, cuts)
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
        meta.write_text(json.dumps({"url": url, "order": sent}, ensure_ascii=False), encoding="utf-8")

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
            if not ensure_direct_mode(page, project.build):
                raise SystemExit("직접 생성 모드(설정 칩)를 찾지 못했다 — guides/flow-ui.md 의 2026-10 메모를 보고 TEXT 를 고쳐라")
            configure_video(page, length)

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
            if sent:
                # 2026-10 실측: 마지막 전송 직후 창을 닫으면 그 요청이 Flow 에 안 닿을 때가 있다
                # (4초·6초 그룹에서 마지막 컷 C17·C22 가 사라짐). 넉넉히 기다렸다가 닫는다.
                _log("  마지막 전송이 Flow 에 닿도록 20초 기다린다")
                page.wait_for_timeout(20_000)
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


_JS_THUMBS = """
(pattern) => {
  const rx = new RegExp(pattern);
  return [...document.querySelectorAll("img")].filter(i => rx.test(i.alt || "")).map(i => {
    const r = i.getBoundingClientRect();
    return { x: Math.round(r.x + r.width / 2), y: Math.round(r.y + r.height / 2), w: Math.round(r.width) };
  });
}
"""

_JS_DETAIL = """
() => {
  const v = document.querySelector("video");
  return { src: v ? (v.currentSrc || v.src || null) : null, dur: v ? v.duration : null,
           text: (document.querySelector("main") || document.body).innerText || "" };
}
"""


def _thumbs(page, want: int = 0, timeout_ms: int = 12_000) -> list[dict]:
    """결과 격자의 썸네일 위치(화면 순서). want 개가 보일 때까지 조금 기다린다."""
    waited, th = 0, []
    while waited <= timeout_ms:
        th = page.evaluate(_JS_THUMBS, TEXT["thumb_alt"])
        if want and len(th) >= want:
            break
        page.wait_for_timeout(1000); waited += 1000
    return th


def collect(project: Project, length: int, headless: bool = False) -> int:
    """2026-10 Flow: 격자에는 썸네일만 있다. 썸네일을 하나씩 열어 상세 화면의 <video> 주소와 프롬프트를 읽고,
    프롬프트로 컷을 찾아(match_prompts) 내려받는다."""
    meta_path = project.build / f"submit_{length}s.json"
    if not meta_path.exists():
        raise SystemExit(f"{meta_path.name} 이 없다 — 먼저 `submit {length}` 를 실행하라")
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    url, order = meta["url"], meta["order"]
    if not order:
        raise SystemExit("제출된 컷이 없다 (order 비어 있음)")
    prompts = {c["n"]: c["prompt"] for c in project.load_cuts() if c["n"] in order}

    project.clips.mkdir(parents=True, exist_ok=True)
    got: dict[int, float] = {}
    from playwright.sync_api import sync_playwright
    with sync_playwright() as pw:
        ctx = _context(pw, headless=headless)
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        # 2026-10 실측: 넓은 창(1440)의 상세 화면은 <canvas> 편집기라 <video> 가 없다.
        # 800 폭이면 모바일 배치로 열려 상세 화면에 <video src=flow-content.google/video/…> 가 생긴다.
        page.set_viewport_size({"width": 800, "height": 1000})
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=90_000)
            page.wait_for_timeout(9000)
            th = _thumbs(page, len(order))
            state = readiness(len(th), len(order))
            _log(f"[{length}s] 화면의 완성 클립 {len(th)}개 / 제출 {len(order)}개 → {state}")
            if state == "pending":
                _log("아직 생성 중 — 잠시 뒤 다시 실행하라")
                sys.exit(EXIT_NOT_READY)
            if state == "too_many":
                raise SystemExit("클립이 제출 수보다 많다 — 출력 개수 설정이 1이 아니거나 다른 생성물이 섞였다. "
                                 "프로젝트를 브라우저에서 열어 확인하라")

            details = []
            for k in range(len(th)):
                if k:                                            # 매번 프로젝트를 새로 연다 (뒤로가기는 가끔 격자를 못 살린다)
                    page.goto(url, wait_until="domcontentloaded", timeout=90_000)
                    page.wait_for_timeout(6000)
                    th = _thumbs(page, len(order))
                    if len(th) <= k:
                        _log(f"  격자를 다시 열었더니 썸네일이 {len(th)}개뿐 — 잠시 뒤 다시")
                        sys.exit(EXIT_NOT_READY)
                # 화면 밖이면 스크롤해 보이게 한 뒤 위치를 다시 잰다
                page.evaluate("""([pattern, k]) => { const rx = new RegExp(pattern);
                    const im = [...document.querySelectorAll("img")].filter(i => rx.test(i.alt || ""))[k];
                    if (im) im.scrollIntoView({block: "center"}); }""", [TEXT["thumb_alt"], k])
                page.wait_for_timeout(800)
                th = _thumbs(page, len(order))
                page.mouse.click(th[k]["x"], th[k]["y"])
                d = None
                for _ in range(40):
                    page.wait_for_timeout(500)
                    d = page.evaluate(_JS_DETAIL)
                    if d["src"]:
                        break
                if not d or not d["src"]:
                    try:
                        page.screenshot(path=str(project.build / "collect_fail.png"))
                        _log(f"  진단 화면 → {project.build / 'collect_fail.png'} (주소 {page.url})")
                    except Exception:
                        pass
                    _log(f"  {k + 1}번째 클립에서 동영상을 못 찾았다 — 잠시 뒤 다시")
                    sys.exit(EXIT_NOT_READY)
                details.append(d)
                _log(f"  {k + 1}/{len(th)} 클립 주소 확보")

            cuts_of = match_prompts(prompts, [d["text"] for d in details])
            if None in cuts_of or len(set(cuts_of)) != len(cuts_of) or set(cuts_of) != set(order):
                raise SystemExit(f"프롬프트로 컷을 다 맞추지 못했다 (찾은 컷: {cuts_of} / 제출: {order}) — 받지 않았다")

            for n, d in zip(cuts_of, details):
                r = ctx.request.get(d["src"], timeout=180_000)
                if not r.ok:
                    raise SystemExit(f"C{n:02d} 내려받기 실패 (HTTP {r.status})")
                project.clip(n).write_bytes(r.body())
        finally:
            ctx.close()

    for n in sorted(cuts_of):
        got[n] = _duration(project.clip(n))
        _log(f"  C{n:02d} ← {got[n]:.2f}s")
    (project.build / f"collected_{length}s.json").write_text(json.dumps(got), encoding="utf-8")
    _log(f"[{length}s] 회수 {len(got)}/{len(order)}")
    return len(got)


# ── board: 스토리보드 대표 이미지 (Flow 이미지 모드) ─────────────────────────────
# 왜: 동영상 크레딧을 쓰기 전에 컷마다 같은 프롬프트로 이미지 한 장을 뽑아 구도·단어 해석 사고
#     (방열기가 자동차 부품으로, 사람 없는 컷에 마네킹 등)를 먼저 잡는다.
# 한계: 이미지 모델(Nano Banana)과 동영상 모델(Omni Flash)은 다르다 — 질감이 아니라 구도·해석을 본다.
# 회수 방식: 한 장씩 보내고, 화면에 '새로 생긴 큰 이미지'가 나타날 때까지 기다렸다가 받는다.
#     (이미지 결과 격자의 alt 글자를 아직 실측하지 못해 alt 대신 '전에 없던 큰 이미지'로 찾는다)

_JS_IMGS = """
() => [...document.querySelectorAll("img")].map(i => {
    const r = i.getBoundingClientRect();
    return { src: i.currentSrc || i.src || "", alt: i.alt || "", w: Math.round(r.width), h: Math.round(r.height),
             nw: i.naturalWidth || 0, nh: i.naturalHeight || 0, x: Math.round(r.x), y: Math.round(r.y) };
  }).filter(i => i.src)
"""

_JS_FETCH_B64 = """
async (src) => {
  const r = await fetch(src);
  if (!r.ok) return null;
  const b = await r.blob();
  return await new Promise(res => { const fr = new FileReader();
    fr.onload = () => res({ type: b.type, data: String(fr.result).split(",")[1] }); fr.readAsDataURL(b); });
}
"""


def pick_new_image(before: list[str], now: list[dict], min_px: int = 256, min_shown: int = 60) -> dict | None:
    """전송 전 이미지 주소 목록(before)에 없던, 충분히 큰 이미지 하나를 고른다(순수 로직 — 테스트 대상).

    아이콘·프로필 사진은 크기로 거르고, 여러 개가 새로 보이면 화면 왼쪽 위(최신)를 고른다.
    """
    seen = set(before)
    new = [i for i in now if i.get("src") and i["src"] not in seen
           and max(i.get("nw", 0), i.get("nh", 0)) >= min_px and min(i.get("w", 0), i.get("h", 0)) >= min_shown]
    if not new:
        return None
    return sorted(new, key=lambda i: (i.get("y", 0), i.get("x", 0)))[0]


def _ext_of(content_type: str, data: bytes) -> str:
    if data[:8] == b"\x89PNG\r\n\x1a\n" or "png" in (content_type or ""):
        return "png"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP" or "webp" in (content_type or ""):
        return "webp"
    return "jpg"


def configure_image(page):
    """설정 칩을 열어 '이미지 · 9:16 · x1' 로 맞추고 (칩, 장당 크레딧, 모델)을 돌려준다. 어긋나면 SystemExit."""
    hit = find_settings(page)
    if not hit:
        raise SystemExit("설정 칩을 못 찾았다 — 보내지 않았다")
    page.mouse.click(hit["x"], hit["y"]); page.wait_for_timeout(1200)
    click_text(page, TEXT["image_mode"], "이미지 모드", 1500)
    click_text(page, TEXT["portrait"], "세로 9:16", 700)
    click_text(page, TEXT["count1"], "출력 1개", 900)
    m = page.evaluate(_JS_FIND_ARIA, TEXT["model_aria"])
    model = m["text"] if m else "?"
    credit = page.evaluate(_JS_CREDIT, TEXT["credit"])
    page.keyboard.press("Escape"); page.wait_for_timeout(700)
    now = find_settings(page)
    chip = now["text"] if now else "?"
    _log(f"설정 칩 → {chip} · 모델 {model} · 장당 크레딧 {credit if credit is not None else '표시 없음'}")
    if re.match(r"^(동영상|Video) ·", chip):
        raise SystemExit(f"이미지 모드로 안 바뀌었다 (칩: {chip}) — 보내지 않았다")
    if not re.search(r"x1\b", chip):
        raise SystemExit(f"출력 개수가 1이 아니다 (칩: {chip}) — 보내지 않았다")
    if "crop_9_16" not in chip and "9:16" not in chip:
        raise SystemExit(f"세로 9:16 이 아니다 (칩: {chip}) — 보내지 않았다")
    return chip, credit, model


def board(project: Project, only: set[int] | None = None, max_credit: int | None = None,
          redo: bool = False, headless: bool = False, wait_sec: int = 180) -> int:
    """컷마다 Flow 이미지 모드로 대표 이미지 한 장 → build/board/C##.<확장자>.

    크레딧 안전장치: 설정 패널의 '생성 시 N 크레딧'을 읽어
      · N 이 0 이면 그대로 진행
      · N 이 1 이상이거나 표시가 없으면 보내지 않고 멈춘다 → 사용자가 확인한 뒤 --max-credit N 으로 다시
    """
    cuts = project.load_cuts()
    out = project.build / "board"
    out.mkdir(parents=True, exist_ok=True)
    have = lambda n: any(out.glob(f"C{n:02d}.*"))
    targets = [c for c in cuts if (only is None or c["n"] in only) and (redo or not have(c["n"]))]
    if not targets:
        _log("[board] 뽑을 컷 없음 (이미 다 있다 — 다시 뽑으려면 --redo)")
        return 0
    bad = gate_violations(targets, cuts)
    if bad:
        for b in bad:
            print("★위반:", b)
        raise SystemExit("정본 검증 실패 — 보내지 않았다")

    meta_path = out / "board.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.exists() else {}
    got: list[int] = []
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
            meta["url"] = page.url
            _log(f"프로젝트: {page.url}")
            page.keyboard.press("Escape"); page.wait_for_timeout(500)
            if not ensure_direct_mode(page, project.build):
                raise SystemExit("직접 생성 모드(설정 칩)를 찾지 못했다 — guides/flow-ui.md 의 2026-10 메모를 보라")

            # 설정 패널을 연 채로 화면을 남겨 둔다 (크레딧·모델 확인용)
            chip, credit, model = configure_image(page)
            hit = find_settings(page)
            if hit:
                page.mouse.click(hit["x"], hit["y"]); page.wait_for_timeout(1000)
                page.screenshot(path=str(out / "board_settings.png"))
                page.keyboard.press("Escape"); page.wait_for_timeout(600)
            meta.update({"chip": chip, "credit_per_image": credit, "model": model})
            if credit is None and max_credit is None:
                raise SystemExit(f"장당 크레딧 표시를 못 읽었다 — {out / 'board_settings.png'} 를 확인하고, "
                                 f"괜찮으면 `board {project.ref} --max-credit 0` 처럼 상한을 주고 다시 (보내지 않았다)")
            if credit is not None and credit > (max_credit or 0):
                raise SystemExit(f"이미지 1장당 {credit} 크레딧 · {len(targets)}장이면 약 {credit * len(targets)} — "
                                 f"진행하려면 `board {project.ref} --max-credit {credit}` (보내지 않았다)")
            _log(f"[board] {len(targets)}장: " + ", ".join(f"C{c['n']:02d}" for c in targets))

            for c in targets:
                before = [i["src"] for i in page.evaluate(_JS_IMGS)]
                ed = _editor(page)
                ed.click(timeout=15_000)
                page.keyboard.press("Meta+A" if sys.platform == "darwin" else "Control+A")
                page.keyboard.press("Delete")
                page.wait_for_timeout(300)
                page.keyboard.type(c["prompt"], delay=0)
                page.wait_for_timeout(900)
                typed = ed.inner_text()
                if len("".join(typed.split())) < len("".join(c["prompt"].split())) * 0.95:
                    _log(f"  C{c['n']:02d} 입력이 잘렸다 — 건너뜀")
                    continue
                if not click_text(page, TEXT["send"], "전송 버튼", 2500):
                    _log(f"  C{c['n']:02d} 전송 버튼 못 찾음 — 건너뜀")
                    continue
                pick, last, waited = None, None, 0
                while waited < wait_sec:
                    page.wait_for_timeout(3000); waited += 3
                    cand = pick_new_image(before, page.evaluate(_JS_IMGS))
                    if cand and last and cand["src"] == last["src"]:
                        pick = cand                       # 두 번 연속 같은 주소 = 다 그려졌다
                        break
                    last = cand
                if not pick:
                    _log(f"  C{c['n']:02d} {wait_sec}초 안에 새 이미지가 안 보였다 — 건너뜀 (Flow 화면에서 실패 여부 확인)")
                    page.screenshot(path=str(out / f"C{c['n']:02d}_timeout.png"))
                    continue
                data, ctype = None, ""
                try:
                    r = page.evaluate(_JS_FETCH_B64, pick["src"])
                    if r and r.get("data"):
                        import base64
                        data, ctype = base64.b64decode(r["data"]), r.get("type", "")
                except Exception:
                    data = None
                if data is None and pick["src"].startswith("http"):
                    rr = ctx.request.get(pick["src"], timeout=120_000)
                    if rr.ok:
                        data, ctype = rr.body(), rr.headers.get("content-type", "")
                if not data:
                    _log(f"  C{c['n']:02d} 이미지를 내려받지 못했다 — 건너뜀")
                    continue
                f = out / f"C{c['n']:02d}.{_ext_of(ctype, data)}"
                f.write_bytes(data)
                meta.setdefault("cuts", {})[str(c["n"])] = {"file": f.name, "px": [pick["nw"], pick["nh"]],
                                                           "prompt_head": c["prompt"][:80]}
                meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
                got.append(c["n"])
                _log(f"  C{c['n']:02d} ← {f.name} ({pick['nw']}×{pick['nh']})")
        finally:
            meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
            ctx.close()

    _log(f"[board] {len(got)}/{len(targets)}장 → {out.relative_to(project.dir)}")
    missed = [c["n"] for c in targets if c["n"] not in got]
    if missed:
        _log(f"★빠진 컷 {missed} — `board {project.ref} --only {','.join(map(str, missed))}` 로 다시")
        sys.exit(EXIT_PARTIAL)
    return len(got)


def _duration(path: Path) -> float:
    import subprocess
    out = subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                                   "-of", "csv=p=0", str(path)])
    return float(out.decode().strip())
