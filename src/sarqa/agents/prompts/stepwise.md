## How this conversation works (step by step)

1. First you get the question. Reply with your interpretation: `{"interpretation": {...}}`.
2. Then, in every turn, reply with one JSON object:
   `{"reading": [...], "decision": null or {...}, "action": {...}}`
   where `action` is either
   - a tool call: `{"type": "tool", "tool": "<name>", "args": {...}}` (exactly one call), or
   - the final answer: `{"type": "answer", "answer": <value>, "unit": "<unit>"}`.
3. After each tool call you receive its result (with its id `c<k>`). Read it, fill `reading`, and choose the next action. Loops and if/else are done by you, one call at a time.
4. Give the final answer as soon as you have everything needed. Do not call tools whose results you will not use.

In `reading`, list the values from the latest result that you use later (see "Reading values"). In the first action turn `reading` is `[]`.
