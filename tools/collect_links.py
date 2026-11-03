# -*- coding: utf-8 -*-
"""Flow 상세 주소(/edit/…)로 클립을 찾아 받는다 (크레딧 0) — 2026-11 GV90 편: 격자 썸네일로 안 잡히는 클립(C01~C09).
  .venv/bin/python tools/collect_links.py <편>                 # 격자를 스크롤하며 /edit/ 링크를 모두 모아 확인
  .venv/bin/python tools/collect_links.py <편> <주소> [<주소>…]  # 주어진 주소만 확인
상세 화면의 프롬프트로 컷을 맞추고, 아직 clips/ 에 없는 컷이면 내려받는다. 결과표: build/collect_links.json
"""
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from flowmaker.project import Project
from flowmaker import flow_driver as fd

p = Project(sys.argv[1]); urls = [a for a in sys.argv[2:] if a.startswith("http")]
prompts = {c["n"]: c["prompt"] for c in p.load_cuts()}
need = {c["n"] for c in p.load_cuts() if c.get("engine") != "made" and not p.clip(c["n"]).exists()}
print("아직 없는 컷:", sorted(need))
JS_LINKS = """() => [...document.querySelectorAll('a[href*="/edit/"]')].map(a => a.href)"""
rows = []
from playwright.sync_api import sync_playwright
with sync_playwright() as pw:
    ctx = fd._context(pw, headless=False)
    page = ctx.pages[0] if ctx.pages else ctx.new_page()
    page.set_viewport_size({"width": 800, "height": 1000})
    if not urls and "--tall" in sys.argv:
        # 사용자 아이디어(2026-11): 창을 아주 크게 하면 격자가 한 번에 다 그려진다 → 스크롤 없이 영상 썸네일을 전부 본다
        JS_VIS = """(pattern) => { const rx = new RegExp(pattern);
            return [...document.querySelectorAll('img')].filter(i => rx.test(i.alt||'')).map(i => {
              const r = i.getBoundingClientRect(); return {src:(i.currentSrc||i.src||'').split('?')[0], x:Math.round(r.x+r.width/2), y:Math.round(r.y+r.height/2)}; }); }"""
        page.set_viewport_size({"width": 1400, "height": 9000})
        page.goto(p.flow_url, wait_until="domcontentloaded", timeout=90_000); page.wait_for_timeout(12000)
        vis = page.evaluate(JS_VIS, fd.TEXT["thumb_alt"])
        print(f"큰 창에서 보이는 동영상 썸네일 {len(vis)}개")
        for i, t in enumerate(vis):
            if i:
                page.goto(p.flow_url, wait_until="domcontentloaded", timeout=90_000); page.wait_for_timeout(9000)
                cur = {v["src"]: v for v in page.evaluate(JS_VIS, fd.TEXT["thumb_alt"])}
                if t["src"] not in cur: print("  못 찾음:", i); continue
                t = cur[t["src"]]
            page.mouse.click(t["x"], t["y"])
            for _ in range(20):
                page.wait_for_timeout(500)
                if "/edit/" in page.url: break
            if "/edit/" in page.url and page.url not in urls:
                urls.append(page.url); print(f"  주소 {len(urls)}: {page.url}")
        page.set_viewport_size({"width": 800, "height": 1000})   # 상세 화면에 <video> 가 생기는 폭으로 되돌린다
    elif not urls and "--walk" in sys.argv:
        # 상세 화면에서 화살표 키로 다음 항목을 넘겨 가며 전부 훑는다(격자 스크롤·뒤로가기 없이) — 2026-11 GV90 편
        page.goto(p.flow_url, wait_until="domcontentloaded", timeout=90_000); page.wait_for_timeout(9000)
        th = fd._thumbs(page, 1)
        page.mouse.click(th[0]["x"], th[0]["y"])
        for _ in range(20):
            page.wait_for_timeout(500)
            if "/edit/" in page.url: break
        key = sys.argv[sys.argv.index("--walk") + 1] if len(sys.argv) > sys.argv.index("--walk") + 1 and not sys.argv[sys.argv.index("--walk") + 1].startswith("http") else "ArrowRight"
        visited, same = [], 0
        for step in range(260):
            u = page.url
            if u not in visited:
                visited.append(u); same = 0
                d = None
                for _ in range(12):
                    page.wait_for_timeout(400); d = page.evaluate(fd._JS_DETAIL)
                    if d["src"]: break
                if d and d["src"]:
                    cut = fd.match_prompts(prompts, [d["text"]], prefer=need)[0]
                    row = {"url": u, "cut": cut}
                    if cut in need:
                        r = ctx.request.get(d["src"], timeout=180_000)
                        if r.ok:
                            p.clip(cut).write_bytes(r.body()); need.discard(cut); row["saved"] = True
                    rows.append(row); print(step, row)
                    if not need: break
            else:
                same += 1
                if same >= 3: print("더 넘어가지 않는다 — 끝"); break
            page.keyboard.press(key); page.wait_for_timeout(1200)
        print(f"훑은 항목 {len(visited)}개")
        urls = []
    elif not urls:
        # 격자는 보이는 부분만 그린다 → 화면을 내려가며 아직 안 연 '동영상 썸네일'을 하나씩 눌러 /edit/ 주소를 모은다
        JS_VIS = """(pattern) => { const rx = new RegExp(pattern);
            return [...document.querySelectorAll('img')].filter(i => rx.test(i.alt||'')).map(i => {
              const r = i.getBoundingClientRect(); return {src:(i.currentSrc||i.src||'').split('?')[0], x:Math.round(r.x+r.width/2), y:Math.round(r.y+r.height/2)}; }); }"""
        page.goto(p.flow_url, wait_until="domcontentloaded", timeout=90_000); page.wait_for_timeout(9000)
        done, stall = set(), 0
        for _ in range(200):
            vis = [t for t in page.evaluate(JS_VIS, fd.TEXT["thumb_alt"]) if 0 < t["y"] < 950]
            new = [t for t in vis if t["src"] not in done]
            if not new:
                page.evaluate(fd._JS_SCROLL_MORE, fd.TEXT["thumb_alt"]); page.wait_for_timeout(1200)
                stall += 1
                if stall >= 12: break
                continue
            stall = 0
            t = new[0]; done.add(t["src"])
            page.mouse.click(t["x"], t["y"])
            for _ in range(20):
                page.wait_for_timeout(500)
                if "/edit/" in page.url: break
            if "/edit/" in page.url and page.url not in urls:
                urls.append(page.url); print(f"  주소 {len(urls)}: {page.url}")
            page.go_back(); page.wait_for_timeout(4000)
        print(f"/edit/ 주소 {len(urls)}개 (동영상 썸네일 {len(done)}개를 열어 봄)")
    for u in urls:
        page.goto(u, wait_until="domcontentloaded", timeout=90_000)
        d = None
        for _ in range(40):
            page.wait_for_timeout(500); d = page.evaluate(fd._JS_DETAIL)
            if d["src"]: break
        if not d or not d["src"]:
            rows.append({"url": u, "kind": "image/없음"}); continue
        cut = fd.match_prompts(prompts, [d["text"]], prefer=need)[0]
        row = {"url": u, "cut": cut, "dur": d.get("dur")}
        if cut in need:
            r = ctx.request.get(d["src"], timeout=180_000)
            if r.ok:
                p.clip(cut).write_bytes(r.body()); need.discard(cut); row["saved"] = True
        rows.append(row); print(row)
    ctx.close()
(p.build / "collect_links.json").write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
print("남은 컷:", sorted(need))
