# 동결(M5) 체크리스트

SPEC §0-3, §14 M5, §17.6 기준. **test 문항·test 상자 파일·`freeze-v1` 태그는 이 문서의 절차대로 한 번만 만든다.**
`나` = Claude Code, `당신` = 사용자. 시간은 대략의 추정이다.

## 0. 시작 전 (동결 목표 10/1)

| # | 확인 | 담당 | 시간 |
|---|---|---|---|
| 0-1 | M3 마무리(4차) PR이 모두 병합됐다 (병합 순서는 `docs/m3_report.md` "마무리(4차)") | 당신 | 20 min |
| 0-2 | 로컬 `main`이 최신이고 작업 트리가 깨끗하다: `git status --short`가 비어 있다 | 나 | 1 min |
| 0-3 | `pytest -q -m "not gpu"` (데이터 테스트 포함)와 `ruff check .` 통과, GitHub `main` CI 초록 | 나 | 5 min |
| 0-4 | **리허설**: `scripts/freeze_rehearsal.sh` → 마지막 줄이 `REHEARSAL PASSED` (임시 클론에서 dev 해시로 태그·검사·거부 5가지를 확인한다. 실제 저장소·태그·원격은 건드리지 않는다) | 나 | 1 min |
| 0-5 | 미해결 dev 결정이 없다 (`docs/deviations.md`, `PROTOCOL.md` §7의 확정 결정 참조). test 쿼터(`questions/templates.py`의 `QUOTAS["test"]`, box_dependent 84%)를 확인했다 | 당신 | 10 min |
| 0-6 | Ollama: 11434 서버 하나만 떠 있다 (`ss -ltnp \| grep 1143`), tmux `easqaa-ollama` 살아 있음, `nvidia-smi`에 다른 GPU 작업이 없다 | 나 | 2 min |

## 1. 해시를 고정할 파일 (11개)

`sarqa freeze hashes --split test`가 아래를 표로 출력한다. 모두 `PROTOCOL.md` §1 표에 `` `경로` … `SHA-256` `` 형식으로 들어가고, 실행기의 test 검사(`run/freeze.py`)가 시작할 때 실제 파일과 대조한다.

| 파일 | 만드는 시점 |
|---|---|
| `splits/scenes.json`, `splits/splits.json` | 이미 있음 (M0, PROTOCOL에 행 있음) |
| `outputs/detector/weights.pt` | 이미 있음 (M1, 행 있음) |
| `data/detections/test.json` | 이미 있음 (M1, 행 있음) |
| `data/questions/test.json` | 2-1 |
| `data/injected/test_miss.json`, `test_fp.json`, `test_loc.json` | 2-2 |
| `data/corrected/test_miss.json`, `test_fp.json`, `test_loc.json` | 2-2 |

부가: `splits/splits_report.json`, `data/detections/dev.json`는 PROTOCOL에 이미 행이 있고 검사 대상은 아니다(있으면 유지).

## 2. test 문항·상자 생성 (한 번만)

명령은 이미 있는 파일을 **덮어쓰지 않고 거부한다**. 다시 만들어야 하면 그 결정을 `docs/deviations.md`에 적고 파일을 손으로 지운 뒤 처음부터 다시 실행한다.

| # | 명령 | 결과 | 담당 | 시간 |
|---|---|---|---|---|
| 2-1 | `sarqa questions generate --split test --allow-test` | `data/questions/test.json` (L1 72, L2 90, L3 90, L4 90, L5 18 = 360). 검증(`validate`)을 통과하지 못하면 파일을 만들지 않는다 | 나 | 5 min |
| 2-2 | `sarqa inject build --split test --allow-test` | 주입 3 + 수정 3 파일, 문항의 `reference_answers`·`answer_changed` 채움 (2-1 다음에만) | 나 | 5 min |
| 2-3 | `sarqa questions review --split test --sample 40` | `outputs/gold_check_test.csv`, 라벨 상자를 그린 영상 `outputs/gold_check_test/*.png`, 전체 목록 `outputs/test_review/test_questions.md` (모두 git 밖) | 나 | 2 min |

test 문항 목록에서 `box_dependent`가 몇 개인지(목표 ≥ 80%), 유형별 개수, 층별 실제 주입 수는 2-1·2-2 출력에 나오므로 PROTOCOL.md에 옮긴다 (§5 "test" 표).

## 3. gold check (정답 풀이 30~50문항 직접 확인)

1. `outputs/gold_check_test.csv`를 연다 (Excel/LibreOffice, UTF-8). 표본 40문항은 유형별 비율대로, 유형 안에서는 템플릿을 번갈아 뽑았다(고정 시드, 같은 명령은 같은 표본).
2. 문항마다 `annotated_image`의 PNG를 본다: 빨간 상자 = 라벨 상자(id 표시), 파란 선 = 사분면 경계.
3. 문구와 상자·`label_boxes`·`gold_steps`(정답 풀이의 중간값)로 `gold_answer`가 맞는지 직접 세거나 잰다. 맞으면 `user_ok`에 `O`, 틀리면 `X`와 `user_note`.
4. **모두 `O`**: 4로 진행. **하나라도 `X`**: 원인이 템플릿·생성기 버그이면 고치고(dev로 재현·테스트), test 파일을 지우고 2-1부터 다시 한다. 이 재생성은 test 실행 전이라서 허용되고 `docs/deviations.md`에 이유를 적는다. **test 실행 결과를 본 뒤에는 규칙을 바꾸지 않는다.**
5. 담당: 당신 1~2 h. (파일럿에서 dev 90문항으로 같은 방식을 미리 해볼 수 있다: `sarqa questions review --sample 40`.)

## 4. PROTOCOL.md 완성

`sarqa freeze hashes --split test --write`가 §1 표의 해시 행을 채운다(기존 행은 교체, 새 행은 추가, "미정" 자리표시 행은 삭제). 나머지는 손으로 채운다.

| 항목 | 담당 |
|---|---|
| 해시 행 11개 (`--write`), 프롬프트 해시 4개(`agents/prompts/*.md`), 모델 다이제스트·Ollama 버전 | 나 |
| test 문항 수·`box_dependent` 수·유형별 수, test 주입 요약(층별 실제 주입 수와 dev 탐지 오류 요약을 나란히, SPEC §8.2) | 나 |
| 분류 규칙 요약, 비교 목록과 조건 수(§12.2: 다중 비교 보정을 하지 않으므로 목록을 미리 적는다) | 나 초안, 당신 검토 |
| 확정 결정(A6)과 논문 한계 문장 | 나 초안, 당신 검토 |

## 5. 동결 PR과 태그

1. 브랜치 `exp/28-freeze-v1` (이슈 #28): `PROTOCOL.md`만 바꾼다(test 파일은 git 밖). PR 본문에 `docs/freeze_checklist.md` 각 항목을 체크한다. 이 PR은 아직 태그 전이므로 `frozen-change` 라벨이 필요 없다. **병합은 당신이 한다.**
2. 병합 뒤 로컬을 맞춘다: `git checkout main && git pull`, `git status --short`가 비어 있는지 확인.
3. 태그 (당신의 승인 뒤): 
   ```bash
   git tag -a freeze-v1 -m "freeze v1: code, configs, PROTOCOL and data hashes" <M5 병합 커밋>
   git push origin freeze-v1
   ```
4. 검사: `sarqa freeze check --split test`가 `freeze guard passes for split test`를 출력하는지 확인한다 (아무것도 실행하지 않는 검사). 이 시점부터 `src/sarqa/`(analysis 제외), `configs/`, `pyproject.toml`, `PROTOCOL.md`는 수정 금지이고 `freeze-check.yml`이 PR을 검사한다.

## 6. 백업 (git 밖 파일, 해시로만 고정되어 있음)

동결 직후, 외부 디스크나 다른 머신에 복사한다. 손상되면 실행기가 거부한다.

```bash
tar czf freeze-v1-data.tgz outputs/detector/weights.pt splits data/detections data/questions/test.json \
  data/injected/test_*.json data/corrected/test_*.json PROTOCOL.md
sha256sum freeze-v1-data.tgz > freeze-v1-data.tgz.sha256
```

| 파일 | 크기 |
|---|---|
| `outputs/detector/weights.pt` | 약 159 MB |
| `data/detections/*.json`, `splits/*.json` | 약 2 MB |
| `data/questions/test.json`, `data/injected/test_*`, `data/corrected/test_*` | 생성 후 확인 (수 MB 예상) |

## 7. 본 실행

고정 worktree에서 실행해 실행 중 브랜치를 바꿔도 영향받지 않게 한다 (파일럿과 같은 방식).

```bash
git worktree add ../EASQAA-main-run freeze-v1
ln -s $PWD/data ../EASQAA-main-run/data && ln -s $PWD/outputs ../EASQAA-main-run/outputs
printf 'data\noutputs\n' >> .git/worktrees/EASQAA-main-run/info/exclude   # 심볼릭 링크가 status에 나오지 않게
cd ../EASQAA-main-run && git status --short          # 비어 있어야 한다
```

실행기는 시작할 때 test 검사(깨끗한 작업 트리, 태그 이후 동결 파일 변경 없음, 해시 일치)를 하고 아니면 거부한다.

```bash
tmux new-session -d -s main_run \
  'cd ../EASQAA-main-run && PYTHONPATH=$PWD/src nohup /home/cvlab/anaconda3/envs/easqaa/bin/python -u \
   -c "from sarqa.cli import main; raise SystemExit(main())" run --conditions all --split test \
   --out outputs/runs/ >> outputs/runs/main_run.log 2>&1'
```

- 이어 하기: 같은 명령을 다시 실행하면 이미 기록된 실행은 건너뛴다. 순서는 `outputs/runs/order.json`에 저장되고 해시가 `manifest.json`에 들어간다.
- 진행 확인: `tail -f outputs/runs/main_run.log`, `cat outputs/runs/condition_*.jsonl | wc -l` (총 3,960).
- **Ollama를 재시작하지 않는다.** 서버가 바뀌면 기록의 `server`와 로그 경고로 구간이 표시된다.
- 실행 중 다른 GPU 작업 금지, 절전·화면 잠금 해제, `nvidia-smi`로 GPU 메모리 확인.

| 구간 | 예상 시간 (파일럿 평균 시간 기준) |
|---|---|
| 1그룹 (조건 1, 2, 6~11: 2,880회) | 약 10.8 h |
| 2그룹 (조건 3: 360회) | 약 1.3 h |
| 3그룹 (조건 4, 5: 720회) | 약 1.7 h |
| 합계 | 약 13.8 h (재시도·서버 정체가 없다면) |

끝나면: `manifest.json`이 조건별 문항 수 360을 보이는지 확인, 태그 `run-v1`(§17.6), 분류(`sarqa classify --runs outputs/runs/ --split test`).

## 8. 하지 않는 것

- test 실행 결과를 보고 규칙·프롬프트·임계값을 바꾸지 않는다.
- 태그 뒤 동결 파일이 바뀌면(`frozen-change`) 이유를 기록하고 **전체를 다시 실행**한 뒤 `freeze-v2`를 찍는다.
- test 문항·상자 파일을 덮어쓰지 않는다 (명령이 거부한다). 리허설은 항상 dev로만 한다 (`scripts/freeze_rehearsal.sh`, `sarqa freeze check --split dev`).
