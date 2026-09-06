# -*- coding: utf-8 -*-
"""그림체 정본 — 모든 컷 프롬프트는 여기서 꼬리 문장을 가져오고, 제출 전에 check()를 통과해야 한다.

왜 한 파일에 모으나
    편마다 프롬프트를 복사해 쓰면 그 편만의 예외가 다음 편에 표준처럼 상속된다.
    실제로 한 편에서 고친 실수(옷 없는 마네킹)가 두 편 뒤에 그대로 재발한 적이 있다.
    규칙은 여기 한 곳에만 두고, 사고가 날 때마다 check()에 한 줄씩 보탠다.

그림체 3종
    diag  회색 점토 다이어그램 — 원리 설명. 화면의 70~85%를 차지한다.
    hist  시대 재현 실사     — 이야기 비트에만 (감정 전달).
    real  현대 현장 실사     — 훅과 엔딩 북엔드에만.

사람 규칙 (실측으로 확정)
    꼬리에 "사람이 나오면 ~한 마네킹으로" 같은 조건문을 넣으면 그 문장 자체가 사람을 불러낸다.
    조항 없는 편 = 9/9컷 사람 없음, 조항 넣은 편 = 12/12컷 우두커니 선 마네킹.
    → 기본 꼬리에는 사람 언급이 없다. 사람이 필요한 컷만 본문에서 mannequin(동작)으로 부른다.
    → 사람은 ①나레이션의 동작을 실연하거나 ②크기 대비가 정보일 때만. 우두커니 서 있는 사람 금지.
"""
from __future__ import annotations

import re

# ── 꼬리 문장 ─────────────────────────────────────────────────────────────

def diag_tail() -> str:
    """회색 점토 다이어그램. 사람 언급 없음(조건문 = 소환 주문)."""
    return (" Untextured matte grey clay models on a neutral mid-grey studio background, no sky, no "
            "environment. Soft neutral studio lighting from upper left, gentle ambient occlusion, no "
            "harsh shadows. Flat precise technical documentary infographic look, not photorealistic, "
            "not cinematic. No numbers, no lettering, no text, no captions, no watermark, no UI, no logo.")


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


def check(cuts: list[dict]) -> list[str]:
    """컷 목록을 검사해 위반 문장 목록을 돌려준다. 비어 있으면 통과.

    각 컷: {"n": int, "len": 4|6|8|10, "kind": "diag"|"hist"|"real", "prompt": str, "need": float?}
    규칙마다 실제로 겪은 사고가 있다 — 지우지 말고 보태기만 할 것.
    """
    bad: list[str] = []
    for c in cuts:
        p, n, k = c["prompt"], c["n"], c.get("kind")
        tag = f"C{n:02d}"
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
        if k == "diag" and not p.rstrip().endswith(diag_tail().strip()):
            bad.append(f"{tag}: diag 꼬리가 정본과 다르다 — diag_tail() 을 그대로 붙여라")
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
