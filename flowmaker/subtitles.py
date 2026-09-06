# -*- coding: utf-8 -*-
"""자막 PNG — 흰 글자 + 검은 외곽선, 박스·그림자 없음, 하단 82% 기준선, 2줄 상한.

수치 근거 (세로 쇼츠 모바일 실측, 720×1280 환산)
    채널명 상단이 85.5% → 자막 하단은 82.0%(y=1050)까지만 내린다
    우측 버튼(좋아요·댓글·공유)이 x 87%부터 → 글줄 폭 상한 530px
    글자 높이 ≈ 48px → 폰트 44

폰트
    Pretendard-Black (SIL Open Font License). `doctor` 가 ~/.flowmaker/fonts/ 에 내려받는다.
    다른 폰트를 쓰려면 .env 에 SUBTITLE_FONT=/절대/경로.ttf
"""
from __future__ import annotations

import hashlib
import urllib.request
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from . import env
from .project import Project

W, H = 720, 1280
SIZE = 44
STROKE = 7
BASE_Y = 1050
LINE_GAP = 12
MAXW = 530

FONT_URL = ("https://raw.githubusercontent.com/orioncactus/pretendard/v1.3.9/"
            "packages/pretendard/dist/public/static/Pretendard-Black.otf")
FONT_SHA256 = "94628b0bcea8936b6e5c30d98d685eb9bbaffb0fe2ed255542ecc656c248e021"


def font_path() -> Path:
    custom = env.get("SUBTITLE_FONT")
    if custom:
        p = Path(custom).expanduser()
        if not p.exists():
            raise SystemExit(f"SUBTITLE_FONT 경로가 없다: {p}")
        return p
    p = env.home() / "fonts" / "Pretendard-Black.otf"
    if not p.exists():
        raise SystemExit("자막 폰트가 없다 — `python -m flowmaker doctor` 가 내려받는다")
    return p


def ensure_font() -> Path:
    if env.get("SUBTITLE_FONT"):
        return font_path()
    p = env.home() / "fonts" / "Pretendard-Black.otf"
    if not p.exists():
        p.parent.mkdir(parents=True, exist_ok=True)
        print(f"자막 폰트 내려받는 중 → {p}")
        tmp = p.with_suffix(".part")
        urllib.request.urlretrieve(FONT_URL, tmp)
        digest = hashlib.sha256(tmp.read_bytes()).hexdigest()
        if digest != FONT_SHA256:
            tmp.unlink(missing_ok=True)
            raise SystemExit("내려받은 폰트의 체크섬이 다르다 — 네트워크나 업스트림 문제. "
                             "직접 Pretendard-Black.otf 를 받아 .env 의 SUBTITLE_FONT 로 지정하라")
        tmp.rename(p)
    return p


def wrap(text: str, draw, f) -> list[str]:
    lines, cur = [], ""
    for w in text.split():
        t = (cur + " " + w).strip()
        if draw.textlength(t, font=f) <= MAXW or not cur:
            cur = t
        else:
            lines.append(cur); cur = w
    if cur:
        lines.append(cur)
    if len(lines) > 2:
        raise ValueError(f"자막이 {len(lines)}줄이다 — timing 단계의 분할이 안 먹었다: {text}")
    return lines


def render(text: str, out: Path, f=None) -> None:
    f = f or ImageFont.truetype(str(font_path()), SIZE)
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    lines = wrap(text, d, f)
    lh = SIZE + LINE_GAP
    top = BASE_Y - len(lines) * lh + LINE_GAP
    for i, ln in enumerate(lines):
        tw = d.textlength(ln, font=f)
        d.text(((W - tw) / 2, top + i * lh), ln, font=f, fill=(255, 255, 255, 255),
               stroke_width=STROKE, stroke_fill=(0, 0, 0, 255))
    im.save(out)


def render_all(project: Project) -> int:
    cards = project.load_timing()
    project.subs.mkdir(parents=True, exist_ok=True)
    f = ImageFont.truetype(str(font_path()), SIZE)
    for c in cards:
        render(c["text"], project.subs / f"{c['i']:02d}.png", f)
    print(f"자막 {len(cards)}장 → {project.subs.relative_to(project.dir)}/")
    return len(cards)
