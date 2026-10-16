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
