# dev 문항 검토용 표

문항 문구 검토용 표 (자동 생성: `sarqa questions review`). 문구·어휘·정답 풀이를 확인하고 고칠 곳을 알려 주세요. 정답은 라벨 상자에서 정답 풀이를 실행한 값입니다.

## L1 (18문항)

| qid | 템플릿 | 문구 | 정답 | 단위 | 호출 | 영상 |
|---|---|---|---|---|---|---|
| D-L1-001 | `l1_total_count` | 이 영상에 있는 선박은 모두 몇 척인가? | 3 | ships | 1 | `P0023_4200_5000_6000_6800.jpg` |
| D-L1-002 | `l1_total_count` | 이 영상에 있는 선박은 모두 몇 척인가? | 2 | ships | 1 | `P0021_3600_4400_4200_5000.jpg` |
| D-L1-003 | `l1_total_count` | 이 영상에 있는 선박은 모두 몇 척인가? | 5 | ships | 1 | `P0093_1800_2600_3000_3800.jpg` |
| D-L1-004 | `l1_quadrant_count` | 이 영상의 왼쪽 아래 사분면에 있는 선박은 몇 척인가? | 2 | ships | 1 | `P0011_1800_2600_5400_6200.jpg` |
| D-L1-005 | `l1_quadrant_count` | 이 영상의 왼쪽 위 사분면에 있는 선박은 몇 척인가? | 0 | ships | 1 | `P0096_1200_2000_3600_4400.jpg` |
| D-L1-006 | `l1_quadrant_count` | 이 영상의 왼쪽 아래 사분면에 있는 선박은 몇 척인가? | 1 | ships | 1 | `P0110_4800_5600_9000_9800.jpg` |
| D-L1-007 | `l1_edge_count` | 이 영상에서 상자의 한 변이라도 영상 가장자리에서 20 px 이내에 있는 선박은 몇 척인가? | 1 | ships | 1 | `P0055_1200_2000_4800_5600.jpg` |
| D-L1-008 | `l1_edge_count` | 이 영상에서 상자의 한 변이라도 영상 가장자리에서 20 px 이내에 있는 선박은 몇 척인가? | 2 | ships | 1 | `P0096_0_800_3000_3800.jpg` |
| D-L1-009 | `l1_edge_count` | 이 영상에서 상자의 한 변이라도 영상 가장자리에서 20 px 이내에 있는 선박은 몇 척인가? | 3 | ships | 1 | `P0110_6000_6800_5400_6200.jpg` |
| D-L1-010 | `l1_rect_count` | 이 영상에서 중심이 x 좌표 350~700 px, y 좌표 50~350 px 사각형 안에 있는 선박은 몇 척인가? | 1 | ships | 1 | `P0096_2400_3200_4200_5000.jpg` |
| D-L1-011 | `l1_rect_count` | 이 영상에서 중심이 x 좌표 50~350 px, y 좌표 450~800 px 사각형 안에 있는 선박은 몇 척인가? | 0 | ships | 1 | `P0110_6000_6800_11400_12200.jpg` |
| D-L1-012 | `l1_rect_count` | 이 영상에서 중심이 x 좌표 250~650 px, y 좌표 250~700 px 사각형 안에 있는 선박은 몇 척인가? | 1 | ships | 1 | `P0110_4800_5600_1200_2000.jpg` |
| D-L1-013 | `l1_scene` | 이 영상은 연안(inshore) 장면인가, 외해(offshore) 장면인가? | inshore | none | 1 | `P0093_0_800_1200_2000.jpg` |
| D-L1-014 | `l1_scene` | 이 영상은 연안(inshore) 장면인가, 외해(offshore) 장면인가? | inshore | none | 1 | `P0021_0_800_7800_8600.jpg` |
| D-L1-015 | `l1_scene` | 이 영상은 연안(inshore) 장면인가, 외해(offshore) 장면인가? | offshore | none | 1 | `P0110_6200_7000_6000_6800.jpg` |
| D-L1-016 | `l1_brightness` | 이 영상의 오른쪽 위 사분면의 평균 밝기(0~255)는 얼마인가? | 6.21 | none | 1 | `P0055_600_1400_5900_6700.jpg` |
| D-L1-017 | `l1_brightness` | 이 영상의 왼쪽 아래 사분면의 평균 밝기(0~255)는 얼마인가? | 31.13 | none | 1 | `P0015_0_800_7800_8600.jpg` |
| D-L1-018 | `l1_brightness` | 이 영상의 왼쪽 아래 사분면의 평균 밝기(0~255)는 얼마인가? | 12.46 | none | 1 | `P0102_1800_2600_600_1400.jpg` |

## L2 (22문항)

| qid | 템플릿 | 문구 | 정답 | 단위 | 호출 | 영상 |
|---|---|---|---|---|---|---|
| D-L2-001 | `l2_nearest_ratio` | 가장 가까운 두 선박의 중심 사이 거리는 영상 너비의 몇 %인가? (소수 둘째 자리까지) | 60.15 | percent | 3 | `P0055_1200_2000_4200_5000.jpg` |
| D-L2-002 | `l2_nearest_ratio` | 가장 가까운 두 선박의 중심 사이 거리는 영상 너비의 몇 %인가? (소수 둘째 자리까지) | 18.85 | percent | 3 | `P0011_600_1400_8189_8989.jpg` |
| D-L2-003 | `l2_nearest_ratio` | 가장 가까운 두 선박의 중심 사이 거리는 영상 너비의 몇 %인가? (소수 둘째 자리까지) | 54.325 | percent | 3 | `P0015_4800_5600_2400_3200.jpg` |
| D-L2-004 | `l2_nearest_ratio` | 가장 가까운 두 선박의 중심 사이 거리는 영상 너비의 몇 %인가? (소수 둘째 자리까지) | 78.9625 | percent | 3 | `P0055_600_1400_3000_3800.jpg` |
| D-L2-005 | `l2_nearest_ratio` | 가장 가까운 두 선박의 중심 사이 거리는 영상 너비의 몇 %인가? (소수 둘째 자리까지) | 82.7625 | percent | 3 | `P0068_0_800_5701_6501.jpg` |
| D-L2-006 | `l2_longest_length` | 이 영상에서 가장 긴 선박의 긴 변은 몇 px인가? | 60 | px | 2 | `P0021_3600_4400_4200_5000.jpg` |
| D-L2-007 | `l2_longest_length` | 이 영상에서 가장 긴 선박의 긴 변은 몇 px인가? | 54 | px | 2 | `P0015_3000_3800_3000_3800.jpg` |
| D-L2-008 | `l2_longest_length` | 이 영상에서 가장 긴 선박의 긴 변은 몇 px인가? | 107 | px | 2 | `P0093_1200_2000_3000_3800.jpg` |
| D-L2-009 | `l2_longest_length` | 이 영상에서 가장 긴 선박의 긴 변은 몇 px인가? | 44 | px | 2 | `P0015_5460_6260_6000_6800.jpg` |
| D-L2-010 | `l2_count_over_length` | 이 영상에서 긴 변이 65 px 이상인 선박은 몇 척인가? | 1 | ships | 2 | `P0068_0_800_3000_3800.jpg` |
| D-L2-011 | `l2_count_over_length` | 이 영상에서 긴 변이 45 px 이상인 선박은 몇 척인가? | 1 | ships | 2 | `P0015_1200_2000_8400_9200.jpg` |
| D-L2-012 | `l2_count_over_length` | 이 영상에서 긴 변이 25 px 이상인 선박은 몇 척인가? | 3 | ships | 2 | `P0015_0_800_7800_8600.jpg` |
| D-L2-013 | `l2_count_over_length` | 이 영상에서 긴 변이 70 px 이상인 선박은 몇 척인가? | 2 | ships | 2 | `P0096_0_800_3000_3800.jpg` |
| D-L2-014 | `l2_longest_neighbor` | 가장 긴 선박에서 가장 가까운 다른 선박까지의 중심 사이 거리는 몇 px인가? | 673.8 | px | 4 | `P0110_6000_6800_10800_11600.jpg` |
| D-L2-015 | `l2_longest_neighbor` | 가장 긴 선박에서 가장 가까운 다른 선박까지의 중심 사이 거리는 몇 px인가? | 120.7 | px | 4 | `P0015_0_800_8689_9489.jpg` |
| D-L2-016 | `l2_longest_neighbor` | 가장 긴 선박에서 가장 가까운 다른 선박까지의 중심 사이 거리는 몇 px인가? | 408.6 | px | 4 | `P0055_1200_2000_3000_3800.jpg` |
| D-L2-017 | `l2_longest_neighbor` | 가장 긴 선박에서 가장 가까운 다른 선박까지의 중심 사이 거리는 몇 px인가? | 269.0 | px | 4 | `P0011_0_800_8189_8989.jpg` |
| D-L2-018 | `l2_longest_neighbor` | 가장 긴 선박에서 가장 가까운 다른 선박까지의 중심 사이 거리는 몇 px인가? | 414.9 | px | 4 | `P0102_1800_2600_1200_2000.jpg` |
| D-L2-019 | `l2_longest_shortest_distance` | 가장 긴 선박과 가장 짧은 선박 사이의 중심 거리는 몇 px인가? | 124.9 | px | 5 | `P0015_1200_2000_8689_9489.jpg` |
| D-L2-020 | `l2_longest_shortest_distance` | 가장 긴 선박과 가장 짧은 선박 사이의 중심 거리는 몇 px인가? | 576.6 | px | 5 | `P0068_2000_2800_3600_4400.jpg` |
| D-L2-021 | `l2_longest_shortest_distance` | 가장 긴 선박과 가장 짧은 선박 사이의 중심 거리는 몇 px인가? | 439.7 | px | 5 | `P0068_600_1400_0_800.jpg` |
| D-L2-022 | `l2_longest_shortest_distance` | 가장 긴 선박과 가장 짧은 선박 사이의 중심 거리는 몇 px인가? | 592.7 | px | 5 | `P0055_2400_3200_2400_3200.jpg` |

## L3 (23문항)

| qid | 템플릿 | 문구 | 정답 | 단위 | 호출 | 영상 |
|---|---|---|---|---|---|---|
| D-L3-001 | `l3_quadrant_most_ships` | 네 사분면 중 선박이 가장 많은 사분면은 어디인가? (top_left, top_right, bottom_left, bottom_right 중 하나로 답하라) | top_left | none | 5 | `P0021_1800_2600_8400_9200.jpg` |
| D-L3-002 | `l3_quadrant_most_ships` | 네 사분면 중 선박이 가장 많은 사분면은 어디인가? (top_left, top_right, bottom_left, bottom_right 중 하나로 답하라) | bottom_left | none | 5 | `P0096_2400_3200_1800_2600.jpg` |
| D-L3-003 | `l3_quadrant_most_ships` | 네 사분면 중 선박이 가장 많은 사분면은 어디인가? (top_left, top_right, bottom_left, bottom_right 중 하나로 답하라) | bottom_right | none | 5 | `P0068_600_1400_4800_5600.jpg` |
| D-L3-004 | `l3_quadrant_most_ships` | 네 사분면 중 선박이 가장 많은 사분면은 어디인가? (top_left, top_right, bottom_left, bottom_right 중 하나로 답하라) | top_left | none | 5 | `P0055_1200_2000_4800_5600.jpg` |
| D-L3-005 | `l3_quadrant_most_ships` | 네 사분면 중 선박이 가장 많은 사분면은 어디인가? (top_left, top_right, bottom_left, bottom_right 중 하나로 답하라) | top_left | none | 5 | `P0096_2400_3200_4200_5000.jpg` |
| D-L3-006 | `l3_quadrant_most_ships` | 네 사분면 중 선박이 가장 많은 사분면은 어디인가? (top_left, top_right, bottom_left, bottom_right 중 하나로 답하라) | bottom_left | none | 5 | `P0021_1200_2000_8400_9200.jpg` |
| D-L3-007 | `l3_empty_quadrants` | 선박이 한 척도 없는 사분면은 몇 개인가? | 3 | none | 5 | `P0096_2400_3200_1800_2600.jpg` |
| D-L3-008 | `l3_empty_quadrants` | 선박이 한 척도 없는 사분면은 몇 개인가? | 2 | none | 5 | `P0015_1200_2000_8400_9200.jpg` |
| D-L3-009 | `l3_empty_quadrants` | 선박이 한 척도 없는 사분면은 몇 개인가? | 1 | none | 5 | `P0102_1200_2000_2400_3200.jpg` |
| D-L3-010 | `l3_empty_quadrants` | 선박이 한 척도 없는 사분면은 몇 개인가? | 2 | none | 5 | `P0023_600_1400_8189_8989.jpg` |
| D-L3-011 | `l3_empty_quadrants` | 선박이 한 척도 없는 사분면은 몇 개인가? | 2 | none | 5 | `P0011_1800_2600_3600_4400.jpg` |
| D-L3-012 | `l3_quadrant_most_long` | 긴 변이 20 px 이상인 선박이 가장 많은 사분면은 어디인가? (top_left, top_right, bottom_left, bottom_right 중 하나로 답하라) | bottom_left | none | 9 | `P0093_1800_2600_4200_5000.jpg` |
| D-L3-013 | `l3_quadrant_most_long` | 긴 변이 25 px 이상인 선박이 가장 많은 사분면은 어디인가? (top_left, top_right, bottom_left, bottom_right 중 하나로 답하라) | top_left | none | 9 | `P0110_6200_7000_10200_11000.jpg` |
| D-L3-014 | `l3_quadrant_most_long` | 긴 변이 125 px 이상인 선박이 가장 많은 사분면은 어디인가? (top_left, top_right, bottom_left, bottom_right 중 하나로 답하라) | top_right | none | 9 | `P0093_600_1400_2400_3200.jpg` |
| D-L3-015 | `l3_quadrant_brightest` | 네 사분면 중 평균 밝기가 가장 높은 사분면은 어디인가? (top_left, top_right, bottom_left, bottom_right 중 하나로 답하라) | top_left | none | 5 | `P0068_600_1400_5701_6501.jpg` |
| D-L3-016 | `l3_quadrant_brightest` | 네 사분면 중 평균 밝기가 가장 높은 사분면은 어디인가? (top_left, top_right, bottom_left, bottom_right 중 하나로 답하라) | top_right | none | 5 | `P0015_4200_5000_3000_3800.jpg` |
| D-L3-017 | `l3_quadrant_brightest` | 네 사분면 중 평균 밝기가 가장 높은 사분면은 어디인가? (top_left, top_right, bottom_left, bottom_right 중 하나로 답하라) | top_right | none | 5 | `P0093_2400_3200_3600_4400.jpg` |
| D-L3-018 | `l3_quadrant_brightest` | 네 사분면 중 평균 밝기가 가장 높은 사분면은 어디인가? (top_left, top_right, bottom_left, bottom_right 중 하나로 답하라) | bottom_right | none | 5 | `P0021_600_1400_8400_9200.jpg` |
| D-L3-019 | `l3_quadrant_brightest` | 네 사분면 중 평균 밝기가 가장 높은 사분면은 어디인가? (top_left, top_right, bottom_left, bottom_right 중 하나로 답하라) | top_left | none | 5 | `P0011_4560_5360_7200_8000.jpg` |
| D-L3-020 | `l3_quadrant_noisiest` | 네 사분면 중 배경 잡음 수치가 가장 큰 사분면은 어디인가? (top_left, top_right, bottom_left, bottom_right 중 하나로 답하라) | top_right | none | 5 | `P0011_1200_2000_8189_8989.jpg` |
| D-L3-021 | `l3_quadrant_noisiest` | 네 사분면 중 배경 잡음 수치가 가장 큰 사분면은 어디인가? (top_left, top_right, bottom_left, bottom_right 중 하나로 답하라) | top_right | none | 5 | `P0093_0_800_1200_2000.jpg` |
| D-L3-022 | `l3_quadrant_noisiest` | 네 사분면 중 배경 잡음 수치가 가장 큰 사분면은 어디인가? (top_left, top_right, bottom_left, bottom_right 중 하나로 답하라) | bottom_right | none | 5 | `P0021_5360_6160_6000_6800.jpg` |
| D-L3-023 | `l3_quadrant_noisiest` | 네 사분면 중 배경 잡음 수치가 가장 큰 사분면은 어디인가? (top_left, top_right, bottom_left, bottom_right 중 하나로 답하라) | top_left | none | 5 | `P0015_600_1400_7800_8600.jpg` |

## L4 (22문항)

| qid | 템플릿 | 문구 | 정답 | 단위 | 호출 | 영상 |
|---|---|---|---|---|---|---|
| D-L4-001 | `l4_scene_branch` | 이 영상이 연안(inshore) 장면이면 가장 가까운 두 선박의 중심 사이 거리(px)를, 외해(offshore) 장면이면 가장 긴 선박의 긴 변(px)을 답하라. | 55 | px | 3 | `P0011_2400_3200_3600_4400.jpg` |
| D-L4-002 | `l4_scene_branch` | 이 영상이 연안(inshore) 장면이면 가장 가까운 두 선박의 중심 사이 거리(px)를, 외해(offshore) 장면이면 가장 긴 선박의 긴 변(px)을 답하라. | 57 | px | 3 | `P0068_600_1400_5701_6501.jpg` |
| D-L4-003 | `l4_scene_branch` | 이 영상이 연안(inshore) 장면이면 가장 가까운 두 선박의 중심 사이 거리(px)를, 외해(offshore) 장면이면 가장 긴 선박의 긴 변(px)을 답하라. | 425.6 | px | 2 | `P0093_0_800_0_800.jpg` |
| D-L4-004 | `l4_scene_branch` | 이 영상이 연안(inshore) 장면이면 가장 가까운 두 선박의 중심 사이 거리(px)를, 외해(offshore) 장면이면 가장 긴 선박의 긴 변(px)을 답하라. | 118.1 | px | 2 | `P0015_1800_2600_7800_8600.jpg` |
| D-L4-005 | `l4_count_branch` | 이 영상의 선박이 11척을 초과하면 가장 가까운 두 선박의 중심 사이 거리(px)를, 그렇지 않으면 가장 긴 선박의 긴 변(px)을 답하라. | 67 | px | 3 | `P0102_600_1400_2400_3200.jpg` |
| D-L4-006 | `l4_count_branch` | 이 영상의 선박이 11척을 초과하면 가장 가까운 두 선박의 중심 사이 거리(px)를, 그렇지 않으면 가장 긴 선박의 긴 변(px)을 답하라. | 55 | px | 3 | `P0021_1200_2000_8400_9200.jpg` |
| D-L4-007 | `l4_count_branch` | 이 영상의 선박이 12척을 초과하면 가장 가까운 두 선박의 중심 사이 거리(px)를, 그렇지 않으면 가장 긴 선박의 긴 변(px)을 답하라. | 42 | px | 3 | `P0015_4200_5000_6600_7400.jpg` |
| D-L4-008 | `l4_count_branch` | 이 영상의 선박이 4척을 초과하면 가장 가까운 두 선박의 중심 사이 거리(px)를, 그렇지 않으면 가장 긴 선박의 긴 변(px)을 답하라. | 62.1 | px | 2 | `P0110_6200_7000_6000_6800.jpg` |
| D-L4-009 | `l4_count_branch` | 이 영상의 선박이 3척을 초과하면 가장 가까운 두 선박의 중심 사이 거리(px)를, 그렇지 않으면 가장 긴 선박의 긴 변(px)을 답하라. | 120.7 | px | 2 | `P0015_0_800_8689_9489.jpg` |
| D-L4-010 | `l4_quadrant_branch` | 오른쪽 아래 사분면의 선박이 6척 이상이면 그 사분면에서 가장 긴 선박의 긴 변(px)을, 아니면 영상 전체에서 가장 가까운 두 선박의 중심 사이 거리(px)를 답하라. | 23.7 | px | 2 | `P0093_1200_2000_3000_3800.jpg` |
| D-L4-011 | `l4_quadrant_branch` | 왼쪽 위 사분면의 선박이 5척 이상이면 그 사분면에서 가장 긴 선박의 긴 변(px)을, 아니면 영상 전체에서 가장 가까운 두 선박의 중심 사이 거리(px)를 답하라. | 59.3 | px | 2 | `P0093_0_800_600_1400.jpg` |
| D-L4-012 | `l4_quadrant_branch` | 오른쪽 아래 사분면의 선박이 2척 이상이면 그 사분면에서 가장 긴 선박의 긴 변(px)을, 아니면 영상 전체에서 가장 가까운 두 선박의 중심 사이 거리(px)를 답하라. | 26 | px | 3 | `P0110_6000_6800_5400_6200.jpg` |
| D-L4-013 | `l4_quadrant_branch` | 왼쪽 아래 사분면의 선박이 4척 이상이면 그 사분면에서 가장 긴 선박의 긴 변(px)을, 아니면 영상 전체에서 가장 가까운 두 선박의 중심 사이 거리(px)를 답하라. | 96 | px | 3 | `P0096_1200_2000_3600_4400.jpg` |
| D-L4-014 | `l4_maxlen_branch` | 이 영상에서 가장 긴 선박의 긴 변이 45 px 이상이면 긴 변이 45 px 이상인 선박의 수를, 아니면 전체 선박 수를 답하라. | 4 | ships | 3 | `P0102_1800_2600_3200_4000.jpg` |
| D-L4-015 | `l4_maxlen_branch` | 이 영상에서 가장 긴 선박의 긴 변이 120 px 이상이면 긴 변이 120 px 이상인 선박의 수를, 아니면 전체 선박 수를 답하라. | 3 | ships | 2 | `P0023_600_1400_7800_8600.jpg` |
| D-L4-016 | `l4_maxlen_branch` | 이 영상에서 가장 긴 선박의 긴 변이 30 px 이상이면 긴 변이 30 px 이상인 선박의 수를, 아니면 전체 선박 수를 답하라. | 1 | ships | 3 | `P0021_0_800_7800_8600.jpg` |
| D-L4-017 | `l4_maxlen_branch` | 이 영상에서 가장 긴 선박의 긴 변이 140 px 이상이면 긴 변이 140 px 이상인 선박의 수를, 아니면 전체 선박 수를 답하라. | 6 | ships | 2 | `P0021_600_1400_7200_8000.jpg` |
| D-L4-018 | `l4_maxlen_branch` | 이 영상에서 가장 긴 선박의 긴 변이 150 px 이상이면 긴 변이 150 px 이상인 선박의 수를, 아니면 전체 선박 수를 답하라. | 6 | ships | 2 | `P0102_0_800_2400_3200.jpg` |
| D-L4-019 | `l4_noise_branch` | 이 영상 전체의 배경 잡음 수치가 3.0보다 크면 전체 선박 수를, 그렇지 않으면 가장자리 20 px 이내에 있는 선박 수를 답하라. | 2 | ships | 2 | `P0068_600_1400_0_800.jpg` |
| D-L4-020 | `l4_noise_branch` | 이 영상 전체의 배경 잡음 수치가 14.0보다 크면 전체 선박 수를, 그렇지 않으면 가장자리 20 px 이내에 있는 선박 수를 답하라. | 6 | ships | 2 | `P0096_2400_3200_3600_4400.jpg` |
| D-L4-021 | `l4_noise_branch` | 이 영상 전체의 배경 잡음 수치가 7.0보다 크면 전체 선박 수를, 그렇지 않으면 가장자리 20 px 이내에 있는 선박 수를 답하라. | 0 | ships | 2 | `P0110_6000_6800_11400_12200.jpg` |
| D-L4-022 | `l4_noise_branch` | 이 영상 전체의 배경 잡음 수치가 70.0보다 크면 전체 선박 수를, 그렇지 않으면 가장자리 20 px 이내에 있는 선박 수를 답하라. | 1 | ships | 2 | `P0102_0_800_1800_2600.jpg` |

## L5 (5문항)

| qid | 템플릿 | 문구 | 정답 | 단위 | 호출 | 영상 |
|---|---|---|---|---|---|---|
| D-L5-001 | `l5_noisy_quadrant` | 배경 잡음 수치가 가장 큰 사분면을 찾아라. 그 사분면의 선박이 2척 이상이면 그 사분면에서 긴 변이 100 px 이상인 선박의 수를, 아니면 그 사분면의 선박 수를 답하라. | 0 | ships | 7 | `P0110_5400_6200_9000_9800.jpg` |
| D-L5-002 | `l5_noisy_quadrant` | 배경 잡음 수치가 가장 큰 사분면을 찾아라. 그 사분면의 선박이 6척 이상이면 그 사분면에서 긴 변이 140 px 이상인 선박의 수를, 아니면 그 사분면의 선박 수를 답하라. | 3 | ships | 6 | `P0102_1800_2600_3000_3800.jpg` |
| D-L5-003 | `l5_noisy_quadrant` | 배경 잡음 수치가 가장 큰 사분면을 찾아라. 그 사분면의 선박이 5척 이상이면 그 사분면에서 긴 변이 85 px 이상인 선박의 수를, 아니면 그 사분면의 선박 수를 답하라. | 1 | ships | 6 | `P0055_3000_3800_4200_5000.jpg` |
| D-L5-004 | `l5_scene_quadrant` | 이 영상이 연안(inshore) 장면이면 배경 잡음 수치가 가장 큰 사분면에서, 외해(offshore) 장면이면 선박이 가장 많은 사분면에서 긴 변이 130 px 이상인 선박은 몇 척인가? | 1 | ships | 8 | `P0093_600_1400_2400_3200.jpg` |
| D-L5-005 | `l5_scene_quadrant` | 이 영상이 연안(inshore) 장면이면 배경 잡음 수치가 가장 큰 사분면에서, 외해(offshore) 장면이면 선박이 가장 많은 사분면에서 긴 변이 55 px 이상인 선박은 몇 척인가? | 0 | ships | 8 | `P0110_4800_5600_9000_9800.jpg` |

## 템플릿별 문항 수

| 템플릿 | 문항 수 | 상자 의존 | 분기 |
|---|---|---|---|
| `l1_total_count` | 3 | 예 | 아니오 |
| `l1_quadrant_count` | 3 | 예 | 아니오 |
| `l1_edge_count` | 3 | 예 | 아니오 |
| `l1_rect_count` | 3 | 예 | 아니오 |
| `l1_scene` | 3 | 아니오 | 아니오 |
| `l1_brightness` | 3 | 아니오 | 아니오 |
| `l2_nearest_ratio` | 5 | 예 | 아니오 |
| `l2_longest_length` | 4 | 예 | 아니오 |
| `l2_count_over_length` | 4 | 예 | 아니오 |
| `l2_longest_neighbor` | 5 | 예 | 아니오 |
| `l2_longest_shortest_distance` | 4 | 예 | 아니오 |
| `l3_quadrant_most_ships` | 6 | 예 | 아니오 |
| `l3_empty_quadrants` | 5 | 예 | 아니오 |
| `l3_quadrant_most_long` | 3 | 예 | 아니오 |
| `l3_quadrant_brightest` | 5 | 아니오 | 아니오 |
| `l3_quadrant_noisiest` | 4 | 아니오 | 아니오 |
| `l4_scene_branch` | 4 | 예 | 예 |
| `l4_count_branch` | 5 | 예 | 예 |
| `l4_quadrant_branch` | 4 | 예 | 예 |
| `l4_maxlen_branch` | 5 | 예 | 예 |
| `l4_noise_branch` | 4 | 예 | 예 |
| `l5_noisy_quadrant` | 3 | 예 | 예 |
| `l5_scene_quadrant` | 2 | 예 | 예 |
