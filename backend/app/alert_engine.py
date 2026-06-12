"""Alert engine — threshold detection + OpenRouter (free models) per §3.2 and §3.3.

Replaces deprecated Google Gemini with OpenRouter API using free tier models.
Uses httpx for async HTTP and the openrouter/free router which auto-selects
from available free-tier models.
"""
from __future__ import annotations
import json
import re
import logging
import httpx
from typing import Optional
from app.models import Dimension, Severity

logger = logging.getLogger(__name__)

FALLBACK_TITLE = "Risk Alert Triggered"
FALLBACK_MESSAGE = "A supplier risk threshold has been crossed. Please review the supplier details."
FALLBACK_RECOMMENDATIONS = [
    "Review the affected dimension and assess impact.",
    "Contact the supplier for clarification.",
    "Document the risk and monitor closely.",
]

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
OPENROUTER_MODEL = "openrouter/free"  # Auto-routes to best free model


def should_generate_alert(
    score: float,
    dimension: Dimension,
    supplier_id: str,
    supplier_name: str,
) -> Optional[dict]:
    """
    Check if a dimension score crosses alert threshold per §3.2.

    Returns dict with alert metadata if threshold is crossed, None otherwise.
    """
    if score >= 80:
        return {
            "supplier_id": supplier_id,
            "supplier_name": supplier_name,
            "dimension": dimension,
            "severity": Severity.CRITICAL,
            "score": score,
        }
    elif score >= 65:
        return {
            "supplier_id": supplier_id,
            "supplier_name": supplier_name,
            "dimension": dimension,
            "severity": Severity.HIGH,
            "score": score,
        }
    return None


def check_dimension_thresholds(
    financial: float,
    operational: float,
    compliance: float,
    geo: float,
    esg: float,
    supplier_id: str,
    supplier_name: str,
) -> list[dict]:
    """Check all five dimensions and return list of triggered alert metadata."""
    alerts = []
    dimensions = [
        (Dimension.FINANCIAL, financial),
        (Dimension.OPERATIONAL, operational),
        (Dimension.COMPLIANCE, compliance),
        (Dimension.GEOPOLITICAL, geo),
        (Dimension.ESG, esg),
    ]
    for dimension, score in dimensions:
        result = should_generate_alert(score, dimension, supplier_id, supplier_name)
        if result:
            alerts.append(result)
    return alerts


def generate_alert_prompt(
    supplier_name: str,
    dimension: str,
    score: float,
    severity: str,
    overall_score: float,
) -> list[dict]:
    """
    Build the structured messages array for OpenRouter per §3.3 contract.

    Returns list of message dicts in OpenAI format.
    """
    system_prompt = (
        "You are a supply chain risk analyst. Always respond in valid JSON only. "
        "No markdown fences, no preamble, no explanation outside the JSON."
    )
    user_prompt = f"""A supplier has triggered a risk alert.

Supplier: {supplier_name}
Risk Dimension: {dimension}
Dimension Score: {score:.1f}/100
Severity: {severity}
Overall Risk Score: {overall_score:.1f}/100

Generate a JSON response with the following fields:
- "title": A concise alert headline (max 12 words) for the triggered {dimension} risk dimension.
- "message": Exactly two sentences: (1) what is happening, (2) why it matters to the buyer.
- "recommendations": A JSON array of exactly three short actionable mitigation steps.

Return ONLY valid JSON. No markdown fences, no preamble."""

    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]


def parse_openrouter_response(response_text: str) -> dict:
    """
    Parse OpenRouter response — strip markdown fences and extract JSON.

    Returns dict with title, message, recommendations.
    Falls back to defaults on parse failure.
    """
    if not response_text:
        return _fallback_response()

    # Strip markdown code fences
    cleaned = re.sub(r'```(?:json)?\s*', '', response_text).strip()
    # Also strip any trailing code fence
    cleaned = re.sub(r'\s*```\s*$', '', cleaned).strip()

    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        # Try to find JSON in the response
        json_match = re.search(r'\{.*\}', cleaned, re.DOTALL)
        if json_match:
            try:
                data = json.loads(json_match.group())
            except json.JSONDecodeError:
                logger.warning(f"Failed to parse OpenRouter response as JSON: {cleaned[:200]}")
                return _fallback_response()
        else:
            logger.warning(f"No JSON found in OpenRouter response: {cleaned[:200]}")
            return _fallback_response()

    return {
        "title": data.get("title", FALLBACK_TITLE),
        "message": data.get("message", FALLBACK_MESSAGE),
        "recommendations": data.get("recommendations", FALLBACK_RECOMMENDATIONS),
    }


def _fallback_response() -> dict:
    """Return fallback alert content when LLM is unavailable."""
    return {
        "title": FALLBACK_TITLE,
        "message": FALLBACK_MESSAGE,
        "recommendations": FALLBACK_RECOMMENDATIONS,
    }


class AlertEngine:
    """Alert engine that uses OpenRouter (free tier) for content generation."""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key
        self._http_client: Optional[httpx.AsyncClient] = None
        if api_key:
            self._http_client = httpx.AsyncClient(
                base_url=OPENROUTER_BASE_URL,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": "https://github.com/supplier-risk-scan",
                    "X-Title": "Supplier Risk Scan Agent",
                },
                timeout=30.0,
            )

    async def _call_openrouter(self, messages: list[dict]) -> tuple[str, str]:
        """Make async call to OpenRouter chat completions endpoint.

        Returns (content, model_name) tuple. model_name is empty on failure.
        """
        if not self._http_client:
            return "", ""
        try:
            payload = {
                "model": OPENROUTER_MODEL,
                "messages": messages,
                "response_format": {"type": "json_object"},
            }
            response = await self._http_client.post(
                "/chat/completions",
                json=payload,
            )
            response.raise_for_status()
            data = response.json()
            content = data["choices"][0]["message"]["content"] or ""
            model_used = data.get("model", "") or ""
            return content, model_used
        except httpx.HTTPStatusError as e:
            logger.error(f"OpenRouter API HTTP error: {e.response.status_code} - {e.response.text[:200]}")
            return "", ""
        except Exception as e:
            logger.error(f"OpenRouter API call failed: {e}")
            return "", ""

    async def generate_alert_content(
        self,
        supplier_name: str,
        dimension: str,
        score: float,
        severity: str,
        overall_score: float,
    ) -> dict:
        """
        Generate alert content via OpenRouter or fallback.

        Returns dict with title, message, recommendations, and model info.
        Contains key "ai_model" if content was LLM-generated, empty string otherwise.
        """
        messages = generate_alert_prompt(
            supplier_name=supplier_name,
            dimension=dimension,
            score=score,
            severity=severity,
            overall_score=overall_score,
        )

        if self._http_client:
            response_text, model_used = await self._call_openrouter(messages)
            if response_text:
                result = parse_openrouter_response(response_text)
                result["ai_model"] = model_used
                return result

        fallback = self._generate_fallback_content(
            supplier_name, dimension, score, severity
        )
        fallback["ai_model"] = ""
        return fallback

    def _generate_fallback_content(
        self,
        supplier_name: str,
        dimension: str,
        score: float,
        severity: str,
    ) -> dict:
        """Generate deterministic fallback alert content."""
        dim_label = dimension.lower().capitalize()
        sev_label = "Critical" if severity == "CRITICAL" else "High"
        title = f"{dim_label} Risk: {sev_label} Level ({score:.0f})"
        message = (
            f"{supplier_name} has triggered a {sev_label.lower()} risk alert in the "
            f"{dim_label.lower()} dimension with a score of {score:.1f}/100. "
            f"Immediate attention is recommended to mitigate potential supply chain disruption."
        )
        recommendations = [
            f"Review {dim_label.lower()} metrics and identify root causes.",
            f"Develop a mitigation plan with clear timelines.",
            f"Schedule a review meeting with the supplier.",
        ]
        return {
            "title": title,
            "message": message,
            "recommendations": recommendations,
        }
