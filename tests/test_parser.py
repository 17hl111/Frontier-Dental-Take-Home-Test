# Summary: Unit tests for basic HTML parsing helpers.

from src.scraping.parser import parse_html, first_text


def test_first_text():
    # Verify selector precedence returns the expected text.
    soup = parse_html("<html><body><h1>Hello</h1></body></html>")
    assert first_text(soup, ["h1"]) == "Hello"
