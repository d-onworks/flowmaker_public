# -*- coding: utf-8 -*-
"""env.home() 의 저장소 내부 거부, validator 의 타입 방어, review 의 1장짜리 시트."""
import shutil
import subprocess

import pytest

from flowmaker import env
from flowmaker.project import Project, validate_cuts


def test_home_refuses_repo_inside(monkeypatch):
    monkeypatch.setenv("FLOWMAKER_HOME", str(env.REPO_ROOT / ".flowmaker"))
    with pytest.raises(SystemExit):
        env.home()


def test_home_expands_tilde(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("FLOWMAKER_HOME", "~/fmhome")
    assert env.home() == (tmp_path / "fmhome").resolve()


def test_validator_never_raises_on_garbage():
    assert validate_cuts(["x"])                                   # 문자열 원소
    assert validate_cuts([{"n": "1", "len": 8, "kind": "diag", "sentences": [1], "prompt": "p" * 50}])
    assert validate_cuts([{"n": 1, "len": 8, "kind": "diag", "sentences": [1], "prompt": "p" * 50, "need": "oops"}])
    assert validate_cuts([{"n": 1, "len": 8, "kind": "diag", "sentences": [1], "prompt": "p" * 50, "offset": -1}])
    assert validate_cuts([{"n": 1, "len": 8, "kind": "diag", "sentences": [1], "prompt": "p" * 50, "need": 3.2, "offset": 0.5}]) == []


def test_project_name_vs_path(tmp_path):
    assert Project("bridge").dir == (env.REPO_ROOT / "projects" / "bridge").resolve()
    assert Project(str(tmp_path)).dir == tmp_path.resolve()
    with pytest.raises(SystemExit):
        Project("nope-not-here").must_exist()


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="ffmpeg 없음")
@pytest.mark.parametrize("count", [1, 2, 4, 5])
def test_review_sheet_any_count(tmp_path, count):
    from flowmaker.review import make_sheet
    pngs = []
    for i in range(count):
        p = tmp_path / f"C{i:02d}.png"
        subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "color=c=gray:s=180x320:d=0.1",
                        "-frames:v", "1", str(p), "-y"], check=True)
        pngs.append(p)
    out = tmp_path / "sheet.png"
    for i in range(0, count, 4):
        make_sheet(pngs[i:i + 4], out)
        assert out.exists() and out.stat().st_size > 0
