# M3 진행 보고 (야간 자동 진행)

작성: Claude Code, 2026-09-30 밤. 사용자가 아침에 확인한다. 기준 문서 SPEC.md §6, §7, §8, §11, §14 M3.
PR은 앞 브랜치 위에 쌓았고 **병합은 하지 않았다.** 아래 표의 순서대로 병합하면 된다.

## 단계 현황

| # | 단계 | 상태 | 이슈 / PR |
|---|---|---|---|
| 1 | get_metadata에 영상 크기(width, height) 추가 | 완료 | #56 / [PR #57](https://github.com/coouir/EASQAA/pull/57) |
| 2a | L1~L5 템플릿 카탈로그 (23개), 해석 어휘 | 완료 | #17 / [PR #58](https://github.com/coouir/EASQAA/pull/58) |
| 2b | 문항 생성기·필터·검증기·검토 도구 | 완료 | #18 / [PR #59](https://github.com/coouir/EASQAA/pull/59) |
| 2c | dev 90문항 생성, 검토표 `docs/dev_questions.md`, `outputs/gold_check.csv` | 완료 | #19 / PR 아래 참조 |

## 결정한 것

- **dev 문항 (#19)**: 유형별 18/22/23/22/5 = 90, 영상 70장, 상자 의존 75문항(83%), 분기 27문항, 평균 `gold_calls` 3.38 (호출 수 분포 1:18, 2:21, 3:14, 4:5, 5:24, 6:2, 7:1, 8:2, 9:3). `data/questions/dev.json` SHA-256 `d12e1dc3…babb3`. 재생성: `sarqa questions generate --split dev` (시드 고정, 결정적). test 문항은 만들지 않았고 `--allow-test` 없이는 CLI가 거부한다.
- **L2 구조**: 5개 템플릿 모두 calc 포함, 도구 2~3종. 영상 크기를 쓰는 `l2_nearest_ratio`(get_metadata → spatial_query → calc)만 3종이고 나머지는 spatial_query + calc.
- 템플릿 문구·어휘·L4 분기 구성은 `docs/deviations.md`(2026-09-30 4줄)와 `docs/dev_questions.md`에 있다. **아침에 검토할 것**: 문구 전체, 특히 L3 사분면 문항의 답 형식 안내(`top_left, ...` 나열)와 L4/L5 분기 문구.

## 막힌 것

- 없음

## 파일럿 A 결과

- (미실행)
