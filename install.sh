#!/usr/bin/env bash
# flowmaker 설치 — 아무것도 없는 맥·리눅스에서 이 한 줄이면 끝난다.
#   bash install.sh
# 파이썬이 없으면 파이썬부터 깔고, 그다음 `python -m flowmaker setup` 에 넘긴다
# (가상환경·파이썬 패키지·크로미엄·ffmpeg·.env·자막 폰트는 setup 이 맡는다).
set -uo pipefail
cd "$(dirname "$0")"

say() { printf '%s\n' "$*"; }

# 3.10 이상이면서 실제로 실행되는 파이썬을 찾는다
find_python() {
  local c
  for c in ./.venv/bin/python python3.14 python3.13 python3.12 python3.11 python3.10 python3 python; do
    command -v "$c" >/dev/null 2>&1 || [ -x "$c" ] || continue
    if "$c" -c 'import sys; sys.exit(0 if sys.version_info >= (3,10) else 1)' >/dev/null 2>&1; then
      command -v "$c" 2>/dev/null || printf '%s\n' "$c"
      return 0
    fi
  done
  return 1
}

PY="$(find_python)" || PY=""

if [ -z "$PY" ]; then
  say "파이썬 3.10 이상이 없다 — 먼저 깐다"
  if [ "$(uname -s)" = "Darwin" ]; then
    if command -v brew >/dev/null 2>&1; then
      say "  \$ brew install python"
      brew install python || true
    else
      say "  Homebrew 가 없다. https://brew.sh 로 깔고 다시 실행하거나,"
      say "  https://www.python.org/downloads/ 에서 파이썬을 받아라."
      exit 1
    fi
  elif command -v apt-get >/dev/null 2>&1; then
    say "  \$ sudo apt-get install -y python3 python3-venv python3-pip"
    sudo apt-get install -y python3 python3-venv python3-pip || true
  elif command -v dnf >/dev/null 2>&1; then
    sudo dnf install -y python3 python3-pip || true
  else
    say "  패키지 관리자를 못 찾았다 — 파이썬 3.10 이상을 직접 깔고 다시 실행하라."
    exit 1
  fi
  PY="$(find_python)" || {
    say "파이썬을 깔았는데도 못 찾겠다 — 새 터미널을 열고 다시 실행하라."
    exit 1
  }
fi

say "파이썬: $PY ($("$PY" -V 2>&1))"
exec "$PY" -m flowmaker setup "$@"
