# 환경 확인 결과 (M0)

2026-09-29, 이 저장소의 개발 머신에서 직접 실행해 확인한 값이다.

| 항목 | 확인 결과 |
|---|---|
| Python | conda env `easqaa`, Python 3.10.21 (`/home/cvlab/anaconda3/envs/easqaa/bin/python`) |
| Ollama 버전 | 0.34.0 (`GET /api/version`) |
| 모델 | `qwen3:8b`, 다이제스트 `500a1f067a9f` (`/api/tags`), 8.2B, Q4_K_M, capabilities: completion, tools, thinking |
| `format`(JSON 스키마) | 동작. `answer`(integer)·`unit`(enum)을 요구하는 스키마에 대해 스키마를 만족하는 JSON을 받음 (`think` false/true 둘 다) |
| `think` 옵션 | 동작. `think=false`는 응답에 `thinking` 필드 없음, `think=true`는 `thinking` 필드가 있고 출력 토큰이 많음(17 vs 325, 같은 질문) |
| 시드 결정성 | `temperature=0.2, seed=123, num_ctx=8192, think=false`로 같은 요청 3회 → 출력 3회 모두 동일 (1개 프롬프트에 대한 예비 확인). §14 M4 파일럿에서 실제 문항으로 다시 확인한다 |

`format`/`think`를 지원하므로 Ollama 업데이트는 필요 없다.
