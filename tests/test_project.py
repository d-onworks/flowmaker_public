# -*- coding: utf-8 -*-
"""cuts.json 형식 검사와, 동봉한 예시 3편이 형식·정본 검사를 모두 통과하는지."""
import json
from pathlib import Path

import pytest

from flowmaker.project import credits, validate_cuts
from flowmaker.style import check

ROOT = Path(__file__).resolve().parent.parent
EXAMPLES = sorted(p for p in (ROOT / "examples").iterdir() if p.is_dir())


def good(n, s, length=8, kind="diag"):
    return {"n": n, "len": length, "kind": kind, "sentences": s,
            "prompt": "Clean 3D CG diagram of something quite specific and long enough. " * 2}


def test_valid_sequence_passes():
    assert validate_cuts([good(1, [1, 2]), good(2, [3]), good(3, [4, 5, 6])], n_sentences=6) == []


def test_sentence_gap_and_overlap_flagged():
    assert any("연속" in v for v in validate_cuts([good(1, [1]), good(2, [3])]))
    assert any("연속" in v for v in validate_cuts([good(1, [1, 2]), good(2, [2, 3])]))


def test_bad_len_kind_number():
    v = validate_cuts([good(1, [1], length=5), good(3, [2], kind="photo")])
    assert any("len" in x for x in v) and any("kind" in x for x in v) and any("번호" in x for x in v)


def test_sentence_count_mismatch():
    assert any("대본은" in v for v in validate_cuts([good(1, [1, 2])], n_sentences=5))


def test_credits():
    assert credits([good(1, [1], 4), good(2, [2], 10)]) == 7 + 15


@pytest.mark.parametrize("example", EXAMPLES, ids=[p.name for p in EXAMPLES])
def test_example_is_valid_and_style_clean(example):
    cuts = json.loads((example / "cuts.json").read_text(encoding="utf-8"))
    n_sent = len([l for l in (example / "script.txt").read_text(encoding="utf-8").splitlines() if l.strip()])
    n_sub = len([l for l in (example / "subtitles.txt").read_text(encoding="utf-8").splitlines() if l.strip()])
    assert n_sent == n_sub, "script.txt 와 subtitles.txt 줄 수가 다르다"
    assert validate_cuts(cuts, n_sent) == []
    assert check(cuts) == []
    assert (example / "facts.md").exists()
