# PROTOCOL.md

이 파일은 `freeze-v1` 태그 시점의 **최종본**이다(동결 목표 10/1, SPEC 일정은 10/4). 동결 뒤에는 이 파일도 수정하지 않는다. 데이터 파일의 SHA-256은 실행기가 test 실행을 시작할 때 실제 파일과 대조한다 (SPEC §0-3).
동결 뒤에는 이 파일도 수정하지 않는다. 데이터 파일의 SHA-256은 실행기가 시작할 때 실제 파일과 대조한다.

## 1. 데이터 해시 (SHA-256)

| 파일 | 상태 | SHA-256 |
|---|---|---|
| `splits/scenes.json` | 확정 (M5) | `9cbb465d6cfbeaf1d33ea7ee4c74d20fcdce05d13b986e717ff1c6ddd3f05433` |
| `splits/splits.json` | 확정 (M5) | `6dc6266ac307ed04cb96eb982868ea797cb3a3bbebb3f75eb11b55468604d3f8` |
| `splits/splits_report.json` | 확정 (M0) | `fd6928fa404a32d1c0c6a5d90c256b818b9f43a4bd97fb28c52818d7d4631b7f` |
| `outputs/detector/weights.pt` | 확정 (M5) | `2d2bab8cbfe7f10181ac6501959dcc7c86b30b23cda7497e09711ae260a35ca6` |
| `data/detections/dev.json` | 확정 (M1) | `883487083bf1e0618e8abdf79fa7de148d36c322067aa7d1705ffea947437a06` |
| `data/detections/test.json` | 확정 (M5) | `b082f6cd08c892ddbe027894c1482c606077e57ffc3db1f5e4b2275121b50d42` |
| `data/questions/test.json` | 확정 (M5) | `4f89cd03f2401e3fe326df1581bd56f75ce582b1f6bac0cef811e1e46f85330e` |
| `data/injected/test_miss.json` | 확정 (M5) | `bc98f752b642e4376451519457f43d6ddbbd343a5e40fa368f1404c8226f57a7` |
| `data/injected/test_fp.json` | 확정 (M5) | `3decb9aaef0a8697062a048e8bc56bcf5fb8ae6886616eca172b96fb273f3759` |
| `data/injected/test_loc.json` | 확정 (M5) | `b5885aa2108e4ddf0181236bdbd521a874780ff6a553ed8d954799a9ce7ae074` |
| `data/corrected/test_miss.json` | 확정 (M5) | `f1ec2af609718ba1a4d19852250878953b3845c5fdd8bce2f945a5119fbba51f` |
| `data/corrected/test_fp.json` | 확정 (M5) | `5648b2aeef7c5c98a8fa735e9689d12b373ddd10184cbf286cad79b54c05d508` |
| `data/corrected/test_loc.json` | 확정 (M5) | `ca87ecf96b14500c469bbadc87ecabc7da3ace605b3c7177c145612a4e7b3094` |

검증: `sha256sum splits/*.json` 결과가 위 표와 같아야 한다. 해시를 바꿔야 하면 이유를 기록하고 전체를 다시 실행한다.

## 2. 분할 (SPEC §4.2, 상세는 `docs/data_notes.md` §10~11)

- 라벨 기준 파일: `data/hrsid/HRSID_JPG/annotations/train_test2017.json`. 공식 train/test 파일은 쓰지 않는다.
- 묶음 134개 = 원본 장면 133개(바이트 동일 영상을 공유하는 3쌍 병합) + `G0137`(`P0137_*` 109장, `det_train` 전용).
- 묶음 수: det_train 88 (`G0137` 포함), det_val 13, **dev 10, test 23** (평가 묶음 33).
- 영상 수: det_train 3,722, det_val 527, dev 393, test 962. 시드 25.
- 공식 파일과 상자 수가 다른 26장은 질문 후보에서 제외 (검출기 학습·검증에는 사용).

## 3. 상자 매칭과 오류 정의 (`configs/classify.yaml`)

- IoU ≥ 0.5 그리디(IoU 큰 쌍부터) 일대일 매칭. 누락 = 매칭 안 된 라벨, 오탐 = 매칭 안 된 탐지, 위치·크기 오차 = 매칭 쌍 중 IoU < 0.75.

## 4. 탐지기 (SPEC §4.3; 상세는 `configs/default.yaml`의 `detector`)

- torchvision `fasterrcnn_resnet50_fpn`, COCO 사전학습에서 시작, 클래스 2개. HRSID 학습 가중치는 쓰지 않는다.
- 학습: `det_train` 3,722장, 20 에폭, 배치 4, SGD lr 0.01(500 iter 워밍업 후 cosine), AMP, grad clip 10, 수평 뒤집기만. 실행 커밋 `66c6d21`, 재시도 없이 1회에 완료, 비정상 손실 0회. 매 에폭 `det_val` AP50을 기록해 **epoch 10**(AP50 0.9355)을 가중치로 저장했다.
- 점수 임계값 **0.96**: `det_val`에서 IoU 0.5 F1이 최대인 값(0.05~0.99, 0.01 간격, 동점이면 높은 쪽). `configs/default.yaml`의 `detector.score_threshold`에 고정. NMS IoU 0.5, 영상당 최대 300개.
- 결과 (`outputs/detector_report.json`, 임계값 0.96 기준. **test는 보고만 하고 어떤 값도 test로 정하지 않았다**. 분할이 장면 단위라 HRSID 논문 수치와 직접 비교하지 않는다):

| 분할 | 영상 | 라벨 | AP50 | 정밀도 | 재현율 | F1 | 누락 | 오탐 | 위치·크기 |
|---|---|---|---|---|---|---|---|---|---|
| det_val | 527 | 1,299 | 0.936 | 0.941 | 0.871 | 0.904 | 168 (12.9%) | 71 | 96 (7.4%) |
| dev | 393 | 905 | 0.939 | 0.950 | 0.859 | 0.902 | 128 (14.1%) | 41 | 60 (6.6%) |
| test | 962 | 3,050 | 0.881 | 0.945 | 0.772 | 0.850 | 695 (22.8%) | 137 | 228 (7.5%) |

  연안/외해별 누락률: dev 31.2% / 2.8%, test 41.6% / 2.8%. 누락은 연안(밀집·작은 선박)에 몰려 있고 오탐은 영상당 0.1개 안팎으로 적다.

## 5. 오류 주입·수정 (SPEC §8, `configs/injection.yaml`)

- 보정은 **dev 영상 393장**의 탐지기 오류에서 측정했다 (`sarqa inject calibrate`, 코드 `src/sarqa/inject/calibrate.py`). 층 = 상자 크기 구간(dev 라벨 긴 변의 3분위수 37 px, 53 px) × 연안/외해.
- 측정한 dev 탐지 오류 (정수 반올림한 상자로 매칭, 위 표와 1~3건 차이): 라벨 905, 누락 129, 오탐 42, 위치·크기 63 (매칭 776쌍 중).

| 층 | 누락률 | 위치·크기 교란률 |
|---|---|---|
| small·inshore | 0.436 | 0.178 |
| small·offshore | 0.080 | 0.127 |
| mid·inshore | 0.188 | 0.054 |
| mid·offshore | 0.014 | 0.037 |
| large·inshore | 0.193 | 0.033 |
| large·offshore | 0.011 | 0.082 |

- 오탐: **영상당 개수 = 그 영상에서 누락 주입이 없앨 것으로 기대되는 개수**(층별 누락률의 합 E; `floor(E)`에 확률 `E-floor(E)`로 1을 더해 평균이 E와 같게, `configs/injection.yaml`의 `fp_count_rule: expected_miss`). dev 탐지기의 자연 오탐률(영상당 약 0.1개)은 쓰지 않는다(이유는 `docs/deviations.md` 2026-09-30). 크기(너비, 높이)와 중심(x, y)은 종전대로 dev 오탐 상자의 경험분포에서 뽑고 라벨 상자와 IoU가 0.1을 넘으면 다시 뽑는다(최대 50회). 위치·크기: dev의 IoU 0.5~0.75 매칭 쌍에서 (Δcx/w, Δcy/h, log 너비 비, log 높이 비) 한 쌍을 통째로 뽑아 적용하고 IoU가 [0.5, 0.75)일 때까지 다시 뽑는다(최대 50회, 실패하면 교란하지 않고 기록).
- 시드는 (영상, 유형), 주입 뒤 T 외의 오류가 없는지 자동 검사. 수정은 `corrected(miss)` 누락 라벨 추가, `corrected(fp)` 오탐 삭제, `corrected(loc)` IoU<0.75 쌍을 라벨로 교체.
- dev 문항 영상 70장에서의 실제 주입 (기대 = 층별 확률의 합): 누락 63 (기대 56.9), 위치·크기 32 (기대 27.8), 오탐 55(영상당 0.79, 누락 기대와 같게). box_dependent 75문항 중 주입이 답을 바꾼 문항은 누락 14, 오탐 15, 위치·크기 1.
- 주입·수정 상자 파일(`data/injected/test_*.json`, `data/corrected/test_*.json`)의 SHA-256은 §1 표에 있고, test 문항 영상에서의 실제 주입 수는 §10에 있다.

## 6. 에이전트와 실행 (SPEC §7, §9, §10) — 초안, M5에서 확정

- 모델 `qwen3:8b`(Q4_K_M, 다이제스트 `500a1f067a9f…`), Ollama 0.34.0, 텍스트만. 옵션: `think=false`, `temperature=0.2`, **`num_ctx=16384`**(8192에서 올림, `docs/context_length.md`), `num_predict=2048`, `keep_alive=-1`. 구조화 출력은 JSON 스키마(`format`), 형식 오류는 한 번만 재시도.
- 시드 `seed = hash(qid, repeat) mod 2^31`(sha256 기반), 조건과 무관하게 정한다. 조건 3만 `repeat=1`. **같은 Ollama 서버 프로세스 안에서만 재현되고 재시작하면 재현되지 않는다**(`docs/env_notes.md`). 본 실행 중 재시작하지 않으며, 기록마다 서버 PID·시작 시각(`server`)을 남긴다.
- 프롬프트(`src/sarqa/agents/prompts/`)의 SHA-256: `common.md` `658bde6954e7aa0c28118dad21baddeffc5db33f52dd39c9db060f3b79bfe5e9`, `stepwise.md` `e562dc8caed58aefcdb7988b269d0252a09e975610a95384c778ea52018264a5`, `batch_plan.md` `c9af8afaf61b78e7f745038d5704c6a053cc93c82bd903e5604c0916c3bbe240`, `batch_answer.md` `686f3c72dcc80aa25186120c99c0e9388911855a49316997ff89754979e9f376`.
- 호출 상한 `max(2 × gold_calls, gold_calls + 3)`, 실행당 시간 제한 300초, 정답 판정은 `int`·`category` 정확 일치(단위 포함), `float` ±5% (`grading.py`).
- 조건 11개 × test 360문항 = 3,960회(`configs/conditions.yaml`). 실행 순서: 우선순위 그룹(1: 조건 1, 2, 6~11 → 2: 조건 3 → 3: 조건 4, 5) 순서를 지키고, 그룹 안에서 **문항 순서와 한 문항 안의 조건 순서를 고정 시드로 섞는다.** 계획된 순서는 `order.json`에 저장하고 해시를 `manifest.json`에 넣는다. 기록마다 `run_index`, `started_at`, `prompt_tokens_max`를 남긴다.

## 7. 확정된 결정 (사용자, 2026-10-01; 근거는 `docs/deviations.md`)

1. **조건 2(탐지 입력, 단계별)의 실행 실패율 10.0%를 받아들인다.** dev만 보고 프롬프트를 더 조정하지 않는다(과적합 위험).
2. **L5는 유지한다**(test 18문항, 사례 분석용). 18문항은 `l5_noisy_quadrant` 6 + `l5_scene_quadrant` 12로 나눈다(처음 계획 9 + 9는 분기 균형 규칙 아래에서 test 영상의 `then` 갈래 후보가 부족해 생성이 실패했다, `docs/deviations.md` 2026-10-01).
3. **예산 공식 `max(2g, g+3)`을 유지한다**(`max(2g, g+5)`는 정답이 바뀐 실행 1건뿐, `docs/budget_analysis.md`).
4. **에이전트 프롬프트는 위 4개 파일(현재 main)로 확정한다.**
5. **질문 언어는 한국어로 확정한다**: 시스템 프롬프트·도구 설명은 영어, 질문만 한국어. 영어판(`text_en`)은 dev 비교 기록(`docs/language_comparison_dev.md`)으로만 둔다. 언어 비교 dev 결과는 한국어 75/90, 영어 76/90으로 구별되지 않았다.
6. `num_ctx`는 16384(위 §6). 오탐 주입은 층별 누락 주입의 기대 개수와 같게(§5). `l2_longest_length`는 float ±5%.

## 8. 분류 규칙 요약 (SPEC §11) — 초안

- **입력 오류** = `box_dependent`이고 에이전트가 받은 상자에서 정답 풀이를 실행한 값(`reachable_answer`)이 `gold_answer`와 다름. **에이전트 오류** = 답이 없거나 답 ≠ `reachable_answer`(단위 포함). 오답은 "입력만 / 에이전트만 / 둘 다" 중 하나, 상쇄는 `lucky_correct`. 첫 이탈은 에이전트 오류가 있는 실행에서만, 턴 순서 → 같은 턴이면 단계 순서(해석, 도구 선택, 결과 해석, 계획·분기, 계산, 답 형식화). 판정 불가는 `unknown`.
- 각 단계는 **그 실행이 받은 입력** 기준: 정답 풀이·허용 대안 풀이를 그 상자에서 다시 실행한 결과와 비교한다. 무해한 이탈(사용되지 않은 읽기·계산·추가 호출, 오류 복구, 기록만 틀린 해석·분기)은 기록만 한다.
- **해석 판정 필드는 `target`, 영역, `filters`, 분기 조건뿐**이고 `unit`·`answer_type`은 통계로만 남긴다(최종 단위는 6단계). 읽기·분기 값이 `{"count": 3}`처럼 키가 하나이고 필드 이름과 같은 객체이면 값을 꺼내 비교한다.
- 입력 오류 하위 범주는 받은 상자를 라벨과 IoU 0.5로 매칭해 종류별로 하나씩만 고쳐 정답 풀이를 다시 실행(replay)한다.
- 사람 검증: 오답을 (칸, 첫 이탈, 입력 원인)으로 층화한 표본(기본 120, 상한 150, `sarqa analyze human-sample`). 검증 결과로 규칙을 바꾸지 않는다.

## 9. 비교 목록과 조건 수 (SPEC §12.2) — 초안

다중 비교 보정은 하지 않고, 아래 목록을 미리 고정한다. 모든 비교는 같은 문항을 짝지어 하고 신뢰구간은 장면 묶음 단위 부트스트랩(B=10,000)이다.

| 목적 | 비교 (조건 번호) |
|---|---|
| 그림 1: 오류 원인 분해 | 조건 1 대 조건 2의 오답 분해(입력만 / 에이전트 첫 이탈 단계) |
| 표 1: 탐지 오류 효과 (`box_dependent=true`만) | 하락 폭: 1 → 6, 1 → 7, 1 → 8 / 회복 폭: 2 → 9, 2 → 10, 2 → 11 (세 효과를 더하지 않음) |
| 위약 대조 (`box_dependent=false`) | 1 대 6, 7, 8 및 2 대 9, 10, 11 (변화가 없어야 함) |
| 잡음 수준 | 조건 1 대 조건 3 (정확도 차이와 신뢰구간) |
| 표 2: 유형별 | 조건 1, 2의 L1~L5 정확도와 첫 이탈 분포 |
| 표 3: 방법 비교 | 1 대 4, 2 대 5 |

주 비교 10건(1-2, 1-6, 1-7, 1-8, 2-9, 2-10, 2-11, 1-3, 1-4, 2-5)과 위약 대조 6건, 조건 수 11.

## 10. test 문항과 gold check (M5, 2026-10-01)

**생성**: `sarqa questions generate --split test --allow-test`를 한 번만 실행해 `data/questions/test.json`(360문항)을 만들고, `sarqa inject build --split test --allow-test`로 주입·수정 상자 6개 파일과 문항의 참조 답(`reference_answers`, `answer_changed`)을 채웠다. 해시는 §1 표. 생성 시드는 `configs/default.yaml`의 `seed`(20260929). 쿼터는 `questions/templates.py`의 `QUOTAS["test"]`이고, L5만 처음 계획(9 + 9)이 분기 균형 규칙 아래에서 생성 실패해 6 + 12로 바꿨다(`docs/deviations.md` 2026-10-01, #96).

| 항목 | 값 |
|---|---|
| 문항 | 360 = L1 72, L2 90, L3 90, L4 90, L5 18 |
| `box_dependent` | **304 (84.4%)** (L1 52, L2 90, L3 54, L4 90, L5 18). 아닌 56 = `l1_scene` 10, `l1_brightness` 10, `l3_quadrant_brightest` 18, `l3_quadrant_noisiest` 18 |
| 분기 문항(`has_branch`) | **108** = L4 90 + L5 18 |
| 영상 / 장면 묶음 | 250장(영상당 최대 2문항) / 23개(묶음당 3~33문항) |
| 답 유형 | int 146, float 134, category 80 (top_left 20, bottom_left 20, top_right 15, bottom_right 15, inshore 5, offshore 5) |
| 평균 `gold_calls` / 호출 상한 최대 | 3.36 / 18 |

| 템플릿 | 문항 수 |
|---|---|
| `l1_total_count` | 14 |
| `l1_quadrant_count` | 14 |
| `l1_edge_count` | 12 |
| `l1_rect_count` | 12 |
| `l1_scene` | 10 |
| `l1_brightness` | 10 |
| `l2_nearest_ratio` | 18 |
| `l2_longest_length` | 18 |
| `l2_count_over_length` | 18 |
| `l2_longest_neighbor` | 18 |
| `l2_longest_shortest_distance` | 18 |
| `l3_quadrant_most_ships` | 22 |
| `l3_empty_quadrants` | 20 |
| `l3_quadrant_most_long` | 12 |
| `l3_quadrant_brightest` | 18 |
| `l3_quadrant_noisiest` | 18 |
| `l4_scene_branch` | 16 |
| `l4_count_branch` | 18 |
| `l4_quadrant_branch` | 18 |
| `l4_maxlen_branch` | 20 |
| `l4_noise_branch` | 18 |
| `l5_noisy_quadrant` | 6 |
| `l5_scene_quadrant` | 12 |

**주입·수정이 답을 바꾸는 범위** (정답 풀이를 그 상자에서 실행한 값 기준이며 에이전트 결과가 아니다. `box_dependent` 304문항 기준):

| | 값 |
|---|---|
| 누락 주입으로 정답이 바뀐 문항 | **62** (L1 6, L2 18, L3 8, L4 27, L5 3) |
| 오탐 주입으로 정답이 바뀐 문항 | **43** (L1 8, L2 14, L3 4, L4 16, L5 1) |
| 위치·크기 주입으로 정답이 바뀐 문항 | **6** (L2 4, L4 2). 작은 것은 SPEC §6.4가 예고한 현상이다 |
| `box_dependent=false` 56문항에서 주입이 정답을 바꾼 수 | 0 (위약 대조 전제 충족) |
| 탐지 입력에서 정답 풀이의 답이 gold와 다른 문항 | **81** (L1 7, L2 28, L3 7, L4 35, L5 4) |

수정 조건별 **회복 가능 문항 수** (탐지 입력에서 답이 틀린 81문항 중 그 한 종류만 고치면 gold가 나오는 문항):

| 수정 | 회복 가능 | 고쳐도 틀림 | 탐지에서는 맞았는데 고치면 틀려지는 문항 |
|---|---|---|---|
| 누락만 수정(조건 9) | **43** / 81 | 38 | 2 |
| 오탐만 수정(조건 10) | **6** / 81 | 75 | 5 |
| 위치·크기만 수정(조건 11) | **2** / 81 | 79 | 1 |

(마지막 열은 서로 다른 오류가 우연히 상쇄되어 맞던 문항이다. 한 종류만 고치면 상쇄가 깨진다.)

**test 영상 250장에 실제 주입된 수** (SPEC §8.2, 기대 = 층별 확률의 합, dev 탐지 오류와 나란히):

| 층 | 라벨 | 누락 기대 | 누락 실제 | 위치·크기 기대 | 위치·크기 실제 |
|---|---|---|---|---|---|
| large·inshore | 151 | 29.1 | 26 | 4.9 | 6 |
| large·offshore | 191 | 2.1 | 1 | 15.7 | 11 |
| mid·inshore | 104 | 19.6 | 21 | 5.6 | 8 |
| mid·offshore | 210 | 2.9 | 2 | 7.7 | 4 |
| small·inshore | 334 | 145.5 | 162 | 59.5 | 62 |
| small·offshore | 91 | 7.3 | 5 | 11.6 | 10 |
| **합계** | **1,081** | **206.5** | **217** | **104.9** | **101** |

오탐은 누락 기대 개수(206.5)와 같게 뽑아 **202개**(영상당 0.81). 비교: dev 탐지기의 실제 오류(dev 영상 393장, §5)는 라벨 905, 누락 129(14.3%), 오탐 42, 위치·크기 63(매칭 776쌍 중 8.1%), test 영상 전체에서의 탐지기 실제 오류는 §4 표(누락 22.8%).

**gold check (정답 풀이 사람 검증, SPEC §6.4 6단계)**: 표본 40문항(L1 8, L2 10, L3 10, L4 10, L5 2, 23개 템플릿 전부, 고정 시드). **결과: 40문항 모두 O.** 확인 방법 세 가지:
1. 상자 기반 33문항: 저장소 코드와 독립된 재구현으로 정답 일치 확인 (사용자).
2. 밝기·잡음이 들어간 문항(10문항, 값 28개): `image_stats` 코드를 쓰지 않고 JPEG를 PIL로 직접 읽고 라벨 상자는 COCO 파일에서 직접 읽어 numpy로 사분면 평균(밝기)과 라벨 상자 밖 픽셀의 표준편차(잡음)를 다시 계산해 gold_steps와 비교 (Claude). 최대 차이 밝기 0.0049, 잡음 0.0050(소수 둘째 자리 반올림 오차 이내, 0.01 초과 0건), 이 값으로 다시 구한 답·분기도 모두 일치.
3. 연안/외해와 상자 위치: 주석 영상(`outputs/gold_check_test/index.html`)으로 40문항 전부 직접 확인 (사용자).

라벨 특이 사례 3건(정답은 라벨 기준으로 맞음): T-L2-001(겹친 작은 상자 두 개가 최근접 쌍), T-L3-034(s1이 6×1 px 상자), T-L4-001(대부분 바다이고 가장자리에만 육지가 약하게 보임, 태그는 데이터셋 기준 inshore). 확인표는 `outputs/gold_check_test.csv`(`user_ok` 전부 O, SHA-256 `9404380d214a08dea8dc18c6015f7fb07ef79e16d29d5a1e15ca784ba55038a0`, git 밖).

**논문 한계로 적을 것**: 오탐 주입 규칙(누락 기대 개수와 같게, 실제 탐지기의 오탐 빈도를 흉내 내지 않음), 위치·크기 주입이 답을 거의 바꾸지 않음(6/304), 조건 6의 예산 초과 비율이 높았던 점(파일럿 B), 같은 Ollama 서버 프로세스 안에서만 재현됨, 라벨 특이 사례(겹침·극소 상자).
