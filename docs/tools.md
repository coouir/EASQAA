# 도구 명세 (M2, SPEC §5)

에이전트가 쓰는 도구 5개의 호출·출력 JSON과 기하 규칙이다. 구현은 `src/sarqa/tools/`, 정답 풀이 실행기는 `src/sarqa/program.py`.
이 문서의 **인자 목록과 예시 출력은 `tests/test_tools_doc.py`가 구현과 대조한다.** 예시의 `m1.jpg`~`m5.jpg`는 손으로 만든 미니 영상이다(상자는 `tests/tools_fixtures.py`). 규칙을 바꾸면 테스트가 깨지므로 문서와 코드를 함께 고친다(dev에서만 조정, 동결 뒤 수정 금지).

## 1. 공통 규약

- 에이전트는 텍스트만 받는다. 출력은 컴팩트 JSON 문자열(`render`), 키 순서는 아래 예시와 같다.
- 도구는 **결정적**이다. 영상 크기는 800×800, 좌표는 정수 픽셀, 상자는 `x1 <= x < x2`, `y1 <= y < y2` 꼴의 `xyxy`.
- **오류는 예외가 아니라 `{"error": "<도구>: <문장>"}`** 로 돌려준다: 모르는 도구·인자, 빠진 인자, 알 수 없는 영상·영역·선박 id, 값 범위 위반, 도구 내부 오류. 에이전트가 다음 턴에 읽는다.
- **상자 출처는 에이전트가 알 수 없다.** `BoxProvider`(`label | detected | injected | corrected`)가 출처와 무관하게 같은 형식으로 정규화한다: 좌표는 반올림(0.5는 올림) 후 0~800으로 자름, `(y1, x1)` 오름차순 정렬, id `s1, s2, ...`(영상 전체 기준이라 영역·도구가 달라도 같은 상자는 같은 id). 점수는 어떤 출력에도 나오지 않는다.
- 호출 ID는 실행 순서대로 `c1, c2, ...`. 정답 풀이 실행기는 같은 도구 함수를 `label` 출처로 호출한다(별도 구현 없음).

### 참조 (두 방법 공통, SPEC §7.1)

도구 인자에는 값을 직접 쓰거나 앞 호출의 출력 필드를 `$c<k>.<field>`로 참조한다.

| 형태 | 뜻 |
|---|---|
| `"$c3.count"` | 호출 c3 출력의 `count` |
| `"$c2.long_side_px"` | 리스트 필드 전체 (`calc`의 `list`로 넘길 때) |
| `"$c1.ships.0.id"` | 경로의 숫자 조각은 리스트 인덱스 |
| 일괄 계획의 `"$s4.long_side_px"` | 계획 단계 id 참조. 실행할 때 호출 id `c<k>`에 대응시켜 기록 |

- 문자열 전체가 참조일 때만 값으로 바뀐다. `$`로 시작하는데 형식이 틀리면 오류다.
- 없는 호출·필드를 참조하면 **그 호출은 실행되지 않고** `{"error": "..."}`가 그 호출의 출력이 된다(호출 횟수에는 센다). 참조한 호출이 오류를 냈다면 오류 문장이 함께 나온다.
- **최종 답은 참조가 아니라 값으로 적는다.**

### 기하 규칙 (`tools/geometry.py`)

| 항목 | 규칙 |
|---|---|
| 영역 이름 | `full`, `top_left`, `top_right`, `bottom_left`, `bottom_right`, 또는 `[x1, y1, x2, y2]` |
| 상자의 영역 소속 | **상자 중심**이 영역 안. 겹침 비율은 쓰지 않는다 |
| 사분면 경계 | 중심 x < 400 왼쪽, x ≥ 400 오른쪽. y < 400 위, y ≥ 400 아래 (중심이 정확히 400이면 오른쪽·아래) |
| 사용자 지정 영역 | `x1 ≤ cx < x2`, `y1 ≤ cy < y2`. `x1 < x2`, `y1 < y2` 아니면 오류 |
| 가장자리 근처 | 상자 네 변 중 하나가 영상 경계에서 **20 px 이내**(경계 포함: `x1 ≤ 20`, `800−x2 ≤ 20` 등). 기본값, dev에서 확정 |
| 거리 | 상자 중심 사이 유클리드 거리(px), 소수 첫째 자리 반올림 |
| 길이 | 상자 긴 변(px) |
| 동률 | 가장 가까운 쌍이 여럿이면 id 순서가 앞선 쌍. `argmax`/`argmin`은 앞선 항목 |
| 범주형 답 | 사분면 `top_left / top_right / bottom_left / bottom_right`, 장면 `inshore / offshore`, 예·아니오 `yes / no` (최종 답 스키마에서 enum으로 강제) |

## 2. 도구

### 2.1 `detect_ships(image_id, region="full")`

<!--params detect_ships: image_id, region -->

영역 안(중심 기준) 선박 상자 목록. **신뢰도를 반환하지 않는다**(SPEC §5.3, `docs/deviations.md`).

출력: `region`, `count`, `ships[{id, x1, y1, x2, y2}]`.

<!--example {"tool": "detect_ships", "args": {"image_id": "m3.jpg", "region": "bottom_right"}} -->
```json
{"region":"bottom_right","count":1,"ships":[{"id":"s3","x1":600,"y1":600,"x2":640,"y2":620}]}
```

### 2.2 `spatial_query(image_id, query, region="full", ship_a=None, ship_b=None)`

<!--params spatial_query: image_id, query, region, ship_a, ship_b -->

상자는 도구가 `BoxProvider`에서 직접 얻는다(에이전트가 목록을 넘기지 않는다). **호출 한 번에 영역 하나**. 질의가 받지 않는 인자를 주면 오류다.

| `query` | 받는 인자 | 출력 |
|---|---|---|
| `count` | `region` | `query, region, count, ship_ids` |
| `sizes` | `region` | `query, region, count, ships[{id, long_side_px}], long_side_px[]` |
| `distance` | `ship_a`, `ship_b` (필수) | `query, ship_a, ship_b, distance_px` |
| `nearest_pair` | `region` | `query, region, ship_a, ship_b, distance_px` — 영역 안에 2척 미만이면 오류 |
| `nearest_to` | `ship_a` (필수) | `query, ship_a, ship_b, distance_px` — 영상 전체에서 가장 가까운 다른 선박 |
| `edge` | `region` 또는 `ship_a` (동시 불가) | 목록형: `query, region, margin_px, count, ship_ids`. 선박 하나: `query, margin_px, ship_a, near_edge` |

<!--example {"tool": "spatial_query", "args": {"image_id": "m3.jpg", "query": "count", "region": "top_right"}} -->
```json
{"query":"count","region":"top_right","count":1,"ship_ids":["s1"]}
```

<!--example {"tool": "spatial_query", "args": {"image_id": "m3.jpg", "query": "sizes"}} -->
```json
{"query":"sizes","region":"full","count":3,"ships":[{"id":"s1","long_side_px":40},{"id":"s2","long_side_px":60},{"id":"s3","long_side_px":40}],"long_side_px":[40,60,40]}
```

<!--example {"tool": "spatial_query", "args": {"image_id": "m3.jpg", "query": "distance", "ship_a": "s1", "ship_b": "s3"}} -->
```json
{"query":"distance","ship_a":"s1","ship_b":"s3","distance_px":505.0}
```

<!--example {"tool": "spatial_query", "args": {"image_id": "m3.jpg", "query": "nearest_pair"}} -->
```json
{"query":"nearest_pair","region":"full","ship_a":"s1","ship_b":"s3","distance_px":505.0}
```

<!--example {"tool": "spatial_query", "args": {"image_id": "m3.jpg", "query": "nearest_to", "ship_a": "s2"}} -->
```json
{"query":"nearest_to","ship_a":"s2","ship_b":"s3","distance_px":516.2}
```

<!--example {"tool": "spatial_query", "args": {"image_id": "m4.jpg", "query": "edge"}} -->
```json
{"query":"edge","region":"full","margin_px":20,"count":2,"ship_ids":["s1","s4"]}
```

<!--example {"tool": "spatial_query", "args": {"image_id": "m4.jpg", "query": "edge", "ship_a": "s2"}} -->
```json
{"query":"edge","margin_px":20,"ship_a":"s2","near_edge":false}
```

### 2.3 `get_metadata(image_id)`

<!--params get_metadata: image_id -->

HRSID의 연안/외해 파일에서 온 장면 태그. **해상도(m/px)와 센서는 제공하지 않는다**(데이터에 없음, `docs/data_notes.md` §6, 사용자 결정 §16-1). 그래서 거리·길이 질문은 px 단위다. 상자 출처와 무관하다.

출력: `scene` (`inshore | offshore`).

<!--example {"tool": "get_metadata", "args": {"image_id": "m3.jpg"}} -->
```json
{"scene":"inshore"}
```

### 2.4 `image_stats(image_id, region="full")`

<!--params image_stats: image_id, region -->

8비트 그레이 픽셀에서 계산한다. 픽셀 영역은 사각형(사분면은 영상 절반에서 나눔, 사용자 영역은 반올림 후 영상에 맞춰 자름, 영상 밖이면 오류).

- `mean_brightness`: 영역 전체 픽셀의 평균 (소수 2자리)
- `background_noise`: 영역에서 **라벨 상자를 가린** 픽셀의 표준편차 (모집단, 소수 2자리). **입력 상자 조건과 무관하다**(SPEC §5.3). 가릴 배경 픽셀이 없으면 `null`

<!--example {"tool": "image_stats", "args": {"image_id": "m2.jpg", "region": "top_left"}} -->
```json
{"region":"top_left","mean_brightness":50.56,"background_noise":0.0}
```

### 2.5 `calc(op, list, a, b, cmp, threshold, order, labels, expr, vars)`

<!--params calc: op, list, a, b, cmp, threshold, order, labels, expr, vars -->

값 계산 도구. 인자는 이름 있는 평평한 필드이고(SPEC §6.3 예시의 `{"op": "calc", "args": {"op": "max", "list": ...}}`), 연산별로 받는 인자가 정해져 있으며 다른 인자를 주면 오류다. 결과는 `{"op", "result", ...}`, 실수는 소수 4자리로 반올림. 숫자는 `bool`·문자열·`NaN`이 아닌 유한한 수여야 하고 목록은 1000개까지.

| `op` | 인자 | `result` |
|---|---|---|
| `count` | `list` | 길이 |
| `sum`, `mean`, `max`, `min` | `list` | 합·평균·최대·최소 (`mean`, `max`, `min`은 빈 목록이면 오류) |
| `sort` | `list`, `order`(`asc` 기본 \| `desc`) | 정렬된 목록 |
| `filter` | `list`, `cmp`, `threshold` | 조건을 만족하는 값 목록, 추가 필드 `count` |
| `argmax`, `argmin` | `list`, `labels`(선택) | `labels`를 주면 그 라벨, 아니면 0부터의 인덱스. 추가 필드 `index`, `value`. 동률은 앞쪽 |
| `add`, `sub`, `mul`, `div` | `a`, `b` | 사칙 (0으로 나누면 오류) |
| `expr` | `expr`, `vars`(선택) | 산술식 값 |

`cmp`는 `> >= < <= == !=`. **`expr`은 `eval`을 쓰지 않는다.** AST 화이트리스트: 숫자(절댓값 1e9 이하), `+ - * / // %`, 단항 `+ -`, `vars`에 넘긴 변수 이름만 허용한다. 함수 호출·속성·첨자·문자열·비교·논리·거듭제곱·람다·내포·대입식은 모두 오류이고, 식은 200자·노드 60개까지다. **단위 변환 연산은 없다**(영상별 해상도가 없어 모든 길이·거리가 px).

<!--example {"tool": "calc", "args": {"op": "filter", "list": [40, 60, 40], "cmp": ">", "threshold": 40}} -->
```json
{"op":"filter","result":[60],"count":1}
```

<!--example {"tool": "calc", "args": {"op": "argmax", "list": [1, 0, 1, 2], "labels": ["top_left", "top_right", "bottom_left", "bottom_right"]}} -->
```json
{"op":"argmax","result":"bottom_right","index":3,"value":2}
```

<!--example {"tool": "calc", "args": {"op": "expr", "expr": "(a - b) / 2", "vars": {"a": 10, "b": 4}}} -->
```json
{"op":"expr","result":3.0}
```

### 오류 예시

<!--example {"tool": "spatial_query", "args": {"image_id": "m3.jpg", "query": "count", "region": "middle"}} -->
```json
{"error":"spatial_query: unknown region 'middle'; use one of ['full', 'top_left', 'top_right', 'bottom_left', 'bottom_right'] or [x1, y1, x2, y2]"}
```

## 3. 정답 풀이 실행기 (`program.py`, SPEC §6.3)

JSON 프로그램 `{"steps": [...], "answer": ...}`. 단계는 도구 호출 `{"id", "op": <도구>, "args"}`, `if`(`cond: {lhs, cmp, rhs}`, `then`, `else`), `foreach`(`over`: 리스트 또는 참조, `as`: 변수 이름, `do`). 일괄 계획 에이전트(§7.3)가 같은 언어를 쓴다.

- `args`의 `image_id`에 `"IMG"`를 쓰면 실행 대상 영상이다. `$<단계 id>.<필드>`로 앞 단계 출력을 참조한다.
- `foreach` 안에서는 단계 id가 이번 반복의 출력, **루프 뒤에서는 반복 전체의 값 리스트**다(`$s2.count` = 영역별 개수 리스트). 루프 변수는 `$r`, `$ship.x1` 꼴.
- `answer`는 값, 참조, 또는 `{"then": ..., "else": ...}`(`"if": "<단계 id>"`로 어느 `if`인지 지정 가능, 없으면 마지막 최상위 `if`).
- `run_program(program, image_id, box_provider)`는 답과 모든 중간값(`intermediates`), 호출 기록(`calls`), 계획 단계 → 호출 id 대응(`step_calls`), 분기 판정(`decisions`), `gold_calls`, `budget`을 돌려준다. 같은 프로그램을 네 출처에서 다시 실행할 수 있다.
- **`gold_calls`** = 실제로 실행된 도구 호출 수. `calc`·`get_metadata` 포함, `if` 제외, 안 탄 분기 제외, `foreach`는 펼친 횟수. **호출 상한** `budget = max(2 × gold_calls, gold_calls + 3)`.
- 검증 `validate_program`: 알 수 없는 op, 중복 id, 앞에 없는 id 참조, 잘못된 `cmp`·`over`·`as`, 깊이 4 초과를 문제 목록으로 돌려준다.

## 4. 명세와 달라진 점

`docs/deviations.md` 참고. 이 문서 범위에서는 (1) 신뢰도 미반환(§5.3, 명세가 요구한 기록), (2) 해상도·단위 변환 없음(기존 2026-09-29 항목)이다. 그 밖의 세부 결정(질의 이름, `nearest_to`·`edge`의 형태, `calc`의 연산 집합)은 SPEC이 정하지 않은 부분을 이 문서로 확정한 것이다.
