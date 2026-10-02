# 자동 분류 검증 2차 (계획, 표본 추출 전에 고정)

이 문서는 표본을 뽑기 전에 커밋한다. 표본 추출과 판정 뒤에는 이 문서의 규칙을 바꾸지 않는다.

## 목적
수정된 분류기(PR #102 병합 커밋 `f2fb1a288514a35f2b171fb1ae513e40a79dc304`, #101)의 **첫 이탈 단계** 판정을 독립 AI 평가자의 판정과 비교한다.

## 모집단
- 조건 1·2·4·5의 실행 중 `agent_error`가 참인 것 (수정 후 분류, `outputs/analysis/classified.jsonl`, sha256 `f7a5e2de78882f203cb72473ec1ef307026d1b55a0d7708f36db70fdbac95ef1`).
- 1차 표본(`outputs/analysis/human_sample/human_order.csv`의 110건, sha256 `bfe91adc1bcb116184474a8c3e4085161df9980905e1bf4a66273a1e55e814f1`)은 뺀다.
- `first_deviation_stage_name`이 비어 있는 실행은 없어야 한다(있으면 추출을 멈추고 보고).

## 표본
- 층 = (조건, 수정 후 첫 이탈 단계). 목표 총 100건, 시드 `20261002`.
- 배분: 모든 층에 `min(3, 층 크기)`건을 먼저 주고, 남는 몫(100 − 합)을 `층 크기 − 이미 준 건수`에 비례해 최대잔여법으로 나눈다(동률은 층 키 `(조건, 단계)` 오름차순). 층 크기를 넘기지 않는다. 모집단이 100건을 넘으므로 총 100건이 된다.
- 층 안에서는 `run_id` 순으로 정렬한 뒤 `random.Random(f"{시드}:ai_check2:{조건}:{단계}")`로 섞어 앞에서 뽑는다.
- 판정 순서는 뽑힌 실행을 `run_id` 순으로 정렬한 뒤 `random.Random(f"{시드}:ai_check2:order")`로 섞은 순서다. 층이 순서에서 드러나지 않는다.

## 평가자와 절차
- 평가자는 새 세션의 AI다. 보는 것은 `outputs/analysis/ai_check2/`의 `check.html`(질문, 정답 해석, 정답 풀이와 허용 대안 풀이, 에이전트가 받은 상자로 정답 풀이를 다시 실행한 경로와 도달 가능한 답, 에이전트 기록)과 같은 폴더에서 참조하는 `guide.html`(1차와 같은 기준표)뿐이다.
- 자동 라벨(`ai_check2_KEY/`), 분류 코드, 1차 결과, 연습 문항, 기대 답 힌트는 주지 않는다.
- 실행마다 첫 이탈 단계 하나를 고른다. 선택지는 1차와 같다: `interpretation, tool_selection, result_reading, planning_branch, calculation, answer_formatting, exec_fail, unknown`.
- 내보내기 CSV는 1차와 같은 형식이다(열 `rank, run_id, human_first_deviation, human_note`). 확신도는 메모의 맨 앞에 `[high]`, `[medium]`, `[low]` 중 하나로 적는다.

## 지표
- 단계 일치율, 코헨 카파, 단계별 혼동 행렬, 확신도별 일치율.
- 카파의 95% 구간은 **실행 단위** 부트스트랩(B = 10,000, 시드 `20261002`, 백분위 구간)이다. 장면 묶음 단위가 아니다.
- 제외 규칙은 없다. 판정한 모든 실행을 센다.

## 보고 방침
- 1차(110건)는 분류기 구현 오류 4곳을 찾은 **점검 단계**로 보고한다.
- 2차를 **검증 결과**로 보고한다.
- 2차 결과를 본 뒤에는 분류 코드를 바꾸지 않는다.

## 결과

계획대로 계산했다(제외 없음, 분류 코드는 바꾸지 않음). 입력: `outputs/analysis/ai_check2_out/ai_labels2.csv`(sha256 `58b2b94f5ec25cb54f71e6137593ad163b464f4906bdf88bf681d0afd7b86c78`, 100건), 키 `outputs/analysis/ai_check2_KEY/ai_check2_key.csv`. 코드 `analysis/validation_round2.py`, 결과 CSV는 `outputs/analysis/ai_check2_out/`. 부트스트랩은 실행 단위, 10,000회, 시드 20261002, 백분위 95% 구간.

### 주 결과 (100건)
- 일치율 **30/100 = 0.300**
- 코헨 카파 **0.137** (95% 구간 0.043 ~ 0.234)

혼동 행렬 (행 = AI, 열 = 자동 분류, `confusion.csv`):

| AI \ 자동 | answer_formatting | calculation | exec_fail | interpretation | planning_branch | result_reading | tool_selection |
|---|---|---|---|---|---|---|---|
| answer_formatting | 0 | 0 | 0 | 0 | 0 | 1 | 0 |
| calculation | 0 | **7** | 0 | 10 | 0 | 0 | 24 |
| exec_fail | 0 | 0 | **4** | 7 | 0 | 0 | 0 |
| interpretation | 0 | 0 | 7 | **5** | 0 | 0 | 1 |
| planning_branch | 0 | 0 | 0 | 8 | 0 | 0 | 0 |
| result_reading | 0 | 0 | 0 | 2 | 0 | 0 | 0 |
| tool_selection | 0 | 0 | 0 | 10 | 0 | 0 | **14** |

단계별 일치 (`by_stage.csv`):

| 단계 | 자동 건수 | AI 건수 | 둘 다 같음 |
|---|---|---|---|
| interpretation | 42 | 13 | 5 |
| tool_selection | 39 | 24 | 14 |
| calculation | 7 | 41 | 7 |
| exec_fail | 11 | 11 | 4 |
| result_reading | 1 | 2 | 0 |
| planning_branch | 0 | 8 | 0 |
| answer_formatting | 0 | 1 | 0 |

확신도별 일치율 (`by_confidence.csv`, 메모 맨 앞의 태그):

| 확신도 | 건수 | 일치 | 일치율 |
|---|---|---|---|
| high | 42 | 15 | 0.357 |
| medium | 48 | 12 | 0.250 |
| low | 10 | 3 | 0.300 |

조건별 일치율 (`by_condition.csv`):

| 조건 | 건수 | 일치 | 일치율 |
|---|---|---|---|
| 1 | 26 | 10 | 0.385 |
| 2 | 18 | 7 | 0.389 |
| 4 | 34 | 8 | 0.235 |
| 5 | 22 | 5 | 0.227 |

### 보조 결과 (97건, 보조임)
기준표(guide.html)의 단계별 예시로 쓰인 3건(rank 16 `f3a256b2f40e2d15`, rank 19 `2ed629eaa0dc18e9`, rank 38 `4380d06cf046efe7`)을 뺐다. 계획에 없던 보조 분석이고 주 결과는 위의 100건이다.
- 일치율 **27/97 = 0.278**, 코헨 카파 **0.112** (95% 구간 0.021 ~ 0.207)

### 불일치 분석
불일치 70건. 건수가 많은 칸 상위 4개(`disagreement_cells.csv`, 전체 목록은 `disagreements.csv`). 자동 코드는 자동 분류의 첫 이탈을 만든 판정 코드이다. 대표 rank는 해당 칸에서 rank가 가장 작은 2개이다.

| 칸 (AI / 자동) | 건수 | 자동 판정 코드 | 대표 rank |
|---|---|---|---|
| calculation / tool_selection | 24 | extra_call 12, missing_call 11, wrong_args 1 | 1, 6 |
| calculation / interpretation | 10 | interpretation_mismatch 10 | 5, 8 |
| tool_selection / interpretation | 10 | interpretation_mismatch 10 | 35, 45 |
| planning_branch / interpretation | 8 | interpretation_mismatch 8 | 10, 31 |

AI 메모의 요지 (각 칸의 메모를 읽은 요약; 판단이 아니라 메모 내용):
- **calculation / tool_selection (24):** `missing_call` 11건의 메모는 대부분 "turn 1 plan의 calc 인자 `$s2.ships.long_side_px` 참조 오류(c3 error), 호출 구성은 정답 풀이와 같음"이다(rank 1, 6 등). `extra_call` 12건의 메모는 "사분면별 `detect_ships`로 개수는 맞게 읽었으나 `calc` 없이 스스로 세어 답함"이나 "turn 10 `calc argmax` list가 목록의 목록"이다(rank 7, 20 등).
- **calculation / interpretation (10):** 메모는 "해석 target=pair_distance(정답 longest_neighbor_distance)이나 plan은 argmax+nearest_to로 정답 풀이대로라 무해로 봄"이고, 이어서 `calc` 참조 오류를 든다(rank 5, 8 등). AI는 해석 불일치를 무해로 보았다.
- **tool_selection / interpretation (10):** 메모는 "turn 1 count 조회 없이 nearest_pair 호출, decision condition_value {count:0} 임의값"(rank 35, 45 등 7건)이나 "image_stats region=noisiest_region(error) 후 사분면별 호출 없음"(2건)이다. AI는 해석이 아니라 도구 선택을 첫 이탈로 보았다.
- **planning_branch / interpretation (8):** 메모는 "turn 1 plan if rhs가 문자열(\"4\", \"3\"), decision chosen=null, 받은 값으로는 then(또는 else)이어야 함"이고 "해석 branch=null은 이 값에서 결과 같아 무해"를 곁들인 것도 있다(rank 10, 31 등). 일괄 계획에서 조건값이 문자열이라 분기가 실행되지 않은 경우이다.

### 해석 시 유의
- 일치율 0.300, 카파 0.137은 위 정의(실행 단위 부트스트랩, 10,000회)로 계산한 값이다. 단계별 건수 분포가 달라 불일치가 한 방향에 몰려 있다(자동은 해석 42건, AI는 해석 13건).
- 1차(110건)는 구현 오류를 찾은 점검 단계이고 이 결과가 검증 결과이다. 이 결과를 본 뒤에도 분류 코드는 바꾸지 않는다.
