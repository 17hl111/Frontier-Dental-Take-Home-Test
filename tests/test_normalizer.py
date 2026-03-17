"""This module exists to test LLM normalization guard logic. 
It ensures no API key means no LLM call. 
Possible improvement: add tests for merge behavior and structured specs."""

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