# -*- coding: utf-8 -*-
"""그림체 정본 검사 10개 — 각 규칙이 실제로 걸리는지, 깨끗한 컷은 통과하는지."""
import pytest

from flowmaker.style import check, diag_tail, hist_tail, mannequin, real_tail

CLEAN_DIAG = ("Clean 3D CG cutaway diagram of a stone chamber sliced open so the vault is visible. "
              "The camera is locked off." + diag_tail())


def cut(prompt, n=1, kind="diag", length=8, need=None):
    return {"n": n, "len": length, "kind": kind, "prompt": prompt, "need": need}


def test_clean_cut_passes():
    assert check([cut(CLEAN_DIAG)]) == []


def test_01_number_blocked_but_3d_allowed():
    assert any("숫자" in v for v in check([cut("Clean 3D CG diagram, a wall two metres tall 2m" + diag_tail())]))
    assert check([cut(CLEAN_DIAG)]) == []


@pytest.mark.parametrize("word", ["leaf", "car", "crane", "bank"])
def test_02_colliding_words(word):
    p = f"Clean 3D CG diagram of a {word} moving slowly. The camera is locked off." + diag_tail()
    assert any(word in v for v in check([cut(p)]))


def test_03_install_verbs():
    p = "Clean 3D CG diagram. A block is lowered onto the short arm." + diag_tail()
    assert any("설치 동작" in v for v in check([cut(p)]))


def test_04_conditional_human_clause():
    p = CLEAN_DIAG + " Any human figure is a grey mannequin."
    assert any("소환" in v for v in check([cut(p)]))


def test_05_tails_must_match_exactly():
    assert any("꼬리" in v for v in check([cut("Clean 3D CG diagram of a bridge. The camera is locked off.")]))
    tweaked = CLEAN_DIAG.replace("no logo.", "no logos.")          # 토씨 하나
    assert any("꼬리" in v for v in check([cut(tweaked)]))
    ok_hist = "Workers in hemp robes saw ice." + hist_tail(era="Joseon Korea")
    assert not any("꼬리" in v for v in check([cut(ok_hist, kind="hist", need=4), cut(CLEAN_DIAG, n=2, need=40)]))
    bad_real = "Wide view of a river. Photoreal restrained documentary grade, natural daylight, muted palette of grass. No text."
    assert any("real 꼬리" in v for v in check([cut(bad_real, kind="real", need=4), cut(CLEAN_DIAG, n=2, need=40)]))


def test_plural_people_words_are_caught():
    p = "Clean 3D CG diagram. Workers carry blocks across the room." + diag_tail()
    assert any("fully clothed" in v for v in check([cut(p)]))


def test_06_person_without_clothing():
    p = "Clean 3D CG diagram. A worker carries a block across the room." + diag_tail()
    assert any("fully clothed" in v for v in check([cut(p)]))


def test_07_person_without_action():
    p = "Clean 3D CG diagram. " + "A featureless matte grey mannequin fully clothed in a plain garment, with no face, near the wall." + diag_tail()
    assert any("하는 일이 없다" in v for v in check([cut(p)]))


def test_mannequin_helper_passes_and_requires_action():
    p = "Clean 3D CG diagram. " + mannequin("spreads packed earth over the arches") + diag_tail()
    assert check([cut(p)]) == []
    with pytest.raises(ValueError):
        mannequin("")


def test_08_photoreal_person_without_clothing():
    p = "A worker stands by the river." + real_tail()
    v = check([cut(p, kind="real", need=4), cut(CLEAN_DIAG, n=2, need=40)])
    assert any("옷 지정" in x for x in v)


def test_09_photoreal_share():
    cuts = [cut("Wide view of a river." + real_tail(), kind="real", need=30),
            cut(CLEAN_DIAG, n=2, need=30)]
    assert any("실사 비중" in v for v in check(cuts))


def test_10_photoreal_run():
    cuts = [cut("Wide view." + real_tail(), kind="real", need=10),
            cut("Workers in hemp robes wear straw shoes." + hist_tail(), n=2, kind="hist", need=8),
            cut(CLEAN_DIAG, n=3, need=60), cut(CLEAN_DIAG, n=4, need=60)]
    v = check(cuts)
    assert any("연속 실사" in x for x in v)
    assert not any("실사 비중" in x for x in v)
