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

## 6. 검수와 재생성

- `review` 가 만든 시트는 훑어보는 용도다. **판정은 `build/review/C##.png` 원본**을 열어 손·발·관절·글자·숫자를 확대해 본다.
  축소본에서는 손가락 뭉개짐·부유 사지·엉뚱한 숫자가 안 보인다.
- 문제 컷만 `submit <p> <len> --only 3,7` 로 재생성한다. **정상 컷의 프롬프트는 건드리지 않는다** —
  공개할 프롬프트는 실제로 쓴 문구여야 한다.
- 재생성 전에 "이걸 아는 사람에게 전화로 설명한다면 무엇에 빗댈까"를 한 줄 쓰고 그 비유를 프롬프트에 넣는다.
