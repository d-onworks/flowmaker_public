# -*- coding: utf-8 -*-
"""환경 설정 — .env 읽기와 작업 폴더 위치. 외부 라이브러리 없이 처리한다.

우선순위: 실제 환경변수 > 저장소 루트 .env > ~/.flowmaker/.env
FLOWMAKER_HOME 은 저장소 .env 에서도 읽는다(홈 .env 는 그 안에 있으므로 읽을 수 없다).
"""
from __future__ import annotations

import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
_loaded = False


def _parse(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    if not path.exists():
        return out
    for ln in path.read_text(encoding="utf-8").splitlines():
        s = ln.strip()
        if not s or s.startswith("#") or "=" not in s:
            continue
        k, v = s.split("=", 1)
        v = v.strip().strip('"').strip("'")
        if v:
            out[k.strip()] = v
    return out


def home() -> Path:
    """로그인 프로필·폰트 같은 사용자 로컬 자산이 사는 곳. 기본 ~/.flowmaker.

    저장소 안쪽은 거부한다 — 로그인 쿠키가 든 프로필이 git 에 딸려 올라갈 수 있다.
    """
    raw = os.environ.get("FLOWMAKER_HOME") or _parse(REPO_ROOT / ".env").get("FLOWMAKER_HOME")
    p = Path(raw).expanduser() if raw else Path.home() / ".flowmaker"
    p = p.resolve()
    try:
        p.relative_to(REPO_ROOT)
        raise SystemExit(f"FLOWMAKER_HOME 이 저장소 안이다({p}) — 로그인 프로필이 git 에 올라갈 수 있다. 밖으로 두어라")
    except ValueError:
        pass
    p.mkdir(parents=True, exist_ok=True)
    return p


def load_env() -> dict[str, str]:
    """저장소 .env → 홈 .env 순으로 읽어 환경변수에 없는 키만 채운다."""
    global _loaded
    merged = _parse(REPO_ROOT / ".env")
    for k, v in _parse(home() / ".env").items():
        merged.setdefault(k, v)
    for k, v in merged.items():
        os.environ.setdefault(k, v)
    _loaded = True
    return {k: os.environ[k] for k in merged}


def get(key: str, default: str | None = None) -> str | None:
    if not _loaded:
        load_env()
    return os.environ.get(key, default)


def require(key: str, hint: str = "") -> str:
    v = get(key)
    if not v:
        raise SystemExit(f"{key} 가 없다 — .env 에 넣어라. {hint}".strip())
    return v
