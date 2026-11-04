# -*- coding: utf-8 -*-
"""진단(크레딧 0): Flow 격자에서 img alt 종류·개수와 재생 아이콘이 붙은 카드 수를 센다 — 썸네일 alt 가 바뀌었는지 확인용.
  .venv/bin/python tools/flow_alts.py <편>"""
import json, sys, collections
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from flowmaker.project import Project
from flowmaker import flow_driver as fd
p = Project(sys.argv[1])
from playwright.sync_api import sync_playwright
alts = collections.Counter(); samples = {}
with sync_playwright() as pw:
    ctx = fd._context(pw, headless=False); page = ctx.pages[0] if ctx.pages else ctx.new_page()
    page.set_viewport_size({"width": 800, "height": 1000})
    page.goto(p.flow_url, wait_until="domcontentloaded", timeout=90_000); page.wait_for_timeout(9000)
    seen = set()
    for step in range(40):
        items = page.evaluate("""() => [...document.querySelectorAll('img')].map(i => {
            const card = i.closest('a,button,[role=button],div');
            const txt = card ? (card.innerText||'').slice(0,40) : '';
            return {src:(i.currentSrc||i.src||'').split('?')[0].slice(-60), alt:i.alt||'', w:i.naturalWidth, txt, aria:(card&&card.getAttribute('aria-label'))||''};})""")
        for it in items:
            k = it['src']
            if k in seen: continue
            seen.add(k); alts[it['alt']] += 1; samples.setdefault(it['alt'], it)
        page.evaluate(fd._JS_SCROLL_MORE, fd.TEXT["thumb_alt"]); page.wait_for_timeout(1000)
    ctx.close()
out = {"alts": alts.most_common(), "samples": samples}
(p.build / "flow_alts.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
print(json.dumps(alts.most_common(), ensure_ascii=False))
