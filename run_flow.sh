#!/bin/bash
# Flow 일괄 생성 — 길이 그룹마다 제출하고, 다 제출한 뒤 그룹별로 회수한다.
# 사용: bash run_flow.sh <프로젝트> [길이 …]      (기본 4 6 8 10)
# 크레딧을 쓰는 명령이다. 실행 전에 `check` 가 보여주는 '미생성 크레딧'을 확인할 것.
cd "$(dirname "$0")" || exit 1
P="$1"; shift
[ -z "$P" ] && { echo "사용: bash run_flow.sh <프로젝트> [길이 …]"; exit 1; }
LENS="${*:-4 6 8 10}"
PY=.venv/bin/python
LOG="projects/$P/run.log"
TMP="projects/$P/build/.last_submit.txt"
mkdir -p "projects/$P/build"          # 새 편은 build/ 가 아직 없다 (2026-11 zero15_a 에서 tee·grep 오류)
{
  echo "===== run_flow $P [$LENS] $(date '+%F %T') ====="
  sub=()
  for L in $LENS; do
    $PY -m flowmaker submit "$P" "$L" 2>&1 | tee "$TMP"; s=${PIPESTATUS[0]}
    echo "[submit ${L}s exit $s]"
    grep -q "제출할 컷 없음" "$TMP" && continue          # 이 길이는 이미 다 있음
    { [ "$s" -eq 0 ] || [ "$s" -eq 3 ]; } && sub+=("$L")
  done
  for L in "${sub[@]}"; do
    for i in 1 2 3 4 5 6 7 8 9 10; do
      sleep 90
      $PY -m flowmaker collect "$P" "$L"; r=$?
      echo "[collect ${L}s try $i exit $r]"
      [ "$r" -ne 2 ] && break
    done
  done
  $PY -m flowmaker status "$P"
  echo "===== run_flow 끝 $(date '+%F %T') ====="
} 2>&1 | tee -a "$LOG"
