# 예시 3편

| 폴더 | 소재 | 컷 | 그림체 |
|---|---|---|---|
| `moai` | 모아이 석상 운반 — 머리만 있는 게 아니고, 걸어서 갔다 | 18 | diag 15 · real 3 |
| `icehouse` | 석빙고 — 얼음이 아니라 녹은 물을 상대했다 | 20 | diag 15 · hist 3 · real 2 |
| `drawbridge` | 타워브리지 도개교 — 들어올리는 게 아니라 기울인다 | 20 | diag 15 · hist 2 · real 3 |

각 폴더: `script.txt`(TTS용) · `subtitles.txt`(화면용) · `cuts.json`(프롬프트) · `facts.md`(사실 검증) · `sfx.json`(효과음, 있는 편만).
`python -m flowmaker new <이름> --from moai` 로 복사해 시작할 수 있다.

메모
- 세 편 모두 `python -m flowmaker check` 를 통과한다(`tests/test_project.py` 가 보증).
- `drawbridge` 의 상판 표현은 원래 `leaf`(도개교 업계 용어)였는데, 한 컷에서 **나뭇잎**이 그려진 뒤
  `roadway span` 으로 바꿨다. 예시에는 전 컷을 그 표현으로 맞춰 두었다 — 정본 규칙 02 의 사례다.
- `moai` 의 다이어그램은 석상이 주인공이라 `figure`·`hands` 가 나오지만 사람이 아니다. 크기 대비와
  군중은 `silhouette`(검은 실루엣)로 표현한다 — 옷 검사 대상이 아니고, 동작이나 `for scale` 은 있어야 한다.
