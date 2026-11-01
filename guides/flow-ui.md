# Flow 화면 — 드라이버가 의존하는 것과 고치는 법

`flowmaker/flow_driver.py` 는 구글 Flow(https://labs.google/fx/ko/tools/flow) 를 플레이라이트로 조작한다.
Flow 화면은 예고 없이 바뀐다. 그래서 CSS 선택자·좌표가 아니라 **버튼에 적힌 글자**로 요소를 찾는다.

## 드라이버가 찾는 글자 (`TEXT` 표)

| 키 | 정규식 | 화면에서 |
|---|---|---|
| `dismiss` | `^(시작하기|Get started|닫기|Close|확인|OK)$` | 첫 진입 공지 모달의 버튼 |
| `new_project` | `새 프로젝트|New project` | 프로젝트 목록의 새 프로젝트 버튼 |
| `mode_chip` | `동영상 ·|Video ·` | 프롬프트 입력창 옆 생성 설정 칩 ("동영상 · 8s · …") |
| `length` | `^{len}s$` | 설정 칩을 열면 나오는 길이 버튼 4s/6s/8s/10s |
| `send` | `arrow_forward` | 전송 버튼(머티리얼 아이콘의 글자) |

프롬프트 입력창은 `[contenteditable="true"]` 첫 번째 요소다.

## 생성 설정은 계정이 기억한다 — login 창에서 한 번 맞춘다
드라이버는 **길이만** 고른다(4s/6s/8s/10s). 모드(동영상)·비율(세로 9:16)·출력 개수(1)는 Flow 가 계정별로
기억하는 설정이라, `login` 창에서 프로젝트를 하나 열어 한 번 맞춰 둔다. 드라이버는 설정 칩 글자를 읽어
`{len}s` 가 없으면 제출하지 않고, `9:16` 이 없으면 경고한다. 출력 개수가 1이 아니면 `collect` 가
"동영상이 제출 수보다 많다"로 멈춘다 — 회수 매핑이 틀릴 수 있어 일부러 진행하지 않는다.

## 제출 흐름
1. Flow 열기 → 공지 닫기 → Escape
2. **새 프로젝트** 클릭 → URL 을 기록(이게 회수 열쇠)
3. 설정 칩 → 길이 버튼 → 칩 글자에 `{len}s` 가 들어갔는지 확인. **안 들어갔으면 제출하지 않고 중단**
4. 컷마다: 입력창 클릭 → 전체 선택·삭제 → 프롬프트 타이핑 → 입력된 글자 수 확인 → 전송 → 3.5초 대기
5. **전송에 성공한 컷 번호만** `build/submit_{len}s.json` 의 `order` 에 즉시 기록. 일부만 됐으면 종료코드 3 과 재제출 명령 안내

## 회수 흐름
1. 저장된 URL 열기 → 11초 대기 → 맨 아래로 스크롤
2. `<video>` 개수가 제출 수보다 적으면 **종료코드 2** (아직 생성 중) — 2~3분 뒤 다시. **많으면 중단**(출력 개수 설정 의심)
3. 각 video 의 src 를 fetch 해 최종 CDN 주소를 얻어 내려받는다
4. **화면 순서는 최신이 위** → 제출 순서의 역순으로 `C##.mp4` 에 매핑

길이 그룹(4/6/8/10)마다 프로젝트를 따로 만드는 이유: 한 프로젝트에 길이가 섞이면 매핑이 틀릴 수 있다.

## 화면이 바뀌어 안 될 때

1. `python -m flowmaker login` 으로 창을 띄워 실제 화면을 본다 (또는 `submit` 을 `--headless` 없이 돌려 어디서 멈추는지 본다).
2. 못 찾는다고 찍힌 요소의 **지금 글자**를 확인한다.
3. `flow_driver.py` 의 `TEXT` 표에서 그 정규식만 고친다. 한국어·영어를 `|` 로 같이 받아둔다.
4. 입력창이 `contenteditable` 이 아니게 됐으면 `submit()` 안의 그 한 줄을 고친다.
5. 고친 뒤 `--only` 로 컷 하나만 제출해 확인한다(크레딧 7~15).

좌표를 박거나 긴 CSS 경로를 쓰지 마라 — 다음 변경에서 또 깨진다.

## 계정·비용
- 구글 Flow 는 Google AI Pro/Ultra 구독의 크레딧을 쓴다. 로그인은 사용자가 창에서 직접 한다.
- 길이별 크레딧: 4초 7 · 6초 10 · 8초 12 · 10초 15 (Omni Flash · 720p 기준 실측 — 모델·해상도·등급에 따라 다르다). 한 편 20컷 ≈ 200~230.
- 자동화로 계정이 제한될 가능성은 사용자 몫이다. 무인 반복 생성은 하지 않는다 — 사용자가 시킨 편만.

## 2026-10 Flow 개편 메모 (실측)

- 주소가 `flow.google.com` 으로 옮겨졌다(예전 주소는 그리로 넘어간다).
- 새 프로젝트를 열면 오른쪽에 **AI 에이전트 대화창**이 열려 아래 프롬프트 상자를 가릴 수 있다 → `close_agent_panel()` 이 닫는다
  (aria-label `Close`/`닫기` + 같은 패널 안 '세션' 버튼으로 찾는다).
- 설정 칩 글자: 영어 `Video · 720p · 8s crop_9_16 x1` · 한국어 `동영상 · 720p · 8초 crop_9_16 x1`.
  비율은 글자 대신 아이콘 이름(`crop_9_16`)으로 나온다.
- 칩을 열면 라디오 버튼: 이미지/동영상 · 프레임/소재 · 16:9/9:16 · 모델(Omni 1.1 Flash) · 360p/720p ·
  **4초/6초/8초/10초**(영어 4s…) · x1~x4. 메뉴 아래에 "생성 시 N 크레딧이 사용됩니다" — 단가는 예전과 같다(8초 x1 = 12).
- 드라이버는 이제 동영상 모드 · 길이 · **x1** 을 매번 직접 고르고, 칩에 x1 이 없으면 제출하지 않는다.
- **넓은 창(1440px)에서는 새 프로젝트가 '에이전트' 모드로 열린다.** 프롬프트 상자에 설정 칩 대신 '에이전트 요청 사항'·'설정(tune)'
  버튼만 보인다. 상자 왼쪽의 `에이전트` 알약 버튼을 누르면 꺼지고 칩이 나타난다 → `ensure_direct_mode()` 가 처리한다.

### 2026-10 추가 실측 (2컷 테스트 3차 실패 원인)
- **설정은 브라우저 프로필마다 따로 기억된다.** 플레이라이트 프로필(~/.flowmaker/profile)은 `🍌 Nano Banana 2.1 crop_16_9 x2`
  (이미지 · 16:9 · x2)로 남아 있었다 → 칩 글자가 `동영상 ·` 로 시작하지 않아 못 찾음. 그래서 이제 `configure_video()` 가 매번 전부 맞춘다.
- 설정 칩은 **aria-label `설정 트리거` / `Settings trigger`** 로 찾는다(글자는 모드마다 바뀜). 에이전트 모드의 `tune` 버튼은 aria `설정` 이라 안 걸린다.
- 패널 버튼(전부 `<button role=radio>`, 선택 = aria-checked=true): `image 이미지`/`videocam 동영상`, `crop_free 프레임`/`chrome_extension 소재`,
  `crop_16_9 16:9`/`crop_9_16 9:16`, 모델 `Omni 1.1 Flash arrow_drop_down`(aria `모델 제품군 선택`/`Select model family`),
  `360p`/`720p`, `4초…10초`(영어 `4s…`), `x1…x4`.
- 모델 메뉴(`role=menuitem` 버튼): `volume_up Omni 1.1 Flash` · `Veo 3.1 - Lite` · `Veo 3.1 - Fast` · `Veo 3.1 - Quality`.
  크레딧(720p, x1): Omni 1.1 Flash 4초 7 · 6초 10 · 8초 12 · 10초 15 / Veo 3.1 - Fast 4초 20.
- 패널 아래 `생성 시 N 크레딧이 사용됩니다` / `Generating will use N credits` — 드라이버가 N 을 읽어 CREDITS 표와 다르면 제출하지 않는다.

### 2026-10 회수(collect) 실측
- 결과 격자에는 `<video>` 가 없다. 썸네일 `<img alt="생성된 동영상 썸네일 | Generated video thumbnail">` 만 있고 최신이 왼쪽(위).
- 썸네일을 누르면 `/project/<id>/edit/<asset>` 상세 화면. **창 폭 1440 에선 canvas 편집기(동영상 태그 없음)**,
  **800 폭에선 `<video src="https://flow-content.google/video/<uuid>?Expires…&Signature…">`** (720×1280, 실제 길이) + 생성 프롬프트 전문이 보인다.
- 그래서 collect 는 800×1000 으로 열고, 썸네일을 하나씩 열어 영상 주소와 프롬프트를 읽은 뒤 **프롬프트로 컷을 매핑**한다(`match_prompts`).

## board — 스토리보드 대표 이미지 (이미지 모드, 2026-10 추가 · 아직 실측 전)
- `board <p> [--only 3,7] [--max-credit N] [--redo]` — 컷마다 같은 프롬프트로 **이미지 모드 · 9:16 · x1** 한 장을 뽑아
  `build/board/C##.<jpg|png|webp>` 에 둔다. 설정 패널 화면은 `build/board/board_settings.png`, 기록은 `board.json`.
- 크레딧 안전장치: 패널의 '생성 시 N 크레딧'이 0 이면 진행, 1 이상이거나 표시가 없으면 **보내지 않고** 멈춘다
  → 사용자가 확인한 뒤 `--max-credit N` 으로 다시.
- 회수는 alt 글자 대신 "전송 전에 없던 큰 이미지(원본 256px 이상)"를 찾는다 — 이미지 결과 격자의 alt 를 실측하면
  `TEXT` 에 넣고 `pick_new_image()` 를 alt 기준으로 바꾼다.
- 이미지 모델(Nano Banana)과 동영상 모델(Omni Flash)은 다르다. 보드는 **구도·단어 해석** 확인용이다.

### 2026-10-18 프레임(첫·끝 장면) 모드 조사 — history_shorts/tools/probe_flow_frames.py (전송 없음)
- 화면 글자가 **영어**로 나오기도 한다(같은 프로필): `Frames`/`Ingredients`, `Generating will use N credits`, 전송 aria `Start generation`.
- 동영상 · **Frames** 를 고르면 프롬프트 상자 위에 **`Start` · `End` 칸**과 `Swap first and last frames` 버튼이 생긴다.
- 4초 x1 720p 크레딧(Frames): Omni 1.1 Flash **7**(글만 넣을 때와 같음) · Veo 3.1 Lite 10 · Fast 20 · Quality 100.
- 이미지 모드(Nano Banana 2.1)는 프롬프트 상자 왼쪽 `+`(aria `Add ingredients to the prompt box`)로 참고 이미지를 넣는다 — 0 크레딧.
- 화면에 처음부터 `input[type=file]` 은 없다 → 칸을 눌러 나오는 업로드 메뉴를 찾아야 한다(2차 조사: probe_flow_frames2.py).

### 2026-10-18 Veo 3.1 프레임 모드 실측(history_shorts/tools/flow_frames_submit.py --model veo-fast)
- 프레임 모드에서 모델을 `Veo 3.1 - Fast` 로 바꾸면 **길이·해상도 버튼이 사라지고 8초 · 720p 고정**(칩 `Video · 720p · 8s crop_9_16 x1`), 20 크레딧.
- 위 '4초 … Veo 3.1 Lite 10 · Fast 20 · Quality 100' 은 실제로는 8초 값이었다(길이를 못 바꾼 채 읽음). Lite·Quality 는 다시 볼 것.
- 그래서 Veo 는 컷 길이(4·6초)와 맞지 않는다 → 샘플(--sample)로만 받고, 필요한 구간을 잘라 쓴다.

## 2026-11 — 편마다 Flow 프로젝트 하나

- 사용자 결정: 이미지(board)와 동영상(submit)을 편마다 **한 Flow 프로젝트**에서 만든다. 전에는 부를 때마다 '새 프로젝트'를 만들어 목록이 흩어졌다.
- 처음 board/submit 때 만든 프로젝트 주소가 `projects/<편>/project.json` 의 `"flow_url"` 에 적힌다(`open_flow_project`). 이후에는 그 주소를 연다. 열리지 않으면(지운 프로젝트 등) 새로 만들어 주소를 바꿔 적는다.
- 한 격자에 이미지·다른 길이 그룹·버린 클립이 섞이므로 collect 는 개수로 매핑하지 않는다: 최신 썸네일부터 열어 프롬프트로 컷을 찾고(`match_prompts`), 이미 받아 간 클립(`build/flow_seen.json` 의 taken)에 닿으면 멈춘다(`plan_collect`). 한 번 연 썸네일은 flow_seen.json 에 기억해 다시 열지 않는다.
- 새 편부터 일부러 새 프로젝트로 시작하려면 project.json 의 flow_url 을 지운다.
- **프로젝트 이름 = 편 제목.** `project.json` 의 `"title"`(`new <편> --title "…"` · `title <편> "…"`, 없으면 폴더 이름)을 Flow 프로젝트를 열 때 이름으로 바꾼다(`ensure_flow_title`). 바뀐 게 확인되면 `"flow_titled"` 에 적고 다음부터 건너뛴다.
  2026-11 실측: 머리글 왼쪽 `home <이름> more_vert` 의 `<input aria-label="Editable text">`(기본값 'Nov 01 - 15:17' 같은 날짜). 클릭 → 전체 선택 → 입력 → Enter 로 바뀐다. 오른쪽 검색칸(aria Search)은 제외.
  실패해도 생성은 계속하고 `build/flow_title_probe.json`(머리글 후보 목록) · `flow_title_fail.png` 를 남긴다. 그걸 보고 `pick_title_candidate` 규칙을 고친다.
