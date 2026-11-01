# -*- coding: utf-8 -*-
"""Flow 드라이버의 순수 로직 — 브라우저 없이 검사한다 (회수 매핑·준비 판정)."""
import pytest

from flowmaker.flow_driver import gate_violations, map_clips, pick_new_image, readiness


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


def test_board_picks_only_new_large_image():
    before = ["icon.png", "old.jpg"]
    now = [
        {"src": "icon.png", "nw": 48, "nh": 48, "w": 24, "h": 24, "x": 0, "y": 0},
        {"src": "old.jpg", "nw": 768, "nh": 1376, "w": 200, "h": 356, "x": 300, "y": 400},
        {"src": "avatar.png", "nw": 96, "nh": 96, "w": 32, "h": 32, "x": 1400, "y": 10},   # 새로 보여도 작으면 무시
        {"src": "new.jpg", "nw": 768, "nh": 1376, "w": 200, "h": 356, "x": 60, "y": 400},
    ]
    assert pick_new_image(before, now)["src"] == "new.jpg"


def test_board_none_when_nothing_new():
    assert pick_new_image(["a"], [{"src": "a", "nw": 900, "nh": 900, "w": 300, "h": 300}]) is None


def test_board_prefers_top_left_when_several_new():
    now = [{"src": "b", "nw": 800, "nh": 800, "w": 200, "h": 200, "x": 300, "y": 100},
           {"src": "c", "nw": 800, "nh": 800, "w": 200, "h": 200, "x": 50, "y": 100}]
    assert pick_new_image([], now)["src"] == "c"


def test_gate_judges_photoreal_share_on_whole_project_not_length_group():
    # 2026-10 사고: 6초 그룹만 보면 실사 33% 라 막혔지만 편 전체는 19% — 통과해야 한다
    from flowmaker.style import diag_tail, real_tail
    real = lambda n, need: {"n": n, "len": 6, "kind": "real", "need": need,
                            "prompt": "An empty room in winter. The camera holds still." + real_tail()}
    diag = lambda n, need: {"n": n, "len": 6, "kind": "diag", "need": need,
                            "prompt": "Clean 3D CG cutaway diagram of a floor. The camera is locked off." + diag_tail()}
    group = [real(1, 5.0), diag(2, 4.5), real(3, 4.5), diag(4, 4.0), diag(5, 4.0), diag(6, 4.0)]
    whole = group + [diag(n, 5.0) for n in range(7, 21)]
    assert gate_violations(group, whole) == []
    # 편 전체가 상한을 넘으면 여전히 막는다
    assert gate_violations(group, group[:3])


# ── 편마다 Flow 프로젝트 하나 (2026-11): collect 는 최신 썸네일부터 프롬프트로 찾고, 받아 간 클립에 닿으면 멈춘다
from flowmaker.flow_driver import plan_collect, url_key


def test_plan_collect_skips_other_groups_and_stops_at_taken():
    recs = [{"cut": 9}, {"cut": 3}, {"cut": None}, {"cut": 5}, {"cut": 3, "taken": True}, {"cut": 7}]
    found, stopped = plan_collect([3, 5, 7], recs)
    assert found == {3: 1, 5: 3} and stopped          # 7 은 taken 아래라 쓰지 않는다


def test_plan_collect_regenerated_cut_pending_does_not_take_old_clip():
    # C06 을 다시 만들었는데 아직 생성 중 — 옛 C06(taken) 을 새 것으로 받으면 안 된다
    recs = [{"cut": 2}, {"cut": 6, "taken": True}]
    found, stopped = plan_collect([6], recs)
    assert found == {} and stopped


def test_plan_collect_prefers_newest_duplicate():
    found, _ = plan_collect([4], [{"cut": 4}, {"cut": 4}])
    assert found == {4: 0}


def test_url_key_drops_query():
    assert url_key("https://x/video/abc?sig=1&e=2") == url_key("https://x/video/abc?sig=9") == "https://x/video/abc"


from flowmaker.flow_driver import pick_title_candidate


def test_title_prefers_input_then_default_name():
    c = [{"text": "Flow", "x": 10}, {"text": "11월 1일 15:16", "x": 80}, {"text": "공유", "x": 600}]
    assert pick_title_candidate(c)["text"] == "11월 1일 15:16"
    c2 = c + [{"text": "", "input": True, "x": 90}]
    assert pick_title_candidate(c2)["input"]
    assert pick_title_candidate([{"text": "공유", "x": 1}]) is None
    assert pick_title_candidate([{"text": "온돌 편", "x": 5}], "온돌 편")["text"] == "온돌 편"


def test_match_prompts_handles_curly_quotes():
    from flowmaker.flow_driver import match_prompts
    pr = {3: "Aerial view looking north along the palace's single straight central axis. " * 3}
    page = "Prompt " + pr[3].replace("'", "’") + " Edit"
    assert match_prompts(pr, [page]) == [3]
