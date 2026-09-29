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
