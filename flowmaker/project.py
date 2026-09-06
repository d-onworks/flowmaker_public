# -*- coding: utf-8 -*-
"""프로젝트 폴더 규약과 cuts.json 검증.

projects/<이름>/
    script.txt          나레이션 대본 — 한 줄 = 한 문장. TTS 발음용이라 숫자를 한글로 쓴다("천팔백오십사 년")
    subtitles.txt       자막 문구 — script.txt와 줄 수가 같고, 숫자는 아라비아 숫자("1854년")
    cuts.json           컷 계획 — 아래 스키마
    facts.md            사실 검증 기록 (출처·쓰면 안 되는 것)
    sfx.json            효과음 계획 (선택)
    bgm.mp3             배경음악 (선택 — 있으면 조립에 쓴다)
    ── 아래는 파이프라인이 만든다 ──
    narration_raw.mp3   원샷 더빙 원본        alignment.json      글자 단위 타임스탬프
    narration.wav       배속 적용본           subtitle_timing.json 자막 카드 타임코드
    clips/C01.mp4 …     Flow에서 받은 클립    subs/01.png …        자막 PNG
    build/              중간 산출물           final.mp4            완성본

cuts.json 항목 (필수 / 선택)
    n          필수  컷 번호 (1부터, 빠짐없이)
    len        필수  Flow 생성 길이 — 4 | 6 | 8 | 10 초만 가능
    kind       필수  "diag" | "hist" | "real"
    sentences  필수  이 컷이 덮는 대본 문장 번호 목록 (1부터, 컷 순서대로 이어져야 한다)
    prompt     필수  Flow에 넣는 영어 프롬프트 — 본문 + 그림체 꼬리
    desc       선택  한 줄 설명 (사람이 읽는 메모)
    need       계산  나레이션에 맞춘 실제 필요 초 (`sync-need` 가 쓴다). 양수
    offset     선택  클립 앞을 잘라낼 초. 0 이상
    done       계산  클립 파일이 있는가 — 파일에 저장하지 않는다

프로젝트 지정
    이름("bridge") → projects/bridge.   경로("examples/moai", "/abs/path") → 그 폴더.
    이름에는 경로 구분자를 쓸 수 없다.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

from .env import REPO_ROOT

VALID_LEN = (4, 6, 8, 10)
CREDITS = {4: 7, 6: 10, 8: 12, 10: 15}      # 길이별 Flow 크레딧 (Omni Flash 720p 기준 실측)
KINDS = ("diag", "hist", "real")
DERIVED = ("done",)


def is_name(s: str) -> bool:
    return bool(s) and "/" not in s and os.sep not in s and s not in (".", "..")


class Project:
    def __init__(self, name_or_path: str | Path):
        s = str(name_or_path)
        if is_name(s):
            self.dir = (REPO_ROOT / "projects" / s).resolve()
            self.ref = s                                  # 명령 안내에 쓰는 표기
        else:
            p = Path(s).expanduser()
            self.dir = (p if p.is_absolute() else Path.cwd() / p).resolve()
            self.ref = s
        self.name = self.dir.name

    def must_exist(self) -> "Project":
        if not self.dir.is_dir():
            raise SystemExit(f"프로젝트 폴더가 없다: {self.dir}\n  이름이면 projects/<이름>, 예시면 examples/<이름> 처럼 경로로 지정하라")
        return self

    # 경로
    @property
    def script(self) -> Path: return self.dir / "script.txt"
    @property
    def subtitles(self) -> Path: return self.dir / "subtitles.txt"
    @property
    def cuts_path(self) -> Path: return self.dir / "cuts.json"
    @property
    def sfx_path(self) -> Path: return self.dir / "sfx.json"
    @property
    def bgm(self) -> Path: return self.dir / "bgm.mp3"
    @property
    def narration_raw(self) -> Path: return self.dir / "narration_raw.mp3"
    @property
    def alignment(self) -> Path: return self.dir / "alignment.json"
    @property
    def narration(self) -> Path: return self.dir / "narration.wav"
    @property
    def timing(self) -> Path: return self.dir / "subtitle_timing.json"
    @property
    def clips(self) -> Path: return self.dir / "clips"
    @property
    def subs(self) -> Path: return self.dir / "subs"
    @property
    def build(self) -> Path: return self.dir / "build"
    @property
    def final(self) -> Path: return self.dir / "final.mp4"

    def clip(self, n: int) -> Path:
        return self.clips / f"C{n:02d}.mp4"

    # 읽기·쓰기
    def lines(self, path: Path) -> list[str]:
        if not path.exists():
            raise SystemExit(f"{path.name} 이 없다: {path}")
        return [l.strip() for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]

    def n_sentences(self) -> int | None:
        if self.script.exists() and self.script.read_text(encoding="utf-8").strip():
            return len(self.lines(self.script))
        return None

    def read_cuts_raw(self):
        self.must_exist()
        if not self.cuts_path.exists():
            raise SystemExit(f"cuts.json 이 없다: {self.cuts_path}")
        try:
            return json.loads(self.cuts_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            raise SystemExit(f"cuts.json 이 올바른 JSON 이 아니다: {e}")

    def load_cuts(self) -> list[dict]:
        cuts = self.read_cuts_raw()
        problems = validate_cuts(cuts, n_sentences=self.n_sentences())
        if problems:
            raise SystemExit("cuts.json 형식 오류:\n  " + "\n  ".join(problems))
        for c in cuts:
            c["done"] = self.clip(c["n"]).exists()
        return cuts

    def save_cuts(self, cuts: list[dict]) -> None:
        clean = [{k: v for k, v in c.items() if k not in DERIVED} for c in cuts]
        self.cuts_path.write_text(json.dumps(clean, ensure_ascii=False, indent=1), encoding="utf-8")

    def load_timing(self) -> list[dict]:
        if not self.timing.exists():
            raise SystemExit("subtitle_timing.json 이 없다 — 먼저 `timing` 을 실행하라")
        return json.loads(self.timing.read_text(encoding="utf-8"))


def _num(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def validate_cuts(cuts, n_sentences: int | None = None) -> list[str]:
    """스키마 검사. 위반 목록을 돌려준다(비어 있으면 통과). 예외를 던지지 않는다."""
    bad: list[str] = []
    if not isinstance(cuts, list) or not cuts:
        return ["cuts.json 은 비어 있지 않은 목록이어야 한다"]
    expect_n = 1
    next_sentence = 1
    for i, c in enumerate(cuts):
        if not isinstance(c, dict):
            bad.append(f"{i+1}번째 항목이 객체가 아니다"); continue
        tag = f"C{c.get('n', '?')}"
        missing = [k for k in ("n", "len", "kind", "sentences", "prompt") if k not in c]
        if missing:
            bad.append(f"{tag}: 없는 항목 {missing}"); continue
        if not isinstance(c["n"], int) or isinstance(c["n"], bool):
            bad.append(f"{tag}: n 은 정수여야 한다"); continue
        if c["n"] != expect_n:
            bad.append(f"{tag}: 번호가 {expect_n} 이어야 한다")
        expect_n = c["n"] + 1
        if c["len"] not in VALID_LEN or isinstance(c["len"], bool):
            bad.append(f"{tag}: len 은 {VALID_LEN} 중 하나여야 한다 (Flow 생성 길이)")
        if c["kind"] not in KINDS:
            bad.append(f"{tag}: kind 는 {KINDS} 중 하나여야 한다")
        s = c["sentences"]
        if not isinstance(s, list) or not s or any(not isinstance(x, int) or isinstance(x, bool) for x in s):
            bad.append(f"{tag}: sentences 는 정수 목록이어야 한다")
        else:
            if s[0] != next_sentence or s != list(range(s[0], s[-1] + 1)):
                bad.append(f"{tag}: sentences 는 앞 컷에 이어서 {next_sentence}부터 연속이어야 한다 (지금 {s})")
            next_sentence = s[-1] + 1
        if not isinstance(c["prompt"], str) or len(c["prompt"].strip()) < 40:
            bad.append(f"{tag}: prompt 가 너무 짧다")
        if "need" in c and c["need"] is not None and not (_num(c["need"]) and c["need"] > 0):
            bad.append(f"{tag}: need 는 양수여야 한다")
        if "offset" in c and not (_num(c["offset"]) and c["offset"] >= 0):
            bad.append(f"{tag}: offset 은 0 이상 숫자여야 한다")
    if n_sentences is not None and next_sentence - 1 != n_sentences:
        bad.append(f"컷이 덮는 문장은 {next_sentence-1}개인데 대본은 {n_sentences}줄이다 — 빠지거나 넘친 문장이 있다")
    return bad


def credits(cuts: list[dict], only_pending: bool = False) -> int:
    return sum(CREDITS[c["len"]] for c in cuts if not (only_pending and c.get("done")))


def summary(cuts: list[dict]) -> str:
    by = {k: [c for c in cuts if c["kind"] == k] for k in KINDS}
    parts = [f"{k} {len(v)}컷 {sum(x['len'] for x in v)}초" for k, v in by.items() if v]
    return (f"{len(cuts)}컷 · 생성 길이 합 {sum(c['len'] for c in cuts)}초 · 크레딧 {credits(cuts)} "
            f"(미생성 {credits(cuts, True)}) · " + " / ".join(parts))
