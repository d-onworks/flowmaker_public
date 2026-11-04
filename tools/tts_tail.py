# -*- coding: utf-8 -*-
"""더빙 일부 문장만 다시 읽혀 갈아 끼운다 — 원샷 더빙의 한두 문장만 고칠 때 (2026-11 GV90).

    python3 tools/tts_tail.py <프로젝트> --from 24            # 24번부터 끝까지 (끝이 씹히거나 잘렸을 때)
    python3 tools/tts_tail.py <프로젝트> --from 12 --to 12    # 12번 한 문장만 (대사를 고쳤을 때)

script.txt 를 먼저 고친 뒤 실행한다. 고친 범위 앞뒤 문장은 alignment.json(옛 더빙)과 글자가 같아야 한다.
범위만 같은 목소리·설정으로 따로 읽히고, narration_raw.mp3 의 그 자리(앞뒤 문장 사이 쉼의 가운데)에 갈아 끼운다.
alignment.json 도 같은 자리에서 이어 붙여 timing 이 그대로 돈다. 원본은 *.before_tail 로 남긴다.
"""
import argparse, base64, json, shutil, subprocess, sys, tempfile, urllib.request
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from flowmaker import env
from flowmaker.project import Project
from flowmaker.tts import DEFAULT_VOICE

ap = argparse.ArgumentParser(); ap.add_argument("project")
ap.add_argument("--from", dest="n", type=int, required=True); ap.add_argument("--to", dest="m", type=int)
ap.add_argument("--pad", type=float, default=0.6, help="끝까지 바꿀 때 뒤에 붙이는 무음(초)"); a = ap.parse_args()
p = Project(a.project); cfg = p.config()
lines = p.lines(p.script); m = a.m or len(lines)
head = " ".join(lines[:a.n - 1]); mid = " ".join(lines[a.n - 1:m]); rest = " ".join(lines[m:])
al = json.loads(p.alignment.read_text(encoding="utf-8"))
ch, st, en = al["characters"], al["character_start_times_seconds"], al["character_end_times_seconds"]
old = "".join(ch)
if not old.startswith(head):
    raise SystemExit("alignment 앞부분이 지금 대본과 다르다 — 범위 앞 문장을 고쳤으면 --from 을 앞당겨라")
if rest and not old.endswith(" " + rest):
    raise SystemExit("alignment 뒷부분이 지금 대본과 다르다 — 범위 뒤 문장을 고쳤으면 --to 를 늘려라")
k = len(head) + 1 if head else 0                         # 범위 첫 글자 (옛 alignment 기준)
j = len(old) - len(rest) - 1 if rest else len(old)        # 범위 바로 뒤 공백 위치
cutA = (en[k - 2] + st[k]) / 2 if head else 0.0
cutB = (en[j - 1] + st[j + 1]) / 2 if rest else None

key = env.require("ELEVENLABS_API_KEY", "")
voice = cfg.get("voice_id") or env.get("ELEVENLABS_VOICE_ID", DEFAULT_VOICE)
settings = {"stability": float(cfg.get("tts_stability", 0.45)), "similarity_boost": 0.75,
            "style": float(cfg.get("tts_style", 0.35)), "use_speaker_boost": True}
body = json.dumps({"text": mid, "model_id": env.get("TTS_MODEL", "eleven_v3"), "voice_settings": settings}).encode()
req = urllib.request.Request(f"https://api.elevenlabs.io/v1/text-to-speech/{voice}/with-timestamps?output_format=mp3_44100_128",
                             data=body, headers={"xi-api-key": key, "Content-Type": "application/json"})
res = json.load(urllib.request.urlopen(req, timeout=300))
nal = res.get("alignment") or res.get("normalized_alignment")
tmp = Path(tempfile.mkdtemp()); (tmp / "m.mp3").write_bytes(base64.b64decode(res["audio_base64"]))
nlen = nal["character_end_times_seconds"][-1]
for f in (p.narration_raw, p.alignment):
    shutil.copy(f, f.with_name(f.name + ".before_tail"))
src = p.narration_raw.with_name(p.narration_raw.name + ".before_tail")

g1 = (st[k] - cutA) if head else 0.0                      # 범위 앞 쉼(원래 쉼의 절반)
g2 = (cutB - en[j - 1]) if rest else a.pad                # 범위 뒤 쉼
filt = (f"[0:a]atrim=0:{cutA},asetpts=N/SR/TB[a];"
        f"[1:a]atrim=0:{nlen + 0.05},asetpts=N/SR/TB,adelay={int(g1*1000)}:all=1,apad=pad_dur={g2}[b];")
if rest:
    filt += f"[0:a]atrim=start={cutB},asetpts=N/SR/TB[c];[a][b][c]concat=n=3:v=0:a=1"
else:
    filt += "[a][b]concat=n=2:v=0:a=1"
subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(src), "-i", str(tmp / "m.mp3"),
                "-filter_complex", filt, "-c:a", "libmp3lame", "-b:a", "128k", str(p.narration_raw)], check=True)
off = cutA + g1
newB = off + nlen + 0.05 + g2                             # 뒷부분이 새 파일에서 시작하는 시각
d = (newB - cutB) if rest else 0.0
S = st[:k] + [t + off for t in nal["character_start_times_seconds"]]
E = en[:k] + [t + off for t in nal["character_end_times_seconds"]]
C = ch[:k] + nal["characters"]
if rest:
    C += ch[j:]; S += [t + d for t in st[j:]]; E += [t + d for t in en[j:]]
    S[len(S) - len(ch[j:])] = E[len(S) - len(ch[j:]) - 1]  # 사이 공백 시각을 앞 글자 끝에 맞춘다
assert "".join(C) == " ".join(lines), "이어 붙인 글자가 대본과 다르다"
p.alignment.write_text(json.dumps({"characters": C, "character_start_times_seconds": S,
                                   "character_end_times_seconds": E}, ensure_ascii=False), encoding="utf-8")
print(f"{a.n}~{m}문장 다시 읽음 · {len(mid)}자 · {cutA:.2f}s 부터 교체 · 뒤 문장 {d:+.2f}s 이동 · 끝 {E[-1]:.2f}s")
