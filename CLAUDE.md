# EASQAA
SAR 질의응답 에이전트 오류 분석 실험. 기준 문서는 SPEC.md.

## 규칙
- 먼저 SPEC.md §0, §2, 해당 마일스톤(§14)을 읽는다.
- 10/4 동결(git tag freeze-v1) 이후 src/sarqa/(analysis/ 제외), configs/, pyproject.toml, PROTOCOL.md는 수정 금지. 데이터 해시는 PROTOCOL.md에 있다.
- 오답은 입력 오류(속성)와 에이전트 첫 이탈 단계로 나눠 기록한다 (SPEC §11).
- 두 에이전트(단계별·일괄)는 같은 참조 규칙($c<k>.<field>)과 같은 시드 규칙(hash(qid, repeat))을 쓴다.
- test 결과를 보고 규칙을 바꾸지 않는다. dev에서만 조정한다.
- 정답 풀이와 도구는 같은 함수를 쓴다 (program.py ↔ tools/).
- 에이전트는 텍스트만 본다. 영상·정답을 프롬프트에 넣지 않는다.
- 명세와 다르게 해야 하면 docs/deviations.md에 적고 사용자에게 알린다.
- 실행은 중단되지 않는다: 오류는 기록하고 다음 실행으로.
- 작업은 이슈 → 브랜치(`<종류>/<번호>-<슬러그>`) → PR. main에 직접 push 금지. 커밋은 `type(scope): subject`(영어).
- PR은 체크리스트를 채워 열고, 병합은 사용자가 한다.

## 명령
- pytest
- sarqa run --conditions all --split test
- sarqa classify --runs outputs/runs/
- sarqa analyze --runs outputs/runs/
