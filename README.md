# Error Analysis of SAR QA Agents (EASQAA)

SAR(합성개구레이더) 영상에서 선박을 탐지하고, 그 결과를 도구로 호출해 질문에 답하는 LLM 에이전트의 **오류가 어디서 생기는지**를 분석하는 실험 저장소이다. 오답을 "탐지기가 준 상자가 틀려서 생긴 입력 오류"와 "에이전트가 받은 상자를 잘못 처리해서 생긴 오류"로 나누고, 에이전트 오류는 처음 벗어난 단계(질문 해석, 도구 선택·호출, 결과 해석, 계획·분기, 계산, 답 형식화, 실행 실패)로 분류한다. 패키지와 명령어 이름은 `sarqa`이다. 모든 설계의 단일 기준은 [SPEC.md](SPEC.md)이다.

Code and data for an error analysis of tool-using LLM agents that answer questions about SAR ship-detection results.

## 연구 구성

| 항목 | 내용 |
|---|---|
| 데이터 | HRSID (ship 한 종류), 800×800 영상 5,604장. 원본 136개 장면을 겹치게 잘라 만든 것이라 장면 묶음 단위로 `det_train` / `det_val` / `dev` / `test`로 다시 나눔 (묶음 88 / 13 / 10 / 23개) |
| 탐지기 | Faster R-CNN (torchvision `fasterrcnn_resnet50_fpn`, COCO 사전학습에서 시작, 클래스 2개). 점수 임계값은 `det_val`의 F1 최대값(0.96) |
| 도구 5개 | `detect_ships`, `spatial_query`, `get_metadata`, `image_stats`, `calc` (`docs/tools.md`, `src/sarqa/tools/`) |
| 질문 | 템플릿 23개, 유형 L1~L5, test 360문항 (`docs/dev_questions.md`는 dev 문항 목록). 정답 풀이와 도구는 같은 함수를 씀 |
| 에이전트 | Qwen3-8B (`qwen3:8b`, Ollama), 텍스트만 입력. **단계별 계획**(한 단계씩 도구 호출)과 **일괄 계획**(계획 전체를 먼저 쓰고 실행) 두 방식 |
| 조건 | 11개 (`configs/conditions.yaml`): 라벨 상자, 탐지 상자, 라벨에 누락·오탐·위치 오류 주입, 탐지 상자에서 한 종류 오류 수정, 재실행(변동 폭), 일괄 계획의 라벨·탐지. 11조건 × 360문항 = 3,960회 실행 |
| 분류 | 오답을 입력만 / 에이전트만 / 둘 다로 나누고, 에이전트 오류의 첫 이탈 단계를 기록 (SPEC §11, `src/sarqa/classify/`) |

## 핵심 결과

- 정확도: 라벨 상자·단계별 79.2% → 탐지 상자 63.9%. 오답 중 60%에 입력 오류가 관여
- 라벨 상자 조건에서 단계별과 일괄 계획의 정확도 차이는 6.1%p
- 자동 오류 분류와 AI 판정의 일치는 낮았다(κ=0.137): 단계 분포는 탐색적 결과

## 환경

- Python 3.10 이상 (`pyproject.toml`), 개발·실행은 conda env `easqaa`(Python 3.10.21).
- 탐지기 학습과 추론에는 GPU가 필요하다 (개발 머신: RTX 3080 10GB, torch 2.7.1+cu118). `.[detector]`로 torch·torchvision을 설치한다 (`docs/env_notes.md`).
- 에이전트 실행(`sarqa run`)에는 Ollama 서버가 필요하다. 설정은 `configs/default.yaml`의 `llm`: 모델 `qwen3:8b`, 주소 `http://localhost:11434`, `think: false`, `temperature: 0.2`, `num_ctx: 16384`. 개발 머신의 Ollama는 0.34.0 (`docs/env_notes.md`).
- 데이터가 필요한 테스트는 `@pytest.mark.data`, GPU·Ollama가 필요한 테스트는 `@pytest.mark.gpu`이다. CI는 둘을 뺀 테스트만 돌린다.

## 설치와 테스트

```bash
conda create -n easqaa python=3.10
conda activate easqaa
pip install -e ".[dev]"        # add ".[detector]" for torch/torchvision
pytest -m "not data and not gpu"
```

## 데이터

HRSID는 이 저장소에 **포함되어 있지 않다**. 각자 원 출처에서 HRSID의 라이선스에 따라 내려받아 `data/hrsid/`에 둔다 (파일 구조는 `docs/data_notes.md`). `data/`와 `outputs/`는 `.gitignore` 대상이다.

HRSID: S. Wei, X. Zeng, Q. Qu, M. Wang, H. Su, J. Shi, 'HRSID: A High-Resolution SAR Images Dataset for Ship Detection and Instance Segmentation,' IEEE Access, vol. 8, pp. 120234–120254, 2020.

논문에서 공개한 문항, 실행 기록, 분류 결과, 집계 표는 [`release/`](release/)에 있다.

`splits/`의 파일(`scenes.json`, `splits.json`, `splits_report.json`)은 영상 파일명, 장면 묶음 번호, 분할·연안/외해 태그, 영상별 상자 개수만 담고 있다. 영상 자체와 상자 좌표는 들어 있지 않다.

## 재현 절차

순서와 명령은 `PROTOCOL.md`, `docs/freeze_checklist.md`, `docs/env_notes.md`, `configs/default.yaml`, `scripts/`에 적힌 그대로이다.

1. 데이터 분할 만들기 (`docs/data_notes.md` §10~11): `sarqa data scenes`, `sarqa data splits`. 결과 `splits/*.json`은 저장소에 있고, SHA-256은 `PROTOCOL.md` §1과 `sha256sum splits/*.json`으로 대조한다.
2. 탐지기 학습: `bash scripts/train_detector.sh` (`det_train` 학습, `det_val` AP50 기록). 이어서 `sarqa detector infer`로 추론 캐시를 만들고 점수 임계값을 `det_val` F1에서 정한다.
3. 오류 주입 빈도 측정: `sarqa inject calibrate` (dev 기준, `configs/injection.yaml`).
4. test 문항·주입·수정 상자 생성 (한 번만): `sarqa questions generate --split test --allow-test`, `sarqa inject build --split test --allow-test`.
5. 동결 검사: `sarqa freeze hashes --split test --write`로 PROTOCOL.md의 해시 행을 채우고 `sarqa freeze check --split test`로 확인한다.
6. 본 실행: `sarqa run --conditions all --split test --out outputs/runs/` (Ollama 필요, 중단하면 같은 명령으로 이어 한다).
7. 분류: `sarqa classify --runs outputs/runs/ --split test`.
8. 분석: `python -m sarqa.analysis.main_run --runs outputs/runs --questions data/questions/test.json --out outputs/analysis` (사용법은 `src/sarqa/analysis/main_run.py` 머리말).

탐지기 가중치, 탐지 캐시, test 문항 파일, 실행 기록은 저장소에 들어 있지 않다. 가중치와 data 파일의 SHA-256은 `PROTOCOL.md` §1에 있다.

## 고정 시점: `freeze-v1`

`freeze-v1` 태그는 **결과를 보기 전에** 실험 설계, 코드, 프롬프트, 분류 규칙을 고정한 시점이다. test 문항은 한 번만 생성했고, 데이터 파일의 SHA-256과 설계 결정은 `PROTOCOL.md`에 기록되어 있다. 본 실행은 이 태그의 커밋에서 시작했고, 실행기는 시작할 때 작업 트리가 깨끗한지, 태그 이후 고정 대상 파일이 바뀌지 않았는지, 해시가 일치하는지 검사한다. 이후 `src/sarqa/`(`analysis/` 제외), `configs/`, `pyproject.toml`, `PROTOCOL.md`는 수정하지 않는다. 명세와 달라진 점과 고정 이후의 변경은 `docs/deviations.md`에 기록한다.

## 검증과 한계

자동 오류 분류의 첫 이탈 단계 판정은 독립 AI 평가자의 판정과 비교해 검증했다 (2차 검증, 100건: 일치 30건, 코헨 카파 0.137). 계획, 방법, 결과, 불일치 분석은 [docs/validation_round2.md](docs/validation_round2.md)에 있다. 탐지기 점수 임계값은 `det_val`에서 정했고 test는 보고만 했다 (`PROTOCOL.md` §4). 오탐 주입 개수는 누락 기대 개수에 맞춘 것이라 실제 탐지기의 오탐 빈도를 흉내 내지 않는다 (`docs/deviations.md`).

## 인용

이 저장소는 2026 한국방송·미디어공학회 추계학술대회 대학생 논문 경진대회에 제출한 논문 'SAR 질의응답 에이전트의 오류분석'의 코드와 자료입니다.

## 라이선스

이 저장소의 코드와 문서는 [MIT 라이선스](LICENSE)를 따른다. 단, HRSID 데이터는 별도의 라이선스를 따르며 이 저장소에 포함되어 있지 않다.
