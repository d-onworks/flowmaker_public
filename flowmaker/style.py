# -*- coding: utf-8 -*-
"""그림체 정본 — 모든 컷 프롬프트는 여기서 꼬리 문장을 가져오고, 제출 전에 check()를 통과해야 한다.

왜 한 파일에 모으나
    편마다 프롬프트를 복사해 쓰면 그 편만의 예외가 다음 편에 표준처럼 상속된다.
    실제로 한 편에서 고친 실수(옷 없는 마네킹)가 두 편 뒤에 그대로 재발한 적이 있다.
    규칙은 여기 한 곳에만 두고, 사고가 날 때마다 check()에 한 줄씩 보탠다.

그림체 3종
    diag  원리 설명 도해 — 화면의 70~85%를 차지한다. 그림 스타일은 편마다 고른다(아래 DIAG_STYLES, 기본 clay).
    hist  시대 재현 실사     — 이야기 비트에만 (감정 전달).
    real  현대 현장 실사     — 훅과 엔딩 북엔드에만.

사람 규칙 (실측으로 확정)
    꼬리에 "사람이 나오면 ~한 마네킹으로" 같은 조건문을 넣으면 그 문장 자체가 사람을 불러낸다.
    조항 없는 편 = 9/9컷 사람 없음, 조항 넣은 편 = 12/12컷 우두커니 선 마네킹.
    → 기본 꼬리에는 사람 언급이 없다. 사람이 필요한 컷만 본문에서 mannequin(동작)으로 부른다.
    → 사람은 ①나레이션의 동작을 실연하거나 ②크기 대비가 정보일 때만. 우두커니 서 있는 사람 금지.

diag 스타일 (2026-10 추가 — 편 단위 옵션, projects/<편>/project.json 의 "style")
    clay      회색 점토 다이어그램 (기본 · 지금까지의 모든 편)
    archviz   무채색 실사 건축 CG + 굵은 청록 안내선·화살표 (숫자·라벨은 그리지 않는다 — 필요하면 조립에서 덧입힌다)
              2026-10-18 안내선을 굵은 네온관 느낌(밝은 심 + 반투명 빛 번짐)으로 바꿨다(사용자 지적: 얇아서 잘 안 보임 · 굵어져도 비쳐 보이게). 이전 꼬리로 쓴 편은 check 가 걸린다 → `style <편> archviz` 로 다시
    flat      아이소메트릭 플랫 일러스트 — 색면과 얇은 윤곽선
    (2026-10 비교 보드 뒤 사용자 결정: 실사 재질(material)은 너무 사실적이라 빼고, X-ray 는 고르지 않았다 — 꼬리 문구는 git 기록에 있다)
    스타일은 프롬프트의 세 군데만 바꾼다: 첫머리(opener) · 강조 문장(accent) · 꼬리(tail).
    Flow 크레딧은 모델·길이·해상도로 정해지고 프롬프트와는 무관하다 — 스타일을 바꿔도 크레딧은 같다.
    본문은 스타일과 무관하게 내용(구조·경로·개수)만 쓰고, 강조는 accent(대상, 스타일)로 붙인다.
"""
from __future__ import annotations

import re

# ── 꼬리 문장 ─────────────────────────────────────────────────────────────

_NO_TEXT = "No numbers, no lettering, no text, no captions, no watermark, no UI, no logo."

# 꼬리·첫머리·강조 문장 — 사람 언급 없음(조건문 = 소환 주문). 숫자를 쓰지 않는다.
DIAG_STYLES: dict[str, dict] = {
    "clay": {
        "label": "회색 점토 다이어그램",
        "opener": "Clean 3D CG cutaway diagram",
        "accent": "Everything except {x} is matte grey.",
        "tail": (" Untextured matte grey clay models on a neutral mid-grey studio background, no sky, no "
                 "environment. Soft neutral studio lighting from upper left, gentle ambient occlusion, no "
                 "harsh shadows. Flat precise technical documentary infographic look, not photorealistic, "
                 "not cinematic. " + _NO_TEXT),
    },
    "archviz": {
        "label": "무채색 실사 건축 CG + 청록 안내선",
        "opener": "Photoreal architectural visualization cutaway",
        "accent": "Strong colour is used only for {x}; everything else stays in a near-monochrome palette of white, pale concrete and soft grey.",
        "tail": (" Photoreal architectural visualization in a near-monochrome palette of white, pale concrete and soft "
                 "grey, clean modern rendering on a plain light grey studio ground, no sky, no environment. Soft "
                 "overcast daylight, gentle shadows, everything in crisp focus. Bold thick glowing cyan neon-tube "
                 "guide lines and large bold glowing cyan neon arrows, each with a bright core and a soft translucent "
                 "glow halo, trace the key paths and directions, clearly visible against every surface while the "
                 "structure still shows faintly through the glow, with no labels on them. Precise technical documentary look, not cinematic. " + _NO_TEXT),
    },
    "archviz_clean": {
        # 2026-11 시험: 레퍼런스 쇼츠(흰색 실사 건축 CG, 안내선 없음) 비교용 — archviz 에서 청록 네온 문장만 뺐다
        "label": "무채색 실사 건축 CG (안내선 없음 · 시험)",
        "opener": "Photoreal architectural visualization cutaway",
        "accent": "Strong colour is used only for {x}; everything else stays in a near-monochrome palette of white, pale concrete and soft grey.",
        "tail": (" Photoreal architectural visualization in a near-monochrome palette of white, pale concrete and soft "
                 "grey, clean modern rendering on a plain light grey studio ground, no sky, no environment. Soft "
                 "overcast daylight, gentle shadows, everything in crisp focus. Precise technical documentary look, "
                 "not cinematic. " + _NO_TEXT),
    },
    "archviz_bright": {
        # 2026-11 시험 A/B: archviz_clean 이 '무겁다'(사용자) — 레퍼런스처럼 밝은 쇼룸 톤·매끈한 재질·옅은 그림자
        "label": "밝은 쇼룸 실사 건축 CG (시험)",
        "opener": "Photoreal architectural visualization cutaway",
        "accent": "Strong colour is used only for {x}; everything else stays in a bright high-key palette of clean white, light pale concrete and soft warm grey.",
        "tail": (" Photoreal architectural visualization in a bright high-key palette of clean white, light pale concrete and "
                 "soft warm grey, smooth clean matte surfaces with fine subtle detail, like a premium architectural showroom "
                 "model on a seamless bright white studio ground, no sky, no environment. Bright soft diffuse light from above, "
                 "very soft faint shadows, airy and luminous, everything in crisp sharp focus. Precise technical documentary "
                 "look, not cinematic. " + _NO_TEXT),
    },
    "docu_real": {
        # 2026-11 시험: 사용자가 가져온 '실사에 가까운 CG 다큐' 채널(툰드라 시추탑) — 실제 환경·재질·흐린 자연광·채도 뺀 색·대기 원근
        "label": "실사풍 다큐 CG (환경 포함 · 시험)",
        "opener": "Photoreal documentary CG cutaway",
        "accent": "Strong colour is used only for {x}; everything else keeps a muted, desaturated natural documentary palette.",
        "tail": (" Photoreal documentary CG with real weathered materials and textures, set in its real surroundings with the "
                 "ground and sky visible. Natural overcast daylight, soft diffuse shadows, a muted desaturated cool colour grade, "
                 "gentle atmospheric haze in the distance, realistic small details that show the scale. Restrained documentary "
                 "look, not cinematic, no dramatic lighting. " + _NO_TEXT),
    },
    "hero_mono": {
        # 2026-11 시험: 주인공(본문에서 이름 붙인 대상)만 실사, 주변 도시·산·길은 단색 매스 모형 — 신비한 건축사전식 섞기(사용자 요청, 경복궁)
        "label": "주인공만 실사 + 주변 단색 매스 (시험)",
        "opener": "Photoreal aerial documentary view",
        "accent": "Full natural colour and real texture are used only for {x}; everything around it stays plain untextured light grey.",
        "tail": (" Only the main subject described above is rendered photoreal in full natural colour with real materials and "
                 "texture. Everything around it, the surrounding city blocks, roads, trees and mountains, is simplified into plain "
                 "untextured matte light grey massing models with soft ambient occlusion, like an architectural site model. Soft "
                 "overcast daylight, gentle atmospheric haze, high aerial viewpoint. Precise documentary look, not cinematic. " + _NO_TEXT),
    },
    "flat": {
        "label": "아이소메트릭 플랫 일러스트",
        "opener": "Flat isometric illustration cutaway",
        "accent": "Strong accent colour is used only for {x}; everything else uses the calm muted fills.",
        "tail": (" Clean flat vector illustration in an isometric infographic style, with crisp simple shapes, "
                 "flat colour fills in a calm muted palette of warm grey, sand and soft slate blue, thin even "
                 "outlines and simple flat shading, on a plain light grey background, no sky, no environment. "
                 "Precise technical infographic look, not photorealistic, not cinematic. " + _NO_TEXT),
    },
}
DEFAULT_STYLE = "clay"
# 스타일마다 본문에 남으면 안 되는 다른 스타일의 말 (restyle 이 못 바꾼 흔적)
_STYLE_CLASH = {
    "archviz": re.compile(r"\b(clay|matte grey(?! mannequin)|3D CG)\b", re.I),
    "archviz_clean": re.compile(r"\b(clay|matte grey(?! mannequin)|3D CG)\b", re.I),
    "archviz_bright": re.compile(r"\b(clay|matte grey(?! mannequin)|3D CG)\b", re.I),
    "docu_real": re.compile(r"\b(clay|matte grey(?! mannequin)|3D CG|studio)\b", re.I),
    "hero_mono": re.compile(r"\b(clay|3D CG|studio)\b", re.I),
    "flat": re.compile(r"\b(clay|matte grey(?! mannequin)|3D CG|photoreal)\b", re.I),
}


def _style(name: str) -> dict:
    if name not in DIAG_STYLES:
        raise ValueError(f"diag 스타일이 없다: {name} (있는 것: {', '.join(DIAG_STYLES)})")
    return DIAG_STYLES[name]


def diag_tail(style: str = DEFAULT_STYLE) -> str:
    """diag 꼬리. 기본은 회색 점토."""
    return _style(style)["tail"]


def diag_opener(style: str = DEFAULT_STYLE) -> str:
    """diag 본문 첫머리 (예: 'Clean 3D CG cutaway diagram')."""
    return _style(style)["opener"]


def accent(things: str, style: str = DEFAULT_STYLE) -> str:
    """강조 문장 — 색을 쓸 대상만 고른다. 예: accent("the flame and the warm water", "archviz")."""
    return _style(style)["accent"].format(x=things.strip())


def restyle_prompt(prompt: str, src: str, dst: str) -> str:
    """diag 프롬프트의 첫머리·강조 문장·꼬리를 src 스타일에서 dst 스타일로 바꾼다. 꼬리가 다르면 ValueError."""
    a, b = _style(src), _style(dst)
    body = prompt.rstrip()
    if not body.endswith(a["tail"].strip()):
        raise ValueError(f"꼬리가 {src} 정본과 다르다 — 먼저 check 를 통과시켜라")
    body = body[: len(body) - len(a["tail"].strip())].rstrip()
    if body.startswith(a["opener"]):
        body = b["opener"] + body[len(a["opener"]):]
    pat = re.escape(a["accent"]).replace(re.escape("{x}"), "(.+?)")
    body = re.sub(pat, lambda m: b["accent"].format(x=m.group(1)), body)
    return body + b["tail"]


DEFAULT_CLOTHING = ("a plain long-sleeved one-piece work garment covering the arms and legs fully, "
                    "with plain flat shoes")


def mannequin(action: str, clothing: str = DEFAULT_CLOTHING, plural: bool = False) -> str:
    """사람이 필요한 diag 컷의 본문에 넣는다. 동작은 필수다.

    예: mannequin("spreads and tamps a thick layer of packed earth over the arches")
    """
    if not action or not action.strip():
        raise ValueError("동작 없는 마네킹은 금지다 — 무엇을 하고 있는지 적어라")
    subject = "Featureless matte grey mannequins" if plural else "A featureless matte grey mannequin"
    return f"{subject} fully clothed in {clothing}, with no face, {action.strip()}"


def hist_tail(era: str = "pre-modern Korea",
              palette: str = "hemp, straw, dark timber and weathered grey granite",
              clothing: str = "thick padded plain hemp and indigo robes with straw shoes") -> str:
    """시대 재현 실사. 옷을 반드시 지정하고 얼굴은 화면 밖으로."""
    return (f" Photoreal restrained documentary grade in the look of {era}, overcast daylight or dim "
            f"lamplight, muted earth palette of {palette}. People wear {clothing}, fully clothed, no "
            "bare skin. Faces are turned away or out of frame. "
            "No text, no captions, no watermark, no UI, no logo.")


def real_tail(palette: str = "weathered grey granite, dry earth and green grass") -> str:
    """현대 현장 실사. 기본은 사람 없음 — 사람이 나오면 본문에 옷을 적을 것."""
    return (f" Photoreal restrained documentary grade, natural daylight, muted palette of {palette}. "
            "No people in frame. No text, no captions, no watermark, no UI, no logo.")


TAILS = {"diag": diag_tail, "hist": hist_tail, "real": real_tail}
# hist/real 은 인자가 있어 전체 일치 대신 고정 머리·꼬리를 본다
HIST_HEAD = "Photoreal restrained documentary grade in the look of "
HIST_END = ("fully clothed, no bare skin. Faces are turned away or out of frame. "
            "No text, no captions, no watermark, no UI, no logo.")
REAL_HEAD = "Photoreal restrained documentary grade, natural daylight, muted palette of "
REAL_END = "No people in frame. No text, no captions, no watermark, no UI, no logo."

# ── 구성 규칙 (완성 편 실측에서 역산) ────────────────────────────────────────
PHOTOREAL_SHARE_MAX = 0.28     # hist+real 화면시간 합 / 전체
PHOTOREAL_RUN_MAX_SEC = 16.0   # 실사가 연속으로 이어질 수 있는 최대 초
# 실사의 자리는 훅·엔딩·감정 킥 비트뿐이다. 원리 설명은 무조건 diag.

# ── 단어 함정 (실측) ───────────────────────────────────────────────────────
# 생성 모델에겐 도메인 맥락이 없다. 단어의 가장 흔한 뜻을 그린다.
COLLIDING_WORDS = {
    "leaf": "나뭇잎으로 그려진다 → roadway span 등으로 바꾸고 생김새를 서술",
    "leaves": "나뭇잎으로 그려진다 → roadway spans 로",
    "car": "자동차로 그려진다 → cab, carriage, lift platform 등으로",
    "crane": "학(새)으로 그려질 수 있다 → hoist, lifting rig 로",
    "bank": "은행으로 그려질 수 있다 → riverside, embankment 로",
}
# 설치 동작은 부품이 구조물을 관통·파괴하는 그림을 부른다 → 완성 상태로 쓴다
INSTALL_VERBS = re.compile(r"\b(lowered onto|dropped (in)?to|inserted into|driven into)\b", re.I)

# 사람으로 보는 말. figure(석상도 figure)·hand(조각상의 손)·silhouette(크기 대비용 그림자)은 뺀다 —
# 석상 다이어그램을 사람으로 오인해 예시 편이 통째로 걸린 적이 있다.
_PEOPLE = re.compile(r"\b(mannequins?|humans?|persons?|people|workers?|man|men|woman|women|officials?|clerks?)\b", re.I)
# 검은 실루엣(크기 대비·군중 표현)은 피부가 없으니 옷 검사에서 뺀다. 동작(또는 for scale)은 여전히 필요하다.
_SILHOUETTE = re.compile(r"\bsilhouettes?\b", re.I)
_ACTION = re.compile(r"\b(carr(y|ies)|packs?|press(es)?|spreads?|pulls?|push(es)?|lifts?|stacks?|"
                     r"lowers?|climbs?|walks?|saws?|drags?|pours?|places?|lays?|hauls?|turns?|digs?|"
                     r"covers?|kneels?|loads?|breaks?|sets?|tamps?|stands? beside|holds?|holding|ropes?|for scale|to show (the )?scale|scale reference)\b", re.I)


def _dur(c: dict) -> float:
    return float(c.get("need") or c["len"])


def check(cuts: list[dict], diag_style: str = DEFAULT_STYLE) -> list[str]:
    """컷 목록을 검사해 위반 문장 목록을 돌려준다. 비어 있으면 통과. diag_style = 이 편의 diag 스타일.

    각 컷: {"n": int, "len": 4|6|8|10, "kind": "diag"|"hist"|"real", "prompt": str, "need": float?}
    규칙마다 실제로 겪은 사고가 있다 — 지우지 말고 보태기만 할 것.
    """
    bad: list[str] = []
    ep_style = diag_style
    for c in cuts:
        p, n, k = c["prompt"], c["n"], c.get("kind")
        tag = f"C{n:02d}"
        # 컷별 스타일 (2026-11 사용자 원칙: 필요하면 한 편 안에서 그림체를 섞는다) — cuts.json "style"
        diag_style = c.get("style") or ep_style
        if diag_style not in DIAG_STYLES:
            bad.append(f"{tag}: 스타일 '{diag_style}' 이 없다 (있는 것: {', '.join(DIAG_STYLES)})")
            diag_style = ep_style
        # 01 숫자 — 엉뚱한 숫자를 그린다("3D"의 3은 예외)
        if re.search(r"\d", p.replace("3D", "")):
            bad.append(f"{tag}: 프롬프트에 숫자가 있다(엉뚱한 숫자를 그린다) — 자막으로 옮겨라")
        # 02 일상어와 겹치는 업계 용어
        for w, why in COLLIDING_WORDS.items():
            if re.search(rf"\b{w}\b", p, re.I):
                bad.append(f"{tag}: '{w}' 는 일상어와 겹친다 — {why}")
        # 03 설치 동작
        if INSTALL_VERBS.search(p):
            bad.append(f"{tag}: 설치 동작(lowered onto 등)은 부품이 구조물을 뚫는 그림을 부른다 "
                       f"— 완성 상태로 쓰거나 '~는 내내 온전하다'를 덧붙여라")
        # 04 조건문 = 소환 주문
        if re.search(r"Any human figure", p, re.I):
            bad.append(f"{tag}: 'Any human figure' 조건문이 있다 — 이게 소환 주문이다. 꼬리에서 빼라")
        # 05 정본 꼬리 — 토씨 하나 다르면 걸린다 (diag 전체 · hist/real 은 고정 머리·꼬리)
        if k == "diag" and not p.rstrip().endswith(diag_tail(diag_style).strip()):
            other = [s for s in DIAG_STYLES if s != diag_style and p.rstrip().endswith(diag_tail(s).strip())]
            bad.append(f"{tag}: diag 꼬리가 정본과 다르다 — diag_tail('{diag_style}') 을 그대로 붙여라"
                       + (f" (지금 꼬리는 '{other[0]}' 스타일 — 이 컷만 그 스타일이면 cuts.json 에 \"style\": \"{other[0]}\")" if other else ""))
        # 11 스타일 섞임 — 다른 스타일의 말이 본문에 남으면 그 스타일로 그린다
        if k == "diag" and diag_style in _STYLE_CLASH:
            body = p.rstrip()[: -len(diag_tail(diag_style).strip())] if p.rstrip().endswith(diag_tail(diag_style).strip()) else p
            m = _STYLE_CLASH[diag_style].search(body)
            if m:
                bad.append(f"{tag}: '{m.group(1)}' 는 다른 스타일의 말이다({diag_style} 편) — "
                           f"첫머리는 diag_opener(), 강조는 accent(대상, '{diag_style}') 로 써라")
        if k == "hist" and not (HIST_HEAD in p and p.rstrip().endswith(HIST_END)):
            bad.append(f"{tag}: hist 꼬리가 정본과 다르다 — hist_tail() 을 그대로 붙여라")
        if k == "real" and not (REAL_HEAD in p and p.rstrip().endswith(REAL_END)):
            bad.append(f"{tag}: real 꼬리가 정본과 다르다 — real_tail() 을 그대로 붙여라")
        if k == "diag":
            if _PEOPLE.search(p):
                # 06 옷 (실루엣 컷은 제외)
                if "fully clothed" not in p and not _SILHOUETTE.search(p):
                    bad.append(f"{tag}: 사람이 언급되는데 'fully clothed'+옷 이름이 없다 → 나체가 나온다")
                # 07 동작
                if not _ACTION.search(p):
                    bad.append(f"{tag}: 사람이 있는데 하는 일이 없다 — 동작을 주거나 사람을 빼라")
        if k in ("hist", "real"):
            # 08 실사 컷의 사람 옷 (꼬리의 "No people in frame"은 제외하고 본문만 본다)
            body = re.split(r" Photoreal restrained", p)[0]
            if _PEOPLE.search(body) and not re.search(r"wear|clothed", p):
                bad.append(f"{tag}: 실사에 사람이 있는데 옷 지정이 없다")
    # 09 실사 비중
    total = sum(_dur(c) for c in cuts)
    photo = sum(_dur(c) for c in cuts if c.get("kind") in ("hist", "real"))
    if total and photo / total > PHOTOREAL_SHARE_MAX:
        bad.append(f"실사 비중 {photo/total*100:.1f}% > 상한 {PHOTOREAL_SHARE_MAX*100:.0f}% "
                   f"— 원리 컷을 diag로 돌려라")
    # 10 연속 실사
    run = best = 0.0
    for c in cuts:
        run = run + _dur(c) if c.get("kind") in ("hist", "real") else 0.0
        best = max(best, run)
    if best > PHOTOREAL_RUN_MAX_SEC:
        bad.append(f"연속 실사 {best:.1f}초 > 상한 {PHOTOREAL_RUN_MAX_SEC:.0f}초 — 사이에 diag를 넣어라")
    return bad


def composition_only(violations: list[str]) -> list[str]:
    """구성 규칙(실사 비중·연속) 위반만 골라낸다 — 재생성 때 전체 대상으로 한 번 더 본다."""
    return [v for v in violations if v.startswith(("실사", "연속"))]
