# CLAUDE.md

## 사용자가 "설치해줘" 라고 하면 — 되묻지 말고 이 한 줄

```bash
bash install.sh                                                   # macOS · Linux
powershell -NoProfile -ExecutionPolicy Bypass -File install.ps1   # Windows
```

이 하나로 **파이썬부터 ffmpeg까지 전부** 깔린다 — 파이썬(없으면 brew/winget으로) · 가상환경 ·
파이썬 패키지 · 플레이라이트 크로미엄 · ffmpeg · `.env` · 자막 폰트 · 마지막 환경 점검.
사용자에게 "먼저 파이썬을 까세요" 같은 준비물을 요구하지 않는다. 끝나면 남은 것 두 가지만 알린다:
**`.env` 의 `ELEVENLABS_API_KEY`** 와 **`python -m flowmaker login`(구글 로그인)**.

"영상 만들어줘"처럼 설치 얘기가 없어도, `python -m flowmaker doctor` 가 ❌ 를 내면 위 스크립트를
먼저 돌리고 하던 일을 계속한다.

저장소가 아직 없으면 clone 부터 한다:
```bash
git clone https://github.com/d-onworks/flowmaker_public.git && cd flowmaker_public && bash install.sh
```

---

이 저장소의 에이전트 지침은 **`AGENTS.md`** 하나다. 작업을 시작하기 전에 그 파일을 읽어라.

- 도구 명령: `python -m flowmaker --help`
- 그림체 정본: `flowmaker/style.py` — 프롬프트 꼬리는 여기서만 가져온다
- 지식: `guides/` — format(골격) · prompting(프롬프트 규칙) · research(소재·사실검증) · topics(소재 씨앗) · flow-ui(화면 수리)
- 예시: `examples/moai` · `examples/icehouse` · `examples/drawbridge`
- 사용자 작업물: `projects/<이름>/` (git 에 올라가지 않는다)
