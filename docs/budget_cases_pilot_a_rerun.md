# 예산 초과 사례 분석 (파일럿 A 재실행, 조건 1·2)

자동 생성: `python -m sarqa.analysis.budget_cases`. 원인 정의는 모듈 머리말 참고.

## 원인 × 조건

| 원인 | 조건 1 | 조건 2 | 합 |
|---|---|---|---|
| termination_failure | 2 | 4 | 6 |
| repeated_call | 2 | 4 | 6 |
| error_loop | 0 | 0 | 0 |
| exploration | 1 | 1 | 2 |
| other | 0 | 0 | 0 |

## 템플릿별

| 템플릿 | 건수 | 원인 |
|---|---|---|
| `l3_empty_quadrants` | 1 | {'termination_failure': 1} |
| `l3_quadrant_most_long` | 2 | {'termination_failure': 1, 'repeated_call': 1} |
| `l3_quadrant_most_ships` | 3 | {'repeated_call': 3} |
| `l4_noise_branch` | 1 | {'termination_failure': 1} |
| `l4_scene_branch` | 2 | {'termination_failure': 2} |
| `l5_noisy_quadrant` | 4 | {'repeated_call': 2, 'exploration': 2} |
| `l5_scene_quadrant` | 1 | {'termination_failure': 1} |

평균 호출 수: 11.4 (평균 상한 11.4, 평균 gold_calls 5.6)

## 사례

| qid | 조건 | 템플릿 | 호출/상한/gold | 원인 | 반복 | 오류 | 없는 호출 | 호출 순서 |
|---|---|---|---|---|---|---|---|---|
| D-L3-001 | 1 | `l3_quadrant_most_ships` | 10/10/5 | repeated_call | 3 | 5 | 4 | detect_ships → spatial_query(sizes,top_left) → spatial_query(sizes,top_right) → spatial_query(sizes,bottom_left) → spatial_query(sizes,bottom_right) → calc(argmax) → calc(argmax) → calc(argmax) → calc(argmax) → calc(argmax) |
| D-L3-013 | 1 | `l3_quadrant_most_long` | 18/18/9 | termination_failure | 9 | 12 | 0 | get_metadata → detect_ships → spatial_query(sizes,top_left) → spatial_query(sizes,top_right) → spatial_query(sizes,bottom_left) → spatial_query(sizes,bottom_right) → calc(argmax) → calc(argmax) → calc(argmax) → calc(argmax) → calc(argmax) → calc(argmax) → calc(argmax) → calc(argmax) → calc(argmax) → calc(argmax) → calc(argmax) → calc(argmax) |
| D-L4-002 | 1 | `l4_scene_branch` | 6/6/3 | termination_failure | 0 | 0 | 0 | get_metadata → detect_ships → spatial_query(sizes) → spatial_query(nearest_pair) → calc(argmax) → spatial_query(distance,s3,s1) |
| D-L5-001 | 1 | `l5_noisy_quadrant` | 14/14/7 | repeated_call | 4 | 5 | 5 | get_metadata → image_stats → detect_ships → spatial_query(edge) → spatial_query(sizes) → spatial_query(count,top_left) → spatial_query(count,top_right) → spatial_query(count,bottom_left) → spatial_query(count,bottom_right) → calc(argmax) → calc(argmax) → calc(argmax) → calc(argmax) → calc(argmax) |
| D-L5-003 | 1 | `l5_noisy_quadrant` | 12/12/6 | exploration | 0 | 0 | 2 | get_metadata → image_stats → detect_ships → spatial_query(edge) → spatial_query(sizes) → spatial_query(count,top_left) → spatial_query(count,top_right) → spatial_query(count,bottom_left) → spatial_query(count,bottom_right) → image_stats(top_left) → image_stats(top_right) → image_stats(bottom_left) |
| D-L3-001 | 2 | `l3_quadrant_most_ships` | 10/10/5 | repeated_call | 3 | 5 | 4 | detect_ships → spatial_query(sizes,top_left) → spatial_query(sizes,top_right) → spatial_query(sizes,bottom_left) → spatial_query(sizes,bottom_right) → calc(argmax) → calc(argmax) → calc(argmax) → calc(argmax) → calc(argmax) |
| D-L3-002 | 2 | `l3_quadrant_most_ships` | 10/10/5 | repeated_call | 3 | 5 | 4 | detect_ships → spatial_query(sizes,top_left) → spatial_query(sizes,top_right) → spatial_query(sizes,bottom_left) → spatial_query(sizes,bottom_right) → calc(argmax) → calc(argmax) → calc(argmax) → calc(argmax) → calc(argmax) |
| D-L3-010 | 2 | `l3_empty_quadrants` | 10/10/5 | termination_failure | 3 | 5 | 0 | get_metadata → detect_ships(top_left) → detect_ships(top_right) → detect_ships(bottom_left) → detect_ships(bottom_right) → calc(count) → calc(count) → calc(count) → calc(count) → calc(count) |
| D-L3-012 | 2 | `l3_quadrant_most_long` | 18/18/9 | repeated_call | 9 | 12 | 3 | get_metadata → detect_ships(top_left) → detect_ships(top_right) → detect_ships(bottom_left) → detect_ships(bottom_right) → spatial_query(sizes,bottom_left) → calc(argmax) → calc(argmax) → calc(argmax) → calc(argmax) → calc(argmax) → calc(argmax) → calc(argmax) → calc(argmax) → calc(argmax) → calc(argmax) → calc(argmax) → calc(argmax) |
| D-L4-003 | 2 | `l4_scene_branch` | 5/5/2 | termination_failure | 1 | 3 | 0 | get_metadata → spatial_query(nearest_pair) → detect_ships → spatial_query(nearest_pair) → detect_ships(edge) |
| D-L4-020 | 2 | `l4_noise_branch` | 5/5/2 | termination_failure | 1 | 2 | 0 | image_stats → detect_ships(edge) → detect_ships → detect_ships(edge) → spatial_query(edge) |
| D-L5-001 | 2 | `l5_noisy_quadrant` | 14/14/7 | repeated_call | 4 | 7 | 4 | get_metadata → image_stats → detect_ships → spatial_query(sizes,top_left) → spatial_query(sizes,top_right) → spatial_query(sizes,bottom_left) → spatial_query(sizes,bottom_right) → calc(argmax) → calc(argmax) → calc(argmax) → calc(argmax) → calc(argmax) → calc(argmax) → calc(argmax) |
| D-L5-003 | 2 | `l5_noisy_quadrant` | 12/12/6 | exploration | 0 | 0 | 2 | get_metadata → image_stats → detect_ships → spatial_query(sizes) → spatial_query(edge) → spatial_query(count,top_left) → spatial_query(count,top_right) → spatial_query(count,bottom_left) → spatial_query(count,bottom_right) → image_stats(top_left) → image_stats(top_right) → image_stats(bottom_left) |
| D-L5-004 | 2 | `l5_scene_quadrant` | 16/16/8 | termination_failure | 2 | 3 | 0 | get_metadata → image_stats(noisiest_region) → detect_ships → spatial_query(sizes,noisiest_region) → image_stats(top_left) → image_stats(top_right) → image_stats(bottom_left) → image_stats(bottom_right) → calc(argmax) → spatial_query(sizes,top_right) → calc(filter) → calc(filter) → calc(argmax) → spatial_query(sizes,top_left) → calc(filter) → calc(argmax) |
