# release/

논문에서 공개하기로 한 문항, 실행 기록, 분류 결과, 집계 표의 복사본이다. 원본은 저장소 밖(`data/`, `outputs/`)에 있고, 이 폴더의 파일은 원본을 그대로 복사한 것이다(내용 변경 없음). HRSID 영상 자체는 포함되어 있지 않다. 영상은 각자 원 출처에서 내려받는다(저장소 상위 `README.md`의 "데이터" 절).

파일 무결성은 `SHA256SUMS`로 확인한다.

```bash
cd release && sha256sum -c SHA256SUMS
```

## 폴더 구성

| 경로 | 내용 |
|---|---|
| `questions/test.json` | test 문항 360개(정답 해석, 정답 풀이와 허용 대안 풀이, 정답, 호출 상한 등). 문항은 한 번만 생성했다 (`PROTOCOL.md`) |
| `runs/condition_01.jsonl` ~ `condition_11.jsonl` | 조건별 실행 기록. **각 줄은 한 번의 실행**(문항 하나 × 조건 하나)이며 조건마다 360줄, 합계 3,960줄이다 |
| `runs/manifest.json` | 실행 기록 파일의 해시, 총 실행 수, 서버 구간 등 실행 요약 |
| `classification/classified.jsonl` | 실행마다 자동 오류 분류 결과(입력 오류와 에이전트 오류, 오답 칸, 첫 이탈 단계, 이탈 목록). 3,960줄 |
| `analysis/*.csv` | 집계 표: 조건별 정확도(`accuracy_by_condition.csv`), 짝지은 비교(`paired_comparisons.csv`), 잡음 수준(`noise_cond1_vs_cond3.csv`), 오답 분해(`decomposition_cells.csv`, `decomposition_input_causes.csv`, `decomposition_first_deviation.csv`), 유형별·호출 깊이별(`by_level.csv`, `by_depth.csv`), 주입·수정 효과(`injection_correction_effects.csv`), 기대와의 일치 확인(`consistency_checks.csv`), 방법 비교(`method_comparison.csv`), 실행 실패(`failures_by_condition.csv`), 입력 원인이 unknown인 문항(`unknown_input_causes.csv`) |
| `analysis/figures/figure2.png`, `figure2.pdf` | 오류 원인 분해 그림(조건 1, 2, 4, 5) |
| `validation/round1/`, `validation/round2/` | 자동 오류 분류와 AI 판정을 비교한 자료(아래) |
| `SHA256SUMS` | 이 폴더 안 모든 파일(`SHA256SUMS` 제외)의 SHA-256 |

## 조건 번호 (`SPEC.md` §9)

3,960회 = 11조건 × 360문항. 주입·수정 조건은 단계별 계획으로만 실행했다.

| 조건 | 방식 | 입력 |
|---|---|---|
| 1 | 단계별 계획 (기준) | label (라벨 상자) |
| 2 | 단계별 계획 | detected (탐지 상자) |
| 3 | 단계별 계획 재실행 (`repeat=1` 시드) | label |
| 4 | 일괄 계획 | label |
| 5 | 일괄 계획 | detected |
| 6 | 단계별 계획 | label + 누락만 주입 |
| 7 | 단계별 계획 | label + 오탐만 주입 |
| 8 | 단계별 계획 | label + 위치·크기 오차만 주입 |
| 9 | 단계별 계획 | detected + 누락만 수정 |
| 10 | 단계별 계획 | detected + 오탐만 수정 |
| 11 | 단계별 계획 | detected + 위치·크기 오차만 수정 |

## validation/

자동 오류 분류의 첫 이탈 단계를 AI 판정과 비교한 자료이다. 판정 시점에 판정자에게는 정답표(자동 분류 라벨)가 공개되지 않았다. 방법과 결과는 [`docs/validation_round2.md`](../docs/validation_round2.md)에 있다.

| 경로 | 내용 |
|---|---|
| `round1/ai_labels.csv` | 1차 표본에 대한 AI 판정 |
| `round1/human_sample_key.csv`, `round1/human_order_strata.csv` | 1차 표본의 자동 분류 라벨(정답표)과 순서·층 정보 |
| `round2/ai_labels2.csv` | 2차 표본 100건에 대한 AI 판정(열: `rank`, `run_id`, `human_first_deviation`, `human_note`) |
| `round2/ai_check2_key.csv`, `round2/strata.csv` | 2차 표본의 자동 분류 라벨(정답표)과 층별 모집단·표본 수 |
| `round2/results_main.csv`, `results_aux97.csv` | 일치율과 코헨 카파(주 결과 100건, 보조 97건) |
| `round2/confusion.csv`, `by_stage.csv`, `by_confidence.csv`, `by_condition.csv` | 혼동 행렬, 단계별·확신도별·조건별 일치 |
| `round2/disagreement_cells.csv`, `disagreements.csv` | 불일치가 많은 칸과 불일치 목록 |
