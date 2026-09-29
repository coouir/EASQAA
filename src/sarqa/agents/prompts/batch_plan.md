## How this conversation works (plan first)

You write the whole plan at once, before seeing any tool result. A program then runs your plan, and you are shown the results afterwards. Reply with one JSON object:
`{"interpretation": {...}, "plan": {"steps": [...], "answer": null}}`

### Plan language

A plan is `{"steps": [...], "answer": null}`. Each step has a unique `id` (`s1`, `s2`, ...) and an `op`:

- a tool call: `{"id": "s1", "op": "get_metadata", "args": {"image_id": "IMG"}}`. Use `"IMG"` as the `image_id` value. `op` is a tool name.
- a condition: `{"id": "s2", "op": "if", "cond": {"lhs": "$s1.scene", "cmp": "==", "rhs": "inshore"}, "then": [steps], "else": [steps]}`. Only the chosen side runs. `cmp` is one of `== != > >= < <=`.
- a loop: `{"id": "s3", "op": "foreach", "over": ["top_left", "top_right", "bottom_left", "bottom_right"], "as": "r", "do": [steps]}`. Inside `do`, `$r` is the current item (`$r.field` for object items). `over` is a list or a reference to a list.

A reference is `$<step id>.<field>`, for example `$s1.scene` or `$s4.long_side_px`. Inside a loop a step id means "this iteration's result"; **after the loop the same id means the list of the results of all iterations** (for example, after a loop whose body step `s4` is a `spatial_query count`, `$s4.count` is the list of the four counts, one per item). References may only point to earlier steps.

You cannot see any result while planning, so plan every step that could be needed; a condition decides at run time which side runs. Keep `"answer": null`; the answer is written afterwards.

### Example (only the form, not a real question)

`{"steps": [{"id": "s1", "op": "get_metadata", "args": {"image_id": "IMG"}}, {"id": "s2", "op": "if", "cond": {"lhs": "$s1.scene", "cmp": "==", "rhs": "inshore"}, "then": [{"id": "s3", "op": "detect_ships", "args": {"image_id": "IMG"}}], "else": [{"id": "s4", "op": "spatial_query", "args": {"image_id": "IMG", "query": "sizes"}}, {"id": "s5", "op": "calc", "args": {"op": "max", "list": "$s4.long_side_px"}}]}], "answer": null}`
