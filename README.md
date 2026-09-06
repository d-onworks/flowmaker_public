# flowmaker

구글 Flow 로 컷을 생성하고, ElevenLabs 로 더빙하고, ffmpeg 으로 조립해서
**세로 90초 건축·공학 설명 영상**을 만드는 작업장입니다.
회색 점토 3D 다이어그램으로 원리를 잘라 보여주는 그림체이고, 조회수 수백만 편의 지식 쇼츠를
컷·대본·오디오 단위로 실측해 뽑은 양식을 그대로 따릅니다.

이 저장소는 **AI 코딩 에이전트(Claude Code, Codex 등)가 조작하도록** 만들어졌습니다.
사람은 에이전트에게 말하고, 에이전트가 `AGENTS.md` 를 읽고 대본·프롬프트·생성·조립을 수행합니다.
직접 명령어로 쓸 수도 있습니다.

## 준비물

| 무엇 | 왜 | 어디서 |
|---|---|---|
| Python 3.10+ | 도구 실행 | python.org |
| ffmpeg / ffprobe | 조립·검수 | macOS `brew install ffmpeg` · Ubuntu `apt install ffmpeg` · Windows ffmpeg.org |
| Chrome (권장) | Flow 조작 | 없으면 플레이라이트 내장 크로미엄을 씁니다 |
| **구글 Flow 크레딧** | 영상 생성 | Google AI Pro/Ultra 구독 크레딧(비구독 계정도 소량의 일일 크레딧이 있습니다). 한 편(20컷) ≈ 200~230 크레딧 — **Omni Flash · 720p 기준 실측**이며 모델·해상도·등급에 따라 다르니 Flow 화면의 현재 단가를 확인하세요 |
| **ElevenLabs API 키** | 더빙·효과음 | https://elevenlabs.io 무료 플랜도 됩니다(월 10,000 크레딧 ≈ 6~10편). **무료 플랜은 비상업용** — 수익화하려면 유료 플랜. 배경음악 생성(`music`)은 **유료 플랜 전용**이라 무료면 음악 파일을 직접 넣습니다 |

## 설치

macOS / Linux
```bash
git clone https://github.com/d-onworks/flowmaker_public.git
cd flowmaker_public
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python3 -m playwright install chromium
cp .env.example .env               # ELEVENLABS_API_KEY 를 채운다
python3 -m flowmaker doctor        # 환경 점검 + 자막 폰트 내려받기
python3 -m flowmaker login         # 창이 뜨면 구글 로그인 (한 번만)
```

Windows (PowerShell)
```powershell
git clone https://github.com/d-onworks/flowmaker_public.git
cd flowmaker_public
py -3 -m venv .venv; .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
py -3 -m playwright install chromium
Copy-Item .env.example .env        # ELEVENLABS_API_KEY 를 채운다
py -3 -m flowmaker doctor
py -3 -m flowmaker login
```
(아래 예시는 `python3` 로 쓴다. Windows 는 `py -3` 로 읽으면 된다.)

`login` 창에서 로그인한 뒤, **프로젝트를 하나 열어 생성 설정을 '동영상 · 세로 9:16 · 출력 1개'로 한 번 맞춰 두세요.**
Flow 가 계정별로 기억하므로 이후 자동 제출이 그 설정으로 나갑니다. 드라이버는 길이만 고르고, 칩에 `9:16` 이 안 보이면 경고합니다.

키 없이 되는 범위: 소재·대본·컷 계획·`check`·Flow 생성·`review` 까지. 더빙(`tts`)·효과음(`sfx`)·조립부터는 ElevenLabs 키가 필요합니다.

테스트를 돌리려면 `pip install -r requirements-dev.txt && python3 -m pytest`.

## 에이전트에게 말하기

Claude Code 나 Codex 를 이 폴더에서 열고:

```
실행해                → 환경 점검, 부족한 것 안내
소재 찾아줘           → 후보 3~5개 (반전 한 줄 + 검증 난이도)
도개교로 만들자        → 사실 검증 → 대본 → 확인 요청
영상 생성해           → 컷 계획 → 정본 검사 → Flow 제출 → 회수 → 검수
조립해               → 자막·효과음·조립 → projects/<이름>/final.mp4
```

에이전트는 크레딧을 쓰기 전에 예상량을 알리고, 프롬프트가 정본 검사를 통과하지 못하면 제출하지 않습니다.

## 직접 명령어로

```bash
python3 -m flowmaker new bridge --from drawbridge   # 예시 복사로 시작
python3 -m flowmaker check bridge                   # 형식 + 그림체 정본 검사 (크레딧 0)
python3 -m flowmaker tts bridge                     # 더빙
python3 -m flowmaker timing bridge --target 100     # 배속 + 자막 타임코드
python3 -m flowmaker sync-need bridge               # 컷 길이를 나레이션에 맞춤
python3 -m flowmaker submit bridge 8                # 8초 컷들을 Flow 에 제출
python3 -m flowmaker collect bridge 8               # 몇 분 뒤 회수 (덜 됐으면 종료코드 2)
python3 -m flowmaker review bridge                  # 프레임 검수 시트
python3 -m flowmaker subs bridge && python3 -m flowmaker sfx bridge
python3 -m flowmaker assemble bridge                # → projects/bridge/final.mp4
python3 -m flowmaker status bridge                  # 어디까지 됐나
```

## 폴더

```
AGENTS.md            에이전트 지침 (사람도 읽으면 전체 절차가 보입니다)
flowmaker/           도구 — style(그림체 정본·검사) · flow_driver(플레이라이트) · tts · timing · subtitles · sfx · assemble · review
guides/              지식 — format(90초 골격) · prompting(프롬프트 규칙) · research(소재·사실검증) · topics(씨앗 30) · flow-ui(화면 수리)
examples/            완성 편 3개: moai(모아이) · icehouse(석빙고) · drawbridge(도개교) — 대본·자막·컷·프롬프트·사실검증
projects/            내 작업물 (git 에 올라가지 않음)
tests/               정본 검사·형식·타이밍·조립 테스트
```

프로젝트 폴더 규약과 `cuts.json` 형식은 `flowmaker/project.py` 머리말에 있습니다.

## 그림체 정본이 핵심입니다

`flowmaker/style.py` 하나가 그림체 꼬리 문장 3종과 검사 규칙 10개를 가집니다.
규칙은 전부 실제 사고에서 나왔습니다 — 나뭇잎으로 그려진 다리 상판, 승용차가 된 엘리베이터 칸,
옷을 안 적어서 나온 나체 마네킹, 구조물을 뚫고 내려간 균형추. 사고가 나면 여기에 규칙을 한 줄 보탭니다.
프로젝트 폴더에만 메모하면 두 편 뒤에 잊힙니다. 자세한 건 `guides/prompting.md`.

## 주의

- **AI 생성물임을 밝히세요.** 사실적인 장면이 섞이므로 설명글에 "AI로 만든 3D 애니메이션" 한 줄, 유튜브라면 「AI 사용」 고지를 켜는 것을 권합니다.
- Flow 자동 조작은 구글 약관과 계정 상태에 대한 책임이 사용자에게 있습니다. 무인 반복 생성은 하지 마세요.
- 대본의 수치·연도는 반드시 1차 자료로 확인하세요(`guides/research.md`). 예시의 `facts.md` 가 그 기록입니다.

## 라이선스

MIT. 자막 폰트 Pretendard 는 SIL Open Font License 이며 설치 시 내려받습니다.
