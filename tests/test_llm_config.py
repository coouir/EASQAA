from sarqa.agents.llm import OllamaClient
from sarqa.config import load_config


def test_context_length_is_16384_and_reaches_the_requests():
    """Dev prompts reach 7.2k tokens (8.1k in a control run), so 8192 could silently drop the start of a long
    run (docs/context_length.md). The value is frozen at freeze-v1."""
    assert load_config()["llm"]["num_ctx"] == 16384
    assert OllamaClient().options["num_ctx"] == 16384
    assert load_config()["llm"]["num_predict"] <= 2048              # prompt + answer must fit the window with room
