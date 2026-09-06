# -*- coding: utf-8 -*-
"""타이밍 — 나레이션을 자르지 않고 통째로 배속하고, 자막 카드와 컷 길이를 거기에 맞춘다.

왜 자르지 않나
    문장 사이 무음이 0.1초 남짓이라, 문장별로 잘라 재조립하면 여유를 주면 다음 문장 첫 음절이
    두 번 들리고, 줄이면 첫 음절이 잘린다. 자르지 않으면 두 문제가 생기지 않는다.

자막 카드 규칙 (실측)
    2줄 상한. 긴 문장은 두 장으로 쪼갠다 — 3줄이면 블록이 위로 자라 화면 한가운데를 가린다.
    쪼갤 자리: 숫자 안의 쉼표 제외 · 한쪽이 30% 미만이면 제외 · 뒷조각이 숫자로 시작하면 제외 ·
    앞조각이 한 글자 관형사("이·그·저…")로 끝나면 제외.
    자막 문구는 subtitles.txt(아라비아 숫자)를 쓴다 — 대본은 TTS 발음용 한글 숫자다.
"""
from __future__ import annotations

import json
import os
import subprocess

from PIL import Image, ImageDraw, ImageFont

from . import subtitles
from .project import Project

TEMPO_WARN = 1.30      # 이보다 크면 음이 올라간다 — 대본을 줄이라고 경고
TEMPO_MAX = 1.50       # 이보다 크면 거부


def build(project: Project, target: float | None = None, tempo: float | None = None) -> dict:
    lines = project.lines(project.script)
    if not project.alignment.exists():
        raise SystemExit("alignment.json 이 없다 — 먼저 `tts` 를 실행하라")
    al = json.loads(project.alignment.read_text(encoding="utf-8"))
    chars, st, en = al["characters"], al["character_start_times_seconds"], al["character_end_times_seconds"]
    flat = " ".join(lines)
    if "".join(chars) != flat:
        raise SystemExit(f"alignment 은 {len(''.join(chars))}자인데 지금 대본은 {len(flat)}자다 — "
                         "대본을 고쳤으면 `tts` 를 다시 실행하라 (옛 타임스탬프로 계산하면 자막이 전부 어긋난다)")
    subtitles.font_path()                            # 폰트가 없으면 파일을 만들기 전에 여기서 멈춘다
    raw_total = en[-1]

    if tempo is None:
        tempo = round(raw_total / target, 3) if target else 1.0
    if tempo < 1.0:
        tempo = 1.0
    if tempo > TEMPO_MAX:
        raise SystemExit(f"배속 {tempo:.2f} 는 너무 크다 (원본 {raw_total:.1f}초 → 목표 {target}초). 대본을 줄여라")
    if tempo > TEMPO_WARN:
        print(f"경고: 배속 {tempo:.2f} — 음이 올라갈 수 있다. 대본을 {int((1-TEMPO_WARN/tempo)*100)}% 줄이면 좋다")

    subprocess.run(["ffmpeg", "-v", "error", "-i", str(project.narration_raw),
                    "-af", f"atempo={tempo}", "-ar", "48000", "-ac", "1",
                    "-c:a", "pcm_s16le", str(project.narration), "-y"], check=True)
    total = os.path.getsize(project.narration) / (48000 * 2)

    # 문장 경계 = 정렬값 ÷ 배속
    rows, pos = [], 0
    for i, ln in enumerate(lines, 1):
        idx = flat.index(ln, pos)
        a, b = st[idx] / tempo, en[idx + len(ln) - 1] / tempo
        rows.append({"i": i, "sentence": i, "start": round(a, 3), "end": round(b, 3),
                     "dur": round(b - a, 3), "text": ln})
        pos = idx + len(ln)

    # 자막 문구 교체 (아라비아 숫자판)
    if project.subtitles.exists():
        disp = project.lines(project.subtitles)
        if len(disp) != len(rows):
            raise SystemExit(f"subtitles.txt {len(disp)}줄 != script.txt {len(rows)}줄 — 문장 수를 맞춰라")
        for r, t in zip(rows, disp):
            r["text"] = t
    else:
        print("경고: subtitles.txt 없음 — 대본 그대로 자막에 쓴다 (한글 숫자가 화면에 뜬다)")

    cards = _split_cards(rows)
    project.timing.write_text(json.dumps(cards, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"나레이션 {total:.2f}초 (배속 {tempo:.2f}) · {len(rows)}문장 → 자막 {len(cards)}장")
    return {"tempo": tempo, "seconds": total, "sentences": len(rows), "cards": len(cards)}


# ── 자막 분할 ────────────────────────────────────────────────────────────────
def _measurer():
    f = ImageFont.truetype(str(subtitles.font_path()), subtitles.SIZE)
    d = ImageDraw.Draw(Image.new("RGBA", (subtitles.W, subtitles.H)))
    return f, d


def n_lines(text: str, f=None, d=None) -> int:
    if f is None:
        f, d = _measurer()
    n, cur = 1, ""
    for w in text.split():
        cand = (cur + " " + w).strip()
        if d.textlength(cand, font=f) <= subtitles.MAXW or not cur:
            cur = cand
        else:
            n += 1; cur = w
    return n


def split_point(t: str) -> int | None:
    n = len(t); mid = n / 2
    ok = lambda i: 0.30 * n <= i <= 0.70 * n
    def good(i):
        left, right = t[:i].rstrip(), t[i:].lstrip()
        if not left or not right or right[0].isdigit():
            return False
        lw = left.split()[-1]
        return not (len(lw) == 1 and lw in "이그저한두세네온각매그의")
    commas = [i + 1 for i, c in enumerate(t)
              if c == "," and not (t[i-1:i].isdigit() and t[i+1:i+2].isdigit())]
    spaces = [i for i, c in enumerate(t) if c == " " and 0 < i < n - 1]
    for pool in ([i for i in commas if ok(i) and good(i)],
                 [i for i in spaces if ok(i) and good(i)],
                 [i for i in spaces if good(i)], spaces):
        if pool:
            return min(pool, key=lambda i: abs(i - mid))
    return None


def _split_cards(rows: list[dict]) -> list[dict]:
    f, d = _measurer()
    cards = []
    for r in rows:
        parts = [r["text"]]
        for _ in range(2):                          # 최대 2회 분할 → 최대 4장
            out = []
            for t in parts:
                if n_lines(t, f, d) <= 2:
                    out.append(t); continue
                k = split_point(t)
                out += [t[:k].strip(), t[k:].strip()] if k else [t]
            if out == parts:
                break
            parts = out
        if len(parts) == 1:
            cards.append(dict(r)); continue
        span, tot, acc = r["end"] - r["start"], sum(len(p) for p in parts), 0
        for p in parts:                             # 글자 수에 비례해 시간을 나눈다
            a = r["start"] + span * acc / tot; acc += len(p)
            b = r["start"] + span * acc / tot
            cards.append({"sentence": r["sentence"], "start": round(a, 3), "end": round(b, 3),
                          "dur": round(b - a, 3), "text": p})
    for i, c in enumerate(cards, 1):
        c["i"] = i
    bad = [c["text"] for c in cards if n_lines(c["text"], f, d) > 2]
    if bad:
        raise SystemExit(f"아직 3줄인 자막이 있다 — 문장을 짧게 고쳐라: {bad}")
    return cards


def sync_need(project: Project) -> list[dict]:
    """컷의 need 를 자막 타임코드에 맞춘다 — 컷 시작 = 첫 문장 시작, 끝 = 다음 컷 첫 문장 시작."""
    cuts = project.load_cuts()
    cards = project.load_timing()
    total = cards[-1]["end"]
    first: dict[int, float] = {}
    for c in cards:
        first.setdefault(c["sentence"], c["start"])
    for i, c in enumerate(cuts):
        s0 = 0.0 if i == 0 else first[c["sentences"][0]]
        e0 = first[cuts[i + 1]["sentences"][0]] if i + 1 < len(cuts) else total
        c["need"] = round(e0 - s0, 2)
    project.save_cuts(cuts)
    short = [c for c in cuts if c["need"] > c["len"] * 1.7]
    print(f"{len(cuts)}컷 need 갱신 · 합계 {sum(c['need'] for c in cuts):.2f}초 (나레이션 {total:.2f}초)")
    for c in short:
        print(f"  경고 C{c['n']:02d}: need {c['need']}s 인데 생성 길이 {c['len']}s — 1.7배 넘게 늘려야 한다. len 을 올려라")
    return cuts
