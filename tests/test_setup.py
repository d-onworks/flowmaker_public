# -*- coding: utf-8 -*-
"""setup 의 OS 분기와, 윈도우에서 터졌던 인코딩 사고 2건의 재발 방지.

사고 기록
    ① tts 가 alignment.json 을 로케일 인코딩(윈도우 한국어 = cp949)으로 쓰고
       timing 이 utf-8 로 읽어 UnicodeDecodeError — 윈도우에서 더빙 다음 단계가 전멸했다.
    ② ✅❌⚠— 는 cp949 에 없다. 출력을 파이프로 받으면(에이전트가 결과를 읽는 방식)
       UnicodeEncodeError 로 죽었다.
"""
import pathlib
import subprocess
import sys

import pytest

from flowmaker import setup
from flowmaker.env import REPO_ROOT


# ── OS 분기 ──────────────────────────────────────────────────────────────────
def _which(*present):
    return lambda exe: f"/fake/{exe}" if exe in present else None


@pytest.mark.parametrize("platform,present,head", [
    ("darwin", ("brew",), "brew"),
    ("win32", ("winget",), "winget"),
    ("win32", ("choco",), "choco"),          # winget 이 없으면 choco 로 내려간다
    ("win32", ("scoop",), "scoop"),
    ("linux", ("apt-get",), "sudo"),
    ("linux", ("dnf",), "sudo"),
])
def test_ffmpeg_plan_picks_available_manager(platform, present, head):
    cmd, note = setup.ffmpeg_plan(platform, which=_which(*present))
    assert cmd is not None and cmd[0] == head
    assert "ffmpeg" in " ".join(cmd).lower()      # winget 은 Gyan.FFmpeg
    assert present[0] in note


@pytest.mark.parametrize("platform", ["darwin", "win32", "linux"])
def test_ffmpeg_plan_without_manager_guides_instead_of_crashing(platform):
    cmd, note = setup.ffmpeg_plan(platform, which=_which())
    assert cmd is None and len(note) > 20      # 멈추지 않고 안내문만 준다


def test_ffmpeg_plan_unknown_platform():
    cmd, note = setup.ffmpeg_plan("sunos5", which=_which("brew"))
    assert cmd is None and note


def test_venv_python_path_per_os(tmp_path):
    assert setup.venv_python(tmp_path, "win32").parts[-2:] == ("Scripts", "python.exe")
    assert setup.venv_python(tmp_path, "darwin").parts[-2:] == ("bin", "python")


def test_path_candidates_windows_uses_env(tmp_path):
    got = setup.path_candidates("win32", {"LOCALAPPDATA": r"C:\LA", "USERPROFILE": r"C:\U"})
    assert any("WinGet" in p for p in got) and any("scoop" in p for p in got)
    assert setup.path_candidates("win32", {})      # 환경변수가 없어도 죽지 않는다


# ── 사고 ① 재발 방지 ─────────────────────────────────────────────────────────
def test_all_file_io_declares_utf8():
    """flowmaker/ 안의 read_text·write_text 는 전부 encoding 을 명시해야 한다.

    안 하면 맥은 utf-8, 윈도우 한국어는 cp949 로 갈려서 파일이 왕복하지 못한다.
    """
    offenders = []
    for f in sorted(pathlib.Path(REPO_ROOT / "flowmaker").glob("*.py")):
        lines = f.read_text(encoding="utf-8").splitlines()
        for i, ln in enumerate(lines):
            if "read_text(" not in ln and "write_text(" not in ln:
                continue
            chunk = " ".join(lines[i:i + 3])        # 줄바꿈된 인자까지 본다
            if "encoding=" not in chunk:
                offenders.append(f"{f.name}:{i + 1}  {ln.strip()}")
    assert not offenders, "encoding 미지정:\n" + "\n".join(offenders)


def test_alignment_json_roundtrips_as_utf8(tmp_path):
    """cp949 로 쓰였다면 utf-8 읽기가 깨진다 — 실제로 깨지는지 대조까지 한다."""
    import json
    text = json.dumps({"characters": list("석빙고")}, ensure_ascii=False)
    good = tmp_path / "ok.json"
    good.write_text(text, encoding="utf-8")                     # tts.py 가 하는 방식
    assert json.loads(good.read_text(encoding="utf-8"))         # timing.py 가 하는 방식

    bad = tmp_path / "cp949.json"
    bad.write_bytes(text.encode("cp949"))                       # 수정 전 윈도우가 하던 방식
    with pytest.raises(UnicodeDecodeError):
        bad.read_text(encoding="utf-8")


# ── 사고 ② 재발 방지 ─────────────────────────────────────────────────────────
def test_cli_survives_cp949_pipe():
    """PYTHONIOENCODING=cp949 + 파이프 = 윈도우 한국어 환경 재현."""
    import os
    env = {**os.environ, "PYTHONIOENCODING": "cp949"}
    r = subprocess.run([sys.executable, "-m", "flowmaker", "--help"],
                       cwd=REPO_ROOT, env=env, capture_output=True)
    assert r.returncode == 0, r.stderr.decode(errors="replace")

    # 가드가 없으면 같은 조건에서 실제로 죽는다는 대조군
    c = subprocess.run([sys.executable, "-c", "print('✅❌⚠—')"],
                       env=env, capture_output=True)
    assert c.returncode != 0 and b"UnicodeEncodeError" in c.stderr
