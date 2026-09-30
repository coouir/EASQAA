# 첫 이탈이 "해석"인 사례 (파일럿 A, 조건 1·2)

자동 생성: `python -m sarqa.analysis.interpretation_cases` (입력: `outputs/runs/pilotA/questions_at_run.json`). 어휘와 문구는 바꾸지 않았다. "다른 필드"는 정답 풀이가 쓰는 필드(판정에 쓰임)와 쓰지 않는 필드(참고)를 나눠 적었다. 해석은 항상 가장 이른 턴이라, 사례에 해석 차이가 있고 그것이 "무해"(호출·분기가 정답 방식으로 이뤄짐)로 판정되지 않으면 첫 이탈이 된다.

## 조건 1 (label 입력): 13건

정답 풀이가 쓰는 필드 중 다른 필드별 건수: {'answer_type': 7, 'target': 8, 'branch': 6, 'filters': 1}; 이 중 최종 답이 맞은 건: 0

| qid | 템플릿 | 다른 필드(쓰임) | 다른 필드(안 쓰임) | 최종 답 | 정오 |
|---|---|---|---|---|---|
| D-L2-016 | `l2_longest_neighbor` | answer_type | - | (답 없음: budget_exceeded) | 오답 (정답값 408.6) |
| D-L2-019 | `l2_longest_shortest_distance` | answer_type | - | (답 없음: format_error) | 오답 (정답값 124.9) |
| D-L3-007 | `l3_empty_quadrants` | answer_type | - | 2 none | 오답 (정답값 3) |
| D-L3-008 | `l3_empty_quadrants` | answer_type | - | 1 none | 오답 (정답값 2) |
| D-L3-010 | `l3_empty_quadrants` | answer_type | - | 1 none | 오답 (정답값 2) |
| D-L4-007 | `l4_count_branch` | target, answer_type | - | 679 px | 오답 (정답값 42) |
| D-L4-012 | `l4_quadrant_branch` | target, answer_type | filters | (답 없음: budget_exceeded) | 오답 (정답값 26) |
| D-L4-019 | `l4_noise_branch` | target, branch | - | 1 ships | 오답 (정답값 2) |
| D-L5-001 | `l5_noisy_quadrant` | target, filters, branch | - | (답 없음: budget_exceeded) | 오답 (정답값 0) |
| D-L5-002 | `l5_noisy_quadrant` | target, branch | - | (답 없음: budget_exceeded) | 오답 (정답값 3) |
| D-L5-003 | `l5_noisy_quadrant` | target, branch | - | (답 없음: budget_exceeded) | 오답 (정답값 1) |
| D-L5-004 | `l5_scene_quadrant` | target, branch | region | (답 없음: budget_exceeded) | 오답 (정답값 1) |
| D-L5-005 | `l5_scene_quadrant` | target, branch | region | 1 ships | 오답 (정답값 0) |

### D-L2-016 · 조건 1 · `l2_longest_neighbor`

- 질문: 가장 긴 선박에서 가장 가까운 다른 선박까지의 중심 사이 거리는 몇 px인가?
- 정답 해석: `{"target":"longest_neighbor_distance","region":"full","filters":[],"branch":null,"unit":"px","answer_type":"float"}`
- 에이전트 해석: `{"target":"longest_neighbor_distance","region":"full","filters":[],"branch":null,"unit":"px","answer_type":"int"}`
- 다른 필드 `answer_type` (쓰임): 정답 `"float"` / 에이전트 `"int"`
- 최종 답: 없음 (budget_exceeded) → 오답, 정답값 408.6, 에이전트가 받은 상자로 도달 가능한 값 408.6

### D-L2-019 · 조건 1 · `l2_longest_shortest_distance`

- 질문: 가장 긴 선박과 가장 짧은 선박 사이의 중심 거리는 몇 px인가?
- 정답 해석: `{"target":"pair_distance","region":"full","filters":[],"branch":null,"unit":"px","answer_type":"float"}`
- 에이전트 해석: `{"target":"pair_distance","region":"full","filters":[],"branch":null,"unit":"px","answer_type":"int"}`
- 다른 필드 `answer_type` (쓰임): 정답 `"float"` / 에이전트 `"int"`
- 최종 답: 없음 (format_error) → 오답, 정답값 124.9, 에이전트가 받은 상자로 도달 가능한 값 124.9

### D-L3-007 · 조건 1 · `l3_empty_quadrants`

- 질문: 선박이 한 척도 없는 사분면은 몇 개인가?
- 정답 해석: `{"target":"empty_region_count","region":"full","filters":[],"branch":null,"unit":"none","answer_type":"int"}`
- 에이전트 해석: `{"target":"empty_region_count","region":"full","filters":[],"branch":null,"unit":"none","answer_type":"category"}`
- 다른 필드 `answer_type` (쓰임): 정답 `"int"` / 에이전트 `"category"`
- 최종 답: 2 none → 오답, 정답값 3, 에이전트가 받은 상자로 도달 가능한 값 3

### D-L3-008 · 조건 1 · `l3_empty_quadrants`

- 질문: 선박이 한 척도 없는 사분면은 몇 개인가?
- 정답 해석: `{"target":"empty_region_count","region":"full","filters":[],"branch":null,"unit":"none","answer_type":"int"}`
- 에이전트 해석: `{"target":"empty_region_count","region":"full","filters":[],"branch":null,"unit":"none","answer_type":"category"}`
- 다른 필드 `answer_type` (쓰임): 정답 `"int"` / 에이전트 `"category"`
- 최종 답: 1 none → 오답, 정답값 2, 에이전트가 받은 상자로 도달 가능한 값 2

### D-L3-010 · 조건 1 · `l3_empty_quadrants`

- 질문: 선박이 한 척도 없는 사분면은 몇 개인가?
- 정답 해석: `{"target":"empty_region_count","region":"full","filters":[],"branch":null,"unit":"none","answer_type":"int"}`
- 에이전트 해석: `{"target":"empty_region_count","region":"full","filters":[],"branch":null,"unit":"none","answer_type":"category"}`
- 다른 필드 `answer_type` (쓰임): 정답 `"int"` / 에이전트 `"category"`
- 최종 답: 1 none → 오답, 정답값 2, 에이전트가 받은 상자로 도달 가능한 값 2

### D-L4-007 · 조건 1 · `l4_count_branch`

- 질문: 이 영상의 선박이 12척을 초과하면 가장 가까운 두 선박의 중심 사이 거리(px)를, 그렇지 않으면 가장 긴 선박의 긴 변(px)을 답하라.
- 정답 해석: `{"target":"branch","region":"full","filters":[],"branch":{"on":"ship_count","cmp":">","threshold":12,"then_target":"nearest_distance","else_target":"max_length","then_region":null,"else_region":null},"unit":"px","answer_type":"float"}`
- 에이전트 해석: `{"target":"nearest_distance","region":"full","filters":[],"branch":{"on":"ship_count","cmp":">","threshold":12,"then_target":"nearest_distance","else_target":"max_length","then_region":"full","else_region":"full"},"unit":"px","answer_type":"int"}`
- 다른 필드 `target` (쓰임): 정답 `"branch"` / 에이전트 `"nearest_distance"`
- 다른 필드 `answer_type` (쓰임): 정답 `"float"` / 에이전트 `"int"`
- 최종 답: 679 px → 오답, 정답값 42, 에이전트가 받은 상자로 도달 가능한 값 42

### D-L4-012 · 조건 1 · `l4_quadrant_branch`

- 질문: 오른쪽 아래 사분면의 선박이 2척 이상이면 그 사분면에서 가장 긴 선박의 긴 변(px)을, 아니면 영상 전체에서 가장 가까운 두 선박의 중심 사이 거리(px)를 답하라.
- 정답 해석: `{"target":"branch","region":"bottom_right","filters":[],"branch":{"on":"ship_count","cmp":">=","threshold":2,"then_target":"max_length","else_target":"nearest_distance","then_region":"bottom_right","else_region":"full"},"unit":"px","answer_type":"float"}`
- 에이전트 해석: `{"target":"ship_count","region":"bottom_right","filters":[{"field":"length_px","cmp":">","threshold":0}],"branch":{"on":"ship_count","cmp":">=","threshold":2,"then_target":"max_length","else_target":"nearest_distance","then_region":"bottom_right","else_region":"full"},"unit":"px","answer_type":"int"}`
- 다른 필드 `target` (쓰임): 정답 `"branch"` / 에이전트 `"ship_count"`
- 다른 필드 `answer_type` (쓰임): 정답 `"float"` / 에이전트 `"int"`
- 다른 필드 `filters` (안 쓰임): 정답 `[]` / 에이전트 `[{"field":"length_px","cmp":">","threshold":0}]`
- 최종 답: 없음 (budget_exceeded) → 오답, 정답값 26, 에이전트가 받은 상자로 도달 가능한 값 26

### D-L4-019 · 조건 1 · `l4_noise_branch`

- 질문: 이 영상 전체의 배경 잡음 수치가 3.0보다 크면 전체 선박 수를, 그렇지 않으면 가장자리 20 px 이내에 있는 선박 수를 답하라.
- 정답 해석: `{"target":"branch","region":"full","filters":[],"branch":{"on":"noise","cmp":">","threshold":3.0,"then_target":"ship_count","else_target":"ship_count","then_region":"full","else_region":"edge"},"unit":"ships","answer_type":"int"}`
- 에이전트 해석: `{"target":"ship_count","region":"full","filters":[],"branch":{"on":"scene","cmp":"==","threshold":"inshore","then_target":"ship_count","else_target":"ship_count","then_region":"full","else_region":"edge"},"unit":"ships","answer_type":"int"}`
- 다른 필드 `target` (쓰임): 정답 `"branch"` / 에이전트 `"ship_count"`
- 다른 필드 `branch` (쓰임): 정답 `{"on":"noise","cmp":">","threshold":3.0,"then_target":"ship_count","else_target":"ship_count","then_region":"full","else_region":"edge"}` / 에이전트 `{"on":"scene","cmp":"==","threshold":"inshore","then_target":"ship_count","else_target":"ship_count","then_region":"full","else_region":"edge"}`
- 최종 답: 1 ships → 오답, 정답값 2, 에이전트가 받은 상자로 도달 가능한 값 2

### D-L5-001 · 조건 1 · `l5_noisy_quadrant`

- 질문: 배경 잡음 수치가 가장 큰 사분면을 찾아라. 그 사분면의 선박이 2척 이상이면 그 사분면에서 긴 변이 100 px 이상인 선박의 수를, 아니면 그 사분면의 선박 수를 답하라.
- 정답 해석: `{"target":"branch","region":"noisiest_region","filters":[{"field":"length_px","cmp":">=","threshold":100}],"branch":{"on":"ship_count","cmp":">=","threshold":2,"then_target":"count_over_threshold","else_target":"ship_count","then_region":null,"else_region":null},"unit":"ships","answer_type":"int"}`
- 에이전트 해석: `{"target":"noisiest_region","region":"noisiest_region","filters":[{"field":"length_px","cmp":">","threshold":100}],"branch":null,"unit":"ships","answer_type":"int"}`
- 다른 필드 `target` (쓰임): 정답 `"branch"` / 에이전트 `"noisiest_region"`
- 다른 필드 `filters` (쓰임): 정답 `[{"field":"length_px","cmp":">=","threshold":100}]` / 에이전트 `[{"field":"length_px","cmp":">","threshold":100}]`
- 다른 필드 `branch` (쓰임): 정답 `{"on":"ship_count","cmp":">=","threshold":2,"then_target":"count_over_threshold","else_target":"ship_count","then_region":null,"else_region":null}` / 에이전트 `null`
- 최종 답: 없음 (budget_exceeded) → 오답, 정답값 0, 에이전트가 받은 상자로 도달 가능한 값 0

### D-L5-002 · 조건 1 · `l5_noisy_quadrant`

- 질문: 배경 잡음 수치가 가장 큰 사분면을 찾아라. 그 사분면의 선박이 6척 이상이면 그 사분면에서 긴 변이 140 px 이상인 선박의 수를, 아니면 그 사분면의 선박 수를 답하라.
- 정답 해석: `{"target":"branch","region":"noisiest_region","filters":[{"field":"length_px","cmp":">=","threshold":140}],"branch":{"on":"ship_count","cmp":">=","threshold":6,"then_target":"count_over_threshold","else_target":"ship_count","then_region":null,"else_region":null},"unit":"ships","answer_type":"int"}`
- 에이전트 해석: `{"target":"noisiest_region","region":"noisiest_region","filters":[{"field":"length_px","cmp":">=","threshold":140}],"branch":null,"unit":"ships","answer_type":"int"}`
- 다른 필드 `target` (쓰임): 정답 `"branch"` / 에이전트 `"noisiest_region"`
- 다른 필드 `branch` (쓰임): 정답 `{"on":"ship_count","cmp":">=","threshold":6,"then_target":"count_over_threshold","else_target":"ship_count","then_region":null,"else_region":null}` / 에이전트 `null`
- 최종 답: 없음 (budget_exceeded) → 오답, 정답값 3, 에이전트가 받은 상자로 도달 가능한 값 3

### D-L5-003 · 조건 1 · `l5_noisy_quadrant`

- 질문: 배경 잡음 수치가 가장 큰 사분면을 찾아라. 그 사분면의 선박이 5척 이상이면 그 사분면에서 긴 변이 85 px 이상인 선박의 수를, 아니면 그 사분면의 선박 수를 답하라.
- 정답 해석: `{"target":"branch","region":"noisiest_region","filters":[{"field":"length_px","cmp":">=","threshold":85}],"branch":{"on":"ship_count","cmp":">=","threshold":5,"then_target":"count_over_threshold","else_target":"ship_count","then_region":null,"else_region":null},"unit":"ships","answer_type":"int"}`
- 에이전트 해석: `{"target":"noisiest_region","region":"noisiest_region","filters":[{"field":"length_px","cmp":">=","threshold":85}],"branch":null,"unit":"ships","answer_type":"int"}`
- 다른 필드 `target` (쓰임): 정답 `"branch"` / 에이전트 `"noisiest_region"`
- 다른 필드 `branch` (쓰임): 정답 `{"on":"ship_count","cmp":">=","threshold":5,"then_target":"count_over_threshold","else_target":"ship_count","then_region":null,"else_region":null}` / 에이전트 `null`
- 최종 답: 없음 (budget_exceeded) → 오답, 정답값 1, 에이전트가 받은 상자로 도달 가능한 값 1

### D-L5-004 · 조건 1 · `l5_scene_quadrant`

- 질문: 이 영상이 연안(inshore) 장면이면 배경 잡음 수치가 가장 큰 사분면에서, 외해(offshore) 장면이면 선박이 가장 많은 사분면에서 긴 변이 130 px 이상인 선박은 몇 척인가?
- 정답 해석: `{"target":"branch","region":"full","filters":[{"field":"length_px","cmp":">=","threshold":130}],"branch":{"on":"scene","cmp":"==","threshold":"inshore","then_target":"count_over_threshold","else_target":"count_over_threshold","then_region":"noisiest_region","else_region":"densest_region"},"unit":"ships","answer_type":"int"}`
- 에이전트 해석: `{"target":"count_over_threshold","region":"noisiest_region","filters":[{"field":"length_px","cmp":">=","threshold":130}],"branch":{"on":"scene","cmp":"==","threshold":"inshore","then_target":"count_over_threshold","else_target":"count_over_threshold","then_region":"noisiest_region","else_region":"full"},"unit":"ships","answer_type":"int"}`
- 다른 필드 `target` (쓰임): 정답 `"branch"` / 에이전트 `"count_over_threshold"`
- 다른 필드 `branch` (쓰임): 정답 `{"on":"scene","cmp":"==","threshold":"inshore","then_target":"count_over_threshold","else_target":"count_over_threshold","then_region":"noisiest_region","else_region":"densest_region"}` / 에이전트 `{"on":"scene","cmp":"==","threshold":"inshore","then_target":"count_over_threshold","else_target":"count_over_threshold","then_region":"noisiest_region","else_region":"full"}`
- 다른 필드 `region` (안 쓰임): 정답 `"full"` / 에이전트 `"noisiest_region"`
- 최종 답: 없음 (budget_exceeded) → 오답, 정답값 1, 에이전트가 받은 상자로 도달 가능한 값 1

### D-L5-005 · 조건 1 · `l5_scene_quadrant`

- 질문: 이 영상이 연안(inshore) 장면이면 배경 잡음 수치가 가장 큰 사분면에서, 외해(offshore) 장면이면 선박이 가장 많은 사분면에서 긴 변이 55 px 이상인 선박은 몇 척인가?
- 정답 해석: `{"target":"branch","region":"full","filters":[{"field":"length_px","cmp":">=","threshold":55}],"branch":{"on":"scene","cmp":"==","threshold":"inshore","then_target":"count_over_threshold","else_target":"count_over_threshold","then_region":"noisiest_region","else_region":"densest_region"},"unit":"ships","answer_type":"int"}`
- 에이전트 해석: `{"target":"count_over_threshold","region":"noisiest_region","filters":[{"field":"length_px","cmp":">=","threshold":55}],"branch":{"on":"scene","cmp":"==","threshold":"inshore","then_target":"count_over_threshold","else_target":"count_over_threshold","then_region":"noisiest_region","else_region":"full"},"unit":"ships","answer_type":"int"}`
- 다른 필드 `target` (쓰임): 정답 `"branch"` / 에이전트 `"count_over_threshold"`
- 다른 필드 `branch` (쓰임): 정답 `{"on":"scene","cmp":"==","threshold":"inshore","then_target":"count_over_threshold","else_target":"count_over_threshold","then_region":"noisiest_region","else_region":"densest_region"}` / 에이전트 `{"on":"scene","cmp":"==","threshold":"inshore","then_target":"count_over_threshold","else_target":"count_over_threshold","then_region":"noisiest_region","else_region":"full"}`
- 다른 필드 `region` (안 쓰임): 정답 `"full"` / 에이전트 `"noisiest_region"`
- 최종 답: 1 ships → 오답, 정답값 0, 에이전트가 받은 상자로 도달 가능한 값 0

## 조건 2 (detected 입력): 13건

정답 풀이가 쓰는 필드 중 다른 필드별 건수: {'answer_type': 7, 'target': 9, 'branch': 6, 'filters': 1}; 이 중 최종 답이 맞은 건: 0

| qid | 템플릿 | 다른 필드(쓰임) | 다른 필드(안 쓰임) | 최종 답 | 정오 |
|---|---|---|---|---|---|
| D-L2-016 | `l2_longest_neighbor` | answer_type | - | (답 없음: budget_exceeded) | 오답 (정답값 408.6) |
| D-L2-018 | `l2_longest_neighbor` | answer_type | - | (답 없음: budget_exceeded) | 오답 (정답값 414.9) |
| D-L3-007 | `l3_empty_quadrants` | answer_type | - | 2 none | 오답 (정답값 3) |
| D-L3-008 | `l3_empty_quadrants` | answer_type | - | (답 없음: budget_exceeded) | 오답 (정답값 2) |
| D-L4-003 | `l4_scene_branch` | target, answer_type | - | (답 없음: budget_exceeded) | 오답 (정답값 425.6) |
| D-L4-007 | `l4_count_branch` | target, answer_type | - | 678 px | 오답 (정답값 42) |
| D-L4-012 | `l4_quadrant_branch` | target, answer_type | filters | (답 없음: budget_exceeded) | 오답 (정답값 26) |
| D-L4-019 | `l4_noise_branch` | target, branch | - | 1 ships | 오답 (정답값 2) |
| D-L5-001 | `l5_noisy_quadrant` | target, filters, branch | - | (답 없음: budget_exceeded) | 오답 (정답값 0) |
| D-L5-002 | `l5_noisy_quadrant` | target, branch | - | (답 없음: budget_exceeded) | 오답 (정답값 3) |
| D-L5-003 | `l5_noisy_quadrant` | target, branch | - | (답 없음: budget_exceeded) | 오답 (정답값 1) |
| D-L5-004 | `l5_scene_quadrant` | target, branch | region | (답 없음: budget_exceeded) | 오답 (정답값 1) |
| D-L5-005 | `l5_scene_quadrant` | target, branch | region | 1 ships | 오답 (정답값 0) |

### D-L2-016 · 조건 2 · `l2_longest_neighbor`

- 질문: 가장 긴 선박에서 가장 가까운 다른 선박까지의 중심 사이 거리는 몇 px인가?
- 정답 해석: `{"target":"longest_neighbor_distance","region":"full","filters":[],"branch":null,"unit":"px","answer_type":"float"}`
- 에이전트 해석: `{"target":"longest_neighbor_distance","region":"full","filters":[],"branch":null,"unit":"px","answer_type":"int"}`
- 다른 필드 `answer_type` (쓰임): 정답 `"float"` / 에이전트 `"int"`
- 최종 답: 없음 (budget_exceeded) → 오답, 정답값 408.6, 에이전트가 받은 상자로 도달 가능한 값 407.9

### D-L2-018 · 조건 2 · `l2_longest_neighbor`

- 질문: 가장 긴 선박에서 가장 가까운 다른 선박까지의 중심 사이 거리는 몇 px인가?
- 정답 해석: `{"target":"longest_neighbor_distance","region":"full","filters":[],"branch":null,"unit":"px","answer_type":"float"}`
- 에이전트 해석: `{"target":"longest_neighbor_distance","region":"full","filters":[],"branch":null,"unit":"px","answer_type":"int"}`
- 다른 필드 `answer_type` (쓰임): 정답 `"float"` / 에이전트 `"int"`
- 최종 답: 없음 (budget_exceeded) → 오답, 정답값 414.9, 에이전트가 받은 상자로 도달 가능한 값 413.6

### D-L3-007 · 조건 2 · `l3_empty_quadrants`

- 질문: 선박이 한 척도 없는 사분면은 몇 개인가?
- 정답 해석: `{"target":"empty_region_count","region":"full","filters":[],"branch":null,"unit":"none","answer_type":"int"}`
- 에이전트 해석: `{"target":"empty_region_count","region":"full","filters":[],"branch":null,"unit":"none","answer_type":"category"}`
- 다른 필드 `answer_type` (쓰임): 정답 `"int"` / 에이전트 `"category"`
- 최종 답: 2 none → 오답, 정답값 3, 에이전트가 받은 상자로 도달 가능한 값 3

### D-L3-008 · 조건 2 · `l3_empty_quadrants`

- 질문: 선박이 한 척도 없는 사분면은 몇 개인가?
- 정답 해석: `{"target":"empty_region_count","region":"full","filters":[],"branch":null,"unit":"none","answer_type":"int"}`
- 에이전트 해석: `{"target":"empty_region_count","region":"full","filters":[],"branch":null,"unit":"none","answer_type":"category"}`
- 다른 필드 `answer_type` (쓰임): 정답 `"int"` / 에이전트 `"category"`
- 최종 답: 없음 (budget_exceeded) → 오답, 정답값 2, 에이전트가 받은 상자로 도달 가능한 값 2

### D-L4-003 · 조건 2 · `l4_scene_branch`

- 질문: 이 영상이 연안(inshore) 장면이면 가장 가까운 두 선박의 중심 사이 거리(px)를, 외해(offshore) 장면이면 가장 긴 선박의 긴 변(px)을 답하라.
- 정답 해석: `{"target":"branch","region":"full","filters":[],"branch":{"on":"scene","cmp":"==","threshold":"inshore","then_target":"nearest_distance","else_target":"max_length","then_region":null,"else_region":null},"unit":"px","answer_type":"float"}`
- 에이전트 해석: `{"target":"nearest_distance","region":"full","filters":[],"branch":{"on":"scene","cmp":"==","threshold":"inshore","then_target":"nearest_distance","else_target":"max_length","then_region":"full","else_region":"full"},"unit":"px","answer_type":"int"}`
- 다른 필드 `target` (쓰임): 정답 `"branch"` / 에이전트 `"nearest_distance"`
- 다른 필드 `answer_type` (쓰임): 정답 `"float"` / 에이전트 `"int"`
- 최종 답: 없음 (budget_exceeded) → 오답, 정답값 425.6, 에이전트가 받은 상자로 도달 가능한 값 null

### D-L4-007 · 조건 2 · `l4_count_branch`

- 질문: 이 영상의 선박이 12척을 초과하면 가장 가까운 두 선박의 중심 사이 거리(px)를, 그렇지 않으면 가장 긴 선박의 긴 변(px)을 답하라.
- 정답 해석: `{"target":"branch","region":"full","filters":[],"branch":{"on":"ship_count","cmp":">","threshold":12,"then_target":"nearest_distance","else_target":"max_length","then_region":null,"else_region":null},"unit":"px","answer_type":"float"}`
- 에이전트 해석: `{"target":"nearest_distance","region":"full","filters":[],"branch":{"on":"ship_count","cmp":">","threshold":12,"then_target":"nearest_distance","else_target":"max_length","then_region":"full","else_region":"full"},"unit":"px","answer_type":"int"}`
- 다른 필드 `target` (쓰임): 정답 `"branch"` / 에이전트 `"nearest_distance"`
- 다른 필드 `answer_type` (쓰임): 정답 `"float"` / 에이전트 `"int"`
- 최종 답: 678 px → 오답, 정답값 42, 에이전트가 받은 상자로 도달 가능한 값 43

### D-L4-012 · 조건 2 · `l4_quadrant_branch`

- 질문: 오른쪽 아래 사분면의 선박이 2척 이상이면 그 사분면에서 가장 긴 선박의 긴 변(px)을, 아니면 영상 전체에서 가장 가까운 두 선박의 중심 사이 거리(px)를 답하라.
- 정답 해석: `{"target":"branch","region":"bottom_right","filters":[],"branch":{"on":"ship_count","cmp":">=","threshold":2,"then_target":"max_length","else_target":"nearest_distance","then_region":"bottom_right","else_region":"full"},"unit":"px","answer_type":"float"}`
- 에이전트 해석: `{"target":"ship_count","region":"bottom_right","filters":[{"field":"length_px","cmp":">","threshold":0}],"branch":{"on":"ship_count","cmp":">=","threshold":2,"then_target":"max_length","else_target":"nearest_distance","then_region":"bottom_right","else_region":"full"},"unit":"px","answer_type":"int"}`
- 다른 필드 `target` (쓰임): 정답 `"branch"` / 에이전트 `"ship_count"`
- 다른 필드 `answer_type` (쓰임): 정답 `"float"` / 에이전트 `"int"`
- 다른 필드 `filters` (안 쓰임): 정답 `[]` / 에이전트 `[{"field":"length_px","cmp":">","threshold":0}]`
- 최종 답: 없음 (budget_exceeded) → 오답, 정답값 26, 에이전트가 받은 상자로 도달 가능한 값 23

### D-L4-019 · 조건 2 · `l4_noise_branch`

- 질문: 이 영상 전체의 배경 잡음 수치가 3.0보다 크면 전체 선박 수를, 그렇지 않으면 가장자리 20 px 이내에 있는 선박 수를 답하라.
- 정답 해석: `{"target":"branch","region":"full","filters":[],"branch":{"on":"noise","cmp":">","threshold":3.0,"then_target":"ship_count","else_target":"ship_count","then_region":"full","else_region":"edge"},"unit":"ships","answer_type":"int"}`
- 에이전트 해석: `{"target":"ship_count","region":"full","filters":[],"branch":{"on":"scene","cmp":"==","threshold":"inshore","then_target":"ship_count","else_target":"ship_count","then_region":"full","else_region":"edge"},"unit":"ships","answer_type":"int"}`
- 다른 필드 `target` (쓰임): 정답 `"branch"` / 에이전트 `"ship_count"`
- 다른 필드 `branch` (쓰임): 정답 `{"on":"noise","cmp":">","threshold":3.0,"then_target":"ship_count","else_target":"ship_count","then_region":"full","else_region":"edge"}` / 에이전트 `{"on":"scene","cmp":"==","threshold":"inshore","then_target":"ship_count","else_target":"ship_count","then_region":"full","else_region":"edge"}`
- 최종 답: 1 ships → 오답, 정답값 2, 에이전트가 받은 상자로 도달 가능한 값 2

### D-L5-001 · 조건 2 · `l5_noisy_quadrant`

- 질문: 배경 잡음 수치가 가장 큰 사분면을 찾아라. 그 사분면의 선박이 2척 이상이면 그 사분면에서 긴 변이 100 px 이상인 선박의 수를, 아니면 그 사분면의 선박 수를 답하라.
- 정답 해석: `{"target":"branch","region":"noisiest_region","filters":[{"field":"length_px","cmp":">=","threshold":100}],"branch":{"on":"ship_count","cmp":">=","threshold":2,"then_target":"count_over_threshold","else_target":"ship_count","then_region":null,"else_region":null},"unit":"ships","answer_type":"int"}`
- 에이전트 해석: `{"target":"noisiest_region","region":"noisiest_region","filters":[{"field":"length_px","cmp":">","threshold":100}],"branch":null,"unit":"ships","answer_type":"int"}`
- 다른 필드 `target` (쓰임): 정답 `"branch"` / 에이전트 `"noisiest_region"`
- 다른 필드 `filters` (쓰임): 정답 `[{"field":"length_px","cmp":">=","threshold":100}]` / 에이전트 `[{"field":"length_px","cmp":">","threshold":100}]`
- 다른 필드 `branch` (쓰임): 정답 `{"on":"ship_count","cmp":">=","threshold":2,"then_target":"count_over_threshold","else_target":"ship_count","then_region":null,"else_region":null}` / 에이전트 `null`
- 최종 답: 없음 (budget_exceeded) → 오답, 정답값 0, 에이전트가 받은 상자로 도달 가능한 값 0

### D-L5-002 · 조건 2 · `l5_noisy_quadrant`

- 질문: 배경 잡음 수치가 가장 큰 사분면을 찾아라. 그 사분면의 선박이 6척 이상이면 그 사분면에서 긴 변이 140 px 이상인 선박의 수를, 아니면 그 사분면의 선박 수를 답하라.
- 정답 해석: `{"target":"branch","region":"noisiest_region","filters":[{"field":"length_px","cmp":">=","threshold":140}],"branch":{"on":"ship_count","cmp":">=","threshold":6,"then_target":"count_over_threshold","else_target":"ship_count","then_region":null,"else_region":null},"unit":"ships","answer_type":"int"}`
- 에이전트 해석: `{"target":"noisiest_region","region":"noisiest_region","filters":[{"field":"length_px","cmp":">=","threshold":140}],"branch":null,"unit":"ships","answer_type":"int"}`
- 다른 필드 `target` (쓰임): 정답 `"branch"` / 에이전트 `"noisiest_region"`
- 다른 필드 `branch` (쓰임): 정답 `{"on":"ship_count","cmp":">=","threshold":6,"then_target":"count_over_threshold","else_target":"ship_count","then_region":null,"else_region":null}` / 에이전트 `null`
- 최종 답: 없음 (budget_exceeded) → 오답, 정답값 3, 에이전트가 받은 상자로 도달 가능한 값 2

### D-L5-003 · 조건 2 · `l5_noisy_quadrant`

- 질문: 배경 잡음 수치가 가장 큰 사분면을 찾아라. 그 사분면의 선박이 5척 이상이면 그 사분면에서 긴 변이 85 px 이상인 선박의 수를, 아니면 그 사분면의 선박 수를 답하라.
- 정답 해석: `{"target":"branch","region":"noisiest_region","filters":[{"field":"length_px","cmp":">=","threshold":85}],"branch":{"on":"ship_count","cmp":">=","threshold":5,"then_target":"count_over_threshold","else_target":"ship_count","then_region":null,"else_region":null},"unit":"ships","answer_type":"int"}`
- 에이전트 해석: `{"target":"noisiest_region","region":"noisiest_region","filters":[{"field":"length_px","cmp":">=","threshold":85}],"branch":null,"unit":"ships","answer_type":"int"}`
- 다른 필드 `target` (쓰임): 정답 `"branch"` / 에이전트 `"noisiest_region"`
- 다른 필드 `branch` (쓰임): 정답 `{"on":"ship_count","cmp":">=","threshold":5,"then_target":"count_over_threshold","else_target":"ship_count","then_region":null,"else_region":null}` / 에이전트 `null`
- 최종 답: 없음 (budget_exceeded) → 오답, 정답값 1, 에이전트가 받은 상자로 도달 가능한 값 1

### D-L5-004 · 조건 2 · `l5_scene_quadrant`

- 질문: 이 영상이 연안(inshore) 장면이면 배경 잡음 수치가 가장 큰 사분면에서, 외해(offshore) 장면이면 선박이 가장 많은 사분면에서 긴 변이 130 px 이상인 선박은 몇 척인가?
- 정답 해석: `{"target":"branch","region":"full","filters":[{"field":"length_px","cmp":">=","threshold":130}],"branch":{"on":"scene","cmp":"==","threshold":"inshore","then_target":"count_over_threshold","else_target":"count_over_threshold","then_region":"noisiest_region","else_region":"densest_region"},"unit":"ships","answer_type":"int"}`
- 에이전트 해석: `{"target":"count_over_threshold","region":"noisiest_region","filters":[{"field":"length_px","cmp":">=","threshold":130}],"branch":{"on":"scene","cmp":"==","threshold":"inshore","then_target":"count_over_threshold","else_target":"count_over_threshold","then_region":"noisiest_region","else_region":"full"},"unit":"ships","answer_type":"int"}`
- 다른 필드 `target` (쓰임): 정답 `"branch"` / 에이전트 `"count_over_threshold"`
- 다른 필드 `branch` (쓰임): 정답 `{"on":"scene","cmp":"==","threshold":"inshore","then_target":"count_over_threshold","else_target":"count_over_threshold","then_region":"noisiest_region","else_region":"densest_region"}` / 에이전트 `{"on":"scene","cmp":"==","threshold":"inshore","then_target":"count_over_threshold","else_target":"count_over_threshold","then_region":"noisiest_region","else_region":"full"}`
- 다른 필드 `region` (안 쓰임): 정답 `"full"` / 에이전트 `"noisiest_region"`
- 최종 답: 없음 (budget_exceeded) → 오답, 정답값 1, 에이전트가 받은 상자로 도달 가능한 값 1

### D-L5-005 · 조건 2 · `l5_scene_quadrant`

- 질문: 이 영상이 연안(inshore) 장면이면 배경 잡음 수치가 가장 큰 사분면에서, 외해(offshore) 장면이면 선박이 가장 많은 사분면에서 긴 변이 55 px 이상인 선박은 몇 척인가?
- 정답 해석: `{"target":"branch","region":"full","filters":[{"field":"length_px","cmp":">=","threshold":55}],"branch":{"on":"scene","cmp":"==","threshold":"inshore","then_target":"count_over_threshold","else_target":"count_over_threshold","then_region":"noisiest_region","else_region":"densest_region"},"unit":"ships","answer_type":"int"}`
- 에이전트 해석: `{"target":"count_over_threshold","region":"noisiest_region","filters":[{"field":"length_px","cmp":">=","threshold":55}],"branch":{"on":"scene","cmp":"==","threshold":"inshore","then_target":"count_over_threshold","else_target":"count_over_threshold","then_region":"noisiest_region","else_region":"full"},"unit":"ships","answer_type":"int"}`
- 다른 필드 `target` (쓰임): 정답 `"branch"` / 에이전트 `"count_over_threshold"`
- 다른 필드 `branch` (쓰임): 정답 `{"on":"scene","cmp":"==","threshold":"inshore","then_target":"count_over_threshold","else_target":"count_over_threshold","then_region":"noisiest_region","else_region":"densest_region"}` / 에이전트 `{"on":"scene","cmp":"==","threshold":"inshore","then_target":"count_over_threshold","else_target":"count_over_threshold","then_region":"noisiest_region","else_region":"full"}`
- 다른 필드 `region` (안 쓰임): 정답 `"full"` / 에이전트 `"noisiest_region"`
- 최종 답: 1 ships → 오답, 정답값 0, 에이전트가 받은 상자로 도달 가능한 값 0

