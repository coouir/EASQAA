# PROTOCOL.md

10/4 동결(`freeze-v1`)에 최종본이 된다. 지금은 **동결 전**이며, 항목은 마일스톤이 진행되면서 채운다 (SPEC §0-3).
동결 뒤에는 이 파일도 수정하지 않는다. 데이터 파일의 SHA-256은 실행기가 시작할 때 실제 파일과 대조한다.

## 1. 데이터 해시 (SHA-256)

| 파일 | 상태 | SHA-256 |
|---|---|---|
| `splits/scenes.json` | 확정 (M0) | `9cbb465d6cfbeaf1d33ea7ee4c74d20fcdce05d13b986e717ff1c6ddd3f05433` |
| `splits/splits.json` | 확정 (M0) | `6dc6266ac307ed04cb96eb982868ea797cb3a3bbebb3f75eb11b55468604d3f8` |
| `splits/splits_report.json` | 확정 (M0) | `fd6928fa404a32d1c0c6a5d90c256b818b9f43a4bd97fb28c52818d7d4631b7f` |
| `outputs/detector/weights.pt` (탐지기 가중치, epoch 10) | 확정 (M1) | `2d2bab8cbfe7f10181ac6501959dcc7c86b30b23cda7497e09711ae260a35ca6` |
| `data/detections/dev.json` | 확정 (M1) | `883487083bf1e0618e8abdf79fa7de148d36c322067aa7d1705ffea947437a06` |
| `data/detections/test.json` | 확정 (M1) | `b082f6cd08c892ddbe027894c1482c606077e57ffc3db1f5e4b2275121b50d42` |
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

- 오탐: 영상당 개수는 연안/외해별 dev 영상당 오탐 수의 경험분포에서, 크기(너비, 높이)와 중심(x, y)은 dev 오탐 상자의 경험분포에서 뽑고 라벨 상자와 IoU가 0.1을 넘으면 다시 뽑는다(최대 50회). 위치·크기: dev의 IoU 0.5~0.75 매칭 쌍에서 (Δcx/w, Δcy/h, log 너비 비, log 높이 비) 한 쌍을 통째로 뽑아 적용하고 IoU가 [0.5, 0.75)일 때까지 다시 뽑는다(최대 50회, 실패하면 교란하지 않고 기록).
- 시드는 (영상, 유형), 주입 뒤 T 외의 오류가 없는지 자동 검사. 수정은 `corrected(miss)` 누락 라벨 추가, `corrected(fp)` 오탐 삭제, `corrected(loc)` IoU<0.75 쌍을 라벨로 교체.
- dev 문항 영상 70장에서의 실제 주입 (기대 = 층별 확률의 합): 누락 63 (기대 56.9), 위치·크기 32 (기대 27.8), 오탐 9 (영상당 0.13). **오탐은 dev 탐지기가 영상당 0.1개 정도만 만들어서 주입도 드물다.** 그 결과 dev 문항(box_dependent 75개)에서 주입이 답을 바꾼 문항은 누락 14, 오탐 3, 위치·크기 1.
- 주입·수정 상자 파일(`data/injected/*.json`, `data/corrected/*.json`)의 SHA-256은 M5(freeze)에서 채운다.

## 6. 이후 채울 항목

분류 규칙 요약, 비교 목록과 조건 수(§12.2), test 문항 수와 `box_dependent` 개수.
