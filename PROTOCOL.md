# PROTOCOL.md

10/4 동결(`freeze-v1`)에 최종본이 된다. 지금은 **동결 전**이며, 항목은 마일스톤이 진행되면서 채운다 (SPEC §0-3).
동결 뒤에는 이 파일도 수정하지 않는다. 데이터 파일의 SHA-256은 실행기가 시작할 때 실제 파일과 대조한다.

## 1. 데이터 해시 (SHA-256)

| 파일 | 상태 | SHA-256 |
|---|---|---|
| `splits/scenes.json` | 확정 (M0) | `9cbb465d6cfbeaf1d33ea7ee4c74d20fcdce05d13b986e717ff1c6ddd3f05433` |
| `splits/splits.json` | 확정 (M0) | `6dc6266ac307ed04cb96eb982868ea797cb3a3bbebb3f75eb11b55468604d3f8` |
| `splits/splits_report.json` | 확정 (M0) | `fd6928fa404a32d1c0c6a5d90c256b818b9f43a4bd97fb28c52818d7d4631b7f` |
| `outputs/detector/weights.pt` (탐지기 가중치) | 미정 (M1 학습 후) | — |
| `data/detections/dev.json`, `data/detections/test.json` | 미정 (M1) | — |
| `data/injected/*.json`, `data/corrected/*.json` | 미정 (M5) | — |
| test 문항 파일 | 미정 (M5) | — |

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
- 점수 임계값은 `det_val` F1 최대값으로 정해 `configs/default.yaml`에 고정한다 (M1 학습 후 채움).

## 5. 이후 채울 항목

주입·수정 규칙(`configs/injection.yaml`), 분류 규칙 요약, 비교 목록과 조건 수(§12.2), test 문항 수와 `box_dependent` 개수.
