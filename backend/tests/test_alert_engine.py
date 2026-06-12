"""Tests for alert engine logic with OpenRouter."""
import pytest
from unittest.mock import AsyncMock, patch
from app.alert_engine import (
    check_dimension_thresholds,
    should_generate_alert,
    generate_alert_prompt,
    parse_openrouter_response,
    AlertEngine,
)
from app.models import Severity, Dimension, RiskLevel


class TestShouldGenerateAlert:
    def test_dimension_high_threshold(self):
        """Dimension score >= 65 triggers HIGH alert."""
        result = should_generate_alert(65, Dimension.FINANCIAL, "sup-1", "Test Corp")
        assert result is not None
        assert result["severity"] == Severity.HIGH

    def test_dimension_critical_threshold(self):
        """Dimension score >= 80 triggers CRITICAL alert."""
        result = should_generate_alert(85, Dimension.FINANCIAL, "sup-1", "Test Corp")
        assert result is not None
        assert result["severity"] == Severity.CRITICAL

    def test_dimension_below_threshold(self):
        """Dimension score < 65 does not trigger alert."""
        result = should_generate_alert(50, Dimension.FINANCIAL, "sup-1", "Test Corp")
        assert result is None

    def test_dimension_at_65_is_high(self):
        result = should_generate_alert(65, Dimension.FINANCIAL, "sup-1", "Test Corp")
        assert result is not None
        assert result["severity"] == Severity.HIGH

    def test_dimension_at_80_is_critical(self):
        result = should_generate_alert(80, Dimension.FINANCIAL, "sup-1", "Test Corp")
        assert result is not None
        assert result["severity"] == Severity.CRITICAL

    def test_operational_dimension(self):
        result = should_generate_alert(70, Dimension.OPERATIONAL, "sup-1", "Test Corp")
        assert result is not None
        assert result["dimension"] == Dimension.OPERATIONAL

    def test_esg_dimension(self):
        result = should_generate_alert(90, Dimension.ESG, "sup-1", "Test Corp")
        assert result is not None
        assert result["dimension"] == Dimension.ESG
        assert result["severity"] == Severity.CRITICAL


class TestCheckDimensionThresholds:
    def test_no_alerts_when_all_below_threshold(self):
        """All scores below 65 -> no alerts."""
        alerts = check_dimension_thresholds(
            financial=40, operational=40, compliance=40, geo=40, esg=40,
            supplier_id="sup-1", supplier_name="Test Corp"
        )
        assert len(alerts) == 0

    def test_alerts_for_high_scores(self):
        """Scores above thresholds generate alerts."""
        alerts = check_dimension_thresholds(
            financial=85, operational=40, compliance=70, geo=40, esg=90,
            supplier_id="sup-1", supplier_name="Test Corp"
        )
        assert len(alerts) == 3
        severities = [a["severity"] for a in alerts]
        assert severities.count(Severity.CRITICAL) == 2
        assert severities.count(Severity.HIGH) == 1

    def test_alert_contains_correct_supplier_info(self):
        alerts = check_dimension_thresholds(
            financial=90, operational=40, compliance=40, geo=40, esg=40,
            supplier_id="sup-1", supplier_name="Test Corp"
        )
        assert len(alerts) == 1
        assert alerts[0]["supplier_id"] == "sup-1"
        assert alerts[0]["supplier_name"] == "Test Corp"
        assert alerts[0]["dimension"] == Dimension.FINANCIAL

    def test_dimension_65_generates_high(self):
        alerts = check_dimension_thresholds(
            financial=65, operational=40, compliance=40, geo=40, esg=40,
            supplier_id="sup-1", supplier_name="Test Corp"
        )
        assert len(alerts) == 1
        assert alerts[0]["severity"] == Severity.HIGH

    def test_dimension_80_generates_critical(self):
        alerts = check_dimension_thresholds(
            financial=80, operational=40, compliance=40, geo=40, esg=40,
            supplier_id="sup-1", supplier_name="Test Corp"
        )
        assert len(alerts) == 1
        assert alerts[0]["severity"] == Severity.CRITICAL

    def test_all_five_dimensions_critical(self):
        alerts = check_dimension_thresholds(
            financial=85, operational=85, compliance=85, geo=85, esg=85,
            supplier_id="sup-1", supplier_name="Test Corp"
        )
        assert len(alerts) == 5
        for a in alerts:
            assert a["severity"] == Severity.CRITICAL


class TestGenerateAlertPrompt:
    def test_prompt_contains_dimension_and_info(self):
        messages = generate_alert_prompt(
            supplier_name="Test Corp",
            dimension="FINANCIAL",
            score=85,
            severity="CRITICAL",
            overall_score=72,
        )
        assert isinstance(messages, list)
        assert len(messages) == 2  # system + user messages
        assert messages[0]["role"] == "system"
        assert messages[1]["role"] == "user"

        user_content = messages[1]["content"]
        assert "Test Corp" in user_content
        assert "FINANCIAL" in user_content
        assert "85" in user_content
        assert "CRITICAL" in user_content
        assert "JSON" in user_content or "json" in user_content
        assert "title" in user_content
        assert "message" in user_content
        assert "recommendations" in user_content

    def test_system_prompt_has_json_instruction(self):
        messages = generate_alert_prompt(
            supplier_name="Test Corp",
            dimension="OPERATIONAL",
            score=70,
            severity="HIGH",
            overall_score=55,
        )
        assert "JSON" in messages[0]["content"] or "json" in messages[0]["content"]

    def test_user_prompt_has_supplier_data(self):
        messages = generate_alert_prompt(
            supplier_name="Acme Inc",
            dimension="COMPLIANCE",
            score=82,
            severity="CRITICAL",
            overall_score=68,
        )
        user = messages[1]["content"]
        assert "Acme Inc" in user
        assert "COMPLIANCE" in user
        assert "82" in user


class TestParseOpenRouterResponse:
    def test_valid_json_response(self):
        response = '{"title": "High Risk Detected", "message": "Financial risk is increasing. This affects supply chain stability.", "recommendations": ["Reduce exposure", "Diversify suppliers", "Increase monitoring"]}'
        result = parse_openrouter_response(response)
        assert result is not None
        assert result["title"] == "High Risk Detected"
        assert len(result["recommendations"]) == 3

    def test_response_with_markdown_fences(self):
        response = '```json\n{"title": "Risk Alert", "message": "Issue detected. Action required.", "recommendations": ["Rec 1", "Rec 2", "Rec 3"]}\n```'
        result = parse_openrouter_response(response)
        assert result is not None
        assert result["title"] == "Risk Alert"

    def test_response_with_code_block(self):
        response = '```\n{"title": "Test", "message": "Message here.", "recommendations": ["A", "B", "C"]}\n```'
        result = parse_openrouter_response(response)
        assert result is not None
        assert result["title"] == "Test"

    def test_invalid_json_returns_fallback(self):
        response = "This is not JSON at all"
        result = parse_openrouter_response(response)
        assert result is not None
        assert "title" in result
        assert "message" in result
        assert "recommendations" in result

    def test_partial_json_returns_fallback(self):
        response = '{"title": "Only title"}'
        result = parse_openrouter_response(response)
        assert result is not None
        assert result["title"] == "Only title"
        assert "message" in result  # fallback message
        assert len(result["recommendations"]) >= 1

    def test_empty_response_returns_fallback(self):
        result = parse_openrouter_response("")
        assert result is not None
        assert result["title"] == "Risk Alert Triggered"

    def test_trailing_code_fence(self):
        response = '{"title": "Clean JSON", "message": "Everything fine.", "recommendations": ["A", "B", "C"]} ```'
        result = parse_openrouter_response(response)
        assert result is not None
        assert result["title"] == "Clean JSON"


class TestAlertEngine:
    @pytest.mark.asyncio
    async def test_generate_alert_content_with_mock_openrouter(self):
        """Test that alert engine processes dimension triggers correctly."""
        engine = AlertEngine(api_key="test-key")

        mock_response = '{"title": "Financial Risk", "message": "Score is high. Take action.", "recommendations": ["Audit finances", "Cut costs", "Monitor cash flow"]}'

        with patch.object(engine, '_call_openrouter', new_callable=AsyncMock, return_value=(mock_response, "test-model")):
            result = await engine.generate_alert_content(
                supplier_name="Test Corp",
                dimension="FINANCIAL",
                score=85,
                severity="CRITICAL",
                overall_score=72,
            )
            assert result is not None
            assert result["title"] == "Financial Risk"
            assert len(result["recommendations"]) == 3
            assert result["ai_model"] == "test-model"

    @pytest.mark.asyncio
    async def test_no_api_key_returns_fallback(self):
        """Without API key, engine should return fallback content."""
        engine = AlertEngine(api_key=None)
        result = await engine.generate_alert_content(
            supplier_name="Test Corp",
            dimension="FINANCIAL",
            score=85,
            severity="CRITICAL",
            overall_score=72,
        )
        assert result is not None
        assert "title" in result
        assert "message" in result
        assert len(result["recommendations"]) >= 1

    @pytest.mark.asyncio
    async def test_openrouter_http_error_returns_fallback(self):
        """When OpenRouter HTTP call fails, engine returns fallback."""
        engine = AlertEngine(api_key="test-key")

        with patch.object(engine, '_call_openrouter', new_callable=AsyncMock, return_value=("", "")):
            result = await engine.generate_alert_content(
                supplier_name="Test Corp",
                dimension="FINANCIAL",
                score=85,
                severity="CRITICAL",
                overall_score=72,
            )
            assert result is not None
            assert "title" in result
            assert "message" in result
            assert result["ai_model"] == ""
