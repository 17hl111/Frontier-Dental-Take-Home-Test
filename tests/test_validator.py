# Summary: Unit tests for product validation rules.

from src.models import NormalizedProduct
from src.agents.validator_agent import ValidatorAgent


class DummyStorage:
    # Pretend there are no successful URLs for dedupe.
    def has_successful_url(self, url: str) -> bool:
        return False


class DummyLogger:
    # Minimal logger stub for agent instantiation.
    def info(self, *args, **kwargs):
        pass


def test_validator_accepts_basic_product():
    # Ensure required fields are enough for a valid record.
    validator = ValidatorAgent(DummyStorage(), DummyLogger())
    product = NormalizedProduct(
        category_path=["Gloves"],
        product_name="Example",
        product_url="https://example.com/product/x",
        scraped_at="2026-01-01T00:00:00Z",
    )
    result = validator.validate(product)
    assert result.is_valid is True
