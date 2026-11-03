# -*- coding: utf-8 -*-
"""Flow 프로젝트 격자를 위에서부터 스크롤하며 화면을 찍는다(진단용, 크레딧 0) — 2026-11 GV90 편: 회수가 C01~C09 를 못 찾을 때.
  .venv/bin/python tools/flow_peek.py <편> [장수=8]
결과: projects/<편>/build/flow_peek/peek_##.png + texts.json(실패·오류 문구 후보)
"""
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from flowmaker.project import Project
from flowmaker import flow_driver as fd

p = Project(sys.argv[1])
n = int(sys.argv[2]) if len(sys.argv) > 2 and sys.argv[2].isdigit() else 8
out = p.build / "flow_peek"; out.mkdir(parents=True, exist_ok=True)
from playwright.sync_api import sync_playwright
with sync_playwright() as pw:
    ctx = fd._context(pw, headless=False)
    page = ctx.pages[0] if ctx.pages else ctx.new_page()
    page.set_viewport_size({"width": 1400, "height": 1000})
    page.goto(p.flow_url, wait_until="domcontentloaded", timeout=90_000)
    page.wait_for_timeout(9000)
    if "--videos" in sys.argv:                    # 왼쪽 메뉴 'Videos' — 영상만 모아 본다 (실패·생성 중 카드 확인)
        fd.click_text(page, r"^(Videos|동영상)$", "Videos 메뉴", 3000)
        page.wait_for_timeout(4000)
    texts = []
    for i in range(n):
        page.screenshot(path=str(out / (("vid_" if "--videos" in sys.argv else "peek_") + f"{i:02d}.png")))
        texts += page.evaluate("""() => [...document.querySelectorAll('div,span,p')].map(e => (e.innerText||'').trim())
            .filter(t => t && t.length < 120 && /(fail|error|wrong|couldn|unable|실패|오류|생성하지|policy|정책|retry|다시 시도)/i.test(t))""")
        page.evaluate(fd._JS_SCROLL_MORE, fd.TEXT["thumb_alt"])
        page.wait_for_timeout(1500)
    (out / "texts.json").write_text(json.dumps(sorted(set(texts)), ensure_ascii=False, indent=1), encoding="utf-8")
    print("thumbs:", len(page.evaluate(fd._JS_THUMBS, fd.TEXT["thumb_alt"])), "→", out)
    ctx.close()
