# -*- coding: utf-8 -*-
"""setup — clone 직후 한 번. `doctor` 가 "이걸 깔아라"고 말하는 것들을 실제로 깔아준다.

    venv(없으면 만든다) → pip install → playwright 크로미엄 → ffmpeg → .env → 자막 폰트 → doctor

ffmpeg 은 파이썬 패키지가 아니라 OS 패키지 관리자로 깐다
(macOS brew · Windows winget/choco/scoop · Linux apt/dnf/pacman).
관리자가 없거나 권한이 없으면 멈추지 않고 **명령만 알려주고** 나머지를 계속 진행한다 —
ffmpeg 이 없어도 대본·컷 계획·Flow 생성까지는 되기 때문이다.

윈도우 주의: 방금 깐 ffmpeg 은 이미 떠 있는 셸의 PATH 에 없다. `_refresh_path()` 가
설치 위치를 현재 프로세스 PATH 에 임시로 붙이고, 그래도 없으면 "새 터미널을 열어라"고 알린다.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

from .env import REPO_ROOT

# ── 순수 로직 (테스트 대상) ──────────────────────────────────────────────────

#: OS → (관리자 실행파일, 설치 명령, 관리자가 하나도 없을 때의 안내)
FFMPEG_MANAGERS: dict[str, list[tuple[str, list[str]]]] = {
    "darwin": [
        ("brew", ["brew", "install", "ffmpeg"]),
    ],
    "win32": [
        ("winget", ["winget", "install", "--id", "Gyan.FFmpeg", "-e", "--source", "winget",
                    "--accept-package-agreements", "--accept-source-agreements"]),
        ("choco", ["choco", "install", "ffmpeg", "-y"]),
        ("scoop", ["scoop", "install", "ffmpeg"]),
    ],
    "linux": [
        ("apt-get", ["sudo", "apt-get", "install", "-y", "ffmpeg"]),
        ("dnf", ["sudo", "dnf", "install", "-y", "ffmpeg"]),
        ("pacman", ["sudo", "pacman", "-S", "--noconfirm", "ffmpeg"]),
    ],
}

MANUAL_HINT = {
    "darwin": "Homebrew 가 없다 — https://brew.sh 로 설치한 뒤 `brew install ffmpeg`, "
              "또는 https://evermeet.cx/ffmpeg 에서 받아 PATH 에 넣어라",
    "win32": "winget·choco·scoop 이 하나도 없다 — https://ffmpeg.org/download.html 에서 받아 "
             "압축을 풀고 bin 폴더를 시스템 PATH 에 넣어라 (윈도우10 이상이면 "
             "`winget` 이 기본 탑재이니 Microsoft Store 의 '앱 설치 관리자'를 확인해도 된다)",
    "linux": "apt/dnf/pacman 을 못 찾았다 — 배포판 패키지 관리자로 ffmpeg 을 설치하라",
}


def ffmpeg_plan(platform: str, which=shutil.which) -> tuple[list[str] | None, str]:
    """이 OS 에서 ffmpeg 을 깔 명령. 못 깔면 (None, 안내문)."""
    for exe, cmd in FFMPEG_MANAGERS.get(platform, []):
        if which(exe):
            return cmd, f"{exe} 로 설치"
    return None, MANUAL_HINT.get(platform, "ffmpeg 을 직접 설치해 PATH 에 넣어라")


def in_venv() -> bool:
    return sys.prefix != getattr(sys, "base_prefix", sys.prefix)


def venv_python(venv_dir: Path, platform: str = sys.platform) -> Path:
    """venv 폴더 안의 파이썬 실행파일 경로 (윈도우는 Scripts\\python.exe)."""
    if platform == "win32":
        return venv_dir / "Scripts" / "python.exe"
    return venv_dir / "bin" / "python"


def path_candidates(platform: str, environ: dict[str, str] | None = None) -> list[str]:
    """패키지 관리자가 방금 깐 실행파일이 있을 만한 폴더들."""
    e = os.environ if environ is None else environ
    if platform == "win32":
        out = [r"C:\ProgramData\chocolatey\bin"]
        if e.get("LOCALAPPDATA"):
            out.append(str(Path(e["LOCALAPPDATA"]) / "Microsoft" / "WinGet" / "Links"))
        if e.get("USERPROFILE"):
            out.append(str(Path(e["USERPROFILE"]) / "scoop" / "shims"))
        return out
    if platform == "darwin":
        return ["/opt/homebrew/bin", "/usr/local/bin"]
    return ["/usr/bin", "/usr/local/bin"]


# ── 실행 ─────────────────────────────────────────────────────────────────────

def _refresh_path() -> None:
    cur = os.environ.get("PATH", "").split(os.pathsep)
    for d in path_candidates(sys.platform):
        if d not in cur and Path(d).is_dir():
            cur.append(d)
    os.environ["PATH"] = os.pathsep.join(cur)


def _child_env() -> dict[str, str]:
    """자식 파이썬도 utf-8 로 말하게 한다 — 윈도우 기본 cp949 로 나가면 한글이 깨진다."""
    return {**os.environ, "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"}


def _run(cmd: list[str], why: str, *, dry_run: bool, fatal: bool = True) -> bool:
    printable = " ".join(cmd)
    print(f"\n▶ {why}\n  $ {printable}", flush=True)
    if dry_run:
        print("  (--dry-run 이라 실행하지 않는다)")
        return True
    try:
        subprocess.run(cmd, check=True, env=_child_env())
        return True
    except (subprocess.CalledProcessError, FileNotFoundError, KeyboardInterrupt) as e:
        mark = "실패" if fatal else "실패(건너뜀)"
        print(f"  {mark}: {type(e).__name__} {e}")
        return False


def has_pip(py: Path) -> bool:
    """이 파이썬으로 pip 을 부를 수 있나. 남아 있던 반쪽 venv 를 걸러낸다."""
    try:
        return subprocess.run([str(py), "-m", "pip", "--version"],
                              capture_output=True, timeout=60).returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def base_python() -> Path:
    """venv 안에서 돌고 있을 때 그 venv 를 만든 원래 파이썬."""
    return Path(getattr(sys, "_base_executable", None) or sys.executable)


def make_venv(vdir: Path, dry_run: bool = False) -> Path | None:
    """venv 를 만들고 그 안의 파이썬을 돌려준다. 끝내 못 만들면 None.

    `python -m venv` 는 껍데기를 만든 뒤 ensurepip 으로 pip 을 넣는데, **pip 단계만 깨지는
    윈도우가 있다** — PATH 에 못 읽는 항목이 하나라도 있으면 pip 이 WinError 448 로 죽는다
    (실측: PATH 의 어떤 항목이 신뢰할 수 없는 탑재 지점이었다). 껍데기는 멀쩡하므로
    `--without-pip` 로 다시 만들고 pip 만 따로 붙여 본다.
    """
    if _run([sys.executable, "-m", "venv", str(vdir)], ".venv 만들기", dry_run=dry_run, fatal=False):
        return venv_python(vdir)
    print("  pip 부트스트랩만 실패한 것일 수 있다 — pip 없이 만들고 따로 붙여 본다")
    shutil.rmtree(vdir, ignore_errors=True)
    if _run([sys.executable, "-m", "venv", "--without-pip", str(vdir)],
            ".venv 만들기 (pip 제외)", dry_run=dry_run, fatal=False):
        py = venv_python(vdir)
        if _run([str(py), "-m", "ensurepip", "--default-pip"],
                "venv 에 pip 붙이기", dry_run=dry_run, fatal=False):
            return py
    # ★pip 없는 반쪽 venv 를 남기면 다음 실행이 그걸 골라 더 이상한 곳에서 깨진다. 지우고 간다.
    if not dry_run:
        shutil.rmtree(vdir, ignore_errors=True)
    return None


def run(no_ffmpeg: bool = False, dry_run: bool = False) -> bool:
    print(f"flowmaker setup — {sys.platform} · python {sys.version.split()[0]}")
    if sys.version_info < (3, 10):
        print("파이썬 3.10 이상이 필요하다. python.org 에서 올린 뒤 다시 실행하라.")
        return False

    ok = True
    on_base_python = False

    # 1) 파이썬 환경 — venv 밖이면 저장소에 .venv 를 만들어 거기에 깐다
    if in_venv():
        py = Path(sys.executable)
        print(f"\n가상환경 안이다 → {py}")
        if not dry_run and not has_pip(py):
            py, on_base_python = base_python(), True
            print(f"  이 가상환경엔 pip 이 없다(설치가 중간에 끊긴 흔적) — 원래 파이썬으로 간다 → {py}")
    else:
        vdir = REPO_ROOT / ".venv"
        py = venv_python(vdir)
        if py.exists() and (dry_run or has_pip(py)):
            print(f"\n기존 .venv 를 쓴다 → {py}")
        elif py.exists():
            print(f"\n기존 .venv 에 pip 이 없다 — 지우고 다시 만든다")
            shutil.rmtree(vdir, ignore_errors=True)
            made = make_venv(vdir)
            if made is None:
                print("\n★ 가상환경을 못 만들었다 — 지금 쓰는 파이썬에 그대로 깐다.")
                py, on_base_python = base_python(), True
            else:
                py = made
        elif dry_run:
            print("\n가상환경(.venv) 이 없다 — 새로 만들 예정")
            make_venv(vdir, dry_run=True)
            py = Path(sys.executable)
        else:
            print("\n가상환경(.venv) 이 없다 — 시스템 파이썬을 더럽히지 않도록 새로 만든다")
            made = make_venv(vdir)
            if made is None:
                # 가상환경은 편의일 뿐이다. 못 만들었다고 설치를 포기하지 않는다.
                print("\n★ 가상환경을 못 만들었다 — 지금 쓰는 파이썬에 그대로 깐다.\n"
                      "  (위 오류를 보라. 파이썬 설치가 깨졌거나 PATH 에 못 읽는 항목이 있는 경우다)")
                py, on_base_python = Path(sys.executable), True
            else:
                py = made

    # 2) 파이썬 패키지
    # --no-warn-script-location: pip 이 "스크립트가 PATH 에 없다" 경고를 내려고 PATH 를 전부
    # 훑는데, PATH 에 못 읽는 항목이 하나라도 있으면 거기서 죽는다(윈도우 WinError 448 실측).
    pip_flags = ["--no-warn-script-location"]
    _run([str(py), "-m", "pip", "install", *pip_flags, "--upgrade", "pip"],
         "pip 최신화", dry_run=dry_run, fatal=False)          # 실패해도 설치는 대개 된다
    ok &= _run([str(py), "-m", "pip", "install", *pip_flags, "-r", str(REPO_ROOT / "requirements.txt")],
               "파이썬 패키지 설치 (playwright · pillow)", dry_run=dry_run)

    # 3) 플레이라이트 브라우저
    ok &= _run([str(py), "-m", "playwright", "install", "chromium"],
               "플레이라이트 크로미엄 내려받기", dry_run=dry_run)

    # 4) ffmpeg — OS 패키지 관리자
    if no_ffmpeg:
        print("\n▶ ffmpeg — --no-ffmpeg 라 건너뛴다")
    elif shutil.which("ffmpeg") and shutil.which("ffprobe"):
        print(f"\n▶ ffmpeg — 이미 있다 ({shutil.which('ffmpeg')})")
    else:
        cmd, note = ffmpeg_plan(sys.platform)
        if cmd is None:
            print(f"\n▶ ffmpeg 자동 설치 불가 — {note}")
            ok = False
        else:
            if cmd[0] == "sudo":
                print("\n  (관리자 권한이 필요해 비밀번호를 물을 수 있다)")
            _run(cmd, f"ffmpeg 설치 — {note}", dry_run=dry_run, fatal=False)
            if not dry_run:
                _refresh_path()
                if shutil.which("ffmpeg"):
                    print(f"  확인됨 → {shutil.which('ffmpeg')}")
                else:
                    print("  아직 PATH 에 안 보인다 — **새 터미널을 열고** 다시 `setup` 을 실행하라")
                    ok = False

    # 5) .env
    envf, example = REPO_ROOT / ".env", REPO_ROOT / ".env.example"
    if envf.exists():
        print("\n▶ .env — 이미 있다")
    elif dry_run:
        print(f"\n▶ .env — .env.example 을 복사할 예정")
    else:
        shutil.copy(example, envf)
        print(f"\n▶ .env 를 만들었다 → {envf}\n"
              f"  ELEVENLABS_API_KEY 를 채워라 (더빙·효과음에 필요. 없어도 컷 생성까지는 된다)")

    # 6) 자막 폰트 — 새 venv 에는 이 프로세스의 PIL 이 없으므로 그쪽 파이썬으로 부른다
    _run([str(py), "-c", "from flowmaker.subtitles import ensure_font; print(ensure_font())"],
         "자막 폰트(Pretendard) 확인·내려받기", dry_run=dry_run, fatal=False)

    # 7) 최종 점검 — ★판정은 doctor 가 한다.
    # 중간 단계가 0 이 아니어도 목적은 이뤄진 경우가 있다(pip 이 다 깔고 마지막 경고에서 죽는 등).
    # 실제로 쓸 수 있느냐만 본다.
    print("\n" + "─" * 60)
    if not dry_run:
        r = subprocess.run([str(py), "-m", "flowmaker", "doctor"], cwd=REPO_ROOT, env=_child_env())
        if r.returncode == 0 and not ok:
            print("\n(중간에 실패한 단계가 있었지만 점검은 통과했다 — 그대로 써도 된다)")
        ok = r.returncode == 0

    if not in_venv() and not dry_run and not on_base_python:
        act = r".venv\Scripts\Activate.ps1" if sys.platform == "win32" else "source .venv/bin/activate"
        print(f"\n★ 이후 명령은 가상환경 안에서 실행하라:  {act}")
        print(f"  (또는 매번 `{py} -m flowmaker <명령>`)")
    print("\n다음: `login` 으로 구글 로그인 → 에이전트에게 \"소재 찾아줘\"" if ok
          else "\n위 실패 항목을 해결한 뒤 `setup` 을 다시 실행하라.")
    return ok
