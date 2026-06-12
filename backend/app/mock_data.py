"""Mock data generator — creates 15 suppliers per §6 of the PRD.

Three seed suppliers with forced characteristics:
1. GlobalTech Manufacturing Co — CRITICAL, DETERIORATING
2. Reliable Components Inc — LOW, STABLE
3. Acme Industrial Supplies — MEDIUM→HIGH, DETERIORATING

Plus 12 random suppliers distributed across risk tiers per §6.2.
"""
from __future__ import annotations
import uuid
import random
from datetime import datetime, timezone, timedelta
from faker import Faker
from app.models import (
    Supplier, Alert, RiskLevel, Trend, Dimension, Severity,
)
from app.risk_scorer import (
    compute_financial_score, compute_operational_score,
    compute_compliance_score, compute_geo_score, compute_esg_score,
    compute_overall_score, determine_risk_level, determine_trend,
)

fake = Faker()

# Country risk index per §2.1 — hardcoded for ~20 countries
COUNTRY_RISK_INDEX: dict[str, int] = {
    "US": 15, "DE": 12, "JP": 10, "GB": 14, "FR": 18,
    "CA": 10, "AU": 10, "SE": 8, "CH": 6, "NL": 10,
    "CN": 65, "RU": 80, "IR": 85, "KP": 90, "VE": 85,
    "IN": 45, "BR": 50, "ZA": 55, "NG": 70, "TH": 40,
    "VN": 42, "MX": 48, "ID": 38, "TR": 60, "SA": 45,
}

TRADE_RESTRICTED_COUNTRIES = {country for country, risk in COUNTRY_RISK_INDEX.items() if risk >= 60}

INDUSTRIES = [
    "Manufacturing", "Electronics", "Chemicals", "Automotive",
    "Pharmaceuticals", "Aerospace", "Textiles", "Food & Beverage",
    "Construction", "Energy", "Mining", "Technology",
]


def get_country_risk_index(country: str) -> int:
    """Return risk index for a country, defaulting to 50 if unknown."""
    return COUNTRY_RISK_INDEX.get(country, 50)


def _generate_raw_metrics(risk_multiplier: float = 1.0) -> dict:
    """
    Generate raw underlying metrics that will be fed into risk scorers.
    risk_multiplier: 0.0 (lowest risk) to 1.0 (highest risk).
    """
    # Credit score: 300-850, invert: high multiplier → low credit
    credit_score = max(300, min(850, int(850 - (550 * risk_multiplier) + random.uniform(-50, 50))))
    # Profit margin: -5% to +25%
    profit_margin = max(-5.0, min(25.0, 25.0 - (30.0 * risk_multiplier) + random.uniform(-3, 3)))
    # DSO: 20-120
    dso = max(20, min(120, 20 + (100 * risk_multiplier) + random.uniform(-10, 10)))
    # Debt ratio: 0-1
    debt_ratio = max(0.0, min(1.0, risk_multiplier + random.uniform(-0.15, 0.15)))
    # On-time delivery: 60-99
    otd = max(60, min(99, 99 - (39 * risk_multiplier) + random.uniform(-3, 3)))
    # Defect rate: 0.1-8
    defect = max(0.1, min(8.0, 0.1 + (7.9 * risk_multiplier) + random.uniform(-0.5, 0.5)))
    # Capacity utilization: 30-100
    cap_util = max(30, min(100, 100 - (70 * risk_multiplier) + random.uniform(-5, 5)))
    # Violations
    violations = max(0, int(5 * risk_multiplier + random.choice([0, 0, 0, 1, 1, 2])))
    # Cert expiry: 0-900 days
    cert_expiry = max(1, int(900 - (900 * risk_multiplier) + random.uniform(-30, 30)))
    # Country
    country = random.choice(list(COUNTRY_RISK_INDEX.keys()))
    country_risk = get_country_risk_index(country)
    has_trade_restrictions = country in TRADE_RESTRICTED_COUNTRIES
    # ESG sub-scores
    esg_env = max(5, min(95, 95 * risk_multiplier + random.uniform(-10, 10)))
    esg_soc = max(5, min(95, 95 * risk_multiplier + random.uniform(-10, 10)))
    esg_gov = max(5, min(95, 95 * risk_multiplier + random.uniform(-10, 10)))

    return {
        "credit_score": credit_score,
        "profit_margin": round(profit_margin, 1),
        "dso": round(dso, 1),
        "debt_ratio": round(debt_ratio, 2),
        "on_time_delivery_pct": round(otd, 1),
        "defect_rate_pct": round(defect, 2),
        "capacity_utilization_pct": round(cap_util, 1),
        "violations_last_12mo": violations,
        "cert_expiry_days": cert_expiry,
        "country": country,
        "country_risk_index": country_risk,
        "trade_restrictions": has_trade_restrictions,
        "esg_environmental": round(esg_env, 1),
        "esg_social": round(esg_soc, 1),
        "esg_governance": round(esg_gov, 1),
    }


def _compute_scores_from_metrics(metrics: dict) -> dict:
    """Compute all dimension scores from raw metrics."""
    financial = compute_financial_score(
        credit_score=metrics["credit_score"],
        profit_margin=metrics["profit_margin"],
        dso=metrics["dso"],
        debt_ratio=metrics["debt_ratio"],
    )
    operational = compute_operational_score(
        on_time_delivery_pct=metrics["on_time_delivery_pct"],
        defect_rate_pct=metrics["defect_rate_pct"],
        capacity_utilization_pct=metrics["capacity_utilization_pct"],
    )
    compliance = compute_compliance_score(
        violations_last_12mo=metrics["violations_last_12mo"],
        cert_expiry_days=metrics["cert_expiry_days"],
    )
    geo = compute_geo_score(
        country_risk_index=metrics["country_risk_index"],
        trade_restrictions=metrics["trade_restrictions"],
    )
    esg = compute_esg_score(
        environmental=metrics["esg_environmental"],
        social=metrics["esg_social"],
        governance=metrics["esg_governance"],
    )
    overall = compute_overall_score(
        financial=financial,
        operational=operational,
        compliance=compliance,
        geo=geo,
        esg=esg,
    )
    return {
        "financial_score": financial,
        "operational_score": operational,
        "compliance_score": compliance,
        "geo_score": geo,
        "esg_score": esg,
        "overall_score": overall,
    }


def _generate_history(overall_score: float, days: int = 30, trend_bias: float = 0.0) -> list[float]:
    """Generate 30-day score history with realistic variance and optional trend bias.

    Args:
        overall_score: Current overall score to anchor history end.
        days: Number of history entries (default 30).
        trend_bias: Positive = deteriorating (upward), negative = improving (downward),
                    zero = stable. Each step adds a random walk + this bias.
    """
    history = []
    current = overall_score - (trend_bias * days)  # Start from opposite direction
    for _ in range(days):
        current += trend_bias + random.uniform(-1.5, 1.5)
        current = max(5, min(95, current))
        history.append(round(current, 1))
    return history


def _create_alert(
    supplier_id: str,
    supplier_name: str,
    dimension: Dimension,
    severity: Severity,
    score: float,
) -> Alert:
    """Create an alert object with Gemini-style content (fallback text)."""
    dimension_label = dimension.value.lower().capitalize()
    severity_label = "Critical" if severity == Severity.CRITICAL else "High"

    title = f"{dimension_label} Risk: {severity_label} Level ({score:.0f})"
    message = (
        f"{supplier_name} has triggered a {severity_label.lower()} risk alert in the "
        f"{dimension_label.lower()} dimension with a score of {score:.1f}/100. "
        f"Immediate attention is recommended to mitigate potential supply chain disruption."
    )
    recommendations = [
        f"Review {dimension_label.lower()} metrics and identify root causes of elevated risk.",
        f"Develop a mitigation plan with clear timelines and assigned owners.",
        f"Schedule a review meeting with the supplier to discuss remediation steps.",
    ]
    return Alert(
        alert_id=str(uuid.uuid4()),
        supplier_id=supplier_id,
        supplier_name=supplier_name,
        dimension=dimension,
        severity=severity,
        title=title,
        message=message,
        recommendations=recommendations,
    )


def _check_and_create_alerts(
    scores: dict,
    supplier_id: str,
    supplier_name: str,
) -> list[Alert]:
    """
    Check dimension thresholds per §3.2 and create alerts.

    Dimension-level alerts fire when any individual dimension score
    crosses 65 (HIGH) or 80 (CRITICAL).
    """
    alerts = []
    threshold_config = [
        (Dimension.FINANCIAL, scores["financial_score"]),
        (Dimension.OPERATIONAL, scores["operational_score"]),
        (Dimension.COMPLIANCE, scores["compliance_score"]),
        (Dimension.GEOPOLITICAL, scores["geo_score"]),
        (Dimension.ESG, scores["esg_score"]),
    ]
    for dimension, score in threshold_config:
        if score >= 80:
            alerts.append(_create_alert(
                supplier_id, supplier_name, dimension, Severity.CRITICAL, score
            ))
        elif score >= 65:
            alerts.append(_create_alert(
                supplier_id, supplier_name, dimension, Severity.HIGH, score
            ))
    return alerts


def generate_globaltech() -> Supplier:
    """Generate GlobalTech Manufacturing Co — CRITICAL, DETERIORATING."""
    sid = str(uuid.uuid4())
    metrics = {
        "credit_score": 320,
        "profit_margin": -4.0,
        "dso": 110,
        "debt_ratio": 0.85,
        "on_time_delivery_pct": 65.0,
        "defect_rate_pct": 7.0,
        "capacity_utilization_pct": 95.0,
        "violations_last_12mo": 4,
        "cert_expiry_days": 15,
        "country": "CN",
        "country_risk_index": 65,
        "trade_restrictions": True,
        "esg_environmental": 85,
        "esg_social": 80,
        "esg_governance": 82,
    }
    scores = _compute_scores_from_metrics(metrics)
    history = _generate_history(scores["overall_score"], trend_bias=1.2)

    alerts = _check_and_create_alerts(scores, sid, "GlobalTech Manufacturing Co")

    return Supplier(
        supplier_id=sid,
        name="GlobalTech Manufacturing Co",
        country="CN",
        industry="Manufacturing",
        **scores,
        risk_level=RiskLevel.CRITICAL,
        trend=Trend.DETERIORATING,
        history=history,
        alerts=alerts,
        last_scanned_at=datetime.now(timezone.utc),
    )


def generate_reliable_components() -> Supplier:
    """Generate Reliable Components Inc — LOW, STABLE. All scores ≤ 25."""
    sid = str(uuid.uuid4())
    # Force all dimension scores ≤ 25 by using very good raw metrics
    metrics = {
        "credit_score": 820,
        "profit_margin": 22.0,
        "dso": 25,
        "debt_ratio": 0.15,
        "on_time_delivery_pct": 98.0,
        "defect_rate_pct": 0.3,
        "capacity_utilization_pct": 85.0,
        "violations_last_12mo": 0,
        "cert_expiry_days": 800,
        "country": "DE",
        "country_risk_index": 12,
        "trade_restrictions": False,
        "esg_environmental": 15,
        "esg_social": 10,
        "esg_governance": 12,
    }
    scores = _compute_scores_from_metrics(metrics)
    # Ensure all scores ≤ 25
    scores["financial_score"] = min(scores["financial_score"], 25.0)
    scores["operational_score"] = min(scores["operational_score"], 25.0)
    scores["compliance_score"] = min(scores["compliance_score"], 25.0)
    scores["geo_score"] = min(scores["geo_score"], 25.0)
    scores["esg_score"] = min(scores["esg_score"], 25.0)
    scores["overall_score"] = compute_overall_score(
        scores["financial_score"], scores["operational_score"],
        scores["compliance_score"], scores["geo_score"], scores["esg_score"],
    )

    history = _generate_history(scores["overall_score"])

    return Supplier(
        supplier_id=sid,
        name="Reliable Components Inc",
        country="DE",
        industry="Electronics",
        **scores,
        risk_level=RiskLevel.LOW,
        trend=Trend.STABLE,
        history=history,
        alerts=[],  # No alerts
        last_scanned_at=datetime.now(timezone.utc),
    )


def generate_acme_industrial() -> Supplier:
    """Generate Acme Industrial Supplies — MEDIUM→HIGH, DETERIORATING."""
    sid = str(uuid.uuid4())
    # Score in 55-65 range, ESG > 70
    metrics = {
        "credit_score": 550,
        "profit_margin": 2.0,
        "dso": 85,
        "debt_ratio": 0.50,
        "on_time_delivery_pct": 78.0,
        "defect_rate_pct": 4.0,
        "capacity_utilization_pct": 72.0,
        "violations_last_12mo": 2,
        "cert_expiry_days": 120,
        "country": "IN",
        "country_risk_index": 45,
        "trade_restrictions": False,
        "esg_environmental": 78,
        "esg_social": 72,
        "esg_governance": 75,
    }
    scores = _compute_scores_from_metrics(metrics)
    scores["esg_score"] = max(scores["esg_score"], 72.0)
    scores["overall_score"] = compute_overall_score(
        scores["financial_score"], scores["operational_score"],
        scores["compliance_score"], scores["geo_score"], scores["esg_score"],
    )

    history = _generate_history(scores["overall_score"], trend_bias=0.7)

    alerts = _check_and_create_alerts(scores, sid, "Acme Industrial Supplies")

    return Supplier(
        supplier_id=sid,
        name="Acme Industrial Supplies",
        country="IN",
        industry="Manufacturing",
        **scores,
        risk_level=RiskLevel.HIGH if scores["overall_score"] >= 60 else RiskLevel.MEDIUM,
        trend=Trend.DETERIORATING,
        history=history,
        alerts=alerts,
        last_scanned_at=datetime.now(timezone.utc),
    )


def generate_edge_suppliers() -> list[Supplier]:
    """
    Generate 2 suppliers sitting JUST below HIGH threshold (score ~60-64).
    These have no alerts initially but will trigger an alert on the first
    scanner cycle that pushes any dimension to 65+.
    Perfect for demo — alerts appear within seconds of startup.
    """
    suppliers = []
    for name, industry, country in [
        ("Northern Materials Corp", "Mining", "CA"),
        ("Pacific Logistics Group", "Transportation", "MX"),
    ]:
        sid = str(uuid.uuid4())
        # Set all dimension scores to 58-64 range (just below HIGH threshold)
        scores = {
            "financial_score": round(random.uniform(58, 63), 1),
            "operational_score": round(random.uniform(58, 64), 1),
            "compliance_score": round(random.uniform(58, 63), 1),
            "geo_score": round(random.uniform(58, 63), 1),
            "esg_score": round(random.uniform(58, 64), 1),
        }
        scores["overall_score"] = compute_overall_score(
            scores["financial_score"], scores["operational_score"],
            scores["compliance_score"], scores["geo_score"], scores["esg_score"],
        )
        history = _generate_history(scores["overall_score"], trend_bias=0.3)
        trend = determine_trend(history)
        risk_level = determine_risk_level(scores["overall_score"])
        # No alerts — all dimensions < 65

        supplier = Supplier(
            supplier_id=sid,
            name=name,
            country=country,
            industry=industry,
            **scores,
            risk_level=risk_level,
            trend=trend,
            history=history,
            alerts=[],
            last_scanned_at=datetime.now(timezone.utc),
        )
        suppliers.append(supplier)
    return suppliers


def generate_random_suppliers() -> list[Supplier]:
    """
    Generate 10 random suppliers distributed per §6.2.

    Risk tier distribution:
      LOW:      3 suppliers (score range 10-38)
      MEDIUM:   4 suppliers (score range 40-58)
      HIGH:     2 suppliers (score range 62-73)
      CRITICAL: 1 supplier  (score range 76-95)
    """
    tier_config = [
        ("LOW", 3, (10, 38)),
        ("MEDIUM", 4, (40, 58)),
        ("HIGH", 2, (62, 73)),
        ("CRITICAL", 1, (76, 95)),
    ]

    suppliers = []
    for tier_name, count, score_range in tier_config:
        for _ in range(count):
            sid = str(uuid.uuid4())
            target_overall = random.uniform(*score_range)
            risk_multiplier = target_overall / 100.0
            supplier_name = fake.company()

            metrics = _generate_raw_metrics(risk_multiplier)
            scores = _compute_scores_from_metrics(metrics)

            history = _generate_history(scores["overall_score"])
            trend = determine_trend(history)
            risk_level = determine_risk_level(scores["overall_score"])
            alerts = _check_and_create_alerts(scores, sid, supplier_name)

            supplier = Supplier(
                supplier_id=sid,
                name=supplier_name,
                country=metrics["country"],
                industry=random.choice(INDUSTRIES),
                **scores,
                risk_level=risk_level,
                trend=trend,
                history=history,
                alerts=alerts,
                last_scanned_at=datetime.now(timezone.utc),
            )
            suppliers.append(supplier)

    return suppliers


def generate_suppliers() -> list[Supplier]:
    """Generate all 15 suppliers: 3 seed + 12 random."""
    suppliers = [
        generate_globaltech(),
        generate_reliable_components(),
        generate_acme_industrial(),
    ]
    suppliers.extend(generate_edge_suppliers())
    suppliers.extend(generate_random_suppliers())
    return suppliers
