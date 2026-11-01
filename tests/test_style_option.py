# -*- coding: utf-8 -*-
"""diag 그림 스타일 옵션(clay·archviz·flat) — 2026-10, 점토 말고 다른 그림체도 쓰고 싶다는 요청에서 생겼다."""
import json
import re

import pytest

from flowmaker import style
from flowmaker.project import Project

TAIL_CLAY_2026 = (" Untextured matte grey clay models on a neutral mid-grey studio background, no sky, no "
                  "environment. Soft neutral studio lighting from upper left, gentle ambient occlusion, no "
                  "harsh shadows. Flat precise technical documentary infographic look, not photorealistic, "
                  "not cinematic. No numbers, no lettering, no text, no captions, no watermark, no UI, no logo.")
BODY = ("Clean 3D CG cutaway diagram of a room floor in section. A row of round pipes carries warm orange water "
        "inside a thick layer of cement mortar. Everything except the warm water is matte grey. "
        "The camera holds still.")
CUT = {"n": 1, "len": 4, "kind": "diag", "sentences": [1], "prompt": BODY + TAIL_CLAY_2026}


def test_clay_is_default_and_unchanged():
    assert style.DEFAULT_STYLE == "clay"
    assert style.diag_tail() == TAIL_CLAY_2026          # 지금까지 만든 편의 꼬리가 그대로 통과해야 한다
    assert style.check([CUT]) == []


def test_every_style_has_no_digits_and_no_text_clause():
    for name, s in style.DIAG_STYLES.items():
        assert not re.search(r"\d", (s["tail"] + s["accent"] + s["opener"]).replace("3D", "")), name
        assert s["tail"].rstrip().endswith("no watermark, no UI, no logo."), name
        assert "{x}" in s["accent"], name


@pytest.mark.parametrize("dst", ["archviz", "flat"])
def test_restyle_round_trip_and_check(dst):
    moved = style.restyle_prompt(CUT["prompt"], "clay", dst)
    assert moved.startswith(style.diag_opener(dst))
    assert style.accent("the warm water", dst) in moved
    assert moved.endswith(style.diag_tail(dst).strip())
    assert style.check([{**CUT, "prompt": moved}], diag_style=dst) == []
    assert style.restyle_prompt(moved, dst, "clay") == CUT["prompt"].rstrip()


def test_wrong_tail_names_the_style_it_has():
    moved = style.restyle_prompt(CUT["prompt"], "clay", "archviz")
    bad = style.check([{**CUT, "prompt": moved}])                     # clay 편인데 archviz 꼬리
    assert bad and "archviz" in bad[0]


def test_clay_words_left_in_other_style_are_caught():
    leftover = BODY.replace("Clean 3D CG cutaway diagram", style.diag_opener("archviz")) + style.diag_tail("archviz")
    bad = style.check([{**CUT, "prompt": leftover}], diag_style="archviz")
    assert any("matte grey" in b for b in bad)
    ok = leftover.replace("Everything except the warm water is matte grey.", style.accent("the warm water", "archviz"))
    assert style.check([{**CUT, "prompt": ok}], diag_style="archviz") == []


def test_mannequin_grey_is_not_a_clash():
    body = (style.diag_opener("archviz") + " of a pit. " + style.mannequin("tamps packed earth with a wooden rammer")
            + ". " + style.accent("the fresh earth", "archviz"))
    assert style.check([{**CUT, "prompt": body + style.diag_tail("archviz")}], diag_style="archviz") == []


def test_project_style_default_and_setting(tmp_path):
    p = Project(tmp_path)
    assert p.style == "clay"
    p.set_style("flat")
    assert json.loads((tmp_path / "project.json").read_text(encoding="utf-8")) == {"style": "flat"}
    assert Project(tmp_path).style == "flat"
    (tmp_path / "project.json").write_text('{"style": "oil"}', encoding="utf-8")
    with pytest.raises(SystemExit):
        Project(tmp_path).style


def test_unknown_style_is_refused():
    with pytest.raises(ValueError):
        style.diag_tail("xray")


def test_cut_style_override_mixes_styles_in_one_episode():
    """2026-11 사용자 원칙: 필요하면 한 편 안에서 그림체를 섞는다 — 컷의 "style" 이 편 스타일보다 우선."""
    from flowmaker import style
    a = {"n": 1, "len": 4, "kind": "diag", "prompt": "x." + style.diag_tail("hero_mono"), "style": "hero_mono"}
    b = {"n": 2, "len": 4, "kind": "diag", "prompt": "y." + style.diag_tail("archviz_bright")}
    assert style.check([a, b], diag_style="archviz_bright") == []
    no = dict(a); no.pop("style")
    assert any("C01" in v for v in style.check([no, b], diag_style="archviz_bright"))
    bad = dict(a, style="nope")
    assert any("없다" in v for v in style.check([bad], diag_style="archviz_bright"))
