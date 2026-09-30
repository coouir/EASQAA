# 예산 초과 사례 분석 (파일럿 A, 조건 1·2)

자동 생성: `python -m sarqa.analysis.budget_cases`. 원인 정의는 모듈 머리말 참고.

## 원인 × 조건

| 원인 | 조건 1 | 조건 2 | 합 |
|---|---|---|---|
| termination_failure | 0 | 4 | 4 |
| repeated_call | 2 | 7 | 9 |
| error_loop | 0 | 0 | 0 |
| exploration | 5 | 4 | 9 |
| other | 0 | 0 | 0 |

## 템플릿별

| 템플릿 | 건수 | 원인 |
|---|---|---|
| `l2_count_over_length` | 2 | {'termination_failure': 2} |
| `l2_longest_neighbor` | 3 | {'exploration': 2, 'repeated_call': 1} |
| `l3_empty_quadrants` | 1 | {'exploration': 1} |
| `l3_quadrant_most_long` | 2 | {'repeated_call': 2} |
| `l3_quadrant_most_ships` | 2 | {'exploration': 1, 'repeated_call': 1} |
| `l4_maxlen_branch` | 1 | {'termination_failure': 1} |
| `l4_quadrant_branch` | 2 | {'repeated_call': 2} |
| `l4_scene_branch` | 1 | {'termination_failure': 1} |
| `l5_noisy_quadrant` | 6 | {'exploration': 3, 'repeated_call': 3} |
| `l5_scene_quadrant` | 2 | {'exploration': 2} |

평균 호출 수: 10.5 (평균 상한 10.5, 평균 gold_calls 5.2)

## 사례

| qid | 조건 | 템플릿 | 호출/상한/gold | 원인 | 반복 | 오류 | 없는 호출 | 호출 순서 |
|---|---|---|---|---|---|---|---|---|
| D-L2-016 | 1 | `l2_longest_neighbor` | 8/8/4 | exploration | 0 | 0 | 1 | detect_ships → spatial_query(sizes) → spatial_query(nearest_pair) → spatial_query(distance,s1,s2) → spatial_query(distance,s1,s3) → spatial_query(distance,s2,s3) → spatial_query(nearest_to,s1) → spatial_query(nearest_to,s2) |
| D-L3-006 | 1 | `l3_quadrant_most_ships` | 10/10/5 | exploration | 0 | 1 | 2 | detect_ships → spatial_query(nearest_pair) → spatial_query(edge) → get_metadata → image_stats → spatial_query(sizes) → calc(argmax) → spatial_query(nearest_to,s3) → spatial_query(count,top_left) → spatial_query(count,top_right) |
| D-L4-012 | 1 | `l4_quadrant_branch` | 6/6/3 | repeated_call | 3 | 4 | 1 | detect_ships(bottom_right) → spatial_query(sizes,bottom_right) → spatial_query(argmax,bottom_right) → spatial_query(argmax,bottom_right) → spatial_query(argmax,bottom_right) → spatial_query(argmax,bottom_right) |
| D-L5-001 | 1 | `l5_noisy_quadrant` | 14/14/7 | exploration | 0 | 2 | 0 | get_metadata → image_stats(top_left) → image_stats(top_right) → image_stats(bottom_left) → image_stats(bottom_right) → detect_ships(noisiest_region) → detect_ships(top_left) → spatial_query(sizes,top_left) → detect_ships(top_right) → spatial_query(sizes,top_right) → detect_ships(bottom_left) → detect_ships(bottom_right) → spatial_query(sizes,bottom_right) → image_stats(noisiest_region) |
| D-L5-002 | 1 | `l5_noisy_quadrant` | 12/12/6 | exploration | 0 | 0 | 0 | get_metadata → image_stats(top_left) → image_stats(top_right) → image_stats(bottom_left) → image_stats(bottom_right) → detect_ships(top_left) → detect_ships(top_right) → detect_ships(bottom_left) → detect_ships(bottom_right) → spatial_query(sizes,top_right) → spatial_query(sizes,bottom_right) → spatial_query(edge,top_right) |
| D-L5-003 | 1 | `l5_noisy_quadrant` | 12/12/6 | repeated_call | 2 | 1 | 1 | get_metadata → image_stats(top_left) → image_stats(top_right) → image_stats(bottom_left) → image_stats(bottom_right) → detect_ships(top_left) → detect_ships(top_right) → detect_ships(bottom_left) → detect_ships(bottom_right) → image_stats(noisiest_region) → image_stats(bottom_right) → image_stats(bottom_left) |
| D-L5-004 | 1 | `l5_scene_quadrant` | 16/16/8 | exploration | 0 | 2 | 0 | get_metadata → image_stats(top_left) → image_stats(top_right) → image_stats(bottom_left) → image_stats(bottom_right) → spatial_query(sizes,noisiest_region) → spatial_query(sizes,top_right) → spatial_query(sizes,bottom_left) → spatial_query(sizes,bottom_right) → spatial_query(sizes,top_left) → spatial_query(sizes) → spatial_query(edge,noisiest_region) → spatial_query(edge,top_right) → spatial_query(edge,bottom_left) → spatial_query(edge,bottom_right) → spatial_query(edge,top_left) |
| D-L2-011 | 2 | `l2_count_over_length` | 5/5/2 | termination_failure | 1 | 3 | 0 | detect_ships → spatial_query(sizes) → calc(count) → calc(count) → calc(count) |
| D-L2-013 | 2 | `l2_count_over_length` | 5/5/2 | termination_failure | 1 | 3 | 0 | detect_ships → spatial_query(sizes) → calc(count) → calc(count) → calc(count) |
| D-L2-016 | 2 | `l2_longest_neighbor` | 8/8/4 | exploration | 0 | 0 | 1 | detect_ships → spatial_query(sizes) → spatial_query(nearest_pair) → spatial_query(distance,s1,s2) → spatial_query(distance,s3,s2) → spatial_query(distance,s1,s3) → spatial_query(nearest_to,s1) → spatial_query(nearest_to,s2) |
| D-L2-018 | 2 | `l2_longest_neighbor` | 8/8/4 | repeated_call | 2 | 0 | 2 | detect_ships → spatial_query(sizes) → spatial_query(nearest_pair) → spatial_query(distance,s3,s1) → spatial_query(distance,s3,s2) → spatial_query(distance,s3,s4) → spatial_query(distance,s3,s1) → spatial_query(distance,s3,s2) |
| D-L3-005 | 2 | `l3_quadrant_most_ships` | 10/10/5 | repeated_call | 9 | 0 | 4 | detect_ships → detect_ships → detect_ships → detect_ships → detect_ships → detect_ships → detect_ships → detect_ships → detect_ships → detect_ships |
| D-L3-008 | 2 | `l3_empty_quadrants` | 10/10/5 | exploration | 0 | 0 | 1 | get_metadata → detect_ships → spatial_query(edge) → spatial_query(nearest_pair) → spatial_query(nearest_to,s1) → spatial_query(nearest_to,s2) → spatial_query(nearest_to,s3) → detect_ships(top_left) → detect_ships(top_right) → detect_ships(bottom_left) |
| D-L3-012 | 2 | `l3_quadrant_most_long` | 18/18/9 | repeated_call | 10 | 11 | 3 | get_metadata → detect_ships(top_left) → detect_ships(top_right) → detect_ships(bottom_left) → detect_ships(bottom_right) → spatial_query(sizes,bottom_left) → spatial_query(count,bottom_left) → spatial_query(argmax,bottom_left) → spatial_query(argmax,bottom_left) → spatial_query(argmax,bottom_left) → spatial_query(argmax,bottom_left) → spatial_query(argmax,bottom_left) → spatial_query(argmax,bottom_left) → spatial_query(argmax,bottom_left) → spatial_query(argmax,bottom_left) → spatial_query(argmax,bottom_left) → spatial_query(argmax,bottom_left) → spatial_query(argmax,bottom_left) |
| D-L3-014 | 2 | `l3_quadrant_most_long` | 18/18/9 | repeated_call | 9 | 10 | 1 | get_metadata → detect_ships(top_left) → spatial_query(sizes,top_left) → detect_ships(top_right) → spatial_query(sizes,top_right) → detect_ships(bottom_left) → detect_ships(bottom_right) → spatial_query(sizes,bottom_right) → spatial_query(argmax,top_left) → spatial_query(argmax,top_left) → spatial_query(argmax,top_left) → spatial_query(argmax,top_left) → spatial_query(argmax,top_left) → spatial_query(argmax,top_left) → spatial_query(argmax,top_left) → spatial_query(argmax,top_left) → spatial_query(argmax,top_left) → spatial_query(argmax,top_left) |
| D-L4-003 | 2 | `l4_scene_branch` | 5/5/2 | termination_failure | 1 | 2 | 0 | get_metadata → detect_ships → spatial_query(nearest_pair) → detect_ships(edge) → detect_ships |
| D-L4-012 | 2 | `l4_quadrant_branch` | 6/6/3 | repeated_call | 3 | 3 | 1 | detect_ships(bottom_right) → spatial_query(sizes,bottom_right) → spatial_query(argmax,bottom_right) → spatial_query(argmax,bottom_right) → spatial_query(argmax,bottom_right) → spatial_query(sizes,bottom_right) |
| D-L4-016 | 2 | `l4_maxlen_branch` | 6/6/3 | termination_failure | 2 | 4 | 0 | detect_ships → spatial_query(sizes) → calc(count) → calc(count) → calc(count) → calc(count) |
| D-L5-001 | 2 | `l5_noisy_quadrant` | 14/14/7 | repeated_call | 3 | 2 | 1 | get_metadata → image_stats(top_left) → image_stats(top_right) → image_stats(bottom_left) → image_stats(bottom_right) → detect_ships(noisiest_region) → detect_ships(top_left) → detect_ships(top_right) → detect_ships(bottom_left) → detect_ships(bottom_right) → image_stats(noisiest_region) → image_stats(top_right) → image_stats(bottom_right) → image_stats(bottom_left) |
| D-L5-002 | 2 | `l5_noisy_quadrant` | 12/12/6 | exploration | 0 | 0 | 0 | get_metadata → image_stats(top_left) → image_stats(top_right) → image_stats(bottom_left) → image_stats(bottom_right) → detect_ships(top_left) → detect_ships(top_right) → detect_ships(bottom_left) → detect_ships(bottom_right) → spatial_query(sizes,top_right) → spatial_query(sizes,bottom_right) → spatial_query(edge,top_right) |
| D-L5-003 | 2 | `l5_noisy_quadrant` | 12/12/6 | repeated_call | 2 | 1 | 1 | get_metadata → image_stats(top_left) → image_stats(top_right) → image_stats(bottom_left) → image_stats(bottom_right) → detect_ships(top_left) → detect_ships(top_right) → detect_ships(bottom_left) → detect_ships(bottom_right) → image_stats(noisiest_region) → image_stats(bottom_right) → image_stats(bottom_left) |
| D-L5-004 | 2 | `l5_scene_quadrant` | 16/16/8 | exploration | 0 | 2 | 0 | get_metadata → image_stats(top_left) → image_stats(top_right) → image_stats(bottom_left) → image_stats(bottom_right) → spatial_query(sizes,noisiest_region) → spatial_query(sizes,top_right) → spatial_query(sizes,bottom_left) → spatial_query(sizes,bottom_right) → spatial_query(sizes,top_left) → spatial_query(sizes) → spatial_query(edge,noisiest_region) → spatial_query(edge,top_right) → spatial_query(edge,bottom_left) → spatial_query(edge,bottom_right) → spatial_query(edge,top_left) |
