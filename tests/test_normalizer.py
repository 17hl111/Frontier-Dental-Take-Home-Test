# Summary: Unit tests for LLM normalization guard conditions.

from src.agents.llm_normalizer_agent import LLMNormalizerAgent
from src.models import RawProductRecord


class DummyLogger:
    # Minimal logger stub for agent instantiation.
    def info(self, *args, **kwargs):
        pass
    def warning(self, *args, **kwargs):
        pass


def test_should_not_call_llm_without_key():
    # LLM calls should be disabled when no API key is configured.
    agent = LLMNormalizerAgent({"llm": {"enabled": True, "model": "gpt-4o-mini"}, "secrets": {"openai_api_key": ""}}, DummyLogger())
    raw = RawProductRecord(product_url="https://example.com/p", scraped_at="now")
    assert agent.should_call_llm(raw) is False
