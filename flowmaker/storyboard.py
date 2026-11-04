# -*- coding: utf-8 -*-
"""스토리보드 시트 — `board` 가 뽑은 대표 이미지(build/board/C##.*)를 컷 정보와 함께 HTML 한 장으로 묶는다.

projects/<p>/storyboard.html  (이미지를 base64 로 품어 파일 하나로 열린다)
    컷마다: 이미지 · 컷 번호 · 그림체 · 생성 길이/필요 길이 · 덮는 자막 문장 · desc · 판정(통과/다시 뽑는 중) · 메모
    메모는 build/board/notes.json ({"5": "집들이 서양식으로 나왔다 …"}) 이 있으면 붙인다.

왜: 영상 크레딧을 쓰기 전에 사용자가 컷 20장을 한눈에 보고 고칠 곳을 고르게 한다(2026-10 온돌 편에서 도입).
"""
from __future__ import annotations

import base64
import html
import io
import json

from .project import CREDITS, Project

KIND_KO = {"diag": "점토 다이어그램", "hist": "시대 재현 실사", "real": "현대 실사"}


def _thumb_b64(path) -> str:
    from PIL import Image
    im = Image.open(path).convert("RGB")
    im.thumbnail((420, 760))
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=82)
    return base64.b64encode(buf.getvalue()).decode()


def run(project: Project, redo: set[int] | None = None) -> str:
    redo = redo or set()
    cuts = project.load_cuts()
    subs = project.lines(project.subtitles)
    board = project.build / "board"
    notes_path = board / "notes.json"
    notes = json.loads(notes_path.read_text(encoding="utf-8")) if notes_path.exists() else {}
    cards, missing = [], []
    for c in cuts:
        n = c["n"]
        imgs = sorted(board.glob(f"C{n:02d}.*"), key=lambda p: p.stat().st_mtime)
        imgs = [p for p in imgs if p.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp")]
        if not imgs:
            missing.append(n)
            img = '<div class="noimg">이미지 없음</div>'
        else:
            img = f'<img src="data:image/jpeg;base64,{_thumb_b64(imgs[-1])}" alt="C{n:02d}">'
        lines = "".join(f'<p class="line"><span class="sn">{s}</span>{html.escape(subs[s - 1])}</p>'
                        for s in c["sentences"])
        need = f" · 필요 {c['need']:.1f}초" if c.get("need") else ""
        st, badge = ("redo", "다시 뽑는 중") if n in redo else ("ok", "통과")
        note = notes.get(str(n), "")
        cards.append(f'''<article class="card {st}">{img}
  <div class="meta"><b>C{n:02d}</b><span class="k {c['kind']}">{KIND_KO[c['kind']]}</span><span class="len">{c['len']}초{need}</span><span class="badge">{badge}</span></div>
  {lines}<p class="desc">{html.escape(c.get('desc', ''))}</p>{('<ul class="must">' + ''.join('<li>' + html.escape(m) + '</li>' for m in c.get('must') or []) + '</ul>') if c.get('must') else ''}{f'<p class="note">{html.escape(note)}</p>' if note else ''}
</article>''')
    total = sum(c["len"] for c in cuts)
    credit = sum(CREDITS[c["len"]] for c in cuts)
    page = f'''<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html.escape(project.name)} 스토리보드</title><style>
:root{{--bg:#f4f3f0;--card:#fff;--ink:#1d1d1b;--mute:#6b6a66;--line:#e2e0db;--ok:#2f7d4f;--redo:#b5541c;--diag:#55606e;--hist:#8a6a3a;--real:#3d6f8f}}
@media (prefers-color-scheme:dark){{:root:not([data-theme="light"]){{--bg:#161615;--card:#21201f;--ink:#ecebe7;--mute:#a09e98;--line:#34332f;--ok:#5fbf86;--redo:#f08a4b}}}}
:root[data-theme="dark"]{{--bg:#161615;--card:#21201f;--ink:#ecebe7;--mute:#a09e98;--line:#34332f;--ok:#5fbf86;--redo:#f08a4b}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--ink);font:15px/1.5 -apple-system,"Apple SD Gothic Neo","Noto Sans KR",sans-serif}}
header{{padding:20px 16px 8px;max-width:1280px;margin:auto}}h1{{font-size:22px;margin:0 0 4px}}header p{{margin:0;color:var(--mute)}}
main{{display:grid;grid-template-columns:repeat(auto-fill,minmax(230px,1fr));gap:14px;padding:12px 16px 40px;max-width:1280px;margin:auto}}
.card{{background:var(--card);border:1px solid var(--line);border-radius:12px;overflow:hidden}}.card.redo{{border-color:var(--redo);border-width:2px}}
.card img,.noimg{{width:100%;display:block;aspect-ratio:9/16;object-fit:cover;background:#888}}.noimg{{display:flex;align-items:center;justify-content:center;color:#fff}}
.meta{{display:flex;flex-wrap:wrap;gap:6px;align-items:center;padding:10px 12px 4px;font-size:13px}}.meta b{{font-size:15px}}
.k{{padding:1px 7px;border-radius:99px;color:#fff;font-size:12px}}.k.diag{{background:var(--diag)}}.k.hist{{background:var(--hist)}}.k.real{{background:var(--real)}}
.len{{color:var(--mute)}}.badge{{margin-left:auto;font-weight:600;color:var(--ok)}}.redo .badge{{color:var(--redo)}}
.line{{margin:4px 12px;font-size:14px}}.sn{{display:inline-block;min-width:20px;color:var(--mute);font-size:12px}}
.desc{{margin:6px 12px 10px;color:var(--mute);font-size:12.5px}}.must{{margin:0 12px 10px;padding-left:18px;font-size:12.5px}}.must li{{margin:2px 0}}.note{{margin:0 12px 12px;padding:8px 10px;border-radius:8px;background:color-mix(in srgb,var(--redo) 12%,transparent);font-size:13px}}
</style></head><body><header><h1>{html.escape(project.name)} · 스토리보드</h1>
<p>{len(cuts)}컷 · 영상 생성 길이 합 {total}초 · 예상 {credit}크레딧 · 대표 이미지는 Flow 이미지 모드로 뽑은 것이라 영상의 질감과는 다를 수 있다. 오른쪽 아래 별 마크는 조립 때 지워진다.</p></header>
<main>{"".join(cards)}</main></body></html>'''
    out = project.dir / "storyboard.html"
    out.write_text(page, encoding="utf-8")
    print(f"스토리보드 {len(cuts)}컷 → {out.relative_to(project.dir.parent.parent)}" +
          (f" · 이미지 없는 컷 {['C%02d' % n for n in missing]}" if missing else ""))
    return str(out)
