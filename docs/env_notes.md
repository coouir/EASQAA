# 환경 확인 결과 (M0)

2026-09-29, 이 저장소의 개발 머신에서 직접 실행해 확인한 값이다.

| 항목 | 확인 결과 |
|---|---|
| Python | conda env `easqaa`, Python 3.10.21 (`/home/cvlab/anaconda3/envs/easqaa/bin/python`) |
| Ollama 버전 | 0.34.0 (`GET /api/version`) |
| 모델 | `qwen3:8b`, 다이제스트 `500a1f067a9f` (`/api/tags`), 8.2B, Q4_K_M, capabilities: completion, tools, thinking |
| `format`(JSON 스키마) | 동작. `answer`(integer)·`unit`(enum)을 요구하는 스키마에 대해 스키마를 만족하는 JSON을 받음 (`think` false/true 둘 다) |
| `think` 옵션 | 동작. `think=false`는 응답에 `thinking` 필드 없음, `think=true`는 `thinking` 필드가 있고 출력 토큰이 많음(17 vs 325, 같은 질문) |
| 시드 결정성 | `temperature=0.2, seed=123, num_ctx=8192, think=false`로 같은 요청 3회 → 출력 3회 모두 동일 (1개 프롬프트에 대한 예비 확인). §14 M4 파일럿에서 실제 문항으로 다시 확인한다 |

`format`/`think`를 지원하므로 Ollama 업데이트는 필요 없다.

## 탐지기 학습 환경 (M1)

| 항목 | 값 |
|---|---|
| GPU / 드라이버 | RTX 3080 10GB, 드라이버 525.147.05 (CUDA 12.0) |
| PyTorch | torch 2.7.1+cu118, torchvision 0.22.1+cu118 (드라이버 525에 맞춰 cu118 빌드를 `--index-url https://download.pytorch.org/whl/cu118`로 설치) |
| 사전학습 가중치 | torchvision `FasterRCNN_ResNet50_FPN_Weights.COCO_V1` (COCO). HRSID 학습 가중치는 쓰지 않음 |
| tmux | 시스템에 없고 sudo도 없어 conda env `tmuxenv`(conda-forge, tmux 3.7)에 별도 설치: `/home/cvlab/anaconda3/envs/tmuxenv/bin/tmux` |
| 학습 시작 전 GPU 점유 | `ollama ps` 비어 있음(로드된 모델 없음), GPU 사용 206 MiB, 컴퓨트 프로세스 없음 |

학습 실행 (커밋을 고정한 worktree에서 실행해 메인 체크아웃의 브랜치 전환에 영향받지 않게 한다):

```bash
git worktree add --detach ../EASQAA-m1-run <commit>
ln -s $PWD/data ../EASQAA-m1-run/data && ln -s $PWD/outputs ../EASQAA-m1-run/outputs
tmux new-session -d -s m1_train 'cd ../EASQAA-m1-run && nohup bash scripts/train_detector.sh >> outputs/detector/tmux_wrapper.log 2>&1'
```

재개: 같은 명령을 다시 실행하면 `outputs/detector/last.pt`(에폭 단위)에서 이어 한다. 로그: `outputs/detector/train.log`(진행), `metrics.jsonl`(에폭별 AP50), `nohup.log`(프로세스 출력·재시도).

## Ollama·에이전트 실측 (M3, 2026-09-30)

| 항목 | 값 |
|---|---|
| Ollama | 0.34.0, 모델 `qwen3:8b` (Q4_K_M), 다이제스트 `500a1f06…9b8b41`. `format`(JSON 스키마, `anyOf`·`enum` 포함)과 `think:false` 모두 동작 |
| 기본 옵션 | `think=false`, `temperature=0.2`, `num_ctx=8192`, `num_predict=2048` (`configs/default.yaml`의 `llm:`) |
| 시스템 프롬프트 크기 | 공통 약 1,700 토큰 (도구 설명·해석 어휘·읽기/분기 기록 규칙 포함) |
| **시드 결정성** | dev 문항 4개 × 두 방법 × 같은 시드 3회 반복(같은 세션, 순차 실행): **8/8 조합에서 모든 턴의 LLM 출력이 완전히 같았다.** 프로세스·서버 재시작 뒤에도 같은지는 확인하지 않았다 (파일럿에서 다시 볼 것) |
| 지연 (라벨 입력, dev 8문항 시험) | 단계별 LLM 호출 1회 약 1.5~3초. 문항당 L1 3~8초, L2 7~8초, L3 22초(9호출), L5 30초(14호출, 예산 초과). 일괄 계획은 문항당 3~9초 |

## Ollama 재시작과 시드 결정성 (2026-09-30, 이슈 #71)

같은 8건(dev 문항 D-L2-010, D-L3-001, D-L4-005, D-L2-019 × 단계별·일괄, 라벨 입력, 시드 = hash(qid, 0))을 서버 재시작 전후로 실행해 모든 턴의 LLM 출력을 비교했다 (원자료 `outputs/determinism/*.json`, git 밖). 서버: `ollama serve`(포트 11434, tmux `easqaa-ollama`)만 껐다가 같은 명령으로 다시 띄웠다. 같은 머신의 다른 `ollama serve`(포트 11435)는 건드리지 않았다. 모델·다이제스트(`500a1f067a9f`)와 Ollama 0.34.0은 그대로.

| 비교 | 모든 턴의 출력이 같은 조합 |
|---|---|
| 재시작 전 ↔ 재시작 직후 (현재 프롬프트) | **2 / 8** |
| 재시작 직후 ↔ 그 뒤 한 번 더 (같은 서버 세션) | **8 / 8** |
| 재시작 전 ↔ 재시작 직후, 최종 답 | 4 / 8 (다른 4건: 한 건은 예산 초과로 바뀜, 세 건은 값이 다름) |
| 이전 세션(첫 결정성 시험, 이전 프롬프트) ↔ 재시작 후 같은 이전 프롬프트, 최종 답 | 7 / 8 (다른 1건: D-L2-010 단계별이 "답 없음" → 1 ships) |

**결론**: 같은 서버 세션 안에서는 같은 입력·같은 시드가 같은 출력을 낸다(8/8, 이전 시험의 8/8과 일치). **서버를 재시작하면 결정성이 유지되지 않는다.** 첫 차이는 해석·계획·읽기 같은 첫 몇 토큰 안에서 나며 이후 경로가 갈라진다 (재시작으로 KV 캐시·프롬프트 캐시 상태가 달라져 수치가 미세하게 달라지는 것으로 보이며, 원인은 확인하지 않았다).

**적용**: (1) 본 실행 중에는 Ollama를 재시작하지 않는다. 재시작이 필요하면 그 시점 이후의 기록을 다른 실행 묶음으로 취급한다(`meta`에 서버 시작 시각이 없으므로 재시작하면 기록을 남길 것). (2) 조건 3(`repeat=1` 재실행)은 "같은 조건에서 답이 바뀌는 정도"를 시드 차이로 재는 변동 측정이고, 시드 재현성에 기대지 않는다. (3) 재시작 전후로 결과를 짝지어 비교하지 않는다. (4) 논문에는 "같은 서버 세션 안에서만 재현된다"고 적는다.
