# -*- coding: utf-8 -*-
"""Flow 드라이버의 순수 로직 — 브라우저 없이 검사한다 (회수 매핑·준비 판정)."""
import pytest

from flowmaker.flow_driver import map_clips, readiness


def test_maps_newest_first_to_submission_order():
    # 화면은 최신이 위: 제출 [3, 7, 9] → 화면 [u9, u7, u3]
    assert map_clips([3, 7, 9], ["u9", "u7", "u3"]) == {9: "u9", 7: "u7", 3: "u3"}


def test_count_mismatch_refuses():
    with pytest.raises(ValueError):
        map_clips([3, 7], ["a", "b", "c"])
    with pytest.raises(ValueError):
        map_clips([3, 7, 9], ["a", "b"])


def test_readiness_states():
    assert readiness(2, 3) == "pending"
    assert readiness(3, 3) == "ready"
    assert readiness(6, 3) == "too_many"
