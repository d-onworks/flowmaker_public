# 프롬프트 — 그림체 정본과 컷 설계

정확한 3D 영상은 좋은 프롬프트에서 나오지 않는다. **사고가 날 때마다 금지 패턴을 코드에 한 줄씩 박고,
크레딧을 쓰기 전에 그 코드가 프롬프트를 막는 데서** 나온다. 정본은 `flowmaker/style.py` 하나다.

## 1. 그림체 3종 — 꼬리 문장을 토씨 하나 안 바꾸고 붙인다

```python
from flowmaker.style import diag_tail, hist_tail, real_tail, mannequin
```

| kind | 함수 | 무엇 | 자리 |
|---|---|---|---|
| `diag` | `diag_tail()` | 질감 없는 무광 **회색 점토 모델**, 중간 회색 스튜디오 배경, 하늘·환경 없음, 좌상단 부드러운 조명 | 원리 설명 (화면의 70~85%) |
| `hist` | `hist_tail(era, palette, clothing)` | 시대 재현 실사. 시대·색·옷을 인자로 | 이야기 비트 |
| `real` | `real_tail(palette)` | 현대 현장 실사, 기본 사람 없음 | 훅·엔딩 |

프롬프트 = **본문(장면 서술) + 꼬리**. 본문은 컷마다 다르고 꼬리는 kind 마다 하나다.
왜 회색 점토인가 — "3D 단면도를 그려줘"라고 하면 모델이 매번 다른 걸 상상한다. "무광 회색 점토, 중간 회색
배경, 하늘 없음"은 해석의 여지가 없다. **정확도는 지시의 강도가 아니라 서술의 구체성에서 나온다.**

### 1-1. diag 그림 스타일 고르기 (2026-10 추가)

diag 는 편마다 그림 스타일을 고를 수 있다. 기본은 점토(clay)이고, 설정은 `projects/<편>/project.json` 의 `"style"`.

| style | 무엇 | 잘 맞는 소재 | 조심할 것 |
|---|---|---|---|
| `clay` | 회색 점토 다이어그램 (지금까지의 모든 편) | 원리·흐름 — 회색 위에 주황(열)·파랑(물)이 또렷하다 | 재료 차이(돌·흙·콘크리트)가 안 보인다 |
| `archviz` | 무채색 실사 건축 CG + 빛나는 청록 안내선·화살표 | 실제 건물·구조가 주인공인 편, 고급스러운 다큐 느낌 | 숫자·라벨은 그리게 하지 않는다(엉뚱한 글자 — 남의 쇼츠에서 색상 코드 "#00E5FF" 가 글자로 찍힌 사례). 치수는 조립에서 덧입힌다 |
| `flat` | 아이소메트릭 플랫 일러스트 | 가볍고 친근한 편, 개념 비교 | 깊이·재질이 약하다 |

2026-10-18: archviz 안내선을 '얇은 청록'에서 '굵은 청록 네온관(밝은 심 + 반투명 빛 번짐) + 큰 화살표'로 바꿨다(사용자 지적: 얇아서 잘 안 보임 · 굵어져도 투명도는 있게 · 네온사인 느낌). 역사 모드는 청록 대상(청기와·물)과 겹치지 않게 굵은 마젠타(`archviz_bold`, history_shorts/historymaker/hstyle.py).
2026-10 비교 보드(온돌 C08·C12·C14)에서 실사 재질(material)은 "너무 사실적"이라 빼고, X-ray 는 고르지 않았다.
보드: projects/ondol/build/styletest/ (지난 시험) · projects/styletest_<style>/ (지금 옵션).

- **크레딧은 스타일과 무관하다.** Flow 크레딧은 모델·길이·해상도로 정해지고 프롬프트 내용과는 상관없다. 보드도 그대로 0크레딧.
- 스타일은 프롬프트의 세 군데만 바꾼다: 첫머리 `diag_opener(style)` · 강조 문장 `accent(대상, style)` · 꼬리 `diag_tail(style)`.
  본문은 내용(구조·경로·개수)만 쓴다. 예: `diag_opener("archviz") + " of a room floor in section. … " + accent("the warm water", "archviz") + " The camera holds still." + diag_tail("archviz")`
- 새 편: `new <편> --style archviz`. 쓰던 편: `style <편> archviz` — diag 컷의 첫머리·강조·꼬리를 옮기고 이전 cuts.json 을 `build/cuts.before_archviz.json` 에 남긴다.
  클립이 이미 있으면 한 편 안에 스타일이 섞이므로 막는다(`--force` 로만).
- `check` 는 편의 스타일 꼬리로 검사하고, 다른 스타일의 말('matte grey', 'clay', '3D CG' 등)이 본문에 남으면 잡는다(규칙 11).
- **한 편 안에서는 한 스타일만.** 새 스타일은 보드부터 — 스타일마다 잘 틀리는 곳이 다르다.
  `tools/pipe_fill.py` 는 회색 바탕 기준으로 맞춘 값이라 다른 스타일에서는 `--th` 등을 다시 잡는다.

## 2. 컷 설계 — cuts.json

- Flow 는 **4·6·8·10초**만 생성한다. 크레딧 7·10·12·15.
- 컷 하나가 대본 문장 1~3개를 덮는다. `sentences` 는 1번부터 빠짐없이 이어져야 한다(`check` 가 본다).
- 컷 길이는 나레이션에서 그 문장들이 차지하는 시간(`sync-need` 가 계산하는 `need`)보다 **같거나 길게**.
  `need` 가 `len` 을 넘으면 `len` 을 한 단계 올린다(권장). 조립은 부족분을 느리게 재생해 채우는데
  1.2배까지는 티가 안 나고 **1.7배를 넘으면 거부**한다(절대 한계).
- 한 편 = 18~20컷, 크레딧 200~230.
- 본문 서술 순서: **무엇이(피사체) → 어떻게 잘렸나(단면·구도) → 무엇이 움직이나 → 카메라.**
  예) "Clean 3D CG cutaway diagram of a bridge pier sliced open so the chamber inside is visible below the
  roadway. A large solid block is already fixed to the short arm … The camera holds still on the chamber."
- 카메라는 한 문장으로 못박는다: `The camera is locked off.` / `The camera holds close and still on …` /
  `The camera orbits slowly by about thirty degrees.`

## 3. 검사 규칙 10개 — 각각 실제 사고에서 나왔다

`python -m flowmaker check <프로젝트>` 가 전부 검사하고, `submit` 이 제출 직전 한 번 더 검사한다.

| # | 규칙 | 사고 |
|---|---|---|
| 01 | 프롬프트에 **숫자 금지** | 치수 라벨을 요청하자 73m→280m, 1.2m→0.85m 로 엉뚱한 숫자를 그렸다. 수치는 자막으로 |
| 02 | 일상어와 겹치는 업계 용어 금지 — `leaf` `car` `crane` `bank` | 도개교 상판(leaf)이 **나뭇잎**으로, 엘리베이터 칸(car)이 **승용차**로 그려졌다. 생김새로 서술한다: "roadway span, a flat riveted steel deck with railings" |
| 03 | 설치 동작 금지 — `lowered onto` `dropped into` `inserted into` | 균형추를 "짧은 팔 끝에 내려놓는다"고 쓰자 추가 **상판을 뚫고 교각을 쪼갰다.** 완성 상태로 쓴다: "already fixed to the short arm, with clear space all around it" + "The roadway above stays whole and undamaged throughout" |
| 04 | 꼬리에 `Any human figure …` 조건문 금지 | 조건문이 있는 편은 **12컷 중 12컷**에 우두커니 선 마네킹이 생겼다. 없는 편은 9/9 사람 없음. 조건문은 조건이 아니라 소환이다 |
| 05 | 꼬리는 kind 별 정본과 **토씨까지 일치** (diag 전체 · hist/real 은 고정 머리·꼬리) | 편마다 꼬리를 손으로 베끼다 한 편의 예외가 다음 편의 표준이 됐다 |
| 06 | 사람이 있으면 `fully clothed` + 옷 이름 (크기 대비용 검은 실루엣은 제외) | "no bare skin"만 쓰자 **나체 마네킹**이 나왔다. 옷은 긍정문으로 입힌다 |
| 07 | 사람이 있으면 **동작 동사** 필수 | 옷을 입혔더니 이번엔 **아무것도 안 하고 서 있는** 마네킹 12컷. 사람은 ①동작을 실연하거나 ②크기 대비일 때만 |
| 08 | 실사 컷에 사람이 있으면 옷 지정 | 실사에서도 같은 이유 |
| 09 | 실사(hist+real) 화면시간 **28% 이하** | 한 편이 실사 68%로 나가자 다음 편이 그걸 복사해 43%가 됐다. 원리는 무조건 diag |
| 10 | 실사 **연속 16초 이하** | 실사가 길게 이어지면 다이어그램 채널이 아니게 된다 |

새 사고가 나면 **`style.py` 의 `check()` 에 규칙을 보탠다.** 프로젝트 폴더에만 메모하면 두 편 뒤에 증발한다.

## 4. 사람을 쓸 때

```python
body = "Clean 3D CG cutaway diagram of an ice store … " + mannequin(
    "spreads and tamps a thick layer of packed earth over the arches")
prompt = body + diag_tail()
```
- `mannequin(동작)` 은 동작 없이는 예외를 던진다. 우두커니 서 있는 사람은 만들 수 없다.
- 시대물(hist)은 `hist_tail(clothing=…)` 로 그 시대 옷을 입힌다.
- 필요 없는 컷에는 사람을 **언급 자체를 하지 않는다.** 부정문("no people")도 그 단어를 부른다 — 꼬리에서만 쓴다.

## 5. 모양은 긍정문으로, 부정문은 역효과

- 반원 아치를 원했는데 뾰족한 고딕 아치가 나왔다. `not pointed` 로는 안 고쳐졌고
  **"one smooth continuous half-round barrel of stacked stone blocks curving like the inside of a tunnel"** 로 한 번에 됐다.
- 문제 상황 컷에 `flat ceiling` 을 썼는데 모델이 알아서 아치(해답)를 그렸다. 문제 상황일수록 형태를 더 강하게 못박는다.
- "안 나오길 바라는 대상"은 언급하지 않는 문장이 가장 깨끗하다. 강조할수록 더 그린다.
- 부품은 이름이 아니라 모양으로: `wedge` → "two thick tapered steel blocks, narrow at the bottom and wide at the top".
- "멈춰 있다"는 안 먹는다 → `Nothing in the scene moves at all. The camera is locked off and completely static.`
- **창 밑 라디에이터 (2026-10 온돌 편, 두 번):** 창이 있는 방을 그리면 모델이 창 밑에 라디에이터를 알아서 넣는다.
  바닥난방 이야기에서는 치명적이다 → `the wall beneath the window is plain and bare` 로 막았다(언급하지 않고 모양으로).
- **시대 섞임 (같은 편):** 전통 구들 단면에 현대 온수관이 끼어 나왔다. 해법 이전 장면은 밑에 무엇이 있는지 모양으로 못박는다 →
  `beneath the slabs there are only open empty channels separated by low ridges of packed mud`.
- **2026-10 온돌 편 2차 검수에서 나온 것 (0.6초 간격으로 다시 보니 처음 검수에서 놓친 것들):**
  - 클립 끝에 불길이 되살아남 — 불이 관으로 바뀌는 컷의 마지막 2초에 불꽃이 다시 피었다. 뒷부분만 틀렸으면 `"until"` 로 잘라 쓴다(크레딧 0).
  - 방열기 속 뜨거운 물이 가운데 통판 하나로 나옴 → `each hollow section ... glows only inside it, the gaps between the sections stay grey`.
    위로 오르는 `warm haze` 는 굵은 주황 연기(불난 것처럼)가 됐다 → `a thin, faint, transparent shimmer`.
  - '창 불빛이 하나씩 꺼진다'가 꺼졌다 켜졌다 깜빡임으로 나옴 → `once a window goes dark it stays dark ... no window ever lights up again`.
  - '방석 놓인 바닥 단면'이 머리판·다리 달린 침대가 됨 → 판이 화면 양끝까지 이어지고 콘크리트 바닥에 붙어 있다고 모양으로 쓴다. 베개 대신 `folded quilt`.
  - '작은 기와집'만 쓰면 굴뚝 달린 서양 오두막이 나옴 → 처마 끝이 들린 기와지붕·창살 창 같은 한국 집의 모양을 적는다.
  - 실사 인물이 같은 옷으로 여럿 나오고 사라지거나 반투명해지며 순간이동 → 한 명만, `stays kneeling in exactly that same spot ... until the very end of the shot`.
    물건이 저절로 움직이는 장면도 실사에서 된다(관이 저절로 이어지는 컷).

## 5-1. 사실 컷은 구조 명세(must)부터 (2026-10 추가)

공학·고증 영상의 핵심은 원리와 구조를 **사실대로** 그리는 것이다. 상징·비유 컷과 사실 컷을 나누고, 사실 컷은 그림보다 명세를 먼저 쓴다.
- cuts.json 의 사실 컷에 `"must": ["…", "…"]` — 그림에서 반드시 맞아야 하는 것을 한 줄씩. 근거는 facts.md 에 있어야 한다.
  쓸 것: **연결**(어디서 나와 어디로 들어가나), **순서**(경로를 처음부터 끝까지), **방향**(흐름·기울기), **개수**(관 하나, 출수구 둘), **모양**(Y자형 6층),
  **상태가 바뀌는 방식**(시간이 아니라 위치로 — 흐르는 물의 온도는 경로를 따라 변한다), **없어야 할 것**(갈래·끊긴 끝·시대에 없던 물건).
- 상징 컷(사망을 꺼지는 불빛으로 등)은 `"abstract": true` — 그리는 방식은 사용자에게 묻는다. `check` 는 둘 다 없는 컷을 알려준다.
- **프롬프트는 명세를 경로·위치·개수로 풀어 쓴다.** "a single continuous pipe in a serpentine" 만으로는 나선·여러 갈래·끊긴 끝이 나왔다(온돌 편 C13·C15).
  "출구에서 내려와 → 왼쪽부터 오른쪽으로 평행 직선과 U자 굽이 → 마지막 줄에서 뒷벽을 따라 → 보일러 입구로" 처럼 순서대로 쓰고,
  "exactly one pipe … no branches, no forks, no crossings, no loose open ends" 를 붙인다.
- **보드·움직임 시트에서 명세를 한 줄씩 대조한다.** 관은 출구부터 입구까지 손가락으로 따라가듯 본다. 하나라도 틀리면 영상 크레딧을 쓰기 전에 고친다.
- 온돌 편에서 명세 없이 넘어갔다 틀린 것: 순환 색이 위치가 아니라 시간으로 한꺼번에 바뀜(C15), 지그재그 대신 나선·여러 관(C13),
  1962년 마포아파트를 상자형 건물에 층을 꿰는 관으로 그림(실제는 Y자형 6층, 층마다 따로 — C16).

## 5-2. Flow 영상이 보드를 따르지 않을 때 — 확인된 보드로 클립 만들기 (2026-10 추가)

Flow 텍스트→영상은 보드 이미지를 시작 프레임으로 쓰지 않는다. 보드가 명세에 맞아도 영상은 다시 틀릴 수 있다
(온돌 편 C13·C15·C16 — 관 경로, 순환 색, 건물 모양·층수). 구조가 핵심이고 움직임이 단순한 컷은 보드로 직접 클립을 만든다(크레딧 0).
- `tools/pipe_fill.py` — 관 속을 물이 흐르는 컷. 보드에서 관 골격을 계산해 출구부터 위치 순서대로 주황→파랑으로 채운다.
  빈 관은 회색, 흰 하이라이트·바닥 반사 없음. 빠르게 되풀이(`--period`)하거나 한 번만(`--once`).
- `tools/board_pan.py` — 보드 여러 장을 천천히 줌·이동하고 크로스페이드로 잇는다. 한 장에 명세를 다 못 담을 때(전경 → 분해도).
- 만든 클립은 clips/C##.mp4, cuts.json 에 `"unmark": false`(마크는 보드에서 이미 지움)와 `"made": "board+…"`, 실제 명령은 build/boardclip/README.txt.
- **한 장에 명세를 너무 많이 담지 않는다.** Y자 평면 + 6층 + 층별 분해를 한 장에 요구하면 보드가 매번 하나씩 틀렸다 → 장면을 둘로 나눈다.
- **보드 후보 여러 장을 한 번에**: board 전용 임시 프로젝트(projects/<편>_c##)에 후보 프롬프트를 컷 1·2·3…으로 넣고 `board <임시>` 한 번.
  이미 있는 컷은 건너뛰므로 후보를 덧붙여 다시 돌리면 새 후보만 뽑는다.
- **개수는 원본을 확대해 센다** — 층수·창 줄·발코니·관 줄. "six storeys, six rows of windows"를 줘도 Flow 이미지는 다섯 층을 그렸다(4장 중 4장).
  거의 맞는 보드는 고쳐 쓴다: 층이 하나 모자라면 정면 무늬의 세로 주기(픽셀)를 재고, 정면 한가운데를 잘라 그 아래를 한 층 내린다
  (빈 틈은 바로 위 층으로 채워짐, 원근 소실점 방향으로 내림, 무늬 없는 벽·바닥은 부드럽게 늘림 — build/boardclip/C16_add_storey.py).
- **자막 띠(화면 높이 74~82%)가 판정에 필요한 부분을 가리지 않게** 프레이밍한다. 보드 아래를 가장자리 복제로 늘려 건물을 위로 올린다.

## 6. 검수와 재생성

- `review` 가 만든 시트는 훑어보는 용도다. **판정은 `build/review/C##.png` 원본**을 열어 손·발·관절·글자·숫자를 확대해 본다.
- **움직임은 `motion_C##.png`로 본다.** 완성본에 들어가는 구간 전체를 0.6초 간격으로 깐 시트다(왼쪽 위부터).
  시작·중간·끝 3장만 보다가 온돌 편에서 불 되살아남·불빛 깜빡임·사람 순간이동·장면 바뀜을 다 놓쳤다. 컷마다 빠짐없이 본다.
  끝부분만 틀렸으면 cuts.json 에 `"until": <초>` (크레딧 0, 1.7배까지 늘림), 사이가 틀렸으면 재생성.
  축소본에서는 손가락 뭉개짐·부유 사지·엉뚱한 숫자가 안 보인다.
- 문제 컷만 `submit <p> <len> --only 3,7` 로 재생성한다. **정상 컷의 프롬프트는 건드리지 않는다** —
  공개할 프롬프트는 실제로 쓴 문구여야 한다.
- 재생성 전에 "이걸 아는 사람에게 전화로 설명한다면 무엇에 빗댈까"를 한 줄 쓰고 그 비유를 프롬프트에 넣는다.

## 7. 2026-11-01 시험에서 배운 것 (레퍼런스 @Zeronodong 비교 · 경복궁)

**시험 스타일 4종** (`flowmaker/style.py` · 편마다 `new <편> --style …`):

| style | 무엇 | 결과 |
|---|---|---|
| `archviz_clean` | archviz 에서 청록 네온 문장만 뺌 | 무겁고 칙칙하다(사용자) — 쓰지 않는다 |
| `archviz_bright` | 밝은 쇼룸 톤·매끈한 재질·옅은 그림자 | 보드는 레퍼런스처럼 깔끔. 글→영상(Omni Flash)은 반쯤만 밝아짐 → **보드→영상(frames)** 으로 쓴다 |
| `docu_real` | 실제 환경·재질·흐린 자연광·채도 뺀 색·대기 원근 | '실사에 가까운 CG 다큐'. 장소 소개·훅·엔딩용. 위 1/3 비우기를 잘 안 지킨다(배경을 채움) |
| `hero_mono` | 본문에서 이름 붙인 대상만 실사, 주변 도시·산은 단색 매스 | 신비한 건축사전식 + 실사 주인공. 장소(경복궁) 장면에 잘 맞고 고증 부담이 주인공에 모인다 |

**질감 차이는 툴보다 방식** — 같은 모델·같은 프롬프트로 글→영상(A)은 무겁게, 보드→영상(B)은 보드의 깨끗한 톤 그대로 나왔다.

**보드→영상(`frames`)** — cuts.json 컷에 `"engine": "frames"`. 보드 AI 마크는 VM 에서 지운 `build/board_clean/C##.jpg` 를 쓴다(`tools/board_pan.py` 의 `unmark`).
- ★카메라가 크게 이동하는 항공 장면은 **영상 중간에 배치가 바뀐다**(경복궁: 2.4초부터 문·개천 자리에 근정전이 하나 더 생김). 첫 프레임만 보드이고 그 뒤는 모델이 새로 그린다.
  배치가 핵심이고 움직임이 단순한 장면은 `tools/board_pan.py` 로 보드에서 직접 만든다(크레딧 0, 배치 그대로). frames 는 카메라 이동이 작은 장면에.

**실제 장소를 그릴 때 (경복궁 보드 3장 비교)**
- 이름만 → 대표 모습(광화문·근정전)만 맞고 위치(경회루)는 엉뚱.
- 모양·순서·개수로 풀어 쓰기 → 위치 관계 대부분 맞음, 세부 순서(개천이 흥례문 뒤) 틀림.
- 풀어 쓰기 + **배치 스케치 참고 이미지**(cuts.json `"ref": "refs/layout.png"`) → 순서·위치까지 맞음. ★고증 장소 장면의 기본.
  스케치는 위에서 본 평면(위=북), 글자 없이 색 덩어리로. 프롬프트에 "배치만 따르고 색·그림체는 따르지 말 것"을 쓴다.
- 참고 이미지 붙이기: '+'(aria "Add ingredients to the prompt box") → Upload → **올라가는 % 가 끝날 때까지** 기다린 뒤 파일 이름으로 골라 '프롬프트에 추가' → 프롬프트 상자에 붙은 그림이 방금 올린 한 장인지 확인. 전 컷의 재료 그림은 매 컷 지운다(`clear_ingredients`).

**회수(collect) 매칭** — Flow 상세 화면은 ' 를 ’ 로 보여준다 → 따옴표를 맞춰 비교. 영상 프롬프트가 같은 컷이 둘이면 이번에 찾는 컷을 고른다(`prefer`).

**자막** — 지금 크기(44px)로는 12자 안팎이 한 줄 한계. 사용자 원칙은 한 줄 자막이라 subtitles.txt 에 ` / ` 로 직접 나눈다(zero15). 기본값(두 줄까지 허용)을 한 줄로 바꿀지는 미정.

## 8. 장면 전환 — 전경에서 세부로는 빠른 줌인 (2026-11 사용자 원칙)

사용자: "경복궁 전경을 보여주고 빠르게 근정전으로 줌인해서 근정전 클로즈업에서 다음 이야기로. 천천히 움직일 특별한 이유가 없으면 빠른 화면 전환으로 지루하지 않게."

**컷 계획(스토리보드)에서 정한다** — 이야기가 '전체 → 그 안의 한 부분'으로 넘어가는 곳(궁궐 → 정전, 건물 → 방, 기계 → 부품, 지도 → 한 지점)은
두 컷을 한 쌍으로 짠다:
- 앞 컷 = **전경 보드**(뒤 컷의 대상이 화면 안에 또렷이 보이게, 그 자리를 must 에 적는다)
- 뒤 컷 = **클로즈업 보드**(같은 방향에서 본 모습. 전경 보드의 그 부분을 잘라 `"ref"` 로 붙이면 같은 건물로 나온다)
- 뒤 컷에 `"zoom_from": {"cut": <앞 컷>, "target": [x, y], "to": 3.2}` — target 은 전경 보드 좌표.
- 전환 속도는 **빠르게가 기본**(줌 0.6~0.8초, 줌 블러). 천천히 다가갈 이유(공간의 크기를 느끼게 하는 장면 등)가 있을 때만 느리게 — 그때는 이유를 desc 에 적는다.
- 카메라가 크게 이동하는 전환을 Flow 영상(글→영상·frames)에 맡기지 않는다 — 중간에 배치가 바뀐다(경복궁 frames 시험). 두 보드로 직접 만든다:
  `python3 tools/zoom_cut.py clips/tmp.mp4 --wide build/board/C03.jpg --close build/board/C04.jpg --target 408,512 --to 3.2 --hold <앞 컷 need − 줌> --zoom 0.7 --close-sec <뒤 컷 need> --split`
  → `tmp_a.mp4`(전경+줌, 앞 컷) · `tmp_b.mp4`(클로즈업, 뒤 컷)를 clips/C03.mp4 · C04.mp4 로 두고 두 컷 모두 `"unmark": false`, `"made": "board+zoom_cut"`.
- 클로즈업 컷 안에서도 멈춰 있지 않게 계속 천천히 다가간다(zoom_cut 이 1.10→1.16). 더 움직임이 필요하면 클로즈업 보드에서 frames(카메라 이동이 작은 장면이라 배치가 지켜진다)로 만든다.

**8-1. 시점이 바뀌는 전환은 Flow 시작·끝 장면으로 (2026-11-01 경복궁, 사용자 판정)**
- 드론 전경 → 정면 클로즈업처럼 **시점(높이·각도)이 바뀌면 2D 줌(zoom_cut)으로는 안 된다** — 확대 → 바꿔치기가 "중간에 끊어진 느낌"(사용자).
- `frames` 컷에 `"frames": {"start": "build/board_clean/C03.jpg", "end": "build/board_clean/C04.jpg"}` — Flow 가 두 보드 사이를 3D 비행으로 이어 그린다(4초 7크레딧).
  경복궁 C05: 남쪽 하늘 → 축을 따라 흥례문·개천·근정문 위를 지나 → 근정전 정면에 도착. 중간 배치(문 순서) 유지, 끝 프레임이 C04 보드와 일치.
  끝 장면이 정해져 있어서 시작 장면만 줄 때(경복궁 C03 frames)와 달리 중간에 건물이 생기지 않았다.
- 뒤 컷은 끝 장면 보드(C04)로 바로 이어 붙인다(board_pan 으로 천천히 다가감) — 이음매가 보이지 않는다.
- 프롬프트: "one continuous drone flight … dives down quickly along the central axis … arrives low in front … buildings stay exactly where they are; only the camera moves."
- zoom_cut 은 **같은 각도**에서 가까이 가는 전환(지도 → 한 지점, 단면 → 부품 확대)에만 쓴다.
