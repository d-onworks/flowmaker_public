# -*- coding: utf-8 -*-
"""효과음·배경음악 — ElevenLabs 생성 API. 둘 다 선택 사항이다.

sfx.json (프로젝트 폴더)
    [{"name": "01_horn", "prompt": "A deep low ship horn ...", "duration": 4.0, "influence": 0.5,
      "sentence": 1, "offset": 0.2, "volume": 0.48}, ...]
    sentence  붙일 문장 번호 (자막 카드 번호가 아니다 — 카드는 쪼개지면 번호가 밀린다)
    offset    그 문장 시작에서 몇 초 뒤(음수면 앞)
    원칙: 서사 포인트에만, 컷당 1개 이하.

배경음악
    bgm.mp3 를 프로젝트 폴더에 두면 조립에 쓴다. 없으면 `music` 명령으로 만들 수 있다
    (ElevenLabs 음악 API 는 유료 플랜 전용이다. 무료 플랜이면 저작권 확인된 파일을 직접 넣어라).
"""
from __future__ import annotations

import concurrent.futures as cf
import json
import urllib.request

from . import env
from .project import Project


def _post(url: str, body: dict, key: str) -> bytes:
    req = urllib.request.Request(url, data=json.dumps(body).encode(),
                                 headers={"xi-api-key": key, "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=300) as r:
        return r.read()


def generate(project: Project) -> bool:
    """sfx.json 의 효과음을 전부 만든다. 하나라도 실패하면 False (다시 실행하면 된 것은 건너뛴다)."""
    if not project.sfx_path.exists():
        print("sfx.json 없음 — 효과음 없이 간다")
        return True
    key = env.require("ELEVENLABS_API_KEY")
    plan = json.loads(project.sfx_path.read_text(encoding="utf-8"))
    out_dir = project.build / "sfx"
    out_dir.mkdir(parents=True, exist_ok=True)

    def one(s):
        dst = out_dir / f"{s['name']}.mp3"
        if dst.exists():
            return (s["name"], "있음(건너뜀)")
        try:
            audio = _post("https://api.elevenlabs.io/v1/sound-generation",
                          {"text": s["prompt"], "duration_seconds": float(s.get("duration", 4.0)),
                           "prompt_influence": float(s.get("influence", 0.5))}, key)
            dst.write_bytes(audio)
            return (s["name"], "ok")
        except Exception as e:
            return (s["name"], str(e)[:120])

    with cf.ThreadPoolExecutor(max_workers=3) as ex:
        results = list(ex.map(one, plan))
    failed = [n for n, st in results if st not in ("ok", "있음(건너뜀)")]
    for n, st in results:
        print(f"  {n}: {st}")
    if failed:
        print(f"실패 {len(failed)}건 — 키·크레딧을 확인하고 `sfx` 를 다시 실행하라 (된 것은 건너뛴다)")
        return False
    return True


def music(project: Project, prompt: str, seconds: int = 100) -> None:
    key = env.require("ELEVENLABS_API_KEY")
    print(f"배경음악 생성 중 ({seconds}초) …")
    audio = _post("https://api.elevenlabs.io/v1/music",
                  {"prompt": prompt, "music_length_ms": int(seconds * 1000)}, key)
    project.bgm.write_bytes(audio)
    print(f"→ {project.bgm.name}")
