# -*- coding: utf-8 -*-
"""원샷 더빙 — 대본 전체를 한 번에 읽혀 톤을 일정하게 유지하고, 글자 단위 타임스탬프를 받는다.

왜 한 번에 읽히나
    문장마다 따로 부르면 문장마다 톤·속도가 흔들려 기계 티가 난다.
    한 테이크로 뽑고, 길이 조절은 나중에 통째로 배속(timing 단계)만 건다.

모델 메모 (실측)
    eleven_v3 는 speed 인자를 무시한다. 그래서 길이는 대본 글자 수로 잡아야 한다.
    v3 원본이 목표 길이의 1.3배를 넘으면 배속이 커져 음이 올라간다 → 대본을 줄여라.
"""
from __future__ import annotations

import base64
import json
import urllib.request

from . import env
from .project import Project

DEFAULT_VOICE = "JBFqnCBsd6RMkjVDRZzb"     # ElevenLabs 기본 제공 목소리 중 하나. .env 로 바꿔 쓸 것


def synthesize(project: Project) -> dict:
    key = env.require("ELEVENLABS_API_KEY", "https://elevenlabs.io 에서 발급(무료 플랜도 API 키가 나온다)")
    voice = env.get("ELEVENLABS_VOICE_ID", DEFAULT_VOICE)
    model = env.get("TTS_MODEL", "eleven_v3")
    lines = project.lines(project.script)
    flat = " ".join(lines)                      # 개행 대신 공백 — 한 테이크 유지

    settings = {"stability": 0.45, "similarity_boost": 0.75, "style": 0.35, "use_speaker_boost": True}
    if model != "eleven_v3":
        settings["speed"] = float(env.get("TTS_SPEED", "1.1"))
    body = json.dumps({"text": flat, "model_id": model, "voice_settings": settings}).encode()
    req = urllib.request.Request(
        f"https://api.elevenlabs.io/v1/text-to-speech/{voice}/with-timestamps?output_format=mp3_44100_128",
        data=body, headers={"xi-api-key": key, "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=300) as r:
            res = json.load(r)
    except urllib.error.HTTPError as e:
        raise SystemExit(f"ElevenLabs 오류 {e.code}: {e.read().decode(errors='ignore')[:300]}")

    project.narration_raw.write_bytes(base64.b64decode(res["audio_base64"]))
    al = res.get("alignment") or res.get("normalized_alignment")
    project.alignment.write_text(json.dumps(al, ensure_ascii=False), encoding="utf-8")
    total = al["character_end_times_seconds"][-1]
    print(f"더빙 저장 · {model} · 글자 {len(flat)}자 · 원본 길이 {total:.2f}초 → {project.narration_raw.name}")
    return {"chars": len(flat), "seconds": total, "model": model}
