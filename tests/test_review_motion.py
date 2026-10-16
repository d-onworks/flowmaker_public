# -*- coding: utf-8 -*-
"""쓰는 구간 계산(offset·until·need)과 0.6초 움직임 시트 — 2026-10 온돌 편 2차 검수에서 생겼다."""
import shutil
import subprocess

import pytest

from flowmaker.assemble import usable, used_span
from flowmaker.project import validate_cuts

BASE = {"n": 1, "len": 10, "kind": "diag", "sentences": [1], "prompt": "p" * 50}


def test_usable_plain_offset_until():
    assert usable({**BASE}, 10.0) == (0.0, 10.0)
    assert usable({**BASE, "offset": 1.5}, 10.0) == (1.5, 8.5)
    assert usable({**BASE, "until": 6.5}, 10.0) == (0.0, 6.5)
    assert usable({**BASE, "offset": 1.0, "until": 6.5}, 10.0) == (1.0, 5.5)
    assert usable({**BASE, "until": 12.0}, 10.0) == (0.0, 10.0)        # 클립보다 긴 until 은 클립 끝까지


def test_usable_refuses_bad_ranges():
    with pytest.raises(SystemExit):
        usable({**BASE, "offset": 10.0}, 10.0)
    with pytest.raises(SystemExit):
        usable({**BASE, "offset": 3.0, "until": 2.0}, 10.0)


def test_used_span_is_what_reaches_the_video():
    assert used_span({**BASE, "need": 8.64}, 10.0) == (0.0, 8.64)                  # 안 늘림 → need 만큼
    assert used_span({**BASE, "need": 8.64, "until": 6.5}, 10.0) == (0.0, 6.5)     # 늘림 → 쓸 수 있는 구간 전부
    assert used_span({**BASE, "need": 3.0, "offset": 2.0}, 10.0) == (2.0, 5.0)


def test_validator_until():
    ok = {**BASE, "need": 8.64}
    assert validate_cuts([{**ok, "until": 6.5}]) == []
    assert validate_cuts([{**ok, "until": 0}])
    assert validate_cuts([{**ok, "until": "6.5"}])
    assert validate_cuts([{**ok, "offset": 3.0, "until": 2.0}])


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="ffmpeg 없음")
def test_motion_sheet_covers_span(tmp_path):
    from flowmaker.review import motion_sheet
    src = tmp_path / "c.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "testsrc=s=360x640:d=8:r=30",
                    "-pix_fmt", "yuv420p", str(src), "-y"], check=True)
    out = tmp_path / "m.png"
    assert motion_sheet(src, 0.0, 6.5, out) == 11
    assert out.exists() and out.stat().st_size > 0
    assert motion_sheet(src, 2.0, 2.3, out) == 1                        # 아주 짧아도 한 장은 나온다


def test_lead_shrinks_own_need_and_span():
    from flowmaker.assemble import lead_of, own_need
    c = {**BASE, "need": 5.0, "lead": {"cut": 18, "from": 2.0, "dur": 1.99}}
    assert lead_of(c) == (18, 2.0, 1.99)
    assert abs(own_need(c) - 3.01) < 1e-9
    a, b = used_span(c, 6.0)
    assert (a, round(b, 2)) == (0.0, 3.01)
    assert lead_of({**BASE}) is None


def test_validator_lead():
    two = [{**BASE, "need": 5.0}, {**BASE, "n": 2, "sentences": [2], "need": 4.0}]
    ok = [{**two[0], "lead": {"cut": 2, "from": 1.0, "dur": 1.5}}, two[1]]
    assert validate_cuts(ok) == []
    assert validate_cuts([{**two[0], "lead": {"cut": 1, "dur": 1.5}}, two[1]])          # 자기 자신
    assert validate_cuts([{**two[0], "lead": {"cut": 9, "dur": 1.5}}, two[1]])          # 없는 컷
    assert validate_cuts([{**two[0], "lead": {"cut": 2, "dur": 4.9}}, two[1]])          # 자기 그림이 안 남음
    assert validate_cuts([{**two[0], "lead": {"cut": 2, "dur": -1}}, two[1]])


def test_validator_must_and_abstract():
    ok = {**BASE, "need": 5.0}
    assert validate_cuts([{**ok, "must": ["관은 하나", "두 끝 모두 보일러에"]}]) == []
    assert validate_cuts([{**ok, "abstract": True}]) == []
    assert validate_cuts([{**ok, "must": []}])
    assert validate_cuts([{**ok, "must": ["", "x"]}])
    assert validate_cuts([{**ok, "must": "관은 하나"}])
    assert validate_cuts([{**ok, "abstract": "yes"}])
