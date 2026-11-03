# -*- coding: utf-8 -*-
"""구글 Flow 브라우저 조작 — 플레이라이트.

흐름
    login    창을 띄워 사용자가 구글에 로그인한다. 쿠키는 ~/.flowmaker/profile 에 남는다(한 번만).
             ★같은 창에서 생성 설정(동영상 · 세로 9:16 · 출력 1개)을 한 번 맞춰 둔다 — Flow 는 계정별로 기억한다.
    submit   길이 그룹(4/6/8/10초) 하나를 이 편의 Flow 프로젝트에 제출하고 **실제로 전송된 컷 순서**를 저장한다.
             ★제출 직전에 style.check() 를 다시 돌린다 — 크레딧을 쓰기 전 마지막 관문.
    collect  저장된 프로젝트를 다시 열어 생성이 끝난 클립을 내려받는다. 기다리지 않는다 —
             덜 됐으면 종료코드 2로 빠지므로 잠시 뒤 다시 부르면 된다.

편마다 Flow 프로젝트 하나 (2026-11 사용자 결정)
    전에는 board·submit 을 부를 때마다 새 프로젝트를 만들어 Flow 목록이 편 하나에 여러 개로 흩어졌다.
    이제 처음 연 프로젝트 주소를 project.json "flow_url" 에 적고, 이후 board(이미지)·submit(동영상)이 모두 그 프로젝트를 다시 연다.
    그래서 한 프로젝트 격자에 이미지·이전 클립·버린 클립이 섞인다 → collect 는 개수로 매핑하지 않고,
    최신 썸네일부터 열어 **프롬프트로 컷을 찾고**, 이미 받아 간 클립(build/flow_seen.json 의 taken)에 닿으면 멈춘다.
    재생성한 컷이 아직 생성 중이면 옛 클립까지 내려가기 전에 taken 에 닿아 멈추므로 옛 클립을 새 것으로 잘못 받지 않는다.

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
def gate_violations(targets: list[dict], cuts: list[dict], diag_style: str = "clay") -> list[str]:
    """제출 직전 관문. 컷 규칙(숫자·옷·꼬리…)은 이번에 보낼 컷만, 구성 규칙(실사 비중·연속)은 편 전체로 본다.

    2026-10 사고: 6초 그룹(6컷 중 실사 2컷)만 놓고 실사 비중을 재서 33.6% 로 막혔다 — 편 전체는 19%.
    diag_style 은 편의 그림 스타일(project.json). clay 면 예전과 똑같이 부른다(바꿔 끼운 검사 함수와의 호환).
    """
    chk = (lambda cs: style.check(cs)) if diag_style == "clay" else (lambda cs: style.check(cs, diag_style=diag_style))
    per_cut = [v for v in chk(targets) if not v.startswith(("실사", "연속"))]
    return per_cut + style.composition_only(chk(cuts))


def map_clips(order: list[int], urls: list[str]) -> dict[int, str]:
    """화면(최신순) 동영상 주소를 제출 순서의 컷 번호에 매핑한다. 개수가 정확히 같아야 한다."""
    if len(urls) != len(order):
        raise ValueError(f"동영상 {len(urls)}개 / 제출 {len(order)}개 — 개수가 다르면 매핑할 수 없다")
    return dict(zip(order[::-1], urls))


def match_prompts(prompts: dict[int, str], pages: list[str], head: int = 160, prefer: set | None = None) -> list[int | None]:
    """상세 화면 글자마다 그 안에 들어 있는 컷 프롬프트를 찾아 컷 번호를 돌려준다.

    2026-10 Flow 는 클립을 열면 생성에 쓴 프롬프트 전문이 보인다 — 화면 순서(최신순) 가정 대신 이걸로 매핑한다.
    전문이 안 맞으면 앞부분(head 글자)으로 한 번 더 본다. 0개 또는 2개 이상 맞으면 None.
    """
    # 2026-11: Flow 상세 화면은 ' 를 ’ 로 바꿔 보여준다(경복궁 "palace's") — 따옴표·대시를 맞춘 뒤 비교한다
    _q = str.maketrans({"\u2019": "'", "\u2018": "'", "\u201c": '"', "\u201d": '"', "\u2013": "-", "\u2014": "-", "\u00a0": " "})
    norm = lambda x: " ".join((x or "").translate(_q).split())
    out: list[int | None] = []
    for t in pages:
        t = norm(t)
        hits = [n for n, pr in prompts.items() if norm(pr) and norm(pr) in t]
        if not hits:
            hits = [n for n, pr in prompts.items() if norm(pr) and norm(pr)[:head] in t]
        if len(hits) > 1 and prefer:                 # 2026-11 경복궁: 보드만 다르고 영상 프롬프트가 같은 컷(C02·C03) — 이번에 찾는 컷을 고른다
            hits = [n for n in hits if n in prefer] or hits
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
  const el = [...document.querySelectorAll("button,[role=button],[role=tab],[role=menuitem],[role=menuitemradio],[role=option],[role=radio],a")].filter(vis)
    .find(e => rx.test((e.innerText || "").replace(/\\s+/g, " ").trim()));
  if (!el) return null;
  const r = el.getBoundingClientRect();
  return { x: Math.round(r.x + r.width / 2), y: Math.round(r.y + r.height / 2),
           text: (el.innerText || "").replace(/\\s+/g, " ").trim().slice(0, 60) };
}
"""


_JS_PANEL_ITEMS = """
() => [...document.querySelectorAll("button,[role],a,li")].filter(e => {
    const r = e.getBoundingClientRect(); return r.width > 4 && r.height > 4 && r.top < innerHeight && r.bottom > 0; })
  .map(e => ({ tag: e.tagName, role: e.getAttribute("role") || "", aria: e.getAttribute("aria-label") || "",
               text: (e.innerText || "").replace(/\\s+/g, " ").trim().slice(0, 50),
               y: Math.round(e.getBoundingClientRect().y) })).slice(0, 150)
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
    # 2026-11: 편마다 한 프로젝트를 쓰면서 board(이미지) 뒤에 같은 프로젝트로 submit 하게 됐다 — 칩이 이미지 모드로 남아 있다.
    # 첫 시도에서 패널 안 '동영상'을 못 찾았다(패널이 안 열렸거나 다른 요소) → 열린 화면을 남기고 한 번 더 연다.
    page.mouse.click(hit["x"], hit["y"]); page.wait_for_timeout(1500)
    if not click_text(page, TEXT["video_mode"], "동영상 모드", 1500):  # 이미지 모드였다면 여기서 패널이 동영상 설정으로 바뀐다
        dbg = Path.cwd() / "flow_video_mode_debug"
        try:
            page.screenshot(path=str(dbg) + ".png")
            dbg.with_suffix(".json").write_text(json.dumps(page.evaluate(_JS_PANEL_ITEMS), ensure_ascii=False, indent=1),
                                                encoding="utf-8")
            _log(f"  진단 → {dbg}.png · {dbg.with_suffix('.json').name}")
        except Exception:
            pass
        page.keyboard.press("Escape"); page.wait_for_timeout(700)
        hit = find_settings(page)
        if hit:
            page.mouse.click(hit["x"], hit["y"]); page.wait_for_timeout(2000)
            click_text(page, TEXT["video_mode"], "동영상 모드(다시)", 1500)
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

_JS_TITLE_CANDS = """
() => {
  // 프로젝트 화면 위쪽(머리글)의 '프로젝트 이름' 후보 — 입력칸·편집 가능 글자·짧은 글자 순으로.
  // Flow 화면 구조를 아직 실측하지 못했다(2026-11) → 후보 목록을 build/flow_title_probe.json 에 남긴다.
  const vis = e => { const r = e.getBoundingClientRect();
    return r.width > 20 && r.height > 10 && r.top >= 0 && r.top < 110 && getComputedStyle(e).visibility !== "hidden"; };
  const icon = t => /^[a-z_]+$/.test(t);              // 머티리얼 아이콘 글자(arrow_back 등)
  const out = [];
  for (const e of document.querySelectorAll('input,textarea,[contenteditable="true"],[role="textbox"],h1,h2,button,span,div,a')) {
    if (!vis(e)) continue;
    const isInput = /^(INPUT|TEXTAREA)$/.test(e.tagName) || e.isContentEditable || e.getAttribute("role") === "textbox";
    const t = (isInput ? (e.value || e.innerText || e.getAttribute("aria-label") || "") : (e.innerText || "")).replace(/\\s+/g, " ").trim();
    if (!isInput && (e.children.length > 2 || !t || t.length > 60 || icon(t))) continue;
    const r = e.getBoundingClientRect();
    out.push({ tag: e.tagName, input: isInput, text: t.slice(0, 60), aria: e.getAttribute("aria-label") || "",
               x: Math.round(r.x + r.width / 2), y: Math.round(r.y + r.height / 2), w: Math.round(r.width) });
  }
  return out;
}
"""

_JS_ACTIVE_EDIT = """
() => { const e = document.activeElement; if (!e) return null;
  const ok = /^(INPUT|TEXTAREA)$/.test(e.tagName) || e.isContentEditable;
  return ok ? (e.value !== undefined && e.tagName !== "DIV" ? e.value : e.innerText) : null; }
"""

# 프로젝트 이름 자리에 흔히 보이는 기본 이름 (날짜·'제목 없음' 등) — 후보를 고를 때 우선한다
_DEFAULT_TITLE_RX = re.compile(r"(제목 없|Untitled|새 프로젝트|New project|\d{1,2}[./:\- ]\d{1,2}|"
                               r"(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.? \d|\d+월 \d+일)", re.I)
_SKIP_TITLE_RX = re.compile(r"^(Flow|Google Flow|공유|Share|내보내기|Export|에이전트|Agent|로그인|Sign in)$", re.I)


def pick_title_candidate(cands: list[dict], current_title: str = "") -> dict | None:
    """머리글 후보에서 '프로젝트 이름'으로 보이는 것 하나 (순수 로직 — 테스트 대상).
    입력칸 > 지금 제목과 같은 글자 > 기본 이름(날짜·제목 없음) 모양 > 가장 왼쪽 짧은 글자."""
    c = [x for x in cands if not _SKIP_TITLE_RX.match(x.get("text", ""))
         and not re.match(r"^(Search|검색)$", x.get("aria", ""), re.I)]
    # 2026-11 실측: 머리글 왼쪽 'home <이름> more_vert' 안의 <input aria-label="Editable text" value="Nov 01 - 15:17">
    for rule in (lambda x: x.get("input") and re.search(r"Editable|편집", x.get("aria", ""), re.I),
                 lambda x: x.get("input"),
                 lambda x: current_title and x.get("text") == current_title,
                 lambda x: _DEFAULT_TITLE_RX.search(x.get("text", ""))):
        hit = [x for x in c if rule(x)]
        if hit:
            return sorted(hit, key=lambda x: x.get("x", 0))[0]
    return None


def ensure_flow_title(page, project: Project) -> bool:
    """Flow 프로젝트 이름을 편 제목(project.title)으로 바꾼다. 이미 확인됐으면 건너뛴다.
    실패해도 생성은 계속한다(이름은 부가 기능) — 후보 목록·화면을 build/ 에 남겨 TEXT·규칙을 고칠 수 있게 한다."""
    title = project.title
    if project.config().get("flow_titled") == title:
        return True
    project.build.mkdir(parents=True, exist_ok=True)
    probe = project.build / "flow_title_probe.json"
    try:
        cands = page.evaluate(_JS_TITLE_CANDS)
        hit = pick_title_candidate(cands, project.config().get("flow_titled") or "")
        ok = False
        if hit:
            for click in ("click", "dblclick"):
                getattr(page.mouse, click)(hit["x"], hit["y"]); page.wait_for_timeout(700)
                if page.evaluate(_JS_ACTIVE_EDIT) is not None:
                    page.keyboard.press("Meta+A" if sys.platform == "darwin" else "Control+A")
                    page.keyboard.type(title, delay=0)
                    page.keyboard.press("Enter"); page.wait_for_timeout(1200)
                    page.keyboard.press("Escape"); page.wait_for_timeout(400)
                    ok = any(title in (x.get("text") or "") for x in page.evaluate(_JS_TITLE_CANDS))
                    break
                page.keyboard.press("Escape"); page.wait_for_timeout(300)
        probe.write_text(json.dumps({"title": title, "picked": hit, "ok": ok, "candidates": cands},
                                    ensure_ascii=False, indent=1), encoding="utf-8")
        if ok:
            project.set_config("flow_titled", title)
            _log(f"  Flow 프로젝트 이름 → {title}")
            return True
        page.screenshot(path=str(project.build / "flow_title_fail.png"))
        _log(f"  ★Flow 프로젝트 이름을 못 바꿨다(생성은 계속) — {probe.name} · flow_title_fail.png 를 보고 고친다")
    except Exception as e:                                   # 이름 때문에 생성을 멈추지 않는다
        _log(f"  ★Flow 프로젝트 이름 바꾸기 오류(생성은 계속): {e}")
    return False



def open_flow_project(page, project: Project) -> str:
    """이 편의 Flow 프로젝트를 연다 — project.json "flow_url" 이 있으면 그것을, 없으면 '새 프로젝트'를 만들어 주소를 적어 둔다.
    (로그인 확인이 끝난 page 를 받는다.)"""
    url = project.flow_url
    if url:
        page.goto(url, wait_until="domcontentloaded", timeout=90_000)
        page.wait_for_timeout(7000)
        dismiss_modals(page)
        if "/project/" in page.url:
            _log(f"프로젝트(이 편 것을 이어 씀): {page.url}")
            ensure_flow_title(page, project)
            return page.url
        _log(f"  저장된 프로젝트를 열지 못했다(지금 주소 {page.url}) — 새로 만든다")
        page.goto(FLOW_URL, wait_until="domcontentloaded", timeout=90_000)
        page.wait_for_timeout(7000)
        dismiss_modals(page)
    if not click_text(page, TEXT["new_project"], "새 프로젝트", 9000):
        raise SystemExit("'새 프로젝트' 버튼을 못 찾았다 — guides/flow-ui.md 를 보고 TEXT 를 고쳐라")
    page.wait_for_timeout(1500)
    project.set_flow_url(page.url)
    project.set_config("flow_titled", None)
    _log(f"프로젝트(새로 만듦 → project.json flow_url): {page.url}")
    page.wait_for_timeout(2500)
    ensure_flow_title(page, project)
    return page.url


def submit(project: Project, length: int, only: set[int] | None = None, headless: bool = False) -> Path:
    cuts = project.load_cuts()
    targets = [c for c in cuts if not c["done"] and c["len"] == length and c.get("engine", "flow") == "flow"
               and (only is None or c["n"] in only)]
    if not targets:
        _log(f"[{length}s] 제출할 컷 없음")
        sys.exit(0)

    # ★마지막 관문 — 이번에 크레딧을 쓸 컷만 검사하고, 구성 규칙은 전체로 한 번 더 본다
    bad = gate_violations(targets, cuts, project.style)
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

            url = open_flow_project(page, project)
            save()

            page.keyboard.press("Escape"); page.wait_for_timeout(500)
            if not ensure_direct_mode(page, project.build):
                raise SystemExit("직접 생성 모드(설정 칩)를 찾지 못했다 — guides/flow-ui.md 의 2026-10 메모를 보고 TEXT 를 고쳐라")
            configure_video(page, length)

            for c in targets:
                ed = _editor(page)
                _clear_editor(page, ed)
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
    return { x: Math.round(r.x + r.width / 2), y: Math.round(r.y + r.height / 2), w: Math.round(r.width),
             src: i.currentSrc || i.src || "" };
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


# 2026-11 GV90 편: 격자가 화면에 보이는 만큼만 그린다(보드 이미지가 많아 클립 13개만 보이고 오래된 C01~C09 를 못 찾음).
# 마지막 썸네일을 화면 아래로 끌어 내리고 스크롤 가능한 조상까지 내려서 더 불러온다.
_JS_SCROLL_MORE = """
(pattern) => {
  const rx = new RegExp(pattern);
  const ims = [...document.querySelectorAll("img")].filter(i => rx.test(i.alt || ""));
  const all = [...document.querySelectorAll("img")];
  const last = all[all.length - 1] || ims[ims.length - 1];
  if (last) last.scrollIntoView({block: "end"});
  let el = last ? last.parentElement : null;
  while (el) { const s = getComputedStyle(el); if (/(auto|scroll)/.test(s.overflowY) && el.scrollHeight > el.clientHeight) { el.scrollBy(0, el.clientHeight * 0.9); break; } el = el.parentElement; }
  window.scrollBy(0, window.innerHeight * 0.9);
  return ims.length;
}
"""


def _thumbs(page, want: int = 0, timeout_ms: int = 12_000) -> list[dict]:
    """결과 격자의 썸네일 위치(화면 순서). want 개가 보일 때까지 기다리고, 모자라면 아래로 스크롤해 더 불러온다."""
    waited, th = 0, []
    while waited <= timeout_ms:
        th = page.evaluate(_JS_THUMBS, TEXT["thumb_alt"])
        if want and len(th) >= want:
            break
        if want:
            page.evaluate(_JS_SCROLL_MORE, TEXT["thumb_alt"])
        page.wait_for_timeout(1000); waited += 1000
    return th


def _thumbs_all(page, max_steps: int = 40) -> list[dict]:
    """격자를 끝까지 스크롤해 보이는 동영상 썸네일 수가 더 늘지 않을 때까지 불러온 뒤 맨 위로 돌아간다."""
    n_prev, still = -1, 0
    for _ in range(max_steps):
        n = page.evaluate(_JS_SCROLL_MORE, TEXT["thumb_alt"])
        page.wait_for_timeout(900)
        still = still + 1 if n == n_prev else 0
        if still >= 3:
            break
        n_prev = n
    page.evaluate("() => { window.scrollTo(0, 0); document.querySelectorAll('*').forEach(e => { if (e.scrollTop) e.scrollTop = 0; }); }")
    page.wait_for_timeout(800)
    return page.evaluate(_JS_THUMBS, TEXT["thumb_alt"])


def url_key(u: str | None) -> str:
    """서명 붙은 주소의 ?쿼리·#조각을 떼어 같은 파일이면 같은 키가 되게 한다."""
    return (u or "").split("#")[0].split("?")[0]


def plan_collect(order: list[int], recs: list[dict]) -> tuple[dict[int, int], bool]:
    """최신순 썸네일 기록(recs: {"cut": n|None, "taken": bool})에서 이번 그룹(order) 컷의 위치를 고른다 — 순수 로직.

    · 위에서부터 보며 같은 컷은 처음(=가장 최신) 것만 쓴다.
    · 이미 받아 간 클립(taken)에 닿으면 멈춘다 — 그 아래는 이번 제출보다 오래된 것이다.
    돌려주는 값: ({컷: 인덱스}, 멈춤 여부)
    """
    want, found = set(order), {}
    for k, r in enumerate(recs):
        if r.get("taken"):
            # 2026-11 GV90 편: frames 는 길이가 섞인 한 묶음으로 제출해 격자에서 4·6·8초가 뒤섞인다 —
            # 4초를 먼저 받으면 맨 위가 '받아 간 클립'이라 6·8초 회수가 바로 멈췄다. 받아 간 것은 건너뛰고 계속 본다.
            continue
        n = r.get("cut")
        if n in want and n not in found:
            found[n] = k
    return found, False


def collect(project: Project, length: int, headless: bool = False, partial: bool = False) -> int:
    """썸네일을 최신순으로 하나씩 열어 상세 화면의 <video> 주소와 프롬프트를 읽고, 프롬프트로 컷을 찾아 내려받는다.

    편마다 Flow 프로젝트 하나라 격자에 다른 길이 그룹·예전 클립·버린 클립이 섞여 있다(2026-11).
    한 번 연 썸네일은 build/flow_seen.json 에 기억해 다시 열지 않는다(다시 부를 때 빠르다).
    """
    meta_path = project.build / f"submit_{length}s.json"
    if not meta_path.exists():
        raise SystemExit(f"{meta_path.name} 이 없다 — 먼저 `submit {length}` 를 실행하라")
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    url, order = meta.get("url") or project.flow_url, meta["order"]
    if not order:
        raise SystemExit("제출된 컷이 없다 (order 비어 있음)")
    all_prompts = {c["n"]: c["prompt"] for c in project.load_cuts()}

    seen_path = project.build / "flow_seen.json"
    seen: dict = json.loads(seen_path.read_text(encoding="utf-8")) if seen_path.exists() else {}
    save_seen = lambda: seen_path.write_text(json.dumps(seen, ensure_ascii=False, indent=1), encoding="utf-8")
    taken_videos = {v.get("video") for v in seen.values() if v.get("taken")}

    project.clips.mkdir(parents=True, exist_ok=True)
    got: dict[int, float] = {}
    picked: dict[int, str] = {}           # 컷 → 썸네일 키
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
            _thumbs(page, 1)
            th = _thumbs_all(page)
            _log(f"[{length}s] 프로젝트의 완성 클립 썸네일 {len(th)}개(끝까지 스크롤) · 이번에 찾을 컷 {order}")
            recs: list[dict] = []
            for k in range(len(th)):
                key = url_key(th[k].get("src"))           # 썸네일 주소가 없으면 기억하지 않는다(위치는 바뀌므로)
                rec = seen.get(key) if key else None
                if rec is not None and rec.get("cut") is None and not rec.get("taken"):
                    if "text" in rec:                            # 글이 남아 있으면 다시 열지 않고 지금 규칙으로 다시 맞춰 본다
                        rec["cut"] = match_prompts(all_prompts, [rec["text"]], prefer=set(order))[0]
                    else:
                        rec = None                               # 예전 판(글 미보관)에서 못 맞춘 것 — 다시 열어 본다
                if rec is None:
                    if k:                                        # 매번 프로젝트를 새로 연다 (뒤로가기는 가끔 격자를 못 살린다)
                        page.goto(url, wait_until="domcontentloaded", timeout=90_000)
                        page.wait_for_timeout(6000)
                        th2 = _thumbs(page, k + 1)
                        if len(th2) <= k:
                            _log(f"  격자를 다시 열었더니 썸네일이 {len(th2)}개뿐 — 잠시 뒤 다시")
                            sys.exit(EXIT_NOT_READY)
                    page.evaluate("""([pattern, k]) => { const rx = new RegExp(pattern);
                        const im = [...document.querySelectorAll("img")].filter(i => rx.test(i.alt || ""))[k];
                        if (im) im.scrollIntoView({block: "center"}); }""", [TEXT["thumb_alt"], k])
                    page.wait_for_timeout(800)
                    th2 = _thumbs(page, k + 1)
                    if url_key(th2[k].get("src")) != url_key(th[k].get("src")):
                        _log("  격자 순서가 바뀌었다(새 클립이 생겼다) — 잠시 뒤 다시")
                        sys.exit(EXIT_NOT_READY)
                    page.mouse.click(th2[k]["x"], th2[k]["y"])
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
                    cut = match_prompts(all_prompts, [d["text"]], prefer=set(order))[0]
                    rec = {"video": d["src"], "cut": cut, "taken": url_key(d["src"]) in {url_key(v) for v in taken_videos},
                           "text": " ".join((d["text"] or "").split())[:6000]}   # 못 맞췄을 때 원인을 보려고 앞부분을 남긴다
                    if key:
                        seen[key] = rec
                        save_seen()
                    _log(f"  {k + 1}번째 썸네일 → " + (f"C{cut:02d}" if cut else "이 편 컷 아님/프롬프트 바뀜")
                         + (" (이미 받아 간 클립)" if rec["taken"] else ""))
                recs.append(rec)
                found, stopped = plan_collect(order, recs)
                if len(found) == len(order) or stopped:
                    break

            found, _ = plan_collect(order, recs)
            missing = [n for n in order if n not in found]
            if missing and not partial:
                _log(f"  아직 안 보이는 컷 {missing} — 생성 중이면 잠시 뒤 다시 (찾은 것만 받으려면 --partial)")
                sys.exit(EXIT_NOT_READY)
            if missing:
                _log(f"  ★격자에 없는 컷 {missing} — 찾은 {len(found)}개만 받는다(--partial). 없는 컷은 Flow 화면에서 실패 여부를 확인할 것")

            for n, k in found.items():
                rec = recs[k]
                r = ctx.request.get(rec["video"], timeout=180_000)
                if not r.ok:
                    raise SystemExit(f"C{n:02d} 내려받기 실패 (HTTP {r.status})")
                project.clip(n).write_bytes(r.body())
                rec["taken"] = True
                save_seen()
        finally:
            ctx.close()

    for n in sorted(found):
        got[n] = _duration(project.clip(n))
        _log(f"  C{n:02d} ← {got[n]:.2f}s")
    (project.build / f"collected_{length}s.json").write_text(json.dumps(got), encoding="utf-8")
    _log(f"[{length}s] 회수 {len(got)}/{len(order)}")
    return len(got)


# ── frames: 확인된 보드 이미지를 첫 장면(Start)으로 영상 만들기 (2026-11 쇼츠로 가져옴 — longform_studio/longmaker/frames.py 와 같은 경로)
# 왜: Flow 글→영상은 보드를 따르지 않고(온돌·zero15 C03), 질감도 첫 프레임 품질을 못 따라간다.
# cuts.json 의 컷에 "engine": "frames" 를 적으면 submit(글→영상)은 건너뛰고 이 명령이 맡는다. 크레딧은 글→영상과 같다.
# 이 편의 Flow 프로젝트 하나에 보내고 build/submit_<len>s.json 에 적어 두므로 회수는 그냥 `collect <편> <len>`.
# 보드의 AI 마크는 build/board_clean/C##.jpg (VM 에서 지운 판)가 있으면 그것을 쓴다 — 영상에 별이 두 개 생기지 않게.


def _clear_editor(page, ed) -> None:
    """프롬프트 칸만 비운다 (2026-11 GV90 편 사고 의심: 클릭이 칸을 못 잡은 채 Cmd+A·Delete 를 누르면
    Flow 격자의 미디어가 전부 선택·삭제(휴지통)될 수 있다). 포커스가 편집 칸이 아니면 키를 누르지 않고 멈춘다."""
    ed.click(timeout=15_000)
    ok = page.evaluate("() => { const a = document.activeElement; return !!(a && (a.isContentEditable || a.closest('[contenteditable=\"true\"]'))); }")
    if not ok:
        raise SystemExit("프롬프트 칸에 포커스가 없다 — 전체 선택·삭제 키를 누르지 않고 멈췄다(보내지 않았다)")
    ed.press("Meta+A" if sys.platform == "darwin" else "Control+A")
    ed.press("Delete")

def _set_start_frame(page, img: Path, tag: str, shot, slot: str = "start") -> None:
    """프레임 칸(Start/End)에 그림을 넣는다. slot="end" 는 마지막 장면 — 2026-11 경복궁 하강 비행(전경 → 근정전 정면)."""
    slot_rx = r"^(Start|시작)$" if slot == "start" else r"^(End|끝|종료)$"
    label = "시작(Start)" if slot == "start" else "끝(End)"
    if not click_text(page, slot_rx, f"{tag} {label} 칸", 2000):
        shot(f"{tag}_no_{slot}_slot"); raise SystemExit(f"{tag} {label} 칸을 못 찾았다 — 보내지 않았다 (크레딧 0)")
    hit = page.evaluate(_JS_FIND, r"Upload media|미디어 업로드")
    if not hit:
        shot(f"{tag}_no_dialog"); raise SystemExit("'Select a frame image' 창이 안 떴다 — 보내지 않았다")
    with page.expect_file_chooser(timeout=10_000) as fc:
        page.mouse.click(hit["x"], hit["y"])
    fc.value.set_files(str(img))
    page.wait_for_timeout(3000)
    if page.evaluate(_JS_FIND, r"^I agree$|^동의$"):
        shot(f"{tag}_rights")
        print("\n★ Flow 창에 'Rights to use this image' 확인이 떴습니다. 읽고 직접 'I agree'(동의)를 눌러 주세요(3분 기다림).\n", flush=True)
        for _ in range(90):
            page.wait_for_timeout(2000)
            if not page.evaluate(_JS_FIND, r"^I agree$|^동의$"):
                break
        else:
            raise SystemExit("동의 창이 닫히지 않았다 — 보내지 않았다")
    stem = img.stem[:16]
    JS_ITEM = """(stem) => { const vis = e => { const r = e.getBoundingClientRect(); return r.width > 40 && r.height > 20; };
            const el = [...document.querySelectorAll("button,[role=button],[role=option],li,div")].filter(vis)
              .filter(e => (e.innerText || "").trim().startsWith(stem) && (e.innerText || "").length < 80)
              .sort((x, y) => x.getBoundingClientRect().height - y.getBoundingClientRect().height)[0];
            if (!el) return null; const r = el.getBoundingClientRect();
            return {x: Math.round(r.x + r.width / 2), y: Math.round(r.y + r.height / 2), text: el.innerText.trim()}; }"""
    filled = False
    for _ in range(60):
        page.wait_for_timeout(1000)
        if not page.evaluate(_JS_FIND, slot_rx) and not page.evaluate(_JS_FIND, r"Upload media|미디어 업로드"):
            filled = True; break
        if page.evaluate(_JS_FIND, r"^\d{1,2}%$"):
            continue
        if page.evaluate(_JS_FIND, r"^(Add to prompt|프롬프트에 추가)$"):
            item = page.evaluate(JS_ITEM, stem)
            if item:
                page.mouse.click(item["x"], item["y"]); page.wait_for_timeout(1500)
                click_text(page, r"^(Add to prompt|프롬프트에 추가)$", "Add to prompt", 2500)
    if not filled and not page.evaluate(_JS_FIND, slot_rx):
        filled = True
    if not filled:
        shot(f"{tag}_not_filled"); raise SystemExit(f"{tag} 시작 칸에 그림이 안 들어갔다 — 보내지 않았다")
    shot(f"{tag}_set")
    _log(f"  {tag} {label} 프레임 ← {img.name}")


def frames(project: Project, only: set[int] | None = None, headless: bool = False) -> int:
    import shutil
    cuts = project.load_cuts()
    targets = [c for c in cuts if c.get("engine") == "frames" and not c["done"] and (only is None or c["n"] in only)]
    if not targets:
        _log("[frames] 제출할 컷 없음 (cuts.json 에 \"engine\": \"frames\" 인 미생성 컷)"); return 0
    board = project.build / "board"
    def frame_spec(c: dict, key: str) -> Path | None:          # cuts.json "frames": {"start": "경로", "end": "경로"} (편 폴더 기준)
        v = (c.get("frames") or {}).get(key)
        return (project.dir / v).resolve() if v else None

    def start_img(n: int) -> Path | None:
        c = next((x for x in cuts if x["n"] == n), {})
        if frame_spec(c, "start"):
            return frame_spec(c, "start") if frame_spec(c, "start").exists() else None
        for d in (project.build / "board_clean", board):
            hit = sorted(d.glob(f"C{n:02d}.*")) if d.exists() else []
            if hit:
                return hit[0]
        return None
    nob = [c["n"] for c in targets if not start_img(c["n"])]
    if nob:
        raise SystemExit(f"보드 이미지가 없는 컷: {nob} — board 로 먼저 뽑고 사용자 확인을 받는다")
    bad = gate_violations(targets, cuts, project.style)
    if bad:
        for b in bad:
            print("★위반:", b)
        raise SystemExit("정본 검증 실패 — 제출하지 않았다 (크레딧 0)")
    _log(f"[frames] {len(targets)}컷 · 크레딧 약 {sum(CREDITS[c['len']] for c in targets)}: "
         + ", ".join(f"C{c['n']:02d}" for c in targets))
    dbg = project.build / "frames_submit"; dbg.mkdir(parents=True, exist_ok=True)
    sent = 0
    from playwright.sync_api import sync_playwright
    with sync_playwright() as pw:
        ctx = _context(pw, headless=headless)
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        shot = lambda n: page.screenshot(path=str(dbg / f"{n}.png"))
        try:
            page.goto(FLOW_URL, wait_until="domcontentloaded", timeout=90_000); page.wait_for_timeout(7000)
            dismiss_modals(page)
            if not logged_in(page):
                raise SystemExit("로그인이 안 돼 있다 — 먼저 `login` 을 실행하라")
            url = open_flow_project(page, project)
            for c in targets:
                L = int(c["len"]); tag = f"C{c['n']:02d}"
                page.keyboard.press("Escape"); page.wait_for_timeout(500)
                if not ensure_direct_mode(page, dbg):
                    raise SystemExit("직접 생성 모드(설정 칩)를 찾지 못했다")
                hit = find_settings(page); page.mouse.click(hit["x"], hit["y"]); page.wait_for_timeout(1500)
                click_text(page, TEXT["video_mode"], "동영상 모드", 1200)
                if not click_text(page, r"^(crop_free )?(프레임|Frames?)$", "프레임(Frames)", 1000):
                    shot(f"{tag}_no_frames_tab")
                page.keyboard.press("Escape"); page.wait_for_timeout(700)
                configure_video(page, L)
                src = start_img(c["n"])
                tmp = dbg / f"{tag}_start_{time.strftime('%H%M%S')}{src.suffix}"; shutil.copyfile(src, tmp)
                _set_start_frame(page, tmp, tag, shot)
                end = frame_spec(c, "end")
                if end:
                    if not end.exists():
                        raise SystemExit(f"{tag} 끝 장면 그림이 없다: {end} — 보내지 않았다")
                    tmp2 = dbg / f"{tag}_end_{time.strftime('%H%M%S')}{end.suffix}"; shutil.copyfile(end, tmp2)
                    _set_start_frame(page, tmp2, tag, shot, slot="end")
                ed = _editor(page); _clear_editor(page, ed)
                page.keyboard.type(c["prompt"], delay=0); page.wait_for_timeout(900)
                if len("".join(ed.inner_text().split())) < len("".join(c["prompt"].split())) * 0.95:
                    raise SystemExit(f"{tag} 프롬프트 입력이 잘렸다 — 보내지 않았다")
                hit = find_settings(page); page.mouse.click(hit["x"], hit["y"]); page.wait_for_timeout(1200)
                cr = page.evaluate(_JS_CREDIT, TEXT["credit"]); page.keyboard.press("Escape"); page.wait_for_timeout(700)
                if cr != CREDITS[L]:
                    shot(f"{tag}_credit"); raise SystemExit(f"{tag} 표시 크레딧 {cr} ≠ 예상 {CREDITS[L]} — 보내지 않았다")
                if not click_text(page, TEXT["send"], "전송", 3500):
                    raise SystemExit("전송 버튼을 못 찾았다")
                meta_path = project.build / f"submit_{L}s.json"
                meta = json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.exists() else {"url": url, "order": []}
                meta["url"] = url
                meta["order"] = [n for n in meta.get("order", []) if n != c["n"]] + [c["n"]]
                meta_path.write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")
                sent += 1
                _log(f"  {tag} 제출(보드→영상 · {cr} 크레딧) {sent}/{len(targets)}")
                page.wait_for_timeout(6000)
            _log("  마지막 전송이 Flow 에 닿도록 20초 기다린다"); page.wait_for_timeout(20_000)
        finally:
            ctx.close()
    _log(f"[frames] {sent}컷 제출 → 2~4분 뒤: collect {project.ref} <길이>")
    return sent


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


def _board_suspect(f: Path, ref: Path | None) -> tuple[str, str] | None:
    """받은 보드가 진짜 결과인지 확인 (2026-11 GV90 편 사고): 286px 썸네일을 받아 옴 · 참고 이미지를 거의 그대로 돌려줌."""
    try:
        from PIL import Image, ImageChops, ImageStat   # 맥 .venv 에는 numpy 가 없다 — PIL 만
    except Exception:
        return None
    im = Image.open(f)
    if max(im.size) < 1000:
        return ("small", f"해상도가 {im.size[0]}×{im.size[1]} 뿐(썸네일을 받은 것 같다)")
    if ref and ref.exists():
        r = Image.open(ref).convert("L")
        if abs(r.size[0] / r.size[1] - im.size[0] / im.size[1]) < 0.05:
            d = ImageChops.difference(im.convert("L").resize((192, 344)), r.resize((192, 344)))
            if ImageStat.Stat(d).mean[0] < 12:
                return ("refcopy", "참고 이미지와 거의 같다(참고 이미지를 받았거나 모델이 그대로 베낌)")
    return None


# 보드 이미지 모델 (2026-11 GV90 편): 기본은 0크레딧 Nano Banana 2.1 — 창에 무엇이 골라져 있든 매번 맞춘다.
# 'pro' 는 공학·복잡한 구조용 시험. 장당 크레딧은 아래 안전장치(--max-credit)가 지킨다.
IMAGE_MODELS = {"2.1": r"Nano Banana 2\.1", "pro": r"Nano Banana Pro"}


def configure_image(page, image_model: str = "2.1"):
    """설정 칩을 열어 '이미지 · 9:16 · x1 · 모델' 로 맞추고 (칩, 장당 크레딧, 모델)을 돌려준다. 어긋나면 SystemExit."""
    hit = find_settings(page)
    if not hit:
        raise SystemExit("설정 칩을 못 찾았다 — 보내지 않았다")
    page.mouse.click(hit["x"], hit["y"]); page.wait_for_timeout(1200)
    click_text(page, TEXT["image_mode"], "이미지 모드", 1500)
    click_text(page, TEXT["portrait"], "세로 9:16", 700)
    click_text(page, TEXT["count1"], "출력 1개", 900)
    want = IMAGE_MODELS[image_model]
    m = page.evaluate(_JS_FIND_ARIA, TEXT["model_aria"])
    if m and not re.search(want, m["text"]):
        _log(f"  이미지 모델 {m['text']} → {want.replace(chr(92), '')} 로 바꾼다")
        page.mouse.click(m["x"], m["y"]); page.wait_for_timeout(1200)
        click_text(page, r"^\W*" + want + r"\b", want.replace(chr(92), ''), 1500)
        page.wait_for_timeout(800)
    m = page.evaluate(_JS_FIND_ARIA, TEXT["model_aria"])
    model = m["text"] if m else "?"
    if not re.search(want, model):
        page.keyboard.press("Escape")
        raise SystemExit(f"이미지 모델을 {want.replace(chr(92), '')} 로 못 바꿨다 (지금: {model}) — 보내지 않았다")
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


# ── board 참고 이미지 (2026-11 경복궁 시험) — cuts.json 컷에 "ref": "refs/layout.png"(편 폴더 기준)
# 프롬프트 상자 근처의 '이미지 추가' 버튼 → 'Upload media' → 파일 → (처음 한 번 사용자 동의) → 프롬프트에 붙는다.
# Flow 이미지 모드의 이 버튼은 아직 실측 전이다 — 못 찾으면 프롬프트 상자 주변 버튼 목록·화면을 남기고 그 컷은 보내지 않는다.

_JS_PROMPT_BUTTONS = """
() => {
  // 화면 아래쪽(프롬프트 상자 둘레) 버튼만 — 머리글의 add(새 프로젝트 등)와 헷갈리지 않게
  const vis = e => { const r = e.getBoundingClientRect(); return r.width > 8 && r.height > 8 && r.top > innerHeight * 0.55 && r.bottom < innerHeight + 2; };
  return [...document.querySelectorAll("button,[role=button]")].filter(vis).map(e => {
    const r = e.getBoundingClientRect();
    return { text: (e.innerText || "").replace(/\\s+/g, " ").trim().slice(0, 40), aria: e.getAttribute("aria-label") || "",
             x: Math.round(r.x + r.width / 2), y: Math.round(r.y + r.height / 2) };
  });
}
"""
_ADD_REF_RX = re.compile(r"^(add|add_2|add_circle|add_photo_alternate|attach_file|image|photo|이미지|Add image|Add media|"
                         r"이미지 추가|미디어 추가|재료|Ingredients?)$|add.*(image|media|이미지|미디어)|(이미지|미디어).*(추가|업로드)|"
                         r"ingredient|reference|참조|upload|업로드", re.I)


def pick_add_ref_button(btns: list[dict]) -> dict | None:
    """프롬프트 상자 둘레 버튼에서 '이미지 추가'로 보이는 것 하나 (순수 로직). aria 우선, 그다음 아이콘 글자. 전송(arrow_forward)·설정 칩 제외."""
    ok = [b for b in btns if not re.search(r"arrow_forward|설정|Settings|crop_|Nano|Video|동영상", (b.get("text", "") + " " + b.get("aria", "")), re.I)]
    for key in ("aria", "text"):
        hit = [b for b in ok if b.get(key) and _ADD_REF_RX.search(b[key])]
        if hit:
            return sorted(hit, key=lambda b: b.get("x", 0))[0]
    return None


_JS_PROMPT_BOX = """
() => {
  // 프롬프트 상자(편집 칸을 품은 큰 상자) 안의 붙은 재료 그림(chip)과 지우기 버튼
  const ed = document.querySelector('[contenteditable="true"]');
  if (!ed) return null;
  let box = ed;
  for (let i = 0; i < 8 && box.parentElement; i++) {
    box = box.parentElement;
    if (box.getBoundingClientRect().width > 450 && box.querySelector('button')) break;
  }
  const chips = [...box.querySelectorAll("img")].map(i => i.currentSrc || i.src).filter(Boolean);
  const clears = [...box.querySelectorAll("button")].filter(b => {
    const t = (b.innerText || "").trim(), a = b.getAttribute("aria-label") || "";
    return t === "close" || /remove|clear|delete|삭제|제거|지우기/i.test(a);
  }).map(b => { const r = b.getBoundingClientRect(); return {x: Math.round(r.x + r.width / 2), y: Math.round(r.y + r.height / 2), aria: b.getAttribute("aria-label") || ""}; });
  return { chips, clears };
}
"""

_JS_PCT = """
() => [...document.querySelectorAll("div,span,p")].some(e => {
  const r = e.getBoundingClientRect(); if (r.width < 4 || r.height < 4) return false;
  return /^\\d{1,3}%$/.test((e.innerText || "").trim()); })
"""

_JS_PICK_ITEM = """
([stem, pre]) => {
  // 고르기 창 안의 항목: 파일 이름으로, 없으면 전에 없던 그림으로
  const vis = e => { const r = e.getBoundingClientRect(); return r.width > 30 && r.height > 30 && r.top >= 0 && r.top < innerHeight; };
  let el = [...document.querySelectorAll("button,[role=button],[role=option],li,div")].filter(vis)
    .filter(e => (e.innerText || "").trim().startsWith(stem) && (e.innerText || "").length < 80)
    .sort((x, y) => x.getBoundingClientRect().height - y.getBoundingClientRect().height)[0];
  if (!el) {
    const seen = new Set(pre);
    el = [...document.querySelectorAll("[role=dialog] img, dialog img")].filter(vis).find(i => !seen.has(i.currentSrc || i.src));
  }
  if (!el) return null;
  const r = el.getBoundingClientRect();
  const im = el.tagName === "IMG" ? el : el.querySelector("img");
  return {x: Math.round(r.x + r.width / 2), y: Math.round(r.y + r.height / 2), text: (el.innerText || el.alt || "").trim().slice(0, 40),
          src: im ? (im.currentSrc || im.src) : ""};
}
"""


def clear_ingredients(page, tag: str) -> None:
    """프롬프트 상자에 남아 있는 재료 그림을 지운다(이전 컷·이전 실행에서 붙은 것이 다음 컷을 오염시키지 않게)."""
    for _ in range(4):
        st = page.evaluate(_JS_PROMPT_BOX)
        if not st or not st["chips"]:
            return
        if not st["clears"]:
            _log(f"  {tag} 프롬프트 상자에 재료 그림 {len(st['chips'])}장이 남아 있는데 지우기 버튼을 못 찾았다")
            return
        b = st["clears"][0]; page.mouse.click(b["x"], b["y"]); page.wait_for_timeout(700)
    _log(f"  {tag} 남아 있던 재료 그림을 지웠다")


def _attach_ref(page, img: Path, tag: str, debug_dir: Path) -> set:
    """참고 이미지를 프롬프트 상자에 붙이고, 붙은 그림 주소(들)를 돌려준다 — 결과 이미지로 잘못 받지 않게 board 가 제외한다.
    2026-11 첫 시도: '+'(aria 'Add ingredients to the prompt box') → 올리기는 됐지만 올라가는 중(46%)에 '프롬프트에 추가'를 눌러
    이미 있던 다른 보드 그림(C02)이 붙었고, 다 올라간 스케치가 결과로 잡혔다 → 다 올라갈 때까지 기다리고, 파일 이름/새 그림으로 고르고, 붙은 그림을 확인한다."""
    shot = lambda n: page.screenshot(path=str(debug_dir / f"{n}.png"))
    clear_ingredients(page, tag)
    pre = [i["src"] for i in page.evaluate(_JS_IMGS)]
    btns = page.evaluate(_JS_PROMPT_BUTTONS)
    (debug_dir / f"{tag}_prompt_buttons.json").write_text(json.dumps(btns, ensure_ascii=False, indent=1), encoding="utf-8")
    hit = pick_add_ref_button(btns)
    if not hit:
        shot(f"{tag}_no_add_ref")
        raise SystemExit(f"{tag} 참고 이미지 넣는 버튼을 못 찾았다 — {debug_dir.name}/{tag}_prompt_buttons.json 을 보고 고친다 (보내지 않았다)")
    _log(f"  {tag} 참고 이미지 버튼: {hit.get('aria') or hit.get('text')}")
    chooser = None
    try:                                                  # 버튼이 곧바로 파일 선택 창을 여는 경우
        with page.expect_file_chooser(timeout=2500) as fc:
            page.mouse.click(hit["x"], hit["y"])
        chooser = fc.value
    except Exception:
        page.wait_for_timeout(1200)
    reused = None
    if chooser is None:                                   # 고르기 창이 떴다 — 이 프로젝트에 이미 올린 같은 파일이 있으면 그걸 고른다(2026-11 경복궁 C04)
        shot(f"{tag}_picker_open")
        item = page.evaluate(_JS_PICK_ITEM, [img.stem[:16], []])
        if item and item.get("text", "").startswith(img.stem[:16]):
            _log(f"  {tag} 이미 올린 '{item['text']}' 를 고름 (다시 올리지 않음)")
            page.mouse.click(item["x"], item["y"]); page.wait_for_timeout(1200)
            click_text(page, r"^(Add to prompt|프롬프트에 추가)$", "Add to prompt", 2500)
            reused = item
    if chooser is None and reused is None:                # 없으면 '업로드'
        up = page.evaluate(_JS_FIND, r"Upload media|Upload image|미디어 업로드|이미지 업로드|^(upload )?(Upload|업로드)$")
        if not up:
            (debug_dir / f"{tag}_after_click_buttons.json").write_text(
                json.dumps(page.evaluate(_JS_PANEL_ITEMS), ensure_ascii=False, indent=1), encoding="utf-8")
            raise SystemExit(f"{tag} 업로드 버튼을 못 찾았다 — {debug_dir.name}/{tag}_picker_open.png (보내지 않았다)")
        try:
            with page.expect_file_chooser(timeout=10_000) as fc:
                page.mouse.click(up["x"], up["y"])
            chooser = fc.value
        except Exception:
            shot(f"{tag}_no_chooser")
            raise SystemExit(f"{tag} 파일 선택 창이 안 떴다 — {debug_dir.name}/{tag}_no_chooser.png (보내지 않았다)")
    if chooser is not None:
        chooser.set_files(str(img))
    page.wait_for_timeout(2500)
    if page.evaluate(_JS_FIND, r"^I agree$|^동의$"):
        shot(f"{tag}_rights")
        print("\n★ Flow 창에 'Rights to use this image' 확인이 떴습니다. 읽고 직접 'I agree'(동의)를 눌러 주세요(3분 기다림).\n", flush=True)
        for _ in range(90):
            page.wait_for_timeout(2000)
            if not page.evaluate(_JS_FIND, r"^I agree$|^동의$"):
                break
        else:
            raise SystemExit("동의 창이 닫히지 않았다 — 보내지 않았다")
    calm = 0                                              # 다 올라갈 때까지 (화면 어디든 'NN%' 가 두 번 연속 없을 때)
    for _ in range(120):
        page.wait_for_timeout(1000)
        calm = calm + 1 if not page.evaluate(_JS_PCT) else 0
        if calm >= 2:
            break
    shot(f"{tag}_after_upload")
    st = page.evaluate(_JS_PROMPT_BOX) or {"chips": []}
    new_chips = [c for c in st["chips"] if c not in pre]
    if not new_chips and page.evaluate(_JS_FIND, r"^(Add to prompt|프롬프트에 추가)$"):
        item = page.evaluate(_JS_PICK_ITEM, [img.stem[:16], pre])
        if item:
            _log(f"  {tag} 고르기 창에서 선택: {item.get('text') or '새 그림'}")
            page.mouse.click(item["x"], item["y"]); page.wait_for_timeout(1200)
        click_text(page, r"^(Add to prompt|프롬프트에 추가)$", "Add to prompt", 2500)
    if page.evaluate(_JS_FIND, r"^(Add to prompt|프롬프트에 추가)$"):
        page.keyboard.press("Escape"); page.wait_for_timeout(600)
    shot(f"{tag}_ref_set")
    st = page.evaluate(_JS_PROMPT_BOX) or {"chips": []}
    new_chips = [c for c in st["chips"] if c not in pre]
    if reused and len(st["chips"]) == 1 and not new_chips:
        new_chips = list(st["chips"])                     # 이미 있던 그림을 골랐으니 '새 그림'이 아닐 수 있다 — 한 장만 붙었으면 통과
    if len(st["chips"]) != 1 or not new_chips:
        (debug_dir / f"{tag}_ref_state.json").write_text(json.dumps({"pre": pre, "box": st}, ensure_ascii=False, indent=1), encoding="utf-8")
        raise SystemExit(f"{tag} 프롬프트 상자에 붙은 그림이 방금 올린 참고 이미지가 아니다(붙은 {len(st['chips'])}장, 새 것 {len(new_chips)}장) — "
                         f"{debug_dir.name}/{tag}_ref_set.png 확인 (보내지 않았다)")
    _log(f"  {tag} 참고 이미지 ← {img.name} (프롬프트 상자에 붙은 것 확인)")
    return set(new_chips) | {i["src"] for i in page.evaluate(_JS_IMGS)} - set(pre)


def board(project: Project, only: set[int] | None = None, max_credit: int | None = None,
          redo: bool = False, headless: bool = False, wait_sec: int = 180, image_model: str = "2.1") -> int:
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
    bad = gate_violations(targets, cuts, project.style)
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
            meta["url"] = open_flow_project(page, project)
            page.keyboard.press("Escape"); page.wait_for_timeout(500)
            if not ensure_direct_mode(page, project.build):
                raise SystemExit("직접 생성 모드(설정 칩)를 찾지 못했다 — guides/flow-ui.md 의 2026-10 메모를 보라")

            # 설정 패널을 연 채로 화면을 남겨 둔다 (크레딧·모델 확인용)
            chip, credit, model = configure_image(page, image_model)
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
                ref_srcs: set = set()
                if c.get("ref"):                                 # 참고 이미지를 먼저 붙이고, 그 뒤에 '전송 전' 목록을 잰다
                    rp = (project.dir / c["ref"]).resolve()
                    if not rp.exists():
                        _log(f"  C{c['n']:02d} 참고 이미지가 없다: {c['ref']} — 건너뜀"); continue
                    ref_srcs = _attach_ref(page, rp, f"C{c['n']:02d}", out)
                else:
                    clear_ingredients(page, f"C{c['n']:02d}")
                before = [i["src"] for i in page.evaluate(_JS_IMGS)] + list(ref_srcs)
                ed = _editor(page)
                _clear_editor(page, ed)
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
                # 'change only …' 판(같은 시점에서 문 상태만 바꾼 시작·끝 장면)은 원래 참고 이미지와 비슷하다 → 베낌 검사는 빼고 크기만 본다
                same_view = "change only what is described here" in c["prompt"]
                bad = _board_suspect(f, None if same_view or not c.get("ref") else project.dir / c["ref"])
                if bad:
                    sus = f.with_name(f"C{c['n']:02d}_suspect_{bad[0]}{f.suffix}")
                    f.rename(sus); got.remove(c["n"])
                    _log(f"  ★C{c['n']:02d} 결과가 의심스럽다 — {bad[1]} → {sus.name} 로 치웠다 (다시 뽑을 것)")
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
