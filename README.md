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
| Python 3.10+ | 도구 실행 | python.org (윈도우는 설치할 때 **Add python.exe to PATH** 를 꼭 켜세요) |
| ffmpeg / ffprobe | 조립·검수 | **`setup` 이 깝니다** (직접 하려면 macOS `brew install ffmpeg` · Windows `winget install Gyan.FFmpeg` · Ubuntu `apt install ffmpeg`) |
| Chrome (권장) | Flow 조작 | 없으면 플레이라이트 내장 크로미엄을 씁니다 |
| **구글 Flow 크레딧** | 영상 생성 | Google AI Pro/Ultra 구독 크레딧(비구독 계정도 소량의 일일 크레딧이 있습니다). 한 편(20컷) ≈ 200~230 크레딧 — **Omni Flash · 720p 기준 실측**이며 모델·해상도·등급에 따라 다르니 Flow 화면의 현재 단가를 확인하세요 |
| **ElevenLabs API 키** | 더빙·효과음 | https://elevenlabs.io 무료 플랜도 됩니다(월 10,000 크레딧 ≈ 6~10편). **무료 플랜은 비상업용** — 수익화하려면 유료 플랜. 배경음악 생성(`music`)은 **유료 플랜 전용**이라 무료면 음악 파일을 직접 넣습니다 |

## 설치

**macOS · Windows · Linux 공통 — 두 줄이면 끝납니다.**

```bash
git clone https://github.com/d-onworks/flowmaker_public.git
cd flowmaker_public
python3 -m flowmaker setup          # Windows PowerShell 은 python -m flowmaker setup
```

`setup` 이 알아서 합니다 — 가상환경(`.venv`) 만들기 · 파이썬 패키지 · 플레이라이트 크로미엄 ·
**ffmpeg**(macOS `brew` · Windows `winget`/`choco`/`scoop` · Linux `apt`/`dnf`/`pacman`) ·
`.env` 복사 · 자막 폰트 내려받기 · 마지막에 환경 점검.

끝나면 안내대로 가상환경을 켜고 로그인합니다.

```bash
source .venv/bin/activate           # Windows: .\.venv\Scripts\Activate.ps1
# .env 를 열어 ELEVENLABS_API_KEY 를 채웁니다 (없어도 컷 생성까지는 됩니다)
python3 -m flowmaker login          # 창이 뜨면 구글 로그인 (한 번만)
```

> `--dry-run` 을 붙이면 무엇을 실행할지 보여주기만 합니다. `--no-ffmpeg` 은 ffmpeg 설치를 건너뜁니다.
> 패키지 관리자가 없어 ffmpeg 자동 설치가 안 되면 `setup` 이 받는 곳을 알려주고 나머지는 계속 진행합니다.

<details>
<summary>윈도우에서 막힐 때 (실측으로 확인된 것들)</summary>

- **`py -3` 이 아무 말 없이 끝난다** — 런처가 버전을 못 찾는 상태입니다. `py -0` 으로 잡히는 버전을 보고 `py -3.12` 처럼 콕 집어 부르거나, 그냥 `python` 을 쓰세요.
- **`python` 이 Microsoft Store 를 연다** — 0바이트짜리 가짜 실행파일(앱 실행 별칭)입니다. python.org 설치본을 **Add python.exe to PATH** 를 켜고 까세요.
- **`.venv` 만들기가 pip 단계에서 실패한다** — `setup` 이 알아서 `--without-pip` 로 다시 만들고 pip 만 따로 붙여 봅니다. 그래도 안 되면 가상환경 없이 지금 파이썬에 깔고 계속 진행합니다. 설치 자체는 끝납니다.
- **pip 이 `WinError 448 … 신뢰할 수 없는 탑재 지점` 으로 죽는다** — 파이썬이 아니라 **PATH 에 깨진 폴더가 섞인 것**입니다. 그 PC의 모든 pip 설치가 같이 깨집니다. `setup` 은 `--no-warn-script-location` 으로 피해 가지만, 근본 해결은 환경변수에서 그 항목을 지우는 것입니다.
- **ffmpeg 을 방금 깔았는데 `doctor` 가 못 찾는다** — PATH 반영이 안 된 것입니다. **새 터미널**을 열고 다시 확인하세요.

</details>
> 윈도우에서 ffmpeg 을 방금 깔았다면 PATH 반영을 위해 **새 터미널**을 열고 `python -m flowmaker doctor` 로 확인하세요.
> 패키지 관리자가 없어 ffmpeg 자동 설치가 안 되면 `setup` 이 받는 곳을 알려주고 나머지는 계속 진행합니다.

<details>
<summary>손으로 설치하기 (setup 을 쓰지 않을 때)</summary>

macOS / Linux
```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python3 -m playwright install chromium
brew install ffmpeg                 # Ubuntu: sudo apt install ffmpeg
cp .env.example .env
python3 -m flowmaker doctor
```

Windows (PowerShell)
```powershell
python -m venv .venv; .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m playwright install chromium
winget install --id Gyan.FFmpeg -e
Copy-Item .env.example .env
python -m flowmaker doctor
```
</details>

(아래 예시는 `python3` 로 씁니다. Windows 는 `python` 으로 읽으면 됩니다.)

`login` 창에서 로그인한 뒤, **프로젝트를 하나 열어 생성 설정을 '동영상 · 세로 9:16 · 출력 1개'로 한 번 맞춰 두세요.**
Flow 가 계정별로 기억하므로 이후 자동 제출이 그 설정으로 나갑니다. 드라이버는 길이만 고르고, 칩에 `9:16` 이 안 보이면 경고합니다.

키 없이 되는 범위: 소재·대본·컷 계획·`check`·Flow 생성·`review` 까지. 더빙(`tts`)·효과음(`sfx`)·조립부터는 ElevenLabs 키가 필요합니다.

테스트를 돌리려면 `pip install -r requirements-dev.txt && python3 -m pytest` (55개). macOS 15 / Windows 11(한국어·cp949) 양쪽에서 통과를 확인했습니다.

## 에이전트에게 말하기

Claude Code 나 Codex 를 이 폴더에서 열고:

```
실행해                → 환경 점검, 부족한 건 알아서 설치
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
flowmaker/           도구 — style(그림체 정본·검사) · flow_driver(플레이라이트) · tts · timing · subtitles · sfx · assemble · review · setup/doctor(환경)
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
