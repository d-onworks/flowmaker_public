# -*- coding: utf-8 -*-
"""환경 점검 — 부족한 게 있으면 무엇을 어떻게 깔지 알려준다. 폰트는 여기서 내려받는다.

필수(없으면 종료코드 1): python · ffmpeg · pillow · playwright · 폰트
선택(경고만): ELEVENLABS_API_KEY(더빙·효과음) · Flow 로그인 프로필
"""
from __future__ import annotations

import shutil
import sys

from . import env


def run(install_font: bool = True) -> bool:
    required_ok = True
    notes: list[str] = []

    def line(good: bool, what: str, fix: str = "", required: bool = True) -> None:
        nonlocal required_ok
        if required:
            required_ok = required_ok and good
        mark = "✅" if good else ("❌" if required else "· ")
        print(f"  {mark} {what}" + (f"  → {fix}" if (fix and not good) else ""))
        if not good and not required:
            notes.append(fix)

    print("환경 점검")
    line(sys.version_info >= (3, 10), f"python {sys.version.split()[0]}", "3.10 이상 필요")
    line(bool(shutil.which("ffmpeg")) and bool(shutil.which("ffprobe")), "ffmpeg / ffprobe",
         "`python -m flowmaker setup` 이 깔아준다 "
         "(직접: macOS brew install ffmpeg · Windows winget install Gyan.FFmpeg · Ubuntu sudo apt install ffmpeg)")
    try:
        import PIL  # noqa: F401
        have_pil = True
        line(True, "pillow")
    except ImportError:
        have_pil = False
        line(False, "pillow", "python -m flowmaker setup")
    try:
        from playwright.sync_api import sync_playwright  # noqa: F401
        line(True, "playwright (파이썬 패키지)")
        try:
            with sync_playwright() as pw:
                b = pw.chromium.launch(headless=True); b.close()
            line(True, "playwright 크로미엄")
        except Exception:
            line(False, "playwright 크로미엄", "python -m flowmaker setup")
    except ImportError:
        line(False, "playwright", "python -m flowmaker setup")

    if have_pil:
        from . import subtitles          # PIL 이 있을 때만 — 없으면 import 자체가 죽는다
        try:
            p = subtitles.ensure_font() if install_font else subtitles.font_path()
            line(True, f"자막 폰트 {p.name}")
        except Exception as e:
            line(False, "자막 폰트", str(e))

    env.load_env()
    key = env.get("ELEVENLABS_API_KEY")
    line(bool(key), "ELEVENLABS_API_KEY" + (f" (…{key[-4:]})" if key else ""),
         "더빙·효과음에 필요. .env 에 ELEVENLABS_API_KEY=… — 없어도 대본·컷 계획·Flow 생성·검수까지는 된다", required=False)
    prof = env.home() / "profile"
    line(prof.exists() and any(prof.iterdir()), "Flow 로그인 프로필",
         "python -m flowmaker login  (창이 뜨면 구글 로그인 — Flow 생성에 필요)", required=False)

    print()
    if not required_ok:
        print("`python -m flowmaker setup` 을 실행하면 대부분 자동으로 깔린다.")
    elif notes:
        print("필수 도구는 준비됐다. 아직 안 되는 단계:")
        for n in notes:
            print(f"  · {n}")
    else:
        print("모두 준비됐다.")
    return required_ok
