"""Unit tests for HTML collector parsing.

Uses unittest.mock to simulate HTTP responses so tests run
without network access.
"""

import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from collector.taline import get_taline_price, parse_price
from collector.hoorgold import get_hoorgold_price


def test_parse_price_typical():
    """Extract digits from Persian-formatted price."""
    assert parse_price("۱,۸۷۵,۰۰۰") == 1875000.0
    assert parse_price("18,750,000") == 18750000.0
    assert parse_price("18750000") == 18750000.0


def test_parse_price_no_digits():
    """Raise ValueError when no digits found."""
    try:
        parse_price("N/A")
        assert False, "Should have raised ValueError"
    except ValueError as e:
        assert "N/A" in str(e)


def test_taline_success():
    """Taline collector parses valid HTML response."""
    html = """
    <html>
      <body>
        <span class="elementor-heading-title">قیمت ۱گرم طلای ۱۸</span>
        <span class="elementor-heading-title">۱۸,۷۵۰,۰۰۰</span>
      </body>
    </html>
    """
    mock_response = MagicMock()
    mock_response.text = html
    mock_response.raise_for_status = MagicMock()

    with patch("collector.taline.requests.get", return_value=mock_response):
        result = get_taline_price()

    assert result["platform"] == "Taline"
    assert result["price"] == 187500000.0  # *10 for Toman→Rial
    assert "۱۸,۷۵۰,۰۰۰" in result["raw"]


def test_taline_missing_label():
    """Taline raises RuntimeError when 18K label not found."""
    html = "<html><body><span>Other content</span></body></html>"
    mock_response = MagicMock()
    mock_response.text = html
    mock_response.raise_for_status = MagicMock()

    with patch("collector.taline.requests.get", return_value=mock_response):
        try:
            get_taline_price()
            assert False, "Should have raised RuntimeError"
        except RuntimeError as e:
            assert "18K gold price not found" in str(e)


def test_taline_label_no_value():
    """Taline raises RuntimeError when label exists but no following value."""
    html = """
    <html><body>
      <span class="elementor-heading-title">قیمت ۱گرم طلای ۱۸</span>
    </body></html>
    """
    mock_response = MagicMock()
    mock_response.text = html
    mock_response.raise_for_status = MagicMock()

    with patch("collector.taline.requests.get", return_value=mock_response):
        try:
            get_taline_price()
            assert False, "Should have raised RuntimeError"
        except RuntimeError as e:
            assert "value is missing" in str(e)


def test_hoorgold_success_first_selector():
    """HoorGold collector parses HTML with first selector match."""
    html = """
    <html><body>
      <span class="gold-price-18"><span class="gold-cost">18,750,000</span></span>
    </body></html>
    """
    mock_response = MagicMock()
    mock_response.text = html
    mock_response.raise_for_status = MagicMock()

    with patch("collector.hoorgold.requests.get", return_value=mock_response):
        result = get_hoorgold_price()

    assert result["platform"] == "HoorGold"
    assert result["price"] == 187500000.0  # *10 for Toman→Rial


def test_hoorgold_success_fallback_selector():
    """HoorGold falls back to secondary selector when primary missing."""
    html = """
    <html><body>
      <div class="gold-price-18">
        <div class="gold-cost">19,100,000</div>
      </div>
    </body></html>
    """
    mock_response = MagicMock()
    mock_response.text = html
    mock_response.raise_for_status = MagicMock()

    with patch("collector.hoorgold.requests.get", return_value=mock_response):
        result = get_hoorgold_price()

    assert result["platform"] == "HoorGold"
    assert result["price"] == 191000000.0


def test_hoorgold_no_element():
    """HoorGold raises RuntimeError when no price element found."""
    html = "<html><body><p>No gold price here</p></body></html>"
    mock_response = MagicMock()
    mock_response.text = html
    mock_response.raise_for_status = MagicMock()

    with patch("collector.hoorgold.requests.get", return_value=mock_response):
        try:
            get_hoorgold_price()
            assert False, "Should have raised RuntimeError"
        except RuntimeError as e:
            assert "Could not locate" in str(e)


def test_taline_http_error():
    """Taline propagates HTTP errors from requests."""
    mock_response = MagicMock()
    mock_response.raise_for_status.side_effect = Exception("HTTP 503")

    with patch("collector.taline.requests.get", return_value=mock_response):
        try:
            get_taline_price()
            assert False, "Should have raised"
        except Exception as e:
            assert "HTTP 503" in str(e)


if __name__ == "__main__":
    test_parse_price_typical()
    test_parse_price_no_digits()
    test_taline_success()
    test_taline_missing_label()
    test_taline_label_no_value()
    test_hoorgold_success_first_selector()
    test_hoorgold_success_fallback_selector()
    test_hoorgold_no_element()
    test_taline_http_error()
    print("All collector tests passed.")
