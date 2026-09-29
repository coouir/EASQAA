# M3 진행 보고 (야간 자동 진행)

작성: Claude Code, 2026-09-30 밤. 사용자가 아침에 확인한다. 기준 문서 SPEC.md §6, §7, §8, §11, §14 M3.
PR은 앞 브랜치 위에 쌓았고 **병합은 하지 않았다.** 아래 표의 순서대로 병합하면 된다.

## 단계 현황

| # | 단계 | 상태 | 이슈 / PR |
|---|---|---|---|
| 1 | get_metadata에 영상 크기(width, height) 추가 | 완료 | #56 / [PR #57](https://github.com/coouir/EASQAA/pull/57) |
| 2a | L1~L5 템플릿 카탈로그 (23개), 해석 어휘 | 완료 | #17 / [PR #58](https://github.com/coouir/EASQAA/pull/58) |
| 2b | 문항 생성기·필터·검증기·검토 도구 | 완료 | #18 / [PR #59](https://github.com/coouir/EASQAA/pull/59) |
| 2c | dev 90문항 생성, 검토표 `docs/dev_questions.md`, `outputs/gold_check.csv` | 완료 | #19 / [PR #60](https://github.com/coouir/EASQAA/pull/60) |
| 3 | Ollama 클라이언트, 단계별·일괄 에이전트, dev 문항 시험 실행 | 완료 | #20 #21 #22 / [PR #61](https://github.com/coouir/EASQAA/pull/61) |
| 4 | 오류 주입·수정, dev 보정(`configs/injection.yaml`) | 완료 | #23 #24 / [PR #62](https://github.com/coouir/EASQAA/pull/62) |
| (5a) | 실행기(이어 하기, 조건 표, 기록 스키마, 동결 검사) — 파일럿에 필요해 추가 | 완료 | #25 / [PR #63](https://github.com/coouir/EASQAA/pull/63) |
| 5 | 오류 분류기 초안 (입력 오류 속성, 1~6단계, replay) | 완료 | #26 / [PR #64](https://github.com/coouir/EASQAA/pull/64) |
| 6 | 파일럿 A (dev 90 × 조건 1·2) | 실행 중 | tmux `pilotA`, 로그 `outputs/runs/pilotA.log` |

PR은 #57 → #58 → #59 → #60 → #61 → #62 → #63 → #64 순으로 쌓여 있다(각 PR의 base가 앞 브랜치). 순서대로 병합하면 된다. CI(ruff + pytest, frozen-check)는 #57~#63 통과, #64는 확인 중.

## 결정한 것

- **dev 문항 (#19)**: 유형별 18/22/23/22/5 = 90, 영상 70장, 상자 의존 75문항(83%), 분기 27문항, 평균 `gold_calls` 3.38 (호출 수 분포 1:18, 2:21, 3:14, 4:5, 5:24, 6:2, 7:1, 8:2, 9:3). `data/questions/dev.json` SHA-256 `d12e1dc3…babb3`. 재생성: `sarqa questions generate --split dev` (시드 고정, 결정적). test 문항은 만들지 않았고 `--allow-test` 없이는 CLI가 거부한다.
- **L2 구조**: 5개 템플릿 모두 calc 포함, 도구 2~3종. 영상 크기를 쓰는 `l2_nearest_ratio`(get_metadata → spatial_query → calc)만 3종이고 나머지는 spatial_query + calc.
- 템플릿 문구·어휘·L4 분기 구성은 `docs/deviations.md`(2026-09-30 4줄)와 `docs/dev_questions.md`에 있다. **아침에 검토할 것**: 문구 전체, 특히 L3 사분면 문항의 답 형식 안내(`top_left, ...` 나열)와 L4/L5 분기 문구.

- **주입 보정 (#23)**: dev 영상 393장에서 층(크기 3구간 × 연안/외해)별로 측정. dev 문항 영상 70장에 실제 주입: 누락 63(기대 56.9), 위치·크기 32(기대 27.8), 오탐 9. **오탐은 dev 탐지기가 영상당 0.1개만 만들어 주입도 드물다.** 답을 바꾼 box_dependent 문항은 누락 14, 오탐 3, 위치·크기 1 / 75. 오탐·위치·크기 효과는 검정력이 낮을 것이다 (SPEC §6.4 주의와 같은 구조). 사용자 판단 필요: 이대로 갈지, 오탐을 문항 영상에 한해 더 자주 주입할지.
- **분류기 단순화 (#26)**: 틀린 읽기·계산 인자가 뒤에서 쓰였을 때 "올바른 값으로 바꿔 다시 실행" 검사를 하지 않고, 쓰였으면 이탈로 센다. 잘못된 분기를 택한 뒤의 도구·계산 호출은 그 분기의 결과로 보고 무해 처리한다.
- **시드 결정성**: 같은 세션에서 8/8 동일 (docs/env_notes.md). 재시작 뒤 결정성은 미확인.
- **일괄 계획의 최종 호출 필드**는 SPEC의 `readings` 대신 단계별과 같은 `reading`으로 통일했다.
- 에이전트 프롬프트 파일 4개는 초안이다. 파일럿에서 dev 결과로만 조정한다.

## 막힌 것

- 없음. (Bash 권한 검사가 몇 번 일시 실패했으나 재시도로 해결. 작업 손실 없음.)

## 파일럿 A 결과

- (미실행)
