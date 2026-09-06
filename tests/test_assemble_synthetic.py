# -*- coding: utf-8 -*-
"""조립 통합 테스트 — Flow·ElevenLabs 없이 합성 클립과 무음 나레이션으로 final.mp4 까지 간다.

ffmpeg 이 없으면 건너뛴다. 자막 폰트가 없으면 내려받는다(네트워크 없으면 건너뛴다).
"""
import json
import shutil
import subprocess

import pytest

from flowmaker import assemble, subtitles
from flowmaker.project import Project
from flowmaker.style import diag_tail

pytestmark = pytest.mark.skipif(not shutil.which("ffmpeg"), reason="ffmpeg 없음")


def _color_clip(path, seconds, color):
    subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i",
                    f"color=c={color}:s=720x1280:d={seconds}:r=30", "-pix_fmt", "yuv420p", str(path), "-y"], check=True)


def _silence(path, seconds):
    subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "anullsrc=r=48000:cl=mono",
                    "-t", str(seconds), "-c:a", "pcm_s16le", str(path), "-y"], check=True)


def test_assemble_end_to_end(tmp_path):
    try:
        subtitles.ensure_font()
    except Exception as e:                       # 네트워크 없음 등
        pytest.skip(f"폰트 준비 실패: {e}")

    p = Project(tmp_path / "synthetic")
    p.dir.mkdir(); p.clips.mkdir(); p.subs.mkdir(); p.build.mkdir()
    p.script.write_text("첫 문장입니다.\n둘째 문장입니다.\n셋째 문장입니다.\n", encoding="utf-8")
    p.subtitles.write_text("첫 문장입니다.\n둘째 문장입니다.\n셋째 문장입니다.\n", encoding="utf-8")
    cuts = [
        {"n": 1, "len": 4, "kind": "diag", "sentences": [1], "desc": "a",
         "prompt": "Clean 3D CG diagram of a plain block on a ground plane. The camera is locked off." + diag_tail(), "need": 3.0},
        {"n": 2, "len": 4, "kind": "diag", "sentences": [2, 3], "desc": "b",
         "prompt": "Clean 3D CG diagram of a plain block on a ground plane. The camera is locked off." + diag_tail(), "need": 5.0},
    ]
    p.save_cuts(cuts)
    _color_clip(p.clip(1), 4, "gray")
    _color_clip(p.clip(2), 4, "darkgray")          # need 5.0 > 4.0 → 1.25배 늘림 경로
    _silence(p.narration, 8.0)
    cards = [{"i": 1, "sentence": 1, "start": 0.0, "end": 3.0, "dur": 3.0, "text": "첫 문장입니다."},
             {"i": 2, "sentence": 2, "start": 3.0, "end": 5.5, "dur": 2.5, "text": "둘째 문장입니다."},
             {"i": 3, "sentence": 3, "start": 5.5, "end": 8.0, "dur": 2.5, "text": "셋째 문장입니다."}]
    p.timing.write_text(json.dumps(cards, ensure_ascii=False), encoding="utf-8")
    assert subtitles.render_all(p) == 3

    d = assemble.run(p)
    assert p.final.exists()
    assert abs(d - 8.0) < 0.3
