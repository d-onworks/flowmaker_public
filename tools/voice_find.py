# -*- coding: utf-8 -*-
"""ElevenLabs 목소리 후보 찾기 (2026-11 GV90 편: '더 젊고 딕션 좋고 빠른 목소리').

  list <편> [--gender male|female|any] [--n 30]
      공유 목소리 라이브러리에서 한국어·젊은 목소리를 찾아 미리듣기(무료, 크레딧 0)를 내려받고
      projects/<편>/build/voices/voices.html 에 목록·재생기를 만든다.
  try <편> <번호…>
      list 결과의 번호로 고른 후보를 내 목소리 라이브러리에 추가하고(이미 있으면 건너뜀),
      같은 대본 앞 세 문장을 eleven_v3 로 읽혀 build/voices/try_<번호>.mp3 · 초당 글자 수를 남긴다.
      (크레딧: 후보당 대본 앞 세 문장 글자 수만큼)
  add <편> <이름>
      공유 라이브러리에서 이름으로 찾아(언어 무관) 목록 끝 번호로 붙인다 — 예: 외국인 목소리를 한국어로 읽혀 보기.
  use <편> <번호>
      project.json 에 "voice_id" 를 적는다 → 이후 tts 가 그 목소리를 쓴다(.env 보다 우선).
"""
from __future__ import annotations
import base64, html, json, sys, urllib.parse, urllib.request
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from flowmaker import env  # noqa: E402

API = "https://api.elevenlabs.io"


def _req(method, path, body=None):
    key = env.require("ELEVENLABS_API_KEY")
    data = json.dumps(body).encode() if body is not None else None
    r = urllib.request.Request(API + path, data=data, method=method,
                               headers={"xi-api-key": key, "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(r, timeout=120) as f:
            return json.load(f)
    except urllib.error.HTTPError as e:
        raise SystemExit(f"ElevenLabs 오류 {e.code} {path}: {e.read().decode(errors='ignore')[:300]}")


def _dir(p):
    d = Path(__file__).resolve().parents[1] / "projects" / p / "build" / "voices"
    d.mkdir(parents=True, exist_ok=True)
    return d


def cmd_list(p, gender="any", n=30):
    d = _dir(p)
    seen, out = set(), []

    def korean(v):
        # language=ko 로 물어도 '한국어도 읽을 수 있는' 다국어 목소리(영어 원어민)가 섞여 온다 → 주 언어가 한국어인 것만
        if (v.get("language") or "").lower().startswith("ko"):
            return True
        return False

    for uc in ("informative_educational", "narrative_story", "social_media", "conversational", "advertisement", None):
        for page in range(5):
            q = {"page_size": 100, "page": page, "language": "ko", "age": "young", "sort": "usage_character_count_1y"}
            if gender != "any":
                q["gender"] = gender
            if uc:
                q["use_cases"] = uc
            res = _req("GET", "/v1/shared-voices?" + urllib.parse.urlencode(q))
            vs = res.get("voices", [])
            for v in vs:
                if v["voice_id"] in seen or not korean(v):
                    continue
                if gender != "any" and v.get("gender") != gender:
                    continue
                # 한국어 미리듣기가 따로 있으면 그것을 쓴다
                for vl in v.get("verified_languages") or []:
                    if (vl.get("language") or "").startswith("ko") and vl.get("preview_url"):
                        v["preview_url"] = vl["preview_url"]
                seen.add(v["voice_id"]); out.append(v)
            if not res.get("has_more"):
                break
    out.sort(key=lambda v: -(v.get("usage_character_count_1y") or 0))
    out = out[:n]
    rows = []
    for i, v in enumerate(out, 1):
        f = d / f"preview_{i:02d}.mp3"
        if f.exists():
            f.write_bytes(b"")   # 이전 목록의 파일이 남으면 번호가 어긋난다(2026-11 사고) — 비우고 새로 받는다
        if v.get("preview_url"):
            try:
                urllib.request.urlretrieve(v["preview_url"], f)
            except Exception as e:  # 미리듣기가 없는 목소리도 있다
                print(f"  {i:02d} 미리듣기 실패: {e}")
        rows.append({"no": i, "voice_id": v["voice_id"], "owner": v.get("public_owner_id"), "name": v.get("name"),
                     "gender": v.get("gender"), "age": v.get("age"), "accent": v.get("accent"),
                     "use_case": v.get("use_case"), "descriptive": v.get("descriptive"),
                     "description": (v.get("description") or "")[:200],
                     "usage_1y": v.get("usage_character_count_1y"), "cloned": v.get("cloned_by_count"),
                     "free_ok": v.get("free_users_allowed"), "preview": f.name if f.exists() and f.stat().st_size > 0 else None})
        print(f"{i:02d} {v.get('name')[:28]:28} {v.get('gender'):6} {v.get('age'):6} {str(v.get('use_case')):24} {str(v.get('descriptive')):14} 사용 {v.get('usage_character_count_1y')}")
    (d / "voices.json").write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
    h = ["<meta charset=utf-8><title>목소리 후보</title><style>body{font:15px sans-serif;max-width:900px;margin:20px auto}"
         "td{padding:6px;border-bottom:1px solid #ddd;vertical-align:top}</style><h2>목소리 후보 (주 언어 한국어·젊은 목소리)</h2><table>"]
    for r in rows:
        a = f"<audio controls preload=none src='{r['preview']}'></audio>" if r["preview"] else "(미리듣기 없음)"
        h.append(f"<tr><td><b>{r['no']:02d}</b></td><td><b>{html.escape(r['name'] or '')}</b><br>{r['gender']} · {r['age']} · "
                 f"{r['use_case']} · {r['descriptive']}<br><small>{html.escape(r['description'])}</small></td><td>{a}</td></tr>")
    (d / "voices.html").write_text("\n".join(h) + "</table>", encoding="utf-8")
    print(f"\n→ {d/'voices.html'} (브라우저로 열어 들어 보세요) · 후보 {len(rows)}개 · 크레딧 0")


def _rows(p):
    return {r["no"]: r for r in json.loads((_dir(p) / "voices.json").read_text(encoding="utf-8"))}


def _ensure_in_library(r):
    mine = {v["voice_id"] for v in _req("GET", "/v1/voices").get("voices", [])}
    if r["voice_id"] in mine:
        return r["voice_id"]
    res = _req("POST", f"/v1/voices/add/{r['owner']}/{r['voice_id']}", {"new_name": f"fm_{r['name']}"[:40]})
    return res.get("voice_id", r["voice_id"])


def cmd_try(p, nos):
    root = Path(__file__).resolve().parents[1] / "projects" / p
    lines = [l.strip() for l in (root / "script.txt").read_text(encoding="utf-8").splitlines() if l.strip()][:3]
    text = " ".join(lines)
    rows = _rows(p); d = _dir(p)
    settings = {"stability": 0.45, "similarity_boost": 0.75, "style": 0.35, "use_speaker_boost": True}
    print(f"시험 문장 {len(text)}자 × {len(nos)}명 = 약 {len(text)*len(nos)}자 크레딧")
    for no in nos:
        r = rows[no]; vid = _ensure_in_library(r)
        res = _req("POST", f"/v1/text-to-speech/{vid}/with-timestamps?output_format=mp3_44100_128",
                   {"text": text, "model_id": env.get("TTS_MODEL", "eleven_v3"), "voice_settings": settings})
        (d / f"try_{no:02d}.mp3").write_bytes(base64.b64decode(res["audio_base64"]))
        al = res.get("alignment") or res.get("normalized_alignment")
        sec = al["character_end_times_seconds"][-1]
        r["try_voice_id"] = vid; r["try_sec"] = round(sec, 2); r["try_cps"] = round(len(text) / sec, 2)
        print(f"{no:02d} {r['name'][:28]:28} {sec:5.2f}초 · 초당 {len(text)/sec:.2f}자 → try_{no:02d}.mp3")
    allr = list(rows.values()); (d / "voices.json").write_text(json.dumps(allr, ensure_ascii=False, indent=1), encoding="utf-8")
    print("참고: 현재 목소리는 초당 약 6.06자(766자/126.5초)")


def cmd_add(p, name):
    res = _req("GET", "/v1/shared-voices?" + urllib.parse.urlencode({"page_size": 30, "search": name, "sort": "usage_character_count_1y"}))
    vs = [v for v in res.get("voices", []) if (v.get("name") or "").lower().startswith(name.lower())]
    if not vs:
        raise SystemExit(f"'{name}' 로 시작하는 공유 목소리가 없다")
    v = max(vs, key=lambda v: v.get("usage_character_count_1y") or 0)
    rows = _rows(p); no = max(rows) + 1
    rows[no] = {"no": no, "voice_id": v["voice_id"], "owner": v.get("public_owner_id"), "name": v.get("name"),
                "gender": v.get("gender"), "age": v.get("age"), "accent": v.get("accent"), "language": v.get("language"),
                "use_case": v.get("use_case"), "descriptive": v.get("descriptive"), "description": (v.get("description") or "")[:200],
                "usage_1y": v.get("usage_character_count_1y"), "preview": None}
    (_dir(p) / "voices.json").write_text(json.dumps(list(rows.values()), ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{no:02d} {v.get('name')} ({v.get('language')} · {v.get('accent')}) 추가")
    return no


def cmd_use(p, no):
    r = _rows(p)[no]
    cfg = Path(__file__).resolve().parents[1] / "projects" / p / "project.json"
    j = json.loads(cfg.read_text(encoding="utf-8")); j["voice_id"] = r.get("try_voice_id") or r["voice_id"]; j["voice_name"] = r["name"]
    cfg.write_text(json.dumps(j, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{p} 목소리 → {r['name']} ({j['voice_id']})")


if __name__ == "__main__":
    a = sys.argv[1:]
    if not a:
        raise SystemExit(__doc__)
    if a[0] == "list":
        g = a[a.index("--gender") + 1] if "--gender" in a else "any"
        n = int(a[a.index("--n") + 1]) if "--n" in a else 30
        cmd_list(a[1], g, n)
    elif a[0] == "try":
        cmd_try(a[1], [int(x) for x in a[2:]])
    elif a[0] == "add":
        cmd_add(a[1], " ".join(a[2:]))
    elif a[0] == "use":
        cmd_use(a[1], int(a[2]))
    else:
        raise SystemExit(__doc__)
