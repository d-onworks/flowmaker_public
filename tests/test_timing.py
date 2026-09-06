# -*- coding: utf-8 -*-
"""자막 분할 규칙 — 폰트 없이 검사할 수 있는 split_point 만."""
from flowmaker.timing import split_point


def test_does_not_split_inside_number_comma():
    t = "지금까지 7,700명이 이 손잡이 덕분에 살아 돌아왔습니다 정말로 그렇습니다"
    k = split_point(t)
    assert k is not None
    assert t[:k].rstrip() != "지금까지 7,"           # 숫자 안 쉼표에서 안 자른다


def test_prefers_balanced_comma():
    t = "바닥을 한쪽으로 기울이고, 가장 낮은 끝에 배수구를 뚫었습니다"
    k = split_point(t)
    assert t[:k].rstrip().endswith(",")
    assert 0.30 * len(t) <= k <= 0.70 * len(t)


def test_right_part_never_starts_with_digit():
    t = "한 연구에서는 사출한 조종사의 3분의 1에게서 척추 골절이 확인됐습니다"
    k = split_point(t)
    assert not t[k:].lstrip()[0].isdigit()


def test_single_word_returns_none():
    assert split_point("짧다") is None
