# 그래픽 (도표·화살표·라벨) — HyperFrames 로 만들어 조립에서 얹기

2026-11 온돌 편 C17(1:18~1:26, 연표 + 보일러 가구 막대)로 확인한 방법. 사용자 원칙:
도표·화살표가 필요한 영상에는 모션 그래픽을 넣어 화면을 풍성하게 하고, **메인 이미지는 처음부터 그래픽 자리를 비워 두고 배치한다.**

## 1. 언제 넣나

- 숫자·연도·비율·비교(A 대 B)·순서·흐름이 나오는 문장. 한 편 2~4곳.
- 정지에 가까운 컷(카메라 고정·보드로 만든 컷)에 우선. 움직이는 그림 위에 대상을 가리키는 화살표를 얹으면 어긋난다 — 그런 컷은 패널형 도표(화면 빈 곳에 독립된 판)만.
- **숫자는 facts.md 에 있는 것만.** 해마다 이어지는 곡선 데이터가 없으면 곡선을 그리지 않는다(연표 표시 + 실제 값 막대로). 개념 곡선이 꼭 필요하면 화면에 '개념도'라고 적는다.
- 어떤 도표로 보여줄지는 혼자 정하지 않는다 — 2~3안을 미리보기와 함께 AskUserQuestion 으로 묻는다.

## 2. 컷 계획에서

cuts.json 그 컷에:

```json
"graphic": {"src": "graphics/C17.mov", "at": 0}
```

- `src` 는 프로젝트 폴더 기준, `at` 은 컷 안 시작 초(생략 0). 그래픽 길이는 컷 끝에서 자동으로 잘린다.
- 메인 이미지 프롬프트에 그래픽 자리를 비우라고 쓴다. 예: "the upper third of the frame is plain empty mid-grey studio background with nothing in it; the subject sits in the lower half".
- 화면 자리(720×1280): 상단 UI y≤110 피하기 · 자막 띠 y 950~1050(74~82%) 피하기 · 출처 줄 y≈1062~1086. 패널형 도표는 보통 y 70~450.

## 3. 보드에서

보드 이미지 위에 그래픽 자리를 반투명 상자로 그린 시트를 같이 보여준다(가리는 것이 없는지 영상 크레딧 전에 확인). 대상이 그 자리로 들어와 있으면 프롬프트를 고친다.

## 4. 만들기 — `projects/<편>/graphics/C##/`

본보기: `projects/ondol/graphics/C17/` 를 통째로 복사해서 시작한다
(`index.html` · `package.json` · `hyperframes.json` · `meta.json` · `assets/fonts/NotoSansKR-{400,500,700,900}.woff`).

index.html 규칙 (어기면 check 가 실패하거나 화면이 튄다):

- `<div id="root" data-composition-id="main" data-start="0" data-duration="<need>" data-width="720" data-height="1280">`, 안의 요소는 `class="clip" data-start data-duration`.
- **배경을 칠하지 않는다** — `html, body { background: transparent }`. 칠하면 알파가 사라진다.
- 글꼴은 프로젝트 안 파일만: `@font-face { font-family: "KRSans"; src: url("assets/fonts/…woff") }`. 시스템 글꼴(Apple SD Gothic Neo 등)은 쓰지 않는다 — 52MB 가 통째로 들어가 미리보기가 시간 초과로 멈췄다.
- GSAP 는 transform·opacity(x·y·scale·scaleY·rotation·opacity)와 SVG stroke-dashoffset 만 움직인다. top·height 같은 레이아웃 값은 프레임마다 튄다(check 오류 gsap_non_transform_motion).
- 한 개의 paused 타임라인을 `window.__timelines["main"]` 에 등록. Math.random·Date.now·네트워크 금지.
- 시각은 `subtitle_timing.json` 의 문장 시작 − 컷 시작으로 잡는다(말과 동시에 뜨게).
- 읽는 글자 19px 이상. 일부러 작은 출처 줄은 `data-layout-ignore`.
- 색: 강조 주황 #ff8a1f(온수) · 경고 빨강 #ff5a4d · 막대 #ffb35c · 패널 rgba(22,22,22,.72) — 편 소재 색과 겹치면 바꾼다.

## 5. 렌더 (사용자 맥, Node 22+ · ffmpeg)

```
cd ~/AI/flowmaker_public/projects/<편>/graphics/C## && { npx hyperframes check; npx hyperframes render --format mov --output ../C##.mov; } 2>&1 | tee render_log.txt
```

- MOV = ProRes 4444(알파 있음). `--prores-profile` 을 주면 알파가 사라진다.
- 확인: `render_log.txt` 의 `Check passed`, `ffprobe` pix_fmt 가 `yuva444p12le`, 프레임을 RGBA 로 뽑아 빈 곳 알파 0.

## 6. 조립

`assemble` 이 그래픽을 클립 위·자막 아래에 얹는다. 위치는 need 합이 아니라 **인코딩된 컷의 실제 길이**로 센다(프레임 반올림이 쌓여 C17 에서 0.05초 어긋났다).
확인: 컷 경계 앞뒤 0.05초 프레임 — 앞 컷·다음 컷에 그래픽이 남지 않는지, 자막을 가리지 않는지.
